"""Immutable local cache of a successful v2 job's native conditioning PNG."""
import hashlib
import io
import json
import os
import re
import sqlite3
import warnings
from contextlib import closing
from copy import deepcopy
from datetime import datetime,timezone
from uuid import UUID
from PIL import Image,UnidentifiedImageError
from backend import control_edge_workflows as flow
MAX_BYTES=32*1024*1024
MAX_PIXELS=16_000_000


def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def anchor(job,validate):
    if job.get('workflow_id')!=flow.ID: raise ValueError('舊流程沒有同次執行的邊緣輸出，不會重新計算或回填。')
    settings=flow.extract(dict(job,source=dict(node_id='7')),validate)
    return dict(job_id=job['id'],workflow_id=flow.ID,engine_url=job['engine_url'],workflow_sha256=digest(job['workflow']),
                reference_metadata=deepcopy(job['reference_metadata']),component_metadata=deepcopy(job['component_metadata']),width=settings['width'],height=settings['height'])


def source(job,validate):
    anchors=anchor(job,validate)
    history=job.get('history') or {};state=history.get('status') if isinstance(history,dict) else None
    if job.get('status')!='completed' or not isinstance(state,dict) or state.get('completed') is not True or state.get('status_str')!='success': raise ValueError('請先確認任務成功；不保存未確認或失敗任務的邊緣圖。')
    outputs=history.get('outputs');entry=outputs.get(flow.EDGE_NODE) if isinstance(outputs,dict) else None
    images=entry.get('images') if isinstance(entry,dict) else None
    if not isinstance(images,list) or len(images)!=1 or not isinstance(images[0],dict): raise ValueError('原歷史缺少唯一 Canny 邊緣輸出；不重新生成。')
    image=images[0];name=image.get('filename');folder=image.get('subfolder','')
    if image.get('type')!='output' or not isinstance(name,str) or len(name)>255 or not re.fullmatch(r'canny_[0-9]+_\.png',name) or not isinstance(folder,str) or folder.replace(chr(92),'/')!='model_atelier/'+str(UUID(job['id'])): raise ValueError('邊緣輸出位置與平台流程不同，未讀取檔案。')
    return anchors,dict(node_id=flow.EDGE_NODE,filename=name,subfolder=folder,type='output')


def pixels(raw,width,height):
    if not raw or len(raw)>MAX_BYTES: raise ValueError('邊緣 PNG 大小無效，最大 32 MiB。')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format!='PNG' or getattr(image,'n_frames',1)!=1 or image.mode!='RGB' or image.size!=(width,height) or image.width*image.height>MAX_PIXELS: raise ValueError('邊緣圖須為與流程尺寸相同的單張 RGB PNG。')
                image.load();channels=image.split()
                if channels[0].tobytes()!=channels[1].tobytes() or channels[0].tobytes()!=channels[2].tobytes(): raise ValueError('原生 Canny 輸出應為黑白 RGB，未保存異常色彩圖。')
                histogram=channels[0].histogram()
                if sum(histogram[1:255]): raise ValueError('原生 Canny 輸出不是二值邊緣圖。')
                return dict(width=width,height=height,edge_pixels=histogram[255],total_pixels=width*height)
    except (UnidentifiedImageError,OSError,Image.DecompressionBombWarning,Image.DecompressionBombError) as exc: raise ValueError('邊緣 PNG 損壞或過大，未保存。') from exc


def path(data,identifier,create=False):
    root=data.resolve();folder=data/'control_edges'
    if folder.is_symlink() or (hasattr(folder,'is_junction') and folder.is_junction()) or not folder.resolve().is_relative_to(root): raise OSError('邊緣目錄超出平台資料範圍。')
    if create: folder.mkdir(exist_ok=True)
    target=folder/(str(UUID(identifier))+'.png')
    if target.is_symlink() or not target.resolve().is_relative_to(root): raise OSError('邊緣圖不允許 symlink 或外部路徑。')
    return target


def get(db_path,identifier):
    with closing(sqlite3.connect(db_path)) as db: row=db.execute('SELECT value FROM settings WHERE key=?',('control_edge:'+identifier,)).fetchone()
    return json.loads(row[0]) if row else None


def checked_raw(data,item):
    target=path(data,item['job_id'])
    if not target.is_file() or target.stat().st_size!=item['size_bytes'] or target.stat().st_size>MAX_BYTES: raise ValueError('本機邊緣圖遺失或大小變更；請從備份還原，不自動覆蓋。')
    with target.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
    if hashlib.sha256(raw).hexdigest()!=item['sha256']: raise ValueError('本機邊緣圖 SHA256 不符；請從備份還原，不自動覆蓋。')
    if pixels(raw,item['width'],item['height'])!={k:item[k] for k in ('width','height','edge_pixels','total_pixels')}: raise ValueError('邊緣圖量測與快照不同。')
    return raw


def summary(db_path,data,job,validate):
    anchors=anchor(job,validate);item=get(db_path,job['id'])
    if item is None: return dict(job_id=job['id'],workflow_id=flow.ID,state='not_saved',image_available=False,import_allowed=job.get('status')=='completed',message='尚未保存同次執行的邊緣 PNG；需由原引擎 output 明確匯入。')
    _,origin=source(job,validate)
    if item.get('source')!=origin: raise ValueError('原歷史邊緣來源與保存紀錄不同；保留原圖，不替換。')
    if item.get('anchor')!=anchors: raise ValueError('邊緣來源與原任務快照不同，拒絕套用。')
    try: checked_raw(data,item)
    except (OSError,ValueError) as exc: return item|dict(state='unavailable',image_available=False,import_allowed=False,message=str(exc))
    return item|dict(state='saved',image_available=True,import_allowed=False,message='原生 Canny 節點 13 的同次輸出；不是目前表單的即時預覽。')


def save(db_path,data,job,anchors,origin,raw):
    metrics=pixels(raw,anchors['width'],anchors['height']);target=path(data,job['id'],create=True);owned=False
    item=dict(job_id=job['id'],workflow_id=flow.ID,anchor=anchors,source=origin,sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw),saved_at=datetime.now(timezone.utc).isoformat(),**metrics)
    try:
        with closing(sqlite3.connect(db_path)) as db,db:
            db.execute('BEGIN IMMEDIATE');key='control_edge:'+job['id'];row=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
            if row:
                old=json.loads(row[0])
                if old['anchor']!=anchors or old['source']!=origin: raise ValueError('已有不同的邊緣快照，拒絕覆寫。')
                checked_raw(data,old);return old,False
            with target.open('xb') as stream:
                owned=True;stream.write(raw);stream.flush();os.fsync(stream.fileno())
            db.execute('INSERT INTO settings VALUES (?,?)',(key,json.dumps(item,ensure_ascii=False,allow_nan=False)))
        return item,True
    except BaseException:
        if owned: target.unlink(missing_ok=True)
        raise
