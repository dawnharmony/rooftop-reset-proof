"""Stronger necessary bounds: complete dash cycles and mandatory press gate.

The gate bound is kept separate until its topological/source obligations are
checked. It is never silently substituted into an active search checkpoint.
"""
import hashlib,json,time
from pathlib import Path
from hybrid_bounds import vertical_minima,cells,ceildiv
HERE=Path(__file__).resolve().parent;U=10**6
NORMAL=127000001;CARRY=20400001;FAST=332400001
# A full dash has at most one grounded carry update: activation. Its other
# 17 updates are airborne. Discount the carry that the generic speed envelope
# otherwise grants to all nonselected updates. Extra departure credit remains.
BONUS=3143*U-17*CARRY

def edge(distance,m,granular):
    if not granular:return max(m,ceildiv((distance-170001)*120+(FAST-NORMAL)*m,FAST))
    # Minimize the maximum of one increasing and one decreasing affine
    # function of whole dash count k. Only the two integers adjacent to
    # their intersection can minimize it (plus the nonnegative endpoint).
    k=max(0,(distance*120-170001*120-NORMAL*m)//(18*(NORMAL+CARRY)+BONUS))
    return min(max(m+18*j,ceildiv(distance*120+CARRY*m-BONUS*j-170001*120,NORMAL+CARRY)) for j in {0,k,k+1})

def passage_ticks(x=336058334,v=127000001):
    n=0
    while x<368*U:
        v=max(60000001,v-(1040*U//120-1));x+=ceildiv(v,120)+1;n+=1
    return n

def graph(supports,m,granular,gate=None):
    def cost(i,a,b):
        if i==gate:return passage_ticks()
        return edge(max(0,b[0]-a[1],a[0]-b[1]),m[i],granular[i])
    f=[[0]]
    for i in range(1,len(supports)):
        f.append([min(t+cost(i,a,b) for a,t in zip(supports[i-1],f[-1])) for b in supports[i]])
    back=[None]*len(supports);back[-1]=[1]
    for i in range(len(supports)-2,-1,-1):
        back[i]=[min(cost(i+1,a,b)+t for b,t in zip(supports[i+1],back[i+1])) for a in supports[i]]
    return {'supports':supports,'minimum':m,'granular':granular,'gate':gate,'forward':f,'backward':back,'resetLowerBound':back[0][0]}

def build():
    start=time.perf_counter();world=json.loads((HERE/'hybrid-world.json').read_text());L=world['ledges']
    assert world['engineSHA256']==hashlib.sha256((HERE.parent/'engine.js').read_bytes()).hexdigest()
    gaps=[L[i]['y']-L[i-1]['y'] for i in range(1,29)];v=vertical_minima(set(gaps));m=[0]+[v[h] for h in gaps]
    supports=[[(56*U,56*U)]]+[cells((l['x']-l['travel']-3)*U,(l['x']+l['travel']+l['w']+3)*U,U) for l in L[1:]]+ [[(420*U,450*U)]]
    # This opened-press suffix graph can start at any actual support x.
    opened=graph(supports,m+[0],[False]+[True]*29)
    # A canceled dash on transfers12->13 or13->14 must reach a wall at335
    # (or368). Even its nearest possible roundabout path takes longer under
    # fractional-dash speed than the most expensive direct granular edge.
    # Therefore the granular cost is also a necessary lower bound for these
    # canceled paths. First15 remains the exception; all later paths are open.
    cancellation_dominance=[]
    for i in [13,14]:
        a=supports[i-1];b=supports[i]
        left=min(x for x,y in a);right=max(y for x,y in a);destleft=min(x for x,y in b);destright=max(y for x,y in b)
        worst_direct=max(abs(left-destright),abs(right-destleft))
        best_via=335*U-right+335*U-destright
        direct=edge(worst_direct,m[i],True);canceled=edge(best_via,m[i],False)
        assert canceled>=direct
        cancellation_dominance.append({'target':i,'worstDirectTicks':direct,'bestCanceledTicks':canceled,'holds':True})
    granular=[False]+[i!=15 for i in range(1,30)]
    ungated=graph(supports,m+[0],granular)
    closed_supports=supports[:15]+[cells(291*U,335*U,U),[(335*U,336058334)],[(368*U,368500002)]]+supports[16:]
    closed_m=m[:16]+[0,0]+m[16:]+[0]
    closed_granular=granular[:16]+[False,False]+[True]*14
    closed=graph(closed_supports,closed_m,closed_granular,gate=17)
    diagnostics=[]
    for name,record in world['records'].items():
        for c in record['contacts']:
            i=c['ledge'];j=i if i<=15 else i+2;x=c['x']*U
            nodes=[k for k,(lo,hi) in enumerate(closed_supports[j]) if lo-1e-5<=x<=hi+1e-5]
            assert nodes,(name,i,x)
            assert min(closed['forward'][j][k] for k in nodes)<=c['tick']
            assert min(closed['backward'][j][k] for k in nodes)<=record['ticks']-c['tick']
        diagnostics.append({'record':name,'contactsAdmitted':29})
    out={'engineSHA256':world['engineSHA256'],'unit':U,'closed':closed,'opened':opened,'ungated':ungated,'cancellationDominance':cancellation_dominance,'pressGateMinTicks':passage_ticks(),'lowerBoundResetTick':closed['resetLowerBound'],'targetExcluded':closed['resetLowerBound']>1646,'diagnostics':diagnostics,'seconds':time.perf_counter()-start,'scope':'Candidate global lower bound; mandatory-gate theorem and arithmetic require independent review before pruning.'}
    (HERE/'hybrid/gate-bounds.json').write_text(json.dumps(out,separators=(',',':')))
    print(json.dumps({k:v for k,v in out.items() if k not in ['closed','opened','ungated']}|{'ungatedDashCycleBound':ungated['resetLowerBound']},indent=2))
if __name__=='__main__':build()
