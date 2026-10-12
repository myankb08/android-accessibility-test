# Accessibility degradation testbed — sign-up form

A controlled test corpus for evaluating screen-reader behaviour on forms with
missing or incorrect programmatic labels.

One hand-authored sign-up form is rendered at six levels of accessibility-tree
degradation. **Every level renders identically.** The visual layer is held
constant and the accessibility tree is the sole independent variable, so any
difference in screen-reader output is attributable to the degradation and not
to a change in layout, spacing or visible text.

## Provenance

The markup **and the stylesheet** here are **hand-authored**. No third-party
HTML, CSS or JavaScript is reproduced in this repository. The field inventory — name, country, birthday,
email, password, phone, marketing opt-ins, verification — reflects a
conventional consumer sign-up flow.

The visual treatment was matched by *measurement*, not by copying: colours and
dimensions were sampled from a rendered reference screenshot and
re-implemented independently. Those measurements — a 482px column, 56px
controls with 1px `#86868b` borders, a 12px radius, `#6e6e73` placeholder ink,
10px horizontal and 14px vertical gaps — are facts about how a page looks, not
protected expression. SF Pro is referenced in the font stack but not bundled,
since it is not licensed for redistribution; on Android the stack resolves to
Roboto.

This matters for two reasons beyond licensing. Hand-authored markup can be
*proved* clean at L0 rather than assumed clean, and it degrades deterministically
because there is no framework re-injecting ARIA at runtime.

The verification image is a static SVG placeholder. It performs no bot
detection and has no correct answer.

## Layout

```
baseline/apple-signup.html      the only file you edit by hand
build.py                        generates everything below
site/
  index.html                    level chooser
  assets/style.css              shared by all levels — guarantees visual parity
  assets/captcha.svg
  L0..L5/index.html             generated
  L0..L5/expected.json          predicted accessible name per field per level
ground-truth/
  apple-signup.json             scoring key
  apple-signup-expected-matrix.csv   field x level status table
```

Regenerate with:

```bash
pip install beautifulsoup4
python3 build.py
```

## The degradation ladder

L0–L4 are cumulative. L5 is an independent condition applied to L0.

| Level | Degradation | Signal remaining |
|---|---|---|
| **L0** | none | correct name on all 20 controls |
| **L1** | label associations broken: `<label for>` → `<span>`, `for` dropped | ARIA names, placeholders, adjacent visible text |
| **L2** | every AT-only string removed: visually-hidden labels deleted; `aria-label`, `aria-labelledby`, `aria-describedby`, `title`, `alt` dropped; `<fieldset>`/`<legend>` → `<div>` | placeholders, visible text, native roles |
| **L3** | `placeholder` and `autocomplete` removed; `id`/`name` replaced with opaque tokens (`e01`, `e02`…) | native role, position, nearby visible text |
| **L4** | native controls replaced by generic containers — `<input>` → `<div contenteditable>`, `<select>` and checkboxes → `<div tabindex="0">`, `<button>` → `<div tabindex="0">` | position and nearby visible text only |
| **L5** | programmatic names swapped between paired fields | a *wrong* name, contradicted by the visible placeholder |

Two design decisions are worth stating explicitly in a write-up.

**L3 repaints rather than deletes.** Placeholder text is visible text, so simply
deleting it would change the rendering and confound the manipulation. Instead
each placeholder is redrawn as an `aria-hidden` `<span>` pinned over the control.
The field still looks labelled; the accessibility tree gets nothing. This is
also the realistic case — labels drawn as images, canvas or decorative markup
are a common real-world failure mode.

**L5 swaps only the invisible name.** The visible placeholder stays correct, so
a sighted user sees the right field while a screen reader is told the wrong one.
Label and placeholder now actively contradict each other, which is the more
interesting test: not only whether a hint can be generated, but whether an
incorrect existing label is detected and overridden.

Only fields whose name is invisible are swapped, which is why L5 renders
identically to L0.

## Visual parity

Verified with headless Chromium at 420 CSS px, full-page, 2× DPR:

Verified with headless Chromium, full-page, at two configurations:

| Level | 1016px @ 2x | 412px @ 2.625x (Android) |
|---|---|---|
| L1, L2, L3, L5 | 0.000% | 0.000% |
| L4 | 0.014% | 0.087% |

The L4 residual is the checkbox tick and the two help-button glyphs, redrawn in
CSS because the native `<input type="checkbox">` and `<button>` no longer exist
at that level. It is confined to four small regions and is not perceptible.

Two details in `style.css` are load-bearing and easy to break:

- `.ghost` sets `line-height` equal to the control's **content-box** height
  (`--control-h - 2px`). That reproduces Chrome's own single-line centring and,
  unlike a flex-centred box, holds at any device pixel ratio. A flex-centred
  ghost matches at 2x and drifts a pixel at 2.625x — which is the ratio the
  study actually runs at.
- That `line-height` must be declared **after** `font: inherit`, because the
  `font` shorthand resets it.

`.ghost` is also inset to the content box rather than the border box: Chrome
clips native placeholder text at the content edge while `overflow: hidden`
clips at the padding edge, so a long string would otherwise run 17px further.

Re-run the check after any edit to `baseline/` or `style.css`.

## Expected results

`ground-truth/apple-signup-expected-matrix.csv` gives the predicted status of
all 20 fields at every level.

| Level | named | unnamed | misnamed |
|---|---|---|---|
| L0 | 20 | 0 | 0 |
| L1 | 12 | 7 | 1 |
| L2 | 8 | 11 | 1 |
| L3 | 2 | 18 | 0 |
| L4 | 5 | 13 | 2 |
| L5 | 6 | 0 | 14 |

Two entries are worth reading closely, because they are exactly the cases a
hint-generation system should be measured on.

`email` is *misnamed* at L1 and L2, not unnamed. With the label unbound, name
computation falls through to the placeholder and the field is announced as
"name@example.com". A user hears a plausible-sounding string and gets no
indication that the label is missing — arguably worse than silence, and
invisible to any metric that only counts unlabelled nodes.

`new-code` and `continue` survive to L4 because their names come from visible
child text, not from any attribute. They are the controls that need no help,
and they belong in the corpus as negative controls: a hint system that fires on
them is producing false positives.

These predictions come from a simplified HTML-AAM name computation in
`build.py`. **Verify a sample against `chrome://accessibility` on the actual
test device before treating them as ground truth** — they are a hypothesis about
what Chrome exposes, not a measurement of it.

## Scoring

`ground-truth/apple-signup.json` carries, per field: `true_label`,
`acceptable_labels` (variants that should count as correct under lenient
matching), `role`, `section` and document `order`.

Each control keeps a `data-field` attribute in the shipped HTML. It is not
exposed through the accessibility tree, so it cannot leak into a prompt, but it
lets an analysis script join a captured hint back to its ground-truth row.
`data-gt-*` attributes exist only in `baseline/` and are stripped from all
generated output.

## Hosting

**GitHub Pages.** Push, then Settings → Pages → deploy from `main`, folder
`/site` (or move `site/` to `/docs`). The site is fully static; HTTPS is
provided, which Chrome for Android prefers.

**Local, for study sessions.** Do not depend on the venue's wifi:

```bash
cd site && python3 -m http.server 8000
adb reverse tcp:8000 tcp:8000
```

The phone then reaches `http://localhost:8000` over USB. Identical content, no
network dependency mid-session.

Each page shows a small level badge in the top-left corner for the researcher's
benefit. It is `aria-hidden` and does not enter the accessibility tree.

## Before running the study

Two things to confirm on the actual device, in this order.

**Confirm the overlay sees web content at all.** Content in Chrome is exposed
as *virtual* `AccessibilityNodeInfo` nodes synthesised by the renderer's
accessibility bridge, not as native `View` objects. Node identity, bounds
reporting and window traversal do not behave identically to the native case.
Load L3, focus one field, and check that the overlay both receives the node and
places its hint over the correct screen rectangle. If it does not, the corpus
size is irrelevant until that is resolved — and a native APK carrying the same
field inventory may be the better artefact, since it matches the deployment
target.

**Confirm L0 is genuinely clean.** Run axe DevTools or Lighthouse against L0 and
confirm zero violations, and walk it once with TalkBack. L0 is the control
condition; if it has defects, every comparison inherits them.

## Naming

The page is deliberately unbranded — "Account", not any company's product name.
The field inventory and visual conventions are what the study needs; a branded
clone on a public repository would be a trademark problem for no research
benefit. If you want branded strings for the sessions themselves, change them
in your local checkout rather than in what you publish.

## Extending

Add a page by writing a second baseline with the same `data-field` /
`data-gt-*` conventions and pointing `build.py` at it. GOV.UK Design System
patterns and the W3C/WAI form tutorials are the usual reference points for a
second and third exemplar — recreated the same way, not copied.
