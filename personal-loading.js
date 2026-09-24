// Labels are presentation only: recording IDs and server paths remain unchanged.
export function recordLabel(label){
  return label.replace(/^真实记录\s+\d+\s*·\s*/, '').replace(/ · [左右]手$/, '');
}

export class LatestLoad {
  current=null;
  start(id,hand){
    this.cancel();
    const controller=new AbortController();
    return this.current={id,hand,controller,signal:controller.signal};
  }
  cancel(){const previous=this.current;this.current=null;previous?.controller.abort();}
  finish(load){if(this.current===load)this.current=null;}
}

export function delay(ms,signal){
  return new Promise((resolve,reject)=>{
    signal.throwIfAborted();
    const cleanup=()=>{clearTimeout(timer);signal.removeEventListener('abort',abort);};
    const abort=()=>{cleanup();reject(signal.reason);};
    const timer=setTimeout(()=>{cleanup();resolve();},ms);
    signal.addEventListener('abort',abort,{once:true});
  });
}

export async function requestJSON(path,{signal,...options}={},timeoutMs=90000){
  const controller=new AbortController();
  const abort=()=>controller.abort(signal.reason);
  signal?.throwIfAborted();signal?.addEventListener('abort',abort,{once:true});
  const timer=setTimeout(()=>controller.abort(new Error('连接超时，请重新加载')),timeoutMs);
  try{
    const response=await fetch(path,{cache:'no-store',...options,signal:controller.signal});
    if(!response.ok){let message='服务器未连接';try{message=(await response.json()).error||message;}catch{}throw new Error(message);}
    const result=await response.json();
    controller.signal.throwIfAborted();
    return result;
  }catch(e){if(controller.signal.aborted)throw controller.signal.reason;throw e;}
  finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}
