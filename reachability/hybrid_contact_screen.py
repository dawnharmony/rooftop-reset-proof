"""Bidirectional support on saved first-contact time/velocity cells.

Each ordinary edge bounds directional displacement. Special press edges use
the coarser displacement envelope except for the crawl, whose upper position
after a given duration follows the crouch recurrence. Keep separate safe x
intervals when hazards cut a hole in a contact domain.
"""

import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
from functools import lru_cache

from hybrid_momentum_bounds import AIR, GROUND, NORMAL, V125, crawl_ticks, normal_only, travel, wall_range, U
from hybrid_bounds import vertical_minima
from resources import Job, available


HERE = Path(__file__).resolve().parent
PROJECTED_NODES = (12, 13, 14, 15, 16, 17, 18)


def union(intervals):
    result = []
    for left, right in sorted(intervals):
        if result and left <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], right))
        else:
            result.append((left, right))
    return tuple(result)


def intersection(intervals, left, right):
    return [(max(a, left), min(b, right)) for a, b in intervals if a <= right and left <= b]


def contact_hazards(frame, ledges, support, spikes):
    if frame['grace'] > 0:
        return []
    y = ledges[support]['y']
    lethal = []
    for i, edge, width in spikes:
        if ledges[i]['y'] - 13 < y < ledges[i]['y'] + 6:
            x = frame['ledges'][i]['x'] + (ledges[i]['w'] - width if edge == 'right' else 0)
            lethal.append((x - 2, x + width + 2))
    for vent in frame['vents']:
        if vent['active'] and vent['y'] - 11 < y < vent['y'] + 24:
            lethal.append((vent['x'] - 3, vent['x'] + 9))
    for bolt in frame['bolts']:
        # The crouching hitbox is contained in the standing hitbox.
        if bolt['active'] and y - 1 < bolt['y'] < y + 17:
            lethal.append((bolt['x'] - 7, bolt['x'] + 7))
    for saw in frame['saws']:
        dy = max(y + 1 - saw['y'], 0, saw['y'] - (y + 11))
        if dy * dy < 30:
            reach = 3 + math.sqrt(30 - dy * dy)
            lethal.append((saw['x'] - reach, saw['x'] + reach))
    # Shrink the open lethal intervals by an outward allowance on each side.
    return [(math.ceil(a * U) + 2, math.floor(b * U) - 2) for a, b in lethal]


def subtract(intervals, left, right):
    if left >= right:
        return intervals
    return tuple(piece for a, b in intervals for piece in
                 intersection(((a, b),), a, left) + intersection(((a, b),), right, b))


def minimum_crawl_x(ticks, velocity):
    left, right = 335 * U, 368 * U
    while left < right:
        middle = (left + right) // 2
        if crawl_ticks(middle, velocity) <= ticks:
            right = middle
        else:
            left = middle + 1
    return left


@lru_cache(maxsize=100000)
def one_dash_displacement(steps, minimum, start_v, end_v):
    """Directional motion sum before dividing by 120, with exactly one dash."""
    normal = steps - 18
    extra = normal - minimum
    assert extra >= 0
    # Prefix before the dash and suffix after it use distinct normal steps.
    # Give the prefix its most favorable allocation of grounded acceleration.
    prefix, suffix = [0], [0]
    for n in range(1, normal + 1):
        ground = min(n, extra)
        cap = start_v + ground * GROUND + (n - ground) * AIR
        prefix.append(prefix[-1] + max(0, min(NORMAL, cap)))
        air = min(n - 1, minimum)
        cap = end_v + air * AIR + (n - 1 - air) * GROUND
        suffix.append(suffix[-1] + max(0, min(NORMAL, cap)))
    # An opposite dash cannot add positive directional motion, even if a
    # world clamp absorbs all of it. A forward dash ends at speed 125.
    best = NORMAL * normal
    for before in range(normal + 1):
        after = normal - before
        air = min(after, minimum)
        if end_v + air * AIR + (after - air) * GROUND >= V125 - 2:
            best = max(best, prefix[before] + 5429 * U + 120 + suffix[after])
    return best


def read_projection(folder, source_hash, deadline):
    status = json.loads((folder / 'status.json').read_text())
    assert status['state'] in ('abstract-counterexample', 'positive-control-complete', 'excluded-in-outer-model')
    assert status['limitResetTick'] == deadline
    covered_nodes = set(status.get('projectedNodes', (12, 13, 14, 15, 17, 18)))
    assert covered_nodes <= set(PROJECTED_NODES)
    manifest = json.loads((folder / 'source-manifest.json').read_text())
    assert manifest['modelSHA256'] == status['sourceSHA256']
    assert any(Path(file['source']).name == 'frontiers.json' and file['sha256'] == source_hash
               for file in manifest['files'])
    database = folder / 'frontier.sqlite'
    contacts = {}
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        depth, digest = db.execute('SELECT depth,sha FROM checkpoint WHERE id=0').fetchone()
        assert depth == status['depth'] and digest == status['sourceSHA256']
        count = 0
        for tick, body in db.execute('SELECT depth,data FROM metrics ORDER BY depth'):
            count += 1
            row = json.loads(body)
            assert count == tick == row['depth']
            for node, cells in row['firstContactCells'].items():
                assert int(node) in covered_nodes
                contacts.update(((int(node), tick, int(index)), tuple(bounds)) for index, bounds in cells.items())
        assert count == depth
    with database.open('rb') as handle:
        archive_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
    return contacts, depth, covered_nodes, archive_hash


def run(source, out, deadline, sweeps, narrow_recharge=False, departure_cap=False, signed_carry=False,
        dash_slot=False, press_run_up=False, gate_velocity_step=None, contact_report=None, press_macro=False,
        saw_transfer=False):
    start = time.monotonic()
    constants = json.loads((HERE / 'constants.json').read_text())
    engine_hash = hashlib.sha256((HERE.parent / 'engine.js').read_bytes()).hexdigest()
    assert constants['engineSHA256'] == engine_hash
    # Static spike geometry for the pinned engine. Moving hazards are exported
    # per update by the original engine in constants.json.
    assert engine_hash == '0a427d28c8ab60e7ee1dc69f3caa6837cc542bec34a757f4394c7e0e079bd031'
    spikes = [(4, 'right', 9), (12, 'left', 9), (16, 'right', 9), (19, 'left', 8), (22, 'right', 7)]
    profile = json.loads(source.read_text())
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    projection_hash = None
    if contact_report is not None:
        assert gate_velocity_step is not None, 'Projection requires the same screened input cells'
        projected, through, covered_nodes, projection_hash = read_projection(contact_report, source_hash, deadline)
    gates = json.loads((HERE / 'hybrid/gate-bounds.json').read_text())
    gate = gates['closed']
    params = json.loads((HERE / 'hybrid/monotone-bounds.json').read_text())['parameters']
    assert len(profile['layers']) == len(params) == 32
    bins = profile['bins']
    if gate_velocity_step is not None:
        # A previously screened cell encloses every state in each of its
        # closed velocity subintervals. Keep the full x intervals in each.
        assert gate_velocity_step > 0 and isinstance(profile['layers'][0], list)
        prior = json.loads(source.with_name('result.json').read_text())
        assert prior['deadline'] == deadline and prior['engineSHA256'] == engine_hash
        step = gate_velocity_step * U
        subdivisions = []
        new_bins = []
        for node, old_bins in enumerate(bins):
            indices = []
            node_bins = []
            for vlo, vhi in old_bins:
                first = len(node_bins)
                if node in (14, 15, 16, 18) and vhi - vlo > step:
                    node_bins.extend((v, min(v + step, vhi)) for v in range(vlo, vhi, step))
                else:
                    node_bins.append((vlo, vhi))
                indices.append(range(first, len(node_bins)))
            subdivisions.append(indices)
            new_bins.append(node_bins)
        bins = new_bins
    cancellation = {row['target']: row['bestCanceledTicks'] for row in gates['cancellationDominance']}
    recharge_air = vertical_minima([0])[0] if narrow_recharge else None
    narrow = set()
    run_up_wall_range = lru_cache(maxsize=4096)(wall_range)

    def narrow_support(support, carry):
        ledge = constants['ledges'][support]
        left = ledge['x'] - ledge['travel'] - 3
        right = ledge['x'] + ledge['travel'] + ledge['w'] + 3
        span = 120 * ((ledge['w'] + 6) * U + 2_120_000) + 19 * carry
        return left > 9 and right < 471 and span < 5429 * U - 120

    if narrow_recharge:
        for node in [*range(1, 15), *range(19, 31)]:
            previous = node - 1 if node <= 14 else node - 3
            carry = params[node]['carry']
            # Before activation, a retained ground flag may overshoot by an
            # ordinary move. Grant another ordinary move after dash completion
            # and nineteen steps of ledge drift. A world clamp is too far from
            # these supports for a same-height return on the next update.
            if narrow_support(previous, carry):
                narrow.add(node)

    @lru_cache(maxsize=4096)
    def dash_limit(node, duration):
        if node not in narrow or duration >= cancellation.get(node, math.inf):
            return None
        extra = duration - gate['minimum'][node]
        # Each completed dash except the last needs its own recharge. A
        # same-height return on a narrow ledge requires a jump and a separate
        # block of non-dash updates before the mandatory ascent.
        return max(0, (extra + recharge_air) // (18 + recharge_air))

    @lru_cache(maxsize=8192)
    def departure_extent(node, start, last):
        support = node - 1 if node <= 14 else node - 3
        frames = constants['frames'][start:last + 1]
        left = min(frame['ledges'][support]['left'] for frame in frames)
        right = max(frame['ledges'][support]['right'] for frame in frames)
        padding = 1_060_000 + params[node]['departure']
        return math.floor(left * U) - padding, math.ceil(right * U) + padding

    @lru_cache(maxsize=8192)
    def directional_carry(node, start, end):
        p = params[node]
        if not signed_carry or not p['carry'] or not (1 <= node <= 12 or 19 <= node <= 30):
            return p['carry'], p['departure'], p['carry'], p['departure']
        support = node - 1 if node <= 12 else node - 3
        # Only the current support can contribute before first contact with
        # the target. Include the whole window and grant zero when moving
        # carry in this direction would always be adverse.
        values = [frame['ledges'][support]['carry'] for frame in constants['frames'][start + 1:end + 1]]
        right = max(0, math.ceil(max(values) * 120 * U) + 2)
        left = max(0, math.ceil(-min(values) * 120 * U) + 2)
        return right, -(-right // 120) + 1, left, -(-left // 120) + 1

    def movement(node, duration, minimum, carry, departure, granular, start_v, end_v, cap):
        upper = travel(duration, minimum, carry, departure, granular, start_v, end_v, cap)
        count = (duration - minimum) // 18
        if cap is not None:
            count = min(count, cap)
        # Avoid the press and all wall-cancellation families. In these
        # ordinary transfers a world clamp changes x without changing vx.
        if not dash_slot or not granular or count != 1 or not (1 <= node <= 12 or 19 <= node <= 30):
            return upper
        no_dash = travel(duration, minimum, carry, departure, granular, start_v, end_v, 0)
        raw = one_dash_displacement(duration, minimum, start_v, end_v)
        raw += carry * (duration - 18 - minimum + 1)
        return min(upper, max(no_dash, -(-raw // 120) + departure))

    def press_support(src, dst, duration, start_v, end_v, backwards):
        if duration == 0:
            # The press guard runs before the landing loop. First entry
            # therefore needs an update after first landing on ledge 15.
            return []
        a, b = start_v
        vlo, vhi = end_v
        # At first entry the last update is grounded and crouched. A vx
        # above the crouch target of 60 must have decayed from a still
        # higher vx on the preceding update.
        before = duration - 1
        before_lo = vlo + (1040 * U // 120 - 2) if vlo > 60 * U + 1 else vlo - GROUND
        before_hi = min(NORMAL, vhi + GROUND)
        right = left = None
        acceleration = before * GROUND
        if before_lo <= before_hi and before_lo <= b + acceleration and a - acceleration <= before_hi:
            right = normal_only(before, b, before_hi) + -(-vhi // 120) + 1
            left = normal_only(before, -a, -before_lo) + - (vlo // 120) + 1
        if duration >= 41:
            # A complete non-cancelled dash can also recontact the ledge.
            right = travel(duration, 0, 0, 1, True, b, vhi)
            left = travel(duration, 0, 0, 1, True, -a, -vlo)
        coarse = travel(duration, 0, 0, 1, False, b, vhi)
        pieces = []
        for lo, hi in src:
            if right is not None:
                if backwards:
                    pieces.extend(p for x, y in dst for p in intersection(((lo, hi),), x - right, y + left))
                else:
                    pieces.extend(intersection(dst, lo - left, hi + right))
            # A wall hit resets x=335 and vx=0. Grant immediate dash speed
            # up to the wall, then the maximum grounded acceleration after
            # it, even for a path that actually hit it in midair.
            first_wall = max(0, -(-((335 * U - hi - 1) * 120) // 312000001))
            wall = run_up_wall_range(before - first_wall, before_lo, before_hi, True)
            if wall:
                before_left, before_right = wall
                before_right = min(before_right, 335 * U + 1)
                if before_left > before_right:
                    continue
                overlaps = intersection(dst, before_left + vlo // 120 - 1, before_right + -(-vhi // 120) + 1)
                if overlaps:
                    if backwards:
                        pieces.extend(p for x, y in overlaps for p in intersection(((lo, hi),), x - coarse, y + coarse))
                    else:
                        pieces.extend(intersection(overlaps, lo - coarse, hi + coarse))
        return pieces
    @lru_cache(maxsize=4096)
    def hazards_at(tick, support):
        return contact_hazards(constants['frames'][tick], constants['ledges'], support, spikes)

    layers = []
    for node, rows in enumerate(profile['layers']):
        support = node if node <= 15 else 15 if node <= 17 else min(node - 2, 28)
        layer = {}
        if gate_velocity_step is None:
            cells = ((int(tick), index, (tuple(part),)) for tick, row in rows.items()
                     for index, part in enumerate(row) if part is not None)
        else:
            refined_cells = []
            for tick, index, parts in rows:
                if contact_report is not None and node in covered_nodes and tick <= through:
                    extent = projected.get((node, tick, index))
                    parts = intersection(parts, extent[0] - 1, extent[1] + 1) if extent else ()
                if parts:
                    refined_cells.extend((tick, refined, tuple(map(tuple, parts)))
                                         for refined in subdivisions[node][index])
            cells = refined_cells
        for tick, index, pieces in cells:
            if tick >= deadline:
                continue
            hazards = hazards_at(tick, support)
            for left, right in hazards:
                pieces = subtract(pieces, left, right)
            if press_run_up and node == 16:
                _, vhi = bins[node][index]
                pieces = tuple(intersection(pieces, 335 * U - 1, 335 * U + -(-vhi // 120) + 2))
            if pieces:
                layer[tick, index] = pieces
        layers.append(layer)

    def sweep(node, backwards):
        source_cells, target_cells = layers[node - 1:node + 1]
        supported = {}
        minimum = gate['minimum'][node]
        granular = gate['granular'][node]
        for (s, j), src in source_cells.items():
            a, b = bins[node - 1][j]
            for (t, k), dst in target_cells.items():
                duration = t - s
                if duration < (61 if node == 17 else minimum):
                    continue
                if node == 17:
                    low = minimum_crawl_x(duration, b)
                    piece = intersection(src, low, 368 * U)
                    if piece:
                        supported.setdefault((s, j) if backwards else (t, k), []).extend(piece if backwards else dst)
                    continue
                vlo, vhi = bins[node][k]
                if node == 16 and press_run_up:
                    pieces = press_support(src, dst, duration, (a, b), (vlo, vhi), backwards)
                    if pieces:
                        supported.setdefault((s, j) if backwards else (t, k), []).extend(pieces)
                    continue
                rc, rd, lc, ld = directional_carry(node, s, t)
                cap = dash_limit(node, duration)
                limit_departure = (departure_cap and granular and 0 < minimum and node != 18
                                   and duration < cancellation.get(node, math.inf))
                families = [(cap, dst)]
                if limit_departure:
                    # With no lower or higher contact in the transfer, every
                    # dash before the last must finish and recharge on source.
                    # The final departure therefore occurs from that ledge.
                    # Two or more dashes spend at least 18 earlier updates.
                    families = []
                    for spent, family_cap in [(0, 1), (18, cap)]:
                        if spent and (duration < minimum + 36 or cap is not None and cap < 2):
                            continue
                        extent = departure_extent(node, s + spent, t - minimum)
                        air = duration - spent
                        after_r = travel(air, minimum, 0, 1, True, 127000001, vhi, 1)
                        after_l = travel(air, minimum, 0, 1, True, 127000001, -vlo, 1)
                        restricted = intersection(dst, extent[0] - after_l, extent[1] + after_r)
                        if restricted:
                            families.append((family_cap, restricted))
                pieces = []
                for family_cap, destinations in families:
                    right = movement(node, duration, minimum, rc, rd, granular, b, vhi, family_cap)
                    left = movement(node, duration, minimum, lc, ld, granular, -a, -vlo, family_cap)
                    if backwards:
                        pieces.extend(q for lo, hi in destinations for q in intersection(src, lo - right, hi + left))
                    else:
                        pieces.extend(q for lo, hi in src for q in intersection(destinations, lo - left, hi + right))
                key = (s, j) if backwards else (t, k)
                if pieces:
                    supported.setdefault(key, []).extend(pieces)
        layers[node - 1 if backwards else node] = {key: union(value) for key, value in supported.items()}

    def sweep_press_macro():
        # Couple the first ledge-13 contact and the last press entry. This
        # query uses the independently necessary intermediate contact windows.
        if any(not layers[node] for node in (13, 14, 15, 16)):
            return
        assert narrow_recharge and press_run_up
        ledge = constants['ledges'][14]
        static = constants['ledges'][13]['travel'] == constants['ledges'][15]['travel'] == 0
        assert static and narrow_support(14, params[15]['carry'])
        latest_14 = max(t for t, _ in layers[14])
        first_13 = min(t for t, _ in layers[13])
        earliest_15 = min(t for t, _ in layers[15])
        first_14 = min(t for t, _ in layers[14])
        source_maxima = {}
        for (tick, _), parts in layers[14].items():
            source_maxima[tick] = max(source_maxima.get(tick, 0), max(x for _, x in parts))
        source_right = (ledge['x'] + ledge['travel'] + ledge['w'] + 3) * U + 2
        if latest_14 - first_13 >= cancellation[14]:
            return
        minimum = gate['minimum'][14] + gate['minimum'][15]
        kept_13, kept_16 = {}, {}
        for (entry, index), targets in layers[16].items():
            vlo, vhi = bins[16][index]
            before = entry - 1
            # A reset to vx=0 must leave enough time for normal acceleration
            # or an entire subsequent dash. Entry itself is crouched.
            need_v = vlo + (1040 * U // 120 - 2)
            recovery = min(18, -(-need_v // GROUND))
            latest_wall = before - recovery
            beneficial_carry = any(frame['ledges'][14]['carry'] > -1e-8
                                   for frame in constants['frames'][first_14 + 1:entry + 1])
            wall_possible = vlo <= 60 * U + 1 or earliest_15 <= latest_wall
            for start, right in source_maxima.items():
                n = latest_wall - start
                if n < 0:
                    continue
                # Until the first dash recharges, grant 18 updates at the
                # full 312 speed even if the dash is shortened at the wall.
                motion = NORMAL * n + (312000001 - NORMAL) * min(18, n)
                if right + -(-motion // 120) + 2 >= 335 * U:
                    wall_possible = True
                # After a dash recharges on 14, start at the right edge of
                # that ledge and grant maximum speed for every remaining tick.
                after_recharge = n - 18 - recharge_air
                if after_recharge >= 0 and source_right + -(-(312000001 * after_recharge) // 120) + 2 >= 335 * U:
                    wall_possible = True
            if beneficial_carry or wall_possible:
                kept_16.setdefault((entry, index), []).extend(targets)
                for key, sources in layers[13].items():
                    kept_13.setdefault(key, []).extend(sources)
                continue
            terminal = -(-vhi // 120) + 1
            for (start, j), sources in layers[13].items():
                n = before - start
                if n < minimum:
                    continue
                dashes = (n - minimum) // 18
                motion = NORMAL * (n - 18 * dashes) + (5429 * U + 120) * dashes
                distance = -(-motion // 120) + terminal + 2
                for lo, hi in sources:
                    for x0, x1 in intersection(targets, 0, hi + distance):
                        kept_16.setdefault((entry, index), []).append((x0, x1))
                        kept_13.setdefault((start, j), []).extend(intersection(((lo, hi),), x0 - distance, hi))
        layers[13] = {key: union(value) for key, value in kept_13.items()}
        layers[16] = {key: union(value) for key, value in kept_16.items()}

    counts = [[len(layer) for layer in layers]]
    local_transfers = []
    if saw_transfer:
        from hybrid_saw_transfer import transfer

        def pause_transfer():
            if (HERE / 'pilot/global-pause.request').exists():
                raise SystemExit('Pause requested before completing the saw transfer')
            if available() < 8192 * 2**20:
                raise SystemExit('RAM reserve reached before completing the saw transfer')

        for support in (11, 12):
            kept, counts_by_mode = transfer(constants, bins, support, layers[support],
                                            layers[support + 1], gate['minimum'][support + 1], pause_transfer)
            layers[support + 1] = {key: union(value) for key, value in kept.items()}
            local_transfers.append({'support': support, 'targetCells': len(layers[support + 1]), **counts_by_mode})
    for _ in range(sweeps):
        previous = layers.copy()
        for node in range(31, 0, -1):
            sweep(node, True)
        for node in range(1, 32):
            sweep(node, False)
        if press_macro:
            sweep_press_macro()
        counts.append([len(layer) for layer in layers])
        if layers == previous or not layers[-1]:
            break

    checked = 0
    for name, record in constants['records'].items():
        if len(record['inputs']) != deadline:
            continue
        states = record['states']
        contacts = []
        maximum = -1
        entry = None
        for t, state in enumerate(states[:-1]):
            player = state['p']
            ground = player['ground']
            if ground is not None and ground > maximum:
                maximum = ground
                contacts.append((ground if ground <= 15 else ground + 2, t))
            if state['crossingPress'] and not states[t - 1]['crossingPress']:
                entry = t
            if state['pressOpen'] and not states[t - 1]['pressOpen']:
                contacts.extend([(16, entry), (17, t)])
        contacts.append((31, deadline - 1))
        for node, tick in contacts:
            player = states[tick]['p']
            x, vx = player['x'] * U, player['vx'] * U
            assert any(t == tick and bins[node][i][0] - 1 <= vx <= bins[node][i][1] + 1
                       and any(a - 1 <= x <= b + 1 for a, b in parts)
                       for (t, i), parts in layers[node].items()), (name, node, tick, x, vx)
            checked += 1

    result = {'deadline': deadline, 'sourceSHA256': source_hash,
              'engineSHA256': engine_hash, 'counts': counts, 'recordContactsAdmitted': checked,
              'narrowRechargeNodes': sorted(narrow), 'minimumRechargeAir': recharge_air,
              'departureCap': departure_cap,
              'signedCarry': signed_carry,
              'dashSlot': dash_slot,
              'pressRunUp': press_run_up,
              'gateVelocityStep': gate_velocity_step,
              'projectionSHA256': projection_hash,
              'pressMacro': press_macro,
              'sawTransfers': local_transfers,
              'earliestPossibleReset': min((t + 1 for t, _ in layers[-1]), default=None),
              'seconds': time.monotonic() - start}
    out.mkdir(exist_ok=True)
    (out / 'result.json').write_text(json.dumps(result, indent=2))
    (out / 'frontiers.json').write_text(json.dumps({'bins': bins, 'layers': [
        [[t, i, parts] for (t, i), parts in layer.items()] for layer in layers]}, separators=(',', ':')))
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--deadline', type=int, default=1646)
    parser.add_argument('--sweeps', type=int, default=3)
    parser.add_argument('--narrow-recharge', action='store_true')
    parser.add_argument('--departure-cap', action='store_true')
    parser.add_argument('--signed-carry', action='store_true')
    parser.add_argument('--dash-slot', action='store_true')
    parser.add_argument('--press-run-up', action='store_true')
    parser.add_argument('--gate-velocity-step', type=int)
    parser.add_argument('--contact-report', type=Path)
    parser.add_argument('--press-macro', action='store_true')
    parser.add_argument('--saw-transfer', action='store_true')
    args = parser.parse_args()
    assert available() >= 8192 * 2**20
    guard = Job(384)
    run(args.source, args.output, args.deadline, args.sweeps, args.narrow_recharge, args.departure_cap,
        args.signed_carry, args.dash_slot, args.press_run_up, args.gate_velocity_step, args.contact_report,
        args.press_macro, args.saw_transfer)
