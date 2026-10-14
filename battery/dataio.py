"""Data files.

Two things are written for every task run:

  * a CSV with one row per trial, flushed after every row so a crash or a
    mid-session abort never costs more than the trial in progress;
  * a JSON sidecar with the full effective configuration, the measured
    frame rate, the trigger table and software versions - everything an
    analyst needs to reconstruct what was actually presented.

Filenames follow a BIDS-like pattern::

    data/sub-P01/ses-1/sub-P01_ses-1_task-temporalorienting_run-run1_beh.csv
"""
from __future__ import annotations

import csv
import json
import platform
import sys
from datetime import datetime
from pathlib import Path


def _safe(text) -> str:
    """Make a string safe for a filename."""
    return "".join(ch for ch in str(text) if ch.isalnum() or ch in "-_") or "na"


def session_dir(cfg, info) -> Path:
    root = Path(cfg.session.data_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent.parent / root
    out = root / f"sub-{_safe(info['participant'])}" / f"ses-{_safe(info['session'])}"
    out.mkdir(parents=True, exist_ok=True)
    return out


class Recorder:
    """One CSV + one JSON sidecar for a single task run."""

    def __init__(self, cfg, info, out_dir: Path, task: str, label: str,
                 fields, extra_meta: dict = None):
        self.cfg = cfg
        self.info = info
        self.task = task
        self.label = label
        stem = (
            f"sub-{_safe(info['participant'])}_ses-{_safe(info['session'])}"
            f"_task-{_safe(task)}_run-{_safe(label)}"
        )
        # Never silently overwrite an existing file.
        base = out_dir / stem
        suffix, n = "", 1
        while (out_dir / f"{stem}{suffix}_beh.csv").exists():
            suffix, n = f"_dup{n}", n + 1
        self.csv_path = out_dir / f"{stem}{suffix}_beh.csv"
        self.json_path = out_dir / f"{stem}{suffix}_beh.json"

        # Columns present on every row of every task.
        self.fields = [
            "participant", "session", "phase", "run_label", "condition_code",
            "experimenter", "task", "trial_index", "onset_unix", "onset_clock_s",
        ] + list(fields)

        self._fh = open(self.csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.fields,
                                      extrasaction="raise", restval="")
        self._writer.writeheader()
        self._fh.flush()
        self.n_rows = 0

        self._meta = {
            "created": datetime.now().isoformat(timespec="seconds"),
            "task": task,
            "label": label,
            "info": dict(info),
            "software": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "psychopy": _psychopy_version(),
            },
            "config": _plain(cfg),
        }
        if extra_meta:
            self._meta.update(extra_meta)

    def write(self, row: dict):
        base = {
            "participant": self.info["participant"],
            "session": self.info["session"],
            "phase": self.info["phase"],
            "run_label": self.label,
            "condition_code": self.info.get("condition_code", ""),
            "experimenter": self.info.get("experimenter", ""),
            "task": self.task,
            "trial_index": self.n_rows,
            "onset_unix": datetime.now().timestamp(),
        }
        base.update(row)
        unknown = set(base) - set(self.fields)
        if unknown:
            raise KeyError(f"{self.task}: columns not declared in fields: {sorted(unknown)}")
        self._writer.writerow(base)
        self._fh.flush()
        self.n_rows += 1

    def close(self, summary: dict = None):
        try:
            self._fh.close()
        except Exception:                              # noqa: BLE001
            pass
        self._meta["n_trials_written"] = self.n_rows
        self._meta["finished"] = datetime.now().isoformat(timespec="seconds")
        if summary:
            self._meta["summary"] = summary
        with open(self.json_path, "w", encoding="utf-8") as fh:
            json.dump(self._meta, fh, indent=2, default=str)


def write_session_log(cfg, info, out_dir: Path, entries: list):
    """Append-only record of what was run, in order, with timestamps."""
    path = out_dir / (
        f"sub-{_safe(info['participant'])}_ses-{_safe(info['session'])}_sessionlog.json"
    )
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:                              # noqa: BLE001
            existing = []
    existing.append({
        "written": datetime.now().isoformat(timespec="seconds"),
        "info": dict(info),
        "entries": entries,
    })
    path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")
    return path


def _psychopy_version():
    try:
        import psychopy
        return psychopy.__version__
    except Exception:                                  # noqa: BLE001
        return "unknown"


def _plain(obj):
    """Convert Config objects back to plain dicts for JSON serialisation."""
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj
