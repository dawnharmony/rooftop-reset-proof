import argparse
from pathlib import Path
import timed_hybrid_run
from geometry_cache import install
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--seconds',type=float,default=300);p.add_argument('--cap',type=int,default=20000);p.add_argument('--limit',type=int,default=1646);p.add_argument('--resume',action='store_true');p.add_argument('--clear-global-pause',action='store_true');p.add_argument('--import-frontier',type=Path);p.add_argument('--positive-control',action='store_true');p.add_argument('--cell',type=float,default=0);p.add_argument('--monotone',action='store_true');p.add_argument('--refine-from',type=int,default=9);p.add_argument('--refine-through',type=int,default=16);p.add_argument('--timing-bin',type=int,default=4);p.add_argument('--contact-screen',type=Path);p.add_argument('--air-deadline',action='store_true');p.add_argument('--gate-partition',action='store_true');p.add_argument('--contact-report',action='store_true');p.add_argument('--saw-partition',action='store_true');a=p.parse_args()
    assert a.timing_bin>=1
    install();timed_hybrid_run.run(a)
