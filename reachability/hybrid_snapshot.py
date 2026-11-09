"""Content-addressed, immutable evidence for evolving proof experiments."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;P=HERE/'pilot'
def snapshot_generic(folder,paths,digest):
    cas=HERE/'hybrid/cas';cas.mkdir(exist_ok=True);manifest=[]
    for source in dict.fromkeys(paths):
        data=source.read_bytes();sha=hashlib.sha256(data).hexdigest();dest=cas/sha
        if dest.exists():assert hashlib.sha256(dest.read_bytes()).hexdigest()==sha
        else:dest.write_bytes(data)
        manifest.append({'source':str(source.resolve()),'sha256':sha,'bytes':len(data),'cas':str(dest.resolve())})
    (folder/'source-manifest.json').write_text(json.dumps({'modelSHA256':digest,'files':manifest},indent=2))
def snapshot(folder,original=False):
    folder=Path(folder);status=json.loads((folder/'status.json').read_text())
    if original:
        sources=['hybrid_run.py','correlated_kernel.py','branch_kernel.py','kernel.py','fast_geometry.py']
        ordered=[P/n for n in sources]+[HERE/'hybrid/bounds.json']
        digest=hashlib.sha256(b''.join(p.read_bytes() for p in ordered)).hexdigest()
    else:
        sources=['hybrid_refined_run.py','hybrid_time_potential.py','correlated_kernel.py','branch_kernel.py','kernel.py','fast_geometry.py']
        ordered=[P/n for n in sources]+[HERE/n for n in ['hybrid_interval_bounds.py','hybrid_gate_bounds.py','hybrid_bounds.py','hybrid/gate-bounds.json','hybrid/phase-bounds.json','constants.json']]
        # Existing coarse/fine experiments used this three-field config.
        cell=16.0 if folder.name=='fresh-01' else 0.0
        config=json.dumps(status.get('modelDigestConfig',[status['limitResetTick'],cell,True])).encode()
        digest=hashlib.sha256(b''.join(p.read_bytes() for p in ordered)+config).hexdigest()
    assert digest==status['sourceSHA256'],('Cannot reconstruct recorded source version',folder,digest,status['sourceSHA256'])
    extra=[ROOT/'engine.js',ROOT/'arcade.js',P/'run/world.bin',P/'geometry_cache.py',HERE/'hybrid/backtrack-check.json']
    cas=HERE/'hybrid/cas';cas.mkdir(exist_ok=True);manifest=[]
    for source in dict.fromkeys(ordered+extra):
        data=source.read_bytes();sha=hashlib.sha256(data).hexdigest();dest=cas/sha
        if dest.exists():assert hashlib.sha256(dest.read_bytes()).hexdigest()==sha
        else:dest.write_bytes(data)
        manifest.append({'source':str(source.resolve()),'sha256':sha,'bytes':len(data),'cas':str(dest.resolve())})
    (folder/'source-manifest.json').write_text(json.dumps({'modelSHA256':digest,'files':manifest},indent=2))
    print(json.dumps({'dataset':str(folder),'sourceVersionReconstructed':True,'files':len(manifest)}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--original',action='store_true');a=p.parse_args();snapshot(a.folder,a.original)
