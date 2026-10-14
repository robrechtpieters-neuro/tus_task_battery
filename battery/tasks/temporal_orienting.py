"""Task 1 - temporal orienting (the primary task).

Trial structure
---------------
RHYTHM block (cues, warning and target all one SOA apart)::

    [fix] cue --SOA-- cue --SOA-- cue --SOA-- WS --SOA-- TARGET
                                              ^^          ^^
                                          warning     expected moment

INTERVAL block (one isolated interval, then a rhythm-breaking gap)::

    [fix] cue --SOA-- cue -----1.5-2.5 x SOA----- WS --SOA-- TARGET

On valid trials (75 %) the target arrives one block-SOA after the warning.
On invalid trials it arrives at the *other* SOA - late in short blocks,
early in long blocks. Catch trials have no target at all.

The primary outcome is the validity effect, RT(invalid) - RT(valid),
compared between the rhythm and interval contexts.
"""
from __future__ import annotations

import time
from statistics import median

from .. import trials as trial_lists

FIELDS = [
    "block_index", "context", "is_practice", "soa_label", "expected_soa_s",
    "trial_in_block",
    "validity", "is_catch", "target_soa_s", "gap_s", "iti_s",
    "first_cue_clock_s", "warning_clock_s", "target_clock_s",
    "warning_rel_s", "target_rel_s",
    "response_key", "rt_s", "responded", "anticipation", "miss", "false_alarm",
    "n_presses", "all_press_rel_target_s",
    "trigger_warning", "trigger_target",
]

BLOCK_INTRO = {
    "rhythm": (
        "Rhythm block",
        "The red squares arrive in a STEADY BEAT, like a metronome.\n\n"
        "The white square keeps that same beat going, so expect the green "
        "square one beat after the white one.\n\n"
        "The beat is faster on some goes and slower on others. Each go tells "
        "you its own speed \u2013 listen to that go, not the last one."
    ),
    "interval": (
        "Interval block",
        "Two red squares show you a single GAP.\n\n"
        "Then there is a longer pause. Ignore that pause \u2013 it is not the "
        "timing. After the white square, expect the green square one GAP later.\n\n"
        "The gap is shorter on some goes and longer on others. Each go shows "
        "you its own gap."
    ),
}


def _show_instructions(ctx, key, hand):
    """Two short pages, showing the actual colours rather than naming them."""
    d = ctx.display
    t = ctx.cfg.tasks.temporal_orienting
    d.instruction_screen(
        heading="Watch for the green square",
        body=("Keep your eyes on the small cross in the middle of the screen.\n\n"
              "On each go, a few coloured squares appear one after another, "
              "always in the same place:"),
        swatches=[
            (t.cue.color,
             "RED squares come first. They tell you WHEN to expect the green one."),
            (t.warning.color,
             "A WHITE square means the green one is about to arrive."),
            (t.target.color,
             "The GREEN square is the one you respond to."),
        ],
    )
    d.instruction_screen(
        heading="How to respond",
        body=("When the green square appears, press the {key} key with your "
              "{hand} index finger, as fast as you can.\n\n"
              "The red squares are worth using: they predict when the green "
              "square will appear, and you will be faster if you pay attention "
              "to them.\n\n"
              "The timing changes from one go to the next \u2013 some are quick, "
              "some are slow. Every go shows you its own timing, so watch the "
              "red squares each time rather than assuming it stays the same."
              ).format(key=key, hand=hand),
    )
    d.instruction_screen(
        heading="Two things that are meant to happen",
        body=("Sometimes the green square arrives at a different moment than "
              "you expected. That is deliberate and you have done nothing "
              "wrong \u2013 just respond when you see it.\n\n"
              "On about one go in four, no green square arrives at all. Those "
              "are there on purpose, to stop guessing from paying off. Wait "
              "for the green square and press only when you actually see it."),
        footer=("Rest your {hand} index finger on the {key} key now.  "
                "Press SPACE when you are ready.").format(key=key, hand=hand),
    )


def run(ctx, label="run0", run_index=0, practice=False):
    cfg = ctx.cfg
    d = ctx.display
    r = ctx.responder
    t = cfg.tasks.temporal_orienting

    resp_keys = r.keys_for(t.response_hand)
    antic_s = float(cfg.response.anticipation_s)

    cue_sq = d.square(t.cue.color, t.cue.size)
    ws_sq = d.square(t.warning.color, t.warning.size)
    tgt_sq = d.square(t.target.color, t.target.size)

    blocks = trial_lists.temporal_orienting_blocks(cfg, ctx.rng, run_index)
    rec = ctx.recorder("temporalorienting", label, FIELDS)

    _show_instructions(ctx, resp_keys[0].upper(), t.response_hand)
    ctx.trig.send("task_start")

    block_times = []
    try:
        if practice:
            # Breska & Ivry run a short practice block per condition before
            # testing, and check the participant can state the timing rule.
            # Without it the first real trials are spent working out the task.
            _run_practice(ctx, run_index, cue_sq, ws_sq, tgt_sq,
                          resp_keys, antic_s)

        for i, block in enumerate(blocks):
            heading, body = BLOCK_INTRO[block["context"]]
            d.instruction_screen(
                heading=heading,
                body=body,
                footer="Block {n} of {N}.  Press SPACE to begin.".format(
                    n=i + 1, N=len(blocks)),
            )
            d.countdown()
            ctx.trig.send("block_start")

            t_block = time.monotonic()
            for trial in block["trials"]:
                row = _run_trial(ctx, block, trial, cue_sq, ws_sq, tgt_sq,
                                 resp_keys, antic_s)
                rec.write(row)
            block_times.append(time.monotonic() - t_block)

            ctx.trig.send("block_end")
            if t.break_between_blocks and i < len(blocks) - 1:
                _break_screen(ctx, i + 1, len(blocks), block_times,
                              resp_keys=resp_keys, hand=t.response_hand)

        d.instruction_screen(
            heading="That part is finished",
            body="Well done. Have a rest for as long as you need.",
            footer="Press SPACE to continue.",
            min_advance_s=1.5,
        )
    finally:
        ctx.trig.send("task_end")
        summary = _summarise(rec.csv_path)
        rec.close(summary=summary)
        _print_summary(label, summary)

    ctx.note(task="temporalorienting", label=label, run_index=run_index,
             file=str(rec.csv_path), summary=summary)
    return rec.csv_path


# ---------------------------------------------------------------------------
def _run_practice(ctx, run_index, cue_sq, ws_sq, tgt_sq, resp_keys, antic_s):
    """A short practice pass, one block per context, with a comprehension check.

    Practice trials are NOT written to the data file - they are discarded,
    exactly as in the published procedure.
    """
    d = ctx.display
    blocks = trial_lists.temporal_orienting_blocks(
        ctx.cfg, ctx.rng, run_index, practice=True)

    d.instruction_screen(
        heading="Let us practise first",
        body=("A short practice run comes first, so you can get used to the "
              "timing before anything is recorded.\n\n"
              "Nothing here is scored. Ask the experimenter anything you like "
              "during the practice."),
        footer="Press SPACE to start practising.",
    )

    for i, block in enumerate(blocks):
        heading, body = BLOCK_INTRO[block["context"]]
        d.instruction_screen(
            heading="Practice – " + heading.lower(),
            body=body,
            footer="Practice block {n} of {N}.  Press SPACE to begin.".format(
                n=i + 1, N=len(blocks)),
        )
        d.countdown()
        for trial in block["trials"]:
            _run_trial(ctx, block, trial, cue_sq, ws_sq, tgt_sq,
                       resp_keys, antic_s)

    # The comprehension check the papers describe: the experimenter confirms
    # the participant can state the rule before real data is collected.
    d.instruction_screen(
        heading="Before we start for real",
        body=("Please tell the experimenter, in your own words:\n\n"
              "1.  What tells you WHEN the green square will arrive?\n"
              "2.  What should you do when no green square comes?\n\n"
              "If either is unclear, the practice can simply be run again – "
              "that is much better than guessing through the real blocks."),
        footer="Experimenter: press SPACE when the participant has answered both.",
        min_advance_s=2.0,
    )


# ---------------------------------------------------------------------------
def _break_screen(ctx, done, total, block_times, resp_keys=None, hand="right"):
    """A break between blocks, with an honest estimate of what is left.

    The participant can also ask for the instructions again from here. Without
    that, someone who has lost the thread mid-run has no way back except to
    interrupt the session, and is likely to just guess instead.
    """
    d = ctx.display
    left = ""
    if block_times:
        mins = (sum(block_times) / len(block_times)) * (total - done) / 60.0
        mins = max(1, round(mins))
        left = "About {m} minute{s} of this part left.\n\n".format(
            m=mins, s="" if mins == 1 else "s")

    reread = list(ctx.cfg.response.keymap.get("reread", ["r"]))
    advance = list(ctx.cfg.response.keymap.advance)
    while True:
        key = d.instruction_screen(
            heading="Take a break",
            body=("Block {d} of {t} finished.\n\n{left}"
                  "Rest your eyes, sit back, move your shoulders. "
                  "The break is as long as you want it to be."
                  ).format(d=done, t=total, left=left),
            footer=("Press SPACE when you are ready to carry on"
                    "   ·   press R to read the instructions again."),
            min_advance_s=2.0,
            keys=advance + reread,
        )
        if key not in reread:
            return
        _show_instructions(ctx, (resp_keys or ["j"])[0].upper(), hand)


# ---------------------------------------------------------------------------
def _run_trial(ctx, block, trial, cue_sq, ws_sq, tgt_sq, resp_keys, antic_s):
    cfg = ctx.cfg
    d = ctx.display
    r = ctx.responder
    t = cfg.tasks.temporal_orienting

    context = block["context"]
    # SOA varies trial to trial inside a block, so it is read from the trial.
    soa_label = trial["soa_label"]
    soa = float(trial["soa_s"])
    n_cues = block["n_cues"]
    is_catch = trial["is_catch"]
    # On catch trials nothing appears, but we still mark the moment the
    # target was expected, so the EEG has an event at the critical time.
    target_soa = float(trial["target_soa_s"]) if not is_catch else soa

    presses = []
    state = {"target_rel": None}

    def collect():
        for name, rt in r.get_presses(resp_keys):
            presses.append((name, rt))
            tr = state["target_rel"]
            late_enough = tr is not None and (rt - tr) >= antic_s
            ctx.trig.send("to_response" if late_enough else "to_anticipation")
        return False

    def collect_and_maybe_stop():
        collect()
        if not t.end_trial_on_response:
            return False
        tr = state["target_rel"]
        if tr is None:
            return False
        return any((rt - tr) >= antic_s for _, rt in presses)

    # --- inter-trial interval -------------------------------------------
    d.blank(d.frames(trial["iti_s"]))

    # --- trial starts: fixation appears and the response clock is zeroed --
    r.flush()
    t0 = d.show(d.frames(t.fixation_lead_s), stims=[d.fixation],
                on_flip=[r.reset_clock], poll=collect)

    # --- cue train --------------------------------------------------------
    first_cue_abs = None
    cue_on_frames = d.frames(t.cue.duration_s)
    for i in range(n_cues):
        onset = d.show(cue_on_frames, stims=[d.fixation, cue_sq],
                       trigger="to_cue_first" if i == 0 else "to_cue_other",
                       photodiode=True, poll=collect)
        if i == 0:
            first_cue_abs = onset
        # Gap to the next event. After the final cue this is the rhythm-
        # breaking pause in interval blocks, or one more beat in rhythm blocks.
        gap = (trial["gap_s"] if i == n_cues - 1 else soa) - t.cue.duration_s
        d.show(d.frames(gap), stims=[d.fixation], poll=collect)

    # --- warning signal ---------------------------------------------------
    ws_trigger = f"to_warning_{context}_{soa_label}"
    ws_abs = d.show(d.frames(t.warning.duration_s), stims=[d.fixation, ws_sq],
                    trigger=ws_trigger, photodiode=True, poll=collect)

    # --- wait for the target ---------------------------------------------
    d.show(d.frames(target_soa - t.warning.duration_s), stims=[d.fixation],
           poll=collect)

    # --- target (or the marked expected moment on catch trials) ----------
    if is_catch:
        tgt_trigger = f"to_catch_{context}_{soa_label}"
        tgt_abs = d.show(d.frames(t.target.duration_s), stims=[d.fixation],
                         trigger=tgt_trigger, poll=collect)
    else:
        tgt_trigger = f"to_target_{context}_{soa_label}_{trial['validity']}"
        tgt_abs = d.show(d.frames(t.target.duration_s),
                         stims=[d.fixation, tgt_sq], trigger=tgt_trigger,
                         photodiode=True, poll=collect)
    state["target_rel"] = tgt_abs - t0

    # --- response window --------------------------------------------------
    d.show(d.frames(t.response_window_s - t.target.duration_s),
           stims=[d.fixation], poll=collect_and_maybe_stop)

    # --- score ------------------------------------------------------------
    target_rel = state["target_rel"]
    rel = [(name, rt - target_rel) for name, rt in presses]
    anticipations = [x for x in rel if x[1] < antic_s]
    responses = [x for x in rel if x[1] >= antic_s]

    responded = bool(responses)
    rt_s = responses[0][1] if responded else ""
    response_key = responses[0][0] if responded else ""
    miss = (not is_catch) and (not responded)
    false_alarm = is_catch and bool(rel)

    # --- feedback ---------------------------------------------------------
    fb = None
    if t.feedback.show_false_alarm and false_alarm:
        fb = "No green square on that one - press only when you see it."
    elif t.feedback.show_anticipation and anticipations:
        fb = "Too early - wait for the green square."
    elif t.feedback.show_miss and miss:
        fb = "No response - please respond faster."
    if fb:
        d.message(fb, duration_s=t.feedback.duration_s)

    return {
        "onset_clock_s": round(t0, 6),
        "block_index": block["block_index"],
        "context": context,
        "is_practice": int(trial.get("is_practice", False)),
        "soa_label": soa_label,
        "expected_soa_s": soa,
        "trial_in_block": trial["trial_in_block"],
        "validity": trial["validity"],
        "is_catch": int(is_catch),
        "target_soa_s": "" if is_catch else target_soa,
        "gap_s": round(trial["gap_s"], 4),
        "iti_s": round(trial["iti_s"], 4),
        "first_cue_clock_s": round(first_cue_abs, 6),
        "warning_clock_s": round(ws_abs, 6),
        "target_clock_s": round(tgt_abs, 6),
        "warning_rel_s": round(ws_abs - t0, 6),
        "target_rel_s": round(target_rel, 6),
        "response_key": response_key,
        "rt_s": round(rt_s, 6) if responded else "",
        "responded": int(responded),
        "anticipation": int(bool(anticipations)),
        "miss": int(miss),
        "false_alarm": int(false_alarm),
        "n_presses": len(presses),
        "all_press_rel_target_s": ";".join(f"{v:.4f}" for _, v in rel),
        "trigger_warning": ctx.trig.resolve(ws_trigger),
        "trigger_target": ctx.trig.resolve(tgt_trigger),
    }


# ---------------------------------------------------------------------------
def _summarise(csv_path):
    """Median RTs and the validity effect, per context x SOA.

    Printed for the experimenter as an immediate data-quality check: if the
    validity effect is not positive in both contexts at baseline, something
    is wrong with the setup, not with the hypothesis.
    """
    import csv

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["responded"] == "1" and row["is_catch"] == "0" and row["rt_s"]:
                rows.append(row)

    out = {}
    for context in ("rhythm", "interval"):
        for soa in ("short", "long"):
            key = f"{context}_{soa}"
            rts = {"valid": [], "invalid": []}
            for row in rows:
                if row["context"] == context and row["soa_label"] == soa:
                    if row["validity"] in rts:
                        rts[row["validity"]].append(float(row["rt_s"]) * 1000.0)
            entry = {
                "n_valid": len(rts["valid"]),
                "n_invalid": len(rts["invalid"]),
                "median_rt_valid_ms": round(median(rts["valid"]), 1) if rts["valid"] else None,
                "median_rt_invalid_ms": round(median(rts["invalid"]), 1) if rts["invalid"] else None,
            }
            if rts["valid"] and rts["invalid"]:
                entry["validity_effect_ms"] = round(
                    median(rts["invalid"]) - median(rts["valid"]), 1
                )
            out[key] = entry
    return out


def _print_summary(label, summary):
    print(f"\n--- temporal orienting [{label}] ---")
    print(f"{'cell':<18}{'n val':>7}{'n inv':>7}{'RT val':>9}{'RT inv':>9}{'validity':>10}")
    for key, s in summary.items():
        print(
            f"{key:<18}{s['n_valid']:>7}{s['n_invalid']:>7}"
            f"{_fmt(s['median_rt_valid_ms']):>9}{_fmt(s['median_rt_invalid_ms']):>9}"
            f"{_fmt(s.get('validity_effect_ms')):>10}"
        )
    print("(validity effect = RT invalid - RT valid, in ms; should be positive)\n")


def _fmt(value):
    return "-" if value is None else f"{value:.0f}"
