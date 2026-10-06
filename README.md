# txt2epub

Convert a plain TXT file to EPUB, splitting chapters by a regex.

Designed for novel-style text files (the default chapter pattern matches
Chinese `第X章/节/回` headings), but works with any chapter regex.

## Setup

```sh
uv sync          # or: python3 -m venv .venv && pip install ebooklib
```

## Usage

```sh
txt2epub book.txt                              # auto title, auto language
txt2epub book.txt -o out.epub -t "书名" -a "作者"
txt2epub book.txt -p '^Part\s+[IVX]+.*$'       # custom chapter regex
txt2epub book.txt -c cover.jpg -l zh           # embed cover, force language
python main.py book.txt                        # same, without installing
```

## Options

| Flag | Description |
| --- | --- |
| `-o, --output` | Output `.epub` path (default: input name with `.epub` suffix) |
| `-t, --title` | Book title (default: file name) |
| `-a, --author` | Author name (default: `Unknown`) |
| `-p, --pattern` | Chapter title regex, matched per line (default: `^第.{1,25}[章节回].*$`) |
| `-l, --lang` | Language code, e.g. `en`, `zh`, `ja` (default: auto-detect) |
| `-c, --cover` | Cover image: jpg / png / gif / webp / svg |

## Notes

- Input encoding is auto-detected among UTF-8 (with/without BOM), GB18030, Big5, Latin-1.
- Language auto-detection is a simple CJK/Latin character-count heuristic; pass `-l` to override.
- The cover is embedded as both EPUB2 `<meta name="cover">` and EPUB3 `properties="cover-image"`, with a generated cover page at the front of the spine.
