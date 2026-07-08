/// Strip a leading "./" so callers may write either "papers/x.pdf" or
/// "./papers/x.pdf".
#let _norm(path) = if path.starts-with("./") { path.slice(2) } else { path }

#let embedpaper(fn, pages, header: none, footer: none, margin: 1in, width: 100%) = {
  /// Embeds every page of a PDF paper into the thesis, one paper page per
  /// thesis page. Each page spans the full text width, breaking out of the
  /// body's column layout, while keeping a customizable header and footer.
  ///
  /// Pages are embedded with Typst's native `image()`, which keeps the paper's
  /// text selectable. `image()` does *not* carry over link annotations, so this
  /// function also records, for every embedded page, where it landed in the
  /// output (page index, position and size). The `embedpaper` CLI (`embedpaper`)
  /// reads that metadata after compilation and re-creates the paper's
  /// links — including internal citation links that jump to the bibliography —
  /// on top of the embedded pages.
  ///
  /// - `fn` (str): Path to the PDF, relative to the project root, e.g.
  ///   "papers/2025-spidr.pdf". A leading "./" is accepted.
  /// - `pages` (int): Number of pages in the PDF. Typst cannot query this, so
  ///   the author provides it.
  /// - `header` (content): Header shown on the embedded pages.
  /// - `footer` (content): Footer shown on the embedded pages.
  /// - `margin`: Page margin for the embedded pages (default: 1in).
  /// - `width` (relative): Width of each embedded page (default: 100%, i.e.
  ///   the full text width between the margins).
  ///
  /// **Example**:
  /// ```typst
  /// #embedpaper(
  ///   "papers/2025-spidr.pdf",
  ///   30,
  ///   header: align(right + horizon)[SpidR],
  ///   footer: context align(center)[#counter(page).display()],
  /// )
  /// ```

  assert(
    type(pages) == int and pages > 0,
    message: "embedpaper: `pages` must be a positive integer (the page count of '" + fn + "').",
  )
  let key = _norm(fn)

  // `page(..)[..]` isolates these settings to the embedded pages and reverts
  // to the document's layout (e.g. two columns) afterwards.
  page(
    columns: 1,
    margin: margin,
    header: header,
    footer: footer,
  )[
    #for i in range(1, pages + 1) {
      // Native PDF page numbers are 1-indexed.
      [#image(fn, page: i, width: width) <__paperimg>]

      // Record where this page was placed so `embedpaper` can transform the
      // source page's links into these coordinates.
      context {
        let el = query(selector(<__paperimg>).before(here())).last()
        layout(size => {
          let dim = measure(block(width: size.width, el))
          let pos = el.location().position()
          [#metadata((
              filename: key,
              src_page: i - 1, // 0-based, as pymupdf expects
              page: pos.page - 1, // 0-based output page index
              x: pos.x.pt(),
              y: pos.y.pt(),
              width: dim.width.pt(),
              height: dim.height.pt(),
            )) <__paperlink>]
        })
      }

      if i < pages { pagebreak(weak: true) }
    }
  ]
}
