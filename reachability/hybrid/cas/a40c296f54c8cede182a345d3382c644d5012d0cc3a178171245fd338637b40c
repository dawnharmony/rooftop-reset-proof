"""Continuous-position, integer-time contact profiles with O(18*T) dilation.

Closed interval hulls and outward micro-unit rounding always enlarge sets.
No spatial sample or finite beam is used. Whole-dash count is handled by 18
residue classes, retaining the same optimistic motion law as gate-bounds.
"""
import json,time
from pathlib import Path
from hybrid_gate_bounds import NORMAL,CARRY,FAST,U,BONUS
from hybrid_bounds import ceildiv
HERE=Path(__file__).resolve().parent;T=1660

def propagate(source,domain,m,granular,gate=False,carry=CARRY,departure=170001,fast=FAST,cycle_bonus=BONUS):
    out=[None]*(T+1)
    dynamic=not(len(domain)==2 and isinstance(domain[0],int))
    if gate:
        for t in range(61,T+1):
            if source[t-61] is not None:out[t]=domain[t] if dynamic else domain
        return out
    residues=18 if granular else 1
    mins=[None]*residues;maxs=[None]*residues
    c=NORMAL+carry if granular else fast
    penalty=carry*m if granular else (fast-NORMAL)*m
    bonus=cycle_bonus if granular else 0
    for t in range(m,T+1):
        s=t-m;part=source[s]
        if part is not None:
            r=s%residues;q=s//residues
            a=120*part[0]+c*s+bonus*q;b=120*part[1]-c*s-bonus*q
            mins[r]=a if mins[r] is None else min(mins[r],a)
            maxs[r]=b if maxs[r] is None else max(maxs[r],b)
        lower=[];upper=[]
        for r in range(residues):
            if mins[r] is None:continue
            d=c*t+bonus*((t-m-r)//residues)-penalty+departure*120
            lower.append((mins[r]-d)//120)
            upper.append(ceildiv(maxs[r]+d,120))
        if not lower:continue
        current=domain[t] if dynamic else domain
        if current is None:continue
        lo=max(current[0],min(lower));hi=min(current[1],max(upper))
        if lo<=hi:out[t]=[lo,hi]
    return out

def profiles(g):
    domains=[[min(a for a,b in cells),max(b for a,b in cells)] for cells in g['supports']]
    f=[[domains[0]]*(T+1)]
    for i in range(1,len(domains)):f.append(propagate(f[-1],domains[i],g['minimum'][i],g['granular'][i],i==g['gate']))
    b=[None]*len(domains);b[-1]=[None]+[domains[-1]]*T
    for i in range(len(domains)-2,-1,-1):b[i]=propagate(b[i+1],domains[i],g['minimum'][i+1],g['granular'][i+1],i+1==g['gate'])
    initial=domains[0][0]
    lower=next(t for t,part in enumerate(b[0]) if part is not None and part[0]<=initial<=part[1])
    return {'domains':domains,'forward':f,'backward':b,'lowerBoundResetTick':lower}

def main():
    start=time.perf_counter();g=json.loads((HERE/'hybrid/gate-bounds.json').read_text())
    out={name:profiles(g[name]) for name in ['closed','opened','ungated']}
    records=json.loads((HERE/'hybrid-world.json').read_text())['records'];checked=0
    for name,record in records.items():
        for c in record['contacts']:
            i=c['ledge'];node=i if i<=15 else i+2;x=c['x']*U
            a=out['closed']['forward'][node][c['tick']];b=out['closed']['backward'][node][record['ticks']-c['tick']]
            assert a and a[0]-1e-5<=x<=a[1]+1e-5,(name,i,'forward',a,x)
            assert b and b[0]-1e-5<=x<=b[1]+1e-5,(name,i,'backward',b,x)
            checked+=1
    out['metadata']={'engineSHA256':g['engineSHA256'],'horizon':T,'unit':U,'recordContactsAdmitted':checked,'seconds':time.perf_counter()-start,'scope':'Continuous-position necessary bound, mandatory-gate theorem still under review'}
    (HERE/'hybrid/interval-bounds.json').write_text(json.dumps(out,separators=(',',':')))
    print(json.dumps(out['metadata']|{name:out[name]['lowerBoundResetTick'] for name in ['closed','opened','ungated']},indent=2))
if __name__=='__main__':main()
