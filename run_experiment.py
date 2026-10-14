#!/usr/bin/env python
"""TUS dentate nucleus task battery - single entry point.

Typical use
-----------
    python run_experiment.py                          # start-up dialog, pre-TUS schedule
    python run_experiment.py --schedule post_tus
    python run_experiment.py --schedule familiarisation
    python run_experiment.py --demo                   # whole battery, tiny, windowed
    python run_experiment.py --list                   # show available schedules
    python run_experiment.py --config my_lab.yaml     # your overrides on top of defaults

Anything given on the command line pre-fills the dialog; --no-dialog skips it.
Press ESCAPE at any point to abort cleanly - data already collected is kept.
"""
from __future__ import annotations

import argparse
import random
import sys
import traceback
from pathlib import Path

# Make the package importable no matter where the script is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from battery import Context                                    # noqa: E402
from battery.config import load_config                         # noqa: E402
from battery.dataio import session_dir, write_session_log      # noqa: E402
from battery.tasks import REGISTRY                             # noqa: E402
from battery.triggers import TriggerPort                       # noqa: E402

# battery.responses and battery.display are imported inside main(), after the
# --list / --help paths, so that those still work on a machine without
# PsychoPy and a missing install produces a readable message, not a traceback.


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="YAML file of overrides, merged over the defaults")
    p.add_argument("--schedule", help="which schedule to run (see --list)")
    p.add_argument("--demo", action="store_true",
                   help="tiny trial counts, windowed - for walking through the battery")
    p.add_argument("--autopilot", action="store_true",
                   help="synthetic participant, no keyboard needed (NOT real data)")
    p.add_argument("--list", action="store_true", help="list schedules and exit")
    p.add_argument("--no-dialog", action="store_true", help="skip the start-up dialog")
    p.add_argument("--no-fullscreen", action="store_true")
    p.add_argument("--seed", type=int, help="fix the trial-order random seed")
    for field in ("participant", "session", "phase", "run", "condition_code",
                  "experimenter"):
        p.add_argument(f"--{field.replace('_', '-')}")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    overrides = {}
    if args.no_fullscreen:
        overrides["display"] = {"fullscreen": False}
    cfg = load_config(args.config, demo=args.demo, cli_overrides=overrides)

    if args.list:
        print("\nAvailable schedules:\n")
        for name, sched in cfg.schedules.items():
            steps = ", ".join(f"{s['task']}:{s.get('label', '')}" for s in sched)
            print(f"  {name:<14} {steps}")
        print()
        return 0

    try:
        from battery.responses import QuitExperiment, Responder
        if args.autopilot:
            from battery.autopilot import AutoResponder
    except ImportError as exc:
        print(f"\nERROR: PsychoPy is not available in this Python ({exc}).")
        print("  Run this with the PsychoPy python - see run_windows.bat -")
        print("  or install it with:  pip install -r requirements.txt\n")
        return 1

    # ---------------------------------------------------------------- info
    info = {k: (v[0] if isinstance(v, list) else v)
            for k, v in cfg.session.dialog.items()}
    for field in list(info):
        value = getattr(args, field, None)
        if value is not None:
            info[field] = value

    if not args.no_dialog:
        from psychopy import gui
        fields = {}
        for key, default in cfg.session.dialog.items():
            supplied = getattr(args, key, None)
            fields[key] = supplied if supplied is not None else default
        dlg = gui.DlgFromDict(fields, title=f"{cfg.session.study_name} - session setup",
                              sortKeys=False)
        if not dlg.OK:
            print("cancelled at the setup dialog.")
            return 1
        info.update(fields)

    if not str(info.get("participant", "")).strip():
        print("ERROR: a participant identifier is required.")
        return 1

    schedule_name = args.schedule or cfg.session.default_schedule
    if schedule_name not in cfg.schedules:
        print(f"ERROR: unknown schedule {schedule_name!r}. Try --list.")
        return 1
    schedule = cfg.schedules[schedule_name]

    seed = args.seed if args.seed is not None else _derive_seed(info, schedule_name)
    rng = random.Random(seed)

    print(f"\n{cfg.session.study_name}: {info['participant']} "
          f"session {info['session']} phase {info['phase']}")
    print(f"schedule: {schedule_name}  |  trial-order seed: {seed}\n")

    # ------------------------------------------------------------ hardware
    trig = TriggerPort(cfg)
    if args.autopilot:
        banner = "!" * 62
        print(f"\n{banner}")
        print("!!  AUTOPILOT: responses are SIMULATED. This is NOT real data.")
        print(f"{banner}\n")
        responder = AutoResponder(cfg, rng=random.Random(seed))
        responder.attach(trig)
        info["participant"] = f"AUTO{info['participant']}"
    else:
        responder = Responder(cfg)
    display = None
    ctx = None
    out_dir = session_dir(cfg, info)
    status = "completed"

    try:
        from battery.display import Display
        display = Display(cfg, trig, responder)

        ctx = Context(cfg=cfg, display=display, responder=responder, trig=trig,
                      rng=rng, info=info, out_dir=out_dir)
        ctx.note(schedule=schedule_name, seed=seed, autopilot=bool(args.autopilot))

        # Participant-facing welcome. Deliberately free of the schedule name
        # and any other internal label: the participant is blind to condition,
        # and "post_tus" on screen would tell them where they are in the study.
        n_parts = len(schedule)
        display.instruction_screen(
            heading="Welcome, and thank you",
            body=("There are {n} short parts to get through. Each one is "
                  "explained on screen before it starts, and there is a "
                  "practice run for anything new.\n\n"
                  "You can take a break between parts, and inside the longer "
                  "parts, for as long as you like. Nothing here is a test of "
                  "you – if something is unclear, just ask.\n\n"
                  "Please keep your eyes on the cross in the middle of the "
                  "screen whenever one is showing, and try to stay still and "
                  "relaxed."
                  ).format(n=n_parts),
            footer="Press SPACE when you are ready to start.",
            min_advance_s=2.0,
        )

        for step in schedule:
            task_name = step["task"]
            kwargs = {k: v for k, v in step.items() if k != "task"}
            print(f"\n>>> {task_name}  {kwargs}")
            REGISTRY[task_name](ctx, **kwargs)

        display.instruction_screen(
            heading="That is everything",
            body=("All parts are finished. Thank you – that was the whole "
                  "session.\n\nPlease sit still for a moment while the "
                  "experimenter comes in."),
            footer="Press SPACE to finish.",
            min_advance_s=1.5,
        )

    except QuitExperiment:
        status = "aborted_by_experimenter"
        print("\n!! aborted with the quit key. Data collected so far has been saved.")
    except Exception:                                  # noqa: BLE001
        status = "error"
        traceback.print_exc()
    finally:
        entries = list(ctx.log) if ctx is not None else []
        try:
            log_path = write_session_log(
                cfg, info, out_dir,
                [{"status": status, "schedule": schedule_name}] + list(entries),
            )
            print(f"\nsession log: {log_path}")
        except Exception:                              # noqa: BLE001
            traceback.print_exc()
        if args.autopilot and hasattr(responder, "dump"):
            try:
                print("autopilot log:", responder.dump(out_dir / "autopilot_injected.json"))
            except Exception:                          # noqa: BLE001
                pass
        if display is not None:
            display.close()
        trig.close()
        print(f"data folder: {out_dir}")
        print(f"status: {status}\n")

    return 0 if status == "completed" else 2


def _derive_seed(info, schedule_name):
    """A reproducible seed from the session identifiers.

    Re-running the same participant/session/schedule reproduces the same
    trial order, which makes a crashed session recoverable; different
    sessions get different orders. Uses crc32 rather than hash(), because
    Python randomises string hashing per process.
    """
    import zlib
    key = f"{info.get('participant')}|{info.get('session')}|{schedule_name}"
    return zlib.crc32(key.encode("utf-8")) % (2 ** 31)


if __name__ == "__main__":
    sys.exit(main())
