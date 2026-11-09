const fs=require('fs'),assert=require('assert/strict'),T=require('../engine.js');
const record=JSON.parse(fs.readFileSync('records/13.725/inputs.json')),inputs=record.path.flat();
const project=s=>({p:s.p,worldTime:s.worldTime,checkpoint:s.checkpoint,floor:s.floor,lifeHigh:s.lifeHigh,pressOpen:s.pressOpen,pressLift:s.pressLift,crossingPress:s.crossingPress,crumbles:s.crumbles});
const tests=[];
for(const stop of [100,500,1000,1500]){
 const s=T.newRun('nightmare');for(const a of inputs.slice(0,stop)){T.update(s,a);s.events=[];}
 T.die(s);let waited=0;while(s.dead){T.update(s,{});waited++;}
 const fresh=T.newRun('nightmare');assert.deepEqual(project(s),project(fresh));
 for(const a of inputs.slice(0,300)){T.update(s,a);T.update(fresh,a);assert.deepEqual(project(s),project(fresh));}
 tests.push({prefixTicks:stop,deadWaitTicks:waited,spawnPhysicsIdentical:true,suffixPhysicsIdentical:true});
}
fs.writeFileSync('reachability/respawn-check.json',JSON.stringify({tests,argument:'Nightmare checkpoint remains zero. Spawn resets every field used by future physics except elapsed time and deaths, which do not affect transitions. Removing a prefix through its last respawn produces the same future motion with a strictly smaller elapsed time. Cosmetic high/floorFlash/events are omitted from the projection.'},null,2));console.log('Respawn dominance checks passed');
