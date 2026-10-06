#!/usr/bin/env python3
r"""
txt2epub - Convert a plain TXT file to EPUB, splitting chapters by a regex.

Usage:
    txt2epub book.txt
    txt2epub book.txt -o out.epub -t "My Book" -a "Author Name"
    txt2epub book.txt -p '^Part\s+[IVX]+.*$'
    txt2epub book.txt --cover cover.jpg -l zh
    txt2epub book.txt --indent 2 --keep-blank-lines

The regex is matched against each line (after stripping whitespace).
Any line that matches becomes a chapter title and starts a new chapter.
Blank lines between paragraphs are dropped by default; with
--keep-blank-lines each run of them is rendered as a scene-break separator.
"""

import argparse
import html
import re
import sys
import uuid
from pathlib import Path

from ebooklib import epub

# Matches Chinese chapter headings: "第一章", "第12章 标题", "第一百二十回"
# (any 1-25 chars between 第 and 章/节/回, e.g. the numeral and title)
DEFAULT_PATTERN = r"^第.{1,25}[章节回].*$"

COVER_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}


def build_css(indent: float) -> str:
    """Build the stylesheet; indent is the paragraph first-line indent in em."""
    return f"""
body {{ font-family: serif; line-height: 1.6; margin: 5%; }}
h1 {{ text-align: center; margin: 2em 0 1em; }}
p {{ text-indent: {indent:g}em; margin: 0 0 0.6em; }}
p.scene-break {{ text-indent: 0; text-align: center; margin: 1em 0; }}
"""


def read_text(path: Path, encoding: str | None = None) -> str:
    """Read the file; forced encoding or a decode-attempt chain for legacy files."""
    if encoding:
        try:
            return path.read_text(encoding=encoding)
        except LookupError as e:
            raise ValueError(f"unknown encoding {encoding!r}") from e
        except UnicodeDecodeError as e:
            raise ValueError(f"file does not decode as {encoding!r}: {e}") from e
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode file")


def split_chapters(text: str, pattern: str, keep_blank_lines: bool = False):
    """Return a list of (title, [paragraph, ...]) tuples.

    Paragraphs are strings. When keep_blank_lines is True, each run of blank
    lines between paragraphs becomes a single None entry marking a scene
    break; runs at chapter boundaries are discarded.
    """
    regex = re.compile(pattern)
    chapters = []
    title, paras = "Front Matter", []

    def has_content(items):
        return any(p is not None for p in items)

    def trim_trailing_breaks(items):
        while items and items[-1] is None:
            items.pop()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            # Collapse a run of blank lines into one scene break between paragraphs
            if keep_blank_lines and paras and paras[-1] is not None:
                paras.append(None)
            continue
        if regex.match(line):
            # Save the previous chapter (skip empty front matter)
            trim_trailing_breaks(paras)
            if has_content(paras) or chapters:
                chapters.append((title, paras))
            title, paras = line, []
        else:
            paras.append(line)

    trim_trailing_breaks(paras)
    chapters.append((title, paras))
    return chapters


def detect_language(text: str) -> str:
    """Guess a language code from character counts; only meant as a default."""
    sample = text[:100_000]  # a prefix is plenty for detection
    cjk = len(re.findall(r"[\u4e00-\u9fff]", sample))  # Han ideographs
    kana = len(re.findall(r"[\u3040-\u30ff]", sample))  # Hiragana + Katakana
    hangul = len(re.findall(r"[\uac00-\ud7af]", sample))
    latin = len(re.findall(r"[A-Za-z]", sample))

    if cjk + kana + hangul > latin:
        if hangul > cjk + kana:
            return "ko"
        if kana * 5 > cjk:
            return "ja"
        return "zh"
    return "en"


def load_cover(path: Path):
    """Return (file_name, bytes) for the cover image."""
    suffix = path.suffix.lower()
    if suffix not in COVER_SUFFIXES:
        supported = ", ".join(sorted(COVER_SUFFIXES))
        raise ValueError(f"unsupported cover image {suffix!r} (supported: {supported})")
    return f"cover{suffix}", path.read_bytes()


def build_identifier(book_title: str, author: str) -> str:
    """Deterministic identifier: same title and author always map to the same UUID.

    Readers key reading progress and annotations to this value, so a
    re-conversion of the same book must not change it.
    """
    name = f"txt2epub:{book_title}|{author}"
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, name)}"


SCENE_BREAK = '<p class="scene-break">* * *</p>'


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    """Show defaults, but skip None (the help text explains the derived value)."""

    def _get_help_string(self, action):
        if action.default is None:
            return action.help
        return super()._get_help_string(action)


def build_epub(
    chapters, out_path, book_title, author, lang, cover=None, indent=0, identifier=None
):
    book = epub.EpubBook()
    book.set_identifier(identifier or build_identifier(book_title, author))
    book.set_title(book_title)
    book.set_language(lang)
    book.add_author(author)

    css = epub.EpubItem(
        uid="style",
        file_name="style/main.css",
        media_type="text/css",
        content=build_css(indent),
    )
    book.add_item(css)

    # Cover image + cover page + <meta name="cover"> for reader pickers.
    # set_cover() guesses the media type from the file name extension.
    cover_page = None
    if cover is not None:
        cover_name, cover_bytes = cover
        book.set_cover(cover_name, cover_bytes)
        cover_page = next(
            item for item in book.get_items() if isinstance(item, epub.EpubCoverHtml)
        )

    items = []
    for i, (title, paras) in enumerate(chapters, start=1):
        parts = [
            SCENE_BREAK if p is None else f"<p>{html.escape(p)}</p>" for p in paras
        ]
        body = "\n".join(parts)
        item = epub.EpubHtml(
            title=title,
            file_name=f"chap_{i:04d}.xhtml",
            lang=lang,
        )
        item.content = f"<h1>{html.escape(title)}</h1>\n{body}"
        item.add_item(css)
        book.add_item(item)
        items.append(item)

    book.toc = tuple(items)  # table of contents built from regex titles
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ([cover_page] if cover_page else []) + ["nav"] + items

    epub.write_epub(str(out_path), book)


def main():
    ap = argparse.ArgumentParser(
        prog="txt2epub",
        description="Convert TXT to EPUB using a chapter regex.",
        formatter_class=_HelpFormatter,
    )
    ap.add_argument("input", type=Path, help="input .txt file")
    ap.add_argument(
        "-o", "--output", type=Path, help="output .epub (default: same name)"
    )
    ap.add_argument(
        "-p", "--pattern", default=DEFAULT_PATTERN, help="chapter title regex"
    )
    ap.add_argument("-t", "--title", help="book title (default: file name)")
    ap.add_argument("-a", "--author", default="Unknown", help="author name")
    ap.add_argument(
        "-l", "--lang", help="language code, e.g. en, zh, ja (default: auto-detect)"
    )
    ap.add_argument(
        "-c", "--cover", type=Path, help="cover image (jpg/png/gif/webp/svg)"
    )
    ap.add_argument(
        "--identifier",
        help="book identifier, e.g. urn:uuid:... or urn:isbn:... "
        "(default: deterministic UUID derived from title and author)",
    )
    ap.add_argument(
        "--encoding",
        help="force input encoding, e.g. utf-8, gb18030, big5 (default: auto-detect)",
    )
    ap.add_argument(
        "--keep-blank-lines",
        action="store_true",
        help="keep blank lines between paragraphs as scene-break separators "
        "(blank lines are dropped without this flag)",
    )
    ap.add_argument(
        "--indent",
        type=float,
        default=0,
        metavar="EM",
        help="paragraph first-line indent in em (2 for classic CJK style)",
    )
    if len(sys.argv) == 1:
        ap.print_help()
        return 1
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"File not found: {args.input}")
    if args.cover and not args.cover.is_file():
        sys.exit(f"Cover not found: {args.cover}")
    if args.indent < 0:
        sys.exit("--indent must be >= 0")

    out = args.output or args.input.with_suffix(".epub")
    title = args.title or args.input.stem

    try:
        text = read_text(args.input, args.encoding)
    except ValueError as e:
        sys.exit(f"Error: {e}")
    lang = args.lang or detect_language(text)

    cover = None
    if args.cover:
        try:
            cover = load_cover(args.cover)
        except ValueError as e:
            sys.exit(f"Error: {e}")

    chapters = split_chapters(
        text, args.pattern, keep_blank_lines=args.keep_blank_lines
    )
    build_epub(
        chapters,
        out,
        title,
        args.author,
        lang,
        cover,
        indent=args.indent,
        identifier=args.identifier,
    )

    extras = [f"language: {lang}"]
    if cover:
        extras.append(f"cover: {args.cover.name}")
    if args.keep_blank_lines:
        extras.append("blank lines kept as separators")
    print(f"Wrote {out} ({', '.join(extras)}) with {len(chapters)} sections:")
    for t, p in chapters[:10]:
        count = sum(1 for x in p if x is not None)
        print(f"  - {t}  ({count} paragraphs)")
    if len(chapters) > 10:
        print(f"  ... and {len(chapters) - 10} more")


if __name__ == "__main__":
    sys.exit(main())
