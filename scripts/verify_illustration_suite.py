"""One pinned model/case per invocation; bounded GPU acceptance, never auto replay."""
import argparse
import copy
from backend import experiment_plans
from scripts import install_model, install_pony as downloader, verify_local_generation as base

MODELS={name:install_model.manifest(name) for name in ('pony-v6-xl','animagine-xl-4.0-opt')}
CASES=('chair','lake','traveler-bookshop','traveler-station')

def settings(engine, checkpoint, case):
    return base.settings(engine,checkpoint) | dict(title='Illustration suite v1 / '+case['id'],
        prompt=case['prompt'],negative_prompt='blurry, low quality, text, watermark',
        width=1024,height=1024,steps=28,cfg=5.0,sampler_name='euler_ancestral',scheduler='normal',loras=[])

class SuiteAcceptance(base.Acceptance):
    model_id='animagine-xl-4.0-opt'
    case_id='chair'
    def __init__(self,*args,**kwargs):
        self.manifest=MODELS[self.model_id]
        self.suite=experiment_plans.suite()
        self.case=next(v for v in self.suite['cases'] if v['id']==self.case_id)
        super().__init__(*args,**kwargs)
        if self.checkpoint!=self.manifest['filename']:
            raise ValueError('Checkpoint must match the pinned model selection')
    def expected_settings(self):
        return settings(self.engine,self.checkpoint,self.case)
    def provenance(self):
        return dict(id=self.suite['id'],version=self.suite['version'],sha256=self.suite['sha256'],case=copy.deepcopy(self.case),
                    condition='Common 1024x1024 / 28 steps / CFG 5 / euler_ancestral / normal / seed 9007199254740993; no LoRA or reference; not model-optimal presets')
    def identity(self,item):
        if not isinstance(item,dict) or any(item.get(key)!=value for key,value in dict(name=self.manifest['filename'],
            version=self.manifest['version'],architecture='sdxl',sha256=self.manifest['sha256'],size_bytes=self.manifest['size_bytes']).items()):
            raise ValueError('Pinned model metadata identity differs')
    def preflight(self):
        target,_,_,_=downloader._paths(downloader.WORKSPACE,self.manifest['filename'],create=False)
        if not target.is_file() or not downloader._verified(target,self.manifest):
            raise ValueError('Pinned local checkpoint size/SHA256 verification failed')
        catalog=self.json('GET','models')
        item=next((v for v in catalog.get('models',[]) if v.get('name')==self.checkpoint),None)
        self.identity(item)
        if catalog.get('engine_url')!=self.engine or catalog.get('sync_error') or item.get('listed') is not True:
            raise ValueError('Fresh original-engine catalog required')
        if experiment_plans.suite()!=self.suite:
            raise ValueError('Fixed suite changed before submission; no job submitted')
        self.report['test_suite']=self.provenance()
        self.report['local_weights_verified']=[dict(name=self.manifest['filename'],sha256=self.manifest['sha256'],size_bytes=self.manifest['size_bytes'])]
    def check_snapshot(self,value):
        self.identity(value.get('model_metadata'))
        if value.get('lora_metadata'):raise ValueError('Common suite must not have active LoRA')
        snapshot=value['model_metadata']
        if 'model_snapshot' in self.report and self.report['model_snapshot']!=snapshot:
            raise ValueError('Immutable model snapshot changed')
        self.report['model_snapshot']=copy.deepcopy(snapshot)
    def assert_job(self,value,expected):
        super().assert_job(value,expected)
        self.check_snapshot(value)
        if value.get('status')=='completed':
            if 'measurements' in self.report and self.report['measurements']!=value.get('measurements'):
                raise ValueError('Original measurements changed')
            self.report['measurements']=copy.deepcopy(value.get('measurements'))
    def validate_report(self,value):
        super().validate_report(value)
        self.identity(value['model_snapshot'])
        if value.get('test_suite')!=self.provenance():
            raise ValueError('Report suite version, hash or selected case differs; no network verification')
    def verify_artworks(self,expected):
        super().verify_artworks(expected)
        for identifier in self.report['artwork_ids']:
            value=self.json('GET','artworks/'+identifier)
            self.check_snapshot(value)
            if value.get('measurements')!=self.report.get('measurements'):
                raise ValueError('Artwork original measurement snapshot differs')

def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--model',choices=tuple(MODELS),default='animagine-xl-4.0-opt')
    parser.add_argument('--case',choices=CASES,default='chair')
    options,rest=parser.parse_known_args(argv)
    runner=type('FixedSuiteAcceptance',(SuiteAcceptance,),dict(model_id=options.model,case_id=options.case))
    return base.main(rest,runner_type=runner,default_checkpoint=MODELS[options.model]['filename'],
        default_report='runtime/suite-'+options.model+'-'+options.case+'.json')

if __name__=='__main__':
    raise SystemExit(main())
