"""Response collection.

Everything the tasks need to know about how a participant answers lives
here, so swapping a keyboard for a Cedrus box changes nothing else.

Timing model
------------
``reset_clock()`` is scheduled with ``win.callOnFlip()`` at the moment a
stimulus appears. Every press returned afterwards carries an ``rt`` measured
from that flip, so reaction times are relative to the true screen onset
rather than to when the code happened to run.
"""
from __future__ import annotations

from psychopy import core


class QuitExperiment(Exception):
    """Raised when the experimenter presses the quit key."""


class Responder:
    def __init__(self, cfg, verbose: bool = True):
        self.cfg = cfg
        self.backend = cfg.response.backend
        self.keymap = cfg.response.keymap
        self.quit_keys = list(cfg.response.keymap.quit)
        self.verbose = verbose
        self._device = None
        self._open()

    # ------------------------------------------------------------------ setup
    def _open(self):
        if self.backend == "cedrus":
            try:
                import pyxid2
                devices = pyxid2.get_xid_devices()
                if not devices:
                    raise RuntimeError("no XID devices found")
                self._device = devices[self.cfg.response.cedrus.device_index]
                self._device.reset_base_timer()
                self._device.reset_rt_timer()
                self._say(f"responses: Cedrus {self._device}")
                return
            except Exception as exc:                   # noqa: BLE001
                self._say(
                    f"!! could not open Cedrus device: {exc}\n"
                    f"!! falling back to keyboard input."
                )
                self.backend = "keyboard"

        from psychopy.hardware import keyboard
        self.clock = core.Clock()
        try:
            self._device = keyboard.Keyboard(clock=self.clock)
        except TypeError:                # older PsychoPy without the kwarg
            self._device = keyboard.Keyboard()
            self._device.clock = self.clock
        self._say("responses: keyboard")

    def _say(self, msg):
        if self.verbose:
            print(msg)

    # ------------------------------------------------------------- key naming
    def keys_for(self, hand: str):
        """Physical keys for a logical hand ('right' / 'left')."""
        return list(self.keymap[f"{hand}_hand"])

    # -------------------------------------------------------------- the clock
    def reset_clock(self):
        """Zero the response clock. Schedule this with win.callOnFlip()."""
        if self.backend == "cedrus":
            self._device.reset_rt_timer()
        else:
            self.clock.reset()

    # ---------------------------------------------------------------- polling
    def flush(self):
        """Discard anything pressed up to now."""
        if self.backend == "cedrus":
            self._device.clear_response_queue()
        else:
            self._device.clearEvents()

    def get_presses(self, key_list=None):
        """Return ``[(name, rt_seconds), ...]`` for presses since the last call.

        ``rt`` is measured from the most recent ``reset_clock()``.
        Quitting is handled here so every polling loop honours it.
        """
        out = []
        if self.backend == "cedrus":
            self._device.poll_for_response()
            while self._device.response_queue:
                resp = self._device.get_next_response()
                if not resp["pressed"]:
                    continue
                name = self._cedrus_name(resp["key"])
                if key_list is None or name in key_list:
                    out.append((name, resp["time"] / 1000.0))
            # The Cedrus box has no quit key; check the keyboard as well.
            from psychopy import event
            if any(k in self.quit_keys for k in event.getKeys(keyList=self.quit_keys)):
                raise QuitExperiment()
            return out

        wanted = None if key_list is None else list(key_list) + self.quit_keys
        for key in self._device.getKeys(keyList=wanted, waitRelease=False, clear=True):
            if key.name in self.quit_keys:
                raise QuitExperiment()
            if key_list is None or key.name in key_list:
                out.append((key.name, key.rt))
        return out

    def _cedrus_name(self, button: int) -> str:
        for logical, physical in self.cfg.response.cedrus.button_map.items():
            if physical == button:
                return self.keymap[logical][0] if logical in self.keymap else logical
        return f"button{button}"

    def check_quit(self):
        """Raise QuitExperiment if the quit key is down. Called every frame."""
        if self.backend == "cedrus":
            from psychopy import event
            if event.getKeys(keyList=self.quit_keys):
                raise QuitExperiment()
        else:
            for key in self._device.getKeys(keyList=self.quit_keys, clear=True):
                raise QuitExperiment()

    def wait_keys(self, key_list):
        """Block until one of ``key_list`` is pressed; return its name."""
        self.flush()
        while True:
            for name, _ in self.get_presses(key_list):
                return name
            core.wait(0.005)
