"""EEG trigger delivery.

One class, ``TriggerPort``, with four interchangeable backends. Tasks never
know which one is active - they just call ``trig.send("to_target_...")``.

Timing note
-----------
Triggers are always scheduled with ``win.callOnFlip()`` by the display
module, so the code is written to the port in the same frame as the
stimulus reaches the screen. The line is reset to zero by ``tick()``, which
the display loop calls once per frame; this keeps the reset non-blocking so
it can never cost a frame.

If the configured hardware is missing, the port degrades to 'none' with a
loud warning rather than crashing mid-session.
"""
from __future__ import annotations

import time


class TriggerPort:
    def __init__(self, cfg, verbose: bool = True):
        self.cfg = cfg
        self.codes = dict(cfg.triggers.codes)
        self.pulse_s = cfg.triggers.pulse_ms / 1000.0
        self.backend = cfg.triggers.backend
        self.verbose = verbose
        self._port = None
        self._high_since = None
        self.log = []            # every code sent, with a timestamp
        # Optional observer, called with each code name as it is sent. The
        # autopilot uses this to learn when stimuli actually appeared; nothing
        # in normal data collection sets it.
        self.on_send = None
        self._open()

    # ------------------------------------------------------------------ setup
    def _open(self):
        if self.backend == "none":
            self._say("triggers: no hardware (codes are still written to data files)")
            return
        try:
            if self.backend == "parallel":
                from psychopy import parallel
                address = self.cfg.triggers.parallel.address
                self._port = parallel.ParallelPort(address=int(str(address), 0))
                self._port.setData(0)
                self._say(f"triggers: parallel port at {address}")

            elif self.backend == "serial_bp":
                import serial
                s = self.cfg.triggers.serial_bp
                self._port = serial.Serial(port=s.port, baudrate=s.baudrate, timeout=0)
                self._port.write(bytes([0]))
                self._say(f"triggers: Brain Products TriggerBox on {s.port}")

            elif self.backend == "lsl":
                from pylsl import StreamInfo, StreamOutlet
                info = StreamInfo(
                    self.cfg.triggers.lsl.stream_name, "Markers", 1, 0, "int32",
                    "tusdn-markers",
                )
                self._port = StreamOutlet(info)
                self._say(f"triggers: LSL outlet {self.cfg.triggers.lsl.stream_name!r}")

        except Exception as exc:                      # noqa: BLE001 - deliberate
            self._say(
                f"!! could not open trigger backend {self.backend!r}: {exc}\n"
                f"!! FALLING BACK TO 'none'. EEG markers will NOT be sent.\n"
                f"!! Stop now unless this is a behavioural pilot."
            )
            self.backend = "none"
            self._port = None

    def _say(self, msg):
        if self.verbose:
            print(msg)

    # ------------------------------------------------------------------- use
    def resolve(self, code) -> int:
        """Turn a code name into its integer value. Ints pass straight through."""
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        try:
            return int(self.codes[code])
        except KeyError:
            raise KeyError(
                f"trigger code {code!r} is not defined in triggers.codes "
                f"(config/default.yaml)"
            ) from None

    def send(self, code):
        """Write a code to the port. Safe to call with None (does nothing)."""
        value = self.resolve(code)
        if self.on_send is not None and code is not None:
            self.on_send(code)
        if value == 0:
            return
        self.log.append((time.perf_counter(), code, value))
        if self._port is None:
            return
        try:
            if self.backend == "parallel":
                self._port.setData(value)
            elif self.backend == "serial_bp":
                self._port.write(bytes([value]))
            elif self.backend == "lsl":
                self._port.push_sample([value])
                return                       # LSL markers are instantaneous
            self._high_since = time.perf_counter()
        except Exception as exc:                      # noqa: BLE001
            self._say(f"!! trigger send failed ({code}): {exc}")

    def tick(self):
        """Reset the line to zero once the pulse has lasted long enough.

        Called every frame by the display loop. Non-blocking by design.
        """
        if self._high_since is None or self._port is None:
            return
        if time.perf_counter() - self._high_since >= self.pulse_s:
            try:
                if self.backend == "parallel":
                    self._port.setData(0)
                elif self.backend == "serial_bp":
                    self._port.write(bytes([0]))
            except Exception:                          # noqa: BLE001
                pass
            self._high_since = None

    def close(self):
        try:
            if self.backend == "parallel" and self._port is not None:
                self._port.setData(0)
            elif self.backend == "serial_bp" and self._port is not None:
                self._port.write(bytes([0]))
                self._port.close()
        except Exception:                              # noqa: BLE001
            pass
        self._port = None
