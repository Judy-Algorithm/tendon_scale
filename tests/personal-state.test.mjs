import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {frameAtTime,validateResult,meshAlias,applyPlaybackBoneVisibility,scaleStatusLabel,scaleRowLabel,scaleRowNote} from '../personal-state.js';

test('applied uncertain observations are not labelled as confirmed lengths or baseline',()=>{
  const row={status:'estimated',measurementStatus:'review'};
  assert.equal(scaleRowLabel(row),'已应用·待复核');
  assert.match(scaleRowNote(row),/固定观测中位数/);
  assert.match(scaleRowNote({status:'scaled',crossSection:'template_proportional_estimate'}),/宽厚按模板/);
  assert.match(scaleRowNote({status:'review'}),/未应用缩放/);
});

test('personal playback uses measured timestamps and preserves missing frames',()=>{
  const frames=[{time:.01},{time:.12,status:'missing'},{time:.25}];
  assert.equal(frameAtTime(frames,-1),0);
  assert.equal(frameAtTime(frames,.12),1);
  assert.equal(frameAtTime(frames,.2),1);
  assert.equal(frameAtTime(frames,2),2);
  assert.equal(frameAtTime([],0),-1);
});
test('playback hides exactly the three arm bones and restores them on pause without changing transforms',()=>{
  const names=['humerus','ulna','radius','proximal_row','capitate','firstmc','3proxph','3midph','3distph'];
  const groups=names.map(()=>({visible:true,matrix:{unchanged:true}}));
  const matrices=groups.map(g=>g.matrix);
  for(const playing of [false,true,true,false,true,false]){
    applyPlaybackBoneVisibility(groups,names,playing);
    assert.deepEqual(groups.map(g=>g.visible),names.map((_,i)=>!(playing&&i<3)));
    groups.forEach((g,i)=>assert.equal(g.matrix,matrices[i]));
  }
  applyPlaybackBoneVisibility(groups,names,false,true);
  assert.ok(groups.every(g=>!g.visible));
  applyPlaybackBoneVisibility(groups,names,true,false);
  assert.deepEqual(groups.map(g=>g.visible),[false,false,false,true,true,true,true,true,true]);
});
test('personal data rejects side, schema, malformed transforms and duplicate time',()=>{
  const fixture=()=>({schemaVersion:'1.0',hand:'right',meshes:[{}],bodyNames:['bone'],muscleNames:['muscle'],plan:{adapter:'arms-right-joint-centres-1'},frames:[{time:0,status:'fitted',bones:[Array(16).fill(0)],paths:[[[0,0,0],[0,1,0]]]}]});
  assert.ok(validateResult(fixture()));
  const estimates=fixture();estimates.plan.adapter='arms-right-landmarks-2';assert.ok(validateResult(estimates));
  const unknown=fixture();unknown.plan.adapter='unknown';assert.throws(()=>validateResult(unknown));
  const side=fixture();side.hand='left';assert.throws(()=>validateResult(side));
  side.plan.adapter='arms-left-landmarks-1';side.plan.hand='left';assert.ok(validateResult(side));
  side.plan.hand='right';assert.throws(()=>validateResult(side));
  const broken=fixture();broken.frames[0].bones[0][0]=NaN;assert.throws(()=>validateResult(broken));
  const duplicate=fixture();duplicate.frames.push(duplicate.frames[0]);assert.throws(()=>validateResult(duplicate));
});
test('applied scales share the requested label while quality and missing CMCs remain distinct',()=>{
  assert.equal(scaleStatusLabel('estimated'),'已缩放');
  assert.equal(scaleStatusLabel('scaled'),'已缩放');
  assert.equal(scaleStatusLabel('awaiting_input'),'暂用基准');
  const source=fs.readFileSync(new URL('../personal.js',import.meta.url),'utf8');
  assert.match(source,/手指根部位置调整/);
  assert.match(source,/相对原模型移动/);
  assert.doesNotMatch(source,/末节角未解算/);
  assert.match(source,/if\(!data\|\|!sync\|\|!viewer\)return/);
});
test('personal view restores video camera button without bringing back raw point controls',()=>{
  const source=fs.readFileSync(new URL('../personal.js',import.meta.url),'utf8');
  assert.doesNotMatch(source,/button\('原始点'/);
  assert.match(source,/button\('视频视角',\(\)=>viewer\?\.matchVideoCamera\(\)\)/);
  assert.match(source,/videoViewButton\.disabled=true/);
  assert.match(source,/videoViewButton\.disabled=false/);
  assert.match(source,/this\.raw\.visible=false/);
  assert.match(source,/this\.matchVideoCamera\(\);this\.resize\(\)/);
});
test('personal entry imports no atlas, SHM controls or old illustrative motion',()=>{
  const source=fs.readFileSync(new URL('../personal.js',import.meta.url),'utf8');
  for(const forbidden of ['atlas-data','control-data','model-data','route-data','motion.js'])assert.ok(!source.includes(forbidden));
  assert.doesNotMatch(source,/BoneHover|createElementNS|this\.labels|this\.hover/);
  assert.match(source,/mesh\.visible=true/);
  assert.match(source,/frame\.paths/);
  assert.match(source,/frame\.bones\.forEach/);
  assert.equal(meshAlias('sdfastSCAPHOIDw'),'scaphoid');
  assert.equal(meshAlias('3proxph'),'3proxph');
  assert.equal(meshAlias('4mc_new'),'4mc');
  assert.equal(meshAlias('5mc_new'),'5mc');
  assert.equal(meshAlias('4proxph_new'),'4proxph');
  assert.equal(meshAlias('5distph_new'),'5distph');
});
test('sample switching scopes result, clock and video together and disposes previous model',()=>{
  const source=fs.readFileSync(new URL('../personal.js',import.meta.url),'utf8');
  assert.match(source,/api\/result\?recordingId=/);
  assert.match(source,/next\.recordingId!==id/);
  assert.match(source,/viewer\?\.dispose\(\);viewer=null;data=null;sync=null/);
  assert.ok(source.includes('`/cam0-${hand}.mp4`'));
  assert.match(source,/next\.hand!==hand/);
  assert.doesNotMatch(source,/if\(viewer&&data\.recordingId===id/);
  assert.doesNotMatch(source,/request\('\/media\/sample-01/);
});
