"""Window, stimuli, and the frame-locked presentation engine.

Everything visual goes through ``Display.show()``. That single method is
where the experiment's timing guarantees live, so it is worth reading once
before changing anything:

  * Durations are converted to a whole number of frames and presented by
    counting flips. Nothing uses ``core.wait()`` for stimulus timing, so an
    event can never land between two refreshes.
  * The EEG trigger and the response-clock reset are both scheduled with
    ``win.callOnFlip()``, which fires in the same vertical blank as the
    stimulus. Reaction times are therefore measured from the screen, not
    from when Python got round to it.
  * A photodiode patch flashes on the same flip, so true onsets can be
    recovered offline and any residual lag measured rather than assumed.
  * ``poll`` is called once per frame *after* the flip, which is how
    responses are collected without ever blocking the display loop.
"""
from __future__ import annotations

from psychopy import core, monitors, visual


class Display:
    def __init__(self, cfg, trig, responder, verbose: bool = True):
        self.cfg = cfg
        self.trig = trig
        self.responder = responder
        self.verbose = verbose
        self.units = cfg.display.units

        mon = monitors.Monitor(cfg.display.monitor.name)
        mon.setWidth(cfg.display.monitor.width_cm)
        mon.setDistance(cfg.display.monitor.distance_cm)
        mon.setSizePix(list(cfg.display.monitor.resolution))

        self.win = visual.Window(
            size=list(cfg.display.monitor.resolution),
            fullscr=cfg.display.fullscreen,
            screen=cfg.display.screen,
            monitor=mon,
            units=self.units,
            color=cfg.display.background,
            allowGUI=not cfg.display.fullscreen,
            waitBlanking=True,
        )
        self.win.mouseVisible = cfg.display.mouse_visible

        self._measure_refresh()
        self._build_stimuli()

    # ------------------------------------------------------------ frame rate
    def _measure_refresh(self):
        nominal = float(self.cfg.display.nominal_refresh_hz)
        measured = None
        if self.cfg.display.measure_refresh:
            self._say("measuring refresh rate ...")
            measured = self.win.getActualFrameRate(
                nIdentical=20, nMaxFrames=300, nWarmUpFrames=20, threshold=1
            )

        if measured is None:
            self.frame_rate = nominal
            self._say(
                f"!! could not measure a stable refresh rate; assuming {nominal} Hz.\n"
                f"!! Close other applications and re-run before collecting real data."
            )
        else:
            self.frame_rate = measured
            self._say(f"refresh rate: {measured:.2f} Hz (nominal {nominal})")
            if abs(measured - nominal) > self.cfg.display.tolerance_hz:
                msg = (
                    f"Measured refresh ({measured:.1f} Hz) differs from the configured "
                    f"nominal_refresh_hz ({nominal} Hz) by more than "
                    f"{self.cfg.display.tolerance_hz} Hz.\n"
                    f"Frame-locked durations would be wrong. Fix the monitor setting or "
                    f"update the config."
                )
                if not self.cfg.display.allow_refresh_mismatch:
                    self.win.close()
                    raise SystemExit("REFUSING TO RUN.\n" + msg)
                self._say("!! " + msg + "\n!! Continuing because allow_refresh_mismatch is true.")

        self.frame_dur = 1.0 / self.frame_rate

    def frames(self, seconds: float) -> int:
        """Whole frames closest to a requested duration (never negative)."""
        return max(0, int(round(float(seconds) / self.frame_dur)))

    def actual_s(self, seconds: float) -> float:
        """What ``seconds`` really becomes once rounded to whole frames."""
        return self.frames(seconds) * self.frame_dur

    def _say(self, msg):
        if self.verbose:
            print(msg)

    # -------------------------------------------------------------- stimuli
    def _build_stimuli(self):
        c = self.cfg
        self.fixation = visual.ShapeStim(
            self.win, vertices="cross", size=(c.display.fixation.size,) * 2,
            fillColor=c.display.fixation.color, lineColor=None, units=self.units,
        )
        t = c.display.text
        # Short centred messages (trial feedback).
        self.text = visual.TextStim(
            self.win, text="", color=t.color, units="height",
            height=t.height, wrapWidth=t.wrap_width,
            alignText="center", anchorHoriz="center", anchorVert="center",
        )
        # Participant-facing instruction pages.
        self.ui_heading = visual.TextStim(
            self.win, text="", color=t.heading_color, units="height",
            height=t.heading_height, wrapWidth=1.4, bold=True,
            alignText="center", anchorHoriz="center", anchorVert="center",
        )
        self.ui_body = visual.TextStim(
            self.win, text="", color=t.color, units="height",
            height=t.height, wrapWidth=t.wrap_width,
            alignText="left", anchorHoriz="left", anchorVert="top",
        )
        self.ui_footer = visual.TextStim(
            self.win, text="", color=t.muted_color, units="height",
            height=t.small_height, wrapWidth=1.4,
            alignText="center", anchorHoriz="center", anchorVert="center",
        )
        self.ui_big = visual.TextStim(
            self.win, text="", color=t.heading_color, units="height",
            height=t.big_height, bold=True,
            alignText="center", anchorHoriz="center", anchorVert="center",
        )

        pd = c.display.photodiode
        self.photodiode = None
        if pd.enabled:
            w, h = self.win.size
            half = pd.size_px / 2.0
            x = (w / 2.0 - half) * (-1 if "left" in pd.corner else 1)
            y = (h / 2.0 - half) * (-1 if "bottom" in pd.corner else 1)
            self.photodiode = visual.Rect(
                self.win, width=pd.size_px, height=pd.size_px, pos=(x, y),
                units="pix", fillColor=pd.off_color, lineColor=None,
            )
        self._pd_on = pd.on_color if pd.enabled else None
        self._pd_off = pd.off_color if pd.enabled else None
        self._pd_frames = pd.n_frames if pd.enabled else 0

    def square(self, color, size):
        """A filled square, the only stimulus shape the battery uses."""
        return visual.Rect(
            self.win, width=size, height=size, fillColor=color,
            lineColor=None, units=self.units,
        )

    # ----------------------------------------------------- the timing engine
    def show(self, n_frames, stims=(), trigger=None, photodiode=False,
             on_flip=(), poll=None):
        """Present ``stims`` for ``n_frames`` frames; return the onset time.

        Parameters
        ----------
        n_frames   : how many refreshes to hold this display for
        stims      : iterable of PsychoPy stimuli to draw each frame
        trigger    : trigger name or int, sent on the *first* flip
        photodiode : flash the corner patch on the first flip
        on_flip    : extra zero-argument callables scheduled on the first flip
                     (this is how the response clock is zeroed at onset)
        poll       : called once per frame after the flip; return True to end
                     this segment early (used to finish a trial on response)

        Returns
        -------
        float : the timestamp of the first flip, in PsychoPy clock time.
        """
        if n_frames <= 0:
            return core.getTime()

        onset = None
        for i in range(n_frames):
            for stim in stims:
                stim.draw()
            if self.photodiode is not None:
                lit = photodiode and i < self._pd_frames
                self.photodiode.fillColor = self._pd_on if lit else self._pd_off
                self.photodiode.draw()

            if i == 0:
                if trigger is not None:
                    self.win.callOnFlip(self.trig.send, trigger)
                for fn in on_flip:
                    self.win.callOnFlip(fn)

            flip_time = self.win.flip()
            if i == 0:
                onset = flip_time

            self.trig.tick()
            self.responder.check_quit()
            if poll is not None and poll():
                break

        return onset

    def blank(self, n_frames, poll=None, stims=()):
        """Hold the background (plus anything in ``stims``) for n frames."""
        return self.show(n_frames, stims=stims, poll=poll)

    # ------------------------------------------------------------- messaging
    def _wait_advance(self, keys=None, min_advance_s=None, stims=()):
        """Hold a screen until the advance key is pressed.

        Presses arriving within ``min_advance_s`` of the screen appearing are
        discarded, so a key left over from the preceding trial cannot skip a
        page the participant has not had time to read.
        """
        keys = list(keys or self.cfg.response.keymap.advance)
        guard = (self.cfg.display.ui.min_advance_s
                 if min_advance_s is None else float(min_advance_s))
        clock = core.Clock()
        self.responder.flush()
        while True:
            for stim in stims:
                stim.draw()
            if self.photodiode is not None:
                self.photodiode.fillColor = self._pd_off
                self.photodiode.draw()
            self.win.flip()
            self.trig.tick()
            self.responder.check_quit()
            presses = self.responder.get_presses(keys)
            if presses and clock.getTime() >= guard:
                return presses[0][0]

    def message(self, text, keys=None, duration_s=None, min_advance_s=None):
        """A short centred message. Held for ``duration_s``, or until a key."""
        self.text.text = text
        self.text.pos = (0, 0)
        if duration_s is not None:
            self.show(self.frames(duration_s), stims=[self.text])
            return None
        return self._wait_advance(keys=keys, min_advance_s=min_advance_s,
                                  stims=[self.text])

    def _text_height(self, stim, text):
        """How tall a rendered TextStim actually is, in 'height' units.

        Measured rather than assumed, because wrapped text is the whole
        reason a fixed layout goes wrong. Falls back to a line estimate if
        the backend does not expose a bounding box.
        """
        try:
            h_pix = float(stim.boundingBox[1])
            if h_pix > 0:
                return h_pix / float(self.win.size[1])
        except Exception:                              # noqa: BLE001
            pass
        chars_per_line = 52
        lines = 0
        for para in text.split("\n"):
            lines += max(1, -(-len(para) // chars_per_line))
        return lines * self.cfg.display.text.height * 1.35

    def _swatch(self, color, y):
        size = self.cfg.display.ui.swatch_size
        return visual.Rect(
            self.win, width=size, height=size, units="height", pos=(-0.40, y),
            fillColor=color, lineColor=self.cfg.display.text.muted_color,
            lineWidth=1.5,
        )

    def _swatch_label(self, text, y):
        return visual.TextStim(
            self.win, text=text, units="height", color=self.cfg.display.text.color,
            height=self.cfg.display.text.height, wrapWidth=0.80, pos=(-0.32, y),
            alignText="left", anchorHoriz="left", anchorVert="center",
        )

    def instruction_screen(self, heading, body=None, swatches=None, footer=None,
                           duration_s=None, min_advance_s=None, keys=None):
        """A readable instruction page.

        heading  : one short line, large
        body     : a short paragraph, left-aligned because that reads better
                   than centred text over more than one line
        swatches : [(colour, 'explanation'), ...] - draws the ACTUAL coloured
                   square beside its explanation, so the participant never has
                   to imagine what a colour name refers to
        footer   : the muted line at the bottom
        """
        stims = []

        self.ui_heading.text = heading
        self.ui_heading.pos = (0, 0.38)
        stims.append(self.ui_heading)

        body_top, body_height = 0.27, 0.0
        if body:
            self.ui_body.text = body
            self.ui_body.pos = (-self.cfg.display.text.wrap_width / 2.0, body_top)
            stims.append(self.ui_body)
            body_height = self._text_height(self.ui_body, body)

        if swatches:
            # Start the legend below where the paragraph actually ended.
            # A fixed position collided with the text whenever the paragraph
            # wrapped to more lines than expected.
            top = (body_top - body_height - 0.055) if body else 0.18
            for i, (color, label) in enumerate(swatches):
                y = top - i * 0.115
                stims.append(self._swatch(color, y))
                stims.append(self._swatch_label(label, y))

        if footer is None:
            footer = "Press SPACE when you are ready.  There is no rush."
        if footer:
            self.ui_footer.text = footer
            self.ui_footer.pos = (0, -0.42)
            stims.append(self.ui_footer)

        if duration_s is not None:
            self.show(self.frames(duration_s), stims=stims)
            return None
        return self._wait_advance(keys=keys, min_advance_s=min_advance_s,
                                  stims=stims)

    def countdown(self, seconds=None, message="Get ready"):
        """A large, unhurried countdown before a block starts."""
        seconds = self.cfg.display.ui.countdown_from if seconds is None else seconds
        for remaining in range(int(seconds), 0, -1):
            self.ui_heading.text = message
            self.ui_heading.pos = (0, 0.16)
            self.ui_big.text = str(remaining)
            self.ui_big.pos = (0, -0.05)
            self.show(self.frames(1.0), stims=[self.ui_heading, self.ui_big])

    # ----------------------------------------------------------------- close
    def close(self):
        try:
            self.win.close()
        except Exception:                              # noqa: BLE001
            pass
