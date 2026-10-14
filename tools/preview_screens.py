#!/usr/bin/env python
"""Render every instruction screen to a PNG, without running the battery.

    python tools/preview_screens.py [--out screens] [--config my.yaml]

Opens a window, draws each participant-facing screen in turn, saves it, and
closes. Nothing is recorded and no data directory is touched.

This exists because instruction text is the part of the battery most likely
to be wrong in a way no test can catch: a paragraph that wraps onto a line
too many, a swatch that lands on top of the text below it, a sentence that
made sense to the person who wrote it and to nobody else. Proofreading them
as images, before a participant ever sees them, is much cheaper than
discovering it mid-session.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="screens", help="directory for the PNGs")
    ap.add_argument("--config", help="YAML overrides, merged over the defaults")
    args = ap.parse_args()

    from battery.config import load_config
    cfg = load_config(args.config)
    cfg.display.fullscreen = False

    from battery.autopilot import AutoResponder
    from battery.display import Display
    from battery.triggers import TriggerPort

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    trig = TriggerPort(cfg, verbose=False)
    responder = AutoResponder(cfg, rng=random.Random(0))
    disp = Display(cfg, trig, responder, verbose=False)

    shots = []

    def capture(keys=None, min_advance_s=None, stims=()):
        """Stand in for _wait_advance: draw, grab the frame, carry on."""
        for stim in stims:
            stim.draw()
        disp.win.flip()
        disp.win.getMovieFrame()
        name = "%02d_%s.png" % (len(shots) + 1, capture.label)
        disp.win.saveMovieFrames(str(out / name))
        shots.append(name)
        return (list(keys or ["space"]))[0]

    capture.label = "screen"
    disp._wait_advance = capture

    def shot(label):
        capture.label = label

    class Ctx:
        pass
    ctx = Ctx()
    ctx.cfg = cfg
    ctx.display = disp
    ctx.responder = responder
    ctx.trig = trig
    ctx.rng = random.Random(0)

    try:
        from battery.tasks import temporal_orienting as TO
        from battery.tasks import self_timing as ST
        from battery.tasks import simple_rt as RT
        from battery.tasks import resting as RS

        key = responder.keys_for(cfg.tasks.temporal_orienting.response_hand)[0].upper()

        shot("welcome")
        disp.instruction_screen(
            heading="Welcome, and thank you",
            body=("There are 4 short parts to get through. Each one is explained "
                  "on screen before it starts, and there is a practice run for "
                  "anything new.\n\nYou can take a break between parts, and inside "
                  "the longer parts, for as long as you like. Nothing here is a "
                  "test of you – if something is unclear, just ask.\n\nPlease "
                  "keep your eyes on the cross in the middle of the screen whenever "
                  "one is showing, and try to stay still and relaxed."),
            footer="Press SPACE when you are ready to start.")

        shot("to_instructions")
        TO._show_instructions(ctx, key, cfg.tasks.temporal_orienting.response_hand)

        for context, (heading, body) in TO.BLOCK_INTRO.items():
            shot("to_block_" + context)
            disp.instruction_screen(heading=heading, body=body,
                                    footer="Block 1 of 4.  Press SPACE to begin.")

        shot("to_break")
        disp.instruction_screen(
            heading="Take a break",
            body=("Block 1 of 4 finished.\n\nAbout 20 minutes of this part left."
                  "\n\nRest your eyes, sit back, move your shoulders. The break "
                  "is as long as you want it to be."),
            footer=("Press SPACE when you are ready to carry on"
                    "   ·   press R to read the instructions again."))

        shot("to_comprehension")
        disp.instruction_screen(
            heading="Before we start for real",
            body=("Please tell the experimenter, in your own words:\n\n"
                  "1.  What tells you WHEN the green square will arrive?\n"
                  "2.  What should you do when no green square comes?\n\n"
                  "If either is unclear, the practice can simply be run again – "
                  "that is much better than guessing through the real blocks."),
            footer="Experimenter: press SPACE when the participant has answered both.")

        shot("st_instructions")
        ST._show_instructions(ctx, cfg.tasks.self_timing.hands[0], key)

        shot("rt_instructions")
        RT._show_instructions(ctx, key, cfg.tasks.simple_rt.response_hand)

        for kind, (heading, body) in RS.INTRO.items():
            shot("rest_" + kind)
            disp.instruction_screen(heading=heading,
                                    body=body.format(minutes=3),
                                    footer="Press SPACE when you are settled.")

        shot("closing")
        disp.instruction_screen(
            heading="That is everything",
            body=("All parts are finished. Thank you – that was the whole "
                  "session.\n\nPlease sit still for a moment while the "
                  "experimenter comes in."),
            footer="Press SPACE to finish.")

    finally:
        disp.close()
        trig.close()

    print("\n%d screens written to %s\n" % (len(shots), out.resolve()))
    for s in shots:
        print("   " + s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
