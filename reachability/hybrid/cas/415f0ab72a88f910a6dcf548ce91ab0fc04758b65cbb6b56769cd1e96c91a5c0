"""Outer reachability with separate (x,vx) and (y,vy) convex polygons.

This is a product abstraction, not full 4-D correlation. Input histories,
hazards and optional platform contacts remain relaxed. Press guards are split
in source order; unresolved guards are enclosed, never selected by a sample.
"""
from dataclasses import dataclass,replace
import math
from kernel import hull,clip,corners,step,SCALE,contains
from branch_kernel import seed as old_seed,Y,bounds

STATS={'vertical_templates':0,'vertical_boxes':0,'press_wall':0,'press_roof':0,'press_under':0,'press_opening':0}

def box(p):
 xs=[x for x,v in p];vs=[v for x,v in p]
 return hull([(x,v) for x in [min(xs),max(xs)] for v in [min(vs),max(vs)]]) if p else []

def lineclip(p,a,b,c,lower=True):
 """Outward intersection with a*y+b*vy >= c (or <= c)."""
 if not p:return []
 out=[]
 for i,u in enumerate(p):
  v=p[(i+1)%len(p)];fu=a*u[0]+b*u[1]-c;fv=a*v[0]+b*v[1]-c
  inside=fu>=0 if lower else fu<=0;other=fv>=0 if lower else fv<=0
  if inside:out.append(u)
  if inside!=other:
   den=fu-fv;yn=u[0]*den+(v[0]-u[0])*fu;vn=u[1]*den+(v[1]-u[1])*fu
   if den<0:den=-den;yn=-yn;vn=-vn
   out.extend(corners(yn,den,vn,den))
 return hull(out)

def affine(p,a,b,c,d,den=1,dy=0,dv=0):
 out=[]
 for y,v in p:
  out.extend(corners(a*y+b*v+dy,den,c*y+d*v+dv,den))
 # A micro-unit margin encloses binary64 arithmetic at bounded game magnitudes.
 return hull([(y+ey,v+ev) for y,v in out for ey,ev in [(-1,-1),(-1,1),(1,-1),(1,1)]])

def set_v(p,v):return affine(p,1,0,0,0,dv=v*SCALE)
def set_y(p,y):return affine(p,0,0,0,1,dy=y*SCALE)
def cap_v(p,minimum):
 lo=clip(p,1,minimum,False);hi=clip(p,1,minimum,True)
 return hull(hi+[(y,minimum) for y,v in lo])

def simplify(p,cap):
 if len(p)<=cap:return p,0
 STATS['vertical_templates']+=1
 result=box(p)
 for a,b in [(8,1),(8,-1),(4,1),(4,-1),(2,1),(2,-1)]:
  values=[a*y+b*v for y,v in p]
  result=lineclip(lineclip(result,a,b,min(values),True),a,b,max(values),False)
 if len(result)>max(64,cap):STATS['vertical_boxes']+=1;result=box(p)
 return result,1

@dataclass(slots=True)
class Region:
 p:list;z:list;g:int;d:int;cy:int;ready:int;direction:int;opened:int;cross:int;anchor:int;trace:bytes=b''
 def discrete(self):return (self.g,self.d,self.cy,self.ready,self.direction,self.opened,self.cross,self.anchor)
 @property
 def y(self):return (min(y for y,v in self.z)/SCALE,max(y for y,v in self.z)/SCALE)
 @property
 def v(self):return (min(v for y,v in self.z)/SCALE,max(v for y,v in self.z)/SCALE)

def seed(s):
 old=old_seed(s);p=s['p'];ys=[math.floor(p['y']*SCALE)-1,math.ceil(p['y']*SCALE)+1];vs=[math.floor(p['vy']*SCALE)-1,math.ceil(p['vy']*SCALE)+1]
 return Region(old.p,hull([(y,v) for y in ys for v in vs]),*old.discrete())

def merge(a,b,vertex_cap):
 p=hull(a.p+b.p);n=0
 if len(p)>vertex_cap:p=box(p);n+=1
 z,m=simplify(hull(a.z+b.z),vertex_cap)
 return replace(a,p=p,z=z),n+m

def key(r,cell):
 if not cell:return r.discrete()
 x0,x1,v0,v1=bounds(r.p);y0,y1,w0,w1=bounds(r.z)
 return r.discrete()+(math.floor((x0+x1)/2/cell),math.floor((v0+v1)/2/(cell*4)),math.floor((y0+y1)/2/(cell/4)),math.floor((w0+w1)/2/(cell*4)))

def crouch_step(p):
 """Enclose targets [-60,60], including retained faster run-up momentum."""
 A=math.ceil(1250*SCALE/120)+1;a=math.floor(1040*SCALE/120)-1;L=60*SCALE
 cuts=sorted(set([-1000*SCALE,-L-a,-L,-L+A,L-A,L,L+a,1000*SCALE]))
 points=[]
 for lo,hi in zip(cuts,cuts[1:]):
  part=clip(clip(p,1,lo,True),1,hi,False)
  for x,v in part:
   vl=min(-L,v+a) if v<-L else max(-L,v-A)
   vh=max(L,v-a) if v>L else min(L,v+A)
   for w in [vl,vh]:points.extend(corners(120*x+w,120,w,1))
 q=hull([(x+e,v) for x,v in points for e in [-1,1]])
 inside=clip(clip(q,0,7*SCALE,True),0,473*SCALE,False)
 return hull(inside+[(7*SCALE,v) for x,v in clip(q,0,7*SCALE,False)]+[(473*SCALE,v) for x,v in clip(q,0,473*SCALE,True)])

def crossing(q):
 if q.opened:yield q;return
 for lo,hi,mode in [(None,335,0),(335,368,q.cross),(368,None,2 if q.cross else 0)]:
  p=q.p
  if lo is not None:p=clip(p,0,lo*SCALE-1,True)
  if hi is not None:p=clip(p,0,hi*SCALE+1,False)
  if p:yield replace(q,p=p,opened=1 if mode==2 else 0,cross=1 if mode==2 else mode)

def press(q,crouched,side,old_roof,loose=False):
 """Exact guard order, with outward overlap at strict boundary surfaces."""
 if q.opened:yield q,False;return
 if loose:
  # Same permissive wall/roof/underside alternatives as the interval pilot.
  yield from ((r,False) for r in crossing(q))
  x0,x1,_,_=bounds(q.p)
  if x1>335 and x0<368 and q.y[1]>484 and q.y[0]<666:
   if side in ['left','any']:
    STATS['press_wall']+=1;yield from ((r,True) for r in crossing(replace(q,p=[(335*SCALE,0)],d=0,direction=0)))
   if side in ['right','any']:
    STATS['press_wall']+=1;yield from ((r,True) for r in crossing(replace(q,p=[(368*SCALE,0)],d=0,direction=0)))
   if old_roof:
    STATS['press_roof']+=1;yield from ((r,True) for r in crossing(replace(q,z=[(666*SCALE,0)])))
   for h in [484,495]:
    under=hull([(h*SCALE,min(0,v)) for y,v in q.z])
    yield from ((r,True) for r in crossing(replace(q,z=under)))
   if crouched and q.g==15:yield from ((r,False) for r in crossing(replace(q,cross=1)))
  return
 # Outside the horizontal near guard is unimpeded.
 for edge,lower in [(335*SCALE+1,False),(368*SCALE-1,True)]:
  p=clip(q.p,0,edge,lower)
  if p:yield from ((r,False) for r in crossing(replace(q,p=p)))
 near=clip(clip(q.p,0,335*SCALE-1,True),0,368*SCALE+1,False)
 if not near:return
 q=replace(q,p=near);threshold=(495 if crouched else 484)*SCALE
 # Noncollision alternatives are restricted to the actual vertical guards.
 for edge,lower in [(threshold+1,False),(666*SCALE-1,True)]:
  z=clip(q.z,0,edge,lower)
  if z:yield from ((r,False) for r in crossing(replace(q,z=z)))
 z=clip(clip(q.z,0,threshold-1,True),0,666*SCALE+1,False)
 if not z:return
 collisions=[z]
 if crouched and q.g==15:
  opening=clip(clip(z,0,578*SCALE-1,True),0,583*SCALE+1,False)
  if opening:
   STATS['press_opening']+=1;yield from ((r,False) for r in crossing(replace(q,z=opening,cross=1)))
  collisions=[clip(z,0,578*SCALE+1,False),clip(z,0,583*SCALE-1,True)]
 for z in collisions:
  if not z:continue
  a=replace(q,z=z)
  if side in ['left','right']:
   STATS['press_wall']+=1;wall=335 if side=='left' else 368
   yield from ((r,True) for r in crossing(replace(a,p=[(wall*SCALE,0)],d=0,direction=0)))
  else:
   if old_roof:
    down=clip(z,1,1,False)
    if down:
     STATS['press_roof']+=1;yield from ((r,True) for r in crossing(replace(a,z=[(666*SCALE,0)])))
    z=clip(z,1,-1,True)
   if z:
    STATS['press_under']+=1
    # vy'=min(0,vy), preserving the y reset and velocity range.
    under=hull([(0,min(0,v)) for y,v in z]);under=set_y(under,495 if crouched else 484)
    yield from ((r,True) for r in crossing(replace(a,z=under)))

def finish(q,last_z,world,token,crouched,side,old_roof,motion,loose):
 for a,collision in press(q,crouched,side,old_roof,loose):
  z=clip(a.z,0,(Y[a.anchor]+54)*SCALE+1,False)
  if not z:continue
  a=replace(a,z=z,trace=a.trace+bytes([token]))
  if a.g>=0:
   yield replace(a,z=set_y(a.z,Y[a.g]));continue
  yield a # Crumble/contact histories remain conservatively optional.
  if a.d:continue
  down=clip(a.z,1,1,False)
  if not down:continue
  old_hi=max(y for y,v in last_z)
  for i in range(min(28,a.anchor+1),-1,-1):
   h=Y[i]*SCALE
   if old_hi<h-1001:continue
   land=clip(down,0,h+1,False)
   if not collision:
    land=lineclip(land,120,-1 if motion else 0,120*(h-1001),True)
   if not land:continue
   left,right,_=world[i]
   p=clip(clip(a.p,0,math.floor((left-1e-9)*SCALE),True),0,math.ceil((right+1e-9)*SCALE),False)
   if p:yield replace(a,p=p,z=[(h,0)],g=i,ready=1,cy=11,anchor=i)

def successors(r,world,target,loose_press=False):
 # previousX is captured before moving-platform carry in the source engine.
 sides=[('any',r.p)] if r.opened else [('left',clip(r.p,0,335*SCALE+1,False)),('middle',clip(clip(r.p,0,335*SCALE-1,True),0,368*SCALE+1,False)),('right',clip(r.p,0,368*SCALE-1,True))]
 for side,original in sides:
  if not original:continue
  carried=original
  if r.g>=0:
   c=world[r.g][2];lo=math.floor((c-1e-9)*SCALE);hi=math.ceil((c+1e-9)*SCALE)
   carried=hull([(x+d,v) for x,v in carried for d in [lo,hi]])
  supports=[]
  if r.g<0:supports.append(replace(r,p=carried,cy=max(0,r.cy-1)))
  else:
   left,right,_=world[r.g];p=clip(clip(carried,0,math.floor((left-1e-9)*SCALE),True),0,math.ceil((right+1e-9)*SCALE),False)
   if p:supports.append(replace(r,p=p,cy=11))
   if r.g in [3,9,13,17,23,26]:
    # Crumble age is still relaxed, so detachment can occur anywhere.
    supports.append(replace(r,p=carried,g=-1,cy=max(0,r.cy-1)))
   else:
    # Steel/moving platforms cannot spontaneously disappear. In particular,
    # this preserves the forced grounded/crouched state inside the press.
    for edge,lower in [(math.ceil((left+1e-9)*SCALE),False),(math.floor((right-1e-9)*SCALE),True)]:
     outside=clip(carried,0,edge,lower)
     if outside:supports.append(replace(r,p=outside,g=-1,cy=max(0,r.cy-1)))
  for s in supports:
   passage=[]
   if not s.opened and s.g==15:
    inside=clip(clip(s.p,0,335*SCALE-1,True),0,368*SCALE+1,False)
    if inside:passage.append((replace(s,p=inside),True))
    for edge,lower in [(335*SCALE+1,False),(368*SCALE-1,True)]:
     outside=clip(s.p,0,edge,lower)
     if outside:passage.append((replace(s,p=outside),False))
   else:passage=[(s,False)]
   for s,in_passage in passage:
    actions=[(s,0,False)] if s.g<0 else [(s,16,True)]+([] if in_passage else [(s,0,False)])
    if not in_passage:
     if s.g>=0 or r.cy>0:actions.append((replace(s,g=-1,cy=0,z=set_v(s.z,285)),4,False))
     if s.g>0:actions.append((replace(s,g=-1,cy=0,z=set_v(affine(s.z,1,0,0,1,dy=-2500000),-85)),4|16,False))
    for a,flags,crouched in actions:
     cuts=[(a,flags)]
     above=clip(a.z,1,110*SCALE-1,True)
     if above:cuts.append((replace(a,z=affine(above,50,0,0,27,50)),flags|8))
     for c,flags in cuts:
      dashes=[(c,flags,crouched)]
      if c.ready and not in_passage:
       for direction in [-1,1]:dashes.append((replace(c,g=-1,cy=0,d=18,ready=0,direction=direction),flags|32,False))
      for d,flags,crouched in dashes:
       # Split previousY >= roof before the vertical movement, retaining correlation.
       roofs=[(d,False)] if d.opened else [(replace(d,z=clip(d.z,0,666*SCALE+1,False)),False),(replace(d,z=clip(d.z,0,666*SCALE-1,True)),True)]
       for d,old_roof in roofs:
        if not d.z:continue
        if d.d:
         left=d.d-1;velocity=d.direction*(312 if left else 125)
         p=step(d.p,-1,-1,2,velocity,world,clamp_world=True);q=replace(d,p=p,d=left,direction=d.direction if left else 0)
         yield from finish(q,d.z,world,(d.direction+1)|flags,False,side,old_roof,False,loose_press)
        else:
         p=crouch_step(d.p) if d.g>=0 and crouched else step(d.p,-1,-1,1 if d.g>=0 else 0,0,world,clamp_world=True)
         if not p:continue
         x0,x1,_,_=bounds(p);axis=-1 if (x0+x1)/2>world[target][0]+3 else 1
         if d.g>=0:
          yield from finish(replace(d,p=p),d.z,world,(axis+1)|flags,crouched,side,old_roof,False,loose_press)
         else:
          gravities=[(d.z,740,0,-420)]
          down=clip(d.z,1,1,False)
          if down:gravities.append((down,1410,16,-490))
          for z,gravity,downflag,limit in gravities:
           z=affine(z,120,0,0,120,120,dv=-gravity*SCALE);z=cap_v(z,limit*SCALE)
           z=affine(z,120,1,0,120,120)
           yield from finish(replace(d,p=p,z=z),d.z,world,(axis+1)|flags|downflag,False,side,old_roof,True,loose_press)

def area_ratio(p):
 if not p:return 0
 area=abs(sum(p[i-1][0]*p[i][1]-p[i][0]*p[i-1][1] for i in range(len(p))))
 xs=[y for y,v in p];vs=[v for y,v in p];rectangle=2*(max(xs)-min(xs))*(max(vs)-min(vs))
 return area/rectangle if rectangle else 1
