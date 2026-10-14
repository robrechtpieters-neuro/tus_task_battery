#!/usr/bin/env python
"""Pre-flight check. Run this FIRST on any new computer.

    python tools/check_install.py

It verifies, in order:
  1. Python and PsychoPy are importable, and reports versions
  2. the configuration file parses and passes validation
  3. trial lists build correctly and have the counts you expect
  4. the trigger backend opens (or reports why it did not)
  5. the response device opens
  6. a window opens and the refresh rate is stable, with a frame-drop test

Nothing here writes data. It is safe to run at any time, and it is the
fastest way to find out whether a machine is fit to collect real data.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS, FAIL, WARN = "  [ok]  ", "  [FAIL]", "  [warn]"


def main():
    problems = 0

    print("\n=== 1. software ===")
    print(f"{PASS} python {sys.version.split()[0]}  ({sys.executable})")
    try:
        import psychopy
        print(f"{PASS} psychopy {psychopy.__version__}")
    except Exception as exc:                           # noqa: BLE001
        print(f"{FAIL} psychopy not importable: {exc}")
        print("        Run this with the PsychoPy python, or: pip install psychopy")
        return 1
    try:
        import yaml  # noqa: F401
        print(f"{PASS} pyyaml")
    except Exception:                                  # noqa: BLE001
        print(f"{FAIL} pyyaml missing:  pip install pyyaml")
        return 1

    print("\n=== 2. configuration ===")
    from battery.config import load_config
    try:
        cfg = load_config()
        print(f"{PASS} config/default.yaml parsed and validated")
    except SystemExit as exc:
        print(f"{FAIL} {exc}")
        return 1
    print(f"         units={cfg.display.units}  nominal={cfg.display.nominal_refresh_hz} Hz  "
          f"triggers={cfg.triggers.backend}  responses={cfg.response.backend}")

    print("\n=== 3. trial lists ===")
    from battery import trials
    rng = random.Random(1)
    blocks = trials.temporal_orienting_blocks(cfg, rng, run_index=0)
    total = sum(len(b["trials"]) for b in blocks)
    per_block = [len(b["trials"]) for b in blocks]
    names = [b["context"][:4] for b in blocks]
    print(f"{PASS} temporal orienting: {len(blocks)} blocks {names}, "
          f"{per_block} trials, {total} total")
    counts = {}
    for b in blocks:
        for t in b["trials"]:
            counts[t["validity"]] = counts.get(t["validity"], 0) + 1
    print(f"         validity counts: {counts}")

    st = trials.self_timing_blocks(cfg, rng, session_number=1, practice=True)
    print(f"{PASS} self-timing: {len(st)} blocks, "
          f"{sum(len(b['trials']) for b in st)} trials "
          f"({sum(len(b['trials']) for b in st if not b['is_practice'])} scored)")
    print(f"{PASS} simple RT: {len(trials.simple_rt_trials(cfg, rng))} trials")

    est = _estimate_minutes(cfg, blocks, st)
    print(f"         estimated durations (min): {est}")

    print("\n=== 4. triggers ===")
    from battery.triggers import TriggerPort
    trig = TriggerPort(cfg, verbose=False)
    if trig.backend == cfg.triggers.backend:
        print(f"{PASS} backend '{trig.backend}' opened")
    else:
        print(f"{WARN} requested '{cfg.triggers.backend}' but fell back to '{trig.backend}'")
        problems += 1
    missing = _check_trigger_codes(cfg, trig)
    if missing:
        print(f"{FAIL} trigger codes referenced by tasks but missing from config: {missing}")
        problems += 1
    else:
        print(f"{PASS} every trigger code the tasks use is defined")

    print("\n=== 5. responses ===")
    from battery.responses import Responder
    responder = Responder(cfg, verbose=False)
    print(f"{PASS} backend '{responder.backend}', "
          f"right={responder.keys_for('right')} left={responder.keys_for('left')}")

    print("\n=== 6. display timing ===")
    from battery.display import Display
    cfg.display.fullscreen = True          # timing is only meaningful fullscreen
    try:
        disp = Display(cfg, trig, responder, verbose=False)
    except SystemExit as exc:
        print(f"{FAIL} {exc}")
        trig.close()
        return 1
    print(f"{PASS} window opened, measured {disp.frame_rate:.2f} Hz "
          f"(frame = {disp.frame_dur * 1000:.2f} ms)")

    dropped, n = _frame_drop_test(disp, seconds=3.0)
    pct = 100.0 * dropped / max(n, 1)
    line = PASS if pct < 1.0 else (WARN if pct < 5.0 else FAIL)
    print(f"{line} frame-drop test: {dropped}/{n} late frames ({pct:.2f} %)")
    if pct >= 1.0:
        problems += 1
        print("         Close other applications, disable compositing/overlays,")
        print("         and set the GPU to maximum performance before collecting data.")

    for label, seconds in (("0.700 s SOA", 0.700), ("1.200 s SOA", 1.200),
                           ("0.100 s stim", 0.100)):
        print(f"         {label}: {disp.frames(seconds)} frames = "
              f"{disp.actual_s(seconds) * 1000:.2f} ms "
              f"(error {1000 * (disp.actual_s(seconds) - seconds):+.2f} ms)")

    disp.close()
    trig.close()

    print("\n=== summary ===")
    if problems == 0:
        print("  All checks passed. This machine is ready to collect data.\n")
        return 0
    print(f"  {problems} issue(s) above need attention before real data collection.\n")
    return 1


def _frame_drop_test(disp, seconds=3.0):
    """Count frames that took more than 1.5x the expected interval."""
    from psychopy import core
    n = disp.frames(seconds)
    threshold = disp.frame_dur * 1.5
    last = core.getTime()
    dropped = 0
    for _ in range(n):
        disp.win.flip()
        now = core.getTime()
        if now - last > threshold:
            dropped += 1
        last = now
    return dropped, n


def _check_trigger_codes(cfg, trig):
    """Every code name the task modules can generate must exist in the config."""
    to = cfg.tasks.temporal_orienting
    st = cfg.tasks.self_timing
    needed = ["task_start", "task_end", "block_start", "block_end",
              "to_cue_first", "to_cue_other", "to_response", "to_anticipation",
              "rt_target", "rt_response", "rt_anticipation"]
    for context in to.n_cues:
        for soa in to.soa_s:
            needed += [f"to_warning_{context}_{soa}", f"to_catch_{context}_{soa}"]
            for validity in ("valid", "invalid"):
                needed.append(f"to_target_{context}_{soa}_{validity}")
    for hand in st.hands:
        needed += [f"st_start_{hand}", f"st_response_{hand}"]
        for delay in st.delays_s:
            needed.append(f"st_cue_{delay}_{hand}")
    for kind in cfg.tasks.resting.order:
        needed += [f"rest_{kind}_start", f"rest_{kind}_end"]
    return sorted({n for n in needed if n not in trig.codes})


def _estimate_minutes(cfg, to_blocks, st_blocks, assumed_rt_s=0.35):
    """Wall-clock estimate per task, summed over the trials actually generated.

    Every trial is costed from its own parameters rather than from a
    worst-case formula, so these numbers can be trusted when planning the
    post-TUS schedule against the ~60 min offline effect window.
    """
    to = cfg.tasks.temporal_orienting
    total_to = 0.0
    for block in to_blocks:
        n_cues = block["n_cues"]
        for trial in block["trials"]:
            soa = float(trial["soa_s"])
            # first cue -> warning signal, then warning -> target
            to_ws = (n_cues - 1) * soa + trial["gap_s"]
            target_soa = trial["target_soa_s"] if trial["target_soa_s"] else soa
            if trial["is_catch"] or not to.end_trial_on_response:
                after = float(to.response_window_s)
            else:
                after = min(float(to.response_window_s),
                            float(to.target.duration_s) + assumed_rt_s)
            total_to += (sum(to.iti_s) / 2 + float(to.fixation_lead_s)
                         + to_ws + target_soa + after)

    st = cfg.tasks.self_timing
    total_st = 0.0
    for block in st_blocks:
        for trial in block["trials"]:
            total_st += (sum(st.iti_s) / 2 + float(st.cue_duration_s)
                         + trial["cue_to_start_s"] + trial["delay_s"])
            if block["is_practice"]:
                total_st += float(st.practice.feedback_duration_s)

    srt = cfg.tasks.simple_rt
    total_srt = int(srt.n_trials) * (
        sum(srt.iti_s) / 2 + sum(srt.foreperiod_s) / 2
        + float(srt.target.duration_s) + assumed_rt_s
    )

    rest = float(cfg.tasks.resting.eyes_open_s) + float(cfg.tasks.resting.eyes_closed_s)
    return {
        "temporal_orienting": round(total_to / 60, 1),
        "self_timing": round(total_st / 60, 1),
        "simple_rt": round(total_srt / 60, 1),
        "resting": round(rest / 60, 1),
        "_note": "excludes instructions and breaks; assumes ~350 ms responses",
    }


if __name__ == "__main__":
    sys.exit(main())
