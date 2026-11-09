# Minimum Nightmare reset time

For the original engine with SHA-256
`0a427d28c8ab60e7ee1dc69f3caa6837cc542bec34a757f4394c7e0e079bd031`,
a fresh Nightmare run needs at least **1,647 updates** to reset.
Each update is 1/120 second. The archived run attains the bound with zero
deaths and an explicit reset. This is a computational exclusion with
source-level inclusion arguments and replayable arithmetic checks.

## What the faster run would have to do

The numerical argument grants any axis in [−1, 1], either dash direction,
and independent per-tick button events. This includes browser controls
and enlarges their event histories. The browser uses the engine's fixed
timestep. A win requires a grounded rooftop player within 15 units of
the button at the start of a separate interaction update. A reset by
1,646 therefore requires eligibility by 1,645.

Nightmare respawns reset the future physics and world phases to the same
fresh state. Elapsed time and the death counter do not affect future
movement or hazards. Deleting the prefix through a last respawn gives a
strictly faster suffix, so excluding the fresh zero-death case covers all
Nightmare clears within the deadline.

A jump has less than 54 units of rise. Every pair of consecutive height
gaps totals at least 68. Jumps, drops and dashes clear coyote eligibility,
and only an actual ledge contact renews it. The press roof does not raise
feet above their previous height, and the other press corrections arrest
or lower them. Each intervening support must therefore be reached before
a new maximum support can be reached.

First contact on ledge 14 is left of the press. Before landing on 15,
passing underneath would require feet at or below 484. Even a fresh
jump from that height cannot reach ledge 15 at 578. After landing on
15, the maximum height remains below the roof at 666. A surviving
nonretreating ascent must pass through the grounded crouch opening.
The last successful entry and the first open state bound the gate time.
Once the player is inside on that attempt, the solid ledge keeps them
grounded and the press forces crouch. Returning to the left edge clears
the crossing flag. The position and velocity envelopes therefore use
the entry on the final uninterrupted attempt and the engine's crouch
acceleration.

## How the contact windows enclose legal runs

The phase calculation grants every support its full collision domain
at each timestamp. Its position bound gives ordinary movement up to
127 units/s and grants maximum carry outside the mandatory air updates.
The vertical debit is obtained by outward arithmetic over launch delay,
dash pauses and up to two cuts. For a fixed launch and cut schedule,
maximal fast fall reaches a downward crossing no later than any other
descent. It leaves the upward portion unchanged. The debit also allows
the landing tolerance and a continuous envelope of coyote launch heights.

Complete dashes spend 18 updates and move at most 5,429/120 units.
Press-cancelled dash paths are granted fractional dash speed in the
press approach. For transfers 12–13 and 13–14 a cancellation needs a
detour to the press and back. Even the optimistic detour time covers the
worst direct displacement bound, so allowing the direct bound at that
time retains the detour. For the narrower departure and recharge
constraints the calculation leaves possible cancellation windows on
their permissive families.

The retreat check takes the **last** downward landing in a hypothetical
faster run. Its prefix may contain any earlier retreats. The last retreat
is replaced by a zero-time move to any point on the lower ledge. The
suffix starts there and has no later retreat. The weaker phase bounds
exclude all 406 lower-support pairs even after granting that teleport,
including a separate check for retreat after opening but before first
contact 16. The later position and velocity bounds may consequently
charge carry only to the current support between successive contacts.

The momentum calculation retains time, position intervals and velocity
bins. It allocates acceleration optimistically on each side of a
transfer, and accounts for the velocity reset on the press wall
separately from an uninterrupted run-up. The later contact screen
checks both directions across each edge. A disjoint position interval
survives if any admissible source or destination interval supports it.
Signed carry uses the best displacement in each direction over the whole
transfer window. On narrow ledges, each extra dash needs a recontact to
recharge. When a full horizontal dash cannot return at the same height,
that recontact costs a separate same-height flight. The departure bound
grants the entire phase range of the last grounded support, including the
maximum ground-flag overshoot and departure carry.

The timed projection advances the fresh spawn through complete tick
layers. The transition kernel encloses horizontal position and velocity
and vertical position and velocity in outward-rounded polygons. Discrete
branches cover grounded and airborne motion, launch, cut, dash, the press
and landing. Continuous steering is relaxed to an acceleration interval.
Optional contacts and crumble behavior are relaxed. A convex merge only
adds states. Lethal clipping removes only positions inside inscribed
hazard regions, regardless of crouch pose. The remaining-time predicates
apply to the next mandatory contact. They grant extra distance whenever
a press cancellation, an in-progress flight or a same-ledge return makes
the sharper direct-flight argument inapplicable.

The projection records all surviving first landings before merging and
feeds their position enclosures, indexed by velocity and tick, back into
the contact graph. Its input profile and complete SQLite layers are
hash-checked. The search need only complete the layers that contain the
projected contacts. Its abstract roof trace has no bearing on this
inclusion argument.

The final press bound couples ledge 13 to the required tick-846 entry.
The incoming velocity requires enough time after a wall reset to
accelerate or complete a new dash. The source contact windows place the
player too far from the wall to recover that early, even with maximum
dash speed and a separate allowance for recharging on ledge 14.
Throughout the relevant window, ledge 14 carries to the left. Dropping
that adverse carry still bounds rightward displacement from above.
Counting the two mandatory ascents and complete dash cycles therefore
forces ledge 13 at 728 with x ≥ 158.405427. The backward screen forces
ledge 11 at 617 and ledge 12 at 672. The admitted x interval on ledge 11
is contained in **[158, 168]**.

## The impossible 55-update handoff

The fixed-point checker widens the incoming velocity to the entire
[−127, 127] range with outward margins, and accepts any landing on
ledge 12 in its full collision interval [35, 83]. The horizontal gap
rules out ordinary movement alone, even if every update receives
maximum platform carry. It also rules out a dash that recharges on
ledge 11, because the remaining ordinary updates could not cover the
distance from any same-ledge recontact to ledge 12. A press cancellation
is out of horizontal range. The required ascent consumes at least 37
ordinary updates, leaving room for one full dash, directed left.

The checker enumerates grounded waits, coyote detachments, all retained
cut timings and all possible dash slots. A grounded wait may include a
same-tick detach and recontact. Earlier jump-and-return cycles cannot
fit the ordinary budget. Height is enclosed between the fastest and
slowest legal descents on a nanounit lattice. Horizontal acceleration
and ledge carry advance closed position-velocity polygons. At each tick
the checker removes only the interval of x that is lethal for **every**
height in that branch. The saw radius is rounded inward. The two sides
of the surviving set are propagated separately.

All **73** tested schedules fail to reach ledge 12 at tick 672.
The wider interval therefore excludes the smaller necessary contact
domain. The backward and forward sweeps leave every contact layer empty
for the 1,646 deadline. Turning off the saw admits schedules, which
confirms that the hazard is essential to this particular exclusion.
The matching 1,647 control retains all 32 archived contacts and its first
admitted reset is 1,647.

## Reproduction

Run `python reachability/audit_reset_1646.py` from the project root.
The audit replays the saved winner in the unchanged engine, regenerates
and compares all 1,661 exported world frames, checks the proof lineage
and complete projection layers, checks 744 phase recurrence samples
against direct evaluation, recomputes the retreat exclusions and
repeats the widened decisive transfer.

The older momentum folders lacked source manifests. Independent reruns
under the archived source/configuration produced byte-identical
frontier profiles and new manifests. The final transfer checker was
rerun after allowing grounded waits to include same-tick recontacts.
The mathematical scope and executable evidence are in the linked
workspace files.

During the publication review, the transfer checker was widened to grant
survival on the touchdown update. The engine snaps the player to the ledge
before testing hazards, so the pre-snap height envelope is inappropriate
for that update. Both the 1,646 exclusion and the 1,647 control reproduced
byte-identical frontier profiles in `contact-publish-check-1646` and
`contact-publish-check-1647`.

- [Negative result](contact-audit-fixed-1646/result.json)
- [Matching 1,647 control](contact-audit-fixed-1647/result.json)
- [Audit output](reset-1646-audit.json)
- [Fixed-point transfer implementation](../hybrid_saw_transfer.py)
- [Contact-screen implementation](../hybrid_contact_screen.py)
