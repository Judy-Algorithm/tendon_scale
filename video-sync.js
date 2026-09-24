// Media has one frame per original packet. Never infer capture time from FPS alone.
export function validateVideoSync(meta,result){
  if(meta.schemaVersion!=='1.0'||meta.hand!==result.hand||meta.sourceHash!==result.report.source.sourceHash)throw new Error('视频与模型记录不匹配');
  if(result.recordingId&&meta.recordingId!==result.recordingId)throw new Error('视频与模型记录编号不匹配');
  if(meta.mediaFps!==30||meta.frameTimesS?.length!==meta.frameCount||meta.frameCount<2)throw new Error('视频时间轴不完整');
  if(!meta.frameTimesS.every((t,i,a)=>Number.isFinite(t)&&(!i||t>a[i-1])))throw new Error('视频时间轴无效');
  if(!meta.crop?.every(Number.isFinite)||meta.crop.length!==4||meta.crop[2]<=0||meta.crop[3]<=0)throw new Error('视频视角无效');
  const start=result.report.motion.startS+result.frames[0].time,end=result.report.motion.startS+result.frames.at(-1).time;
  if(start<meta.frameTimesS[0]||end>meta.frameTimesS.at(-1))throw new Error('视频未覆盖模型时间段');
  return meta;
}
export function captureAtMedia(meta,seconds){
  const index=Math.max(0,Math.min(seconds*meta.mediaFps,meta.frameCount-1)),i=Math.floor(index);
  return meta.frameTimesS[i]+(index-i)*((meta.frameTimesS[i+1]??meta.frameTimesS[i])-meta.frameTimesS[i]);
}
export function mediaAtCapture(meta,seconds){
  const a=meta.frameTimesS;
  if(seconds<=a[0])return 0;
  if(seconds>=a.at(-1))return (a.length-1)/meta.mediaFps;
  let lo=0,hi=a.length-1;
  while(hi-lo>1){const mid=Math.floor((lo+hi)/2);if(a[mid]<=seconds)lo=mid;else hi=mid;}
  return (lo+(seconds-a[lo])/(a[hi]-a[lo]))/meta.mediaFps;
}
export function nearestFrame(frames,seconds){
  let lo=0,hi=frames.length-1;
  while(lo<hi){const mid=Math.floor((lo+hi)/2);if(frames[mid].time<seconds)lo=mid+1;else hi=mid;}
  return lo&&seconds-frames[lo-1].time<=frames[lo].time-seconds?lo-1:lo;
}
export function videoProjection(meta,near,far){
  const [x,y,w,h]=meta.crop,k=meta.intrinsics;
  return [2*k[0][0]/w,0,1-2*(k[0][2]-x)/w,0,
    0,2*k[1][1]/h,2*(k[1][2]-y)/h-1,0,
    0,0,-(far+near)/(far-near),-2*far*near/(far-near),0,0,-1,0];
}
