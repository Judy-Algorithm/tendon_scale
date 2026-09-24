"""Loopback task-53 catalog, lazy source/video preparation and serialized fitting.

The six existing services remain intact. New records use a bounded queue and
disk display caches, not resident models and not personalized .osim files.
"""
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from all_catalog import inventory,public_record,checked_source

ROOT=Path(os.environ['TENDON_RUNTIME']).resolve()
CODE=Path(__file__).parent
READER=Path(os.environ.get('TENDON_READER_PYTHON',str(ROOT/'reader-env/bin/python')))
SOLVER=Path(os.environ.get('TENDON_SOLVER_PYTHON',sys.executable))
RECORDS=inventory()
QUEUE=queue.Queue(maxsize=8)
LOCK=threading.Lock();JOBS={}
# Changes to compute/extraction code must not reuse an old display cache.
COMPUTE_FILES=('personalize.py','scaling_core.py','scale_checks.py','left_adapter.py','path_repairs.py',
    'palm_scaling.py','landmark_estimates.py','extract_rrd.py','extract_video.py','prepare_record.py','solve_record.py')
REVISION=hashlib.sha256(b''.join((CODE/name).read_bytes() for name in COMPUTE_FILES)).hexdigest()[:12]
CACHE=ROOT/'cache'/'all-records'/REVISION
MEDIA_NAMES={'cam0-right.mp4':'video/mp4','cam0-left.mp4':'video/mp4',
 'cam0-sync.json':'application/json','cam0-left-sync.json':'application/json'}

def folder(identifier):return CACHE/identifier

def set_job(key,**values):
    with LOCK:JOBS[key]=dict(recordingId=key[0],**values)

def worker():
    while True:
        key=QUEUE.get();identifier,hand=key;directory=folder(identifier)
        try:
            source=checked_source(RECORDS[identifier])
            set_job(key,status='running',stage='读取三维点和准备视频')
            subprocess.run([str(READER),str(CODE/'prepare_record.py'),str(source),str(directory),identifier,hand],check=True,timeout=900)
            set_job(key,status='running',stage='缩放个人手部并解算动作')
            process=subprocess.Popen([str(SOLVER),str(CODE/'solve_record.py'),str(ROOT),str(directory),identifier,hand],stdout=subprocess.PIPE,text=True)
            timeout=threading.Timer(900,process.kill);timeout.daemon=True;timeout.start()
            try:
                for line in process.stdout:
                    try:
                        update=json.loads(line)
                        if 'progress' in update:set_job(key,status='running',stage='解算手部动作',progress=update['progress'])
                    except ValueError:print(line.rstrip(),flush=True)
                if process.wait()!=0:raise RuntimeError('Model solve failed or exceeded time limit')
            finally:timeout.cancel()
            set_job(key,status='ready')
        except Exception as error:
            print(identifier,hand,type(error).__name__,str(error),flush=True)
            set_job(key,status='error',message='这条记录的数据读取、视频同步或模型检查未通过，可选择其他记录；详情见服务器日志')
        finally:QUEUE.task_done()

class Handler(BaseHTTPRequestHandler):
    def json(self,status,value):
        body=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers()
        if self.command!='HEAD':self.wfile.write(body)

    def local(self):
        return not self.headers.get('Origin') and bool(re.fullmatch(r'(127\.0\.0\.1|localhost):\d+',self.headers.get('Host','')))

    def legacy(self,hand,body=None):
        headers={'Accept-Encoding':'gzip'}
        if body is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(f'http://127.0.0.1:{8768 if hand=="left" else 8769}'+self.path,data=body,headers=headers,method=self.command)
        try:
            with urllib.request.urlopen(request,timeout=15) as response:
                self.send_response(response.status)
                for key in ('Content-Type','Content-Encoding','Content-Length','Cache-Control'):
                    if response.headers.get(key):self.send_header(key,response.headers[key])
                self.end_headers()
                if self.command!='HEAD':
                    while block:=response.read(65536):self.wfile.write(block)
        except urllib.error.HTTPError as e:self.json(e.code,dict(error='原有记录暂未就绪'))
        except urllib.error.URLError:self.json(503,dict(error='原有样本服务未连接'))

    def file(self,path,kind):
        if not path.is_file():return self.json(404,dict(error='请先加载这条记录，准备对应视频'))
        size=path.stat().st_size;start,end=0,size-1;status=200
        if value:=self.headers.get('Range'):
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
            if not match or not any(match.groups()):return self.json(416,dict(error='Invalid range'))
            a,b=match.groups()
            if a:start=int(a);end=min(int(b),end) if b else end
            else:start=max(0,size-int(b))
            if start>end or start>=size:return self.json(416,dict(error='Invalid range'))
            status=206
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store')
        if path.suffix=='.gz':self.send_header('Content-Encoding','gzip')
        else:self.send_header('Accept-Ranges','bytes')
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length',str(end-start+1));self.end_headers()
        if self.command=='HEAD':return
        with path.open('rb') as file:
            file.seek(start);remaining=end-start+1
            while remaining:
                block=file.read(min(65536,remaining))
                if not block:break
                self.wfile.write(block);remaining-=len(block)

    def do_HEAD(self):self.do_GET()

    def do_GET(self):
        if not self.local():return self.json(403,dict(error='Loopback only'))
        url=urlparse(self.path);query=parse_qs(url.query)
        if url.path=='/api/health':return self.json(200,dict(status='ok',recordings=len(RECORDS),mode='all-task53-lazy',revision=REVISION))
        if url.path=='/api/recordings':return self.json(200,[public_record(r) for r in RECORDS.values()])
        if url.path.startswith('/api/media/'):
            parts=url.path.split('/')
            if len(parts)!=5 or parts[3] not in RECORDS or parts[4] not in MEDIA_NAMES:return self.json(404,dict(error='Unknown media'))
            return self.file(folder(parts[3])/parts[4],MEDIA_NAMES[parts[4]])
        identifier=query.get('recordingId',['sample-01'])[0];hand=query.get('hand',['right'])[0]
        if identifier not in RECORDS or hand not in ('right','left'):return self.json(404,dict(error='Unknown recording or hand'))
        if url.path not in ('/api/job','/api/result'):return self.json(404,dict(error='Unknown route'))
        if RECORDS[identifier]['legacy']:return self.legacy(hand)
        key=(identifier,hand);result=folder(identifier)/f'result-{hand}.json.gz'
        if url.path=='/api/result':return self.file(result,'application/json')
        with LOCK:job=JOBS.get(key,dict(recordingId=identifier,status='ready' if result.is_file() else 'idle'))
        self.json(200,job)

    def do_POST(self):
        if not self.local():return self.json(403,dict(error='Loopback only'))
        if urlparse(self.path).path!='/api/jobs':return self.json(404,dict(error='Unknown route'))
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1024 or self.headers.get('Transfer-Encoding') or self.headers.get_content_type()!='application/json':raise ValueError()
            body=self.rfile.read(length);data=json.loads(body);identifier=data['recordingId'];hand=data['hand']
            if set(data)!={'recordingId','hand'} or identifier not in RECORDS or hand not in ('left','right'):raise ValueError()
        except (ValueError,KeyError,TypeError):return self.json(400,dict(error='Invalid recording request'))
        if RECORDS[identifier]['legacy']:return self.legacy(hand,body)
        key=(identifier,hand)
        with LOCK:
            if JOBS.get(key,{}).get('status') not in ('queued','running','ready'):
                if (folder(identifier)/f'result-{hand}.json.gz').is_file():JOBS[key]=dict(status='ready',recordingId=identifier)
                else:
                    try:QUEUE.put_nowait(key)
                    except queue.Full:return self.json(429,dict(error='等待解算的记录较多，请稍后再试'))
                    JOBS[key]=dict(status='queued',recordingId=identifier)
        return self.json(202,dict(status='accepted',recordingId=identifier))

if __name__=='__main__':
    threading.Thread(target=worker,daemon=True).start()
    print(f'Task 53 catalog: {len(RECORDS)} files, loopback:8770',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8770),Handler).serve_forever()
