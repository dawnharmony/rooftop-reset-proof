"""Can even an instantaneous free retreat fit the global deadline?

Any real backward landing h->j<h is relaxed to a zero-time teleport to ANY
point of support j after first reaching h. If no prefix/suffix pair survives,
that specific backward landing is impossible within the target budget.
"""
import json,sys,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'pilot'))
from hybrid_time_potential import TimePotential

def main():
    p=TimePotential(1646);possible=[];excluded=[]
    for h in range(1,29):
        prefix=h if h<=15 else h+2
        for j in range(h):
            name='closed' if h<=15 else 'opened'
            suffix=j if name=='opened' or j<=15 else j+2
            first=next(t for t,part in enumerate(p.forward[prefix]) if part is not None)
            times=[t for t in range(first,1647) if p.back[name][suffix][1646-t] is not None]
            row={'highest':h,'retreatTo':j,'firstPossibleInstantRetreatTick':times[0] if times else None}
            (possible if times else excluded).append(row)
    # Opening then retreating before first16 has paid the mandatory gate.
    gate_possible=[]
    for j in range(15):
        first=next(t for t,part in enumerate(p.forward[17]) if part is not None)
        times=[t for t in range(first,1647) if p.back['opened'][j][1646-t] is not None]
        if times:gate_possible.append({'highest':15,'retreatTo':j,'opened':True,'first':times[0]})
    digest=hashlib.sha256((HERE/'hybrid/gate-bounds.json').read_bytes()+(HERE/'hybrid/phase-bounds.json').read_bytes()).hexdigest()
    result={'deadline':1646,'boundsSHA256':digest,'pairsExcludedEvenWithFreeInstantRetreat':len(excluded),'possiblePairs':possible,'opened15PossiblePairs':gate_possible,'allBackwardLandingsExcluded':not possible and not gate_possible,'scope':'Necessary prefix/suffix interval overlap, not a concrete route.'}
    (HERE/'hybrid/backtrack-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
