#!/usr/bin/env python3
"""Build the active correct/degraded corpus. Legacy L0–L5 lives in archive/legacy-levels.
Only editable-field label associations differ. Expected names are design expectations,
not measurements of Chrome or TalkBack. Requires beautifulsoup4.
"""
import csv
import json
import shutil
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
TARGETS = {'first-name', 'last-name', 'email', 'password', 'confirm-password', 'phone-number'}
ACCEPTABLE = {
    'first-name': ['Given name'], 'last-name': ['Surname', 'Family name'],
    'email': ['Email', 'E-mail address'], 'password': ['New password', 'Create password'],
    'confirm-password': ['Re-enter password', 'Repeat password', 'Verify password'],
    'phone-number': ['Phone', 'Mobile number', 'Telephone number'],
    'country-region': ['Country', 'Region', 'Country or region'],
    'birth-month': ['Birthday month', 'Birth month'], 'birth-day': ['Birthday day', 'Birth day'],
    'birth-year': ['Birthday year', 'Birth year'], 'opt-announcements': ['Receive announcements', 'Announcements'],
}

def main():
    site = ROOT / 'site'
    site.mkdir(exist_ok=True)
    for filename in ('style.css', 'study.js', 'researcher.js', 'tasks.json'):
        shutil.copy2(ROOT / filename, site / filename)
    shutil.copy2(ROOT / 'researcher.html', site / 'index.html')
    baseline = (ROOT / 'apple-signup.html').read_text()
    truth = []
    for version in ('correct', 'degraded'):
        soup = BeautifulSoup(baseline, 'html.parser')
        soup.body['data-condition'] = version
        soup.link['href'] = '../style.css'
        soup.script['src'] = '../study.js'
        expected = []
        for order, control in enumerate(soup.select('[data-field]'), 1):
            field = control['data-field']
            label = soup.find('label', attrs={'for': control['id']})
            name = label.get_text(' ', strip=True)
            is_target = field in TARGETS
            if version == 'correct':
                truth.append({'field': field, 'id': control['id'], 'order': order,
                              'true_label': name, 'acceptable_labels': [name] + ACCEPTABLE[field],
                              'target': is_target,
                              'element': control.name, 'input_type': control.get('type')})
            if version == 'degraded' and is_target:
                label.name = 'span'
                del label['for']
            expected.append({'field': field, 'target': is_target,
                             'expected_programmatic_label': None if version == 'degraded' and is_target else name,
                             'note': 'Verify on the study phone; browser inference and OCR may supply text.'})
        out = site / version
        out.mkdir(exist_ok=True)
        (out / 'index.html').write_text(str(soup))
        (out / 'expected.json').write_text(json.dumps(expected, indent=2) + '\n')
    gt = ROOT / 'ground-truth'
    gt.mkdir(exist_ok=True)
    (gt / 'apple-signup.json').write_text(json.dumps({'schema_version': 2, 'fields': truth}, indent=2) + '\n')
    with (gt / 'apple-signup-expected-matrix.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['field', 'true_label', 'target', 'correct', 'degraded'])
        for row in truth:
            writer.writerow([row['field'], row['true_label'], row['target'], 'associated label',
                             'unassociated visible text' if row['target'] else 'associated label'])
    print(f'Built correct/degraded: {len(truth)} controls, {len(TARGETS)} target text fields.')

if __name__ == '__main__':
    main()
