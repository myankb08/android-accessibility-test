#!/usr/bin/env python3
"""
build.py — generates the degraded testbed from a single hand-authored L0 baseline.

Every artefact under site/ and ground-truth/ is GENERATED. Never edit those by
hand: edit apple-signup.html (the flat L0 baseline) and re-run this script.

    python3 build.py

Degradation ladder (L0-L4 are cumulative; L5 is an independent condition):

  L0  Baseline. Every control has a correct programmatic name.
  L1  Label associations broken. <label for> -> <span>, `for` dropped.
      ARIA names, placeholders and visible text remain.
  L2  All assistive-technology-only strings removed: visually-hidden labels
      deleted; aria-label / aria-labelledby / aria-describedby / title / alt
      dropped; <fieldset>/<legend> downgraded to <div>. Visible text remains.
  L3  Placeholder and autocomplete removed; id/name replaced with opaque
      tokens so no semantics leak through the resource-id channel.
  L4  Native controls replaced by generic containers: <input> becomes
      <div contenteditable>, <select> and checkboxes become <div tabindex="0">,
      <button> becomes <div tabindex="0">. Role information is gone.
  L5  Misleading names. L0 structure, but the programmatic name and placeholder
      of each field are swapped with those of another field.

Only invisible names are swapped at L5, so all six levels render identically.
That is deliberate: the visual layer is held constant, and the accessibility
tree is the sole independent variable.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).parent
BASELINE = ROOT / "apple-signup.html"   # hand-edited L0 source (kept flat, alongside style.css)
SITE = ROOT / "site"
GT = ROOT / "ground-truth"

PAGE = "apple-signup"
LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5"]

LEVEL_DESC = {
    "L0": "Baseline — every control correctly named",
    "L1": "Label associations broken (for/id unbound)",
    "L2": "All AT-only strings removed (sr-only labels, ARIA, alt, title)",
    "L3": "Placeholder, autocomplete and semantic id/name removed",
    "L4": "Native controls replaced by generic divs",
    "L5": "Misleading names (labels and placeholders swapped between fields)",
}

# L5 permutation — pairs of fields whose accessible names are exchanged.
# Restricted to fields whose name is invisible, so the rendering is unchanged.
L5_SWAPS = [
    ("first-name", "email"),
    ("last-name", "phone-number"),
    ("password", "captcha-input"),
    ("confirm-password", "birth-year"),
    ("birth-month", "birth-day"),
    ("birthday-help", "phone-help"),
    ("captcha-image", "audio-code"),
]

TEXT_INPUT_TYPES = {"text", "email", "password", "tel", "search", "url", "number"}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def load_baseline() -> BeautifulSoup:
    return BeautifulSoup(BASELINE.read_text(encoding="utf-8"), "html.parser")


def fields_in_order(soup: BeautifulSoup):
    """Every element carrying data-field, in document order."""
    return soup.select("[data-field]")


def is_sr_only(tag) -> bool:
    return "sr-only" in (tag.get("class") or [])


def rename_tag(tag, name: str):
    tag.name = name
    return tag


def strip_build_attrs(soup: BeautifulSoup):
    """Remove data-gt-* and data-labels from shipped HTML. data-field is kept:
    it is invisible to the accessibility tree and lets the analysis scripts
    join a captured hint back to its ground-truth row."""
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.startswith("data-gt-") or attr == "data-labels":
                del tag[attr]


def fix_asset_paths(soup: BeautifulSoup, level: str):
    # site/ is self-contained: style.css and assets/ are copied into it, so each variant at
    # site/<level>/index.html reaches them one directory up ("../").
    for link in soup.find_all("link", href=True):
        href = link["href"]
        if not href.startswith(("http", "/", "../", "data:")):
            link["href"] = "../" + href
    for img in soup.find_all("img", src=True):
        if img["src"].startswith("assets/"):
            img["src"] = "../" + img["src"]
    badge = soup.select_one("[data-level-badge]")
    if badge:
        badge.string = level
    title = soup.find("title")
    if title:
        title.string = f"Create Your Account — {level}"


# --------------------------------------------------------------------------
# degradation steps
# --------------------------------------------------------------------------

def step_break_labels(soup: BeautifulSoup):
    """L1: <label for=x> becomes <span>, association destroyed, text retained."""
    for label in soup.find_all("label"):
        label.attrs.pop("for", None)
        rename_tag(label, "span")
    for tag in soup.find_all(attrs={"aria-labelledby": True}):
        del tag["aria-labelledby"]


def step_remove_at_only_strings(soup: BeautifulSoup):
    """L2: delete every string that exists only for assistive technology."""
    for tag in soup.find_all(class_="sr-only"):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in ("aria-label", "aria-labelledby", "aria-describedby", "title"):
            tag.attrs.pop(attr, None)
    for img in soup.find_all("img"):
        img.attrs.pop("alt", None)
    for legend in soup.find_all("legend"):
        rename_tag(legend, "div")
    for fs in soup.find_all("fieldset"):
        rename_tag(fs, "div")


def step_remove_hint_attrs(soup: BeautifulSoup):
    """L3: kill placeholder, autocomplete and semantic identifiers.

    The placeholder is not simply deleted — its text is repainted as an
    aria-hidden <span> pinned over the control. The field still *looks*
    labelled to a sighted observer while exposing nothing to the
    accessibility tree. This mirrors the very common real-world failure of
    labels drawn as images, canvas or aria-hidden decoration, and it keeps
    the rendering identical to L0."""
    for tag in soup.find_all(attrs={"placeholder": True}):
        text = tag["placeholder"]
        del tag["placeholder"]
        wrapper = tag.find_parent(class_="field")
        if wrapper is None or not text.strip():
            continue
        ghost = soup.new_tag("span")
        ghost["class"] = ["ghost"]
        ghost["aria-hidden"] = "true"
        ghost.string = text
        tag.insert_before(ghost)

    for tag in soup.find_all(True):
        tag.attrs.pop("autocomplete", None)

    counter = 0
    for tag in soup.find_all(True):
        if tag.has_attr("id"):
            counter += 1
            tag["id"] = f"e{counter:02d}"
        if tag.has_attr("name"):
            tag["name"] = f"e{counter:02d}" if counter else "e00"


def step_genericise_controls(soup: BeautifulSoup):
    """L4: replace native controls with generic containers."""
    for inp in list(soup.find_all("input")):
        itype = (inp.get("type") or "text").lower()
        div = soup.new_tag("div")
        for attr in ("class", "id", "name", "data-field"):
            if inp.has_attr(attr):
                div[attr] = inp[attr]
        if itype == "checkbox":
            div["tabindex"] = "0"
        else:
            div["contenteditable"] = "true"
        inp.replace_with(div)

    for sel in list(soup.find_all("select")):
        chosen = sel.find("option", selected=True) or sel.find("option")
        text = chosen.get_text(strip=True) if chosen else ""
        div = soup.new_tag("div")
        for attr in ("class", "id", "name", "data-field"):
            if sel.has_attr(attr):
                div[attr] = sel[attr]
        div["tabindex"] = "0"
        div.string = text
        sel.replace_with(div)

    for btn in list(soup.find_all("button")):
        btn.attrs.pop("type", None)
        btn["tabindex"] = "0"
        rename_tag(btn, "div")


def step_mislead(soup: BeautifulSoup):
    """L5: exchange the accessible name and placeholder of paired fields."""
    index = {t["data-field"]: t for t in fields_in_order(soup)}

    def read(tag):
        name = tag.get("aria-label") or tag.get("alt")
        label = None
        if tag.has_attr("id"):
            label = soup.find("label", attrs={"for": tag["id"]})
        return {
            "aria_label": tag.get("aria-label"),
            "alt": tag.get("alt"),
            "placeholder": tag.get("placeholder"),
            "label_text": label.get_text(strip=True) if label else None,
            "label_tag": label,
            "name": name,
        }

    for a_id, b_id in L5_SWAPS:
        if a_id not in index or b_id not in index:
            continue
        a, b = index[a_id], index[b_id]
        ra, rb = read(a), read(b)

        # Only the programmatic name moves. The visible placeholder stays
        # correct, so a sighted user sees the right field while a screen
        # reader is told the wrong one — and label and placeholder now
        # actively contradict each other.
        for tag, src in ((a, rb), (b, ra)):
            if tag.has_attr("aria-label"):
                new = src["aria_label"] or src["label_text"] or src["alt"]
                if new:
                    tag["aria-label"] = new
            if tag.has_attr("alt"):
                new = src["alt"] or src["aria_label"] or src["label_text"]
                if new:
                    tag["alt"] = new

        if ra["label_tag"] is not None and rb["label_tag"] is not None:
            ra["label_tag"].string = rb["label_text"]
            rb["label_tag"].string = ra["label_text"]


PIPELINE = {
    "L0": [],
    "L1": [step_break_labels],
    "L2": [step_break_labels, step_remove_at_only_strings],
    "L3": [step_break_labels, step_remove_at_only_strings, step_remove_hint_attrs],
    "L4": [step_break_labels, step_remove_at_only_strings, step_remove_hint_attrs,
           step_genericise_controls],
    "L5": [step_mislead],
}


# --------------------------------------------------------------------------
# simplified accessible-name computation (HTML-AAM subset)
# --------------------------------------------------------------------------

def visible_text(tag) -> str:
    """Text contributing to the accessible name. aria-hidden subtrees are
    excluded; CSS-clipped (.sr-only) text is NOT — it is still exposed."""
    parts = []
    for node in tag.descendants:
        if isinstance(node, NavigableString):
            parent = node.parent
            hidden = False
            while parent is not None and getattr(parent, "attrs", None) is not None:
                if parent.get("aria-hidden") == "true":
                    hidden = True
                    break
                parent = parent.parent
            if not hidden:
                parts.append(str(node))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def accessible_name(soup, tag) -> str:
    """Approximates the name Chrome exposes through the AccessibilityNodeInfo
    bridge. Verify a sample against chrome://accessibility before relying on it."""
    if tag.get("aria-labelledby"):
        refs = [soup.find(id=i) for i in tag["aria-labelledby"].split()]
        text = " ".join(visible_text(r) for r in refs if r is not None).strip()
        if text:
            return text
    if tag.get("aria-label", "").strip():
        return tag["aria-label"].strip()

    name = tag.name.lower()

    if name == "img":
        return tag.get("alt", "").strip() if tag.has_attr("alt") else ""

    if name in ("input", "select", "textarea"):
        if tag.has_attr("id"):
            lab = soup.find("label", attrs={"for": tag["id"]})
            if lab is not None:
                text = visible_text(lab)
                if text:
                    return text
        lab = tag.find_parent("label")
        if lab is not None:
            text = visible_text(lab)
            if text:
                return text
        if tag.get("placeholder", "").strip():
            return tag["placeholder"].strip()
        if tag.get("title", "").strip():
            return tag["title"].strip()
        if name == "input" and (tag.get("type") or "").lower() in ("submit", "button"):
            return tag.get("value", "").strip()
        return ""

    if name == "button":
        return visible_text(tag) or tag.get("title", "").strip()

    if tag.get("contenteditable") == "true":
        return ""

    return visible_text(tag)


def exposed_role(tag) -> str:
    if tag.get("role"):
        return tag["role"]
    name = tag.name.lower()
    if name == "input":
        t = (tag.get("type") or "text").lower()
        return {"checkbox": "checkbox", "radio": "radio", "submit": "button",
                "button": "button"}.get(t, "textbox" if t in TEXT_INPUT_TYPES else t)
    if name == "select":
        return "combobox"
    if name == "button":
        return "button"
    if name == "img":
        return "image"
    if tag.get("contenteditable") == "true":
        return "generic editable"
    if tag.has_attr("tabindex"):
        return "generic focusable"
    return "generic"


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def build_level(level: str) -> tuple[BeautifulSoup, BeautifulSoup]:
    soup = load_baseline()
    for step in PIPELINE[level]:
        step(soup)
    analysis = copy.copy(BeautifulSoup(str(soup), "html.parser"))
    fix_asset_paths(soup, level)
    strip_build_attrs(soup)
    return soup, analysis


def main():
    baseline = load_baseline()

    # ---- ground truth, read off L0 -------------------------------------
    truth = []
    for order, tag in enumerate(fields_in_order(baseline), start=1):
        truth.append({
            "field": tag["data-field"],
            "order": order,
            "true_label": tag["data-gt-label"],
            "acceptable_labels": [tag["data-gt-label"]]
                                 + [a for a in tag.get("data-gt-alt", "").split("|") if a],
            "role": tag["data-gt-role"],
            "section": tag["data-gt-section"],
            "element": tag.name,
            "input_type": tag.get("type"),
        })

    by_field = {row["field"]: row for row in truth}

    # ---- copy shared assets so site/ is portable & self-contained -------
    SITE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "style.css", SITE / "style.css")
    site_assets = SITE / "assets"
    site_assets.mkdir(exist_ok=True)
    for asset in (ROOT / "assets").glob("*"):
        if asset.is_file():
            shutil.copy2(asset, site_assets / asset.name)

    # ---- emit each level ------------------------------------------------
    matrix = {}
    for level in LEVELS:
        soup, analysis = build_level(level)
        outdir = SITE / level
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "index.html").write_text(soup.prettify(), encoding="utf-8")

        rows = []
        for tag in fields_in_order(analysis):
            fid = tag["data-field"]
            name = accessible_name(analysis, tag)
            gt = by_field[fid]
            correct = name.strip().lower() in {
                a.strip().lower() for a in gt["acceptable_labels"]}
            rows.append({
                "field": fid,
                "order": gt["order"],
                "true_label": gt["true_label"],
                "exposed_name": name,
                "exposed_role": exposed_role(tag),
                "status": "named" if correct else ("misnamed" if name else "unnamed"),
            })
        matrix[level] = rows
        (outdir / "expected.json").write_text(
            json.dumps({"page": PAGE, "level": level,
                        "description": LEVEL_DESC[level], "fields": rows},
                       indent=2), encoding="utf-8")

    GT.mkdir(parents=True, exist_ok=True)
    (GT / f"{PAGE}.json").write_text(
        json.dumps({"page": PAGE, "source": "hand-authored, not derived from any "
                    "third-party page source", "fields": truth}, indent=2),
        encoding="utf-8")

    # ---- CSV summary for the paper --------------------------------------
    lines = ["field,order,true_label," + ",".join(LEVELS)]
    for row in truth:
        cells = [matrix[lv][row["order"] - 1]["status"] for lv in LEVELS]
        label = row["true_label"].replace(",", ";")
        lines.append(f'{row["field"]},{row["order"]},"{label}",' + ",".join(cells))
    (GT / f"{PAGE}-expected-matrix.csv").write_text("\n".join(lines) + "\n",
                                                    encoding="utf-8")

    write_index(matrix)

    print(f"{len(truth)} fields x {len(LEVELS)} levels\n")
    header = f'{"level":5} {"named":>6} {"unnamed":>8} {"misnamed":>9}'
    print(header)
    print("-" * len(header))
    for lv in LEVELS:
        rows = matrix[lv]
        c = lambda s: sum(1 for r in rows if r["status"] == s)
        print(f'{lv:5} {c("named"):6} {c("unnamed"):8} {c("misnamed"):9}')


def write_index(matrix):
    cards = []
    for lv in LEVELS:
        rows = matrix[lv]
        broken = sum(1 for r in rows if r["status"] != "named")
        cards.append(
            f'<tr><td><a href="{lv}/">{lv}</a></td>'
            f'<td>{LEVEL_DESC[lv]}</td>'
            f'<td><code>{broken} / {len(rows)}</code></td></tr>')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Accessibility degradation testbed</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<main class="index">
  <h1>Accessibility degradation testbed</h1>
  <p>One hand-authored signup form, rendered identically at six levels of
     accessibility-tree degradation. Visual layout is held constant; only the
     programmatic semantics change.</p>
  <table>
    <caption>Sign-up form</caption>
    <thead><tr><th>Level</th><th>Degradation applied</th>
      <th>Fields without a correct name</th></tr></thead>
    <tbody>
      {"".join(cards)}
    </tbody>
  </table>
</main>
</body>
</html>
"""
    (SITE / "index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
