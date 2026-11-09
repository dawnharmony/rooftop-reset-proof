"""Recheck the proof artifacts and the enlarged decisive transfer domain."""

import hashlib
import json
from pathlib import Path
import random
import sqlite3
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'hybrid'
sys.path.insert(0, str(ROOT / 'pilot'))

from hybrid_bounds import ceildiv, vertical_minima
from hybrid_backtrack_check import retreat_suffixes
from hybrid_interval_bounds import T, propagate
from hybrid_saw_transfer import transfer
from hybrid_time_potential import TimePotential
from resources import Job, available


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_manifest(folder, engine_hash):
    manifest = read(folder / 'source-manifest.json')
    status = read(folder / 'status.json')
    assert manifest['modelSHA256'] == status['sourceSHA256']
    files = {}
    for entry in manifest['files']:
        name = Path(entry['source']).name
        digest = entry['sha256']
        path = DATA / 'cas' / digest
        assert sha(path) == digest and path.stat().st_size == entry['bytes']
        files[name] = digest
    assert files['engine.js'] == engine_hash
    return status, files


def check_lineage(deadline, engine_hash):
    momentum = 'momentum-1646-air-v8' if deadline == 1646 else 'momentum-1647-air-control'
    names = [momentum, f'contact-entry-{deadline}', f'contact-fine-{deadline}',
             f'contact-projected-{deadline}', f'contact-audit-macro-{deadline}', f'contact-audit-fixed-{deadline}']
    files = []
    parent = None
    for name in names:
        folder = DATA / name
        report = read(folder / 'result.json')
        digest = sha(folder / 'frontiers.json')
        assert report['deadline'] == deadline and report['engineSHA256'] == engine_hash
        if parent is not None:
            assert report['sourceSHA256'] == parent
        files.append({'name': name, 'profileSHA256': digest})
        parent = digest
    rerun = DATA / f'momentum-audit-{deadline}'
    assert sha(rerun / 'frontiers.json') == files[0]['profileSHA256']
    status, _ = check_manifest(rerun, engine_hash)
    assert status['state'] == 'possible'

    run = DATA / ('contact-report-01' if deadline == 1646 else 'contact-report-control')
    status, manifest = check_manifest(run, engine_hash)
    assert status['limitResetTick'] == deadline
    assert manifest['frontiers.json'] == files[2]['profileSHA256']
    assert manifest['constants.json'] == sha(ROOT / 'constants.json')
    projection = read(DATA / names[3] / 'result.json')
    archive = run / 'frontier.sqlite'
    assert projection['projectionSHA256'] == sha(archive)
    with sqlite3.connect(archive.as_uri() + '?mode=ro', uri=True) as db:
        checkpoint = db.execute('SELECT depth,sha FROM checkpoint WHERE id=0').fetchone()
        assert checkpoint == (status['depth'], status['sourceSHA256'])
        depths = [tick for tick, in db.execute('SELECT depth FROM metrics ORDER BY depth')]
        assert depths == list(range(1, status['depth'] + 1))
    assert status['state'] == ('abstract-counterexample' if deadline == 1646 else 'positive-control-complete')
    assert status['depth'] > 945
    return files, status['depth']


def check_phase(constants, engine_hash):
    gate_path = DATA / 'gate-bounds.json'
    phase_path = DATA / 'phase-bounds.json'
    gate = read(gate_path)
    phase = read(phase_path)
    retreat = read(DATA / 'backtrack-check.json')
    assert gate['engineSHA256'] == phase['metadata']['engineSHA256'] == engine_hash
    combined = hashlib.sha256(gate_path.read_bytes() + phase_path.read_bytes()).hexdigest()
    assert retreat['boundsSHA256'] == combined
    ledges = constants['ledges']
    gaps = [b['y'] - a['y'] for a, b in zip(ledges, ledges[1:])]
    minima = vertical_minima(set(gaps) | {0})
    assert minima[0] == 23
    assert [minima[gap] for gap in gaps] == gate['opened']['minimum'][1:29]
    assert min(a + b for a, b in zip(gaps, gaps[1:])) >= 68

    world = (ROOT / 'pilot/run/world.bin').read_bytes()
    for tick, frame in enumerate(constants['frames'][:1647]):
        for support, row in enumerate(frame['ledges']):
            offset = (tick * 29 + support) * 24
            assert struct.unpack_from('<ddd', world, offset) == (row['left'], row['right'], row['carry'])

    graph = gate['closed']
    rng = random.Random(1646)
    for node in range(1, 32):
        source = phase['forward'][node - 1]
        domain = phase['domains'][node]
        minimum = graph['minimum'][node]
        granular = graph['granular'][node]
        is_gate = node == graph['gate']
        calculated = propagate(source, domain, minimum, granular, is_gate)
        assert calculated == phase['forward'][node]
        for tick in rng.sample(range(T + 1), 24):
            ranges = []
            if is_gate:
                # Compare to ANY earlier entry, not just the implementation's
                # single shifted sample. Its static entry domain permits wait.
                expected = domain[tick] if tick >= 61 and any(source[:tick - 60]) else None
            else:
                for s in range(tick - minimum + 1):
                    if source[s] is None:
                        continue
                    elapsed = tick - s
                    if granular:
                        motion = 147400002 * elapsed - 20400001 * minimum
                        motion += (3143000000 - 17 * 20400001) * ((elapsed - minimum) // 18)
                    else:
                        motion = 332400001 * elapsed - (332400001 - 127000001) * minimum
                    lo, hi = source[s]
                    ranges.append((lo + (-motion // 120) - 170001,
                                   hi + ceildiv(motion, 120) + 170001))
                expected = None
                if ranges:
                    lo = max(domain[tick][0], min(a for a, _ in ranges))
                    hi = min(domain[tick][1], max(b for _, b in ranges))
                    if lo <= hi:
                        expected = [lo, hi]
            assert calculated[tick] == expected, (node, tick)

    p = TimePotential(1646)
    back = retreat_suffixes(p, constants)
    tested = 0
    for high in range(1, 29):
        first = p.first[high if high <= 15 else high + 2]
        kind = 'closed' if high <= 15 else 'opened'
        for low in range(high):
            assert all(back[kind][low][1646 - t] is None for t in range(first, 1647))
            tested += 1
    for low in range(15):
        assert all(back['opened'][low][1646 - t] is None for t in range(p.first[17], 1647))
    assert retreat['pairsExcludedEvenWithFreeInstantRetreat'] == tested == 406
    assert retreat['allBackwardLandingsExcluded']
    ledge_zero_minima = {name: next(t for t, row in enumerate(profiles[0]) if row is not None)
                         for name, profiles in back.items()}
    return tested, ledge_zero_minima


def replay_engine():
    code = r"""
const fs = require('fs'), assert = require('node:assert/strict'), engine = require('./engine.js');
const data = JSON.parse(fs.readFileSync('reachability/constants.json'));
let time = 0, grace = .25;
for (const [tick, frame] of data.frames.entries()) {
    if (tick) { time += engine.step; grace = Math.max(0, grace - engine.step); }
    assert.equal(frame.t, time);
    assert.equal(frame.grace, grace);
    for (const [index, ledge] of engine.ledges.entries()) {
        const x = engine.ledgeX(ledge, time);
        const actual = frame.ledges[index];
        assert.equal(actual.left, x - 3);
        assert.equal(actual.right, x + ledge.w + 3);
        assert.equal(actual.carry, x - engine.ledgeX(ledge, time - engine.step));
    }
    assert.deepEqual(frame.saws, engine.saws.map(saw => engine.sawAt(saw, time)));
    assert.deepEqual(frame.bolts, engine.emitters.map(emitter => engine.boltAt(emitter, time)));
    assert.deepEqual(frame.vents, engine.vents.map(vent => engine.ventAt(vent, time)));
}
const run = engine.newRun('nightmare');
const input = JSON.parse(fs.readFileSync('records/13.725/inputs.json')).path.flat();
assert.equal(input.length, 1647);
assert.equal(input.at(-1).interact, true);
for (const [tick, action] of input.entries()) {
    assert.equal(engine.approachingButton(run), tick === 1646);
    engine.update(run, action);
    assert.equal(run.deaths, 0);
    assert.equal(run.won, tick === 1646);
}
console.log(JSON.stringify({physicsFrames: data.frames.length, recordTicks: input.length, resetPressed: true}));
"""
    result = subprocess.run(['node', '-e', code], cwd=ROOT.parent, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main():
    assert available() >= 8 * 2**30
    job = Job(384)
    engine_hash = sha(ROOT.parent / 'engine.js')
    constants = read(ROOT / 'constants.json')
    assert constants['engineSHA256'] == engine_hash and constants['dt'] == 1 / 120
    original = replay_engine()
    retreat_pairs, ledge_zero_minima = check_phase(constants, engine_hash)
    negative, negative_depth = check_lineage(1646, engine_hash)
    positive, positive_depth = check_lineage(1647, engine_hash)
    negative_profile = read(DATA / negative[-2]['name'] / 'frontiers.json')
    assert {t for t, *_ in negative_profile['layers'][11]} == {617}
    assert {t for t, *_ in negative_profile['layers'][12]} == {672}
    assert all(158000000 <= lo <= hi <= 168000000
               for _, _, parts in negative_profile['layers'][11] for lo, hi in parts)

    bins = [None] * 14
    bins[11] = bins[12] = [(-127000001, 127000001)]
    start = {(617, 0): [(158000000, 168000000)]}
    end = {(672, 0): [(34999999, 83000001)]}
    surviving, local = transfer(constants, bins, 11, start, end, 37, lambda: None)
    assert not surviving and local == {'tested': 73, 'survived': 0, 'fallback': 0}
    empty = read(DATA / negative[-1]['name'] / 'frontiers.json')
    assert all(not layer for layer in empty['layers'])
    control = read(DATA / positive[-1]['name'] / 'result.json')
    assert control['earliestPossibleReset'] == 1647 and control['recordContactsAdmitted'] == 32
    report = {'engineSHA256': engine_hash, 'targetResetTick': 1646, 'retreatPairs': retreat_pairs,
              'fullLedgeZeroSuffixTicks': ledge_zero_minima,
              'originalEngineReplay': original,
              'verifiedWorldFrames': 1647, 'projectionDepths': [negative_depth, positive_depth],
              'independentPhaseSamples': 31 * 24, 'widenedSawTransfer': local,
              'negativeLineage': negative, 'positiveLineage': positive,
              'firstAdmittedControlReset': 1647, 'peakJobCommitMiB': job.peak() / 2**20}
    (DATA / 'reset-1646-audit.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
