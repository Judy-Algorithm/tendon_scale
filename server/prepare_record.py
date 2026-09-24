"""On-demand source extraction and browser video encoding, in the reader environment."""
import json
import subprocess
import sys
from pathlib import Path
from pathlib import Path
import numpy as np
import imageio_ffmpeg
from extract_rrd import extract
from extract_video import extract as extract_video

def prepare(source,directory,identifier,hand):
    directory.mkdir(parents=True,exist_ok=True)
    raw=directory/'raw.npz'
    if not raw.exists():
        temporary=directory/'raw.tmp.npz';extract(source,temporary);temporary.replace(raw)
    with np.load(raw,allow_pickle=False) as data:
        times=data['capture_timestamp_ns'];duration=float((times[-1]-times[0])/1e9)
        if duration<2:raise ValueError('Recording too short')
    start=30. if duration>=42 else 0.
    end=min(start+12.,duration-.05)
    sync=directory/('cam0-left-sync.json' if hand=='left' else 'cam0-sync.json')
    output=directory/f'cam0-{hand}.mp4'
    if not output.exists() or not sync.exists():
        extract_video(source,raw,directory,identifier,start,end,hand)
        meta=json.loads(sync.read_text());x,y,w,h=meta['crop']
        ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();original=directory/'cam0-original.h265'
        reader=imageio_ffmpeg.read_frames(str(original),pix_fmt='rgb24')
        dimensions=next(reader)['size'];reader.close()
        if list(dimensions)!=meta['resolution']:raise ValueError('Camera resolution differs from audited source')
        # Source packet timestamps can only map directly to displayed frames if
        # the codec does not reorder B pictures. Fail rather than silently desync.
        audit=subprocess.run([ffmpeg,'-v','info','-threads','2','-i',str(original),'-vf','showinfo','-an','-f','null','-'],capture_output=True,text=True,check=True)
        if 'type:B' in audit.stderr:raise ValueError('Video has reordered B frames; timing adapter needs review')
        temp=directory/f'cam0-{hand}.tmp.mp4'
        result=subprocess.run([ffmpeg,'-v','error','-y','-threads','2','-fflags','+genpts','-r','30','-i',str(original),
            '-vf',f'crop={w}:{h}:{x}:{y}','-c:v','libx264','-threads','2','-preset','veryfast','-crf','21',
            '-pix_fmt','yuv420p','-fps_mode','passthrough','-movflags','+faststart','-an','-progress','pipe:1',str(temp)],
            capture_output=True,text=True,check=True)
        counts=[int(line.split('=')[1]) for line in result.stdout.splitlines() if line.startswith('frame=')]
        if not counts or counts[-1]!=meta['frameCount']:raise ValueError('Video frame count changed')
        temp.replace(output)
    (directory/f'window-{hand}.json').write_text(json.dumps(dict(startS=start,endS=end,durationS=duration)))

if __name__=='__main__':prepare(Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3],sys.argv[4])
