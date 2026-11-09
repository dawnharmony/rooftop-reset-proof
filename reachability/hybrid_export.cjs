'use strict';
const fs=require('fs'),crypto=require('crypto'),T=require('../engine.js');
const records={};
for(const name of ['13.725','13.742','13.808']){
 const a=JSON.parse(fs.readFileSync(`records/${name}/inputs.json`)),s=T.newRun('nightmare');
 const contacts=[{ledge:0,tick:0,x:s.p.x}],trace=[{x:s.p.x,g:s.p.ground,y:s.p.y}];
 let high=0;
 for(const raw of a.path.flat()){
  T.update(s,raw);s.events=[];trace.push({x:s.p.x,g:s.p.ground,y:s.p.y});
  if(s.p.ground!==null&&s.p.ground>high){high=s.p.ground;contacts.push({ledge:high,tick:trace.length-1,x:s.p.x});}
 }
 if(!s.won||s.deaths)throw Error('archive failed');
 records[name]={ticks:trace.length-1,contacts,trace};
}
fs.writeFileSync('reachability/hybrid-world.json',JSON.stringify({engineSHA256:crypto.createHash('sha256').update(fs.readFileSync('engine.js')).digest('hex'),ledges:T.ledges,records}));
