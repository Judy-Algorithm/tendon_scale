"""Loopback-only sample comparison; one compute worker and six in-memory results."""
import gzip
import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from personalize import build
from recording_catalog import load_records,public_record

ROOT=Path(os.environ['TENDON_RUNTIME']).resolve()
HAND=os.environ.get('TENDON_HAND','right')
if HAND not in ('left','right'):raise ValueError('Unsupported service hand')
PORT=int(os.environ.get('TENDON_PORT',8768 if HAND=='left' else 8769))
BASE=ROOT/'base'/('Hand_Wrist_Model_LEFT_GlobalX180.osim' if HAND=='left' else 'Hand_Wrist_Model_for_development.osim')
RECORDINGS=load_records(ROOT)
for record in RECORDINGS.values():
    record['hand']=HAND
    if HAND=='left':record['label']=record['label'].replace('右手','左手')
LOCK=threading.Lock()
COMPUTE_LOCK=threading.Lock()
JOBS={key:dict(status='idle',recordingId=key) for key in RECORDINGS}
RESULTS={}

def encoded(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()

def run_job(identifier):
    record=RECORDINGS[identifier]
    try:
        with COMPUTE_LOCK:
            with LOCK:JOBS[identifier]=dict(status='running',recordingId=identifier,progress=dict(done=0,total=359))
            def progress(value):
                with LOCK:JOBS[identifier].update(progress=value)
            payload=build(BASE,ROOT/'cache'/record['rawFile'],start=record['startS'],end=record['endS'],progress=progress)
            if record.get('sourceHash') and payload['plan']['sourceHash']!=record['sourceHash']:
                raise ValueError('Registered recording fingerprint changed')
            payload['recordingId']=identifier
            payload['report']['recordingId']=identifier
            plan_data=encoded(payload['plan'])
            key=hashlib.sha256(plan_data).hexdigest()[:20]
            destination=ROOT/'cache'/f'profile-{key}.json'
            if not destination.exists():destination.write_bytes(plan_data)
            (ROOT/'cache'/f'report-{key}.json').write_bytes(encoded(payload['report']))
            result=gzip.compress(encoded(payload),compresslevel=3)
            with LOCK:
                RESULTS[identifier]=result
                JOBS[identifier]=dict(status='ready',recordingId=identifier,profileId=key,report=payload['report'],resultBytes=len(result))
    except Exception as error:
        print(f'{identifier}: {type(error).__name__}: {error}',flush=True)
        with LOCK:JOBS[identifier]=dict(status='error',recordingId=identifier,message='该记录解算未通过检查，请查看核验日志')

class Handler(BaseHTTPRequestHandler):
    def send_json(self,status,data):
        payload=encoded(data)
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers();self.wfile.write(payload)

    def do_GET(self):
        parsed=urlparse(self.path);route=parsed.path
        if route=='/api/health':return self.send_json(200,dict(status='ok',mode='private-sample-comparison',model=BASE.name,recordings=len(RECORDINGS)))
        if route=='/api/recordings':return self.send_json(200,[public_record(r) for r in RECORDINGS.values()])
        query=parse_qs(parsed.query)
        if set(query)-{'recordingId','hand'} or len(query.get('recordingId',['sample-01']))!=1 or query.get('hand',[HAND])!=[HAND]:
            return self.send_json(400,dict(error='Invalid recording query'))
        identifier=query.get('recordingId',['sample-01'])[0]
        if identifier not in RECORDINGS:return self.send_json(404,dict(error='Recording not registered'))
        if route=='/api/job':
            with LOCK:snapshot=dict(JOBS[identifier])
            return self.send_json(200,snapshot)
        if route=='/api/result':
            with LOCK:result=RESULTS.get(identifier)
            if result is None:return self.send_json(409,dict(error='Result not ready'))
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Encoding','gzip')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(result)))
            self.end_headers();self.wfile.write(result);return
        self.send_json(404,dict(error='Not found'))

    def do_POST(self):
        if self.headers.get('Origin'):return self.send_json(403,dict(error='Cross-origin requests disabled'))
        if urlparse(self.path).path!='/api/jobs' or self.headers.get_content_type()!='application/json':
            return self.send_json(400,dict(error='Invalid request'))
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1024:raise ValueError()
            data=json.loads(self.rfile.read(length))
            if set(data)!={'recordingId','hand'} or data['recordingId'] not in RECORDINGS or data['hand']!=HAND:raise ValueError()
            identifier=data['recordingId']
        except (ValueError,TypeError):return self.send_json(400,dict(error='Record and hand must match this service'))
        with LOCK:
            if JOBS[identifier]['status'] not in ('queued','running','ready'):
                JOBS[identifier]=dict(status='queued',recordingId=identifier)
                threading.Thread(target=run_job,args=(identifier,),daemon=True).start()
        self.send_json(202,dict(status='accepted',recordingId=identifier))

if __name__=='__main__':
    print(f'Private {HAND} service ready on loopback:{PORT}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
