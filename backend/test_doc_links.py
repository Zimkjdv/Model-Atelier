from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from scripts import check_doc_links


class DocumentLinkTests(unittest.TestCase):
    def setUp(self):
        workspace = TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.git('init', '-q')

    def git(self, *args):
        subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def run_checker(self):
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = check_doc_links.main(self.root)
        return code, output.getvalue()

    def test_real_markdown_and_html_links_ignore_examples_and_local_evidence(self):
        self.write('.gitignore', 'runtime/\n')
        self.write('runtime/raw/report.html', '<a href="missing.html">private report</a>')
        self.write('docs/圖 檔.txt', 'local asset')
        self.write(
            'docs/detail.md',
            '# **掃描** `API`\n\n掃描 API\n--------\n\n<a id="stable"></a>\n',
        )
        self.write(
            'docs/guide/index.html',
            '<a id="scan"></a><a href="../detail.md#stable">contract</a>'
            '<a href="#top">top</a><img src="../圖%20檔.txt">'
            '<a name="legacy"></a><a href="#legacy">old</a>',
        )
        self.write('frontend/index.html', '<script type="module" src="/src/main.ts"></script>')
        self.write('frontend/src/main.ts', '')
        self.write(
            'README.md',
            '# Readme\n\n'
            '| Docs | Link |\n| --- | --- |\n| Scan | [Guide][guide] |\n\n'
            '[guide]: docs/guide/#scan\n\n'
            '[Heading](docs/detail.md#掃描-api) [Repeated](docs/detail.md#掃描-api-1)\n'
            '![asset](<docs/圖 檔.txt>)\n\n'
            '<span>See <a href="docs/detail.md?from=index#stable">this</a></span>\n\n'
            '[evidence](runtime/absent.html#missing) [data](data/untracked.png) '
            '[web](https://example.invalid/missing) [cdn](//example.invalid/missing)\n\n'
            '`[example](missing.md)`\n\n'
            '```html\n<a href="missing.md">example</a>\n```\n',
        )
        code, output = self.run_checker()
        self.assertEqual(code, 0, output)
        self.assertIn('in 4 Markdown and HTML files', output)

    def test_broken_paths_and_fragments_fail_with_the_source_location(self):
        self.write('docs/Target.md', '# heading\n')
        missing = self.write('docs/deleted.md', '# Deleted\n')
        self.git('add', 'docs/deleted.md')
        missing.unlink()
        self.write(
            'README.md',
            '# Title\n\n[deleted](docs/deleted.md)\n\n[case](docs/target.md)\n\n'
            '[fragment](docs/Target.md#missing)\n\n[outside](../outside.md)\n\n'
            '[file with slash](docs/Target.md/)\n',
        )
        self.write('docs/guide.html', '<h1 id="top">Guide</h1>\n<a href="#missing">wrong</a>')
        code, output = self.run_checker()
        self.assertEqual(code, 1)
        for location, error in (
            ('README.md:3', 'missing local target'),
            ('README.md:5', 'missing local target'),
            ('README.md:7', 'missing anchor'),
            ('README.md:9', 'missing local target'),
            ('README.md:11', 'missing local target'),
            ('docs/guide.html:2', 'missing anchor'),
        ):
            self.assertIn(f'{location}: {error}', output)
