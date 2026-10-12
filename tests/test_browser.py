"""Real Chromium checks: condition isolation, AX names, validation, completion, export.
Run with a Python environment containing beautifulsoup4 and playwright (Chromium installed).
"""
import functools
import http.server
import json
import threading
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {'first-name','last-name','email','password','confirm-password','phone-number'}

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

class StudyBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'site')))
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.tasks = json.loads((ROOT/'tasks.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.server.shutdown(); cls.server.server_close()

    def page(self, version='correct', task='A'):
        page = self.browser.new_page(viewport={'width':412,'height':900})
        page.goto(f'{self.url}/{version}/?trial=TEST_01&task={task}&reader=hintback')
        page.locator('#start').click()
        return page

    def fill(self,page, task):
        for field, value in self.tasks[task].items():
            node=page.locator(f'[data-field="{field}"]')
            if node.evaluate('(e) => e.tagName')=='SELECT': node.select_option(label=value)
            else: node.fill(value)

    def export(self,page):
        page.locator('summary').click()
        with page.expect_download() as download:
            page.locator('#download').click()
        return json.loads(Path(download.value.path()).read_text())

    def test_only_target_associations_differ(self):
        normalized=[]
        for version in ('correct','degraded'):
            soup=BeautifulSoup((ROOT/'site'/version/'index.html').read_text(),'html.parser')
            del soup.body['data-condition']
            self.assertFalse(soup.select('[placeholder], .ghost, .sr-only, [contenteditable], [aria-hidden]'))
            for control in soup.select('[data-field]'):
                if control['data-field'] in TARGETS:
                    label=control.find_previous_sibling()
                    self.assertEqual(label.name,'label' if version=='correct' else 'span')
                    label.name='label'; label['for']=control['id']
            normalized.append(str(soup))
        self.assertEqual(*normalized)

    def test_visual_and_accessible_names(self):
        screenshots=[]
        for version in ('correct','degraded'):
            page=self.page(version)
            try:
                screenshots.append(page.screenshot(full_page=True))
                ax=page.accessibility.snapshot(interesting_only=False)
                def nodes(node):
                    yield node
                    for child in node.get('children',[]): yield from nodes(child)
                textboxes=[n for n in nodes(ax) if n.get('role')=='textbox']
                self.assertEqual(len(textboxes),6)
                if version=='correct': self.assertEqual([n['name'] for n in textboxes],['First name','Last name','Email address','Password','Confirm password','Phone number'])
                else: self.assertTrue(all(not n.get('name') for n in textboxes),textboxes)
            finally: page.close()
        self.assertEqual(*screenshots)

    def test_submission_and_export(self):
        for version in ('correct','degraded'):
            for task in ('A','B'):
                with self.subTest(version=version,task=task):
                    page=self.page(version,task)
                    try:
                        page.locator('button[type=submit]').click()
                        self.assertEqual(page.locator('#error-list li').count(),10)
                        self.assertEqual(page.evaluate('document.activeElement.id'),'errors')
                        self.fill(page,task)
                        # A valid-looking value in the wrong field must not count as success.
                        page.locator('#f01').fill(self.tasks[task]['last-name'])
                        page.locator('button[type=submit]').click()
                        self.assertEqual(page.locator('#error-list li').count(),1)
                        page.locator('#f01').fill(self.tasks[task]['first-name'])
                        page.locator('button[type=submit]').click()
                        self.assertEqual(page.locator('#result-title').inner_text(),'Task completed')
                        data=self.export(page)
                        self.assertEqual(data['summary']['submit_attempts'],3)
                        self.assertTrue(all(data['summary']['field_results'].values()))
                        self.assertGreater(data['summary']['duration_ms'],0)
                        text=json.dumps(data)
                        for value in ('Mira','Ravi','River42!','Cloud73!','mira@example.com','ravi@example.com'):
                            self.assertNotIn(value,text)
                        self.assertEqual(page.locator('#f01').input_value(),'')
                    finally: page.close()

    def test_stop_and_missing_setup(self):
        page=self.page('degraded')
        try:
            page.locator('#stop').click()
            data=self.export(page)
            self.assertEqual(data['summary']['outcome'],'stopped')
            self.assertEqual(data['summary']['submit_attempts'],0)
        finally: page.close()
        page=self.browser.new_page()
        try:
            page.goto(f'{self.url}/correct/')
            self.assertTrue(page.locator('#start').is_disabled())
        finally: page.close()

if __name__=='__main__': unittest.main()
