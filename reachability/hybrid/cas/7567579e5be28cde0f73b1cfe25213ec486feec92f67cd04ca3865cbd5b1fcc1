"""Phase-aware mandatory-contact profiles, using original JS platform tables."""
import hashlib,json,math,time
from pathlib import Path
import hybrid_interval_bounds as base
from hybrid_gate_bounds import U
HERE=Path(__file__).resolve().parent

def build():
    began=time.perf_counter();g=json.loads((HERE/'hybrid/gate-bounds.json').read_text())['closed'];c=json.loads((HERE/'constants.json').read_text())
    assert c['engineSHA256']==hashlib.sha256((HERE.parent/'engine.js').read_bytes()).hexdigest()
    domains=[]
    for node,cells in enumerate(g['supports']):
        if node in [0,16,17,31]:domains.append([[min(a for a,b in cells),max(b for a,b in cells)]]*(base.T+1));continue
        support=node if node<=15 else node-2
        series=[]
        for t in range(base.T+1):
            l=c['frames'][t]['ledges'][support]
            lo=math.floor(l['left']*U)-1;hi=math.ceil(l['right']*U)+1
            if node==15:hi=min(hi,335*U+1)
            series.append([lo,hi])
        domains.append(series)
    f=[domains[0]]
    for i in range(1,len(domains)):f.append(base.propagate(f[-1],domains[i],g['minimum'][i],g['granular'][i],i==g['gate']))
    earliest=next(t+1 for t,part in enumerate(f[-1]) if part is not None)
    backward={}
    for deadline in [1646,1647,1649,1657]:
        b=[None]*len(domains);b[-1]=[None]+[domains[-1][0]]*base.T
        for i in range(len(domains)-2,-1,-1):
            reverse=[domains[i][deadline-r] if 0<=deadline-r<=base.T else None for r in range(base.T+1)]
            b[i]=base.propagate(b[i+1],reverse,g['minimum'][i+1],g['granular'][i+1],i+1==g['gate'])
        backward[str(deadline)]=b
    checks=0
    world=json.loads((HERE/'hybrid-world.json').read_text())
    for name,record in world['records'].items():
        b=backward[str(record['ticks'])]
        for contact in record['contacts']:
            i=contact['ledge'];node=i if i<=15 else i+2;t=contact['tick'];x=contact['x']*U
            a=f[node][t];part=b[node][record['ticks']-t]
            assert a and a[0]-1e-5<=x<=a[1]+1e-5,(name,i,'forward',a,x)
            assert part and part[0]-1e-5<=x<=part[1]+1e-5,(name,i,'backward',part,x)
            checks+=1
    metadata={'engineSHA256':c['engineSHA256'],'earliestResetTick':earliest,'targetExcluded':earliest>1646,'recordContactsAdmitted':checks,'seconds':time.perf_counter()-began,'scope':'Phase-aware necessary bound; gate/source and arithmetic audit pending'}
    target={'metadata':metadata,'domains':domains,'forward':f,'backward':backward['1646']}
    (HERE/'hybrid/phase-bounds.json').write_text(json.dumps(target,separators=(',',':')))
    (HERE/'hybrid/phase-positive-control.json').write_text(json.dumps({'deadline':1647,'backward':backward['1647']},separators=(',',':')))
    print(json.dumps(metadata,indent=2))
if __name__=='__main__':build()
