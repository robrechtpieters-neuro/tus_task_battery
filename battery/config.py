"""Configuration loading and merging.

The battery keeps every tunable parameter in ``config/default.yaml``. This
module loads it, optionally deep-merges a user override file on top, and
returns it as a dict that also supports attribute access, so you can write
``cfg.tasks.temporal_orienting.soa_s.short`` instead of a chain of ``[...]``.

Nothing here knows anything about the experiment; it is pure plumbing.
"""
from __future__ import annotations

import copy
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required but not installed.\n"
        "  Standalone PsychoPy: it is already bundled - run via the PsychoPy python.\n"
        "  pip install pyyaml"
    ) from exc

PKG_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PKG_ROOT / "config" / "default.yaml"


# Names that already exist on dict (keys, items, values, get, copy, ...).
# A config key with one of these names could never be read with dot access,
# because normal attribute lookup finds the dict method first and __getattr__
# is never consulted. _validate() rejects them with a clear message rather
# than letting it fail confusingly at run time.
RESERVED_KEY_NAMES = frozenset(dir(dict))


class Config(dict):
    """A dict whose keys are also attributes.

    Nested dicts are converted at load time, so mutation works as expected::

        cfg.display.fullscreen = False   # really changes the config

    Config keys must not be named after dict methods - see RESERVED_KEY_NAMES.
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(
                f"no config key {key!r} (available here: {sorted(self)})"
            ) from None

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        del self[key]


def _convert(obj):
    """Recursively turn plain dicts into Config objects."""
    if isinstance(obj, dict):
        return Config({k: _convert(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_convert(v) for v in obj]
    return obj


def deep_merge(base: dict, override: dict) -> dict:
    """Merge ``override`` into ``base`` recursively, returning a new dict.

    Dicts are merged key by key; everything else (including lists) is
    replaced wholesale. This is what lets an override file mention only the
    handful of keys it wants to change.
    """
    out = copy.deepcopy(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_yaml(path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


def load_config(user_config=None, demo: bool = False, cli_overrides: dict = None) -> Config:
    """Build the effective configuration.

    Layers, applied in order (later wins):
      1. config/default.yaml
      2. the file passed to --config, if any
      3. demo_overrides, if --demo was given
      4. anything passed programmatically in ``cli_overrides``
    """
    cfg = load_yaml(DEFAULT_CONFIG_PATH)

    if user_config:
        user_path = Path(user_config)
        if not user_path.is_absolute():
            # Look next to the config folder first, then the current directory.
            candidate = PKG_ROOT / "config" / user_path
            user_path = candidate if candidate.exists() else Path.cwd() / user_path
        if not user_path.exists():
            raise SystemExit(f"config file not found: {user_path}")
        cfg = deep_merge(cfg, load_yaml(user_path))

    if demo:
        cfg = deep_merge(cfg, cfg.get("demo_overrides", {}))

    if cli_overrides:
        cfg = deep_merge(cfg, cli_overrides)

    cfg = _convert(cfg)
    _validate(cfg)
    return cfg


def find_shadowed_keys(node, path="") -> list:
    """Config keys that collide with dict method names, as dotted paths."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key in RESERVED_KEY_NAMES:
                found.append(f"{path}{key}")
            found += find_shadowed_keys(value, f"{path}{key}.")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found += find_shadowed_keys(value, f"{path}[{i}].")
    return found


def _validate(cfg: Config) -> None:
    """Catch the configuration mistakes that would otherwise only show up
    as strange behaviour halfway through a session."""
    problems = []

    shadowed = find_shadowed_keys(cfg)
    if shadowed:
        problems.append(
            "these keys are named after dict methods and cannot be read with dot "
            f"access - rename them: {', '.join(shadowed)}"
        )

    to = cfg.tasks.temporal_orienting
    n_valid = to.trials.per_cell * to.trials.valid_proportion
    if abs(n_valid - round(n_valid)) > 1e-9:
        problems.append(
            f"temporal_orienting: per_cell ({to.trials.per_cell}) x valid_proportion "
            f"({to.trials.valid_proportion}) = {n_valid}, which is not a whole number "
            f"of trials."
        )

    if set(to.soa_s) != {"short", "long"}:
        problems.append("temporal_orienting.soa_s must have exactly the keys short and long.")

    st = cfg.tasks.self_timing
    if set(st.delays_s) != set(st.cue_colors):
        problems.append("self_timing: delays_s and cue_colors must use the same labels.")

    if cfg.display.units not in ("deg", "height"):
        problems.append("display.units must be 'deg' or 'height'.")

    valid_backends = ("none", "parallel", "serial_bp", "lsl")
    if cfg.triggers.backend not in valid_backends:
        problems.append(f"triggers.backend must be one of {valid_backends}.")

    for name, sched in cfg.schedules.items():
        for item in sched:
            if item["task"] not in cfg.tasks:
                problems.append(f"schedule {name!r} refers to unknown task {item['task']!r}.")

    if problems:
        raise SystemExit("Configuration problems:\n  - " + "\n  - ".join(problems))
