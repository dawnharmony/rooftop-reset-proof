"""Disjunctive event-cell coupling; not a full 4-D convex domain.

Every event cell is retained. Resource collapse may merge geometry inside a
cell, but cannot merge different event tags. Exhaustion stops the query.
"""
from dataclasses import dataclass,replace
import math
import correlated_kernel as base
from correlated_kernel import bounds,box,area_ratio,STATS
from kernel import SCALE,clip

@dataclass(slots=True)
class Region(base.Region):
 tag:tuple=(0,0,0,0)

def seed(s):
 r=base.seed(s)
 return Region(r.p,r.z,*r.discrete(),r.trace)

def cells(p,width):
 lo=min(x for x,v in p);hi=max(x for x,v in p);w=width*SCALE
 for cell in range(lo//w,hi//w+1):
  part=clip(clip(p,0,cell*w,True),0,(cell+1)*w,False)
  if part:yield cell,part

def successors(r,world,target,loose_press=False):
 for q in base.successors(r,world,target,loose_press):
  token=q.trace[-1];event=0
  if token&4:event=2 if token&16 else 1
  if token&32:event=3
  if q.g>=0 and (r.g!=q.g or r.d):event=4
  if not event:yield q;continue
  # Conditional product cells remember where/when a shared boundary occurred.
  for xb,p in cells(q.p,64):
   for yb,z in cells(q.z,32):
    yield replace(q,p=p,z=z,tag=(event,len(q.trace)//16,xb,yb))

def key(r,cell):return base.key(r,cell)+r.tag

def merge(a,b,vertex_cap):
 assert a.tag==b.tag,'Merging different boundary histories would erase coupling'
 return base.merge(a,b,vertex_cap)
