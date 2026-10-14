"""Task 2 - self-timed action initiation.

A colour cue names the required delay. The fixation cross then disappears -
that offset is the START event - and the participant presses at the
instructed delay with no go-signal of any kind::

    [fix] CUE(colour = delay) --0.8-1.2 s-- fixation OFF --> press at delay

Hand alternates by block. The prediction is asymmetric: dentate inactivation
in monkeys delayed *ipsiversive* self-timed responses, so right-cerebellar
stimulation should affect the RIGHT hand more than the left.

Measures: produced interval, signed error, and trial-to-trial variability
(the CV, from which clock vs motor variance is separated offline).
"""
from __future__ import annotations

from statistics import mean, pstdev

from .. import trials as trial_lists

FIELDS = [
    "block_index", "hand", "is_practice", "trial_in_block",
    "delay_label", "delay_s", "cue_to_start_s", "iti_s",
    "cue_clock_s", "start_clock_s",
    "start_rel_predicted_s", "start_rel_measured_s", "n_premature",
    "produced_s", "error_s", "error_pct", "responded", "timed_out",
    "response_key", "trigger_cue", "trigger_start",
]

def _show_instructions(ctx, hand, key):
    """Show the three cue colours as actual squares beside their delays.

    Naming the colours in text was not enough: the participant has to map
    three colours onto three delays, so the colours themselves are shown.
    """
    d = ctx.display
    st = ctx.cfg.tasks.self_timing
    swatches = []
    for label in st.delays_s:
        seconds = float(st.delays_s[label])
        swatches.append((st.cue_colors[label],
                         "wait {s:.1f} seconds".format(s=seconds)))

    d.instruction_screen(
        heading="Time it yourself",
        body=("In this part you decide when to press \u2013 nothing tells you.\n\n"
              "A coloured square tells you how long to wait:"),
        swatches=swatches,
    )
    d.instruction_screen(
        heading="Your starting signal",
        body=("After the coloured square, the cross stays on screen for a "
              "moment and then DISAPPEARS.\n\n"
              "The moment the cross disappears is your starting signal. From "
              "then, wait the time the colour asked for, and press the {key} "
              "key with your {hand} index finger.\n\n"
              "Please do not count out loud, tap your foot, or nod along. Just "
              "use your own sense of how long the interval feels."
              ).format(key=key, hand=hand),
        footer=("Rest your {hand} index finger on the {key} key.  "
                "Press SPACE when you are ready.").format(key=key, hand=hand),
    )

def _show_block_note(ctx, is_practice):
    """The one short page shown before each block."""
    if is_practice:
        ctx.display.instruction_screen(
            heading="Practice first",
            body=("These first few are practice, so you can get a feel for the "
                  "three delays.\n\nAfter each one you will be told whether you "
                  "were early, late or about right."),
            footer="Press SPACE to start practising.",
        )
    else:
        ctx.display.instruction_screen(
            heading="Now the real blocks",
            body=("From here there is no feedback \u2013 you will not be told how "
                  "you did.\n\nThat is deliberate, not a fault. Keep using the "
                  "same three delays, and do not worry about being exact."),
            footer="Press SPACE to begin.",
        )


def run(ctx, label="pre", practice=True, session_number=None):
    cfg = ctx.cfg
    d = ctx.display
    r = ctx.responder
    st = cfg.tasks.self_timing

    if session_number is None:
        try:
            session_number = int(ctx.info.get("session", 1))
        except (TypeError, ValueError):
            session_number = 1

    cues = {lbl: d.square(col, st.cue_size) for lbl, col in st.cue_colors.items()}
    blocks = trial_lists.self_timing_blocks(cfg, ctx.rng, session_number, practice)
    rec = ctx.recorder("selftiming", label, FIELDS)

    ctx.trig.send("task_start")

    try:
        for block_index, block in enumerate(blocks):
            hand = block["hand"]
            resp_keys_block = r.keys_for(hand)
            key = resp_keys_block[0].upper()
            hand_changed = (block_index == 0
                            or blocks[block_index - 1]["hand"] != hand)

            # The colour legend and the start-signal explanation are only
            # worth showing when the hand changes; repeating them before
            # every block would be tedious.
            if hand_changed:
                if block_index:
                    d.instruction_screen(
                        heading="Now the other hand",
                        body=("The next blocks use your {hand} hand.\n\n"
                              "Get comfortable before you carry on \u2013 there "
                              "is no hurry.").format(hand=hand),
                        footer="Press SPACE when you are settled.",
                        min_advance_s=1.5,
                    )
                _show_instructions(ctx, hand, key)
            _show_block_note(ctx, block["is_practice"])
            d.countdown()
            ctx.trig.send("block_start")

            resp_keys = resp_keys_block
            for trial in block["trials"]:
                row = _run_trial(ctx, block_index, block, trial, cues, resp_keys)
                rec.write(row)

            ctx.trig.send("block_end")

        d.instruction_screen(
            heading="That part is finished",
            body="Well done. Rest for as long as you like.",
            footer="Press SPACE to continue.",
            min_advance_s=1.5,
        )
    finally:
        ctx.trig.send("task_end")
        summary = _summarise(rec.csv_path)
        rec.close(summary=summary)
        _print_summary(label, summary)

    ctx.note(task="selftiming", label=label, file=str(rec.csv_path), summary=summary)
    return rec.csv_path


# ---------------------------------------------------------------------------
def _run_trial(ctx, block_index, block, trial, cues, resp_keys):
    cfg = ctx.cfg
    d = ctx.display
    r = ctx.responder
    st = cfg.tasks.self_timing

    hand = trial["hand"]
    delay_label = trial["delay_label"]
    delay_s = trial["delay_s"]

    # The response clock is zeroed at CUE onset, not at the start event, so
    # that presses made *before* the start event are timed on the same scale
    # and can be identified as premature rather than producing a nonsensical
    # negative reaction time.
    presses = []
    premature = []
    state = {"start_rel": None}

    def collect():
        for name, rt in r.get_presses(resp_keys):
            start_rel = state["start_rel"]
            if start_rel is None or rt < start_rel:
                premature.append((name, rt))     # pressed before the go moment
                continue
            presses.append((name, rt - start_rel))
            ctx.trig.send(f"st_response_{hand}")
        return bool(presses)          # first valid press ends the trial

    # --- inter-trial interval, fixation visible --------------------------
    d.show(d.frames(trial["iti_s"]), stims=[d.fixation])

    # --- cue --------------------------------------------------------------
    r.flush()
    cue_trigger = f"st_cue_{delay_label}_{hand}"
    cue_abs = d.show(d.frames(st.cue_duration_s),
                     stims=[d.fixation, cues[delay_label]],
                     trigger=cue_trigger, photodiode=True,
                     on_flip=[r.reset_clock], poll=collect)

    # --- fixation-only period, then the fixation goes out -----------------
    d.show(d.frames(trial["cue_to_start_s"]), stims=[d.fixation], poll=collect)

    # The start event is a whole number of frames after the cue, so its time
    # on the response clock is known exactly before it happens. Setting it
    # here (rather than after the segment) is what lets `collect` tell a real
    # response from a premature one while the segment is still running.
    state["start_rel"] = d.actual_s(st.cue_duration_s) + d.actual_s(trial["cue_to_start_s"])

    start_trigger = f"st_start_{hand}"
    start_abs = d.show(
        d.frames(st.max_response_s), stims=[],          # blank = fixation OFF
        trigger=start_trigger, photodiode=True, poll=collect,
    )
    # Measured, as a check on the predicted value above.
    start_rel_measured = start_abs - cue_abs

    # --- score ------------------------------------------------------------
    responded = bool(presses)
    produced = presses[0][1] if responded else None
    error_s = (produced - delay_s) if responded else None
    error_pct = (100.0 * error_s / delay_s) if responded else None

    # --- practice feedback -------------------------------------------------
    if block["is_practice"]:
        if not responded:
            msg = "No press that time.\n\nTry to press at the delay the colour asked for."
        elif abs(error_pct) <= float(st.practice.good_window_pct):
            msg = "About right\n\nyou waited {p:.1f} s   (asked for {t:.1f} s)".format(
                p=produced, t=delay_s)
        elif error_s < 0:
            msg = "A little early\n\nyou waited {p:.1f} s   (asked for {t:.1f} s)".format(
                p=produced, t=delay_s)
        else:
            msg = "A little late\n\nyou waited {p:.1f} s   (asked for {t:.1f} s)".format(
                p=produced, t=delay_s)
        d.message(msg, duration_s=st.practice.feedback_duration_s)

    return {
        "onset_clock_s": round(cue_abs, 6),
        "block_index": block_index,
        "hand": hand,
        "is_practice": int(block["is_practice"]),
        "trial_in_block": trial["trial_in_block"],
        "delay_label": delay_label,
        "delay_s": delay_s,
        "cue_to_start_s": round(trial["cue_to_start_s"], 4),
        "iti_s": round(trial["iti_s"], 4),
        "cue_clock_s": round(cue_abs, 6),
        "start_clock_s": round(start_abs, 6),
        "start_rel_predicted_s": round(state["start_rel"], 6),
        "start_rel_measured_s": round(start_rel_measured, 6),
        "n_premature": len(premature),
        "produced_s": round(produced, 6) if responded else "",
        "error_s": round(error_s, 6) if responded else "",
        "error_pct": round(error_pct, 3) if responded else "",
        "responded": int(responded),
        "timed_out": int(not responded),
        "response_key": presses[0][0] if responded else "",
        "trigger_cue": ctx.trig.resolve(cue_trigger),
        "trigger_start": ctx.trig.resolve(start_trigger),
    }


# ---------------------------------------------------------------------------
def _summarise(csv_path):
    import csv

    cells = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["is_practice"] == "1" or row["responded"] != "1" or not row["produced_s"]:
                continue
            key = f"{row['hand']}_{row['delay_label']}"
            cells.setdefault(key, {"target_s": float(row["delay_s"]), "produced": []})
            cells[key]["produced"].append(float(row["produced_s"]))

    out = {}
    for key, cell in cells.items():
        vals = cell["produced"]
        m = mean(vals)
        sd = pstdev(vals) if len(vals) > 1 else 0.0
        out[key] = {
            "n": len(vals),
            "target_ms": round(cell["target_s"] * 1000, 1),
            "mean_produced_ms": round(m * 1000, 1),
            "bias_ms": round((m - cell["target_s"]) * 1000, 1),
            "sd_ms": round(sd * 1000, 1),
            "cv": round(sd / m, 4) if m else None,
        }
    return out


def _print_summary(label, summary):
    print(f"\n--- self-timing [{label}] ---")
    print(f"{'cell':<16}{'n':>5}{'target':>9}{'produced':>10}{'bias':>8}{'SD':>8}{'CV':>8}")
    for key, s in sorted(summary.items()):
        print(
            f"{key:<16}{s['n']:>5}{s['target_ms']:>9.0f}{s['mean_produced_ms']:>10.0f}"
            f"{s['bias_ms']:>+8.0f}{s['sd_ms']:>8.0f}{(s['cv'] or 0):>8.3f}"
        )
    print()
