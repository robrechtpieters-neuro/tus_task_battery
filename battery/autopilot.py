"""Synthetic participant, for dry runs and regression testing.

    python run_experiment.py --demo --autopilot --no-dialog

Runs the entire battery with no human at the keyboard, producing plausible
data. Use it to check a schedule end to end after editing the config, to
demonstrate the battery to a collaborator, or to regenerate example data
files for an analysis script.

How it knows when to respond
----------------------------
It listens to the trigger stream. Every stimulus trigger is sent on the flip
that puts the stimulus on screen, so the trigger tells the autopilot exactly
when a target appeared - and, for self-timing, which delay was cued. This
means the simulated responses are timed against the real presentation, and
the RTs that come out the far end of the data files are the ones the scoring
code actually computed.

It deliberately produces some anticipations, misses and catch-trial false
alarms, so those code paths get exercised too.

NOT for real data collection. The start-up banner says so, and every data
file it writes is stamped autopilot=True in its JSON sidecar.
"""
from __future__ import annotations

import random

from .responses import Responder


class AutoResponder(Responder):
    def __init__(self, cfg, rng=None, verbose: bool = True,
                 rt_mean=0.350, rt_sd=0.055,
                 p_miss=0.02, p_anticipate=0.02, p_catch_false_alarm=0.05,
                 timing_sd_frac=0.09, advance_dwell=0.4):
        super().__init__(cfg, verbose=False)
        # Stamped into every JSON sidecar as response_backend, so a data file
        # produced by the autopilot can never be mistaken for a real one.
        self.backend = "autopilot"
        self.rng = rng or random.Random(0)
        self.rt_mean, self.rt_sd = rt_mean, rt_sd
        self.p_miss = p_miss
        self.p_anticipate = p_anticipate
        self.p_catch_false_alarm = p_catch_false_alarm
        self.timing_sd_frac = timing_sd_frac
        self.advance_dwell = advance_dwell

        self._pending = []          # [(clock_time_to_fire, key), ...]
        # Every simulated press, as it was injected. Dumped next to the data
        # files so the recorded value can be compared against the intended one
        # - the only way to tell a scoring error from a harness artefact.
        self.injected = []
        self._advance_at = None
        self._cued_delay_s = None   # set by the most recent self-timing cue
        self._delays = {k: float(v) for k, v in cfg.tasks.self_timing.delays_s.items()}
        self._advance_keys = set(cfg.response.keymap.advance)
        if verbose:
            print("responses: AUTOPILOT (synthetic participant - not real data)")

    # ------------------------------------------------------------ the hook
    def attach(self, trig):
        """Listen to the trigger stream. Called once at start-up."""
        trig.on_send = self._on_trigger

    def _on_trigger(self, code):
        if not isinstance(code, str):
            return
        now = self.clock.getTime()

        if code.startswith("to_target_") or code == "rt_target":
            hand = "right"
            if self.rng.random() < self.p_miss:
                return                                   # no response at all
            if self.rng.random() < self.p_anticipate:
                latency = self.rng.uniform(0.02, 0.14)   # scored as anticipation
            else:
                latency = max(0.12, self.rng.gauss(self.rt_mean, self.rt_sd))
            self.injected.append({"code": code, "kind": "rt", "clock_now": now,
                                  "intended_s": latency, "target_s": None})
            self._press(now + latency, hand)

        elif code.startswith("to_catch_"):
            if self.rng.random() < self.p_catch_false_alarm:
                self._press(now + self.rng.uniform(0.2, 0.6), "right")

        elif code.startswith("st_cue_"):
            # st_cue_<delay label>_<hand>
            parts = code.split("_")
            self._cued_delay_s = self._delays.get(parts[2])

        elif code.startswith("st_start_"):
            hand = code.rsplit("_", 1)[-1]
            target = self._cued_delay_s
            if target is None:
                return
            produced = max(0.1, self.rng.gauss(target, target * self.timing_sd_frac))
            self.injected.append({"code": code, "kind": "self_timing", "clock_now": now,
                                  "intended_s": produced, "target_s": target})
            self._press(now + produced, hand)

    def dump(self, path):
        """Write every injected press to JSON, for verifying the scoring code."""
        import json
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.injected, fh, indent=2)
        return path

    def _press(self, when, hand):
        keys = self.keys_for(hand)
        self._pending.append((when, keys[0]))

    # -------------------------------------------------- Responder overrides
    def get_presses(self, key_list=None):
        now = self.clock.getTime()

        # Instruction / break screens: wait a beat, then "press space".
        if key_list and self._advance_keys.issuperset(key_list):
            if self._advance_at is None:
                self._advance_at = now + self.advance_dwell
                return []
            if now >= self._advance_at:
                self._advance_at = None
                return [(sorted(self._advance_keys)[0], 0.0)]
            return []

        out = []
        for item in list(self._pending):
            when, key = item
            if when <= now:
                self._pending.remove(item)
                if key_list is None or key in key_list:
                    out.append((key, when))
        return out

    def flush(self):
        self._pending.clear()
        self._advance_at = None

    def check_quit(self):
        return None

    def wait_keys(self, key_list):
        return list(key_list)[0]
