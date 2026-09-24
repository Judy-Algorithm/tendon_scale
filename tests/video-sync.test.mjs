import test from 'node:test';
import assert from 'node:assert/strict';
import {captureAtMedia,mediaAtCapture,nearestFrame,validateVideoSync,videoProjection} from '../video-sync.js';
import {parseRange} from '../scripts/media-range.mjs';
const meta={schemaVersion:'1.0',hand:'right',sourceHash:'same',mediaFps:30,frameCount:4,frameTimesS:[10,10.032,10.069,10.102],crop:[0,0,640,360]};
const result={hand:'right',frames:[{time:0},{time:.08}],report:{source:{sourceHash:'same'},motion:{startS:10}}};
test('video and model require the same recording, side and covered capture interval',()=>{
  assert.equal(validateVideoSync(meta,result),meta);
  assert.throws(()=>validateVideoSync({...meta,hand:'left'},result));
  assert.throws(()=>validateVideoSync({...meta,sourceHash:'different'},result));
  assert.throws(()=>validateVideoSync({...meta,frameTimesS:[10,10.032,10.032,10.102]},result));
  assert.throws(()=>validateVideoSync(meta,{...result,frames:[{time:0},{time:.2}]}));
  assert.equal(validateVideoSync({...meta,recordingId:'sample-02'},{...result,recordingId:'sample-02'}).recordingId,'sample-02');
  assert.throws(()=>validateVideoSync({...meta,recordingId:'sample-01'},{...result,recordingId:'sample-02'}));
});
test('irregular capture intervals map reversibly without FPS clock drift',()=>{
  for(const capture of [10,10.001,10.032,10.056,10.069,10.1,10.102])assert.ok(Math.abs(captureAtMedia(meta,mediaAtCapture(meta,capture))-capture)<1e-12);
  assert.equal(captureAtMedia(meta,2/30),10.069);
  assert.equal(mediaAtCapture(meta,9),0);
  assert.equal(mediaAtCapture(meta,11),.1);
  assert.equal(nearestFrame([{time:0},{time:.033},{time:.067}],.025),1);
});
test('video range serving supports seeks, suffixes, HEAD-sized ranges and rejects invalid ranges',()=>{
  assert.deepEqual(parseRange('bytes=10-19',100),{start:10,end:19});
  assert.deepEqual(parseRange('bytes=90-',100),{start:90,end:99});
  assert.deepEqual(parseRange('bytes=-8',100),{start:92,end:99});
  assert.equal(parseRange(undefined,100),null);
  for(const h of ['bytes=100-','bytes=9-8','bytes=-0','bytes=-','bytes=0-1,3-4'])assert.throws(()=>parseRange(h,100));
});
test('camera projection matches calibrated pixels after OpenCV-to-Three axis conversion and fixed crop',()=>{
  const calibration={crop:[328,16,640,360],intrinsics:[[846.7,0,640.73],[0,846.39,360.46],[0,0,1]]};
  const matrix=videoProjection(calibration,.001,5);
  for(const p of [[0,0,.7],[.1,-.15,.62],[-.05,.08,.8]]){
    const eye=[p[0],-p[1],-p[2],1];
    const c=Array.from({length:4},(_,i)=>eye.reduce((sum,v,j)=>sum+matrix[4*i+j]*v,0));
    const pixel=[(c[0]/c[3]+1)*320,(1-c[1]/c[3])*180];
    assert.ok(Math.abs(pixel[0]-(846.7*p[0]/p[2]+640.73-328))<1e-9);
    assert.ok(Math.abs(pixel[1]-(846.39*p[1]/p[2]+360.46-16))<1e-9);
  }
});
