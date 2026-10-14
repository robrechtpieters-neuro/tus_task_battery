# TUS Dentate Nucleus Task Battery

PsychoPy implementation of the four tasks described in
*Offline Transcranial Ultrasound Stimulation of the Cerebellar Dentate Nucleus
in Healthy Volunteers* (section 12 of the proposal):

| Task | What it measures | Measured duration |
|---|---|---|
| **Temporal orienting** (rhythm vs interval) | the validity effect — the **primary outcome** | **~27 min** (212 trials) |
| **Self-timed action** | produced interval, bias and variability, per hand | ~11.5 min with practice, ~9 without |
| **Simple RT** | generalised slowing — should show *no* effect | ~4 min |
| **Resting state** | 3 min eyes open + 3 min eyes closed | 6 min |

> **Timing, measured not estimated.** These figures come from
> `tools/check_install.py`. The post-TUS battery is ~50 min of task in total.
> Started ~5 min after sonication it finishes around **T+55**, inside the
> ~60 min window in which the offline effect is expected — 5 minutes of
> margin, not more. If that is too tight, the lever is
> `tasks.temporal_orienting.trials.per_cell`: 36 → ~T+52, 32 → ~T+50, at a
> proportionate cost in per-cell precision. Do **not** change the
> valid/invalid/catch proportions: they are what make this comparable to the
> published paradigm. Re-run `check_install.py` after any change to see the
> new totals.

---

## 1. Quick start

```bash
python tools/check_install.py                # ALWAYS run this first on a new machine
python run_experiment.py --demo              # whole battery, tiny, windowed (~4 min)
python run_experiment.py --demo --autopilot  # same, with a simulated participant
python run_experiment.py                     # real session, start-up dialog
```

`--autopilot` runs the whole battery with no human at the keyboard, producing
plausible data. Use it to check a schedule end to end after editing the config,
to demo the tasks to a collaborator, or to generate example files for an
analysis script. It listens to the trigger stream to know when each stimulus
actually appeared, so the simulated responses are timed against the real
presentation. Data it writes is prefixed `sub-AUTO...` and stamped
`autopilot: true` in the JSON sidecar. **It cannot validate keyboard latency** —
only a photodiode and a real button box can do that.

On Windows you can double-click `check_install.bat` and `run_windows.bat` instead.

Press **ESCAPE** at any moment to abort. Data already written is kept — the CSV
is flushed after every single trial.

---

## 2. Installing on a new PC

1. Install **PsychoPy Standalone** (2023.2 or later) from psychopy.org.
   This bundles Python and every dependency the battery needs.
2. Copy this whole `tus_task_battery` folder anywhere on the machine.
   There are no absolute paths in the code, so no configuration is needed.
3. Run `check_install.bat`. It refuses to give you a clean bill of health
   until the refresh rate is stable and the trigger table is complete.
4. Edit `config/default.yaml` — at minimum the `display.monitor` block and
   `display.nominal_refresh_hz` — then run `check_install.bat` again.

If you use a plain Python install instead: `pip install -r requirements.txt`.

---

## 3. Running a session

The two-session crossover maps onto schedules:

```bash
# Imaging visit: practise every task once, with a comprehension check.
# Nothing here is written to the data file.
python run_experiment.py --schedule familiarisation

# Stimulation day: ONE pass, started ~5 min after sonication (~50 min)
python run_experiment.py --schedule post_tus

# Only if something interrupts the session and you need to restart a part
python run_experiment.py --schedule to_only
python run_experiment.py --schedule st_only
python run_experiment.py --schedule rt_only
python run_experiment.py --schedule rest_only
```

`python run_experiment.py --list` prints every schedule.

**Blinding.** The start-up dialog asks for `condition_code`, not the condition.
Enter the blinded code from the allocation file. The task program never needs
to know, and never records, which condition was actually delivered.

### Same-day data check

```bash
python tools/quicklook.py data/sub-P01/ses-1
```

Prints the validity effect per (context × SOA) cell. It should be clearly
**positive in both** rhythm and interval cells — that is the basic temporal
cueing effect, present in everyone. If it is not, suspect the setup — key
mapping, monitor timing, whether the participant understood the task —
before they leave.

---

## 4. How the code is organised

```
run_experiment.py        entry point: dialog, hardware setup, runs a schedule
config/default.yaml      EVERY parameter. The code has no hard-coded numbers.
battery/
    config.py            loads and deep-merges YAML, validates it
    trials.py            builds trial lists (pure Python - no PsychoPy)
    display.py           window, stimuli, and the frame-locked timing engine
    responses.py         keyboard / Cedrus, and the response clock
    triggers.py          parallel / TriggerBox / LSL / none
    dataio.py            CSV + JSON sidecar writing
    tasks/
        temporal_orienting.py
        self_timing.py
        simple_rt.py
        resting.py
tools/
    check_install.py     pre-flight hardware and timing check
    test_offline.py      self-test needing no screen (run after every edit)
    quicklook.py         same-day behavioural summary
```

The dependency arrows only ever point one way: `run_experiment` → `tasks` →
`trials`/`display`/`responses`/`triggers` → `config`. A task never reaches out
to global state; it receives a `Context` holding everything it needs.

**Two files do almost all the work you will care about:**

* `config/default.yaml` — *what* the experiment is (timings, counts, colours,
  trigger codes, schedules).
* `battery/trials.py` — *how trials are composed* (validity mix, shuffling
  constraints, block order). It imports no PsychoPy, so you can inspect it
  without opening a window:

  ```python
  from battery.config import load_config
  from battery import trials
  import random
  blocks = trials.temporal_orienting_blocks(load_config(), random.Random(1), 0)
  print([(b["context"], b["soa_label"], len(b["trials"])) for b in blocks])
  ```

---

## 5. Customising

Edit `config/default.yaml` directly, or keep your changes separate:

```bash
python run_experiment.py --config my_lab.yaml
```

`my_lab.yaml` only needs the keys you are changing — it is deep-merged over the
defaults:

```yaml
display:
  nominal_refresh_hz: 120
  monitor: {width_cm: 60.0, distance_cm: 70.0, resolution: [2560, 1440]}
triggers:
  backend: serial_bp
  serial_bp: {port: "COM5"}
```

### Common edits

| To change | Edit |
|---|---|
| The two SOAs | `tasks.temporal_orienting.soa_s` |
| Trials per block | `tasks.temporal_orienting.trials.per_cell` |
| Valid/invalid ratio | `tasks.temporal_orienting.trials.valid_proportion` |
| Response keys | `response.keymap.right_hand` / `left_hand` |
| Trigger numbers | `triggers.codes` (keep your EEG script in sync) |
| Self-timing delays | `tasks.self_timing.delays_s` **and** `cue_colors` (same labels) |
| Task order | `schedules:` |
| Stimulus colours/sizes | each task's `cue` / `warning` / `target` block |

After **any** edit: `python tools/test_offline.py`. It re-derives trial counts,
checks the validity mix, verifies every trigger code the tasks can emit is
defined, and confirms each task's data columns match its `FIELDS` list. It
takes two seconds and catches the mistakes that would otherwise appear
mid-session.

### Adding a task

1. Write `battery/tasks/my_task.py` exposing `run(ctx, **kwargs)` and a
   module-level `FIELDS` list.
2. Add it to `REGISTRY` in `battery/tasks/__init__.py`.
3. Add its parameters under `tasks:` and reference it from a schedule.

---

## 6. Timing: what is guaranteed and what is not

This is the part worth understanding before you trust a millisecond.

* **Frame-locked presentation.** Every duration is converted to a whole number
  of frames and presented by counting flips. Nothing uses `core.wait()` for
  stimulus timing.
* **Triggers and the response clock fire on the flip.** Both are scheduled with
  `win.callOnFlip()`, so the EEG marker and the RT origin coincide with the
  screen, not with when Python got round to it.
* **Rounding is real and is logged.** At 144 Hz a 700 ms SOA becomes 101 frames
  = 701.4 ms, and a 100 ms stimulus becomes 14 frames = 97.2 ms. The error is
  always under half a frame, it is identical across conditions, and
  `check_install.py` prints it for your monitor. The measured refresh rate is
  written into every JSON sidecar.
* **Response triggers carry up to one frame of jitter**, because presses are
  detected in the per-frame poll. Use the `rt_s` column for analysis; the
  response trigger is for segmentation convenience only. Stimulus triggers do
  not have this problem.
* **Verify, don't assume.** Enable the photodiode patch
  (`display.photodiode.enabled: true`, on by default), tape the sensor over the
  corner, and record it as an EEG channel. You then have the true onset of
  every critical event and can measure your display lag rather than trust it.

`check_install.py` also runs a frame-drop test. Above ~1 % late frames, close
background applications, disable desktop compositing and GPU overlays, and set
the graphics card to maximum performance.

---

## 7. Data output

```
data/sub-P01/ses-1/
    sub-P01_ses-1_task-temporalorienting_run-run1_beh.csv
    sub-P01_ses-1_task-temporalorienting_run-run1_beh.json
    ...
    sub-P01_ses-1_sessionlog.json
```

* **CSV** — one row per trial, flushed immediately. Existing files are never
  overwritten; a repeat run gets a `_dup1` suffix.
* **JSON sidecar** — the complete effective configuration, the measured frame
  rate, the trigger backend, software versions, and an end-of-run summary.
  Everything needed to reconstruct what was presented.
* **Session log** — append-only record of which tasks ran, in what order, and
  whether the session completed or was aborted.

Key columns in the temporal-orienting file: `context`, `soa_label`, `validity`,
`is_catch`, `rt_s`, `anticipation`, `miss`, `target_clock_s`, `trigger_target`.
The primary outcome is `median(rt_s | invalid) - median(rt_s | valid)`, computed
separately for `context == "interval"` and `context == "rhythm"`.

---

## 8. EEG triggers

Set `triggers.backend` to `parallel`, `serial_bp` (Brain Products TriggerBox),
`lsl`, or `none`. Codes live in `triggers.codes` and are looked up by name, so
the config file *is* the contract with your EEG analysis script.

If the hardware cannot be opened the program prints a loud warning and falls
back to `none` rather than crashing — it will still run, but **no markers are
sent**, so check the start-up output before every session. `check_install.py`
reports this as a failure rather than a warning.

---

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `REFUSING TO RUN` on refresh mismatch | Set `display.nominal_refresh_hz` to the real rate, or fix the monitor. `allow_refresh_mismatch: true` overrides — piloting only. |
| `ModuleNotFoundError: psychopy` | Run via the PsychoPy python (see `run_windows.bat`), not the system python. |
| Frame drops above 1 % | Close other applications, disable compositing/overlays, set the GPU to maximum performance, run fullscreen. |
| Stimuli the wrong size | `display.monitor` (width, distance, resolution) is wrong — `deg` units depend on it. |
| Triggers not arriving | Check the start-up line reporting the backend; confirm the port; on 64-bit Windows a parallel port needs inpoutx64. |
| Participant reports the wrong key | `response.keymap.right_hand` / `left_hand`. |
| Validity effect negative at baseline | Almost always the key mapping or the instructions, not the participant. |

---

## 10. Notes for the record

* Trial order is seeded reproducibly from participant + session + schedule, so
  a crashed session can be resumed with the same order (`--seed` overrides).
* Block order in the temporal orienting task rotates with run number, so no
  context is systematically tested first or last after stimulation.
* Self-timing hand order alternates with session number, so hand order is not
  confounded with the crossover condition.
* Catch trials (no target) are included so that pure anticipation cannot pay
  off; false alarms on those trials are recorded.

---

## 11. What has actually been verified

Version 1.0.1. Two levels of testing, and it is worth knowing which is which.

**Offline** — `python tools/test_offline.py`, 73 checks, no screen required.
Config merging and validation, trial counts and validity mix per block, invalid
trials using the *other* SOA, shuffle constraints, block-order rotation, seed
reproducibility, hand-order alternation, the complete trigger table against
every code the tasks can emit, each task's data columns against its `FIELDS`
list, the CSV/JSON writer, and frame-rounding arithmetic from 60 to 240 Hz.

**Live** — full battery run on a real 60 Hz screen with `--autopilot`, all four
tasks, 88 temporal-orienting and 120 self-timing trials:

| Check | Result |
|---|---|
| Warning→target interval, 700 ms intended | measured 699.3–701.3 ms across all four cells |
| Warning→target interval, 1200 ms intended | measured 1198.5–1200.2 ms |
| Validity → SOA mapping | correct in every cell (valid-in-short = 700, invalid-in-short = 1200, inverted in long blocks) |
| Self-timing start event, predicted vs measured | **−1.35 ms mean, SD 4.1 ms** (max 15.8 ms = one frame) |
| Injected RT distribution recovered | 361 ± 50 ms from an injected 350 ± 55 ms (n = 77) |
| Injected interval variability recovered | CV 0.090 injected → **0.090** recovered (n = 120) |
| Injected vs recorded interval, trial by trial | +6.2 ms, SD 5.0 (n = 48) — see note below |
| Edge paths | anticipations, misses, catch trials and premature presses all exercised |

**About that +6.2 ms.** It is not a scoring error. The autopilot timestamps its
own simulated presses from inside a trigger callback; the task scores against
frame-count arithmetic referenced to the flip. The +6.2 ms is the gap between
those two reference points, and a real keypress uses *neither* — it is
timestamped by the keyboard driver. The number that does transfer to real data
is the one directly measured above: the scoring reference (`start_rel_predicted`)
matches the actual flip to **−1.35 ms, SD 4.1 ms**. Both figures are recorded in
every self-timing data file (`start_rel_predicted_s`, `start_rel_measured_s`), so
you can check this on your own hardware at any time.

**Not verified, and not verifiable this way:**

* **Keyboard/response-box latency.** The autopilot injects presses inside
  PsychoPy, so it tests the scoring arithmetic, not the input hardware. Measure
  this on the lab machine with a photodiode and the actual response device.
* **Real trigger hardware.** Only the `none` backend has been exercised. Confirm
  parallel/TriggerBox output with an oscilloscope or a test EEG recording before
  the first participant.
* **The Cedrus code path**, which is written but has never run against a device.
* **Fullscreen timing on the lab monitor.** `check_install.py` is the gate.
