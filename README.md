# embedpaper

Embed full PDF papers into a Typst document, preserving selectable text and links.

Typst 0.15's native `image()` can embed PDF pages full-width with selectable
text, but it drops link annotations. `embedpaper` restores them: a Typst
function places each page and records where it landed, and a small CLI
re-creates the source PDF's citation, cross-reference, and URI links on the
compiled output.

## Install

```sh
uvx embedpaper --help
```

Requires [uv](https://github.com/astral-sh/uv) and the
[Typst CLI](https://github.com/typst/typst) on your `PATH`.

## Usage

1. Import `embedpaper.typ` and call it inside a page for each PDF you want to embed:

   ```typst
   #import "embedpaper.typ": embedpaper

   #page[
     #embedpaper("papers/example.pdf", 12)
   ]
   ```

   `pages` is the PDF's page count (Typst can't query it, so pass it explicitly).
   Pass `width:` to scale the paper against the page width (default `100%`).

2. Compile, then run `embedpaper` to restore the links:

   ```sh
   typst compile document.typ
   uvx embedpaper document.typ
   ```

   This reads the placement metadata Typst embedded during compilation and
   incrementally saves `document.pdf` with each source link remapped onto its
   embedded page.

3. Optionally, verify the result:

   ```sh
   uvx embedpaper document.typ --audit
   ```

   The audit re-derives where every link *should* point from the source PDFs
   and checks the compiled document against it — link count parity, correct
   destinations, and "Figure N" / "Table N" cross-references — exiting
   non-zero on any mismatch. Useful as a CI regression guard.

## How it works

- `embedpaper.typ` places each source page as an image and emits
  `<__paperlink>` metadata (filename, source page, output page, and
  placement rectangle) for every embedded page.
- `embedpaper embed` queries that metadata with `typst query`, then uses
  PyMuPDF to copy each source page's links onto the matching output page,
  scaling coordinates and remapping internal destinations to their new
  page.
