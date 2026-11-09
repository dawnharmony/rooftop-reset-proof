"""Integer-lattice outer convex reachability, conditional on a mode schedule.
Coordinates are micro-world-units. Every rounding is OUTWARD, never nearest.
"""
import math,struct,zlib
from fractions import Fraction
SCALE=1_000_000
ROW=struct.Struct('<bbb d') # previous support, landing, 0=air/1=ground/2=dash, dash velocity
def hull(points):
 p=sorted(set(points))
 if len(p)<=2:return p
 def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
 lo=[];hi=[]
 for a in p:
  while len(lo)>1 and cross(lo[-2],lo[-1],a)<=0:lo.pop()
  lo.append(a)
 for a in reversed(p):
  while len(hi)>1 and cross(hi[-2],hi[-1],a)<=0:hi.pop()
  hi.append(a)
 return lo[:-1]+hi[:-1]
def floor(n,d):return n//d
def ceil(n,d):return -((-n)//d)
def corners(xn,xd,vn,vd):
 return [(x,v) for x in {floor(xn,xd),ceil(xn,xd)} for v in {floor(vn,vd),ceil(vn,vd)}]
def clip(poly,axis,edge,lower):
 if not poly:return []
 points=[]
 for i,a in enumerate(poly):
  b=poly[(i+1)%len(poly)];inside=(a[axis]>=edge) if lower else (a[axis]<=edge)
  other=(b[axis]>=edge) if lower else (b[axis]<=edge)
  if inside:points.append(a)
  if inside!=other:
   den=b[axis]-a[axis];num=edge-a[axis]
   xn=a[0]*den+(b[0]-a[0])*num;vn=a[1]*den+(b[1]-a[1])*num
   if den<0:den=-den;xn=-xn;vn=-vn
   points.extend(corners(xn,den,vn,den))
 return hull(points)
def interval(v):
 # 1e-9 covers individual binary64 operation error at these bounded magnitudes.
 return math.floor((v-1e-9)*SCALE),math.ceil((v+1e-9)*SCALE)
def step(poly,ground,landing,mode,velocity,world,clamp_world=False):
 if not poly:return []
 carry=interval(world[ground][2]) if ground>=0 else (0,0)
 if mode==2:
  vl,vh=interval(velocity)
  poly=hull([(x,v) for x,_ in poly for v in (vl,vh)])
 else:
  a=math.ceil((1250 if mode==1 else 670)/120*SCALE)+1
  poly=hull([(x,v+dv) for x,v in poly for dv in (-a,a)])
  poly=clip(clip(poly,1,-127*SCALE-1,True),1,127*SCALE+1,False)
 # Affine movement x'=x+v'/120+carry, plus outward roundoff enclosure.
 points=[]
 for x,v in poly:
  for c in carry:
   points.extend(corners(x*120+v+c*120,120,v,1))
 poly=hull([(x+e,v) for x,v in points for e in (-1,1)])
 # The fixed-mode contract excludes world/press wall collisions. Restricting
 # positions to world bounds retains every trajectory in that contract.
 if clamp_world and poly:
  inside=clip(clip(poly,0,7*SCALE,True),0,473*SCALE,False)
  left=clip(poly,0,7*SCALE,False);right=clip(poly,0,473*SCALE,True)
  poly=hull(inside+[(7*SCALE,v) for x,v in left]+[(473*SCALE,v) for x,v in right])
 else:poly=clip(clip(poly,0,7*SCALE,True),0,473*SCALE,False)
 if landing>=0:
  left,right,_=world[landing]
  poly=clip(clip(poly,0,interval(left)[0],True),0,interval(right)[1],False)
 return poly
def contains(poly,p):
 if not poly:return False
 if len(poly)==1:return p==poly[0]
 if len(poly)==2:
  a,b=poly;return (b[0]-a[0])*(p[1]-a[1])==(b[1]-a[1])*(p[0]-a[0]) and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1])
 return all((poly[(i+1)%len(poly)][0]-a[0])*(p[1]-a[1])-(poly[(i+1)%len(poly)][1]-a[1])*(p[0]-a[0])>=0 for i,a in enumerate(poly))
def run(rows,start_tick,world,initial,max_vertices=128,oracle=None):
 poly=initial;contacts=[];peak=len(poly);coarsened=0;count=0
 for i,(g,land,mode,v) in enumerate(ROW.iter_unpack(rows)):
  poly=step(poly,g,land,mode,v,world[start_tick+i+1]);count+=1
  if not poly:break
  peak=max(peak,len(poly))
  if len(poly)>max_vertices:
   xs=[p[0] for p in poly];vs=[p[1] for p in poly]
   poly=[(min(xs),min(vs)),(max(xs),min(vs)),(max(xs),max(vs)),(min(xs),max(vs))];poly=hull(poly);coarsened+=1
  if oracle:
   x,vx=oracle[i]
   # The rounded point lies within one lattice unit of the actual float.
   assert contains(poly,(Fraction(x)*SCALE,Fraction(vx)*SCALE)),('oracle outside',i,x,vx)
  if land>=0:contacts.append((start_tick+i+1,land,poly.copy()))
 raw=bytearray()
 for tick,g,p in contacts:
  raw.extend(struct.pack('<HBB',tick,g,len(p)))
  for x,v in p:raw.extend(struct.pack('<ii',x,v))
 return {'nonempty':bool(poly),'steps':count,'peak_vertices':peak,'coarsenings':coarsened,'contacts':len(contacts),'vertices_stored':sum(len(p) for _,_,p in contacts),'raw_bytes':len(raw),'blob':zlib.compress(raw),'end_tick':start_tick+count,'min_x':min((x for x,v in poly),default=0)/SCALE,'max_x':max((x for x,v in poly),default=0)/SCALE}
