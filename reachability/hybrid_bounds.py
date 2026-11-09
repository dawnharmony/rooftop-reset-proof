"""Route-independent optimistic mandatory-contact timing graph.

All graph distances are integer ticks. A spatial cell contains a CLOSED
interval; edge distances use the nearest interval endpoints. Overlap and
independent choices at successive edges enlarge the set of trajectories.
No ranked frontier, sampled controls, or recorded landing times are used.
"""
import argparse, hashlib, json, math, time
from pathlib import Path

HERE=Path(__file__).resolve().parent
Q=10**9
def ceildiv(a,b): return -((-a)//b)

def vertical_envelope(horizon=90):
    """Upper previous-height envelope conditional on downward motion.

    Up to two jump cuts, even at the same non-dash update, are admitted.
    Dash pause time is deleted. Normal descending gravity maximizes height;
    the first nonpositive velocity occurs before fast-fall can activate.
    Arithmetic is outward fixed point with a nanounit per operation margin.
    """
    previous=[-10**30]*(horizon+1)
    peak=0
    schedules=[(-1,-1)]+[(a,-1) for a in range(horizon)]+[(a,b) for a in range(horizon) for b in range(a,horizon)]
    for a,b in schedules:
        yl=yh=0;vl=vh=285*Q
        for t in range(horizon):
            for cut in (a,b):
                if t==cut:
                    vl=vl*54//100-1;vh=ceildiv(vh*54,100)+1
            vl-=ceildiv(740*Q,120)+1;vh-=740*Q//120-1
            # A real descending fast-fall trajectory is below this slow-fall
            # trajectory, and has the same first nonpositive-velocity update.
            if vl<=0: previous[t+1]=max(previous[t+1],yh)
            yl+=vl//120-1;yh+=ceildiv(vh,120)+1
            peak=max(peak,yh)
    return previous,peak

def cells(lo,hi,width):
    # micro-units avoid a floating-point floor/ceil narrowing a support.
    return [(a,min(a+width,hi)) for a in range(lo,hi+1,width)]

def vertical_minima(heights,horizon=80):
    """Necessary touchdown conditions, including all coyote delays <=11.

    Maximum fast-fall is earliest for each fixed ascent/cut schedule: it
    leaves the ascent unchanged and weakly lowers every descending position.
    Use one outward interval trajectory, rather than mixing slow previous
    height with fast current height. Optimize over a continuous launch-height
    offset interval, deliberately larger than real coyote possibilities.
    Coyote launch height is enclosed between -1410*k*(k+1)/(2*120^2)
    and zero, and all k waiting updates count toward elapsed flight time.
    """
    best={h:10**6 for h in heights}
    schedules=[(-1,-1)]+[(a,-1) for a in range(horizon)]+[(a,b) for a in range(horizon) for b in range(a,horizon)]
    for a,b in schedules:
        high=low=0;vs=vl=285*Q
        for t in range(horizon):
            valid=True
            for cut in (a,b):
                if t==cut:
                    # Original cuts require pre-cut vy>110. Before first
                    # descent the slow envelope bounds every real velocity;
                    # later no real cut can occur. Discard only a definitely
                    # impossible requested cut, retaining threshold ambiguity.
                    if vs<110*Q-1:valid=False;break
                    vs=ceildiv(vs*54,100)+1;vl=vl*54//100-1
            if not valid:break
            prev=high
            vs=max(-490*Q+1,vs-((1410 if vs<=0 else 740)*Q//120-1))
            vl=max(-490*Q-1,vl-ceildiv((1410 if vl<=0 else 740)*Q,120)-1)
            high+=ceildiv(vs,120)+1;low+=vl//120-1
            n=t+1
            if vl>0:continue
            for h in heights:
                if prev<round((h-.001001)*Q) or n>=best[h]:continue
                for k in range(12):
                    drop=ceildiv(1410*Q*k*(k+1),2*120*120)+1000
                    if max(-drop,round((h-.001001)*Q)-prev)<=min(0,h*Q-low):
                        best[h]=min(best[h],n+k);break
    return best

def build(width=1):
    began=time.perf_counter();world=json.loads((HERE/'hybrid-world.json').read_text())
    assert hashlib.sha256((HERE.parent/'engine.js').read_bytes()).hexdigest()==world['engineSHA256']
    L=world['ledges'];env,peak=vertical_envelope()
    assert peak<54*Q
    gaps=[L[i]['y']-L[i-1]['y'] for i in range(1,29)]
    min_by_gap=vertical_minima(set(gaps))
    minimum=[0]+[min_by_gap[h] for h in gaps]
    U=10**6;w=round(width*U)
    supports=[[(56*U,56*U)]]+[cells((l['x']-l['travel']-3)*U,(l['x']+l['travel']+l['w']+3)*U,w) for l in L[1:]]
    # A final virtual contact represents button eligibility. Its +1 action
    # is separate because the engine checks reset BEFORE movement.
    supports.append([(420*U,450*U)]);minimum.append(0)
    # Upper speed/carry bounds include a micro-unit arithmetic allowance.
    speed=332400001;normal=127000001;carry=170001
    def edge(i,a,b):
        distance=max(0,b[0]-a[1],a[0]-b[1])
        m=minimum[i]
        # Select the mandatory flight's m airborne updates at speed <=127.
        # Every other update is granted speed312+20.4, including arbitrary
        # repeated dashes/recontacts. One flight departure gets carry credit.
        return max(m,ceildiv((distance-carry)*120+(speed-normal)*m,speed))
    forward=[[0]]
    for i in range(1,len(supports)):
        forward.append([min(t+edge(i,a,b) for a,t in zip(supports[i-1],forward[-1])) for b in supports[i]])
    backward=[None]*len(supports);backward[-1]=[1]
    for i in range(len(supports)-2,-1,-1):
        backward[i]=[min(edge(i+1,a,b)+t for b,t in zip(supports[i+1],backward[i+1])) for a in supports[i]]
    validation=[]
    for name,record in world['records'].items():
        assert [c['ledge'] for c in record['contacts']]==list(range(29))
        for c in record['contacts']:
            i=c['ledge'];x=c['x']*U
            nodes=[j for j,(lo,hi) in enumerate(supports[i]) if lo-1e-5<=x<=hi+1e-5]
            assert nodes,(name,i,x)
            assert min(forward[i][j] for j in nodes)<=c['tick'],(name,i,'earliest')
            assert min(backward[i][j] for j in nodes)<=record['ticks']-c['tick'],(name,i,'remaining')
        validation.append({'record':name,'all29ContactsAdmitted':True})
    report={'schema':1,'engineSHA256':world['engineSHA256'],'cellWidth':width,'unit':U,'minimumNonDashUpdates':minimum,'maximumJumpHeightUpper':peak/Q,'supports':supports,'forward':forward,'backward':backward,'lowerBoundResetTick':backward[0][0],'targetResetTick':1646,'targetExcluded':backward[0][0]>1646,'validation':validation,'seconds':time.perf_counter()-began,'scope':'Global mandatory-contact relaxation; soundness argument remains subject to independent source review, not machine-checked JS refinement.'}
    report['windows']=[{'ledge':i,'earliest':min(forward[i]),'latestFor1646':1646-min(backward[i]),'cells':len(supports[i]),'survivingCells':sum(a+b<=1646 for a,b in zip(forward[i],backward[i]))} for i in range(29)]
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--width',type=float,default=1);p.add_argument('--output',default='bounds.json');a=p.parse_args();r=build(a.width)
    out=HERE/'hybrid';out.mkdir(exist_ok=True)
    (out/a.output).write_text(json.dumps(r,separators=(',',':')))
    print(json.dumps({k:v for k,v in r.items() if k not in ['supports','forward','backward']},indent=2))
