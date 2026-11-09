"""Unscheduled, first-contact outer reachability.
Horizontal convex polygons x vertical intervals x explicit resource modes.
Every merge is a union enclosure. No beam/ranking/state sampling prunes coverage.
Inputs in stored traces are proposals only; the regions are not concrete paths.
"""
from dataclasses import dataclass,replace
import math
from kernel import hull,clip,step,SCALE,contains
Y=[0,32,68,105,145,182,222,261,299,337,378,420,459,501,539,578,618,660,700,740,780,820,862,901,941,982,1023,1062,1105]
Q=1024
def outward(lo,hi):return (math.floor((lo-1e-9)*Q)/Q,math.ceil((hi+1e-9)*Q)/Q)
def add(a,b):return outward(a[0]+b[0],a[1]+b[1])
def scale(a,b):return outward(min(a[0]*b,a[1]*b),max(a[0]*b,a[1]*b))
@dataclass(slots=True)
class Region:
 p:list;y:tuple;v:tuple;g:int;d:int;cy:int;ready:int;direction:int;opened:int;cross:int;anchor:int;trace:bytes=b''
 def discrete(self):return (self.g,self.d,self.cy,self.ready,self.direction,self.opened,self.cross,self.anchor)
def bounds(p):return min(x for x,v in p)/SCALE,max(x for x,v in p)/SCALE,min(v for x,v in p)/SCALE,max(v for x,v in p)/SCALE
def seed(state):
 p=state['p'];d=0;t=p['dash']
 while t>0:t=max(0,t-1/120);d+=1
 cy=0;t=p['coyote']
 while t>0:
  t=max(0,t-1/120)
  if t>0:cy+=1
 x,v=p['x']*SCALE,p['vx']*SCALE
 poly=hull([(a,b) for a in [math.floor(x)-1,math.ceil(x)+1] for b in [math.floor(v)-1,math.ceil(v)+1]])
 return Region(poly,(p['y'],p['y']),(p['vy'],p['vy']),p['ground'] if p['ground'] is not None else -1,d,cy,int(p['dashReady']),p['facing'] if d else 0,int(state['pressOpen']),int(state['crossingPress']),state['_support'])
def merge(a,b,vertex_cap):
 p=hull(a.p+b.p);coarsen=0
 if len(p)>vertex_cap:
  xs=[x for x,v in p];vs=[v for x,v in p];p=hull([(x,v) for x in [min(xs),max(xs)] for v in [min(vs),max(vs)]]);coarsen=1
 return replace(a,p=p,y=(min(a.y[0],b.y[0]),max(a.y[1],b.y[1])),v=(min(a.v[0],b.v[0]),max(a.v[1],b.v[1]))),coarsen
def key(r,cell):
 if not cell:return r.discrete()
 x0,x1,v0,v1=bounds(r.p)
 return r.discrete()+(math.floor((x0+x1)/2/cell),math.floor((v0+v1)/2/(cell*4)),math.floor(sum(r.y)/2/(cell/4)),math.floor(sum(r.v)/2/(cell*4)))
def finish(r,last_y,old_x,world,token):
 """Press alternatives and optional contacts; ambiguous guards branch outward."""
 variants=[r];x0,x1,_,_=bounds(r.p)
 if not r.opened and x1>335 and x0<368 and r.y[1]>484 and r.y[0]<666:
  # No-collision remains an extra possibility at ambiguous/relaxed guards.
  if old_x[0]<=335:variants.append(replace(r,p=[(335*SCALE,0)],d=0,direction=0))
  if old_x[1]>=368:variants.append(replace(r,p=[(368*SCALE,0)],d=0,direction=0))
  if last_y[1]>=666 and r.v[0]<0:variants.append(replace(r,y=(666,666),v=(0,0)))
  for h in [484,495]:variants.append(replace(r,y=(h,h),v=(min(0,r.v[0]),min(0,r.v[1]))))
 for q in variants:
  if q.y[0]>Y[q.anchor]+54:continue
  q=replace(q,y=(max(-10000,q.y[0]),min(Y[q.anchor]+54,q.y[1])),trace=q.trace+bytes([token]))
  choices=[q]
  if not q.opened:
   xx0,xx1,_,_=bounds(q.p)
   if xx0<=335:choices.append(replace(q,cross=0))
   if q.g==15 and q.y[0]<=578<=q.y[1] and xx1>335 and xx0<368:choices.append(replace(q,cross=1))
   if q.cross and xx1>=368:choices.append(replace(q,opened=1))
  for u in choices:
   if u.g>=0:
    yield replace(u,y=(Y[u.g],Y[u.g]));continue
   yield u # Optional non-contact covers crumbled or skipped surfaces.
   if u.d or u.v[0]>0:continue
   for i in range(min(28,u.anchor+1),-1,-1):
    left,right,_=world[i]
    if last_y[1]<Y[i]-.001 or u.y[0]>Y[i]:continue
    p=clip(clip(u.p,0,math.floor((left-1e-9)*SCALE),True),0,math.ceil((right+1e-9)*SCALE),False)
    if p:yield replace(u,p=p,y=(Y[i],Y[i]),v=(0,0),g=i,ready=1,cy=11,anchor=i)
def successors(r,world,target):
 old_x=bounds(r.p)[:2];carried=r.p
 if r.g>=0:
  c=world[r.g][2];lo=math.floor((c-1e-9)*SCALE);hi=math.ceil((c+1e-9)*SCALE)
  carried=hull([(x+d,v) for x,v in carried for d in [lo,hi]])
 support=[replace(r,p=carried,g=-1,cy=max(0,r.cy-1))]
 if r.g>=0:
  left,right,_=world[r.g];p=clip(clip(carried,0,math.floor((left-1e-9)*SCALE),True),0,math.ceil((right+1e-9)*SCALE),False)
  if p:support.append(replace(r,p=p,cy=11))
 for s in support:
  actions=[(s,0)]
  if s.g>=0 or r.cy>0:actions.append((replace(s,g=-1,cy=0,v=(285,285)),4))
  if s.g>0:actions.append((replace(s,g=-1,cy=0,y=add(s.y,(-2.5,-2.5)),v=(-85,-85)),4|16))
  for a,flags in actions:
   cuts=[(a,flags)]
   if a.v[1]>110:cuts.append((replace(a,v=scale((max(110,a.v[0]),a.v[1]),.54)),flags|8))
   for c,flags in cuts:
    dashes=[(c,flags)]
    if c.ready:
     for direction in [-1,1]:dashes.append((replace(c,g=-1,cy=0,d=18,ready=0,direction=direction),flags|32))
    for d,flags in dashes:
     if d.d:
      left=d.d-1;velocity=d.direction*(312 if left else 125)
      p=step(d.p,-1,-1,2,velocity,world,clamp_world=True)
      q=replace(d,p=p,d=left,direction=d.direction if left else 0)
      axis=d.direction
      yield from finish(q,d.y,old_x,world,(axis+1)|flags)
     else:
      p=step(d.p,-1,-1,1 if d.g>=0 else 0,0,world,clamp_world=True)
      x0,x1,_,_=bounds(p);center=world[target][0]+3;axis=-1 if (x0+x1)/2>center else 1
      if d.g>=0:
       # Crouch is unrestricted; acceleration enclosure also covers retained
       # run-up momentum. Emit a crouched proposal for passage transitions.
       for down in [0,16]:yield from finish(replace(d,p=p),d.y,old_x,world,(axis+1)|flags|down)
      else:
       for gravity,vy,down in [(740,d.v,0)]+([(1410,(d.v[0],min(0,d.v[1])),16)] if d.v[0]<=0 else []):
        v=add(vy,(-gravity/120,-gravity/120));limit=-490 if down else -420
        v=(max(limit,v[0]),max(limit,v[1]));y=add(d.y,scale(v,1/120))
        yield from finish(replace(d,p=p,v=v,y=y),d.y,old_x,world,(axis+1)|flags|down)
