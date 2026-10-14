"""Trial-list construction.

Deliberately kept as plain functions with no PsychoPy imports, so you can
inspect - or unit-test - exactly what the participant will get without
opening a window::

    from battery.config import load_config
    from battery import trials
    import random
    cfg = load_config()
    blocks = trials.temporal_orienting_blocks(cfg, random.Random(1), run_index=0)
    print(len(blocks), [b["context"] for b in blocks])
    print(blocks[0]["trials"][:5])

This is the file to edit if you want to change *what* happens on each
trial. ``tasks/`` decides how it is drawn; this decides what it is.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _uniform(rng, span):
    lo, hi = span
    return rng.uniform(float(lo), float(hi))


def _shuffle_constrained(rng, items, is_special, max_run=2, first_must_be_normal=True):
    """Shuffle, avoiding long runs of 'special' trials (invalid / catch).

    Built constructively rather than by shuffle-and-retry. Once catch trials
    are 25 % of all trials and a quarter of the rest are invalid, ~43 % of a
    block is 'special', and random retries essentially never satisfy
    max_run = 2 - the old version silently gave up and returned an
    unconstrained order, which is how runs of seven appeared.

    Specials are dealt into the gaps between normal trials, with each gap
    capped at ``max_run``. That always succeeds when
    ``n_special <= (n_normal + 1) * max_run``; if the request is genuinely
    infeasible it falls back to a plain shuffle rather than hanging.
    """
    items = list(items)
    normal = [x for x in items if not is_special(x)]
    special = [x for x in items if is_special(x)]
    rng.shuffle(normal)
    rng.shuffle(special)

    n_gaps = len(normal) + 1
    first_gap = 1 if first_must_be_normal else 0
    usable = n_gaps - first_gap
    if not normal or len(special) > usable * max_run:
        rng.shuffle(items)
        return items

    # Deal specials one at a time into a randomly chosen gap that still has
    # room, so clustering is spread rather than front-loaded.
    gaps = [[] for _ in range(n_gaps)]
    open_gaps = list(range(first_gap, n_gaps))
    for item in special:
        i = rng.choice(open_gaps)
        gaps[i].append(item)
        if len(gaps[i]) >= max_run:
            open_gaps.remove(i)

    order = []
    for i, item in enumerate(normal):
        order.extend(gaps[i])
        order.append(item)
    order.extend(gaps[-1])
    return order


# ---------------------------------------------------------------------------
# Task 1 - temporal orienting
# ---------------------------------------------------------------------------
def temporal_orienting_blocks(cfg, rng, run_index: int = 0, practice: bool = False):
    """Return the blocks for one run.

    Context (rhythm / interval) is BLOCKED; SOA is randomised WITHIN a block.

    That split matters and is not arbitrary. In Breska & Ivry the cued
    interval has to be read off the stimulus stream on every trial - the
    rhythm's period, or the gap between the two interval cues. If SOA were
    blocked, block context alone would predict the target and the cue stream
    would be redundant, which is exactly the inference the task is built to
    avoid. Both published versions randomise SOA within block.

    Context order is rotated by run number, so no context is always first and
    order cannot be confounded with time since stimulation.
    """
    t = cfg.tasks.temporal_orienting
    contexts = list(t.context_order)
    if t.rotate_block_order_by_run and contexts:
        k = run_index % len(contexts)
        contexts = contexts[k:] + contexts[:k]

    per_context = {}
    for context in set(contexts):
        n_blocks = sum(1 for c in contexts if c == context)
        per_context[context] = _temporal_orienting_trials(
            cfg, rng, context, n_blocks, practice=practice)

    blocks = []
    taken = {}
    for block_index, context in enumerate(contexts):
        i = taken.get(context, 0)
        taken[context] = i + 1
        chunk = per_context[context][i]
        for j, trial in enumerate(chunk):
            trial["trial_in_block"] = j
        blocks.append({
            "block_index": block_index,
            "context": context,
            "n_cues": int(t.n_cues[context]),
            "is_practice": bool(practice),
            "trials": chunk,
        })
    return blocks


def _temporal_orienting_trials(cfg, rng, context: str, n_blocks: int,
                               practice: bool = False):
    """Build this context's trials for the whole run, dealt into n_blocks.

    Proportions follow Breska & Ivry (2020): of the target trials, 75 % are
    valid and 25 % invalid (the target arrives at the OTHER SOA); catch
    trials, on which no target appears at all, are 25 % of all trials.
    """
    t = cfg.tasks.temporal_orienting
    tr_cfg = t.practice_trials if practice else t.trials

    n_target = int(tr_cfg.per_cell)
    n_valid = int(round(n_target * float(t.trials.valid_proportion)))
    n_invalid = n_target - n_valid
    catch_p = float(t.trials.catch_proportion)
    # catch is a proportion of ALL trials in the cell, not of the target trials
    n_catch = int(round(n_target * catch_p / (1.0 - catch_p)))

    proto = []
    for soa_label in t.soa_s:
        soa = float(t.soa_s[soa_label])
        other_label = "long" if soa_label == "short" else "short"
        other_soa = float(t.soa_s[other_label])
        # Valid: the target arrives one cued SOA after the warning signal.
        for _ in range(n_valid):
            proto.append({"soa_label": soa_label, "soa_s": soa,
                          "validity": "valid", "is_catch": False,
                          "target_soa_s": soa})
        # Invalid: it arrives at the other SOA - late after a short cue,
        # early after a long one.
        for _ in range(n_invalid):
            proto.append({"soa_label": soa_label, "soa_s": soa,
                          "validity": "invalid", "is_catch": False,
                          "target_soa_s": other_soa})
        # Catch: no target at all, so pure anticipation cannot pay off.
        for _ in range(n_catch):
            proto.append({"soa_label": soa_label, "soa_s": soa,
                          "validity": "catch", "is_catch": True,
                          "target_soa_s": None})

    # Deal into blocks FIRST, so every block holds the same mix of cells,
    # then shuffle within each block. Doing it the other way round (shuffle
    # the pool, then deal) silently breaks the clustering constraint,
    # because trials that were adjacent after the shuffle end up in
    # different blocks.
    rng.shuffle(proto)
    chunks = [[] for _ in range(max(1, n_blocks))]
    for i, item in enumerate(proto):
        chunks[i % len(chunks)].append(item)

    out = []
    for chunk in chunks:
        order = _shuffle_constrained(
            rng, chunk, is_special=lambda tr: tr["validity"] != "valid", max_run=2
        )
        block_trials = []
        for tr in order:
            trial = dict(tr)
            trial["context"] = context
            trial["is_practice"] = bool(practice)
            trial["iti_s"] = _uniform(rng, t.iti_s)
            soa = trial["soa_s"]
            if context == "interval":
                # Breska & Ivry use two discrete multipliers, not a continuous
                # range, so the stream is non-isochronous but the cued
                # interval is still unambiguous.
                trial["gap_s"] = soa * float(
                    rng.choice(list(t.interval_gap_multiplier)))
            else:
                trial["gap_s"] = soa      # rhythm: the warning continues the beat
            block_trials.append(trial)
        out.append(block_trials)
    return out


# ---------------------------------------------------------------------------
# Task 2 - self-timed action initiation
# ---------------------------------------------------------------------------
def self_timing_blocks(cfg, rng, session_number: int = 1, practice: bool = True):
    """One block per hand, each optionally preceded by a practice block.

    Hand order alternates with session number so that, across the three
    sessions of the crossover, hand order is not confounded with condition.
    """
    st = cfg.tasks.self_timing
    hands = list(st.hands)
    if st.alternate_hand_order_by_session and int(session_number) % 2 == 0:
        hands = hands[::-1]

    delay_labels = list(st.delays_s.keys())
    blocks = []
    for hand in hands:
        if practice and st.practice.enabled:
            blocks.append({
                "hand": hand,
                "is_practice": True,
                "trials": _self_timing_trials(
                    cfg, rng, hand, delay_labels,
                    int(st.practice.trials_per_delay), is_practice=True,
                ),
            })
        blocks.append({
            "hand": hand,
            "is_practice": False,
            "trials": _self_timing_trials(
                cfg, rng, hand, delay_labels,
                int(st.trials_per_cell), is_practice=False,
            ),
        })
    return blocks


def _self_timing_trials(cfg, rng, hand, delay_labels, n_per_delay, is_practice):
    st = cfg.tasks.self_timing
    proto = []
    for label in delay_labels:
        for _ in range(n_per_delay):
            proto.append({
                "delay_label": label,
                "delay_s": float(st.delays_s[label]),
                "hand": hand,
                "is_practice": is_practice,
            })
    rng.shuffle(proto)
    for i, tr in enumerate(proto):
        tr["trial_in_block"] = i
        tr["cue_to_start_s"] = _uniform(rng, st.cue_to_start_s)
        tr["iti_s"] = _uniform(rng, st.iti_s)
    return proto


# ---------------------------------------------------------------------------
# Task 3 - simple reaction time
# ---------------------------------------------------------------------------
def simple_rt_trials(cfg, rng):
    """Unpredictable foreperiods; nothing here is predictable by design."""
    srt = cfg.tasks.simple_rt
    trials = []
    for i in range(int(srt.n_trials)):
        trials.append({
            "trial_in_block": i,
            "foreperiod_s": _uniform(rng, srt.foreperiod_s),
            "iti_s": _uniform(rng, srt.iti_s),
        })
    return trials


# ---------------------------------------------------------------------------
# Task 4 - resting state
# ---------------------------------------------------------------------------
def resting_periods(cfg):
    r = cfg.tasks.resting
    return [{"kind": kind, "duration_s": float(r[f"{kind}_s"])} for kind in r.order]
