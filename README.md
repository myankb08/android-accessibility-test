# HintBack form study: correct and degraded

The active corpus has two versions of one working form. The original L0–L5 source,
assets, generated pages, and scoring files are preserved in `archive/legacy-levels/`.
Do not mix legacy announcement measurements with this revised corpus.

The correct version uses visible, associated labels. The degraded version converts
only the six text-field labels to visible spans without an association. Both have
no placeholders, hidden labels, overlays, CAPTCHA, or nonfunctional imitation controls.
Both retain native input types. Both use the same opaque IDs/names (`f01`…`f11`),
`autocomplete="off"`, visible context, styling, validation, and task data. Browser
heuristics may still infer names or offer autofill; check the actual device settings.

Targets: first name, last name, email, password, confirm password, phone number.
Country and the three birthday dropdowns remain correctly labelled and functional.
The email preference remains a native labelled checkbox. This is a test of missing
label associations, not of incorrect labels or missing control functionality.

## Published study page

Open https://myankb08.github.io/android-accessibility-test/ in Chrome on the study phone.
The researcher setup page selects the correct/degraded version, a coded trial ID,
reader condition, and fictitious dataset A or B. No USB connection or local server is
required to load the published pages; an internet connection is required.

Only `site/` is deployed to GitHub Pages. The editable source, tests, ground truth,
and legacy L0–L5 archive remain in this repository. The deployment workflow rebuilds
and tests the active corpus before publishing it.

Web task validation and records are processed in the browser. Hosting serves the
static files, and normal hosting access logs may include request metadata. The page
does not send form entries or study JSON exports to a server.

## Build and preview

From this directory:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python build.py
python3 -m http.server 8000 --directory site
```

Open `http://localhost:8000/` for researcher setup. For an Android phone over USB:

```sh
adb reverse tcp:8000 tcp:8000
```

Then open the same address in Chrome on the phone. All processing is local. The
static server receives requests for files, not form entries. Use the generated pages;
`apple-signup.html` is the build source, not the directly runnable study page.

The setup page supplies two provisional fictitious datasets, A and B. They are not
yet validated as equally difficult. Read/provide the task information separately in
an accessible format. Use a unique coded trial ID and keep it identical in Android
capture and web setup. The reader selection on the setup page records the condition;
it does not switch Android accessibility services or enable/disable the model.

## Task behaviour and records

Start begins the elapsed timer and reveals the form. Continue checks the expected
values in their correct fields; an empty or wrong-field entry cannot count as success.
Errors use the same neutral wording in both versions, with focus moved to an error
summary and links back to affected controls. No error reveals the expected answer or
adds a missing field name. Email case and surrounding whitespace are normalized;
passwords are exact; phone spaces, parentheses, and hyphens are ignored. The dummy
phone strings are test values only and are never dialled or sent a message.

A successful submission announces task completion. End task records a stopped
session. Either outcome reveals a researcher section to download JSON. Download it
before leaving the page: records are intentionally in memory only, and reload/closing
loses them. The export contains timestamps, per-field correctness, DOM focus/input
counts, first/last input times, submission attempts, and outcome; it excludes entered
strings. Form values are cleared at task end. Browser events are also logged to the
browser console as `HintBackWeb` JSON, not automatically to Android logcat.

**DOM focus is not accessibility focus.** A TalkBack swipe may not generate a DOM
focus event. Use Android focus records for navigation analysis. Deletion-event count
is a partial correction measure, not a count of all errors. Web duration uses a
monotonic clock from Start through accepted submission/End; it includes typing and
hint delays. Clock timestamps aid alignment, but web and Android monotonic origins
are different. Trial ID is the primary join key.

## Capture Android diagnostics

Build/install the revised phone debug APK as described in [the HintBack build notes](https://github.com/myankb08/HintQT5-draft/blob/main/TALKBACK_BUILD_NOTES.md).
The July 2026 installed build does not support the newer trial-start/end diagnostic broadcasts.
Enable that build's accessibility service. No device settings are changed by this
repository's build or browser tests.

Before opening each form, start capture from this directory:

```sh
python3 tools/study_logs.py capture --trial P01_D_H_A --reader hintback --output P01_D_H_A.android.jsonl
```

Wait for `Ready`, then open the form with the same trial ID. Complete or stop the task,
export the web JSON, then press Ctrl-C in the capture terminal. This closes the Android
trial. Use a new output filename: the tool refuses to overwrite existing records.
Add `--serial SERIAL` if multiple devices are attached.

For the same-build comparison with generation disabled:

```sh
python3 tools/study_logs.py capture --trial P01_D_T_B --reader talkback --output P01_D_T_B.android.jsonl
```

Here `talkback` means **the same research APK with generation disabled**, not the
separately installed Google TalkBack package. This controls build/version differences.
If using stock TalkBack, this capture cannot observe its internal decisions. Record
its exact version and settings separately; confirm the final comparison in the protocol.

The start command resets cached hints and invalidates pending callbacks. Model weights
stay loaded, so a cache reset is not a cold model startup. Logs report model load,
queue wait, inference, and request-to-result timing separately. Keep OCR, verbosity,
keyboard, speech rate, and other settings consistent between paired conditions.
Previously saved native custom labels from older builds are not deleted by this command;
new hints no longer write to that database. Web study fields use memory-only hints.

Detailed traces are opt-in and debug-only. They may contain node text, prompts, and
fictitious entries; collect them only on the controlled study page with dummy data.
There is no audio recording. Chunked logcat records preserve long Unicode prompts;
the capture tool reconstructs ordinary JSONL. To decode an existing text capture:

```sh
python3 tools/study_logs.py decode raw-logcat.txt decoded.jsonl
```

Recorded Android events include:

- `trial_start` / `trial_end`: session identity and engine mode.
- `focus`: accessibility or input focus, node identity and snapshot.
- `eligibility`: skipped by label manager, existing text/hint/label/state, disabled,
  eligible cache miss, or cached hint composed. These are compositor calls, not visit counts.
- `request`: exact prompt, target and candidate nearby nodes, input type, context scope.
  The candidate list precedes PromptBuilder's own filtering; inspect the exact prompt
  to see what was actually submitted.
- `tokenized` / `decoded`: token IDs, raw/cleaned model output, generation cap reached.
- `generation_complete`: model inference and queue/request timing.
- `generation_discarded` / errors: stale-trial results or failures.
- `speech_queued`, `speech_started`, `speech_completed`, `speech_skipped`: delivery of
  fresh hints. `spoken=true` reflects TalkBack's completion callback, not proof of comprehension.

Cached-hint records mean text was composed into ordinary TalkBack feedback. They do
not currently carry a completion callback for that whole utterance. First-visit hints
still arrive after ongoing speech; repeat visits can lead with the cached hint. This
behaviour is now observable, not claimed to be resolved or timing-equivalent.

Cache keys include session, package, window, document identity/text, and field identity;
coordinates are not used. Document identity is best-effort on Android, so always start
a new trial before loading a new page. Context extraction is restricted to the nearest
web document when available, to exclude Chrome toolbar controls; `context_scope=window`
marks the fallback that must be inspected on the study phone.

## Scoring and next pilot

`ground-truth/apple-signup.json` defines the intended field labels. `expected.json`
records design expectations, not a measured Android accessibility tree. All 11 fields
are scored for form completion; report the six HintBack target fields separately.
The email preference is optional in the form but task instructions ask participants to
leave it unchecked; its requested state is included in the task correctness check.

First run a researcher walkthrough of correct/degraded with generation off/on. Use a
fresh trial each time and inspect first versus repeat focus, prompts, skipped triggers,
cache reuse after scrolling, errors, and actual speech. A correct form should receive
no unnecessary hints. Do not weaken the degraded page until a desired model score is
obtained: fix the defect definition first, then report performance honestly.

The participant protocol remains provisional. Separate field identification from typing
if that task is retained; counterbalance order and account for learning of the same form.
Record keyboard experience and keep the input method consistent within participant.
Use a separate practice task. BLV and sighted groups remain separate in analysis.
The full form's timed task, researcher instructions, and hint timing need a device pilot
before freezing the participant task set and updating the other IEC documents.

## Verification

```sh
.venv/bin/playwright install chromium
.venv/bin/python -m unittest discover -s tests -v
```

Browser checks cover identical screenshots, correct/degraded accessibility names,
invalid and wrong-field submissions, both dummy datasets, success/stopped exports,
and absence of entered strings in web logs. Decoder tests cover long Unicode prompts,
interleaving, and incomplete records. Android compilation does not replace device tests.
