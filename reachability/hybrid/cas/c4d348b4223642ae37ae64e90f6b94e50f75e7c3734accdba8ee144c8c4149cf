"""Exact integer replacements. No rounding rules or reachable sets change."""
def hull(points):
 p=sorted(set(points))
 if len(p)<=2:return p
 lo=[];hi=[]
 for a in p:
  while len(lo)>1:
   u,v=lo[-2],lo[-1]
   if (v[0]-u[0])*(a[1]-u[1])-(v[1]-u[1])*(a[0]-u[0])>0:break
   lo.pop()
  lo.append(a)
 for a in reversed(p):
  while len(hi)>1:
   u,v=hi[-2],hi[-1]
   if (v[0]-u[0])*(a[1]-u[1])-(v[1]-u[1])*(a[0]-u[0])>0:break
   hi.pop()
  hi.append(a)
 return lo[:-1]+hi[:-1]

def canonical(p):
 n=len(p)
 if n<2:return True
 if p[0]!=min(p):return False
 if n==2:return p[0]<p[1]
 for i,u in enumerate(p):
  v=p[(i+1)%n];w=p[(i+2)%n]
  if (v[0]-u[0])*(w[1]-v[1])-(v[1]-u[1])*(w[0]-v[0])<=0:return False
 return True

def clip(p,axis,edge,lower):
 if not p:return []
 flags=[a[axis]>=edge if lower else a[axis]<=edge for a in p]
 if all(flags):return p if canonical(p) else hull(p)
 if not any(flags):return []
 out=[];other=1-axis
 for i,a in enumerate(p):
  b=p[(i+1)%len(p)]
  if flags[i]:out.append(a)
  if flags[i]!=flags[(i+1)%len(p)]:
   den=b[axis]-a[axis];num=a[other]*den+(b[other]-a[other])*(edge-a[axis])
   if den<0:den=-den;num=-num
   lo=num//den;hi=-((-num)//den)
   out.append((edge,lo) if axis==0 else (lo,edge))
   if hi!=lo:out.append((edge,hi) if axis==0 else (hi,edge))
 return hull(out)

def install():
 import kernel,correlated_kernel,boundary_kernel,adaptive_kernel
 for m in [kernel,correlated_kernel,boundary_kernel,adaptive_kernel]:
  m.hull=hull;m.clip=clip
 from dataclasses import replace
 def merge(a,b,vertex_cap):
  p=a.p if a.p==b.p else hull(a.p+b.p);n=0
  if len(p)>vertex_cap:p=correlated_kernel.box(p);n+=1
  if a.z==b.z and len(a.z)<=vertex_cap:z=a.z;count=0
  else:z,count=correlated_kernel.simplify(hull(a.z+b.z),vertex_cap)
  return replace(a,p=p,z=z),n+count
 correlated_kernel.merge=merge
