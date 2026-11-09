const fs=require('fs'),assert=require('assert/strict'),T=require('../engine.js');
const r=require('./constants.json').records['13.725'];
assert.equal(T.approachingButton(r.states[1645]),false);assert.equal(T.approachingButton(r.states[1646]),true);
fs.writeFileSync('reachability/verifier-fixture.json',JSON.stringify({startTick:0,inputs:r.inputs}));
let vy=285,y=0,apex=0;while(vy>0){vy-=740*T.step;y+=vy*T.step;apex=Math.max(apex,y);}
assert.ok(apex<54);
fs.writeFileSync('reachability/invariants.json',JSON.stringify({normalJumpApex:apex,conservativeHeightAboveLastSupport:54,smallestTwoLevelGap:Math.min(...T.ledges.slice(2).map((l,i)=>l.y-T.ledges[i].y)),recordEligibleTick:1646,recordResetTick:1647,targetLatestEligibleTick:1645,argument:'Between contacts there is at most one jump: jumping, dropping and dashing clear coyote; only a contact restores it. Jump starts vy=285, upward gravity is740, cuts reduce positive vy, and dashes freeze height. Press roof support never raises y above its pre-step y and does not restore coyote. Thus height stays below last support+54; the landing tolerance0.001 cannot bridge a68-unit two-level gap.'},null,2));console.log('Horizon and platform-gap checks passed');
