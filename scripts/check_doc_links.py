"""Validate local links in repository Markdown and HTML without fetching URLs."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import posixpath
import subprocess
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = {'.md', '.html', '.htm'}
LOCAL_ARTIFACTS = {'runtime', 'data'}
# Vite serves this entry with frontend/ as its web root.
WEB_ROOTS = {'frontend/index.html': 'frontend'}
MARKDOWN = MarkdownIt('commonmark').enable(['table', 'strikethrough'])


@dataclass
class Document:
    anchors: set[str] = field(default_factory=set)
    links: list[tuple[int, str]] = field(default_factory=list)


class HtmlLinks(HTMLParser):
    def __init__(self, document, line=1):
        super().__init__()
        self.document = document
        self.line = line

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if not value:
                continue
            if name == 'id' or (tag == 'a' and name == 'name'):
                self.document.anchors.add(value)
            elif name in ('href', 'src'):
                self.document.links.append((self.line + self.getpos()[0] - 1, value))


def heading_text(tokens):
    parts = []
    for token in tokens:
        if token.children:
            parts.append(heading_text(token.children))
        elif token.type in ('text', 'code_inline'):
            parts.append(token.content)
        elif token.type in ('softbreak', 'hardbreak'):
            parts.append(' ')
    return ''.join(parts)


def markdown_document(text):
    document = Document()
    headings = set()
    tokens = MARKDOWN.parse(text)
    for index, token in enumerate(tokens):
        line = token.map[0] + 1 if token.map else 1
        if token.type == 'heading_open':
            title = heading_text(tokens[index + 1].children or []).strip().lower()
            base = ''.join(
                char
                for char in title.replace(' ', '-')
                if char in '-_' or unicodedata.category(char)[0] in 'LMN'
            )
            anchor = base
            suffix = 1
            while anchor in headings:
                anchor = f'{base}-{suffix}'
                suffix += 1
            headings.add(anchor)
        elif token.type == 'html_block':
            html = HtmlLinks(document, line)
            html.feed(token.content)
            html.close()
        elif token.type == 'inline':
            # Keep one parser for the inline HTML fragments in this block.
            html = HtmlLinks(document, line)
            for child in token.children or []:
                if child.type == 'html_inline':
                    html.feed(child.content)
                elif child.type in ('link_open', 'image'):
                    value = child.attrGet('href' if child.type == 'link_open' else 'src')
                    if value:
                        document.links.append((line, value))
            html.close()
    document.anchors.update(headings)
    return document


def read_document(path):
    text = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.md':
        return markdown_document(text)
    document = Document()
    html = HtmlLinks(document)
    html.feed(text)
    html.close()
    return document


def repository_files(root):
    # Git also supplies exact spelling on case-insensitive filesystems.
    listed = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root
    )
    return {name for name in listed.decode('utf-8').split('\0') if name and (root / name).is_file()}


def check(root):
    files = repository_files(root)
    directories = {parent.as_posix() for name in files for parent in Path(name).parents}
    documents = {
        name: read_document(root / name)
        for name in sorted(files)
        if Path(name).suffix.lower() in DOCUMENTS
    }
    count = 0
    problems = []
    for source, document in documents.items():
        for line, link in document.links:
            location = f'{source}:{line}'
            try:
                url = urlsplit(link)
                if url.scheme or url.netloc:
                    continue
                path = unquote(url.path, errors='strict')
                anchor = unquote(url.fragment, errors='strict')
            except ValueError as exc:
                problems.append(f'{location}: invalid URL {link!r}: {exc}')
                continue
            target = source
            if path:
                base = (
                    WEB_ROOTS.get(source, '') if path.startswith('/') else posixpath.dirname(source)
                )
                target = posixpath.normpath(posixpath.join(base, path.lstrip('/')))
            if target.split('/', 1)[0] in LOCAL_ARTIFACTS:
                continue
            count += 1
            if target not in directories and (target not in files or path.endswith('/')):
                problems.append(f'{location}: missing local target {link!r} ({target})')
                continue
            if not anchor:
                continue
            if target in directories:
                target = posixpath.normpath(posixpath.join(target, 'index.html'))
            destination = documents.get(target)
            if destination is not None:
                implicit_top = Path(target).suffix.lower() != '.md' and anchor.lower() == 'top'
                if anchor not in destination.anchors and not implicit_top:
                    problems.append(f'{location}: missing anchor {link!r} ({target})')
            elif target not in files:
                problems.append(f'{location}: no HTML index for fragment {link!r}')
    return len(documents), count, problems


def main(root=ROOT):
    try:
        documents, count, problems = check(root)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Document link check failed: {exc}', file=sys.stderr)
        return 1
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1
    print(f'Checked {count} local links in {documents} Markdown and HTML files.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
