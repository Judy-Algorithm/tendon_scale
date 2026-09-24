"""Operator-registered allowlist; HTTP never accepts filesystem paths."""
import json

IDS={f'sample-{i:02d}' for i in range(1,7)}

def validate_records(records,root):
    result={};hashes=set()
    for record in records:
        r=dict(record);identifier=r['id']
        if identifier not in IDS or identifier in result or r['hand']!='right':raise ValueError('Invalid recording identity')
        expected='sample-raw.npz' if identifier=='sample-01' else identifier+'-raw.npz'
        if r['rawFile']!=expected or not (root/'cache'/expected).is_file():raise ValueError('Unregistered raw cache')
        if not 0<=r['startS']<r['endS']<=r['durationS']:raise ValueError('Invalid comparison window')
        fingerprint=r.get('sourceHash')
        if fingerprint:
            if len(fingerprint)!=64 or fingerprint in hashes:raise ValueError('Duplicate or invalid source hash')
            hashes.add(fingerprint)
        r['videoBase']='/media/'+identifier;result[identifier]=r
    return dict(sorted(result.items()))

def load_records(root):
    default=dict(id='sample-01',label='真实记录 01 · 右手',hand='right',durationS=119.974,
                 profileScope='recording',startS=30.,endS=42.,rawFile='sample-raw.npz')
    file=root/'cache/recordings.json'
    records=json.loads(file.read_text()) if file.exists() else []
    if not any(r['id']=='sample-01' for r in records):records.insert(0,default)
    return validate_records(records,root)

def public_record(record):
    return {k:v for k,v in record.items() if k!='rawFile'}
