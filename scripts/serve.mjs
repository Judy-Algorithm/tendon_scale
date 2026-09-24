import http from 'node:http';
import fs from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import path from 'node:path';
import {parseRange} from './media-range.mjs';
const root=process.cwd();
const personalPorts={left:Number(process.env.TENDON_API_LEFT_PORT||18767),right:Number(process.env.TENDON_API_RIGHT_PORT||8769)};
const catalogPort=Number(process.env.TENDON_CATALOG_PORT||18770);
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml'};
http.createServer(async(req,res)=>{
  try{
    const url=new URL(req.url,'http://localhost');
    const host=req.headers.host||'';
    if(!/^(127\.0\.0\.1|localhost):\d+$/.test(host)){res.writeHead(403).end();return;}
    if(url.pathname.startsWith('/media/')){
      const allowed=new Map(Array.from({length:6},(_,i)=>`sample-${String(i+1).padStart(2,'0')}`).flatMap(id=>[
        [`/media/${id}/cam0-right.mp4`,'video/mp4'],
        [`/media/${id}/cam0-sync.json`,'application/json; charset=utf-8'],
        [`/media/${id}/cam0-left.mp4`,'video/mp4'],
        [`/media/${id}/cam0-left-sync.json`,'application/json; charset=utf-8']
      ]));
      if(!allowed.has(url.pathname)||!['GET','HEAD'].includes(req.method)){res.writeHead(404).end();return;}
      if(req.headers.origin&&req.headers.origin!==`http://${host}`){res.writeHead(403).end();return;}
      const file=path.join(root,'private-media',url.pathname.split('/')[2],path.basename(url.pathname));
      const stat=await fs.stat(file);
      let range;
      try{range=parseRange(req.headers.range,stat.size);}catch{res.writeHead(416,{'Content-Range':`bytes */${stat.size}`}).end();return;}
      const headers={'Content-Type':allowed.get(url.pathname),'Accept-Ranges':'bytes','Cache-Control':'no-store','Content-Length':range?range.end-range.start+1:stat.size};
      if(range)headers['Content-Range']=`bytes ${range.start}-${range.end}/${stat.size}`;
      res.writeHead(range?206:200,headers);
      if(req.method==='HEAD'){res.end();return;}
      const stream=createReadStream(file,range||{});stream.on('error',()=>res.destroy());res.on('close',()=>stream.destroy());stream.pipe(res);return;
    }
    if(url.pathname.startsWith('/api/')){
      const allowed=new Set(['/api/health','/api/recordings','/api/job','/api/result','/api/jobs']);
      const remoteMedia=/^\/api\/media\/record-[a-f0-9]{20}\/cam0-(?:right\.mp4|left\.mp4|sync\.json|left-sync\.json)$/.test(url.pathname);
      if((!allowed.has(url.pathname)&&!remoteMedia)||!['GET','POST','HEAD'].includes(req.method)||(remoteMedia&&req.method==='POST')){res.writeHead(404).end();return;}
      if(req.headers.origin&&req.headers.origin!==`http://${host}`){res.writeHead(403).end();return;}
      if(req.method==='POST'&&(Number(req.headers['content-length']||0)>1024||req.headers['transfer-encoding'])){res.writeHead(413).end();return;}
      const headers={'Accept-Encoding':'gzip'};
      for(const key of ['content-type','content-length','range'])if(req.headers[key])headers[key]=req.headers[key];
      const upstream=http.request({host:'127.0.0.1',port:catalogPort,path:url.pathname+url.search,method:req.method,headers},response=>{
        res.writeHead(response.statusCode,response.headers);response.pipe(res);
      });
      // Large model/video transfers can pause on the SSH connection. Only time
      // out inactivity, and release the old transfer when the browser cancels.
      upstream.setTimeout(60000,()=>upstream.destroy(new Error('Server timeout')));
      res.on('close',()=>upstream.destroy());
      upstream.on('error',()=>{
        if(res.destroyed)return;
        if(res.headersSent){res.destroy();return;}
        res.writeHead(503,{'Content-Type':'application/json'});
        res.end(JSON.stringify({error:'服务器连接暂时中断，请重试加载'}));
      });
      req.pipe(upstream);return;
    }
    const filename=path.resolve(root,'.'+decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname));
    if(!filename.startsWith(root+path.sep)||filename.includes(path.sep+'.git'+path.sep)||filename.startsWith(path.join(root,'private-media')+path.sep)){res.writeHead(403).end();return;}
    const data=await fs.readFile(filename);res.writeHead(200,{'Content-Type':types[path.extname(filename)]||'application/octet-stream','Cache-Control':'no-store'}).end(data);
  }catch{res.writeHead(404).end();}
}).listen(Number(process.env.PORT||4173),'127.0.0.1',()=>console.log('http://127.0.0.1:'+(process.env.PORT||4173)));
