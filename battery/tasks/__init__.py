"""Task modules.

Each task exposes a single ``run(ctx, **kwargs)`` function. ``REGISTRY`` maps
the names used in ``schedules:`` in the YAML config onto those functions, so
adding a new task means writing one module and adding one line here.
"""
from . import resting, self_timing, simple_rt, temporal_orienting

REGISTRY = {
    "temporal_orienting": temporal_orienting.run,
    "self_timing": self_timing.run,
    "simple_rt": simple_rt.run,
    "resting": resting.run,
}

__all__ = ["REGISTRY", "temporal_orienting", "self_timing", "simple_rt", "resting"]
