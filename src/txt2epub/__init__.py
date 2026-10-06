#!/usr/bin/env python3
r"""
txt2epub - Convert a plain TXT file to EPUB, splitting chapters by a regex.

Usage:
    txt2epub book.txt
    txt2epub book.txt -o out.epub -t "My Book" -a "Author Name"
    txt2epub book.txt -p '^Part\s+[IVX]+.*$'
    txt2epub book.txt --cover cover.jpg -l zh

The regex is matched against each line (after stripping whitespace).
Any line that matches becomes a chapter title and starts a new chapter.
"""
import argparse
import html
import re
import sys
from pathlib import Path

from ebooklib import epub

# Matches: "Chapter 1", "Chapter 12: Title", "CHAPTER ONE", "Chapter IV - Title"
DEFAULT_PATTERN = r"^第.{1,25}[章节回].*$"

COVER_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}

CSS = """
body { font-family: serif; line-height: 1.6; margin: 5%; }
h1 { text-align: center; margin: 2em 0 1em; }
p { text-indent: 2em; margin: 0 0 0.6em; }
"""


def read_text(path: Path) -> str:
    """Try common encodings so non-UTF-8 files still load."""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode file")


def split_chapters(text: str, pattern: str):
    """Return a list of (title, [paragraph, ...]) tuples."""
    regex = re.compile(pattern)
    chapters = []
    title, paras = "Front Matter", []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if regex.match(line):
            # Save the previous chapter (skip empty front matter)
            if paras or chapters:
                chapters.append((title, paras))
            title, paras = line, []
        else:
            paras.append(line)

    chapters.append((title, paras))
    return chapters


def detect_language(text: str) -> str:
    """Guess a language code from character counts; only meant as a default."""
    sample = text[:100_000]  # a prefix is plenty for detection
    cjk = len(re.findall(r"[\u4e00-\u9fff]", sample))     # Han ideographs
    kana = len(re.findall(r"[\u3040-\u30ff]", sample))    # Hiragana + Katakana
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


def build_epub(chapters, out_path, book_title, author, lang, cover=None):
    book = epub.EpubBook()
    book.set_identifier(f"txt2epub-{abs(hash(book_title))}")
    book.set_title(book_title)
    book.set_language(lang)
    book.add_author(author)

    css = epub.EpubItem(
        uid="style",
        file_name="style/main.css",
        media_type="text/css",
        content=CSS,
    )
    book.add_item(css)

    # Cover image + cover page + <meta name="cover"> for reader pickers.
    # set_cover() guesses the media type from the file name extension.
    cover_page = None
    if cover is not None:
        cover_name, cover_bytes = cover
        book.set_cover(cover_name, cover_bytes)
        cover_page = next(
            item for item in book.get_items()
            if isinstance(item, epub.EpubCoverHtml)
        )

    items = []
    for i, (title, paras) in enumerate(chapters, start=1):
        body = "\n".join(f"<p>{html.escape(p)}</p>" for p in paras)
        item = epub.EpubHtml(
            title=title,
            file_name=f"chap_{i:04d}.xhtml",
            lang=lang,
        )
        item.content = f"<h1>{html.escape(title)}</h1>\n{body}"
        item.add_item(css)
        book.add_item(item)
        items.append(item)

    book.toc = tuple(items)          # table of contents built from regex titles
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ([cover_page] if cover_page else []) + ["nav"] + items

    epub.write_epub(str(out_path), book)


def main():
    ap = argparse.ArgumentParser(description="Convert TXT to EPUB using a chapter regex.")
    ap.add_argument("input", type=Path, help="input .txt file")
    ap.add_argument("-o", "--output", type=Path, help="output .epub (default: same name)")
    ap.add_argument("-p", "--pattern", default=DEFAULT_PATTERN, help="chapter title regex")
    ap.add_argument("-t", "--title", help="book title (default: file name)")
    ap.add_argument("-a", "--author", default="Unknown", help="author name")
    ap.add_argument("-l", "--lang", help="language code, e.g. en, zh, ja (default: auto-detect)")
    ap.add_argument("-c", "--cover", type=Path, help="cover image (jpg/png/gif/webp/svg)")
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"File not found: {args.input}")
    if args.cover and not args.cover.is_file():
        sys.exit(f"Cover not found: {args.cover}")

    out = args.output or args.input.with_suffix(".epub")
    title = args.title or args.input.stem

    text = read_text(args.input)
    lang = args.lang or detect_language(text)

    cover = None
    if args.cover:
        try:
            cover = load_cover(args.cover)
        except ValueError as e:
            sys.exit(f"Error: {e}")

    chapters = split_chapters(text, args.pattern)
    build_epub(chapters, out, title, args.author, lang, cover)

    suffix = f", language: {lang}, cover: {args.cover.name}" if cover else f", language: {lang}"
    print(f"Wrote {out}{suffix} with {len(chapters)} sections:")
    for t, p in chapters[:10]:
        print(f"  - {t}  ({len(p)} paragraphs)")
    if len(chapters) > 10:
        print(f"  ... and {len(chapters) - 10} more")


if __name__ == "__main__":
    main()
