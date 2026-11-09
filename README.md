# Rooftop Reset — the one-tick gap

The saved Nightmare run presses reset in **1,647 physics ticks (13.725 seconds)** with zero deaths. The computational proof excludes any successful reset by tick **1,646** for the exact engine build in this repository.

- [Proof and reproduction notes](reachability/hybrid/RESET-1646-PROOF.md)
- [Recorded run](videos/rooftop-reset-nightmare-13.725.mp4) and [replay inputs](records/13.725/inputs.json)
- [Audit output](reachability/hybrid/reset-1646-audit.json)
- [1,646-tick exclusion](reachability/hybrid/contact-publish-check-1646/result.json) and [1,647-tick control](reachability/hybrid/contact-publish-check-1647/result.json)

The decisive check concerns the saw between ledges 11 and 12. The timing and movement bounds force any faster run to make that transfer from tick 617 to tick 672. The fixed-point check rules out the transfer across the entire required position and velocity range.

Run the audit from the repository root on Windows with Python 3.11 or newer, Node.js, and at least 8 GiB of available RAM. The script uses the Python standard library.

```powershell
python reachability/audit_reset_1646.py
```

The audit replays the winning inputs in the pinned engine, verifies the exported physics frames and saved artifact lineage, and repeats the decisive transfer check. It uses the saved reachability databases. The proof notes explain the assumptions behind the model and what each stage checks.

Engine SHA-256 `0a427d28c8ab60e7ee1dc69f3caa6837cc542bec34a757f4394c7e0e079bd031`.
