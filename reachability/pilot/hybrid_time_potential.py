"""Deadline viability using uncropped phase-aware future contact profiles.

Free source domains cover ground-flag overshoot and arbitrary airborne x.
All future contact domains use original-engine phases at absolute timestamps.
"""
import hashlib,json,math,sys
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'reachability'))
import hybrid_interval_bounds as base
from hybrid_gate_bounds import U,passage_ticks,edge
from correlated_kernel import bounds
from kernel import clip

class TimePotential:
    def __init__(self,deadline=1646,monotone=False):
        self.monotone=monotone
        self.deadline=deadline;self.g=json.loads((ROOT/'reachability/hybrid/gate-bounds.json').read_text());self.free={}
        c=json.loads((ROOT/'reachability/constants.json').read_text());phase=json.loads((ROOT/'reachability/hybrid/phase-bounds.json').read_text())
        assert c['engineSHA256']==phase['metadata']['engineSHA256']==hashlib.sha256((ROOT/'engine.js').read_bytes()).hexdigest()
        self.forward=phase['forward'];self.forward_free={}
        self.first=[next(t for t,p in enumerate(a) if p is not None) for a in self.forward]
        if monotone:
            assert deadline==1646
            check=json.loads((ROOT/'reachability/hybrid/backtrack-check.json').read_text())
            digest=hashlib.sha256((ROOT/'reachability/hybrid/gate-bounds.json').read_bytes()+(ROOT/'reachability/hybrid/phase-bounds.json').read_bytes()).hexdigest()
            assert check['allBackwardLandingsExcluded'] and check['boundsSHA256']==digest
        self.back={};self.domains={}
        for name in ['closed','opened']:
            graph=self.g[name];domains=[]
            for node,cells in enumerate(graph['supports']):
                special=(name=='closed' and node in [0,16,17,31]) or (name=='opened' and node in [0,29])
                if special:domains.append([[min(a for a,b in cells),max(b for a,b in cells)]]*(base.T+1));continue
                support=node if name=='opened' or node<=15 else node-2
                series=[]
                for t in range(base.T+1):
                    l=c['frames'][t]['ledges'][support]
                    lo=math.floor(l['left']*U)-1;hi=math.ceil(l['right']*U)+1
                    if name=='closed' and node==15:hi=min(hi,335*U+1)
                    series.append([lo,hi])
                domains.append(series)
            b=[None]*len(domains);b[-1]=[None]+[domains[-1][0]]*base.T
            for i in range(len(domains)-2,-1,-1):
                reverse=[domains[i][deadline-r] if 0<=deadline-r<=base.T else None for r in range(base.T+1)]
                b[i]=base.propagate(b[i+1],reverse,graph['minimum'][i+1],graph['granular'][i+1],i+1==graph['gate'])
            self.back[name]=b;self.domains[name]=domains

    def viable(self,r,t):
        remaining=self.deadline-t
        if remaining<1:return False
        if not r.opened and r.anchor>=16:return False
        earliest=self.first[max(17,r.anchor+2)] if r.opened else self.first[r.anchor]
        if t<earliest:return False
        x0,x1,_,v1=bounds(r.p)
        # Quantization enlarges the query interval and uses an upper velocity.
        lo=math.floor(x0*1000)*1000;hi=math.ceil(x1*1000)*1000
        if not r.opened and r.anchor==15:
            if r.g<0:cross=61
            elif hi<=335*U:cross=edge(max(0,335*U-hi),0,False)+61
            else:cross=passage_ticks(min(368*U,hi),min(127000001,max(0,math.ceil(v1*1000)*1000+1)))
            return remaining>=cross and self.back['closed'][17][remaining-cross] is not None
        name='opened' if r.opened else 'closed';graph=self.g[name]
        actual=min(29,r.anchor+1)
        node=actual if name=='opened' or actual<=15 else actual+2
        # Node29/31 is the virtual button; its edge has zero vertical debit.
        m=graph['minimum'][node] if r.g>=0 else 0
        granular=graph['granular'][node] and not r.d
        if not r.opened and r.g<0:granular=False # May be mid press-cancel excursion.
        key=(name,node,m,granular)
        if key not in self.free:
            self.free[key]=base.propagate(self.back[name][node],[7*U-1,473*U+1],m,granular)
        part=self.free[key][remaining]
        return part is not None and lo<=part[1] and hi>=part[0]

    def prune(self,r,t):
        if not self.viable(r,t):return None
        if self.monotone and r.opened and r.anchor<15:return None
        if not r.opened and r.anchor==15 and r.g>=0 and self.monotone:
            elapsed=t-self.first[16];upper=335*U+1
            if elapsed>=0:
                x=336058334;v=127000001
                for _ in range(min(elapsed,62)):
                    v=max(60000001,v-(1040*U//120-1));x+=-(-v//120)+1
                upper=min(368*U+1,x)
            p=clip(r.p,0,upper,False)
            return replace(r,p=p) if p else None
        if not self.monotone and (not r.opened or r.anchor<16):return r
        node=r.anchor if r.anchor<=15 else r.anchor+2
        force_free=r.anchor==0 or (r.opened and r.anchor==15)
        if r.opened and r.anchor==15:node=17
        if r.g>=0 and not force_free:
            part=self.forward[node][t]
            # A retained ground flag can end one ordinary movement update
            # beyond its current phase contact interval. The carried point
            # before that movement satisfies the contact-prefix speed bound.
            margin=1060000
        else:
            if node not in self.forward_free:
                self.forward_free[node]=base.propagate(self.forward[node],[7*U-1,473*U+1],0,False)
            part=self.forward_free[node][t];margin=1
        if part is None:return None
        p=clip(clip(r.p,0,part[0]-margin,True),0,part[1]+margin,False)
        return replace(r,p=p) if p else None
