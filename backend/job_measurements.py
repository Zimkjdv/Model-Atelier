"""Source-scoped measurements for new jobs; do not backfill historical records."""
from copy import deepcopy
from datetime import datetime
from backend import environment

TERMINAL = {'completed', 'failed', 'cancelled', 'stopped'}
MAX_SECONDS = 365 * 86400

def initial(engine_url):
    return dict(schema_version=1, engine_url=engine_url, dispatch_started_at=None,
                terminal_observed_at=None, dispatch_to_observation_seconds=None,
                engine_execution_seconds=None, engine_timestamps_ms=None,
                resources_before_submission=None, task_vram_peak_bytes=None,
                timing_note='平台時鐘從提交起始到首次確認終態，包含佇列、網路與查詢延遲；引擎起訖包含載入及快取，皆非純 GPU 取樣。')

def resources(stats, engine_url, captured_at):
    report = environment.engine_diagnostics(stats)
    return dict(source=engine_url + '/system_stats', engine_url=engine_url, captured_at=captured_at,
                status=report['status'], ram=report['ram'], devices=report['devices'],
                note='提交前單次原引擎回報；非連續峰值、任務專用資源或最低需求，可能含可回收快取。')

def elapsed(start, end):
    try:
        a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
        if a.tzinfo is None or b.tzinfo is None: return None
        seconds = (b-a).total_seconds()
        return round(seconds, 3) if 0 <= seconds <= MAX_SECONDS else None
    except (TypeError, ValueError, OverflowError):
        return None

def engine_timing(job):
    history = job.get('history')
    expected = {'completed':'execution_success', 'failed':'execution_error', 'stopped':'execution_interrupted'}.get(job['status'])
    if not expected or not isinstance(history, dict): return None
    state=history.get('status')
    messages=state.get('messages') if isinstance(state, dict) else None
    if (not isinstance(state,dict) or type(state.get('completed')) is not bool
        or state.get('status_str') != ('success' if job['status']=='completed' else 'error')
        or (job['status']=='completed' and state['completed'] is not True)
        or not isinstance(messages,list) or len(messages)>1024): return None
    selected=[]
    kinds={'execution_start','execution_success','execution_error','execution_interrupted'}
    for index, row in enumerate(messages):
        if not isinstance(row,list) or len(row)!=2: return None
        if not isinstance(row[0],str): return None
        if row[0] not in kinds: continue
        data=row[1]
        if (not isinstance(data,dict) or data.get('prompt_id')!=job['prompt_id']
            or type(data.get('timestamp')) is not int or not 0 <= data['timestamp'] <= 9007199254740991): return None
        selected.append((index,row[0],data['timestamp']))
    if len(selected)!=2 or selected[0][1]!='execution_start' or selected[1][1]!=expected: return None
    start,end=selected[0][2],selected[1][2]
    return dict(start=start,end=end) if 0 <= end-start <= MAX_SECONDS*1000 else None

def advance(value, timestamp):
    measurement=value.get('measurements')
    if (not isinstance(measurement,dict) or type(measurement.get('schema_version')) is not int
        or measurement['schema_version']!=1 or not {'dispatch_started_at','terminal_observed_at'} <= set(measurement)): return
    result=deepcopy(measurement)
    if value['status']=='submitting' and result['dispatch_started_at'] is None:
        result['dispatch_started_at']=timestamp
    if value['status'] in TERMINAL and result['terminal_observed_at'] is None:
        result['terminal_observed_at']=timestamp
        result['dispatch_to_observation_seconds']=elapsed(result['dispatch_started_at'],timestamp)
        times=engine_timing(value)
        result['engine_timestamps_ms']=times
        result['engine_execution_seconds']=round((times['end']-times['start'])/1000,3) if times else None
    value['measurements']=result
