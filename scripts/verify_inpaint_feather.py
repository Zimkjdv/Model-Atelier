"""One fixed inpaint feather case; verify-report uses GET-only durable evidence."""
import argparse
import copy
import hashlib
import io
import math
from PIL import Image,ImageChops,ImageFilter,ImageOps
from backend import inpaint_feather_workflows as flow,control_edges
from scripts import verify_inpaint_generation as old,verify_local_generation as base


def decode(raw):
    if len(raw)>flow.MAX_BYTES: raise ValueError('Image exceeds 32 MiB')
    with Image.open(io.BytesIO(raw)) as image:
        if image.format!='PNG' or image.mode!='RGB' or image.width*image.height>16_000_000 or getattr(image,'n_frames',1)!=1: raise ValueError('Expected bounded RGB PNG')
        image.load();return image.copy()


def feather_metrics(binary_raw,blend_raw,source_raw,result_raw):
    binary,blend,source,result=map(decode,(binary_raw,blend_raw,source_raw,result_raw))
    if len({image.size for image in (binary,blend,source,result)})!=1: raise ValueError('Mask/result geometry differs')
    mask=binary.convert('L');alpha=blend.convert('L')
    if binary.tobytes()!=mask.convert('RGB').tobytes() or sum(mask.histogram()[1:255]) or blend.tobytes()!=alpha.convert('RGB').tobytes(): raise ValueError('Masks must be binary noise and grayscale blend RGB')
    if ImageChops.multiply(alpha,ImageOps.invert(mask)).getextrema()[1]: raise ValueError('Blend leaks into black preserved pixels')
    padded=ImageOps.expand(mask,border=1,fill=0).filter(ImageFilter.MinFilter(3)).crop((1,1,1+mask.width,1+mask.height))
    boundary=ImageChops.subtract(mask,padded);count=boundary.histogram()[255]
    if not count: raise ValueError('No fixed inner boundary pixels')
    channels=ImageChops.difference(source,result).split();delta=ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2]);difference=ImageChops.multiply(delta,boundary);hist=difference.histogram();total=sum(i*n for i,n in enumerate(hist));a=alpha.histogram()
    return dict(scope='Integer max-channel delta from processed source at fixed one-pixel inner binary boundary (8 neighbors); not a seam quality score',
        alpha_zero_pixels=a[0],alpha_opaque_pixels=a[255],alpha_transition_pixels=sum(a[1:255]),outside_alpha_nonzero_pixels=0,
        boundary_pixels=count,boundary_changed_pixels=sum(hist[1:]),boundary_max_delta=difference.getextrema()[1],boundary_sum_delta=total,boundary_mean_delta=round(total/count,6))


class FeatherAcceptance(old.InpaintAcceptance):
    workflow_id=flow.ID
    generate_path='inpaint-feather/generate'
    radius=0
    def expected_settings(self): return super().expected_settings()|dict(title='Feather GPU acceptance / '+self.model_id+' / radius '+str(self.radius),feather_radius=self.radius)
    def build_workflow(self,settings,job_id=None): return flow.build(settings,job_id)
    def preflight(self):
        super().preflight()
        response=self.request('POST','inpaint-feather/preview',json=self.expected_settings());raw=response.content;image=decode(raw)
        if image.size!=(768,768) or response.headers.get('X-Atelier-SHA256')!=hashlib.sha256(raw).hexdigest(): raise ValueError('CPU preview integrity differs')
        self.report['preview_sha256']=hashlib.sha256(raw).hexdigest()
    def check_snapshots(self,item):
        super().check_snapshots(item)
        # Artwork summaries omit the full graph; read its dedicated endpoint.
        graph=item.get('workflow')
        if graph is None: graph=self.json('GET','artworks/'+item['id']+'/workflow')
        flow.extract(dict(item,workflow=graph,source=item.get('source') or dict(node_id='7')),lambda value:value)
    def assert_job(self,item,expected):
        super().assert_job(item,expected)
        if control_edges.digest(item['workflow'])!=control_edges.digest(expected): raise ValueError('Full serialized feather workflow differs')
    def validate_report(self,value):
        super().validate_report(value)
        if type(value['settings'].get('feather_radius')) is not int or value['settings']['feather_radius']!=self.radius: raise ValueError('Invalid feather radius')
        item=dict(value,id=value['job_id'],workflow_id=flow.ID,checkpoint=self.checkpoint,engine_url=self.engine,reference_settings=value['settings'],source=dict(node_id='7'))
        flow.extract(item,lambda v:v)
        if control_edges.digest(value['workflow'])!=control_edges.digest(self.build_workflow(value['settings'],value['job_id'])): raise ValueError('Feather workflow JSON types differ')
        prep=value['reference_metadata'][1]['blend_preprocessing'];proof=value['blend_mask_proof'];metric=value['feather_metrics']
        if (not isinstance(proof,dict) or any(proof.get(k)!=prep.get(v) for k,v in dict(sha256='sha256',size_bytes='size',width='width',height='height',binary_sha256='binary_sha256').items()) or value.get('preview_sha256')!=prep['sha256'] or not isinstance(proof.get('decoded_luma_sha256'),str) or len(proof['decoded_luma_sha256'])!=64 or any(v not in '0123456789abcdef' for v in proof['decoded_luma_sha256'])): raise ValueError('Blend PNG/preview integrity proof differs')
        keys=('alpha_zero_pixels','alpha_opaque_pixels','alpha_transition_pixels','outside_alpha_nonzero_pixels','boundary_pixels','boundary_changed_pixels','boundary_max_delta','boundary_sum_delta')
        if not isinstance(metric,dict) or any(type(metric.get(k)) is not int for k in keys) or any(metric[k]<0 for k in keys) or sum(metric[k] for k in keys[:3])!=768*768 or metric['outside_alpha_nonzero_pixels']!=0 or not 0<metric['boundary_pixels']<=value['mask_metrics']['edited_pixels'] or metric['boundary_changed_pixels']>metric['boundary_pixels'] or metric['boundary_max_delta']>255 or metric['boundary_sum_delta']>metric['boundary_pixels']*255: raise ValueError('Invalid alpha/boundary metrics')
        if type(metric.get('boundary_mean_delta')) not in (float,int) or not math.isfinite(metric['boundary_mean_delta']) or metric['boundary_mean_delta']!=round(metric['boundary_sum_delta']/metric['boundary_pixels'],6) or (self.radius==0 and metric['alpha_transition_pixels']): raise ValueError('Invalid boundary mean or zero-radius alpha')
    def verify_artworks(self,expected):
        super().verify_artworks(expected)
        job_id=self.report['job_id'];prefix='jobs/'+job_id
        source=self.request('GET',prefix+'/reference-image').content;binary=self.request('GET',prefix+'/reference-mask').content;blend=self.request('GET',prefix+'/reference-blend-mask').content
        prep=self.report['reference_metadata'][1]['blend_preprocessing'];image=decode(blend)
        if hashlib.sha256(blend).hexdigest()!=prep['sha256'] or len(blend)!=prep['size'] or self.report['preview_sha256']!=prep['sha256']: raise ValueError('Saved blend bytes differ from immutable snapshot or original CPU preview')
        proof=dict(sha256=prep['sha256'],size_bytes=len(blend),width=image.width,height=image.height,binary_sha256=prep['binary_sha256'],decoded_luma_sha256=hashlib.sha256(image.convert('L').tobytes()).hexdigest())
        if 'blend_mask_proof' in self.report and self.report['blend_mask_proof']!=proof: raise ValueError('Original blend proof changed')
        metrics=feather_metrics(binary,blend,source,self.request('GET','artworks/'+self.report['artwork_ids'][0]+'/image').content)
        if 'feather_metrics' in self.report and self.report['feather_metrics']!=metrics: raise ValueError('Original blend metrics changed')
        self.report['blend_mask_proof']=copy.deepcopy(proof);self.report['feather_metrics']=metrics


def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--model',choices=tuple(old.MODELS),default='pony-v6-xl');parser.add_argument('--radius',type=int,choices=(0,16),required=True)
    parser.add_argument('--source-id',required=True);parser.add_argument('--mask-id',required=True)
    options,rest=parser.parse_known_args(argv)
    runner=type('FixedFeather',(FeatherAcceptance,),dict(model_id=options.model,source_id=options.source_id,mask_id=options.mask_id,radius=options.radius))
    return base.main(rest,runner_type=runner,default_checkpoint=old.MODELS[options.model]['filename'],default_report='runtime/inpaint-feather-'+options.model+'-'+str(options.radius)+'.json')

if __name__=='__main__': raise SystemExit(main())
