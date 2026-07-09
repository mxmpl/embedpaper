"""Re-create the links of embedded papers on the compiled PDF."""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

PLACEMENT_LABEL = "<__paperlink>"


@dataclass(frozen=True)
class Placement:
    """Where one source page was embedded in the compiled document.

    Coordinates are in points with a top-left origin, matching the placement
    metadata that ``embedpaper.typ`` records for every embedded page.
    """

    filename: str  # absolute path to the source PDF
    src_page: int  # 0-based page index in the source PDF
    page: int  # 0-based page index in the compiled document
    x: float
    y: float
    width: float
    height: float


class PdfEmbedError(Exception):
    """A recoverable error in the embedding pipeline."""


def run_typst(args: list[str], timeout: int = 30) -> str:
    """Run a ``typst`` subcommand, returning stdout or raising ``PdfEmbedError``."""
    try:
        result = subprocess.run(["typst", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as error:
        raise PdfEmbedError("Typst compiler not found; is it installed and on your PATH?") from error
    except subprocess.TimeoutExpired as error:
        raise PdfEmbedError(f"`typst {args[0]}` timed out after {timeout}s") from error
    if result.returncode != 0:
        raise PdfEmbedError(f"`typst {args[0]}` failed:\n{result.stderr.strip()}")
    return result.stdout


def read_placements(document: Path, document_dir: Path) -> list[Placement]:
    """Query the compiled document for the placement metadata of every embedded page."""
    logger.info("Reading embed placements")
    raw = run_typst(["query", str(document), PLACEMENT_LABEL])
    entries = json.loads(raw) if raw.strip() else []
    placements = [
        Placement(
            filename=str((document_dir / entry["value"]["filename"]).resolve()),
            src_page=int(entry["value"]["src_page"]),
            page=int(entry["value"]["page"]),
            x=float(entry["value"]["x"]),
            y=float(entry["value"]["y"]),
            width=float(entry["value"]["width"]),
            height=float(entry["value"]["height"]),
        )
        for entry in entries
    ]
    logger.info("Found %d embedded pages", len(placements))
    return placements


def scale_rect(place: Placement, scale: float, rect: pymupdf.Rect) -> pymupdf.Rect:
    """Map a rectangle from source-page coordinates onto the embedded page ``place``."""
    return pymupdf.Rect(
        place.x + rect.x0 * scale,
        place.y + rect.y0 * scale,
        place.x + rect.x1 * scale,
        place.y + rect.y1 * scale,
    )


def remap_destination(link: dict, target: Placement, source_doc: pymupdf.Document) -> pymupdf.Point:
    """Map an internal link's destination point onto the embedded target page.

    For named destinations (how LaTeX/hyperref stores citation and cross-reference
    targets), PyMuPDF returns the point verbatim in the source page's *PDF*
    coordinates (bottom-left origin, y up). ``insert_link`` expects the
    destination in top-left coordinates and flips it to PDF space itself, so we
    only flip the source point to top-left and scale it into the embedded page;
    ``insert_link`` handles the final flip.
    """
    to = link.get("to", pymupdf.Point(0, 0))
    src_page = source_doc[link["page"]]
    scale = target.width / src_page.rect.width
    top_y = src_page.rect.height - to.y  # source bottom-left -> source top-left
    out_x = target.x + to.x * scale  # -> embedded page, top-left
    out_y = target.y + top_y * scale
    return pymupdf.Point(out_x, out_y)


def _transfer_one(link, place, scale, out_page, by_source, source) -> int:
    """Transfer a single link; return 1 if it was added, 0 if skipped."""
    # `from` is in the source page's top-left coordinates, like the placement
    # metadata, so it scales directly.
    new = {"kind": link["kind"], "from": scale_rect(place, scale, link["from"])}

    if link["kind"] == pymupdf.LINK_URI:
        new["uri"] = link["uri"]
    elif link["kind"] in (pymupdf.LINK_GOTO, pymupdf.LINK_NAMED):
        # `get_links` resolves named destinations to page + point. Internal
        # links always target the same paper file.
        target = by_source.get((place.filename, link.get("page", -1)))
        if target is None:
            return 0  # destination page wasn't embedded
        new["kind"] = pymupdf.LINK_GOTO
        new["page"] = target.page
        new["to"] = remap_destination(link, target, source(place.filename))
    else:
        return 0  # drop LAUNCH / GOTOR (external file) links
    out_page.insert_link(new)
    return 1


def transfer_links(pdf_path: Path, placements: list[Placement]) -> int:
    """Copy each source page's links onto the matching embedded page.

    Returns the number of links added. The document is saved in place
    incrementally.
    """
    if not placements:
        logger.warning("No embedded pages found; nothing to link")
        return 0
    # (source pdf, source page) -> its placement, so internal links can be
    # remapped from source coordinates to the page they now live on.
    by_source = {(p.filename, p.src_page): p for p in placements}
    source_docs: dict[str, pymupdf.Document] = {}

    def source(filename: str) -> pymupdf.Document:
        return source_docs.setdefault(filename, pymupdf.open(filename))

    added = 0
    try:
        with pymupdf.open(pdf_path) as doc:
            for place in placements:
                src_page = source(place.filename)[place.src_page]
                # width:100% preserves the aspect ratio, so a single scale maps
                # source-page points to output points.
                scale = place.width / src_page.rect.width
                out_page = doc[place.page]
                for link in src_page.get_links():
                    added += _transfer_one(link, place, scale, out_page, by_source, source)
            doc.saveIncr()
    finally:
        for src in source_docs.values():
            src.close()
    logger.info("Added %d links to %s", added, pdf_path)
    return added
