"""Read only original multiview joint observations. Run in the Rerun environment."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import rerun.recording as rdf


def extract(source, destination):
    recording = rdf.load_recording(str(source))
    fields = ('joints_world_raw', 'valid', 'valid_joints', 'capture_timestamp_ns')
    values = {name: [] for name in fields}
    for chunk in recording.chunks():
        if str(chunk.entity_path) != '/data/wilor/source/frames':
            continue
        batch = chunk.to_record_batch()
        for name in fields:
            if name not in batch.schema.names:
                raise ValueError(f'Missing raw field: {name}; no filtered fallback')
            values[name].extend(row[0] for row in batch.column(name).to_pylist())
    arrays = {key: np.asarray(value) for key, value in values.items()}
    order = np.argsort(arrays['capture_timestamp_ns'])
    arrays = {key: value[order] for key, value in arrays.items()}
    if arrays['joints_world_raw'].shape[1:] != (2, 21, 3):
        raise ValueError('Unexpected source landmark dimensions')
    if np.any(np.diff(arrays['capture_timestamp_ns']) <= 0):
        raise ValueError('Duplicate or reversed timestamps')
    # This adapter is deliberately restricted to the audited task-53 source schema.
    metadata = dict(schemaVersion='1.0', sourceKind='raw_reconstructed_3d',
                    pointField='joints_world_raw', handOrder=['left', 'right'],
                    landmarkSet='wilor_mano21_index_v1', lengthUnit='m',
                    coordinateFrame='cam0', sourceFile=source.name,
                    sourceHash=hashlib.file_digest(source.open('rb'), 'sha256').hexdigest())
    np.savez_compressed(destination, **arrays, metadata=json.dumps(metadata))
    print(json.dumps(dict(frames=len(order), shape=arrays['joints_world_raw'].shape,
                          destination=str(destination))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    extract(args.source, args.destination)
