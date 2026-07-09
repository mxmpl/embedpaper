#let embedpaper(fn, pages, width: 100%) = {
  /// Embeds every page of a PDF as native `image()` content, one source page
  /// per output page. Inherits the surrounding `page` context (call it inside a
  /// single-column page, e.g. via `embedpaper-page`). Also emits `<__paperlink>`
  /// metadata per page so the `embedpaper` CLI can restore the PDF's links,
  /// which `image()` drops.
  ///
  /// - `fn` (str): Path to the PDF, relative to the project root.
  /// - `pages` (int): Page count of the PDF (Typst cannot query it).
  /// - `width` (relative): Paper width vs. the **full page** width (default:
  ///   100%); scaled to fit this width and the page height, preserving aspect
  ///   ratio, then centered. Scaling against the whole page (rather than the
  ///   body area inside the margins) lets the paper bleed past the body margins,
  ///   so its own text lines up with the body text instead of being pushed
  ///   inward. The page's margins are left untouched, so an inherited
  ///   header/footer stays exactly where it sits on ordinary pages.
  assert(
    type(pages) == int and pages > 0,
    message: "embedpaper: `pages` must be a positive integer (the page count of '"
      + fn
      + "').",
  )
  for i in range(1, pages + 1) {
    context {
      let nat = measure(image(fn, page: i))
      let rel = width + 0% + 0pt
      let avail-w = rel.ratio * page.width + rel.length
      let scale = calc.min(avail-w / nat.width, page.height / nat.height)
      // `place` keeps the paper out of the flow so it can bleed into the
      // margins while the page's header/footer stay put.
      place(center + horizon, [#image(
        fn,
        page: i,
        width: nat.width * scale,
      ) <__paperimg>])
    }
    // Record where this page was placed so the `embedpaper` CLI can transform
    // the source page's links into these coordinates. `location().position()`
    // reports the flow anchor (the body-region top-left); the paper is centered
    // in the body region and bleeds past it, so shift by half the difference
    // between the body region and the paper to reach its real top-left.
    layout(size => context {
      let el = query(selector(<__paperimg>).before(here())).last()
      let dim = measure(el)
      let pos = el.location().position()
      [#metadata((
        filename: fn,
        src_page: i - 1, // 0-based, as pymupdf expects
        page: pos.page - 1, // 0-based output page index
        x: (pos.x + (size.width - dim.width) / 2).pt(),
        y: (pos.y + (size.height - dim.height) / 2).pt(),
        width: dim.width.pt(),
        height: dim.height.pt(),
      )) <__paperlink>]
    })
    if i < pages { pagebreak(weak: true) }
  }
}
