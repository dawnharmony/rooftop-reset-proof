'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const shell=$('arcade'), canvas=$('game'), view=TowerView.make(canvas);
  const touchMedia=matchMedia('(any-pointer: coarse), (max-width: 650px), (max-width: 950px) and (max-height: 500px)');
  const names={hard:'Hard',nightmare:'Nightmare'};
  const idleMotion=matchMedia('(prefers-reduced-motion: no-preference)');
  let lastIdlePaint=0;
  const storage={
    get(key){try{return localStorage.getItem('tibo-roof-v1-'+key);}catch{return null;}},
    set(key,value){try{localStorage.setItem('tibo-roof-v1-'+key,String(value));}catch{}}
  };
  const preferred=storage.get('difficulty')==='nightmare'?'nightmare':'hard';
  // The original Hard record keeps its existing storage key.
  const bestKey=d=>d==='nightmare'?'best-nightmare':'best';
  const bestTime=d=>Number(storage.get(bestKey(d)))||0;
  const format=(sec,decimal=false)=>Math.floor(sec/60)+':'+String(Math.floor(sec)%60).padStart(2,'0')+(decimal?'.'+Math.floor(sec*10)%10:'');
  let mode='ready',menuOrigin='ready',run=Tower.newRun(preferred);
  const resetDestination='https://chatgpt.com/';
  let redirectTimer=0, redirectAt=0;
  let latch={},activeKeys=new Set(),lastFrame=performance.now(),accum=0;
  let audio=null,score=null,effects=null,sound=storage.get('sound')!=='off',noticeUntil=0;
  const effectVoices=new Set();
  const announce=msg=>{$('announce').textContent=msg;};
  function icon(button,name){button.querySelector('use').setAttribute('href','#i-'+name);}
  function wakeAudio(){
    if(!sound)return;
    try {
      if(!audio) {
        const Audio=window.AudioContext||window.webkitAudioContext;
        if(Audio){
          audio=new Audio();score=createClimbScore(audio);
          effects=audio.createGain();effects.connect(audio.destination);
        }
      }
      if(audio && audio.state!=='running')audio.resume().catch(()=>{});
    } catch {}
  }
  function stopEffects(){
    if(!effects)return;
    const now=audio.currentTime;
    effects.gain.cancelScheduledValues(now);effects.gain.setTargetAtTime(.0001,now,.004);
    for(const voice of effectVoices){try{voice.stop(now+.015);}catch{}}
  }
  function tone(f,end,length,type='square',gain=.025,delay=0){
    if(!sound||!audio||audio.state!=='running')return;
    const osc=audio.createOscillator(),vol=audio.createGain(),t=audio.currentTime+delay;
    osc.type=type;osc.frequency.setValueAtTime(f,t);osc.frequency.exponentialRampToValueAtTime(Math.max(18,end),t+length);
    vol.gain.setValueAtTime(.0001,t);vol.gain.exponentialRampToValueAtTime(gain,t+.008);vol.gain.exponentialRampToValueAtTime(.0001,t+length);
    effects.gain.cancelScheduledValues(audio.currentTime);effects.gain.setValueAtTime(1,audio.currentTime);
    effectVoices.add(osc);osc.onended=()=>{effectVoices.delete(osc);osc.disconnect();vol.disconnect();};
    osc.connect(vol);vol.connect(effects);osc.start(t);osc.stop(t+length+.015);
  }
  function fx(e){
    if(e==='jump')tone(230,510,.105,'square',.021);
    if(e==='dash'){tone(430,85,.13,'sawtooth',.024);tone(650,120,.095,'triangle',.03);}
    if(e==='death'){tone(155,36,.26,'sawtooth',.032);tone(250,63,.19,'square',.018,.055);}
    if(e==='checkpoint'||e==='win'){const notes=e==='win'?[330,415,494,660,830]:[330,440,660];notes.forEach((n,i)=>tone(n,n*1.02,.17,'triangle',.073,i*.085));}
    if(e==='start')tone(160,340,.13,'triangle',.06);
    if(e==='drop')tone(270,82,.105,'triangle',.04);
    if(e==='bolt')tone(760,160,.14,'sawtooth',.024);
    if(e==='press-open'){tone(196,294,.16,'triangle',.06);tone(392,587,.20,'triangle',.055,.11);}
  }
  function soundUI(){
    const b=$('sound');b.querySelector('span').textContent=sound?'Sound on':'Sound off';
    b.setAttribute('aria-pressed',String(sound));icon(b,sound?'sound':'muted');
  }
  $('sound').onclick=()=>{sound=!sound;storage.set('sound',sound?'on':'off');soundUI();if(sound){wakeAudio();tone(370,470,.08,'triangle',.04);}else {score?.pause();stopEffects();}};
  function fullUI(){
    const b=$('full');b.hidden=!shell.requestFullscreen||!document.fullscreenEnabled;
    b.querySelector('span').textContent=document.fullscreenElement?'Exit fullscreen':'Fullscreen';
    b.setAttribute('aria-pressed',String(!!document.fullscreenElement));
  }
  $('full').onclick=async()=>{
    try{if(document.fullscreenElement)await document.exitFullscreen();else await shell.requestFullscreen();}
    catch{announce('Fullscreen is unavailable in this browser.');}
    fullUI();
  };
  document.addEventListener('fullscreenchange',fullUI);
  $('dialog-choices').replaceChildren(...Array.from($('start-choices').children,b=>b.cloneNode(true)));
  function clearKeys(){
    activeKeys.clear();latch={};
    touch.clear();
  }
  const freePlay=()=>mode==='playing'||mode==='ready';
  const touchDash=document.querySelector('[data-key="dash"]');
  function updateTouch(){
    $('touch-pad').hidden=!freePlay()||!touchMedia.matches;
    $('dash-state').hidden=mode!=='playing'||touchMedia.matches;
    $('quick-hint').textContent=touchMedia.matches?'Stick to move · Pull down to crouch':'← → move   ·   ↓ crouch   ·   Space jump   ·   Shift dash';
  }
  function setText(id,value){const el=$(id);if(el.textContent!==value)el.textContent=value;}
  function hud(){
    const d=run.difficulty;
    if(shell.dataset.difficulty!==d)shell.dataset.difficulty=d;
    setText('floor-id',String(run.floor+1).padStart(2,'0')+' / 06');
    setText('room',Tower.floors[run.floor]);setText('mode-badge',names[d]);
    setText('deaths',String(run.deaths));setText('timer',format(run.time));
    $('dash-state').classList.toggle('spent',!run.p.dashReady);touchDash.classList.toggle('spent',!run.p.dashReady);
  }
  function setMode(next){
    if(next!=='playing')score?.pause();
    if(next!=='playing'&&next!=='won')stopEffects();
    mode=next;clearKeys();accum=0;lastFrame=performance.now();
    const play=freePlay();$('entry').hidden=next!=='ready';$('overlay').hidden=play;
    $('hud').inert=!play;$('notice').hidden=true;$('roof-action').hidden=true;updateTouch();hud();
  }
  function start(difficulty=run.difficulty){
    clearTimeout(redirectTimer);redirectAt=0;
    run=Tower.newRun(difficulty);storage.set('difficulty',run.difficulty);score?.reset();noticeUntil=0;
    setMode('playing');view.resize();view.snap(run);view.draw(run,0);canvas.focus({preventScroll:true});
    wakeAudio();fx('start');announce(names[run.difficulty]+' climb started in the basement.');
  }
  for(const button of document.querySelectorAll('[data-difficulty]')){
    button.onclick=()=>start(button.dataset.difficulty);
  }
  function setDialog(title,body,kicker,primary,secondary=''){
    $('dialog').dataset.view=mode;
    $('dialog-title').textContent=title;$('dialog-text').textContent=body;$('dialog-kicker').textContent=kicker;
    $('primary').querySelector('span').textContent=primary;$('secondary').querySelector('span').textContent=secondary;$('secondary').hidden=!secondary;
    $('tools').hidden=mode!=='paused';$('dialog-choices').hidden=mode!=='choose';$('retry').hidden=mode!=='paused'||menuOrigin==='ready';
    $('primary').focus({preventScroll:true});
  }
  function pause(){
    if(!freePlay())return;menuOrigin=mode;pausedDialog();
  }
  function pausedDialog(){
    setMode('paused');const d=run.difficulty,best=bestTime(d);
    const stats=menuOrigin==='ready'?(d==='nightmare'?'Every death returns to the basement.':'Flags save your floor.'):format(run.time,true)+'  /  '+run.deaths+' '+(run.deaths===1?'death':'deaths');
    setDialog(menuOrigin==='ready'?'Game menu':'Paused',stats+(best?'  /  Best '+format(best,true):''),names[d]+' · '+Tower.floors[run.floor],menuOrigin==='ready'?'Back':'Resume','New climb');
    $('retry').querySelector('span').textContent=d==='nightmare'?'Retry basement':'Retry flag';
  }
  function resume(){
    setMode(menuOrigin==='ready'?'ready':'playing');wakeAudio();canvas.focus({preventScroll:true});
  }
  function help(){
    setMode('help');
    const movement=touchMedia.matches?'Stick sideways to run. Pull down to crouch, diagonally down to crawl. Hold down + Jump to drop through a ledge. In the air, pull down while falling for a fast drop.\n\nHold Jump for height. Slide your thumb from Jump to Dash.':'← → or A/D to move. Hold ↓ or S to crouch and crawl. ↓ + Jump drops through a ledge. Hold ↓ while falling for a fast drop.\n\nSpace, W or ↑ jumps. Shift or X dashes. R retries. P or Esc pauses.';
    const rule=run.difficulty==='nightmare'?'Nightmare has no checkpoints. Every death or retry sends Tibo to the basement.':'Hard saves your floor when you land on a flag.';
    setDialog('Controls',movement+' Landing recharges your dash.\n\n'+rule+'\n\nStand beside the rooftop button and '+(touchMedia.matches?'tap Press reset.':'click Press reset or press E or Jump.')+' The reset opens ChatGPT.','Rooftop Reset','Back');
  }
  function choose(){
    setMode('choose');
    setDialog('Choose a climb',menuOrigin==='ready'?'Pick a difficulty.':'Choosing a mode starts a new run.','Rooftop Reset','Back');
  }
  function openChatGPT(){
    if(mode!=='won'||!redirectAt)return;
    clearTimeout(redirectTimer);redirectAt=0;
    window.location.assign(resetDestination);
  }
  function win(){
    const d=run.difficulty,previous=bestTime(d),record=!previous||run.time<previous;
    if(record)storage.set(bestKey(d),run.time);
    setMode('won');
    const stats=format(run.time,true)+'  ·  '+run.deaths+' '+(run.deaths===1?'death':'deaths');
    setDialog('Reset pressed.',stats+'\nOpening ChatGPT in 3 seconds.',names[d]+(record?' · New personal best':' · Rooftop reached'),'Open ChatGPT now');
    announce(names[d]+' clear. Opening ChatGPT in three seconds.');
    redirectAt=Date.now()+3000;
    redirectTimer=window.setTimeout(openChatGPT,3000);
  }
  window.addEventListener('pagehide',()=>{clearTimeout(redirectTimer);redirectAt=0;});
  window.addEventListener('pageshow',event=>{
    if(event.persisted&&mode==='won'){
      run=Tower.newRun(run.difficulty);setMode('ready');redraw();
    }
  });
  $('pause').onclick=pause;$('help').onclick=help;
  $('primary').onclick=()=>{if(mode==='paused')resume();else if(mode==='choose')pausedDialog();else if(mode==='help')pausedDialog();else if(mode==='won')openChatGPT();};
  $('secondary').onclick=choose;
  $('retry').onclick=()=>{resume();latch.retry=true;};
  const mapping={ArrowLeft:'left',KeyA:'left',ArrowRight:'right',KeyD:'right',Space:'jump',ArrowUp:'jump',KeyW:'jump',ShiftLeft:'dash',ShiftRight:'dash',KeyX:'dash',KeyR:'retry',KeyE:'interact',ArrowDown:'down',KeyS:'down'};
  function pressed(action){if(['jump','dash','retry','interact'].includes(action))latch[action]=true;}
  function held(action){for(const key of activeKeys)if(mapping[key]===action)return true;return touch.held(action);}
  function horizontalInput(){
    let direction=0;
    // When the arrows overlap, the newest press wins and releasing it restores the older one.
    for(const key of activeKeys) {
      if(mapping[key]==='left')direction=-1;
      else if(mapping[key]==='right')direction=1;
    }
    return direction || touch.axis;
  }
  document.addEventListener('keydown',e=>{
    if(e.metaKey||e.ctrlKey||e.altKey)return;
    if(mode==='paused' && ['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.code)) {
      const choices=[...$('dialog').querySelectorAll('.menu-grid button')].filter(b=>b.getClientRects().length);
      const current=choices.indexOf(document.activeElement);
      const offset={ArrowLeft:-1,ArrowRight:1,ArrowUp:-2,ArrowDown:2}[e.code];
      const target=Math.max(0,Math.min(choices.length-1,current+offset));
      choices[target]?.focus({preventScroll:true});e.preventDefault();return;
    }
    if(!freePlay()&&e.code==='Tab'){
      const buttons=[...$('dialog').querySelectorAll('button')].filter(b=>b.getClientRects().length>0);
      const first=buttons[0],last=buttons[buttons.length-1];
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
      if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
      return;
    }
    if(e.code==='Escape'||e.code==='KeyP'){
      if(e.repeat)return;
      if(freePlay())pause();else if(mode==='paused')resume();else if(mode==='help')pausedDialog();else if(mode==='choose')pausedDialog();
      e.preventDefault();return;
    }
    if(!freePlay())return;
    const focusButton=document.activeElement instanceof HTMLButtonElement;
    if(mode==='ready'&&e.code==='Enter'&&!focusButton&&!e.repeat){e.preventDefault();start();return;}
    const action=mapping[e.code];if(!action||e.code==='Space'&&focusButton)return;
    if(mode==='ready'){
      if(e.repeat||!['left','right','down','jump','dash'].includes(action))return;
      start();
    }
    e.preventDefault();if(!e.repeat&&!activeKeys.has(e.code)){activeKeys.add(e.code);pressed(action);}
  });
  document.addEventListener('keyup',e=>{if(!activeKeys.delete(e.code))return;if(mapping[e.code]==='jump'&&!held('jump'))latch.cut=true;});
  const touch=makeTouchControls($('touch-pad'),()=>{
    if(!freePlay())return false;
    if(mode==='ready')start();
    return true;
  },pressed,()=>{if(!held('jump'))latch.cut=true;});
  $('roof-action').onclick=()=>{
    if(mode==='playing'&&Tower.approachingButton(run))latch.interact=true;
  };
  function blur(){if(mode==='playing')pause();else clearKeys();}
  window.addEventListener('blur',blur);document.addEventListener('visibilitychange',()=>{if(document.hidden)blur();});
  function redraw(){view.resize();if(mode==='ready')view.snap(run);view.draw(run,0);}
  for(const id of ['mural-art','hero-poses','hero-moves','terrier-poses'])$(id).addEventListener('load',redraw,{once:true});
  new ResizeObserver(redraw).observe(shell);
  touchMedia.addEventListener?.('change',()=>{clearKeys();updateTouch();redraw();});
  function handleEvent(event){
    view.event(run,event);fx(event);
    if(event==='floor'||event==='checkpoint'){
      const name=Tower.floors[run.floor],msg=event==='checkpoint'?name+' checkpoint':name;
      const hint=run.floor===3&&!run.pressOpen?(touchMedia.matches?'Push ↘ to crawl under the press':'Hold ↓ + → under the press'):msg;
      $('notice').textContent=hint;noticeUntil=run.time+(run.floor===3?3:1.3);announce(hint+'.');
    }else if(event==='spawn'&&run.deaths){
      noticeUntil=0;announce('Back in '+Tower.floors[run.floor]+'.');
    }else if(event==='win')win();
  }
  function frame(now){
    const dt=Math.max(0,Math.min(.08,(now-lastFrame)/1000));lastFrame=now;
    if(mode==='playing'){
      accum+=dt;
      while(accum>=Tower.step&&mode==='playing'){
        const input={...latch,down:held('down')||touch.down,axis:horizontalInput()};latch={};Tower.update(run,input);accum-=Tower.step;
        for(const event of run.events)handleEvent(event);run.events.length=0;
      }
      view.draw(run,dt);$('roof-action').hidden=mode!=='playing'||run.dead||!Tower.approachingButton(run);hud();$('notice').hidden=mode!=='playing'||run.dead||run.time>=noticeUntil;
      if(mode==='playing'&&sound)score?.tick(run.floor,run.difficulty==='nightmare');
    }
    if(mode==='ready'&&idleMotion.matches&&!document.hidden&&now-lastIdlePaint>=80){
      view.draw(run,Math.min(.12,(now-lastIdlePaint)/1000));lastIdlePaint=now;
    }
    if(mode==='won'&&redirectAt&&Date.now()>=redirectAt)openChatGPT();
    requestAnimationFrame(frame);
  }
  soundUI();fullUI();setMode('ready');redraw();requestAnimationFrame(frame);
})();
