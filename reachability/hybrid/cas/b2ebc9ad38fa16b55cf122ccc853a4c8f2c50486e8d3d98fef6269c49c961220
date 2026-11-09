"""Bounded memoization of pure, exact integer geometry; no domain changes."""
from functools import lru_cache

def install():
    import fast_geometry as f
    import kernel, correlated_kernel, boundary_kernel, adaptive_kernel
    original_hull,original_clip=f.hull,f.clip
    @lru_cache(maxsize=16384)
    def cached_hull(points):return tuple(original_hull(points))
    @lru_cache(maxsize=32768)
    def cached_clip(points,axis,edge,lower):return tuple(original_clip(list(points),axis,edge,lower))
    def hull(points):return list(cached_hull(tuple(points)))
    def clip(points,axis,edge,lower):return list(cached_clip(tuple(points),axis,edge,lower))
    # Copies at the boundary prevent callers from mutating cached results.
    for m in [kernel,correlated_kernel,boundary_kernel,adaptive_kernel]:m.hull=hull;m.clip=clip
    return cached_hull,cached_clip
