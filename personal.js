import './vendor/three.min.js';
import './vendor/orbit-controls.js';
import {validateResult,meshAlias,applyPlaybackBoneVisibility,scaleRowLabel,scaleRowNote} from './personal-state.js';
import {captureAtMedia,mediaAtCapture,nearestFrame,validateVideoSync,videoProjection} from './video-sync.js';
import {tendonScaleResult} from './tendon-scale.js';
import {recordLabel,LatestLoad,delay,requestJSON as request} from './personal-loading.js';

const THREE=window.THREE;
const $=id=>document.getElementById(id);
const element=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
const button=(text,action)=>{const e=element('button','visibility-toggle',text);e.type='button';e.addEventListener('click',action);return e;};
let viewer=null,data=null,playing=false,playhead=0,activeFrame=-1,sync=null,records=[];
const loads=new LatestLoad();
document.body.classList.add('personal-mode');
const comparison=element('div','personal-comparison');
const modelPane=element('section','comparison-pane');
const videoPane=element('section','comparison-pane');
const stage=$('stage');stage.before(comparison);
modelPane.append(element('h2','','模型解算 · 右手'),stage);
const video=element('video','reference-video');video.muted=true;video.playsInline=true;video.preload='auto';video.disablePictureInPicture=true;
video.setAttribute('aria-label','同一记录的右手真实视频');
videoPane.append(element('h2','','真实视频 · 右手'),video);
comparison.append(modelPane,videoPane);
const status=element('span','personal-status','连接服务器…');status.setAttribute('role','status');
document.querySelector('.topbar').append(status);
const link=document.querySelector('.personal-entry');link.textContent='原有视图';link.href='./';
document.querySelector('.panel-heading h2').textContent='个人手部';
document.querySelector('.joint-count').textContent='右手';
document.querySelector('.view-tools').hidden=true;
const content=$('joint-list');content.replaceChildren();
const loader=element('div','personal-load');
const search=element('input','record-search');search.type='search';search.placeholder='搜索日期、文件名或设备';search.setAttribute('aria-label','搜索服务器记录');search.disabled=true;
const recordCount=element('p','record-count');recordCount.setAttribute('role','status');
const select=element('select');select.setAttribute('aria-label','记录');select.disabled=true;
const side=element('select','hand-select');side.setAttribute('aria-label','左右手');side.disabled=true;
for(const [value,label] of [['right','右手'],['left','左手']]){const o=element('option','',label);o.value=value;side.append(o);}
side.value=new URLSearchParams(location.search).get('hand')==='left'?'left':'right';
const sideQuery=hand=>hand==='left'?'&hand=left':'';
const loadButton=button('加载',loadRecording);loadButton.disabled=true;
loader.append(search,recordCount,select,side,loadButton);content.append(loader);
const viewTools=element('div','personal-tools');
const videoViewButton=button('视频视角',()=>viewer?.matchVideoCamera());
videoViewButton.disabled=true;
videoViewButton.title='恢复与右侧视频对应的模型视角';
viewTools.append(videoViewButton);content.append(viewTools);
function filterRecords(){
  const current=select.value,query=search.value.trim().toLowerCase();
  const shown=records.filter(r=>[r.label,r.sourceFile,r.id].join(' ').toLowerCase().includes(query));
  select.replaceChildren(...shown.map(r=>{const o=element('option','',r.label.replace(/ · [左右]手$/,''));o.value=r.id;o.title=r.sourceFile||r.label;return o;}));
  if(shown.some(r=>r.id===current))select.value=current;
  recordCount.textContent=`共 ${records.length} 条记录`+(query?` · 找到 ${shown.length} 条`:'');
  if(loads.current&&select.value!==loads.current.id)cancelLoading();
  updateLoadControls();
}
search.addEventListener('input',filterRecords);
select.addEventListener('change',cancelLoading);
side.addEventListener('change',cancelLoading);
function updateLoadControls(){
  search.disabled=!records.length;side.disabled=!records.length;select.disabled=!select.options.length;
  loadButton.disabled=!select.value;loadButton.textContent=loads.current?'停止等待':'加载';
}
function cancelLoading(){
  if(!loads.current)return;
  loads.cancel();updateLoadControls();
  status.textContent='已停止等待，可加载其他记录';
  error.hidden=!!data;if(!data)error.textContent='请选择记录';
}
const info=element('div','personal-info');content.append(info);
const error=$('model-error');error.textContent='请选择记录';error.hidden=false;
const scrub=$('motion-progress');scrub.min='0';scrub.step='0.001';
$('motion-title').textContent='真实动作';
$('motion-angle-label').hidden=true;$('motion-hint').hidden=true;
document.querySelector('.scrub-label').textContent='时间';
$('motion-neutral').hidden=true;
const play=$('motion-play');
play.disabled=true;
play.addEventListener('click',async()=>{
  if(!data||!sync)return;
  if(playing){stop();return;}
  if(playhead>=data.frames.at(-1).time-.04)seek(data.frames[0].time);
  try{await video.play();playing=true;play.textContent='暂停';viewer?.render();}catch{status.textContent='视频无法播放';}
});
scrub.addEventListener('input',()=>{stop();seek(Number(scrub.value));});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
function stop(){playing=false;video.pause();play.textContent=data&&playhead>=data.frames.at(-1).time-.04?'重播':'播放';viewer?.render();}
function seek(seconds){if(!data||!sync)return;video.currentTime=mediaAtCapture(sync,data.report.motion.startS+seconds);showTime(seconds);}
function showTime(seconds){
  if(!data)return;
  playhead=Math.min(seconds,data.frames.at(-1).time);scrub.value=String(playhead);
  $('motion-angle').textContent=`${playhead.toFixed(1)} s`;
  const index=nearestFrame(data.frames,playhead);
  if(index!==activeFrame){activeFrame=index;viewer.setFrame(data.frames[index]);}
}
function updateFromVideo(mediaTime){
  if(!data||!sync||!viewer)return;
  const time=captureAtMedia(sync,mediaTime)-data.report.motion.startS;
  showTime(Math.max(data.frames[0].time,time));
  if(playing&&time>=data.frames.at(-1).time){stop();seek(data.frames.at(-1).time);}
}
if(video.requestVideoFrameCallback){
  const decoded=(_,metadata)=>{updateFromVideo(metadata.mediaTime);video.requestVideoFrameCallback(decoded);};video.requestVideoFrameCallback(decoded);
}else{
  const tick=()=>{if(playing&&!video.seeking)updateFromVideo(video.currentTime);requestAnimationFrame(tick);};requestAnimationFrame(tick);
}
video.addEventListener('seeked',()=>updateFromVideo(video.currentTime));
video.addEventListener('ended',stop);
video.addEventListener('error',()=>{if(!data)return;stop();play.disabled=true;status.textContent='视频加载失败，请重新加载';});

async function connect(){
  try{
    records=(await request('/api/recordings')).map(r=>({...r,label:recordLabel(r.label)}));
    filterRecords();status.textContent='请选择记录';
    if(select.value)await runLoad(false);
  }catch(e){status.textContent=e.message;error.textContent=e.message;error.hidden=false;updateLoadControls();}
}
async function loadRecording(){
  if(loads.current){cancelLoading();return;}
  await runLoad(true);
}
async function runLoad(submit){
  const id=select.value,hand=side.value;if(!id)return;
  const load=loads.start(id,hand),{signal}=load;
  updateLoadControls();stop();error.hidden=true;status.textContent='连接服务器…';
  try{
    if(submit)await request(hand==='left'?'/api/jobs?hand=left':'/api/jobs',{signal,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({recordingId:id,hand})});
    await poll(id,hand,signal,!submit);
  }catch(e){if(!signal.aborted){status.textContent=e.message;error.textContent=e.message;error.hidden=false;}}
  finally{loads.finish(load);updateLoadControls();}
}
async function poll(id,hand,signal,probeOnly=false){
  for(;;){
    const job=await request('/api/job?recordingId='+encodeURIComponent(id)+sideQuery(hand),{signal});
    signal.throwIfAborted();
    if(job.status==='ready'){await receive(id,hand,signal);return;}
    if(probeOnly&&!['running','queued'].includes(job.status)){status.textContent='请选择记录';error.textContent='请选择记录';error.hidden=false;return;}
    if(job.status==='error')throw new Error(job.message||'解算失败，请重新加载');
    if(!['running','queued'].includes(job.status))throw new Error('解算任务未就绪，请重新加载');
    probeOnly=false;
    status.textContent=job.status==='queued'?'等待解算':job.progress?`计算 ${job.progress.done} / ${job.progress.total}`:job.stage||'准备解算…';
    await delay(1500,signal);
  }
}
async function receive(id,hand,signal){
  status.textContent='加载模型…';
  const next=validateResult(await request('/api/result?recordingId='+encodeURIComponent(id)+sideQuery(hand),{signal},300000));
  if(next.recordingId!==id||next.hand!==hand)throw new Error('模型记录或左右手不匹配');
  const record=records.find(r=>r.id===id);
  const nextSync=validateVideoSync(await request(record.videoBase+(hand==='left'?'/cam0-left-sync.json':'/cam0-sync.json'),{signal}),next);
  await delay(0,signal);
  stop();viewer?.dispose();viewer=null;data=null;sync=null;play.disabled=true;videoViewButton.disabled=true;info.replaceChildren();
  await new Promise((resolve,reject)=>{
    const cleanup=()=>{clearTimeout(timer);video.removeEventListener('loadedmetadata',done);video.removeEventListener('error',fail);signal.removeEventListener('abort',abort);};
    const done=()=>{cleanup();resolve();},fail=()=>{cleanup();reject(new Error('视频加载失败'));};
    const abort=()=>{cleanup();video.pause();video.removeAttribute('src');video.load();reject(signal.reason);};
    const timer=setTimeout(fail,30000);
    video.addEventListener('loadedmetadata',done,{once:true});video.addEventListener('error',fail,{once:true});
    signal.addEventListener('abort',abort,{once:true});
    video.src=record.videoBase+`/cam0-${hand}.mp4`;video.load();
  });
  signal.throwIfAborted();
  if(Math.abs(video.duration-nextSync.frameCount/nextSync.mediaFps)>.05)throw new Error('视频帧数与同步表不匹配');
  data=next;sync=nextSync;
  const sideName=hand==='left'?'左手':'右手';
  modelPane.querySelector('h2').textContent='模型解算 · '+sideName;videoPane.querySelector('h2').textContent='真实视频 · '+sideName;
  document.querySelector('.joint-count').textContent=sideName;video.setAttribute('aria-label','同一记录的'+sideName+'真实视频');
  viewer=new PersonalViewer(data);buildInfo(data);activeFrame=-1;videoViewButton.disabled=false;
  $('motion-controls').hidden=false;scrub.max=String(data.frames.at(-1).time);
  $('motion-min').textContent='0 s';$('motion-max').textContent=`${data.frames.at(-1).time.toFixed(1)} s`;
  error.hidden=true;play.disabled=false;seek(data.frames[0].time);
}

function buildInfo(result){
  info.replaceChildren();
  const measurements=element('details','personal-section');measurements.open=true;
  measurements.append(element('summary','','个人尺寸'));
  const table=element('table','scale-table');
  const head=element('tr');for(const text of ['部位','基准','观测','输出','状态'])head.append(element('th','',text));table.append(head);
  const mm=value=>Number.isFinite(value)?(value*1000).toFixed(1):'—';
  for(const row of result.report.allSegments||result.report.scaledSegments){
    const state=scaleRowLabel(row);
    const tr=element('tr');tr.title=scaleRowNote(row);for(const text of [row.label,mm(row.baseLengthM),mm(row.targetLengthM??row.lengthM),mm(row.resultLengthM),state])tr.append(element('td','',text));table.append(tr);
  }
  measurements.append(element('p','scale-unit','单位 mm'),table);
  const palm=result.report.palmLayout;
  if(palm?.status==='inferred'){
    measurements.append(element('p','scale-unit','手指根部位置调整'));
    const shifts=element('table','scale-table');
    ['食指','中指','无名指','小指'].forEach((name,i)=>{const row=element('tr');row.append(element('td','',name+'根部'),element('td','','相对原模型移动 '+mm(Math.hypot(...palm.shiftsGroundM[i]))+' mm'));shifts.append(row);});measurements.append(shifts);
  }
  info.append(measurements);
  const paths=element('details','personal-section');paths.open=true;
  paths.append(element('summary','',`肌腱通道 · ${result.muscleNames.length}`));
  for(const [i,id] of result.muscleNames.entries()){
    const row=element('div','personal-tendon');const header=element('div','personal-tendon-header');const name=element('span','',id);name.style.color=viewer.colors[i];
    const toggle=button(viewer.paths[i].visible?'Hide':'Display',()=>{
      viewer.paths[i].visible=!viewer.paths[i].visible;toggle.textContent=viewer.paths[i].visible?'Hide':'Display';toggle.setAttribute('aria-pressed',String(viewer.paths[i].visible));viewer.render();
    });toggle.setAttribute('aria-label',`显示或隐藏 ${id}`);toggle.setAttribute('aria-pressed',String(viewer.paths[i].visible));header.append(name,toggle);row.append(header);
    const scaling=tendonScaleResult(result,id);
    if(scaling){
      const table=element('table','tendon-scale-table');table.setAttribute('aria-label',id+'通路缩放结果');
      const heads=element('tr');for(const label of ['基准 mm','个人 mm','变化']){const th=element('th','',label);th.scope='col';heads.append(th);}
      const values=element('tr');for(const value of [mm(scaling.baseLengthM),mm(scaling.personalLengthM),(scaling.changePercent>0?'+':'')+scaling.changePercent.toFixed(1)+'%'])values.append(element('td','',value));
      const thead=element('thead');thead.append(heads);const tbody=element('tbody');tbody.append(values);table.append(thead,tbody);row.append(table);
      row.append(element('p','tendon-scale-status'+(scaling.review?' needs-review':''),scaling.review?'模型通路待检查':scaling.status));
    }else row.append(element('p','tendon-scale-status','暂无对应的缩放结果'));
    paths.append(row);
  }
  info.append(paths);
  const report=element('details','personal-section personal-report');
  report.append(element('summary','','核验结果'));
  if(result.report.baseModelName)report.append(element('p','',`基准：${result.report.baseModelName}`));
  if(result.report.scalingQC){
    const qc=result.report.scalingQC.romPaths;
    report.append(element('p','',`路径检查：${qc.coordinates} 个自由度，每个 ${qc.samplesPerCoordinate} 点；${qc.momentArmJumpWarnings.length} 项力臂变化需复核`));
  }
  if(result.report.scaleRatioWarnings?.length)report.append(element('p','','部分骨段与基准尺寸差异较大，需要定位复核'));
  for(const row of result.report.scaledSegments){
    const note=scaleRowNote(row);if(note)report.append(element('p','',`${row.label}：${note}`));
  }
  report.append(element('p','',`关键点拟合误差中位数 ${result.report.motion.rmseMedianMm.toFixed(1)} mm`));
  const names={1:'拇指基部',4:'拇指尖',8:'食指尖',12:'中指尖',16:'无名指尖',20:'小指尖'};
  for(const item of result.report.motion.correspondenceWarnings||[])report.append(element('p','',`${names[item.index]||'关键点 '+item.index}偏差 ${item.medianMm.toFixed(1)} mm · 需复核`));
  const thumbSupport=result.report.motion.distalObservationSupport?.ip_flexion;
  if(thumbSupport&&thumbSupport.observedFrames<thumbSupport.totalFrames)report.append(element('p','',`拇指末节有效观测 ${thumbSupport.observedFrames} / ${thumbSupport.totalFrames} 帧；缺点帧角度由模型约束延续`));
  for(const note of result.report.unavailable)report.append(element('p','',note));
  info.append(report);
}

class PersonalViewer{
  constructor(result){
    this.data=result;this.canvas=$('canvas');this.stage=$('stage');
    // Personal playback shows only model geometry; names remain in the sidebar.
    for(const id of ['path-labels','side-labels']){$(id)?.replaceChildren();if($(id))$(id).style.display='none';}
    this.scene=new THREE.Scene();this.scene.background=new THREE.Color(0x111315);
    this.camera=new THREE.PerspectiveCamera(38,1,.001,5);this.camera.up.set(0,-1,0);
    this.renderer=new THREE.WebGLRenderer({canvas:this.canvas,antialias:true});this.renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));this.renderer.outputEncoding=THREE.sRGBEncoding;
    this.controls=new THREE.OrbitControls(this.camera,this.canvas);this.controls.minDistance=.08;this.controls.maxDistance=1.5;
    this.scene.add(new THREE.HemisphereLight(0xfff7e7,0x303947,.95));const lamp=new THREE.DirectionalLight(0xffffff,.85);lamp.position.set(-.3,-.4,-.5);this.scene.add(lamp);
    const material=new THREE.MeshStandardMaterial({color:0xdcd5c4,roughness:.78,side:THREE.DoubleSide});
    this.bodyGroups=result.bodyNames.map(()=>{const g=new THREE.Group();g.matrixAutoUpdate=false;this.scene.add(g);return g;});this.bones=[];
    for(const item of result.meshes){
      const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(item.vertices,3));g.setIndex(item.faces);g.computeVertexNormals();
      const mesh=new THREE.Mesh(g,material);mesh.name=meshAlias(item.name);this.bodyGroups[item.body].add(mesh);this.bones.push(mesh);
    }
    this.colors=result.muscleNames.map((_,i)=>`hsl(${Math.round(i*137.508)%360},65%,66%)`);
    this.paths=result.muscleNames.map((name,i)=>{
      const capacity=Math.max(...result.frames.filter(f=>f.paths).map(f=>f.paths[i].length-1));
      const cylinder=new THREE.CylinderGeometry(1,1,1,8);
      const mesh=new THREE.InstancedMesh(cylinder,new THREE.MeshBasicMaterial({color:this.colors[i]}),capacity);
      mesh.visible=true;mesh.frustumCulled=false;mesh.name=name;this.scene.add(mesh);return mesh;
    });
    this.dummy=new THREE.Object3D();this.up=new THREE.Vector3(0,1,0);
    this.raw=new THREE.Points(new THREE.BufferGeometry(),new THREE.PointsMaterial({color:0xffffff,size:.002,sizeAttenuation:true,depthTest:false}));this.raw.visible=false;this.scene.add(this.raw);
    this.controls.addEventListener('start',()=>{this.videoCamera=false;this.resize();});
    this.controls.addEventListener('change',()=>this.render());
    this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(this.stage);
    const first=result.frames.find(f=>f.bones);
    const handPoints=first.raw.filter(Boolean);const box=new THREE.Box3().setFromPoints(handPoints.map(p=>new THREE.Vector3(...p)));
    box.getCenter(this.controls.target);this.matchVideoCamera();this.resize();
  }
  matchVideoCamera(){
    const origin=this.data.report.motion.displayOriginWorldM;
    this.videoCamera=false;this.camera.position.set(...origin.map(v=>-v));
    this.camera.up.set(0,-1,0);this.controls.target.set(-origin[0],-origin[1],.7-origin[2]);
    this.controls.update();this.videoCamera=true;this.resize();
  }
  setFrame(frame){
    this.current=frame;
    const missing=frame.status==='missing';
    if(missing){status.textContent='无效帧';this.scene.visible=false;this.render();return;}
    this.scene.visible=true;
    const scaleReview=this.data.report.scalingQC?.romPaths.status==='review'||this.data.report.scaleRatioWarnings?.length;
    status.textContent=scaleReview?'缩放候选 · 需复核':frame.status==='review'?'拟合需复核':'手部拟合';
    frame.bones.forEach((m,i)=>{this.bodyGroups[i].matrix.fromArray(m);});
    frame.paths.forEach((points,i)=>{
      const mesh=this.paths[i];mesh.count=points.length-1;
      for(let j=0;j<points.length-1;j++){
        const a=new THREE.Vector3(...points[j]),b=new THREE.Vector3(...points[j+1]),delta=b.clone().sub(a);
        this.dummy.position.copy(a).add(b).multiplyScalar(.5);this.dummy.quaternion.setFromUnitVectors(this.up,delta.length()>1e-9?delta.clone().normalize():this.up);this.dummy.scale.set(.00045,delta.length(),.00045);this.dummy.updateMatrix();mesh.setMatrixAt(j,this.dummy.matrix);
      }
      mesh.instanceMatrix.needsUpdate=true;
    });
    this.raw.geometry.setAttribute('position',new THREE.Float32BufferAttribute(frame.raw.filter(Boolean).flat(),3));this.raw.geometry.computeBoundingSphere();
    this.render();
  }
  resize(){
    const {width,height}=this.stage.getBoundingClientRect();if(!width||!height)return;
    this.width=width;this.height=height;this.camera.aspect=width/height;this.camera.updateProjectionMatrix();
    if(this.videoCamera){
      this.camera.projectionMatrix.set(...videoProjection(sync,this.camera.near,this.camera.far));
      this.camera.projectionMatrixInverse.copy(this.camera.projectionMatrix).invert();
    }
    this.renderer.setSize(width,height,false);this.render();
  }
  render(){
    applyPlaybackBoneVisibility(this.bodyGroups,this.data.bodyNames,playing,this.current?.status==='missing');
    if(!this.width)return;this.scene.updateMatrixWorld(true);this.camera.updateMatrixWorld(true);
    this.renderer.render(this.scene,this.camera);
  }
  dispose(){this.resizeObserver.disconnect();this.controls.dispose();this.scene.traverse(o=>{o.geometry?.dispose();if(o.material)o.material.dispose();});this.renderer.dispose();}
}
window.personalHand=Object.freeze({snapshot:()=>({ready:!!viewer,recordingId:data?.recordingId,frame:activeFrame,playing,source:data?.report.source.pointField,baseHash:data?.plan.baseModelHash,hand:data?.hand,scaledSegments:data?.report.scaledSegments.length})});
connect();
