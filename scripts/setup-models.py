"""Verify bundled baseline assets; optionally copy them into a private runtime."""
import argparse
import hashlib
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'models' / 'base'
EXPECTED = {
    'Hand_Wrist_Model_for_development.osim': '9a88909ca27da9397abe22599e51ae9699162bdf274f65d2a83d7b02793b24cc',
    'Hand_Wrist_Model_LEFT_GlobalX180.osim': '45c45732788afd4fcc78b89c97cf7a5da51de82dcb735d480459ee4e8770207b',
}

def verify():
    files = set()
    for name, expected in EXPECTED.items():
        model = BASE / name
        if hashlib.sha256(model.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Baseline checksum mismatch: {name}')
        files.add(model)
        for item in ET.parse(model).iter('mesh_file'):
            mesh = item.text.strip()
            # Existing left_adapter.py replaces this missing Ground-only asset.
            if mesh == 'thorax_GlobalX180.vtp':
                mesh = 'thorax.vtp'
            path = BASE / 'Geometry' / mesh
            if not path.is_file():
                raise FileNotFoundError(path)
            ET.parse(path)
            files.add(path)
    return sorted(files)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, help='Optional private runtime directory')
    args = parser.parse_args()
    files = verify()
    if args.runtime:
        destination = args.runtime.resolve() / 'base'
        # Check all conflicts first; never overwrite a different existing model.
        for source in files:
            target = destination / source.relative_to(BASE)
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise ValueError(f'Refusing to overwrite different asset: {target}')
        for source in files:
            target = destination / source.relative_to(BASE)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(source, target)
    print(f'Verified {len(EXPECTED)} baseline models and {len(files)-len(EXPECTED)} geometry files.')
    print('Left Ground thorax fallback is handled in server/left_adapter.py; original XML is unchanged.')
