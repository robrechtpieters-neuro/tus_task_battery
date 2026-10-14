"""Task 4 - resting-state EEG.

Three minutes eyes-open on a fixation cross, three minutes eyes-closed.
No behaviour is collected; the point is a clean, task-free baseline for
spectral and aperiodic measures.

The eyes-closed period ends with a tone, because a participant with their
eyes shut has no way of knowing the block is over. If the sound backend is
unavailable the program says so and falls back to the experimenter telling
them - it does not crash.
"""
from __future__ import annotations

from .. import trials as trial_lists

FIELDS = [
    "period", "kind", "requested_s", "actual_s",
    "start_clock_s", "end_clock_s", "trigger_start", "trigger_end",
]

INTRO = {
    "eyes_open": (
        "Rest with your eyes open",
        "Nothing to do for the next {minutes:.0f} minutes.\n\n"
        "Look at the cross in the middle and let your mind wander. Blink "
        "normally \u2013 you do not have to hold your eyes still.\n\n"
        "Just try to stay reasonably still, and stay awake.",
    ),
    "eyes_closed": (
        "Rest with your eyes closed",
        "When you press SPACE, please close your eyes and keep them closed.\n\n"
        "You will hear a tone after about {minutes:.0f} minutes. That is when "
        "you can open them again \u2013 nothing else will happen before then.\n\n"
        "Stay comfortable, stay still, and stay awake.",
    ),
}


def run(ctx, label="restpre"):
    cfg = ctx.cfg
    d = ctx.display
    r = cfg.tasks.resting

    periods = trial_lists.resting_periods(cfg)
    rec = ctx.recorder("resting", label, FIELDS)
    ctx.trig.send("task_start")

    try:
        for index, period in enumerate(periods):
            kind = period["kind"]
            duration = period["duration_s"]
            heading, body = INTRO[kind]
            d.instruction_screen(
                heading=heading,
                body=body.format(minutes=duration / 60.0),
                footer="Press SPACE when you are settled.",
                min_advance_s=1.5,
            )
            d.countdown(message="Starting")

            start_trigger = f"rest_{kind}_start"
            end_trigger = f"rest_{kind}_end"
            stims = [d.fixation] if kind == "eyes_open" else []

            start = d.show(d.frames(duration), stims=stims, trigger=start_trigger,
                           photodiode=True)
            end = d.show(1, stims=stims, trigger=end_trigger, photodiode=True)

            if kind == "eyes_closed" and r.beep_at_end:
                _beep(cfg)
                d.instruction_screen(
                    heading="You can open your eyes",
                    body="That is the resting recording done.",
                    footer="Press SPACE to continue.",
                    min_advance_s=1.0,
                )

            rec.write({
                "onset_clock_s": round(start, 6),
                "period": index,
                "kind": kind,
                "requested_s": duration,
                "actual_s": round(end - start, 4),
                "start_clock_s": round(start, 6),
                "end_clock_s": round(end, 6),
                "trigger_start": ctx.trig.resolve(start_trigger),
                "trigger_end": ctx.trig.resolve(end_trigger),
            })
    finally:
        ctx.trig.send("task_end")
        rec.close()

    print(f"\n--- resting [{label}] --- {len(periods)} period(s) recorded\n")
    ctx.note(task="resting", label=label, file=str(rec.csv_path))
    return rec.csv_path


def _beep(cfg):
    r = cfg.tasks.resting
    try:
        from psychopy import sound, core
        tone = sound.Sound(value=float(r.beep_hz), secs=float(r.beep_s))
        tone.play()
        core.wait(float(r.beep_s) + 0.1)
    except Exception as exc:                           # noqa: BLE001
        print(f"!! could not play the end-of-block tone ({exc}).")
        print("!! Tell the participant to open their eyes.")
