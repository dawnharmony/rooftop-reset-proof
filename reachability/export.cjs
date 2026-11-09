const fs=require('fs'),path=require('path'),crypto=require('crypto'),T=require('../engine.js');
const sha=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const original='0a427d28c8ab60e7ee1dc69f3caa6837cc542bec34a757f4394c7e0e079bd031';
if(sha('engine.js')!==original)throw Error('Original engine differs');
let t=0,grace=.25;const frames=[];
for(let n=0;n<=1660;n++){
 if(n){t+=T.step;grace=Math.max(0,grace-T.step);}
 frames.push({n,t,grace,ledges:T.ledges.map(l=>{const x=T.ledgeX(l,t);return {x,left:x-3,right:x+l.w+3,carry:x-T.ledgeX(l,t-T.step),y:l.y,threshold:l.y-.001};}),saws:T.saws.map(l=>T.sawAt(l,t)),bolts:T.emitters.map(l=>T.boltAt(l,t)),vents:T.vents.map(l=>T.ventAt(l,t))});
}
const records={};
for(const name of ['13.725','13.742','13.808']){
 const r=JSON.parse(fs.readFileSync('records/'+name+'/inputs.json')),s=T.newRun('nightmare'),states=[{...structuredClone(s),_support:0}];let support=0;
 for(const a of r.path.flat()){s.events=[];T.update(s,a);if(s.p.ground!==null)support=s.p.ground;states.push({...structuredClone(s),_support:support});}
 records[name]={inputs:r.path.flat(),states,inputSHA256:sha('records/'+name+'/inputs.json')};
}
fs.writeFileSync(path.join(__dirname,'constants.json'),JSON.stringify({engineSHA256:original,dt:T.step,ledges:T.ledges,frames,records}));
console.log('Exported original-JavaScript constants and three replay oracles');
