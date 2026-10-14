#!/usr/bin/env python
"""Same-day data check.

    python tools/quicklook.py data/sub-P01/ses-1

Prints the primary outcome - the temporal-validity effect in each context -
plus the self-timing and simple-RT summaries, straight from the CSV files.

This is a data-quality tool, not an analysis. Its job is to answer one
question before the participant leaves the building: does this session's
data look usable? At baseline the validity effect should be clearly
positive in BOTH contexts. If it is not, suspect the setup - key mapping,
monitor timing, instructions - rather than the participant.

Uses only the Python standard library, so it runs anywhere.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median, pstdev


def load(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def temporal_orienting(paths):
    print("\n" + "=" * 74)
    print("TEMPORAL ORIENTING - validity effect = RT(invalid) - RT(valid), ms")
    print("=" * 74)
    for path in sorted(paths):
        rows = load(path)
        cells = defaultdict(lambda: defaultdict(list))
        excluded = 0
        for row in rows:
            if row["is_catch"] == "1" or row["responded"] != "1" or not row["rt_s"]:
                continue
            if row["anticipation"] == "1":
                excluded += 1
                continue
            cells[(row["context"], row["soa_label"])][row["validity"]].append(
                float(row["rt_s"]) * 1000.0
            )

        print(f"\n{path.name}   ({len(rows)} trials, {excluded} anticipations dropped)")
        print(f"  {'context':<10}{'SOA':<7}{'n val':>6}{'n inv':>6}"
              f"{'RT val':>9}{'RT inv':>9}{'effect':>9}")
        by_context = defaultdict(list)
        for (context, soa), data in sorted(cells.items()):
            v, i = data.get("valid", []), data.get("invalid", [])
            effect = (median(i) - median(v)) if (v and i) else None
            if effect is not None:
                by_context[context].append(effect)
            print(f"  {context:<10}{soa:<7}{len(v):>6}{len(i):>6}"
                  f"{_f(median(v) if v else None):>9}{_f(median(i) if i else None):>9}"
                  f"{_f(effect):>9}")
        if by_context:
            print("  " + "-" * 54)
            for context, effects in sorted(by_context.items()):
                print(f"  {context:<10}{'mean':<7}{'':>12}{'':>18}"
                      f"{_f(sum(effects) / len(effects)):>9}")
            if len(by_context) == 2:
                diff = (sum(by_context['interval']) / len(by_context['interval'])
                        - sum(by_context['rhythm']) / len(by_context['rhythm']))
                print(f"\n  interval minus rhythm: {diff:+.0f} ms")
                print("  (the primary outcome is how THIS number changes between "
                      "sessions)")


def self_timing(paths):
    print("\n" + "=" * 74)
    print("SELF-TIMING - produced intervals, scored trials only")
    print("=" * 74)
    for path in sorted(paths):
        rows = [r for r in load(path)
                if r["is_practice"] == "0" and r["responded"] == "1" and r["produced_s"]]
        cells = defaultdict(list)
        targets = {}
        for row in rows:
            key = (row["hand"], row["delay_label"])
            cells[key].append(float(row["produced_s"]) * 1000.0)
            targets[key] = float(row["delay_s"]) * 1000.0
        print(f"\n{path.name}")
        print(f"  {'hand':<8}{'delay':<9}{'n':>5}{'target':>9}{'produced':>10}"
              f"{'bias':>8}{'SD':>8}{'CV':>8}")
        for key, values in sorted(cells.items()):
            m = sum(values) / len(values)
            sd = pstdev(values) if len(values) > 1 else 0.0
            print(f"  {key[0]:<8}{key[1]:<9}{len(values):>5}{targets[key]:>9.0f}"
                  f"{m:>10.0f}{m - targets[key]:>+8.0f}{sd:>8.0f}{sd / m:>8.3f}")


def simple_rt(paths):
    print("\n" + "=" * 74)
    print("SIMPLE RT - should be unaffected by stimulation")
    print("=" * 74)
    for path in sorted(paths):
        rows = load(path)
        rts = [float(r["rt_s"]) * 1000 for r in rows
               if r["responded"] == "1" and r["rt_s"] and r["anticipation"] == "0"]
        ant = sum(int(r["anticipation"] or 0) for r in rows)
        miss = sum(int(r["miss"] or 0) for r in rows)
        print(f"\n{path.name}")
        print(f"  n={len(rts)}  median={_f(median(rts) if rts else None)} ms  "
              f"SD={_f(pstdev(rts) if len(rts) > 1 else None)} ms  "
              f"anticipations={ant}  misses={miss}")


def _f(value):
    return "-" if value is None else f"{value:.0f}"


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    root = Path(argv[1])
    if not root.exists():
        print(f"no such folder: {root}")
        return 1
    files = sorted(root.rglob("*_beh.csv"))
    if not files:
        print(f"no *_beh.csv files under {root}")
        return 1

    groups = defaultdict(list)
    for path in files:
        for task in ("temporalorienting", "selftiming", "simplert", "resting"):
            if f"task-{task}_" in path.name:
                groups[task].append(path)

    if groups["temporalorienting"]:
        temporal_orienting(groups["temporalorienting"])
    if groups["selftiming"]:
        self_timing(groups["selftiming"])
    if groups["simplert"]:
        simple_rt(groups["simplert"])
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
