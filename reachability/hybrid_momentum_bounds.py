"""Conservative time/contact/velocity-bin DP with acceleration end losses.

All continuous endpoint velocities are enclosed in closed bins. A cell stores
an x INTERVAL, not a sampled point. Every source time and velocity bin is used;
interval hulls add possibilities. This is a necessary-condition solver, not an
original-engine route generator or an unreviewed optimality certificate.
"""
import functools,hashlib,json,math,time,argparse,sys,os,msvcrt
from pathlib import Path
import hybrid_interval_bounds as base
from hybrid_bounds import ceildiv
from hybrid_gate_bounds import U,NORMAL
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'pilot'))
from resources import Job,available,memory,identity
from manager import atomic
AIR=ceildiv(670*U,120)+2;GROUND=ceildiv(1250*U,120)+2
V=[-127000001,-96000000,-64000000,-32000000,0,32000000,64000000,96000000,127000001]
BINS=list(zip(V,V[1:]));V125=125000001

@functools.lru_cache(maxsize=100000)
def normal_only(n,u0,u1):
    return ceildiv(sum(max(0,min(NORMAL,u0+GROUND*(j+1),u1+GROUND*(n-1-j))) for j in range(n)),120)+1

_wall={}
def wall_range(steps,vlo,vhi,ground):
    if steps<0:return None
    if ground not in _wall:
        import sys
        sys.path.insert(0,str(HERE/'pilot'))
        from fast_geometry import install
        install()
        _wall[ground]=[[(335*U,0)]]
    from kernel import step,clip
    polys=_wall[ground]
    while len(polys)<=steps:polys.append(step(polys[-1],-1,-1,1 if ground else 0,0,[],clamp_world=True))
    poly=clip(clip(polys[steps],1,vlo-1,True),1,vhi+1,False)
    return (min(x for x,v in poly),max(x for x,v in poly)) if poly else None

def crawl_ticks(x,v):
    n=0
    while x<368*U:
        amount=1040*U//120-1
        v=min(60000001,v+amount+2) if v<60000001 else max(60000001,v-amount)
        x+=ceildiv(v,120)+1;n+=1
        assert n<200
    return n

@functools.lru_cache(maxsize=200000)
def travel(n,m,carry,departure,granular,u0,u1,dash_limit=None):
    """Upper directional net displacement in micro-units.

    Zero dash: per-update necessary speed bounds from both endpoints, with
    extra ground acceleration optimistically allocated at BOTH ends.
    >=1dash: ignore initial velocity, subtract only a universally necessary
    terminal loss. A last opposite dash loses at least one full dash's own
    directional distance, even when a world wall cancels its displacement.
    """
    if n<m:return -1
    if not granular:
        fast=312000001+carry
        return ceildiv(fast*n-(fast-NORMAL)*m,120)+departure
    best=-1
    maximum_dashes=(n-m)//18
    if dash_limit is not None:maximum_dashes=min(maximum_dashes,dash_limit)
    for k in range(maximum_dashes+1):
        normal=n-18*k;extra=normal-m
        def accel(j):return min(j,extra)*GROUND+max(0,j-extra)*AIR
        # The final upward flight contributes at least m AIR updates. Any
        # preceding optional ground updates are farther from the endpoint.
        # If the last dash lies inside that flight, a forward dash resets to
        #125; beyond that reset the terminal-loss terms are already zero.
        def terminal_accel(j):return min(j,m)*AIR+max(0,j-m)*GROUND
        if k==0:
            amount=sum(max(0,min(NORMAL,u0+accel(j+1),u1+terminal_accel(normal-1-j))) for j in range(normal))
        else:
            # If the backwards velocity upper bound is negative, every real
            # velocity in that terminal window is negative too. A clamp at
            # the opposite world wall could move at most 4worldunits by carry
            # before the end, whereas every contact endpoint is >=10 away.
            # Thus no such clamp can occur on a feasible terminal approach.
            loss=sum(max(0,V125-(u1+terminal_accel(j))) for j in range(normal))
            loss=min(loss,5429*U) # Opposite last dash may be wall-clamped.
            amount=NORMAL*normal+(5429*U+120)*k-loss
        amount+=carry*(extra+k)
        best=max(best,ceildiv(amount,120)+departure)
    return best

def run(deadline=1646,width=32,folder=None,resume=False,guard=None):
    folder=Path(folder or HERE/'hybrid'/f'momentum-{deadline}-v{width}');folder.mkdir(exist_ok=True)
    if resume:(folder/'pause.request').unlink(missing_ok=True)
    if (HERE/'pilot/global-pause.request').exists() or (folder/'pause.request').exists():return {'state':'paused'}
    began=time.perf_counter();gate_data=json.loads((HERE/'hybrid/gate-bounds.json').read_text());g=gate_data['closed'];data=json.loads((HERE/'hybrid/monotone-bounds.json').read_text());c=json.loads((HERE/'constants.json').read_text())
    files=[Path(__file__),HERE.parent/'engine.js',HERE.parent/'arcade.js']+[HERE/n for n in ['constants.json','hybrid/monotone-bounds.json','hybrid/gate-bounds.json','hybrid/phase-bounds.json','hybrid/backtrack-check.json','hybrid_bounds.py','hybrid_gate_bounds.py','hybrid_interval_bounds.py','hybrid_monotone_bounds.py','hybrid_phase_bounds.py','hybrid_backtrack_check.py','pilot/kernel.py','pilot/fast_geometry.py']]
    digest=hashlib.sha256(b''.join(f.read_bytes() for f in files)+json.dumps([deadline,width]).encode()).hexdigest()
    def status(state,**extra):atomic(folder/'status.json',{'state':state,'pid':os.getpid(),'process_created':identity(os.getpid()),'deadline':deadline,'velocityWidth':width,'sourceSHA256':digest,'seconds':time.perf_counter()-began,'privateMiB':memory(os.getpid())['private']/2**20,'jobPeakCommitMiB':guard.peak()/2**20 if guard else None,**extra})
    status('building')
    from hybrid_snapshot import snapshot_generic
    snapshot_generic(folder,files,digest)
    assert c['engineSHA256']==gate_data['engineSHA256']==data['metadata']['engineSHA256']==hashlib.sha256((HERE.parent/'engine.js').read_bytes()).hexdigest()
    # The no-retreat lemma is needed for global1646. Larger deadlines below
    # are only consistency tests of known monotone records.
    proof=json.loads((HERE/'hybrid/backtrack-check.json').read_text());assert proof['allBackwardLandingsExcluded']
    weak=hashlib.sha256((HERE/'hybrid/gate-bounds.json').read_bytes()+(HERE/'hybrid/phase-bounds.json').read_bytes()).hexdigest()
    assert proof['boundsSHA256']==data['metadata']['retreatCertificateBoundsSHA256']==weak
    domains=data['domains'];params=data['parameters'];f0=data['forward']
    back=[None]*len(domains);back[-1]=[None]+[domains[-1][0]]*base.T
    for i in range(len(domains)-2,-1,-1):
        reverse=[domains[i][deadline-r] if 0<=deadline-r<=base.T else None for r in range(base.T+1)]
        back[i]=base.propagate(back[i+1],reverse,g['minimum'][i+1],g['granular'][i+1],i+1==g['gate'],**params[i+1])
    values=[-127000001]+[v*U for v in range(-128+width,128,width) if -127<v<127]+[127000001]
    vbins=list(zip(values,values[1:]));bins=[vbins for _ in domains];bins[0]=[(0,0)]
    entry=[v*U for v in range(0,119,width)]+[118333335]
    bins[16]=list(zip(entry,entry[1:]));bins[17]=[(0,60000001)];bins[31]=[(-127000001,127000001)]
    windows=[]
    for i in range(len(domains)):
        windows.append([t for t in range(deadline) if f0[i][t] is not None and back[i][deadline-t] is not None])
    windows[0]=[0]
    # Check the cancellation-detour dominance still holds with terminal loss.
    cancellation=[]
    for target in [13,14]:
        aa=g['supports'][target-1];bb=g['supports'][target]
        d=max(abs(min(x for x,y in aa)-max(y for x,y in bb)),abs(max(y for x,y in aa)-min(x for x,y in bb)))
        p=params[target];m=g['minimum'][target]
        needed=next(n for n in range(m,200) if travel(n,m,p['carry'],p['departure'],True,-127000001,-127000001)>=d)
        original=next(x['bestCanceledTicks'] for x in gate_data['cancellationDominance'] if x['target']==target)
        assert needed<=original,(target,needed,original)
        cancellation.append({'target':target,'worstMomentumDirectTicks':needed,'bestCanceledTicks':original})
    frontier={0:[(56*U,56*U)]};layers=[frontier];counts=[];checked=0;start=1
    checkpoint=folder/'checkpoint.json'
    if checkpoint.exists():
        saved=json.loads(checkpoint.read_text());assert saved['sourceSHA256']==digest,'Checkpoint source mismatch'
        layers=[{int(t):row for t,row in layer.items()} for layer in saved['layers']];frontier=layers[-1];counts=saved['counts'];checked=saved['checked'];start=len(layers)
    for i in range(start,len(domains)):
        nxt={};m=g['minimum'][i];p=params[i];gate=i==g['gate'];granular=g['granular'][i]
        for ti,t in enumerate(windows[i]):
            if ti%4==0:
                reason='pause requested' if (HERE/'pilot/global-pause.request').exists() or (folder/'pause.request').exists() else 'RAM reserve' if available()<8192*2**20 else 'soft memory guard' if memory(os.getpid())['private']>768*2**20 else None
                if not reason and sum(f.stat().st_size for f in folder.iterdir() if f.is_file())>256*2**20:reason='disk guard'
                if reason:
                    atomic(checkpoint,{'sourceSHA256':digest,'layers':layers,'counts':counts,'checked':checked});status('paused',reason=reason,node=i);return {'state':'paused'}
                status('running',node=i,timeIndex=ti,times=len(windows[i]))
            allowed=domains[i][t]
            row=[]
            for vlo,vhi in bins[i]:
                lower=[];upper=[]
                for s,parts in frontier.items():
                    n=t-s
                    if n<(61 if gate else m):continue
                    for j,part in enumerate(parts):
                        if part is None:continue
                        if gate:
                            if n>=crawl_ticks(part[1],bins[i-1][j][1]):
                                lower.append(allowed[0]);upper.append(allowed[1])
                            continue
                        a,b=bins[i-1][j]
                        if i==15:
                            # No shortened dash: ordinary whole-cycle edge.
                            dr=travel(n,m,p['carry'],p['departure'],True,b,vhi)
                            dl=travel(n,m,p['carry'],p['departure'],True,-a,-vlo)
                            lower.append(part[0]-dl);upper.append(part[1]+dr)
                            # A shortened dash must hit the left press wall,
                            # resetting vx and readiness. Until first15 there
                            # is no recharge unless it returns all the way to14.
                            distance=max(0,335*U-part[1]-p['departure'])
                            # Total non-dash debit m still applies. By time
                            # tau, at most n-m updates can have dash speed;
                            # all post-wall updates before first15 are normal.
                            tau=max(0,ceildiv(distance*120,p['fast']),ceildiv(distance*120-(312000001-NORMAL)*(n-m),NORMAL+p['carry']))
                            return_time=ceildiv((335*U-max(y for x,y in g['supports'][14]))*120,NORMAL)
                            no_dash_wall=ceildiv((335*U-max(y for x,y in g['supports'][14])-p['departure'])*120,NORMAL)
                            if n>=min(tau+return_time,no_dash_wall+18):
                                dr=travel(n,m,p['carry'],p['departure'],False,b,vhi);dl=travel(n,m,p['carry'],p['departure'],False,-a,-vlo)
                                lower.append(part[0]-dl);upper.append(part[1]+dr)
                            else:
                                wall=wall_range(n-tau,vlo,vhi,False)
                                if wall:
                                    coarse=travel(n,m,p['carry'],p['departure'],False,b,vhi)
                                    left=max(wall[0],part[0]-coarse);right=min(335*U+1,wall[1],part[1]+coarse)
                                    if left<=right:lower.append(left);upper.append(right)
                            continue
                        if i==16:
                            # Closed15 run-up without a wall hit. A completed
                            # dash that avoids the wall needs a same-height
                            # jump return (>=23normal+18dash updates). Shorter
                            # dash cases are all in the wall-reset family.
                            dr=normal_only(n,b,vhi);dl=normal_only(n,-a,-vlo)
                            lower.append(part[0]-dl);upper.append(part[1]+dr)
                            if n>=41:
                                dr=travel(n,0,0,1,True,b,vhi);dl=travel(n,0,0,1,True,-a,-vlo)
                                lower.append(part[0]-dl);upper.append(part[1]+dr)
                            tau=max(0,ceildiv((335*U-part[1]-1)*120,312000001))
                            wall=wall_range(n-tau,vlo,vhi,True)
                            if wall:lower.append(wall[0]);upper.append(wall[1])
                            continue
                        dr=travel(n,m,p['carry'],p['departure'],granular,b,vhi)
                        dl=travel(n,m,p['carry'],p['departure'],granular,-a,-vlo)
                        lower.append(part[0]-dl);upper.append(part[1]+dr);checked+=1
                if not lower:row.append(None);continue
                lo=max(allowed[0],min(lower));hi=min(allowed[1],max(upper))
                if i==16:hi=min(hi,335*U+ceildiv(vhi,120)+1)
                # Necessary backward position interval for remaining time.
                goalpart=back[i][deadline-t]
                if goalpart is not None:lo=max(lo,goalpart[0]);hi=min(hi,goalpart[1])
                row.append((lo,hi) if lo<=hi else None)
            if any(part is not None for part in row):nxt[t]=row
        frontier=nxt;layers.append(frontier)
        counts.append({'node':i,'times':len(frontier),'velocityCells':sum(p is not None for row in frontier.values() for p in row),'first':min(frontier,default=None),'last':max(frontier,default=None)})
        atomic(checkpoint,{'sourceSHA256':digest,'layers':layers,'counts':counts,'checked':checked})
        if not frontier:break
    possible=bool(frontier) and len(layers)==len(domains)
    report={'deadline':deadline,'velocityWidth':width,'sourceSHA256':digest,'possible':possible,'excludedInNecessaryModel':not possible,'scope':'Candidate momentum/phase bound, not yet independently audited or a global optimality certificate','engineSHA256':data['metadata']['engineSHA256'],'cancellationDominance':cancellation,'layers':counts,'transitionsChecked':checked,'cache':travel.cache_info()._asdict(),'seconds':time.perf_counter()-began}
    # Consistency checks admit every actual contact velocity and position of
    # the matching monotone archive. A failed diagnostic stops the experiment.
    name=next((name for name,r in c['records'].items() if len(r['inputs'])==deadline),None)
    if name:
        archive=c['records'][name];contacts=json.loads((HERE/'hybrid-world.json').read_text())['records'][name]['contacts']
        for contact in contacts:
            support=contact['ledge'];node=support if support<=15 else support+2;t=contact['tick'];state=archive['states'][t]['p'];row=layers[node].get(t)
            assert row is not None,(name,node,t,'time missing')
            assert any(part is not None and lo-1<=state['vx']*U<=hi+1 and part[0]-1<=state['x']*U<=part[1]+1 for (lo,hi),part in zip(bins[node],row)),(name,node,t,state,row)
        report['knownMonotoneRecordAdmitted']=name
    out=folder/'result.json';out.write_text(json.dumps(report,indent=2))
    (folder/'frontiers.json').write_text(json.dumps({'bins':bins,'layers':layers},separators=(',',':')))
    status('possible' if possible else 'excluded-in-necessary-model',result=str(out))
    print(json.dumps(report,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--deadline',type=int,default=1646);p.add_argument('--width',type=int,default=32);p.add_argument('--folder',type=Path);p.add_argument('--resume',action='store_true');p.add_argument('--clear-global-pause',action='store_true');a=p.parse_args();assert 1<=a.width<=64
    if a.clear_global_pause:(HERE/'pilot/global-pause.request').unlink(missing_ok=True)
    folder=(a.folder or HERE/'hybrid'/f'momentum-{a.deadline}-v{a.width}').resolve();folder.mkdir(exist_ok=True)
    lock=(folder/'manager.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    guard=Job(1024);entry=HERE/'pilot/active'/f'{os.getpid()}.json';atomic(entry,{'pid':os.getpid(),'process_created':identity(os.getpid()),'folder':str(folder),'role':'momentum bound'})
    atomic(HERE/'pilot/resume-target.json',{'backend':'momentum','folder':str(folder),'deadline':a.deadline,'width':a.width})
    try:run(a.deadline,a.width,folder,a.resume,guard)
    finally:entry.unlink(missing_ok=True);lock.close()
