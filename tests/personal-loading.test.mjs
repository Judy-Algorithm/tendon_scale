import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {recordLabel,LatestLoad,delay,requestJSON} from '../personal-loading.js';

test('legacy and newly indexed records use the same display format',()=>{
  const label='2026-01-01 12:00:00 · 片段 2 · EXAMPLE_DEVICE';
  assert.equal(recordLabel('真实记录 01 · '+label),label);
  assert.equal(recordLabel(label),label);
  assert.equal(recordLabel('真实记录 06 · '+label+' · 左手'),label);
  const source=fs.readFileSync(new URL('../personal.js',import.meta.url),'utf8');
  assert.doesNotMatch(source,/全手缩放尚未完成/);
});

test('cancel interrupts polling and late completion cannot unlock a newer load',async()=>{
  const loads=new LatestLoad(),old=loads.start('sample-01','right');
  const waiting=delay(60000,old.signal);
  const rejection=assert.rejects(waiting,{name:'AbortError'});
  const next=loads.start('sample-02','left');
  await rejection;
  assert.throws(()=>old.signal.throwIfAborted(),{name:'AbortError'});
  loads.finish(old);assert.equal(loads.current,next);
  loads.cancel();assert.equal(loads.current,null);assert.ok(next.signal.aborted);
});

test('network timeouts and manual cancellation release pending requests',async(t)=>{
  t.mock.method(globalThis,'fetch',(_url,{signal})=>new Promise((_,reject)=>{
    signal.addEventListener('abort',()=>reject(signal.reason),{once:true});
  }));
  await assert.rejects(requestJSON('/api/job',{},5),/连接超时/);
  const controller=new AbortController();
  const pending=requestJSON('/api/result',{signal:controller.signal});
  controller.abort();
  await assert.rejects(pending,{name:'AbortError'});
});
