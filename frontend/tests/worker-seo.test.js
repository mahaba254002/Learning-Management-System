import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import worker from '../worker.js';
const site='https://skynet.mahaba955.workers.dev';
const env={PUBLIC_SITE_ORIGIN:site,INDEX_PUBLIC_SITE:true,API_ORIGIN:'https://api.example.test',ASSETS:{fetch:async()=>new Response('<html>Skynet</html>',{headers:{'Content-Type':'text/html'}})}};

test('deployment routes HTML through the Worker before SPA assets',()=>{
  const config=JSON.parse(readFileSync(new URL('../wrangler.jsonc',import.meta.url),'utf8'));
  assert.equal(config.assets.run_worker_first,true,'Private HTML must receive Worker indexing and caching headers');
  assert.equal(config.assets.binding,'ASSETS','Worker asset responses require the named ASSETS binding');
});
test('public homepage has canonical header and preserves HTML',async()=>{const r=await worker.fetch(new Request(site+'/'),env);assert.equal(await r.text(),'<html>Skynet</html>');assert.equal(r.headers.get('X-Robots-Tag'),null);assert.equal(r.headers.get('Link'),`<${site}/>; rel="canonical"`);});
test('private pages prohibit indexing and cached HTML',async()=>{for(const path of ['/platform/dashboard','/student/login','/invite/private-token']){const r=await worker.fetch(new Request(site+path),env);assert.equal(r.headers.get('X-Robots-Tag'),'noindex, nofollow');assert.equal(r.headers.get('Cache-Control'),'no-store');}});
test('production sitemap includes homepage only',async()=>{const r=await worker.fetch(new Request(site+'/sitemap.xml'),env);assert.equal(r.status,200);const xml=await r.text();assert(xml.includes('<loc>'+site+'/</loc>'));assert(!xml.includes('/student'));});
test('preview and alternate hosts cannot index or expose sitemap',async()=>{for(const preview of [{...env,INDEX_PUBLIC_SITE:false},env]){const url='https://branch-rollback.example.workers.dev';const robots=await worker.fetch(new Request(url+'/robots.txt'),preview);assert.equal(await robots.text(),'User-agent: *\nDisallow: /\n');assert.equal((await worker.fetch(new Request(url+'/sitemap.xml'),preview)).status,404);assert.equal((await worker.fetch(new Request(url+'/'),preview)).headers.get('X-Robots-Tag'),'noindex, nofollow');}});
test('unconfigured staging API fails closed instead of using production',async()=>{const r=await worker.fetch(new Request(site+'/api/me'),{...env,API_ORIGIN:''});assert.equal(r.status,503);assert((await r.json()).detail.includes('staging'));});
test('proxy preserves request and response including cookies',async()=>{const previous=globalThis.fetch;let target;globalThis.fetch=async request=>{target=request;return new Response('{"saved":true}',{status:201,headers:{'Set-Cookie':'access_token=example; Secure; HttpOnly','Content-Type':'application/json'}});};try{const r=await worker.fetch(new Request(site+'/api/drafts?kind=assignment',{method:'POST',headers:{Cookie:'csrf_token=example','X-CSRF-Token':'example'},body:'draft'}),env);assert.equal(target.url,'https://api.example.test/api/drafts?kind=assignment');assert.equal(await target.text(),'draft');assert.equal(target.headers.get('X-CSRF-Token'),'example');assert.equal(r.status,201);assert.equal(await r.text(),'{"saved":true}');assert(r.headers.get('Set-Cookie').includes('HttpOnly'));assert.equal(r.headers.get('Cache-Control'),'no-store');assert.equal(r.headers.get('X-Robots-Tag'),'noindex, nofollow');}finally{globalThis.fetch=previous;}});
test('invalid upstream origins are rejected',async()=>{for(const origin of ['http://api.example.test','https://api.example.test/other','https://user:secret@api.example.test'])assert.equal((await worker.fetch(new Request(site+'/api/me'),{...env,API_ORIGIN:origin})).status,503);});
