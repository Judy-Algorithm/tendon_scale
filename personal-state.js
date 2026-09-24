export function frameAtTime(frames,seconds){
  if(!frames.length)return -1;
  let lo=0,hi=frames.length-1;
  while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(frames[mid].time<=seconds)lo=mid;else hi=mid-1;}
  return lo;
}
export function validateResult(data){
  if(data.schemaVersion!=='1.0'||!['left','right'].includes(data.hand)||!data.frames?.length||!data.meshes?.length)throw new Error('模型数据不完整');
  const adapters=data.hand==='left'?['arms-left-landmarks-1']:['arms-right-joint-centres-1','arms-right-landmarks-2'];
  if(!adapters.includes(data.plan?.adapter)||(data.plan?.hand&&data.plan.hand!==data.hand))throw new Error('模型对应关系不匹配');
  let previous=-Infinity;
  for(const frame of data.frames){
    if(!Number.isFinite(frame.time)||frame.time<=previous)throw new Error('时间轴无效');
    previous=frame.time;
    if(frame.status==='missing')continue;
    if(frame.bones?.length!==data.bodyNames.length||frame.paths?.length!==data.muscleNames.length)throw new Error('帧数据不完整');
    if(!frame.bones.every(m=>m.length===16&&m.every(Number.isFinite)))throw new Error('骨骼变换无效');
    if(!frame.paths.every(p=>p.length>=2&&p.every(v=>v.length===3&&v.every(Number.isFinite))))throw new Error('肌腱路径无效');
  }
  return data;
}
export const scaleStatusLabel=status=>({scaled:'已缩放',estimated:'已缩放',awaiting_model_landmark:'缺标定',awaiting_input:'暂用基准',review:'需复核',insufficient_data:'缺数据'}[status]||'未缩放');
export function scaleRowLabel(row){
  if(['scaled','estimated'].includes(row.status)&&row.measurementStatus==='review')return '已应用·待复核';
  return scaleStatusLabel(row.status);
}
export function scaleRowNote(row){
  const notes=[];
  if(['scaled','estimated'].includes(row.status)&&row.measurementStatus==='review')notes.push('观测波动较大，已用固定观测中位数缩放，不代表骨长已确认');
  if(row.crossSection==='template_proportional_estimate')notes.push('长度匹配观测，宽厚按模板比例估计');
  if(row.measurementMethod==='repeated_stable_windows')notes.push('观测来自多个一致的稳定片段');
  if(row.status==='review')notes.push('未应用缩放，当前保留基准');
  return notes.join('；');
}
export const meshAlias=name=>({sdfastSCAPHOIDw:'scaphoid',sdfastPISIFORMw:'pisiform',sdfastTRIQUETRALw:'triquetrum'}[name]||name.replace(/^([45](?:mc|proxph|midph|distph))_new$/,'$1'));

const playbackHiddenBones=new Set(['humerus','radius','ulna']);
export function applyPlaybackBoneVisibility(groups,names,playing,missing=false){
  groups.forEach((group,i)=>{group.visible=!missing&&!(playing&&playbackHiddenBones.has(names[i]));});
}
