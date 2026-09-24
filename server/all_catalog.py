"""Read-only task-53 inventory. Each RRD file is a record, not a person."""
import hashlib
import os
import re
from pathlib import Path

SOURCE_ROOT=Path(os.environ.get('TENDON_SOURCE_ROOT','private-data'))
# New deployments use one self-contained catalog, with no private sample IDs.
LEGACY_NAMES=[]

def inventory(root=SOURCE_ROOT):
    root=root.resolve();records={}
    for source in sorted(root.rglob('*.rrd')):
        resolved=source.resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():continue
        relative=source.relative_to(root).as_posix()
        legacy=LEGACY_NAMES.index(source.name)+1 if source.name in LEGACY_NAMES else None
        identifier=f'sample-{legacy:02d}' if legacy else 'record-'+hashlib.sha256(relative.encode()).hexdigest()[:20]
        if identifier in records:raise ValueError('Duplicate catalog identity')
        match=re.search(r'-(\d{8})(\d{6})-(\d+)_h265\.rrd$',source.name)
        date=relative.split('/')[0].removeprefix('dt=')
        label=source.stem
        if match:
            _,clock,clip=match.groups();label=f'{date} {clock[:2]}:{clock[2:4]}:{clock[4:]} · 片段 {clip} · {source.parent.parent.name}'
        if legacy:label=f'真实记录 {legacy:02d} · '+label
        records[identifier]=dict(id=identifier,label=label,date=date,sourceFile=source.name,
            sourcePath=str(resolved),sourceSize=resolved.stat().st_size,sourceMtimeNs=resolved.stat().st_mtime_ns,
            legacy=bool(legacy),videoBase=('/media/' if legacy else '/api/media/')+identifier)
    return dict(sorted(records.items(),key=lambda item:(not item[1]['legacy'],item[1]['label'])))

def public_record(record):
    return {k:v for k,v in record.items() if k not in ('sourcePath','sourceSize','sourceMtimeNs','legacy')}

def checked_source(record):
    path=Path(record['sourcePath']).resolve()
    if not path.is_relative_to(SOURCE_ROOT.resolve()):raise ValueError('Source outside task 53')
    stat=path.stat()
    if stat.st_size!=record['sourceSize'] or stat.st_mtime_ns!=record['sourceMtimeNs']:
        raise ValueError('Source changed since inventory; refresh catalog')
    return path
