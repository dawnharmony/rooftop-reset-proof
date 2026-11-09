"""Guard-aligned event partitions; every intersecting cell is retained."""
from dataclasses import replace
from boundary_kernel import Region,seed,key,merge,bounds,box,area_ratio,STATS
import correlated_kernel as base
from kernel import clip,SCALE
import math

def cells(p,edges):
 edges=sorted(set(edges));lo=min(x for x,v in p);hi=max(x for x,v in p)
 for i in range(len(edges)+1):
  left=edges[i-1] if i else None;right=edges[i] if i<len(edges) else None
  if left is not None and hi<left:continue
  if right is not None and lo>right:continue
  q=p
  if left is not None:q=clip(q,0,left,True)
  if right is not None:q=clip(q,0,right,False)
  if q:yield i,q

def successors(r,world,target,loose_press=False):
 for q in base.successors(r,world,target,loose_press):
  token=q.trace[-1];event=0
  if token&4:event=2 if token&16 else 1
  if token&32:event=3
  if q.g>=0 and (r.g!=q.g or r.d):event=4
  if not event:yield q;continue
  xedges=[335*SCALE,368*SCALE]
  for support in [q.anchor,target]:
   xedges.extend([math.floor(world[support][0]*SCALE),math.ceil(world[support][1]*SCALE)])
  yedges=[484*SCALE,495*SCALE,578*SCALE,583*SCALE,666*SCALE,base.Y[q.anchor]*SCALE,base.Y[target]*SCALE]
  for xb,p in cells(q.p,xedges):
   for yb,z in cells(q.z,yedges):
    yield replace(q,p=p,z=z,tag=(event,len(q.trace)//16,xb,yb))
