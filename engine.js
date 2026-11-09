'use strict';
const Tower = (() => {
  const floors = ['Basement', 'Boiler Room', 'Service Shaft', 'Machine Hall', 'Antenna Deck', 'Rooftop'];
  const width = 480;
  const step = 1 / 120;
  const spawnIndices = [0, 5, 10, 15, 20, 25];
  // Each row gives left edge, height above the basement, width, and optional ledge behavior.
  const plan = [
    [24,0,118], [160,32,62], [248,68,54], [333,105,47,'crumble'], [232,145,50],
    [116,182,74], [36,222,43], [130,261,38,'move',11], [232,299,39], [332,337,37,'crumble'],
    [240,378,71], [143,420,38,'move',12], [38,459,42], [126,501,30,'crumble'], [221,539,33,'move',8],
    [294,578,94], [407,618,39], [300,660,33,'crumble'], [200,700,32,'move',9], [91,740,37],
    [165,780,75], [316,820,34], [403,862,28], [302,901,27,'crumble'], [202,941,30,'move',8],
    [90,982,76], [214,1023,31,'crumble'], [326,1062,30,'move',6], [390,1105,70,'finish']
  ];
  const ledges = plan.map(([x,y,w,type='steel',travel=0],i) => ({x,y,w,type,travel,i}));
  const spikes = [{i:4,edge:'right',w:9},{i:12,edge:'left',w:9},{i:16,edge:'right',w:9},{i:19,edge:'left',w:8},{i:22,edge:'right',w:7}];
  const vents = [{i:6,offset:3,cycle:2.9,phase:.45},{i:8,offset:28,cycle:2.55,phase:1.3},{i:21,offset:22,cycle:2.75,phase:.7}];
  const saws = [
    {x:284,y:322,amp:15,rate:2.2,axis:'y',phase:0},
    {x:105,y:480,amp:17,rate:2,axis:'y',phase:.7},
    {x:268,y:720,amp:15,rate:2.4,axis:'y',phase:1.8},
    {x:360,y:920,amp:19,rate:2.4,axis:'y',phase:2.1},
    {x:284,y:1044,amp:17,rate:2.2,axis:'y',phase:1}
  ];
  const finish = {x:435,y:1105};
  const press = {ledge:15, left:338, right:365, floor:ledges[15].y, clearance:20, top:88, skirt:68};
  // Bolts travel at head height. Their coils charge before each shot and go dark between bursts.
  const emitters = [
    {x:202,y:ledges[7].y+22,dir:-1,reach:126,speed:105,period:4.1,charge:.76,offset:.38},
    {x:15,y:ledges[12].y+22,dir:1,reach:114,speed:119,period:3.65,charge:.70,offset:1.38},
    {x:464,y:ledges[22].y+22,dir:-1,reach:132,speed:134,period:3.25,charge:.64,offset:.90}
  ];
  const clamp = (v,min,max) => Math.max(min, Math.min(max,v));
  function ledgeX(ledge,t) { return ledge.x + ledge.travel * Math.sin(t*1.7 + ledge.i*1.23); }
  function sawAt(s,t) { const n = Math.sin(t*s.rate+s.phase)*s.amp; return {x:s.x+(s.axis==='x'?n:0), y:s.y+(s.axis==='y'?n:0)}; }
  function ventAt(vent,t) {
    const ledge=ledges[vent.i], phase=(t+vent.phase)%vent.cycle;
    return {x:ledgeX(ledge,t)+vent.offset, y:ledge.y, active:phase>.70&&phase<1.43, warning:phase>.12&&phase<=.70, phase};
  }
  function boltAt(emitter,time) {
    const phase=(time+emitter.offset)%emitter.period;
    const distance=(phase-emitter.charge)*emitter.speed;
    return {
      x:emitter.x+emitter.dir*Math.max(0,distance), y:emitter.y,
      phase, warning:phase<emitter.charge, active:distance>=0&&distance<=emitter.reach
    };
  }
  function underPress(s) {
    const p=s.p;
    return !s.pressOpen && p.ground===press.ledge && p.x+3>press.left && p.x-3<press.right;
  }
  function moveThroughPress(s,previousX,previousY,dt) {
    const p=s.p;
    if(s.pressOpen) {
      s.pressLift=Math.min(1,s.pressLift+dt*2.6);
      return;
    }
    const near=p.x+3>press.left && p.x-3<press.right;
    const head=p.y+(p.crouched?15:26);
    if(near && head>press.floor-press.skirt && p.y<press.floor+press.top) {
      const inOpening=p.crouched && p.ground===press.ledge && p.y>=press.floor && head<=press.floor+press.clearance;
      if(inOpening)s.crossingPress=true;
      else if(previousX<=press.left-3 || previousX>=press.right+3) {
        p.x=previousX<=press.left-3?press.left-3:press.right+3;
        p.vx=0;p.dash=0;
      } else if(previousY>=press.floor+press.top && p.vy<0) {
        p.y=press.floor+press.top;p.vy=0;
      } else {
        p.y=press.floor-press.skirt-(p.crouched?15:26);p.vy=Math.min(0,p.vy);
      }
    }
    if(s.crossingPress && p.x-3>=press.right) {
      s.pressOpen=true;s.events.push('press-open');
    }
    if(p.x+3<=press.left)s.crossingPress=false;
  }
  function updateFacing(p,axis,dt) {
    const direction=Math.abs(axis)>.12?Math.sign(axis):0;
    p.turnTime=Math.max(0,p.turnTime-dt);
    p.braking=Boolean(p.ground!==null && direction===-p.facing && p.vx*p.facing>22);
    if(!direction || direction===p.facing) {p.turnIntent=0;p.turnAge=0;return;}
    if(p.turnIntent!==direction) {p.turnIntent=direction;p.turnAge=0;}
    p.turnAge+=dt;
    // The feet reverse immediately. Change the illustrated profile once momentum changes sides.
    if(p.turnAge>=.048 && p.vx*direction>8) {
      p.facing=direction;p.turnTime=p.ground!==null?.065:0;p.turnIntent=0;p.turnAge=0;
    }
  }
  function newRun(difficulty = 'hard') {
    const state={difficulty:difficulty==='nightmare'?'nightmare':'hard',p:{},time:0,worldTime:0,deaths:0,floor:0,checkpoint:0,high:0,lifeHigh:0,dead:0,won:false,pressOpen:false,pressLift:0,crossingPress:false,crumbles:[],events:[],floorFlash:1.75};
    spawn(state);
    return state;
  }
  function spawn(s) {
    s.floor=s.checkpoint;
    if(s.difficulty==='nightmare'){s.worldTime=0;s.pressOpen=false;s.pressLift=0;}
    s.crossingPress=false;
    const idx=spawnIndices[s.checkpoint], l=ledges[idx];
    const startX=idx===0?32:idx===press.ledge?20:l.w/2;
    s.p={x:l.x+startX,y:l.y,vx:0,vy:0,ground:idx,facing:idx===5||idx===10? -1:1,coyote:.09,jumpBuffer:0,dash:0,dashReady:true,grace:.25,landTime:0,
      crouched:false,fastFall:false,impactTime:0,turnIntent:0,turnAge:0,turnTime:0,braking:false};
    s.lifeHigh=l.y;s.dead=0;s.crumbles=Array(ledges.length).fill(-1);
    s.events.push('spawn');
  }
  function die(s) {
    if(s.dead || s.won) return;
    s.dead=.47;s.deaths++;s.events.push('death');
  }
  function win(s) {
    if(s.won) return;
    s.won=true;s.events.push('win');
  }
  function approachingButton(s) {return s.p.ground===28 && Math.abs(s.p.x-finish.x)<=15;}
  function update(s,input,dt=step) {
    if(s.won) return;
    s.time+=dt;s.worldTime+=dt;s.floorFlash=Math.max(0,s.floorFlash-dt);
    if(s.dead){s.dead-=dt;if(s.dead<=0)spawn(s);return;}
    if(input.retry){die(s);return;}
    for(let i=0;i<s.crumbles.length;i++) if(s.crumbles[i]>=0)s.crumbles[i]+=dt;
    const p=s.p;
    p.grace=Math.max(0,p.grace-dt);p.landTime=Math.max(0,p.landTime-dt);
    p.impactTime=Math.max(0,p.impactTime-dt);
    p.coyote=Math.max(0,p.coyote-dt);p.jumpBuffer=Math.max(0,p.jumpBuffer-dt);
    if(input.jump)p.jumpBuffer=.13;
    if((input.interact||(input.jump&&!input.down)) && approachingButton(s)){win(s);return;}
    const keyboardAxis=(input.right?1:0)-(input.left?1:0);
    const axis=keyboardAxis || clamp(input.axis || 0,-1,1);
    const previousX=p.x;
    if(p.ground!==null){
      const l=ledges[p.ground];const lx=ledgeX(l,s.worldTime);
      p.x+=lx-ledgeX(l,s.worldTime-dt);
      if(p.x<lx-3||p.x>lx+l.w+3||s.crumbles[p.ground]>.48){
        p.ground=null;
      }else p.coyote=.095;
    }
    const inPassage=underPress(s);
    p.crouched=p.ground!==null && (Boolean(input.down)||inPassage);
    if(p.jumpBuffer>0 && p.coyote>0){
      if(p.crouched) {
        if(input.down && p.ground!==0 && !inPassage) {
          p.y-=2.5;p.vy=-85;p.ground=null;p.coyote=0;p.crouched=false;s.events.push('drop');
        }
      } else {
        p.vy=285;p.ground=null;p.coyote=0;p.landTime=0;s.events.push('jump');
      }
      p.jumpBuffer=0;
    }
    if(input.cut&&p.vy>110)p.vy*=.54;
    if(input.dash && p.dashReady && !inPassage){
      if(Math.abs(axis)>.12)p.facing=Math.sign(axis);
      p.dash=.145;p.dashReady=false;p.ground=null;p.coyote=0;p.crouched=false;p.turnTime=0;p.braking=false;s.events.push('dash');
    }
    p.fastFall=Boolean(input.down && p.ground===null && p.dash<=0 && p.vy<=0);
    const lastY=p.y;
    if(p.dash>0){
      p.dash=Math.max(0,p.dash-dt);p.vx=p.facing*312;
      if(p.dash===0)p.vx=p.facing*125;
    }else{
      const target=axis*(p.crouched?60:127);
      const accel=axis?(p.ground!==null?1040:670):(p.ground!==null?1250:480);
      p.vx+=clamp(target-p.vx,-accel*dt,accel*dt);
      if(p.ground===null)p.vy=Math.max(p.fastFall?-490:-420,p.vy-(p.fastFall?1410:740)*dt);
      p.y+=p.vy*dt;
      updateFacing(p,axis,dt);
    }
    p.x=clamp(p.x+p.vx*dt,7,width-7);
    moveThroughPress(s,previousX,lastY,dt);
    if(p.ground===null&&p.dash===0&&p.vy<=0){
      for(let i=ledges.length-1;i>=0;i--){
        const l=ledges[i];if(s.crumbles[i]>.48||lastY<l.y-.001||p.y>l.y)continue;
        const x=ledgeX(l,s.worldTime);if(p.x<x-3||p.x>x+l.w+3)continue;
        p.impactTime=p.vy < -235 ? .085 : 0;
        p.ground=i;p.y=l.y;p.vy=0;p.dashReady=true;p.coyote=.095;p.landTime=.12;p.fastFall=false;p.crouched=Boolean(input.down);s.events.push('land');
        if(l.type==='crumble'&&s.crumbles[i]<0)s.crumbles[i]=0;
        const nextFloor=spawnIndices.indexOf(i);
        if(nextFloor>s.floor){
          s.floor=nextFloor;s.floorFlash=1.8;
          if(s.difficulty==='hard'){s.checkpoint=nextFloor;s.events.push('checkpoint');}
          else s.events.push('floor');
        }
        break;
      }
    }
    if(p.ground!==null && p.dash===0)p.y=ledges[p.ground].y;
    s.lifeHigh=Math.max(s.lifeHigh,p.y);s.high=Math.max(s.high,p.y);
    if(s.won)return;
    if(p.y<Math.max(-24,s.lifeHigh-155)){die(s);return;}
    if(p.grace>0)return;
    for(const emitter of emitters) {
      if(Math.abs(emitter.y-p.y)>42)continue;
      const bolt=boltAt(emitter,s.worldTime);
      if(bolt.phase>=emitter.charge && bolt.phase<emitter.charge+dt)s.events.push('bolt');
      if(bolt.active && Math.abs(p.x-bolt.x)<7 && p.y+1<bolt.y+2 && p.y+(p.crouched?15:26)>bolt.y-2) {
        die(s);return;
      }
    }
    for(const spike of spikes){
      const l=ledges[spike.i], x=ledgeX(l,s.worldTime)+(spike.edge==='right'?l.w-spike.w:0);
      if(p.x+3>x+1&&p.x-3<x+spike.w-1&&p.y<l.y+6&&p.y+14>l.y+1){die(s);return;}
    }
    for(const swn of saws){
      const b=sawAt(swn,s.worldTime);const dx=b.x-clamp(b.x,p.x-3,p.x+3),dy=b.y-clamp(b.y,p.y+1,p.y+(p.crouched?11:15));
      if(dx*dx+dy*dy<30){die(s);return;}
    }
    for(const vent of vents){
      const v=ventAt(vent,s.worldTime);
      if(v.active&&Math.abs(p.x-(v.x+3))<6&&p.y<v.y+24&&p.y+14>v.y+3){die(s);return;}
    }
  }
  return {floors,width,step,spawnIndices,ledges,spikes,vents,saws,emitters,press,finish,clamp,ledgeX,sawAt,ventAt,boltAt,newRun,die,approachingButton,update};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=Tower;
