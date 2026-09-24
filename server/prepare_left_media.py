"""Derive left-hand framing from original left observations and the same video clock."""
import json
from pathlib import Path
import argparse
import numpy as np

def prepare(root,identifier):
    if identifier not in {f'sample-{i:02d}' for i in range(1,7)}:raise ValueError('Unregistered sample')
    raw=root/'cache'/('sample-raw.npz' if identifier=='sample-01' else identifier+'-raw.npz')
    directory=root/'video'/identifier
    right=directory/'cam0-sync.json'
    if identifier=='sample-01' and not right.exists():right=root/'video/cam0-sync.json'
    meta=json.loads(right.read_text())
    with np.load(raw,allow_pickle=False) as data:
        source=json.loads(str(data['metadata']))
        if source['sourceHash']!=meta['sourceHash']:raise ValueError('Video source mismatch')
        side=source['handOrder'].index('left')
        xyz=data['joints_world_raw'][:,side]
        valid=data['valid_joints'][:,side]&data['valid'][:,side,None]
        t=(data['capture_timestamp_ns']-int(meta['captureOriginNs']))/1e9
    pts=xyz[(t>=30)&(t<=42)][valid[(t>=30)&(t<=42)]]
    pts=pts[np.isfinite(pts).all(axis=1)&(pts[:,2]>0)]
    if len(pts)<30:raise ValueError('Insufficient left-hand points for camera framing')
    k=np.array(meta['intrinsics']);xy=pts@k.T;xy=xy[:,:2]/xy[:,2:3]
    lo,hi=xy.min(0)-65,xy.max(0)+65;centre=(lo+hi)/2
    width=min(1280,np.ceil(max(hi[0]-lo[0],(hi[1]-lo[1])*16/9)/32)*32);height=width*9/16
    x=max(0,min(1280-width,round((centre[0]-width/2)/2)*2))
    y=max(0,min(720-height,round((centre[1]-height/2)/2)*2))
    meta.update(hand='left',recordingId=identifier,crop=[int(x),int(y),int(width),int(height)])
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'cam0-left-sync.json').write_text(json.dumps(meta,separators=(',',':')))
    print(identifier,meta['crop'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);args=p.parse_args()
    for i in range(1,7):prepare(args.root,f'sample-{i:02d}')
