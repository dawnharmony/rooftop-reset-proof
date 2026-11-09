"""Fixed-point outer transfer for the deadline-critical contacts 11–13."""

from itertools import combinations_with_replacement
from math import isqrt

from hybrid_bounds import Q, ceildiv
from kernel import SCALE, clip, hull, interval, step


def ordinary_gravity(v, upper):
    rate = 740 * Q
    return max(-420 * Q, v - (rate // 120 if upper else ceildiv(rate, 120))) + (1 if upper else -1)


def fall_bounds(updates):
    y0 = y1 = v0 = v1 = 0
    values = [(y0, y1)]
    for _ in range(updates):
        # Maximal fast-fall gives the lower bound. Ordinary gravity gives
        # the upper bound, including the first falling update.
        v0 = max(-490 * Q - 1, v0 - ceildiv(1410 * Q, 120) - 1)
        v1 = ordinary_gravity(v1, True)
        y0 += v0 // 120 - 1
        y1 += ceildiv(v1, 120) + 1
        values.append((y0, y1))
    return values


def ascent(ordinary, source_y, target_y, dash_last):
    """Enumerate launch delays and up to two cut slots on the normal clock."""
    falls = fall_bounds(11)
    for waiting in range(ordinary):
        count = ordinary - waiting
        for airborne in range(min(waiting, 11) + 1):
            base_lo, base_hi = falls[airborne]
            schedules = [()] + [(i,) for i in range(count)]
            schedules += list(combinations_with_replacement(range(count), 2))
            for cuts in schedules:
                lo, hi = base_lo + source_y, base_hi + source_y
                vlo = vhi = 285 * Q
                heights = [(lo, hi)]
                for index in range(count):
                    for _ in range(cuts.count(index)):
                        if vhi < 110 * Q - 1:
                            break
                        vlo = max(vlo, 110 * Q - 1) * 54 // 100 - 1
                        vhi = ceildiv(vhi * 54, 100) + 1
                    else:
                        # If vlo could be nonpositive, allowing fast fall
                        # at that endpoint only enlarges the lower side.
                        if vlo <= 1:
                            vlo = max(-490 * Q - 1, vlo - ceildiv(1410 * Q, 120) - 1)
                        else:
                            vlo = ordinary_gravity(vlo, False)
                        vhi = ordinary_gravity(vhi, True)
                        lo += vlo // 120 - 1
                        hi += ceildiv(vhi, 120) + 1
                        heights.append((lo, hi))
                        continue
                    break
                else:
                    previous = heights[-1 if dash_last else -2][1]
                    if vlo <= 1 and lo <= target_y + 1 and previous >= target_y - Q // 1000 - 2:
                        yield waiting, airborne, heights


def avoid_saw(polygon, height, frame, headroom):
    if frame['grace'] > 0:
        return (polygon,)
    saw = frame['saws'][1]
    sx, sy = round(saw['x'] * Q), round(saw['y'] * Q)
    lo, hi = height
    dy = max(0, hi + Q - sy, sy - lo - headroom * Q) + 4
    squared = 30 * Q * Q - dy * dy
    if squared <= 0:
        return (polygon,)
    reach = 3 * Q + isqrt(squared) - 4
    conversion = Q // SCALE
    west = ceildiv(sx - reach, conversion)
    east = (sx + reach) // conversion
    return tuple(piece for piece in (clip(polygon, 0, west, False), clip(polygon, 0, east, True)) if piece)


def rect(left, right, low_v, high_v):
    return hull([(x, v) for x in (left, right) for v in (low_v, high_v)])


def propagate(groups, constants, support, start, finish, waiting, airborne, dash_at, heights):
    direction = -1 if support == 11 else 1
    index = 0
    detach = waiting - airborne + 1
    falling = fall_bounds(airborne)
    for offset in range(1, finish - start + 1):
        frame = constants['frames'][start + offset]
        phase = frame['ledges'][support]
        ground = offset < detach
        carried = offset <= detach
        dashing = dash_at <= offset < dash_at + 18
        velocity = direction * (125 if offset == dash_at + 17 else 312)
        physics = 2 if dashing else 1 if ground else 0
        if offset <= waiting:
            if ground:
                height = (constants['ledges'][support]['y'] * Q,) * 2
            else:
                y = constants['ledges'][support]['y'] * Q
                a, b = falling[offset - detach + 1]
                height = y + a, y + b
        else:
            if not dashing:
                index += 1
            height = heights[index]
        next_groups = []
        for p in groups:
            if carried:
                c0, c1 = interval(phase['carry'])
                p = hull([(x + c, v) for x, v in p for c in (c0, c1)])
            if offset == detach and airborne:
                pieces = tuple(q for q in (clip(p, 0, interval(phase['left'])[1], False),
                                           clip(p, 0, interval(phase['right'])[0], True)) if q)
            else:
                # Waiting may include a detach and same-tick recontact.
                # Treating that update as grounded grants more acceleration.
                pieces = (p,)
            for q in pieces:
                q = step(q, -1, -1, physics, velocity, [], clamp_world=True)
                if q:
                    if offset == finish - start:
                        # The engine snaps feet to the target ledge before
                        # checking hazards. Grant survival on that update.
                        next_groups.append(q)
                    else:
                        next_groups.extend(avoid_saw(q, height, frame, 11 if ground else 15))
        # Keeping both sides of the saw costs at most a few polygons. A
        # hull fallback preserves coverage even for a less narrow profile.
        groups = next_groups if len(next_groups) <= 24 else [hull([v for p in next_groups for v in p])]
        if not groups:
            break
    return groups


def transfer(constants, bins, support, source, targets, minimum, pause):
    """Return supported target cells, or the original cells outside tight scope."""
    source_y = constants['ledges'][support]['y'] * Q
    target_y = constants['ledges'][support + 1]['y'] * Q
    starts = sorted({t for t, _ in source})
    finishes = sorted({t for t, _ in targets})
    if not starts or not finishes:
        return {}, {'tested': 0, 'survived': 0}
    supported = {}
    tested = survived = fallback = 0
    for start in starts:
        initial = [rect(lo - 1, hi + 1, bins[support][k][0] - 1, bins[support][k][1] + 1)
                   for (t, k), parts in source.items() if t == start
                   for lo, hi in parts]
        start_x = [x for p in initial for x, _ in p]
        for finish in finishes:
            pause()
            if finish < start + minimum:
                continue
            goals = {key: parts for key, parts in targets.items() if key[0] == finish}
            target_x = [x for parts in goals.values() for interval_ in parts for x in interval_]
            elapsed = finish - start
            ordinary = elapsed - 18
            # Over-credit all possible carry, including after a hypothetical
            # dash recharge. Check whether a no-dash suffix from either the
            # first contact or a same-level recharge could reach the goal.
            phases = [f['ledges'][support] for f in constants['frames'][start:finish + 1]]
            carry = max(max(abs(v) for v in interval(f['carry'])) for f in phases)
            speed = ceildiv(127 * SCALE + 2, 120) + carry + 2
            if support == 11:
                gap = min(start_x) - max(target_x)
                recharge_gap = min(interval(f['left'])[0] for f in phases) - max(target_x)
            else:
                gap = min(target_x) - max(start_x)
                recharge_gap = min(target_x) - max(interval(f['right'])[1] for f in phases)
            # A press cancellation could shorten a dash. Absolute motion
            # from the first contact cannot reach its left collision plane.
            max_x = max(start_x) + elapsed * (2_600_002 + carry)
            if (max_x >= 335 * SCALE - 2 or elapsed >= minimum + 36
                    or gap <= elapsed * speed or recharge_gap <= max(0, ordinary) * speed
                    or ordinary - minimum >= 23):
                fallback += 1
                for key, parts in goals.items():
                    supported.setdefault(key, []).extend(parts)
                continue
            if ordinary < minimum:
                continue
            for dash_last in (False, True):
                for waiting, airborne, heights in ascent(ordinary, source_y, target_y, dash_last):
                    slots = (ordinary + 1,) if dash_last else range(waiting + 1, ordinary + 1)
                    for dash_at in slots:
                        tested += 1
                        groups = propagate(initial, constants, support, start, finish, waiting,
                                           airborne, dash_at, heights)
                        any_target = False
                        for key, parts in goals.items():
                            low_v, high_v = bins[support + 1][key[1]]
                            for p in groups:
                                q = clip(clip(p, 1, low_v - 1, True), 1, high_v + 1, False)
                                for lo, hi in parts:
                                    sub = clip(clip(q, 0, lo - 1, True), 0, hi + 1, False)
                                    if sub:
                                        left = max(lo, min(x for x, _ in sub) - 1)
                                        right = min(hi, max(x for x, _ in sub) + 1)
                                        if left <= right:
                                            supported.setdefault(key, []).append((left, right))
                                            any_target = True
                        survived += any_target
    return supported, {'tested': tested, 'survived': survived, 'fallback': fallback}
