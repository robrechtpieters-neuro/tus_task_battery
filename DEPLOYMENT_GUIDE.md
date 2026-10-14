# Setting Up the Task Battery on a Dedicated Testing PC

**A step-by-step guide assuming no programming experience**
**Version 1.0 — 31 July 2026**
**Applies to:** TUS Dentate Nucleus Task Battery v1.0

You will not have to write any code. You will copy a folder, run an installer,
change three numbers in a text file, and then double-click things.

Set aside about **90 minutes** the first time. Most of it is waiting for the
PsychoPy installer.

---

## 1. Before you start: why a dedicated PC

The experiment measures reaction times in milliseconds. Anything else running
on the computer — a virus scan, a cloud sync, a chat app checking for messages —
can delay a screen refresh by 10 or 20 ms. That delay lands in your data and
looks exactly like a real effect.

So the testing PC should do one job: run this experiment. No email, no
browsing, no OneDrive, no Teams. If you can, keep it off the network entirely
except when you deliberately copy data off it.

### What to ask IT for

| Component | What to ask for | Why it matters |
|---|---|---|
| **Monitor** | 144 Hz or faster, connected by **DisplayPort** (not HDMI if avoidable) | More refreshes per second means your stimulus timing is accurate to ~7 ms instead of ~17 ms |
| **Graphics** | Any dedicated NVIDIA or AMD card | Built-in laptop graphics drop frames under load |
| **CPU / RAM** | Any modern desktop CPU, 16 GB RAM | Not demanding; reliability matters more than speed |
| **Storage** | SSD | Data is written to disk after every single trial |
| **Operating system** | Windows 10 or 11, **Pro** if possible | Pro lets you defer updates properly |
| **Response device** | Cedrus RB-x40 button box, or an Ekey/Black Box Toolkit device | A normal USB keyboard adds 5–30 ms of *variable* lag. The battery supports both; see §6 |
| **Admin rights** | Yes, for whoever sets it up | You need them to install software and change power settings |

A laptop can work if it is plugged into mains power and its screen is
adequate, but a desktop with a proper gaming monitor is much better.

---

## 2. What to copy across (and what not to)

You are copying **one folder**: `tus_task_battery`.

There is a ready-made zip file next to it:

```
tus_task_battery_v1.0.zip
```

**Do copy:** that zip file. It contains the whole experiment — about 200 KB.

**Do NOT copy:**

| Item | Why not |
|---|---|
| The `.venv` folder | 1.2 GB, and it does not work on another computer. Its files contain the exact path of *this* machine baked in. The new PC gets its own PsychoPy (§4) |
| The `data` folder | That is collected data from testing. Starting clean avoids confusion |
| Any `__pycache__` folders | Automatically regenerated |

The zip already excludes all three.

### How to get the zip onto the new PC

Any of these is fine:

1. **USB stick** — simplest, and works on an offline PC. Recommended.
2. **OneDrive / SharePoint** — upload the zip, download it on the other side.
   Then **remove it from the sync folder** (see §5).
3. **Email it to yourself** — it is small enough.

---

## 3. Where to put it on the new PC

Create this folder and unzip into it:

```
C:\Experiments\tus_task_battery
```

**To unzip:** right-click the zip file → *Extract All…* → change the destination
to `C:\Experiments` → *Extract*. You should end up with
`C:\Experiments\tus_task_battery\run_windows.bat` and so on.

Three rules about the location, and they matter more than they look:

1. **Not inside OneDrive, Dropbox, Google Drive or any synced folder.**
   Sync clients wake up and read files while you are recording. They cause
   dropped frames, and because the experiment writes to the data file after
   every trial, a sync client can also lock a file mid-write.
2. **Not on a network drive (`\\server\...` or a mapped `Z:\`).**
   Same reason, worse.
3. **A short path with no spaces**, like `C:\Experiments\`. Long paths with
   spaces and accented characters cause avoidable trouble.

---

## 4. Install PsychoPy

PsychoPy is the free software that draws the stimuli and reads the keys. The
"Standalone" version includes everything needed — you will not have to install
anything else.

1. Go to **https://www.psychopy.org/download.html**
2. Download the **Windows Standalone installer** (a file ending in `.exe`).
   Choose the latest release unless your lab standardises on a version.
3. Run it. Accept the default install location, which will be
   `C:\Program Files\PsychoPy\`.
4. That is all. Do **not** open PsychoPy itself — you will never need its
   interface. The experiment uses it in the background.

> **Why the default location matters:** the launcher files look for PsychoPy in
> the standard places automatically. If you install it somewhere unusual, see
> §11 for the one line you would need to edit.

The battery was developed and verified against **PsychoPy 2026.2.1**. Anything
from 2023.2 onwards should work.

---

## 5. Turn the PC into a low-latency machine

Work through this once. It takes about 20 minutes and it is the difference
between clean data and data with an unexplained 15 ms of noise in it.

### 5.1 Monitor and refresh rate

1. Right-click the desktop → **Display settings** → scroll down →
   **Advanced display**.
2. Note the **resolution** (e.g. 1920 × 1080) and set **Refresh rate** to the
   highest value offered (e.g. 144 Hz). **Write both numbers down** — you need
   them in §6.
3. In the monitor's own on-screen menu (the physical buttons on the monitor):
   - Turn **Game Mode / Low Latency Mode ON** — this bypasses the monitor's
     internal image processing.
   - Turn **overdrive, motion blur reduction, dynamic contrast and any
     "eco" mode OFF** — each adds processing delay.
   - Turn **G-Sync / FreeSync / Adaptive Sync OFF**. Variable refresh rate is
     exactly what you do not want: you need a fixed, predictable refresh.

### 5.2 Graphics driver (NVIDIA shown; AMD is equivalent)

Right-click desktop → **NVIDIA Control Panel** → **Manage 3D settings** →
**Global Settings**:

| Setting | Set to |
|---|---|
| Power management mode | **Prefer maximum performance** |
| Vertical sync | **On** |
| Low Latency Mode | **Off** |
| Monitor Technology | **Fixed Refresh** |
| Triple buffering | **Off** |

Vertical sync being **on** is deliberate. It is what locks each stimulus to a
real screen refresh, which is what the timing depends on.

### 5.3 Windows settings

1. **Power plan.** Control Panel → Power Options → choose **High performance**.
   Then *Change plan settings* → *Change advanced power settings*:
   - Hard disk → Turn off after: **Never**
   - Sleep → **Never**, hibernate **Never**
   - USB settings → USB selective suspend: **Disabled** (this one matters for
     response boxes)
   - PCI Express → Link State Power Management: **Off**
2. **Screen saver:** off. Settings → Personalisation → Lock screen → Screen
   saver settings → *(None)*.
3. **Notifications:** Settings → System → Notifications → turn **off**. Then
   turn **Focus assist / Do not disturb ON**.
4. **Game Bar:** Settings → Gaming → Xbox Game Bar → **off**. Also turn off
   *Captures* → *Record what happened*.
5. **Windows Update:** Settings → Windows Update → Advanced options → set
   **Active hours** to cover your testing times so it cannot restart mid-session.
   On Windows Pro you can also pause updates for up to five weeks.
6. **Startup programs:** Ctrl+Shift+Esc → *Startup apps* tab → disable
   everything you do not recognise as essential. Particularly: Teams, Discord,
   Spotify, GeForce Experience, OneDrive, Dropbox, any printer or webcam
   utility.

### 5.4 Antivirus — the one people forget

The experiment writes to the data file after **every trial**. Real-time virus
scanning inspects each write, and on some corporate setups that costs enough
time to drop a frame.

Ask IT to add an exclusion for:

```
C:\Experiments\
```

In Windows Defender you can do it yourself: Windows Security → Virus & threat
protection → Manage settings → Exclusions → Add an exclusion → Folder →
`C:\Experiments`.

### 5.5 Before every session

A short ritual, worth doing every time:

- Close every other application (check the system tray, bottom right).
- Unplug the network cable / turn off Wi-Fi if your setup allows it.
- If you use a second monitor, **disconnect it**. Extended desktops can force
  Windows into a compositing mode that adds a frame of lag.

---

## 6. Tell the software about your setup

This is the only file you must edit. It is a plain text file with comments
explaining every line.

1. Open `C:\Experiments\tus_task_battery\config\default.yaml`
   with **Notepad** (right-click → Open with → Notepad).
   Do not use Word — it will add formatting that breaks the file.
2. Find this section near the top and change the three highlighted numbers:

```yaml
display:
  nominal_refresh_hz: 144          # <-- your monitor's refresh rate from §5.1
  monitor:
    width_cm: 53.0                 # <-- width of the VISIBLE screen area, in cm
    distance_cm: 80.0              # <-- eye-to-screen distance you will use
    resolution: [1920, 1080]       # <-- your resolution from §5.1
```

- **`nominal_refresh_hz`** must match your monitor. If it does not, the
  program will refuse to start and tell you so — deliberately, because
  every duration in the experiment is counted in screen refreshes.
- **`width_cm`** is measured with a ruler, across the lit part of the screen
  only, not the plastic bezel.
- **`distance_cm`** is where the participant's eyes will actually be. Use a
  chin rest so it is the same every time. The protocol assumes 80 cm.

3. If you are using a **response button box** rather than a keyboard, also find:

```yaml
response:
  backend: "keyboard"              # change to "cedrus" for a Cedrus box
```

and change `keyboard` to `cedrus`. Otherwise leave it alone. The default
keyboard keys are **J** (right hand) and **F** (left hand).

4. If your EEG trigger cable is connected, find:

```yaml
triggers:
  backend: "none"                  # change to: parallel | serial_bp | lsl
```

- `parallel` — a parallel/LPT port. Also set the `address` below it.
- `serial_bp` — a Brain Products TriggerBox. Also set the `port` (e.g. `COM3`).
- `lsl` — Lab Streaming Layer.

Leave it as `none` while you are still practising; the codes are still saved
to the data files either way.

5. **Save the file** (Ctrl+S) and close Notepad.

> **A safer alternative:** rather than editing `default.yaml`, you can copy
> `config/example_override.yaml`, put only your changed lines in it, and launch
> with that file. See §11. For a single dedicated PC, editing `default.yaml`
> directly is simpler.

---

## 7. Run the pre-flight check

**Double-click `check_install.bat`** in `C:\Experiments\tus_task_battery\`.

A black window opens, a grey window flashes up for a few seconds, and you get a
report. You want to see this at the bottom:

```
  All checks passed. This machine is ready to collect data.
```

The check tests six things, in order: PsychoPy is installed; your config file
is valid; the trial lists build correctly; the EEG trigger port opens; the
response device opens; and — the important one — it measures your actual
refresh rate and counts dropped frames over three seconds.

**The number to care about** is the frame-drop test:

| Result | Meaning |
|---|---|
| **under 1 %** | Good. Collect data. |
| **1–5 %** | Something is stealing time. Go back through §5.3 and §5.4. |
| **over 5 %** | Do not collect data. Usually a sync client, an antivirus scan, or a laptop on battery power. |

Run this check on the first day, and again any time the PC has had a Windows
update or a new program installed.

---

## 8. Try it out before you touch a participant

Before any real testing, run the whole battery yourself in **demo mode** — a
few trials of each task, in a window, taking about four minutes.

Make a shortcut for it:

1. Right-click `run_windows.bat` → *Create shortcut*.
2. Right-click the new shortcut → *Properties*.
3. In the **Target** box, go to the very end of the existing text, add a space,
   and type `--demo`. It should now read something like:
   ```
   "C:\Experiments\tus_task_battery\run_windows.bat" --demo
   ```
4. Click *OK*, rename the shortcut to **DEMO (practice)**, and double-click it.

Demo mode runs the entire battery in about four minutes with a handful of
trials each, in a window rather than fullscreen. Go through it yourself as if
you were the participant. Press **J** for the green squares. Press **Escape**
at any time to stop.

Do this before every participant's first session too — it is the fastest way to
confirm the response keys are working.

---

## 9. Everyday running: make one shortcut per block

You will run different parts of the battery at different times. Rather than
typing anything, make a desktop shortcut for each, exactly as in §8 but with a
different ending in the **Target** box:

| Shortcut name | Add this to the end of Target | Runs | Approx. |
|---|---|---|---|
| **1. Familiarisation (imaging visit)** | `--schedule familiarisation` | Practice of every task, with a comprehension check. Not scored | ~35 min |
| **2. Post-TUS, whole battery** | `--schedule post_tus` | Temporal orienting, self-timing, simple RT, resting — one pass | ~50 min |
| **3. Post-TUS self-timing** | `--schedule st_only` | Self-timing only | ~13 min |
| **4. Temporal orienting only** | `--schedule to_only` | Restart this part after an interruption | ~27 min |
| **5. Post-TUS simple RT** | `--schedule rt_only` | Simple RT only | ~5 min |
| **6. Post-TUS rest** | `--schedule rest_only` | Resting EEG | ~7 min |
| **7. _(unused)_** | | | |
| **DEMO (practice)** | `--demo` | Everything, tiny | ~4 min |

Running the post-TUS blocks one at a time (shortcuts 2–7) is what the protocol
assumes, because *you* decide when each starts relative to the sonication. There
is also a single `--schedule post_tus` that chains all of them back to back, but
you lose that control.

> **Timing note worth knowing.** Those durations add up to about **75 minutes**
> of task for the post-TUS sequence, which is longer than the ~60 minute window
> in which the stimulation effect is expected. This is the open design decision
> flagged in the proposal: either accept a longer window, or reduce
> `trials.per_cell` in the config from 40 to about 28, which brings three
> temporal-orienting runs inside the hour at the cost of some statistical power.
> Decide this before the first real participant, not after.

### What happens when you double-click

1. A setup dialog appears. Fill in:
   - **participant** — the ID, e.g. `P01`
   - **session** — 1, 2 or 3
   - **phase** — `familiarisation` (imaging visit) or `post_tus` (stimulation day)
   - **run** — leave as is unless you have a reason
   - **condition_code** — the **blinded** code from your allocation file.
     Never the real condition. The person running tasks must not know it.
   - **experimenter** — your initials
2. Click **OK**. The screen goes grey and instructions appear.
3. The participant reads each screen and presses **Space** to continue.
4. When it finishes, a summary is printed and the window closes.

**To stop early:** press **Escape**. Everything collected up to that moment is
saved. Nothing is lost.

---

## 10. Where the data goes

Everything lands here, created automatically:

```
C:\Experiments\tus_task_battery\data\sub-P01\ses-1\
```

One folder per participant, one sub-folder per session. Inside, for each task
you ran, three kinds of file:

| File | What it is |
|---|---|
| `..._task-temporalorienting_run-run1_beh.csv` | **The data.** One row per trial, opens in Excel |
| `..._task-temporalorienting_run-run1_beh.json` | A complete record of the settings used, the measured refresh rate, the trigger codes, and a summary. This is what makes the session reproducible |
| `..._sessionlog.json` | What was run, in what order, and whether it finished or was aborted |

Two things worth knowing:

- **Files are never overwritten.** Run the same block twice and the second gets
  `_dup1` added to its name. You will never silently lose data.
- **Data is written after every trial**, not at the end. If the PC crashes on
  trial 150, trials 1–149 are already safely on disk.

### Backing up

The testing PC is not a backup. After each session:

1. Plug in a USB stick.
2. **Copy** (do not move) the entire `data` folder onto it.
3. Once a week, copy that onto your institutional network storage or OneDrive.

Copying the whole `data` folder each time is simplest and safest — it is tiny,
a few hundred KB per session.

---

## 11. Analysing the data

### 11.1 The same-day check — do this before the participant leaves

**Double-click `quicklook.bat`.**

It prints a summary of everything collected so far. To check just one session,
**drag that session's folder onto `quicklook.bat`** instead.

You are looking at the **validity effect** — the last column. It is the
reaction time on invalid trials minus the reaction time on valid trials, in
milliseconds. It should be **clearly positive in both the rhythm and the
interval rows**, typically 30–90 ms.

```
  context   SOA     n val n inv   RT val   RT inv    effect
  interval  long       89    30      364      411        47
  interval  short      90    29      355      380        25
  rhythm    long       90    30      350      404        54
  rhythm    short      89    30      348      399        51
```

If a validity effect is near zero or negative **at baseline**, do not conclude
anything about the participant. Suspect the setup: wrong response key, monitor
timing, or the participant not having understood the instructions. Fix it and
retest before you burn a session.

### 11.2 Looking at the data yourself in Excel

Double-click any `_beh.csv` file — it opens in Excel.

For the temporal orienting task, the columns you need are:

| Column | Meaning |
|---|---|
| `context` | `rhythm` or `interval` |
| `soa_label` | `short` (0.7 s) or `long` (1.2 s) |
| `validity` | `valid`, `invalid` or `catch` |
| `rt_s` | Reaction time **in seconds** (multiply by 1000 for ms) |
| `responded` | 1 if they answered, 0 if they missed |
| `anticipation` | 1 if they jumped the gun — exclude these |
| `is_catch` | 1 on no-target trials — exclude these |

**To compute the primary outcome by hand:**

1. Select all data → *Insert* → *PivotTable*.
2. First, filter out the trials you should not include: set the filters so that
   `is_catch = 0`, `responded = 1`, and `anticipation = 0`.
3. Drag `context` and `validity` into **Rows**.
4. Drag `rt_s` into **Values**, and set it to show the **Average** (Excel
   cannot do medians in a pivot table; average is close enough for a check).
5. For each context: **validity effect = invalid − valid**.
6. The number the study is actually about is
   **(interval effect) − (rhythm effect)**, and specifically how *that*
   changes between the real-stimulation and sham sessions.

### 11.3 Doing the real statistics without coding

For the actual analysis, use **JASP** (free, from https://jasp-stats.org). It
has a point-and-click interface and produces the mixed-model and Bayes-factor
analyses named in the proposal.

The workflow is: use quicklook or Excel to produce one row per participant per
condition per context, save that as a CSV, and open it in JASP. If your
department has a statistician, this is the point to involve them — the analysis
plan in §15 of the proposal is pre-registered and should be followed exactly.

### 11.4 The EEG side

The behavioural files and the EEG recording are linked by the **trigger codes**.
The full table lives in `config/default.yaml` under `triggers: codes:`, and a
copy of it is saved into every `_beh.json` file, so you always know which codes
were in force for a given session.

Your EEG analyst will need:

1. The trigger code table (from the config or any `_beh.json`).
2. The behavioural CSVs, to sort EEG epochs by condition.
3. To know that the **photodiode channel** is the ground truth for stimulus
   onset. Tape the sensor over the white square in the bottom-right corner of
   the screen and record it as an extra channel. Trigger codes are accurate to
   about one screen refresh; the photodiode is accurate to the millisecond.

EEG analysis itself happens in BrainVision Analyzer, EEGLAB, FieldTrip or MNE —
outside this software.

---

## 12. If something goes wrong

| What you see | What to do |
|---|---|
| **"REFUSING TO RUN"** with a refresh-rate message | Your monitor is not running at the rate in the config. Either fix the Windows display setting (§5.1) or change `nominal_refresh_hz` to match |
| **"psychopy not importable"** | PsychoPy is not installed, or is somewhere unusual. Reinstall to the default location (§4) |
| **Frame drops above 1 %** | Work through §5.3 and §5.4 again. Most often: a sync client, antivirus, or a laptop on battery |
| **Key presses do nothing** | The experiment window has lost focus. Click on it once. If it persists, check `response.keymap` in the config |
| **Black window flashes and closes instantly** | An error occurred. Run `check_install.bat` instead — it pauses and shows the message |
| **PsychoPy installed somewhere unusual** | Open `run_windows.bat` in Notepad. Find the line `REM set "PY=C:\Program Files\PsychoPy\python.exe"`, delete the `REM ` at the start, and correct the path. Do the same in `check_install.bat` and `quicklook.bat` |
| **You want to undo a config change** | The original is in the zip file. Extract a fresh `config/default.yaml` from it |

---

## 13. First-day checklist

Print this page.

**Setup, once per PC**

- [ ] Zip copied across and extracted to `C:\Experiments\tus_task_battery`
- [ ] Confirmed the folder is **not** inside OneDrive or on a network drive
- [ ] PsychoPy Standalone installed to the default location
- [ ] Monitor set to its highest refresh rate; resolution and refresh written down
- [ ] Monitor Game Mode on; overdrive, adaptive sync and eco modes off
- [ ] Graphics settings applied (§5.2)
- [ ] Power plan High performance; sleep, hibernate, USB suspend all off
- [ ] Notifications, Game Bar and startup programs disabled
- [ ] Antivirus exclusion added for `C:\Experiments\`
- [ ] `config/default.yaml` edited: refresh rate, screen width, viewing distance, resolution
- [ ] `check_install.bat` run — **all checks passed**, frame drops **under 1 %**
- [ ] Demo mode run through personally, start to finish
- [ ] Desktop shortcuts created for each block (§9)

**Before each session**

- [ ] All other applications closed; Wi-Fi off; second monitor disconnected
- [ ] Chin rest at the distance in the config
- [ ] Demo run once to confirm response keys work
- [ ] Blinded condition code to hand — **not** the real condition

**After each session**

- [ ] `quicklook.bat` run; validity effect positive in both contexts
- [ ] `data` folder copied to a USB stick
- [ ] Anything unusual noted in the lab book, referencing the participant and
      session numbers so it can be matched to the files
