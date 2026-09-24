"""Isolated OpenSim worker; only selected records, never one XML per person."""
import gzip
import json
import sys
from pathlib import Path
from personalize import build

if __name__=='__main__':
    root,directory,identifier,hand=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3],sys.argv[4]
    window=json.loads((directory/f'window-{hand}.json').read_text())
    base=root/'base'/('Hand_Wrist_Model_LEFT_GlobalX180.osim' if hand=='left' else 'Hand_Wrist_Model_for_development.osim')
    payload=build(base,directory/'raw.npz',start=window['startS'],end=window['endS'],
        progress=lambda p:print(json.dumps(dict(progress=p)),flush=True))
    payload['recordingId']=identifier;payload['report']['recordingId']=identifier
    temporary=directory/f'result-{hand}.tmp.gz'
    temporary.write_bytes(gzip.compress(json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode(),compresslevel=3))
    temporary.replace(directory/f'result-{hand}.json.gz')
