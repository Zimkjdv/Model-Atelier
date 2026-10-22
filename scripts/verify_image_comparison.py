"""One fixed img2img comparison variant per invocation; never auto batch or replay."""
import argparse
import copy
import hashlib
import io
from uuid import UUID
from PIL import Image,ImageChops,ImageStat
from backend import image_workflows,experiment_plans
from scripts import install_pony as downloader,verify_local_generation as base
from scripts.verify_illustration_suite import MODELS

DENOISE=(.3,.6)


def baseline(engine,model_id,source_id):
    prefix='score_9,score_8_up,score_7_up,rating_safe,source_anime,' if model_id=='pony-v6-xl' else 'masterpiece,best quality,'
    return base.settings(engine,MODELS[model_id]['filename']) | dict(title='Img2img denoise / '+model_id,
        prompt=prefix+'single red wooden chair, empty room, three quarter view, clean illustration, daylight, no humans',
        negative_prompt='people, person, text, watermark, blurry',loras=[],workflow_mode='image2image',
        image_asset_id=source_id,reference_ids=[source_id],reference_resize='fit',denoise=.3)


def difference(source,result):
    with Image.open(io.BytesIO(source)) as a,Image.open(io.BytesIO(result)) as b:
        a.load();b.load()
        if a.size!=b.size:raise ValueError('Prepared source and result dimensions differ')
        delta=ImageChops.difference(a.convert('RGB'),b.convert('RGB'));channels=delta.split()
        maximum=ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2])
        return dict(scope='RGB change against processed source, not a quality or prompt score',
            changed_pixels=sum(maximum.histogram()[1:]),total_pixels=a.width*a.height,
            mean_absolute_rgb_delta=round(sum(ImageStat.Stat(delta).mean)/3,6),max_channel_delta=maximum.getextrema()[1])


class ImageAcceptance(base.Acceptance):
    model_id='pony-v6-xl'
    source_id=None
    plan_id=None
    denoise=.3
    def __init__(self,*args,**kwargs):
        for identifier in (self.source_id,self.plan_id):
            if not isinstance(identifier,str) or str(UUID(identifier))!=identifier:raise ValueError('Canonical source and plan UUIDs required')
        if self.denoise not in DENOISE:raise ValueError('Unknown fixed denoise profile')
        self.manifest=MODELS[self.model_id]
        super().__init__(*args,**kwargs)
        if self.checkpoint!=self.manifest['filename']:raise ValueError('Pinned checkpoint differs')
    def expected_settings(self):
        settings=baseline(self.engine,self.model_id,self.source_id)
        return settings | dict(denoise=self.denoise,title=(settings['title']+' / 目前提示詞 / denoise='+str(self.denoise))[:100])
    def build_workflow(self,settings,job_id=None):return image_workflows.build(settings,job_id)
    def json(self,method,path,**kwargs):
        if method=='POST' and path==self.generate_path:
            kwargs['json']=kwargs['json'] | dict(experiment=copy.deepcopy(self.report['selection']))
        return super().json(method,path,**kwargs)
    def identity(self,item):
        if not isinstance(item,dict) or any(item.get(k)!=v for k,v in dict(name=self.manifest['filename'],version=self.manifest['version'],architecture='sdxl',sha256=self.manifest['sha256'],size_bytes=self.manifest['size_bytes']).items()):raise ValueError('Pinned model metadata differs')
    def plan(self,record):
        plan=record['plan']
        if record.get('id')!=self.plan_id or plan.get('workflow_id')!='checkpoint-image2image-v1' or plan.get('axis')!='denoise' or plan.get('values')!=list(DENOISE) or plan.get('baseline')!=baseline(self.engine,self.model_id,self.source_id) or plan.get('suite') is not None:raise ValueError('Fixed saved comparison differs')
        expected=[dict(id='variant-'+str(i+1),case_id='current-prompt',value=value,settings=self.expected_settings()|dict(denoise=value,title=(plan['title']+' / 目前提示詞 / denoise='+str(value))[:100])) for i,value in enumerate(DENOISE)]
        if plan.get('variants')!=expected or experiment_plans.digest({k:v for k,v in plan.items() if k not in ('plan_sha256','warnings')})!=plan.get('plan_sha256'):raise ValueError('Plan graph or hash differs')
        return dict(plan_id=self.plan_id,plan_sha256=plan['plan_sha256'],variant_id='variant-'+str(DENOISE.index(self.denoise)+1))
    def preflight(self):
        target=downloader._paths(downloader.WORKSPACE,self.manifest['filename'],create=False)[0]
        if not target.is_file() or not downloader._verified(target,self.manifest):raise ValueError('Pinned local weight verification failed')
        catalog=self.json('GET','models');item=next((v for v in catalog['models'] if v['name']==self.checkpoint),None);self.identity(item)
        record=self.json('GET','experiments/plans/'+self.plan_id)
        if record['archived']:raise ValueError('Plan archived; no new generation')
        self.report['selection']=self.plan(record);self.report['plan']=copy.deepcopy(record['plan'])
        asset=next((v for v in self.json('GET','assets') if v['id']==self.source_id),None)
        if not asset or asset['archived']:raise ValueError('Source unavailable')
        self.report['original_asset']={k:asset[k] for k in ('id','sha256','size','width','height')}
        self.report['weight_anchor']={k:self.manifest[k] for k in ('filename','version','size_bytes','sha256')}
    def check(self,item):
        self.identity(item.get('model_metadata'))
        if item.get('workflow_id')!='checkpoint-image2image-v1' or item.get('reference_settings')!=self.expected_settings() or item.get('lora_metadata'):raise ValueError('Frozen image settings differ')
        refs=item.get('reference_metadata')
        if not isinstance(refs,list) or len(refs)!=1 or any(refs[0].get(k)!=v for k,v in self.report['original_asset'].items()):raise ValueError('Original source anchor differs')
        context=item.get('experiment_context')
        if not isinstance(context,dict) or any(context.get(k)!=v for k,v in self.report['selection'].items()) or context.get('settings')!=self.expected_settings():raise ValueError('Original comparison association differs')
        for key in ('reference_metadata','experiment_context'):
            if key in self.report and self.report[key]!=item.get(key):raise ValueError('Frozen snapshot changed: '+key)
            self.report[key]=copy.deepcopy(item.get(key))
        if item.get('status')=='completed' or item.get('image_available'):
            for key in ('runtime_metadata','measurements'):
                if key in self.report and self.report[key]!=item.get(key):raise ValueError('Frozen performance snapshot changed')
                self.report[key]=copy.deepcopy(item.get(key))
            execution=item.get('runtime_metadata',{}).get('execution_context',{})
            if execution.get('schema_version')!=1 or execution.get('geometry',{}).get('width')!=768 or execution.get('workload')!='inference':raise ValueError('New performance context missing')
    def assert_job(self,item,expected):super().assert_job(item,expected);self.check(item)
    def validate_report(self,value):
        super().validate_report(value)
        if self.plan(dict(id=self.plan_id,plan=value['plan']))!=value.get('selection') or value.get('original_asset',{}).get('id')!=self.source_id:raise ValueError('Report original plan/source differs')
        if value.get('weight_anchor')!={k:self.manifest[k] for k in ('filename','version','size_bytes','sha256')}:raise ValueError('Weight anchor differs')
        if not isinstance(value.get('image_difference'),dict):raise ValueError('Missing image-difference evidence')
    def verify_artworks(self,expected):
        super().verify_artworks(expected)
        job_id=self.report['job_id'];source=self.request('GET','jobs/'+job_id+'/reference-image').content;prep=self.report['reference_metadata'][0]['generation_preprocessing']
        if hashlib.sha256(source).hexdigest()!=prep['sha256'] or len(source)!=prep['size']:raise ValueError('Saved prepared source differs')
        record=self.json('GET','experiments/plans/'+self.plan_id)
        if self.plan(record)!=self.report['selection'] or record['plan']!=self.report['plan']:raise ValueError('Original plan changed')
        results=self.json('GET','experiments/plans/'+self.plan_id+'/results')
        group=next(v for v in results['variants'] if v['variant_id']==self.report['selection']['variant_id'])
        if not any(v['id']==job_id and set(self.report['artwork_ids'])<=set(a['id'] for a in v['artworks']) for v in group['runs']):raise ValueError('Saved results missing original association')
        for identifier in self.report['artwork_ids']:
            item=self.json('GET','artworks/'+identifier);self.check(item)
            metrics=difference(source,self.request('GET','artworks/'+identifier+'/image').content)
            if 'image_difference' in self.report and self.report['image_difference']!=metrics:raise ValueError('Original image-difference metrics changed')
            self.report['image_difference']=metrics


def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--model',choices=tuple(MODELS),default='pony-v6-xl');parser.add_argument('--source-id',required=True);parser.add_argument('--plan-id',required=True)
    parser.add_argument('--denoise',type=float,choices=DENOISE,required=True)
    args,rest=parser.parse_known_args(argv)
    runner=type('FixedImageComparison',(ImageAcceptance,),dict(model_id=args.model,source_id=args.source_id,plan_id=args.plan_id,denoise=args.denoise))
    return base.main(rest,runner_type=runner,default_checkpoint=MODELS[args.model]['filename'],default_report='runtime/image-comparison-'+args.model+'-'+str(args.denoise)+'.json')


if __name__=='__main__':raise SystemExit(main())
