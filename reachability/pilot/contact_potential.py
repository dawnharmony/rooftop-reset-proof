"""Clip first landings to the bidirectionally screened contact profiles."""

from dataclasses import replace
from functools import lru_cache
import json
import math

from kernel import clip, hull, SCALE
from hybrid_contact_screen import PROJECTED_NODES, contact_hazards
from hybrid_momentum_bounds import NORMAL, normal_only, travel


class ContactPotential:
    projected_nodes = PROJECTED_NODES

    def __init__(self, path, deadline, constants, air_deadline=False, gate_partition=False, saw_partition=False):
        report = json.loads(path.with_name('result.json').read_text())
        assert report['deadline'] == deadline
        assert report['engineSHA256'] == constants['engineSHA256']
        profile = json.loads(path.read_text())
        assert len(profile['layers']) == len(profile['bins']) == 32
        self.constants = constants
        self.air_deadline = air_deadline
        self.gate_partition = gate_partition
        self.saw_partition = saw_partition
        self.bins = profile['bins']
        self.rows = []
        for bins, layer in zip(profile['bins'], profile['layers']):
            rows = {}
            for tick, index, pieces in layer:
                low_v, high_v = bins[index]
                rows.setdefault(tick, []).extend((lo, hi, low_v, high_v) for lo, hi in pieces)
            self.rows.append(rows)
        self.latest = [max(rows, default=-1) for rows in self.rows]
        self.extents = [{tick: (min(r[0] for r in row), max(r[1] for r in row),
                                min(r[2] for r in row), max(r[3] for r in row))
                         for tick, row in rows.items()} for rows in self.rows]
        from hybrid_contact_screen import HERE
        gates = json.loads((HERE / 'hybrid/gate-bounds.json').read_text())
        self.graph = gates['closed']
        self.parameters = json.loads((HERE / 'hybrid/monotone-bounds.json').read_text())['parameters']
        source_12 = self.extents[12]
        duration_12 = self.latest[13] - min(source_12, default=deadline)
        self.single_dash_12 = (saw_partition and constants['ledges'][12]['travel'] == 0
                               and 0 < duration_12 < self.graph['minimum'][13] + 36
                               and max((x[1] for x in source_12.values()), default=0)
                               + 2_770_003 * duration_12 < 335 * SCALE - 2)

    @lru_cache(maxsize=4096)
    def hazards(self, tick, ground):
        spikes = [(4, 'right', 9), (12, 'left', 9), (16, 'right', 9), (19, 'left', 8), (22, 'right', 7)]
        return contact_hazards(self.constants['frames'][tick], self.constants['ledges'], ground, spikes)

    def contact_node(self, parent, region):
        if not parent.opened and region.opened:
            return 17
        if region.g > parent.anchor:
            return region.g if region.g <= 15 else region.g + 2
        return None

    def projection_node(self, parent, region):
        # Record every new crossing attempt. A successful run's last entry
        # before the press opens is one of these transitions.
        if not parent.cross and region.cross and not region.opened and region.g == 15:
            return 16
        return self.contact_node(parent, region)

    @lru_cache(maxsize=4096)
    def approach(self, node, tick, grounded, arrival_mask=None):
        left, right = math.inf, -math.inf
        m = self.graph['minimum'][node] if grounded else 0
        params = self.parameters[node]
        for target_tick, (lo, hi, low_v, high_v) in self.extents[node].items():
            steps = target_tick - tick
            if steps < max(0 if node == 31 else 1, m):
                continue
            if arrival_mask is not None and steps < self.graph['minimum'][node]:
                if not (arrival_mask >> steps) & 1:
                    continue
            if grounded and self.graph['granular'][node] and node not in (13, 14):
                rightward = travel(steps, m, params['carry'], params['departure'], True, 127000001, high_v)
                leftward = travel(steps, m, params['carry'], params['departure'], True, 127000001, -low_v)
            else:
                # Includes moving carry and the one-update precision margin.
                rightward = leftward = 2_770_003 * steps
            left = min(left, lo - rightward)
            right = max(right, hi + leftward)
        return (left, right) if left <= right else None

    @staticmethod
    @lru_cache(maxsize=4096)
    def flight_envelope(low_v, high_v, steps):
        """Outward offsets for normal air updates, ignoring dash pauses."""
        low_y = high_y = 0
        # After a legal cut the velocity exceeds 59.4. From this optimistic
        # floor, further cuts can never go below the descending lower bound.
        low_v = min(low_v, 59_399_999)
        result = [(low_y, high_y, low_v)]
        for _ in range(steps):
            low_v = max(-490 * SCALE - 1, low_v - 11_750_001)
            high_v = max(-420 * SCALE + 1, high_v - 6_166_665)
            low_y += low_v // 120 - 1
            high_y += -(-high_v // 120) + 1
            result.append((low_y, high_y, low_v))
        return result

    def direct_landing_times(self, region, node, tick):
        clear_of_press = region.opened or node == 13 and self.single_dash_12
        if region.g >= 0 or region.cy or node == 31 or not clear_of_press:
            return None
        minimum = self.graph['minimum'][node]
        if not minimum:
            return None
        # Below the full ascent minimum there is no time to recontact the
        # source, recharge, and then jump to the higher support. In this
        # window an opened-press state can only finish its current flight.
        low_y, high_y = min(y for y, _ in region.z), max(y for y, _ in region.z)
        low_v = min(v for _, v in region.z) // SCALE * SCALE
        high_v = -(-max(v for _, v in region.z) // SCALE) * SCALE
        envelope = self.flight_envelope(low_v, high_v, minimum - 1)
        target_support = node if node <= 15 else node - 2
        height = self.constants['ledges'][target_support]['y'] * SCALE
        mask = 0
        for target_tick in self.extents[node]:
            steps = target_tick - tick
            if not max(1, region.d) <= steps < minimum:
                continue
            normal = steps - region.d
            counts = [normal]
            if region.ready and normal >= 18:
                counts.append(normal - 18)
            for n in counts:
                bottom, _, velocity = envelope[n]
                # The final update can be a dash pause. In that case its
                # previous height uses all n normal steps, rather than n-1.
                _, top, _ = envelope[n]
                _, previous_top, _ = envelope[max(0, n - 1)]
                if low_y + bottom <= height + 1 and velocity <= 1:
                    if high_y + max(top, previous_top) >= height - 1001:
                        mask |= 1 << steps
                        break
        return mask

    @lru_cache(maxsize=4096)
    def approach_13(self, tick, dash, direction, ready, low_v, high_v, arrivals):
        """Before the press, the screened 12–13 window fits at most one dash."""
        left, right = math.inf, -math.inf
        for target_tick, (lo, hi, end_low, end_high) in self.extents[13].items():
            steps = target_tick - tick
            if steps < max(1, dash):
                continue
            if arrivals is not None and steps < self.graph['minimum'][13] and not (arrivals >> steps) & 1:
                continue
            if dash:
                dash_distance = 312000001 * (dash - 1) + 125000001
                ordinary = NORMAL * (steps - dash)
                move_right = -(-(ordinary + (dash_distance if direction > 0 else 0)) // 120) + 2
                move_left = -(-(ordinary + (dash_distance if direction < 0 else 0)) // 120) + 2
            else:
                move_right = normal_only(steps, high_v, end_high)
                move_left = normal_only(steps, -low_v, -end_low)
                if ready and steps >= 18:
                    boosted = -(-(NORMAL * (steps - 18) + 5429 * SCALE + 120) // 120) + 2
                    move_right = max(move_right, boosted)
                    move_left = max(move_left, boosted)
            left = min(left, lo - move_right)
            right = max(right, hi + move_left)
        return (left, right) if left <= right else None

    @lru_cache(maxsize=2048)
    def airborne_hazards(self, tick):
        frame = self.constants['frames'][tick]
        if frame['grace'] > 0:
            return ()
        rectangles = []
        for i, edge, width in [(4, 'right', 9), (12, 'left', 9), (16, 'right', 9),
                               (19, 'left', 8), (22, 'right', 7)]:
            ledge = self.constants['ledges'][i]
            x = frame['ledges'][i]['x'] + (ledge['w'] - width if edge == 'right' else 0)
            rectangles.append((x - 2, x + width + 2, ledge['y'] - 13, ledge['y'] + 6))
        for vent in frame['vents']:
            if vent['active']:
                rectangles.append((vent['x'] - 3, vent['x'] + 9, vent['y'] - 11, vent['y'] + 24))
        for bolt in frame['bolts']:
            if bolt['active']:
                rectangles.append((bolt['x'] - 7, bolt['x'] + 7, bolt['y'] - 17, bolt['y'] + 1))
        for saw in frame['saws']:
            rectangles.append((saw['x'] - 6.8, saw['x'] + 6.8, saw['y'] - 14.8, saw['y'] + 2.8))
        return [(math.ceil(a * SCALE) + 2, math.floor(b * SCALE) - 2,
                 math.ceil(c * SCALE) + 2, math.floor(d * SCALE) - 2) for a, b, c, d in rectangles]

    def split_saw(self, region, parts, tick, low_y, high_y):
        """Keep horizontal slices coupled to vertical avoidance of the saw at x105."""
        frame = self.constants['frames'][tick]
        saw = frame['saws'][1]
        x, y = saw['x'], saw['y']
        if frame['grace'] > 0 or low_y > (y + 9) * SCALE or high_y < (y - 20) * SCALE:
            return tuple(replace(region, p=polygon) for polygon in parts)
        edges = [x - 7.8, x - 6, x - 3, x + 3, x + 6, x + 7.8]
        boundaries = [round(value * SCALE) for value in edges]
        result = []
        for polygon in parts:
            x0 = min(a for a, _ in polygon)
            x1 = max(a for a, _ in polygon)
            if x1 <= boundaries[0] or x0 >= boundaries[-1]:
                result.append(replace(region, p=polygon))
                continue
            for edge, lower in ((boundaries[0], False), (boundaries[-1], True)):
                outside = clip(polygon, 0, edge, lower)
                if outside:
                    result.append(replace(region, p=outside))
            for lo, hi in zip(boundaries, boundaries[1:]):
                inside = clip(clip(polygon, 0, lo, True), 0, hi, False)
                if not inside:
                    continue
                dx = max(0, abs(lo / SCALE - x) - 3, abs(hi / SCALE - x) - 3) + 0.000002
                radius = math.sqrt(30 - dx * dx)
                bottom = math.ceil((y - 11 - radius) * SCALE) + 2
                top = math.floor((y - 1 + radius) * SCALE) - 2
                for z in (clip(region.z, 0, bottom, False), clip(region.z, 0, top, True)):
                    if z:
                        result.append(replace(region, p=inside, z=z))
        return tuple(result)

    def prune_parts(self, parent, region, tick):
        next_node = region.anchor + 1 if region.anchor < 15 else region.anchor + 3
        if not region.opened and tick >= self.latest[17]:
            return ()
        if tick >= self.latest[next_node]:
            # The virtual button is available during this state, before the
            # subsequent reset update. Physical landings must already exist.
            if next_node != 31 or tick > self.latest[31]:
                return ()
        node = self.contact_node(parent, region)
        grounded = region.g >= 0 and (region.anchor != 15 or region.opened)
        arrivals = self.direct_landing_times(region, next_node, tick) if self.air_deadline else None
        if next_node == 13 and self.single_dash_12:
            low_v = min(v for _, v in region.p) // SCALE * SCALE
            high_v = -(-max(v for _, v in region.p) // SCALE) * SCALE
            extent = self.approach_13(tick, region.d, region.direction, region.ready, low_v, high_v, arrivals)
        else:
            extent = self.approach(next_node, tick, grounded, arrivals)
        if extent is None:
            return ()
        p = clip(clip(region.p, 0, extent[0] - 1, True), 0, extent[1] + 1, False)
        if not p:
            return ()
        parts = [p]
        if node is not None:
            parts = []
            for low_x, high_x, low_v, high_v in self.rows[node].get(tick, ()):
                polygon = clip(clip(p, 0, low_x - 1, True), 0, high_x + 1, False)
                polygon = clip(clip(polygon, 1, low_v - 1, True), 1, high_v + 1, False)
                if polygon:
                    parts.append(polygon)
        if region.g >= 0:
            for left, right in self.hazards(tick, region.g):
                if left < right:
                    parts = [p for poly in parts for p in (clip(poly, 0, left, False),
                                                           clip(poly, 0, right, True)) if p]
        else:
            low_y = min(y for y, _ in region.z)
            high_y = max(y for y, _ in region.z)
            for left, right, bottom, top in self.airborne_hazards(tick):
                if bottom <= low_y and high_y <= top:
                    parts = [p for poly in parts for p in (clip(poly, 0, left, False),
                                                           clip(poly, 0, right, True)) if p]
            if self.saw_partition and region.anchor in (11, 12):
                return self.split_saw(region, parts, tick, low_y, high_y)
        if self.gate_partition and node == 15:
            return tuple(replace(region, p=polygon) for polygon in parts)
        if not parts:
            return ()
        polygon = parts[0] if len(parts) == 1 else hull([point for part in parts for point in part])
        return (replace(region, p=polygon),)

    def partition(self, region):
        if self.saw_partition and region.g < 0 and region.anchor in (11, 12):
            xs, _ = zip(*region.p)
            if min(xs) <= 121 * SCALE and max(xs) >= 89 * SCALE:
                ys, _ = zip(*region.z)
                return ((min(xs) + max(xs)) // (6 * SCALE),
                        (min(ys) + max(ys)) // (6 * SCALE))
        if not self.gate_partition or region.g != 15 or region.opened or region.cross:
            return ()
        # Merge key only. Each polygon is kept whole and cannot be discarded
        # for lying partly outside the bucket that contains its midpoint.
        xs, velocities = zip(*region.p)
        return ((min(xs) + max(xs)) // (4 * SCALE),
                (min(velocities) + max(velocities)) // (16 * SCALE))

    def record_contact(self, report, node, region):
        """Enclose each first contact's x projection in the original velocity bins."""
        cells = report.setdefault(node, {})
        low_v = min(v for _, v in region.p)
        high_v = max(v for _, v in region.p)
        for index, (lo, hi) in enumerate(self.bins[node]):
            if hi + 1 < low_v or high_v < lo - 1:
                continue
            polygon = clip(clip(region.p, 1, lo - 1, True), 1, hi + 1, False)
            if polygon:
                x0 = min(x for x, _ in polygon)
                x1 = max(x for x, _ in polygon)
                if index in cells:
                    x0 = min(x0, cells[index][0])
                    x1 = max(x1, cells[index][1])
                cells[index] = (x0, x1)

    def admits_reset(self, region, tick):
        return any(clip(clip(region.p, 0, low_x - 1, True), 0, high_x + 1, False)
                   for low_x, high_x, _, _ in self.rows[31].get(tick, ()))
