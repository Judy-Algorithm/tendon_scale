// Read-only end-to-end data checks; no browser interaction or visual approval.
import assert from 'node:assert/strict';
import {validateResult} from '../personal-state.js';
import {validateVideoSync,captureAtMedia,mediaAtCapture} from '../video-sync.js';
const base='http://127.0.0.1:4173';
const hand=process.argv.includes('--left')?'left':'right',query=hand==='left'?'&hand=left':'';
const get=async route=>{const response=await fetch(base+route);assert.equal(response.status,200,route);return response.json();};
const records=await get('/api/recordings');assert.equal(records.length,6);
const hashes=new Set();const summaries=[];
for(const record of records){
  let job;
  for(let i=0;i<90;i++){
    job=await get('/api/job?recordingId='+record.id+query);
    if(['ready','error'].includes(job.status))break;
    await new Promise(r=>setTimeout(r,5000));
  }
  assert.equal(job.status,'ready',record.id+': '+job.message);
  const result=validateResult(await get('/api/result?recordingId='+record.id+query));
  assert.equal(result.recordingId,record.id);
  assert.equal(result.hand,hand);assert.equal(result.plan.hand,hand);
  if(process.argv.includes('--observed')){
    assert.equal(result.plan.scalingAlgorithm,'observed-spans-stable-windows-1');
    for(const row of result.report.scaledSegments){
      if(row.measurementStatus==='review'){
        assert.ok(result.report.measurementWarnings.some(w=>w.segment===row.id));
        assert.equal(result.report.status,'review');
      }
    }
  }
  assert.equal(result.plan.adapter,hand==='left'?'arms-left-landmarks-1':'arms-right-landmarks-2');
  assert.equal(result.plan.baseModelHash,hand==='left'?'45c45732788afd4fcc78b89c97cf7a5da51de82dcb735d480459ee4e8770207b':'9a88909ca27da9397abe22599e51ae9699162bdf274f65d2a83d7b02793b24cc');
  assert.equal(result.report.allSegments.length,19);
  assert.equal(result.report.motion.fitCoordinates.length,20);
  assert.ok(!hashes.has(result.plan.sourceHash));hashes.add(result.plan.sourceHash);
  for(const row of result.report.scaledSegments){
    if(['scaled','estimated'].includes(row.status))assert.ok(Math.abs(row.resultLengthM-row.lengthM)<1e-6);
  }
  const sync=validateVideoSync(await get(record.videoBase+(hand==='left'?'/cam0-left-sync.json':'/cam0-sync.json')),result);
  for(const f of result.frames){
    const time=f.time+result.report.motion.startS;
    assert.ok(Math.abs(captureAtMedia(sync,mediaAtCapture(sync,time))-time)<1e-8);
  }
  assert.ok(result.report.motion.pathExportMaxErrorMm<1);
  const video=await fetch(base+record.videoBase+`/cam0-${hand}.mp4`,{headers:{Range:'bytes=0-1023'}});
  assert.equal(video.status,206);assert.equal((await video.arrayBuffer()).byteLength,1024);
  const motion=result.report.motion;
  const summary={id:record.id,hand,sourceFile:result.report.source.sourceFile,frames:motion.frameCount,fitted:motion.fittedFrames,
    rmseMedianMm:motion.rmseMedianMm,reviewFrames:motion.reviewFrames,
    scaled:result.report.scaledSegments.filter(r=>r.status==='scaled').length,
    estimated:result.report.scaledSegments.filter(r=>r.status==='estimated').length,
    observationReview:result.report.scaledSegments.filter(r=>r.measurementStatus==='review').length,
    dimensionReview:result.report.scaledSegments.filter(r=>r.status==='review').length,
    pathErrorMm:motion.pathExportMaxErrorMm};
  summaries.push(summary);console.log(JSON.stringify(summary));
}
console.log('All six distinct recordings passed data and video-sync checks.');
