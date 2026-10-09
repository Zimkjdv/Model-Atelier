"""One fixed seed/strength Canny v2 case, including actual edge PNG evidence.

No automatic batch: each invocation admits one UUID. --verify-report uses only
GETs; it cannot synchronize, import a missing edge, or replay a generation.
"""
import argparse
import copy
import hashlib
import io
import re
from PIL import Image
from backend import control_edges as edges,control_edge_workflows as flow
from scripts import verify_control_generation as control,verify_local_generation as base
PROFILES={
    'seed-a-strength-05':('9007199254740993',0.5),
    'seed-a-strength-10':('9007199254740993',1.0),
    'seed-b-strength-05':('9007199254740995',0.5),
    'seed-b-strength-10':('9007199254740995',1.0),
}


class EdgeAcceptance(control.ControlAcceptance):
    generate_path='control-edge/generate'
    workflow_id=flow.ID
    model_id='animagine-xl-4.0-opt'
    profile='seed-a-strength-05'
    def expected_settings(self):
        seed,strength=PROFILES[self.profile]
        return super().expected_settings()|dict(title='Canny edge acceptance / '+self.model_id+' / '+self.profile,seed=seed,control_strength=strength,control_start=0.0,control_end=1.0)
    def build_workflow(self,settings,job_id=None):
        normalized=copy.deepcopy(settings)
        for key in ('control_strength','control_start','control_end','canny_low','canny_high','cfg','denoise'): normalized[key]=float(normalized[key])
        return flow.build(normalized,job_id)
    def assert_job(self,item,expected):
        super().assert_job(item,expected)
        if edges.digest(item['workflow'])!=edges.digest(expected): raise ValueError('Original full edge workflow JSON differs')
    def proof(self,value,report):
        width,height=report['settings']['width'],report['settings']['height'];job_id=report['job_id']
        anchor=dict(job_id=job_id,workflow_id=flow.ID,engine_url=self.engine,workflow_sha256=edges.digest(report['workflow']),reference_metadata=report['reference_metadata'],component_metadata=report['component_metadata'],width=width,height=height)
        source=value.get('source',{});metrics=value.get('metrics',{})
        if value.get('anchor')!=anchor or any(not control.checksum(value.get(k)) for k in ('sha256','decoded_rgb_sha256')) or type(value.get('size_bytes')) is not int or not 0<value['size_bytes']<=edges.MAX_BYTES: raise ValueError('Edge proof checksum, size or immutable source differs')
        if any(type(metrics.get(k)) is not int for k in ('width','height','edge_pixels','total_pixels')) or metrics.get('width')!=width or metrics.get('height')!=height or metrics.get('total_pixels')!=width*height or not 0<=metrics.get('edge_pixels',-1)<=width*height: raise ValueError('Edge proof geometry or binary-pixel metrics differ')
        if source.get('node_id')!='16' or source.get('type')!='output' or not isinstance(source.get('subfolder'),str) or source['subfolder'].replace(chr(92),'/')!='model_atelier/'+job_id or not re.fullmatch(r'canny_[0-9]+_\.png',str(source.get('filename',''))) or not isinstance(value.get('saved_at'),str): raise ValueError('Edge proof original output location differs')
    def validate_report(self,value):
        super().validate_report(value)
        self.proof(value['edge_output'],value)
        # Python numeric equality alone must not admit a bool port into node 16.
        if edges.digest(value['workflow'])!=edges.digest(self.build_workflow(value['settings'],value['job_id'])): raise ValueError('Edge workflow has changed types or graph')
    def verify_artworks(self,expected):
        super().verify_artworks(expected)
        job_id=self.report['job_id'];prefix='jobs/'+job_id+'/control-edge'
        if self.report['mode']=='generate': self.json('POST',prefix)
        item=self.json('GET',prefix)
        if item.get('job_id')!=job_id or item.get('workflow_id')!=flow.ID or item.get('state')!='saved' or item.get('image_available') is not True or item.get('import_allowed') is not False: raise ValueError('Actual saved edge is unavailable; do not recompute or import during verification')
        raw=self.request('GET',prefix+'/image').content;metrics=edges.pixels(raw,self.report['settings']['width'],self.report['settings']['height'])
        if item.get('sha256')!=hashlib.sha256(raw).hexdigest() or item.get('size_bytes')!=len(raw) or metrics!={k:item.get(k) for k in metrics}: raise ValueError('Actual edge PNG or pixel snapshot differs')
        with Image.open(io.BytesIO(raw)) as image: image.load();pixel_hash=hashlib.sha256(image.tobytes()).hexdigest()
        proof=dict(anchor=item.get('anchor'),source=item.get('source'),sha256=item['sha256'],size_bytes=len(raw),metrics=metrics,decoded_rgb_sha256=pixel_hash,saved_at=item.get('saved_at'))
        self.proof(proof,self.report)
        job=self.json('GET','jobs/'+job_id);anchors,source=edges.source(job,lambda value:value)
        if proof['source']!=source or proof['anchor']!=anchors: raise ValueError('Saved edge does not match original successful history')
        if 'edge_output' in self.report and self.report['edge_output']!=proof: raise ValueError('Immutable edge proof changed')
        for artwork_id in self.report['artwork_ids']:
            if self.json('GET','artworks/'+artwork_id+'/control-edge')!=item: raise ValueError('Artwork edge points to a different original job')
        self.report['edge_output']=copy.deepcopy(proof)


def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--model',choices=tuple(control.MODELS),default=EdgeAcceptance.model_id)
    parser.add_argument('--profile',choices=tuple(PROFILES),required=True)
    parser.add_argument('--source-id',required=True)
    options,rest=parser.parse_known_args(argv)
    runner=type('FixedEdgeAcceptance',(EdgeAcceptance,),dict(model_id=options.model,source_id=options.source_id,profile=options.profile))
    return base.main(rest,runner_type=runner,default_checkpoint=control.MODELS[options.model]['filename'],default_report='runtime/control-edge-'+options.model+'-'+options.profile+'.json')

if __name__=='__main__': raise SystemExit(main())
