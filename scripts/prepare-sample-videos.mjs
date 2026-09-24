// Convert explicitly downloaded source packets, preserving every source frame.
import fs from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
const run=promisify(execFile);
const root=path.resolve('private-media');
const args=process.argv.slice(2),hand=args.includes('--left')?'left':'right';
for(const id of args.filter(x=>x!=='--left')){
  if(!/^sample-0[1-6]$/.test(id))throw new Error('Only six registered samples are allowed');
  const dir=path.join(root,id),meta=JSON.parse(await fs.readFile(path.join(dir,hand==='left'?'cam0-left-sync.json':'cam0-sync.json'),'utf8'));
  if(meta.recordingId!==id||meta.hand!==hand)throw new Error('Recording or hand mismatch');
  const input=path.join(dir,'cam0-original.h265'),output=path.join(dir,`cam0-${hand}.mp4`);
  const probe=JSON.parse((await run('/opt/homebrew/bin/ffprobe',['-v','error','-select_streams','v:0','-show_entries','stream=width,height,has_b_frames','-of','json',input])).stdout).streams[0];
  if(probe.width!==meta.resolution[0]||probe.height!==meta.resolution[1]||probe.has_b_frames!==0)throw new Error('Camera dimensions/frame ordering not audited');
  const [x,y,w,h]=meta.crop;
  try{await fs.access(output);}catch{
    await run('/opt/homebrew/bin/ffmpeg',['-v','error','-n','-fflags','+genpts','-r','30','-i',input,'-vf',`crop=${w}:${h}:${x}:${y}`,'-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-fps_mode','passthrough','-movflags','+faststart','-an',output],{maxBuffer:1024*1024});
  }
  const encoded=JSON.parse((await run('/opt/homebrew/bin/ffprobe',['-v','error','-select_streams','v:0','-show_entries','stream=nb_frames,width,height,duration','-of','json',output])).stdout).streams[0];
  if(Number(encoded.nb_frames)!==meta.frameCount||encoded.width!==w||encoded.height!==h)throw new Error('Encoded video lost frames or changed crop');
  console.log(JSON.stringify({id,frameCount:meta.frameCount,crop:meta.crop,duration:encoded.duration}));
}
