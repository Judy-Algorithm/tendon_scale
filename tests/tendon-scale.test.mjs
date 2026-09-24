import test from 'node:test';
import assert from 'node:assert/strict';
import {tendonScaleResult} from '../tendon-scale.js';
const fixture=()=>({hand:'right',plan:{baseModelHash:'9a88909ca27da9397abe22599e51ae9699162bdf274f65d2a83d7b02793b24cc',policies:{muscleLengths:'Final/reference path ratio from immutable base; replace intermediate Scale result'}},report:{muscleParameters:[{id:'FPL',fiberLengthBefore:.1,fiberLengthAfter:.08,tendonSlackBefore:.2,tendonSlackAfter:.16}],scalingQC:{romPaths:{momentArmJumpWarnings:[]}}}});
test('reports whole-path lengths from the saved ratio, not summed muscle parameters',()=>{
  const row=tendonScaleResult(fixture(),'FPL');
  assert.ok(Math.abs(row.personalLengthM-.2654356326504047*.8)<1e-12);
  assert.ok(Math.abs(row.changePercent+20)<1e-12);
  assert.equal(row.status,'已缩放');
  const r=fixture();r.report.muscleParameters[0].fiberLengthAfter=.1;r.report.muscleParameters[0].tendonSlackAfter=.2;
  assert.equal(tendonScaleResult(r,'FPL').status,'长度不变');
  r.report.scalingQC.romPaths.momentArmJumpWarnings=[{muscle:'FPL'}];
  assert.equal(tendonScaleResult(r,'FPL').status,'需复核');
});
test('rejects mismatched templates, missing data and inconsistent parameter ratios',()=>{
  for(const mutate of [r=>r.plan.baseModelHash='different',r=>r.plan.policies.muscleLengths='different',r=>r.report.muscleParameters=[],r=>r.report.muscleParameters[0].fiberLengthBefore=0,r=>r.report.muscleParameters[0].tendonSlackAfter=.19]){
    const r=fixture();mutate(r);assert.equal(tendonScaleResult(r,'FPL'),null);
  }
  const left=fixture();left.hand='left';left.plan.baseModelHash='45c45732788afd4fcc78b89c97cf7a5da51de82dcb735d480459ee4e8770207b';
  assert.ok(tendonScaleResult(left,'FPL'));
  assert.equal(tendonScaleResult(left,'unknown'),null);
});
