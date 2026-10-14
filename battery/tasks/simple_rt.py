"""Task 3 - simple reaction time (the specificity control).

An unpredictable foreperiod, then a target. There is nothing to anticipate,
so this task should be *insensitive* to the manipulation. A null result here
is the intended outcome: it is what rules out generalised slowing, drowsiness
or discomfort as an explanation for any effect in the temporal orienting task.
"""
from __future__ import annotations

from statistics import median, pstdev

from .. import trials as trial_lists

FIELDS = [
    "trial_in_block", "foreperiod_s", "iti_s",
    "target_clock_s", "rt_s", "responded", "anticipation", "miss",
    "n_presses", "response_key", "trigger_target",
]

def _show_instructions(ctx, key, hand):
    d = ctx.display
    srt = ctx.cfg.tasks.simple_rt
    d.instruction_screen(
        heading="Just react",
        body=("Keep your eyes on the cross in the middle of the screen.\n\n"
              "After a while \u2013 you cannot tell how long \u2013 one square "
              "will appear:"),
        swatches=[(srt.target.color,
                   "the moment you see this, press the {key} key".format(key=key))],
    )
    d.instruction_screen(
        heading="Nothing to predict here",
        body=("There is no pattern to the timing in this part, so there is "
              "nothing to work out. Do not try to guess it.\n\n"
              "Simply keep your eyes on the cross, stay relaxed, and press as "
              "soon as you see the square. It is short."),
        footer=("Rest your {hand} index finger on the {key} key.  "
                "Press SPACE when you are ready.").format(key=key, hand=hand),
    )


def run(ctx, label="pre"):
    cfg = ctx.cfg
    d = ctx.display
    r = ctx.responder
    srt = cfg.tasks.simple_rt

    resp_keys = r.keys_for(srt.response_hand)
    antic_s = float(cfg.response.anticipation_s)
    tgt_sq = d.square(srt.target.color, srt.target.size)

    trials = trial_lists.simple_rt_trials(cfg, ctx.rng)
    rec = ctx.recorder("simplert", label, FIELDS)

    _show_instructions(ctx, resp_keys[0].upper(), srt.response_hand)
    d.countdown()
    ctx.trig.send("task_start")

    try:
        ctx.trig.send("block_start")
        for trial in trials:
            rec.write(_run_trial(ctx, trial, tgt_sq, resp_keys, antic_s))
        ctx.trig.send("block_end")

        d.instruction_screen(
            heading="That part is finished",
            body="Well done.",
            footer="Press SPACE to continue.",
            min_advance_s=1.5,
        )
    finally:
        ctx.trig.send("task_end")
        summary = _summarise(rec.csv_path)
        rec.close(summary=summary)
        print(f"\n--- simple RT [{label}] ---")
        print(f"  n = {summary.get('n', 0)}, median {summary.get('median_rt_ms', '-')} ms, "
              f"SD {summary.get('sd_ms', '-')} ms, "
              f"anticipations {summary.get('n_anticipations', 0)}, "
              f"misses {summary.get('n_misses', 0)}\n")

    ctx.note(task="simplert", label=label, file=str(rec.csv_path), summary=summary)
    return rec.csv_path


# ---------------------------------------------------------------------------
def _run_trial(ctx, trial, tgt_sq, resp_keys, antic_s):
    cfg = ctx.cfg
    d = ctx.display
    r = ctx.responder
    srt = cfg.tasks.simple_rt

    presses = []
    state = {"target_rel": None}

    def collect():
        for name, rt in r.get_presses(resp_keys):
            presses.append((name, rt))
            tr = state["target_rel"]
            ctx.trig.send("rt_response" if (tr is not None and rt - tr >= antic_s)
                          else "rt_anticipation")
        tr = state["target_rel"]
        if tr is None:
            return False
        return any((rt - tr) >= antic_s for _, rt in presses)

    d.blank(d.frames(trial["iti_s"]))

    r.flush()
    # Clock zeroed at the moment the fixation-only foreperiod begins.
    t0 = d.show(d.frames(trial["foreperiod_s"]), stims=[d.fixation],
                on_flip=[r.reset_clock], poll=collect)

    tgt_abs = d.show(d.frames(srt.target.duration_s), stims=[d.fixation, tgt_sq],
                     trigger="rt_target", photodiode=True, poll=collect)
    state["target_rel"] = tgt_abs - t0

    d.show(d.frames(srt.response_window_s - srt.target.duration_s),
           stims=[d.fixation], poll=collect)

    target_rel = state["target_rel"]
    rel = [(name, rt - target_rel) for name, rt in presses]
    responses = [x for x in rel if x[1] >= antic_s]
    anticipations = [x for x in rel if x[1] < antic_s]
    responded = bool(responses)

    return {
        "onset_clock_s": round(t0, 6),
        "trial_in_block": trial["trial_in_block"],
        "foreperiod_s": round(trial["foreperiod_s"], 4),
        "iti_s": round(trial["iti_s"], 4),
        "target_clock_s": round(tgt_abs, 6),
        "rt_s": round(responses[0][1], 6) if responded else "",
        "responded": int(responded),
        "anticipation": int(bool(anticipations)),
        "miss": int(not responded),
        "n_presses": len(presses),
        "response_key": responses[0][0] if responded else "",
        "trigger_target": ctx.trig.resolve("rt_target"),
    }


def _summarise(csv_path):
    import csv

    rts, n_ant, n_miss = [], 0, 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n_ant += int(row["anticipation"] or 0)
            n_miss += int(row["miss"] or 0)
            if row["responded"] == "1" and row["rt_s"]:
                rts.append(float(row["rt_s"]) * 1000.0)
    return {
        "n": len(rts),
        "median_rt_ms": round(median(rts), 1) if rts else None,
        "sd_ms": round(pstdev(rts), 1) if len(rts) > 1 else None,
        "n_anticipations": n_ant,
        "n_misses": n_miss,
    }
