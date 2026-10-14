"""Offline self-test: everything that does not need a screen or PsychoPy.

    python tools/test_offline.py

Checks the configuration, the trial lists, the trigger table, the agreement
between each task's data columns and its FIELDS list, the data writer, and
the frame-rounding arithmetic. Run it after ANY edit to the config or to
battery/trials.py - it catches the mistakes that would otherwise surface
halfway through a session with a participant in the chair.

Exit code 0 = all good.
"""
import ast
import random
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\GBW_MyDownloads\Side project\tus_task_battery")
sys.path.insert(0, str(ROOT))

fails = []
def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)

# ---------------------------------------------------------------- 1. config
print("\n[1] config")
from battery.config import load_config, deep_merge
cfg = load_config()
check(cfg.display.units == "deg", "default config loads and validates")
check(cfg.tasks.temporal_orienting.soa_s.short == 0.7, "dotted access works")
demo = load_config(demo=True)
check(demo.tasks.temporal_orienting.trials.per_cell == 4, "demo overrides applied")
check(demo.display.fullscreen is False, "demo forces windowed")
check(cfg.tasks.temporal_orienting.trials.per_cell == 40, "demo did not mutate defaults")
merged = deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"c": 9}})
check(merged == {"a": {"b": 1, "c": 9}}, "deep_merge keeps untouched keys")

# Config subclasses dict, so a config key named after a dict method (keys,
# items, values, get, ...) can never be read with dot access - attribute
# lookup finds the method first. This caught a real bug: response.keys.
from battery.config import find_shadowed_keys, _convert, _validate
check(not find_shadowed_keys(cfg),
      f"no config key shadows a dict method ({find_shadowed_keys(cfg)})")
check(find_shadowed_keys({"response": {"keys": {"quit": ["escape"]}}}) == ["response.keys"],
      "shadowed keys are detected and reported by path")
try:
    _validate(_convert({**dict(cfg), "response": {**dict(cfg["response"]), "items": 1}}))
    check(False, "validation rejects a shadowing key")
except SystemExit:
    check(True, "validation rejects a shadowing key")

# every attribute the code reads off cfg.response must actually resolve
for attr in ("backend", "keymap", "anticipation_s"):
    check(not callable(getattr(cfg.response, attr)),
          f"cfg.response.{attr} resolves to config data, not a dict method")

# validation must reject bad configs
import copy, io, contextlib
from battery.config import _convert, _validate
bad = _convert(deep_merge(dict(cfg), {"tasks": {"temporal_orienting":
      {"trials": {"per_cell": 41, "valid_proportion": 0.75}}}}))
try:
    _validate(bad)
    check(False, "validation rejects non-integer valid-trial counts")
except SystemExit:
    check(True, "validation rejects non-integer valid-trial counts")

# ---------------------------------------------------------------- 2. trials
print("\n[2] trial lists")
from battery import trials
rng = random.Random(12345)
blocks = trials.temporal_orienting_blocks(cfg, rng, run_index=0)
check(len(blocks) == 4, "4 temporal-orienting blocks")
check(sum(len(b["trials"]) for b in blocks) == 212,
      "212 trials per run (160 target + 52 catch)")

# Context is blocked; SOA is mixed WITHIN a block (Breska & Ivry).
contexts = [b["context"] for b in blocks]
check(sorted(contexts) == ["interval", "interval", "rhythm", "rhythm"],
      f"two blocks of each context: {contexts}")
for b in blocks:
    labels = {t["soa_label"] for t in b["trials"]}
    check(labels == {"short", "long"},
          f"block {b['block_index']} ({b['context']}): both SOAs mixed in, got {labels}")

# per (context x SOA) cell: 30 valid / 10 invalid / 13 catch
cells = Counter()
for b in blocks:
    for t in b["trials"]:
        cells[(b["context"], t["soa_label"], t["validity"])] += 1
for context in ("rhythm", "interval"):
    for lab in ("short", "long"):
        got = (cells[(context, lab, "valid")], cells[(context, lab, "invalid")],
               cells[(context, lab, "catch")])
        check(got == (30, 10, 13), f"{context}/{lab} counts valid/invalid/catch = {got}")

n_catch = sum(1 for b in blocks for t in b["trials"] if t["is_catch"])
n_all = sum(len(b["trials"]) for b in blocks)
check(abs(n_catch / n_all - 0.25) < 0.01,
      f"catch trials are 25% of all trials ({n_catch}/{n_all})")

# invalid trials must use the OTHER SOA
for b in blocks:
    ok = True
    for t in b["trials"]:
        same = t["soa_s"]
        other = 1.2 if t["soa_label"] == "short" else 0.7
        if t["validity"] == "valid":
            ok &= t["target_soa_s"] == same
        elif t["validity"] == "invalid":
            ok &= t["target_soa_s"] == other
        else:
            ok &= t["target_soa_s"] is None
    check(ok, f"block {b['block_index']} ({b['context']}): target SOA correct per validity")

# shuffle constraints
for b in blocks:
    v = [t["validity"] for t in b["trials"]]
    run = best = 0
    for x in v:
        run = run + 1 if x != "valid" else 0
        best = max(best, run)
    check(best <= 2,
          f"block {b['block_index']} ({b['context']}): max non-valid run={best}")

# interval gap in range, rhythm gap == soa
for b in blocks:
    if b["context"] == "interval":
        mults = {round(t["gap_s"] / t["soa_s"], 6) for t in b["trials"]}
        check(mults == {1.5, 2.5},
              f"interval block {b['block_index']}: gap is exactly 1.5x or 2.5x SOA, got {sorted(mults)}")
    else:
        check(all(abs(t["gap_s"] - t["soa_s"]) < 1e-9 for t in b["trials"]),
              f"rhythm block {b['block_index']}: gap == SOA (beat continues)")

# practice lists are built, and are much shorter
prac = trials.temporal_orienting_blocks(cfg, random.Random(7), run_index=0, practice=True)
n_prac = sum(len(b["trials"]) for b in prac)
check(0 < n_prac < 40, f"practice pass is short ({n_prac} trials)")
check(all(t["is_practice"] for b in prac for t in b["trials"]),
      "practice trials are flagged is_practice")

# context order rotates with run index (rhythm-first vs interval-first)
orders = [tuple(b["context"] for b in
                trials.temporal_orienting_blocks(cfg, random.Random(1), run_index=r))
          for r in range(4)]
check(orders[0] != orders[1], f"context order rotates between runs: {orders[0]} vs {orders[1]}")
check(orders[0][0] == "rhythm" and orders[1][0] == "interval",
      f"run 0 starts rhythm, run 1 starts interval: {orders[0][0]}, {orders[1][0]}")

# reproducibility
a = trials.temporal_orienting_blocks(cfg, random.Random(7), 0)
b_ = trials.temporal_orienting_blocks(cfg, random.Random(7), 0)
check([t["validity"] for t in a[0]["trials"]] == [t["validity"] for t in b_[0]["trials"]],
      "same seed reproduces the same trial order")

# self-timing
st = trials.self_timing_blocks(cfg, random.Random(3), session_number=1, practice=True)
scored = [b for b in st if not b["is_practice"]]
check(len(st) == 4 and len(scored) == 2, "self-timing: 2 practice + 2 scored blocks")
check(all(len(b["trials"]) == 72 for b in scored), "72 scored trials per hand (3 x 24)")
check(all(len(b["trials"]) == 18 for b in st if b["is_practice"]),
      "18 practice trials per hand")
h1 = [b["hand"] for b in trials.self_timing_blocks(cfg, random.Random(3), 1, True)]
h2 = [b["hand"] for b in trials.self_timing_blocks(cfg, random.Random(3), 2, True)]
check(h1[0] != h2[0], f"hand order alternates by session ({h1[0]} vs {h2[0]})")

check(len(trials.simple_rt_trials(cfg, random.Random(1))) == 60, "60 simple-RT trials")
fps = [t["foreperiod_s"] for t in trials.simple_rt_trials(cfg, random.Random(1))]
check(all(1.0 <= f <= 4.0 for f in fps), "simple-RT foreperiods within 1-4 s")
check(len(trials.resting_periods(cfg)) == 2, "2 resting periods")

# ------------------------------------------------------------- 3. triggers
print("\n[3] triggers")
from battery.triggers import TriggerPort
trig = TriggerPort(cfg, verbose=False)
check(trig.backend == "none", "'none' backend opens")
check(trig.resolve("to_target_interval_short_valid") == 25, "code lookup by name")
check(trig.resolve(77) == 77, "int codes pass through")
check(trig.resolve(None) == 0, "None is a no-op")
try:
    trig.resolve("does_not_exist"); check(False, "unknown code raises")
except KeyError:
    check(True, "unknown code raises KeyError")
trig.send("to_response"); trig.tick()
check(len(trig.log) == 1, "sent codes are logged")

sys.path.insert(0, str(ROOT / "tools"))
import check_install
missing = check_install._check_trigger_codes(cfg, trig)
check(not missing, f"every code the tasks generate is defined (missing: {missing})")

# --------------------------------------------- 4. task row/FIELDS agreement
print("\n[4] task output columns")
BASE = {"participant", "session", "phase", "run_label", "condition_code",
        "experimenter", "task", "trial_index", "onset_unix", "onset_clock_s"}
for mod_name in ("temporal_orienting", "self_timing", "simple_rt", "resting"):
    src = (ROOT / "battery" / "tasks" / f"{mod_name}.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fields = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "FIELDS":
            fields = {e.value for e in node.value.elts}
    # A data row is either returned from _run_trial(), or passed directly to
    # rec.write({...}). Anything else (e.g. _summarise) is not a data row.
    keys = set()

    def dict_keys(node):
        return {k.value for k in node.keys if isinstance(k, ast.Constant)}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_trial":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                    keys |= dict_keys(sub.value)
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == "write"
                and node.args and isinstance(node.args[0], ast.Dict)):
            keys |= dict_keys(node.args[0])
    check(keys, f"{mod_name}: found a data-row dict to check")
    undeclared = keys - fields - BASE
    unused = fields - keys
    check(not undeclared, f"{mod_name}: no undeclared columns ({undeclared})")
    check(not unused, f"{mod_name}: no unused FIELDS entries ({unused})")

# --------------------------------------------------- 5. Recorder + quicklook
print("\n[5] data files end to end")
from battery.dataio import Recorder, session_dir, write_session_log
tmp = Path(tempfile.mkdtemp())
info = {"participant": "TEST01", "session": "1", "phase": "pre_tus",
        "condition_code": "A", "experimenter": "rp"}
from battery.tasks.temporal_orienting import FIELDS as TO_FIELDS
rec = Recorder(cfg, info, tmp, "temporalorienting", "run0", TO_FIELDS)

rng = random.Random(2)
for i, tr in enumerate(t for b in blocks for t in b["trials"]):
    valid = tr["validity"] == "valid"
    rt = rng.gauss(0.320 if valid else 0.375, 0.05)
    responded = tr["validity"] != "catch"
    rec.write({
        "onset_clock_s": 100.0 + i, "block_index": 0, "context": "interval",
        "soa_label": "short", "expected_soa_s": 0.7, "trial_in_block": i,
        "validity": tr["validity"], "is_catch": int(tr["is_catch"]),
        "target_soa_s": tr["target_soa_s"] or "", "gap_s": tr["gap_s"], "iti_s": 1.0,
        "first_cue_clock_s": 100.0, "warning_clock_s": 101.0, "target_clock_s": 101.7,
        "warning_rel_s": 1.0, "target_rel_s": 1.7,
        "response_key": "j" if responded else "", "rt_s": round(rt, 4) if responded else "",
        "responded": int(responded), "anticipation": 0, "miss": 0, "false_alarm": 0,
        "n_presses": int(responded), "all_press_rel_target_s": "",
        "trigger_warning": 15, "trigger_target": 25,
    })
summary = None
from battery.tasks.temporal_orienting import _summarise
summary = _summarise(rec.csv_path)
rec.close(summary=summary)
check(rec.csv_path.exists() and rec.json_path.exists(), "CSV and JSON sidecar written")
check(rec.n_rows == 212, f"212 rows written ({rec.n_rows})")
eff = summary["interval_short"].get("validity_effect_ms")
check(eff is not None and 30 < eff < 80, f"validity effect recovered from data: {eff} ms")

# a second recorder with the same name must not overwrite
rec2 = Recorder(cfg, info, tmp, "temporalorienting", "run0", TO_FIELDS)
check(rec2.csv_path != rec.csv_path, "existing files are never overwritten")
rec2.close()

try:
    rec3 = Recorder(cfg, info, tmp, "x", "y", ["a"])
    rec3.write({"nope": 1}); check(False, "undeclared column rejected")
except KeyError:
    check(True, "undeclared column raises KeyError")

log = write_session_log(cfg, info, tmp, [{"status": "completed"}])
check(log.exists(), "session log written")

import quicklook
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = quicklook.main(["quicklook", str(tmp)])
out = buf.getvalue()
check(rc == 0 and "validity effect" in out.lower(), "quicklook parses the data files")
check("interval" in out, "quicklook reports per-context results")
shutil.rmtree(tmp, ignore_errors=True)

# --------------------------------------------------------- 6. duration math
print("\n[6] frame-locked duration arithmetic")
for hz in (60, 100, 120, 144, 240):
    fd = 1.0 / hz
    err = {}
    for label, s in (("0.700", 0.700), ("1.200", 1.200), ("0.100", 0.100)):
        n = max(0, int(round(s / fd)))
        err[label] = abs(n * fd - s) * 1000
    worst = max(err.values())
    check(worst <= (1000 * fd / 2) + 1e-9,
          f"{hz} Hz: worst rounding error {worst:.2f} ms (<= half a frame)")

print("\n" + "=" * 60)
if fails:
    print(f"{len(fails)} FAILURE(S):")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ALL CHECKS PASSED")
