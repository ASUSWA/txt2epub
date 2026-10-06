# txt2epub

Convert a plain TXT file to EPUB, splitting chapters by a regex.

Designed for novel-style text files (the default chapter pattern matches
Chinese `第X章/节/回` headings), but works with any chapter regex.

## Installation

Requires Python 3.13+. With [uv](https://docs.astral.sh/uv/getting-started/installation/)
and Git installed:

```sh
uv tool install git+https://github.com/ASUSWA/txt2epub.git
txt2epub --help
```

Or install from a local checkout:

```sh
git clone https://github.com/ASUSWA/txt2epub.git
cd txt2epub
uv tool install .
# Alternatively, in an activated virtual environment:
# python -m pip install .
```

```sh
uv tool upgrade txt2epub     # update a GitHub installation
uv tool uninstall txt2epub   # uninstall
```

## Usage

```sh
txt2epub book.txt                               # writes book.epub
txt2epub book.txt -o out.epub -t "Title" -a "Author"
txt2epub book.txt -p '^Part\s+[IVX]+.*$'          # custom chapter regex
txt2epub book.txt -c cover.jpg -l zh              # cover and language
txt2epub book.txt --encoding gb18030             # force input encoding
txt2epub book.txt --indent 2 --keep-blank-lines   # indent and scene breaks
```

Run `txt2epub --help` for all options.

## Options

| Flag | Description |
| --- | --- |
| `-o, --output` | Output `.epub` path (default: input name with `.epub` suffix) |
| `-t, --title` | Book title (default: file name) |
| `-a, --author` | Author name (default: `Unknown`) |
| `-p, --pattern` | Chapter title regex, matched per line (default: `^第.{1,25}[章节回].*$`) |
| `-l, --lang` | Language code, e.g. `en`, `zh`, `ja` (default: auto-detect) |
| `-c, --cover` | Cover image: jpg / png / gif / webp / svg |
| `--keep-blank-lines` | Render runs of blank lines between paragraphs as scene-break separators (`* * *`) instead of dropping them |
| `--indent EM` | Paragraph first-line indent in `em` (default: `0`, no indent; `2` for classic CJK style) |
| `--identifier ID` | Book identifier, e.g. `urn:uuid:...` or `urn:isbn:...` (default: deterministic UUID from title + author) |
| `--encoding ENC` | Force input encoding, e.g. `utf-8`, `gb18030`, `big5` (default: auto-detect) |

## Notes

- Input encoding is auto-detected among UTF-8 (with/without BOM), GB18030, Big5, Latin-1.
- Language auto-detection is a simple CJK/Latin character-count heuristic; pass `-l` to override.
- The cover is embedded as both EPUB2 `<meta name="cover">` and EPUB3 `properties="cover-image"`, with a generated cover page at the front of the spine.

## Development

```sh
uv sync
uv run txt2epub book.txt
uv run ruff check .
uv run ruff format --check .
```
