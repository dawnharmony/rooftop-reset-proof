"""History-disjunctive refinement of the existing outer transition kernel.

Timing labels only control union-enclosing merges; they never restrict input
choices. All velocity cells at contact are retained. No region is ranked out.
"""
from dataclasses import dataclass,replace
import struct,zlib
import correlated_kernel as base
from correlated_kernel import bounds,Y
from kernel import clip,SCALE

FIRST=9;LAST=16;TIMEBIN=4;REMOVE_DROPS=False
ZERO=(0,0,-1,-1,-1,0)
def configure(first,last,timebin,monotone):
    global FIRST,LAST,TIMEBIN,REMOVE_DROPS
    FIRST,LAST,TIMEBIN,REMOVE_DROPS=first,last,timebin,monotone

@dataclass(slots=True)
class Region(base.Region):
    tag:tuple=ZERO
    def discrete(self):return super(Region,self).discrete()+self.tag

def seed(s):
    r=base.seed(s)
    return Region(r.p,r.z,*r.discrete(),r.trace,ZERO)

def successors(r,world,target):
    for q in base.successors(r,world,target):
        token=q.trace[-1];n=len(q.trace)
        # A true drop leaves vy<0,coyote0 and height below support. Another
        # jump requires a lower contact; the independently checked retreat
        # exclusion makes that impossible in a faster run.
        if REMOVE_DROPS and token&20==20:continue
        # Once below the old support with no coyote and no upward velocity,
        # a real path cannot contact that support again. Press corrections
        # cannot raise it above the previous height. A lower landing is
        # already excluded for the faster deadline.
        if REMOVE_DROPS and q.g<0 and not q.cy:
            if max(y for y,v in q.z)<Y[q.anchor]*SCALE-1001 and max(v for y,v in q.z)<=0:continue
        if not FIRST<=q.anchor<=LAST:
            yield replace(q,tag=ZERO);continue
        if q.g>=0:
            # Ground fixes (y,vy). Keeping airborne histories here costs
            # many cells without retaining a cross-motion relationship.
            yield replace(q,tag=ZERO)
            continue
        entry,velocity,jump,cut,dash,count=q.tag
        if r.g>=0:entry=n//TIMEBIN
        if token&4:
            jump=n//TIMEBIN;cut=-1;count=0
            if not r.d:dash=-1
        if token&8:cut=n//TIMEBIN;count=min(3,count+1)
        if token&32:dash=n//TIMEBIN
        yield replace(q,tag=(entry,velocity,jump,cut,dash,count))

def key(r,cell):return r.discrete()
def merge(a,b,cap):
    assert a.tag==b.tag
    return base.merge(a,b,cap)

HEADER=struct.Struct('<8b6hBBH')
def pack(regions):
    out=bytearray()
    for r in regions:
        out.extend(HEADER.pack(*r.discrete(),len(r.p),len(r.z),len(r.trace)))
        for x,v in r.p+r.z:out.extend(struct.pack('<ii',x,v))
        out.extend(r.trace)
    return zlib.compress(out)
def unpack(blob):
    b=zlib.decompress(blob);i=0;out=[]
    while i<len(b):
        h=HEADER.unpack_from(b,i);i+=HEADER.size;n,m,t=h[14:17]
        points=[struct.unpack_from('<ii',b,i+j*8) for j in range(n+m)];i+=(n+m)*8;trace=b[i:i+t];i+=t
        out.append(Region(points[:n],points[n:],*h[:8],trace,tuple(h[8:14])))
    return out
