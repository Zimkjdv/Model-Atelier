"""One fixed SDXL Canny generation; immutable evidence and GET-only verification."""
import argparse
import copy
import hashlib
from uuid import UUID
from backend import control_workflows as flow
from scripts import install_pony as downloader, verify_local_generation as base
from scripts.verify_illustration_suite import MODELS
CONTROL=downloader.load_manifest(downloader.WORKSPACE/'models'/'controlnet-canny-sdxl-1.0-fp16.json')


def canonical(value):
    if not isinstance(value,str) or str(UUID(value))!=value: raise ValueError('Source ID must be a canonical UUID')
    return value


def checksum(value):
    return isinstance(value,str) and len(value)==64 and all(v in '0123456789abcdef' for v in value)


class ControlAcceptance(base.Acceptance):
    generate_path='control/generate'
    workflow_id=flow.ID
    model_id='pony-v6-xl'
    source_id=None
    def __init__(self,*args,**kwargs):
        self.manifest=MODELS[self.model_id];canonical(self.source_id)
        super().__init__(*args,**kwargs)
        if self.checkpoint!=self.manifest['filename']: raise ValueError('Checkpoint differs from fixed source')
    def expected_settings(self):
        prompt=('score_9,score_8_up,score_7_up,rating_safe,source_anime,' if self.model_id=='pony-v6-xl' else 'masterpiece,best quality,')+'single red wooden chair, empty room, three quarter view, clean illustration, daylight, no humans'
        return base.settings(self.engine,self.checkpoint)|dict(title='Canny GPU acceptance / '+self.model_id,
            prompt=prompt,negative_prompt='people, person, text, watermark, blurry',loras=[],workflow_mode='text2image',
            image_asset_id=self.source_id,reference_ids=[self.source_id],reference_resize='fit',
            control_net_name=CONTROL['filename'],control_strength=0.5,control_start=0,control_end=1,canny_low=0.4,canny_high=0.8)
    def build_workflow(self,settings,job_id=None): return flow.build(settings,job_id)
    def identity(self,item,manifest,control=False):
        expected=dict(name=manifest['filename'],version=manifest['version'],architecture='sdxl',sha256=manifest['sha256'],size_bytes=manifest['size_bytes'])
        if control: expected.update(role='controlnet',kind='canny',source_url=CONTROL['source']['page_url'])
        if not isinstance(item,dict) or any(item.get(k)!=v for k,v in expected.items()): raise ValueError('Fixed weight metadata differs')
    def weight_anchors(self):
        return [dict(name=m['filename'],sha256=m['sha256'],size_bytes=m['size_bytes'],revision=m['source']['revision']) for m in (self.manifest,CONTROL)]
    def preflight(self):
        for manifest in (self.manifest,CONTROL):
            target=downloader._paths(downloader.WORKSPACE,manifest['filename'],create=False)[0]
            if not target.is_file() or not downloader._verified(target,manifest): raise ValueError('Fixed local weight checksum differs: '+manifest['filename'])
        catalog=self.json('GET','models');model=next((m for m in catalog.get('models',[]) if m.get('name')==self.checkpoint),{})
        self.identity(model,self.manifest)
        if catalog.get('engine_url')!=self.engine or catalog.get('sync_error') or model.get('listed') is not True: raise ValueError('Original checkpoint catalog differs')
        controls=self.json('POST','controlnets/sync',json=dict(engine_url=self.engine))
        model=next((m for m in controls.get('controlnets',[]) if m.get('name')==CONTROL['filename']),{})
        self.identity(model|dict(role='controlnet'),CONTROL,True)
        if controls.get('engine_url')!=self.engine or not controls.get('synced_at') or controls.get('sync_error') or model.get('listed') is not True: raise ValueError('Fresh control catalog differs')
        source=next((a for a in self.json('GET','assets') if a.get('id')==self.source_id),{})
        if source.get('archived') or source.get('id')!=self.source_id: raise ValueError('Unavailable source asset')
        self.report['original_assets']=[{k:source[k] for k in ('id','sha256','size','width','height')}]
        self.report['local_weights_verified']=self.weight_anchors()
    def anchors(self,refs,original):
        if not isinstance(refs,list) or len(refs)!=1 or not isinstance(original,list) or len(original)!=1: raise ValueError('Missing one source anchor')
        ref,asset=refs[0],original[0]
        if ref.get('id')!=self.source_id or ref.get('input_role')!='structure' or any(ref.get(k)!=asset.get(k) for k in ('id','sha256','size','width','height')): raise ValueError('Source identity or role differs')
        if any(type(asset.get(k)) is not int or asset[k]<=0 for k in ('size','width','height')) or asset['size']>64*1024*1024 or asset['width']*asset['height']>16_000_000: raise ValueError('Invalid source geometry')
        prep=ref.get('generation_preprocessing',{})
        if prep.get('width')!=768 or prep.get('height')!=768 or prep.get('resize')!='fit' or type(prep.get('version')) is not int or prep['version']!=1 or type(prep.get('size')) is not int or not 0<prep['size']<=64*1024*1024: raise ValueError('Invalid source preprocessing')
        if not checksum(ref.get('sha256')) or not checksum(prep.get('sha256')): raise ValueError('Invalid source checksum')
        control=ref.get('control_preprocessing',{})
        if type(control.get('version')) is not int or any(type(control.get(k)) not in (int,float) for k in ('low_threshold','high_threshold')): raise ValueError('Invalid Canny parameter types')
        if control!=dict(id='comfy-native-canny',version=1,low_threshold=0.4,high_threshold=0.8,execution='original-engine',node_version=None): raise ValueError('Canny preprocessing differs')
    def components(self,item):
        if not isinstance(item,list) or len(item)!=1: raise ValueError('Missing unique control snapshot')
        self.identity(item[0],CONTROL,True)
    def check_snapshots(self,item):
        self.identity(item.get('model_metadata'),self.manifest);self.components(item.get('component_metadata'))
        if item.get('workflow_id')!=self.workflow_id or item.get('reference_settings')!=self.expected_settings() or item.get('lora_metadata'): raise ValueError('Control settings differ')
        self.anchors(item.get('reference_metadata'),self.report['original_assets'])
        for key in ('reference_metadata','component_metadata','model_metadata','runtime_metadata','measurements'):
            if key in self.report and self.report[key]!=item.get(key): raise ValueError('Immutable snapshot changed: '+key)
            if item.get('status')=='completed' or 'image_available' in item: self.report[key]=copy.deepcopy(item.get(key))
    def assert_job(self,item,expected):
        super().assert_job(item,expected);self.check_snapshots(item)
    def validate_report(self,value):
        super().validate_report(value)
        if any(type(value['settings'].get(k)) not in (int,float) for k in ('control_strength','control_start','control_end','canny_low','canny_high')): raise ValueError('Invalid control setting types')
        self.identity(value.get('model_metadata'),self.manifest);self.components(value.get('component_metadata'))
        self.anchors(value.get('reference_metadata'),value.get('original_assets'))
        if value.get('local_weights_verified')!=self.weight_anchors() or not isinstance(value.get('runtime_metadata'),dict) or 'measurements' not in value: raise ValueError('Missing fixed source or environment evidence')
    def verify_artworks(self,expected):
        super().verify_artworks(expected)
        job_id=self.report['job_id'];raw=self.request('GET','jobs/'+job_id+'/reference-image').content
        prep=self.report['reference_metadata'][0]['generation_preprocessing']
        if hashlib.sha256(raw).hexdigest()!=prep['sha256'] or len(raw)!=prep['size']: raise ValueError('Saved processed source checksum differs')
        for kind,ids in (('jobs',[job_id]),('artworks',self.report['artwork_ids'])):
            for identifier in ids:
                if kind=='artworks': self.check_snapshots(self.json('GET',kind+'/'+identifier))
                restored=self.json('GET',kind+'/'+identifier+'/creation-settings')
                if any(restored.get(key)!=self.report[key] for key in ('settings','reference_metadata','component_metadata','runtime_metadata')): raise ValueError('Complete restored control settings or snapshots differ')


def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--model',choices=tuple(MODELS),default='pony-v6-xl');parser.add_argument('--source-id',required=True)
    options,rest=parser.parse_known_args(argv)
    runner=type('FixedControlAcceptance',(ControlAcceptance,),dict(model_id=options.model,source_id=options.source_id))
    return base.main(rest,runner_type=runner,default_checkpoint=MODELS[options.model]['filename'],default_report='runtime/control-'+options.model+'.json')

if __name__=='__main__': raise SystemExit(main())
