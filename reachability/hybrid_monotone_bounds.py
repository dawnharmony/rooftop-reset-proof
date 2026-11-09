"""Per-support carry refinement, conditional on the weaker retreat exclusion.

Does not regenerate the weaker certificate on which no-retreat relies.
With no lower contacts, every grounded carry before next upward contact comes
from the one current support. Full-cycle dash time has at most one such carry.
"""
import hashlib,json,math,time
from pathlib import Path
import hybrid_interval_bounds as base
from hybrid_gate_bounds import U
from hybrid_bounds import ceildiv
HERE=Path(__file__).resolve().parent
def build():
    began=time.perf_counter();g=json.loads((HERE/'hybrid/gate-bounds.json').read_text())['closed'];c=json.loads((HERE/'constants.json').read_text());phase=json.loads((HERE/'hybrid/phase-bounds.json').read_text())
    proof=json.loads((HERE/'hybrid/backtrack-check.json').read_text())
    digest=hashlib.sha256((HERE/'hybrid/gate-bounds.json').read_bytes()+(HERE/'hybrid/phase-bounds.json').read_bytes()).hexdigest()
    assert proof['allBackwardLandingsExcluded'] and proof['boundsSHA256']==digest
    assert c['engineSHA256']==hashlib.sha256((HERE.parent/'engine.js').read_bytes()).hexdigest()
    domains=phase['domains'];params=[]
    for i in range(len(domains)):
        source=i-1 if i<=15 else 15 if i<=18 else i-3
        source=max(0,min(28,source))
        travel=c['ledges'][source]['travel']
        # 1.7*travel is the derivative bound. Actual original-JS carries are
        # also checked directly below at every potentially used update.
        carry=math.ceil(1.7*travel*U)+1 if travel else 0
        for frame in c['frames'][:1647]:assert abs(frame['ledges'][source]['carry'])*U<=carry/120+1
        params.append({'carry':carry,'departure':ceildiv(carry,120)+1,'fast':312000001+carry,'cycle_bonus':3143*U-17*carry})
    f=[domains[0]]
    for i in range(1,len(domains)):f.append(base.propagate(f[-1],domains[i],g['minimum'][i],g['granular'][i],i==g['gate'],**params[i]))
    earliest=next((t+1 for t,part in enumerate(f[-1]) if part is not None),None)
    # Deadline1647 is a consistency control. The no-retreat proof applies to
    #1646; the archived1647run independently satisfies the no-retreat premise.
    backward={};checks=0
    world=json.loads((HERE/'hybrid-world.json').read_text())
    for deadline in [1646,1647,1649,1657]:
        b=[None]*len(domains);b[-1]=[None]+[domains[-1][0]]*base.T
        for i in range(len(domains)-2,-1,-1):
            reverse=[domains[i][deadline-r] if 0<=deadline-r<=base.T else None for r in range(base.T+1)]
            b[i]=base.propagate(b[i+1],reverse,g['minimum'][i+1],g['granular'][i+1],i+1==g['gate'],**params[i+1])
        backward[str(deadline)]=b
    for name,record in world['records'].items():
        for contact in record['contacts']:
            i=contact['ledge'];node=i if i<=15 else i+2;t=contact['tick'];x=contact['x']*U
            a=f[node][t];b=backward[str(record['ticks'])][node][record['ticks']-t]
            assert a and a[0]-1e-5<=x<=a[1]+1e-5,(name,i,'forward',a,x)
            assert b and b[0]-1e-5<=x<=b[1]+1e-5,(name,i,'backward',b,x)
            checks+=1
    metadata={'engineSHA256':c['engineSHA256'],'retreatCertificateBoundsSHA256':digest,'earliestResetTick':earliest,'targetExcluded':earliest is None or earliest>1646,'recordContactsAdmitted':checks,'seconds':time.perf_counter()-began,'scope':'Conditional no-retreat per-support carry bound; source and numerical audit required'}
    out={'metadata':metadata,'parameters':params,'domains':domains,'forward':f,'backward':backward['1646']}
    (HERE/'hybrid/monotone-bounds.json').write_text(json.dumps(out,separators=(',',':')))
    print(json.dumps(metadata,indent=2))
if __name__=='__main__':build()
