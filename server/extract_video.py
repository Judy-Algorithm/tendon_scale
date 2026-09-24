"""Extract original camera-0 HEVC packets and their capture clock; no pose synthesis."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import rerun.recording as rr


def extract(source, raw, destination, recording_id='sample-01', start=30., end=42., hand='right'):
    if hand not in ('left','right'):raise ValueError('Invalid hand')
    destination.mkdir(parents=True, exist_ok=True)
    recording = rr.load_recording(str(source))
    packets, intrinsics = [], None
    for chunk in recording.chunks():
        entity = str(chunk.entity_path)
        if entity not in ('/video/fixed/cam0', '/world/fixed_cameras/cam0'):
            continue
        batch = chunk.to_record_batch()
        names = batch.schema.names
        if entity == '/world/fixed_cameras/cam0':
            if 'Pinhole:image_from_camera' in names:
                intrinsics = batch.column('Pinhole:image_from_camera')[0].as_py()[0]
            continue
        if 'VideoStream:sample' not in names:
            continue
        capture = batch.column('capture_time').cast(pa.int64()).to_pylist()
        samples = batch.column('VideoStream:sample').to_pylist()
        keys = batch.column('VideoStream:is_keyframe').to_pylist()
        for timestamp, sample, key in zip(capture, samples, keys):
            packets.append((timestamp, bytes(sample[0]), key[0]))
    packets.sort(key=lambda item: item[0])
    stamps = np.array([p[0] for p in packets], dtype=np.int64)
    if not len(packets) or not packets[0][2] or np.any(np.diff(stamps) <= 0):
        raise ValueError('Video clock or initial keyframe invalid')
    with np.load(raw, allow_pickle=False) as data:
        source_meta = json.loads(str(data['metadata']))
        pose_stamps = data['capture_timestamp_ns'].astype(np.int64)
        # Select a fixed crop covering the entire right-hand trajectory in this clip.
        side=source_meta['handOrder'].index(hand)
        xyz = data['joints_world_raw'][:, side]
        good = data['valid_joints'][:, side].astype(bool) & data['valid'][:, side, None].astype(bool)
    source_hash = hashlib.file_digest(source.open('rb'), 'sha256').hexdigest()
    if source_hash != source_meta['sourceHash']:
        raise ValueError('Video and raw poses come from different recordings')
    origin = int(pose_stamps[0])
    relative = (stamps-origin)/1e9
    with (destination/'cam0-original.h265').open('wb') as output:
        for _, packet, _ in packets:
            output.write(packet)
    nearest = np.searchsorted(stamps, pose_stamps).clip(1, len(stamps)-1)
    delta = np.minimum(abs(stamps[nearest]-pose_stamps), abs(stamps[nearest-1]-pose_stamps))
    if intrinsics is None:raise ValueError('Missing camera intrinsics')
    k = np.array(intrinsics).reshape(3, 3).T
    selected = (pose_stamps-origin >= start*1e9) & (pose_stamps-origin <= end*1e9)
    pts = xyz[selected][good[selected]]
    pts = pts[np.isfinite(pts).all(axis=1) & (pts[:, 2] > 0)]
    if not len(pts):raise ValueError('No valid '+hand+' observations in comparison window')
    xy = pts @ k.T
    xy = xy[:, :2]/xy[:, 2:3]
    lo, hi = xy.min(axis=0)-65, xy.max(axis=0)+65
    # Fixed 16:9 framing, integer/even dimensions for browser video encoders.
    centre = (lo+hi)/2
    width = min(1280, np.ceil(max(hi[0]-lo[0], (hi[1]-lo[1])*16/9)/32)*32)
    height = width*9/16
    x = max(0, min(1280-width, round((centre[0]-width/2)/2)*2))
    y = max(0, min(720-height, round((centre[1]-height/2)/2)*2))
    metadata = dict(schemaVersion='1.0', recordingId=recording_id, camera='cam0',
                    sourceHash=source_hash, frameCount=len(packets), hand=hand,
                    mediaFps=30, frameTimesS=relative.tolist(), captureOriginNs=str(origin),
                    maxNearestPoseDeltaMs=float(delta.max()/1e6),
                    medianNearestPoseDeltaMs=float(np.median(delta)/1e6),
                    intrinsics=k.tolist(), resolution=[1280,720],
                    crop=[int(x),int(y),int(width),int(height)],
                    encodingPolicy='one input frame per output frame; media time is mapped to capture timestamps')
    (destination/('cam0-left-sync.json' if hand=='left' else 'cam0-sync.json')).write_text(json.dumps(metadata, separators=(',', ':')))
    print(json.dumps({key: metadata[key] for key in ('frameCount','maxNearestPoseDeltaMs','crop')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('raw', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--recording-id',default='sample-01')
    args = parser.parse_args()
    extract(args.source, args.raw, args.destination,args.recording_id)
