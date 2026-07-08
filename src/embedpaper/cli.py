"""Command-line interface: ``embedpaper embed`` and ``embedpaper audit``."""

import argparse
import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .audit import audit
from .embed import PdfEmbedError, read_placements, transfer_links

console = Console()


def _setup_logging() -> None:
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, show_path=False, markup=True)],
    )


def cmd_embed(document: Path) -> int:
    """Re-create the embedded papers' links on the compiled PDF."""
    pdf_path = document.with_suffix(".pdf")
    if not pdf_path.is_file():
        console.print(f"[red]✗[/red] {pdf_path} not found — compile it first (`typst c {document}`)")
        return 1
    placements = read_placements(document, document.parent)
    transfer_links(pdf_path, placements)
    console.print("[green]✓ Done — papers embedded with clickable links[/green]")
    return 0


def cmd_audit(document: Path) -> int:
    """Audit the embedded papers' links; exit non-zero on any failure."""
    if not document.with_suffix(".pdf").is_file():
        console.print(f"[red]✗[/red] {document.with_suffix('.pdf')} not found — build it first")
        return 1
    result = audit(document, document.parent)
    summary = Table("Check", "Passed", title="Embedded-paper link audit")
    summary.add_row("Faithfulness (links kept)", str(result.faithfulness))
    summary.add_row("Destination fidelity", str(result.destination))
    summary.add_row("Figure/Table cross-refs", str(result.crossref))
    console.print(summary)
    if result.ok:
        console.print("[green]✓ All embedded-paper links verified[/green]")
        return 0
    failures = Table("Type", "Detail", title=f"[red]{len(result.failures)} failures[/red]")
    for kind, detail in result.failures[:40]:
        failures.add_row(kind, detail)
    console.print(failures)
    console.print(f"[red]✗ {len(result.failures)} link check(s) failed[/red]")
    return 1


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(
        prog="embedpaper",
        description="Embed full PDF papers into a Typst document with working links.",
    )
    parser.add_argument("document", type=Path, help="the compiled Typst document (.typ)")
    parser.add_argument("--audit", action="store_true", help="whether to audit the embedded papers' links")
    args = parser.parse_args(argv)
    if args.document.suffix != ".typ":
        console.print("[red]✗[/red] Document must have a .typ extension")
        return 1
    try:
        return (cmd_audit if args.audit else cmd_embed)(args.document)
    except PdfEmbedError as error:
        console.print(f"[red]✗[/red] {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
