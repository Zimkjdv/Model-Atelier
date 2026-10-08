"""One pinned checkpoint inpaint; durable original inputs and GET-only recovery."""
import argparse
import copy
import hashlib
import io
from uuid import UUID
from PIL import Image, ImageChops, ImageOps
from backend import inpaint_workflows
from scripts import install_pony as downloader, verify_local_generation as base
from scripts.verify_illustration_suite import MODELS


def canonical(value):
    if not isinstance(value,str) or str(UUID(value))!=value: raise ValueError('Asset ID must be a canonical UUID')
    return value


def mask_metrics(source_raw,mask_raw,result_raw):
    def decode(raw):
        if len(raw)>64*1024*1024: raise ValueError('Input image bytes exceed limit')
        with Image.open(io.BytesIO(raw)) as image:
            if image.width*image.height>16_000_000 or getattr(image,'n_frames',1)!=1: raise ValueError('Image dimensions exceed limits')
            image.load();return image.convert('RGB')
    source,mask,result=map(decode,(source_raw,mask_raw,result_raw))
    if source.size!=mask.size or result.size!=source.size: raise ValueError('Processed image dimensions differ')
    gray=mask.convert('L');hist=gray.histogram()
    if sum(hist[1:255]) or any(ImageChops.difference(mask,gray.convert('RGB')).getextrema()[i][1] for i in range(3)): raise ValueError('Saved mask is not binary RGB')
    if not hist[0] or not hist[255]: raise ValueError('This preservation acceptance needs both edited and preserved pixels')
    channels=ImageChops.difference(source,result).split();delta=ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2])
    outside=ImageChops.multiply(delta,ImageOps.invert(gray));inside=ImageChops.multiply(delta,gray)
    values=dict(scope='Decoded RGB difference against saved processed source; per-pixel maximum channel delta, not original-file byte identity',
        preserved_pixels=hist[0],edited_pixels=hist[255],outside_max_delta=outside.getextrema()[1],outside_changed_pixels=sum(outside.histogram()[1:]),inside_changed_pixels=sum(inside.histogram()[1:]),inside_max_delta=inside.getextrema()[1])
    if values['outside_max_delta']>1: raise ValueError('Pixels outside the mask changed by more than one RGB level')
    if not values['inside_changed_pixels']: raise ValueError('No change observed inside the mask')
    return values


class InpaintAcceptance(base.Acceptance):
    generate_path='inpaint/generate'
    model_id='pony-v6-xl'
    source_id=None
    mask_id=None
    def __init__(self,*args,**kwargs):
        self.manifest=MODELS[self.model_id]
        canonical(self.source_id);canonical(self.mask_id)
        if self.source_id==self.mask_id: raise ValueError('Source and mask must differ')
        super().__init__(*args,**kwargs)
        if self.checkpoint!=self.manifest['filename']: raise ValueError('Checkpoint must match pinned model')
    def expected_settings(self):
        return base.settings(self.engine,self.checkpoint)|dict(title='Inpaint GPU acceptance / '+self.model_id,
            prompt='landscape, mountain lake, single red wooden boat floating on the lake, pine forest, daylight, no humans',
            negative_prompt='people, person, text, watermark, blurry',loras=[],workflow_mode='image2image',
            image_asset_id=self.source_id,mask_asset_id=self.mask_id,reference_ids=[self.source_id,self.mask_id],reference_resize='fit',grow_mask_by=6)
    def build_workflow(self,settings,job_id=None): return inpaint_workflows.build(settings,job_id)
    def identity(self,item):
        expected=dict(name=self.manifest['filename'],version=self.manifest['version'],architecture='sdxl',sha256=self.manifest['sha256'],size_bytes=self.manifest['size_bytes'])
        if not isinstance(item,dict) or any(item.get(k)!=v for k,v in expected.items()): raise ValueError('Pinned checkpoint metadata differs')
    def preflight(self):
        path,_,_,_=downloader._paths(downloader.WORKSPACE,self.manifest['filename'],create=False)
        if not path.is_file() or not downloader._verified(path,self.manifest): raise ValueError('Pinned local weights size/SHA256 failed')
        catalog=self.json('GET','models');model=next((m for m in catalog.get('models',[]) if m.get('name')==self.checkpoint),None)
        self.identity(model)
        if catalog.get('engine_url')!=self.engine or catalog.get('sync_error') or model.get('listed') is not True: raise ValueError('Fresh original-engine catalog required')
        library=self.json('GET','assets')
        original=[next((a for a in library if a.get('id')==identifier),{}) for identifier in (self.source_id,self.mask_id)]
        if any(item.get('id')!=identifier or item.get('archived') for item,identifier in zip(original,(self.source_id,self.mask_id))): raise ValueError('Unavailable source or mask')
        if (original[0]['width'],original[0]['height'])!=(original[1]['width'],original[1]['height']): raise ValueError('Source/mask geometry differs')
        self.report['original_assets']=[{k:item[k] for k in ('id','sha256','size','width','height')} for item in original]
        self.report['local_weights_verified']=[dict(name=self.manifest['filename'],sha256=self.manifest['sha256'],size_bytes=self.manifest['size_bytes'])]
    def check_snapshots(self,item):
        self.identity(item.get('model_metadata'))
        refs=item.get('reference_metadata')
        if (item.get('workflow_id')!=inpaint_workflows.ID or item.get('lora_metadata') or item.get('reference_settings')!=self.expected_settings()
            or not isinstance(refs,list) or len(refs)!=2 or [r.get('input_role') for r in refs]!=['source','mask']): raise ValueError('Inpaint settings or dual snapshots differ')
        for ref,original in zip(refs,self.report['original_assets']):
            if any(ref.get(k)!=v for k,v in original.items()): raise ValueError('Original asset identity changed')
            prep=ref['generation_preprocessing']
            if (prep['width'],prep['height'])!=(768,768) or prep['resize']!='fit' or prep['version']!=1: raise ValueError('Preprocessing snapshot differs')
        mask=refs[1]['generation_preprocessing']
        if any(mask.get(k)!=v for k,v in dict(threshold=128,white='edit',black='preserve',resampling='NEAREST',output_mode='RGB').items()): raise ValueError('Mask policy changed')
        for key in ('reference_metadata','model_metadata','runtime_metadata','measurements'):
            if key in self.report and self.report[key]!=item.get(key): raise ValueError('Immutable snapshot changed: '+key)
            if item.get('status')=='completed' or 'image_available' in item: self.report[key]=copy.deepcopy(item.get(key))
    def assert_job(self,item,expected):
        super().assert_job(item,expected);self.check_snapshots(item)
    def validate_report(self,value):
        super().validate_report(value)
        self.identity(value.get('model_metadata'))
        refs=value.get('reference_metadata');original=value.get('original_assets')
        if not isinstance(refs,list) or len(refs)!=2 or not isinstance(original,list) or len(original)!=2: raise ValueError('Missing dual-input anchors')
        if [r.get('id') for r in refs]!=[self.source_id,self.mask_id] or [r.get('id') for r in original]!=[self.source_id,self.mask_id]: raise ValueError('Input IDs differ')
        if [r.get('input_role') for r in refs]!=['source','mask'] or (original[0]['width'],original[0]['height'])!=(original[1]['width'],original[1]['height']): raise ValueError('Input roles or geometry invalid')
        if not isinstance(value.get('runtime_metadata'),dict) or 'measurements' not in value: raise ValueError('Missing immutable environment anchors')
        for ref,asset in zip(refs,original):
            if any(ref.get(k)!=asset.get(k) for k in ('id','sha256','size','width','height')): raise ValueError('Input anchor differs')
            prep=ref.get('generation_preprocessing',{})
            if any(type(asset.get(k)) is not int or asset[k]<=0 for k in ('width','height','size')) or asset['width']*asset['height']>16_000_000 or asset['size']>64*1024*1024: raise ValueError('Input dimensions or size invalid')
            if prep.get('width')!=768 or prep.get('height')!=768 or prep.get('resize')!='fit' or type(prep.get('version')) is not int or prep['version']!=1 or type(prep.get('size')) is not int or not 0<prep['size']<=64*1024*1024: raise ValueError('Preprocessing anchor invalid')
            for digest in (ref.get('sha256'),prep.get('sha256')):
                if not isinstance(digest,str) or len(digest)!=64 or any(v not in '0123456789abcdef' for v in digest): raise ValueError('Input checksum invalid')
        mask=refs[1]['generation_preprocessing']
        if any(mask.get(k)!=v for k,v in dict(threshold=128,white='edit',black='preserve',resampling='NEAREST',output_mode='RGB').items()): raise ValueError('Invalid mask policy anchor')
        metric=value.get('mask_metrics')
        fields=('preserved_pixels','edited_pixels','outside_max_delta','outside_changed_pixels','inside_changed_pixels','inside_max_delta')
        if not isinstance(metric,dict) or any(type(metric.get(k)) is not int for k in fields): raise ValueError('Missing preservation evidence')
        if (metric['preserved_pixels']<=0 or metric['edited_pixels']<=0 or metric['preserved_pixels']+metric['edited_pixels']!=768*768
            or metric['outside_max_delta'] not in (0,1) or not 0<=metric['outside_changed_pixels']<=metric['preserved_pixels']
            or not 0<metric['inside_changed_pixels']<=metric['edited_pixels'] or not 0<metric['inside_max_delta']<=255): raise ValueError('Invalid preservation measurements')
    def verify_artworks(self,expected):
        super().verify_artworks(expected)
        job_id=self.report['job_id'];job=self.json('GET','jobs/'+job_id)
        source=self.request('GET','jobs/'+job_id+'/reference-image').content
        mask=self.request('GET','jobs/'+job_id+'/reference-mask').content
        for raw,ref in zip((source,mask),self.report['reference_metadata']):
            prep=ref['generation_preprocessing']
            if prep['sha256']!=hashlib.sha256(raw).hexdigest() or prep['size']!=len(raw): raise ValueError('Saved processed input checksum differs')
        restored_job=self.json('GET','jobs/'+job_id+'/creation-settings')
        if restored_job.get('settings')!=self.report['settings'] or restored_job.get('reference_metadata')!=self.report['reference_metadata']: raise ValueError('Original terminal job settings differ')
        for identifier in self.report['artwork_ids']:
            item=self.json('GET','artworks/'+identifier);self.check_snapshots(item)
            restored=self.json('GET','artworks/'+identifier+'/creation-settings')
            if restored.get('reference_metadata')!=self.report['reference_metadata'] or restored.get('runtime_metadata')!=job.get('runtime_metadata'): raise ValueError('Restored immutable snapshots differ')
            metrics=mask_metrics(source,mask,self.request('GET','artworks/'+identifier+'/image').content)
            if 'mask_metrics' in self.report and self.report['mask_metrics']!=metrics: raise ValueError('Original preservation measurements changed')
            self.report['mask_metrics']=metrics


def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--model',choices=tuple(MODELS),default='pony-v6-xl')
    parser.add_argument('--source-id',required=True);parser.add_argument('--mask-id',required=True)
    options,rest=parser.parse_known_args(argv)
    runner=type('FixedInpaintAcceptance',(InpaintAcceptance,),dict(model_id=options.model,source_id=options.source_id,mask_id=options.mask_id))
    return base.main(rest,runner_type=runner,default_checkpoint=MODELS[options.model]['filename'],default_report='runtime/inpaint-'+options.model+'.json')

if __name__=='__main__': raise SystemExit(main())
