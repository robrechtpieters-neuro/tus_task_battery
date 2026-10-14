"""TUS dentate nucleus task battery.

Package layout
--------------
    config.py     load and merge YAML configuration
    triggers.py   EEG trigger delivery (parallel / TriggerBox / LSL / none)
    responses.py  keyboard or Cedrus response box, and the response clock
    display.py    window, stimuli, and the frame-locked presentation engine
    dataio.py     CSV + JSON output
    trials.py     trial-list construction (no PsychoPy - inspect it freely)
    tasks/        one module per task, each exposing run(ctx, **kwargs)

Everything a task needs is bundled in a ``Context`` and handed to it, so a
task module never reaches out to global state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .dataio import Recorder

__version__ = "1.0.0"


@dataclass
class Context:
    """Everything a task needs, passed as a single argument."""

    cfg: Any
    display: Any
    responder: Any
    trig: Any
    rng: Any
    info: dict
    out_dir: Path
    log: list = field(default_factory=list)

    def recorder(self, task: str, label: str, fields) -> Recorder:
        """Open a data file for one task run, stamped with the real timing."""
        return Recorder(
            self.cfg, self.info, self.out_dir, task, label, fields,
            extra_meta={
                "timing": {
                    "measured_refresh_hz": round(self.display.frame_rate, 4),
                    "frame_duration_s": round(self.display.frame_dur, 6),
                },
                "trigger_backend": self.trig.backend,
                "response_backend": self.responder.backend,
            },
        )

    def note(self, **kwargs):
        """Add an entry to the session log."""
        self.log.append(kwargs)
