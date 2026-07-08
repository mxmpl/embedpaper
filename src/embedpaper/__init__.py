"""Embed full PDF papers into a Typst document with selectable text and links.

Typst 0.15's native ``image()`` embeds PDF pages full-width with selectable
text, but it drops link annotations. This package restores them: it reads the
``<__paperlink>`` placement metadata emitted by ``embedpaper.typ`` and re-creates
each paper's links — citations, cross-references and URIs — on the compiled PDF.
"""

from .audit import audit
from .embed import Placement, read_placements, transfer_links

__all__ = ["Placement", "audit", "read_placements", "transfer_links"]
__version__ = "0.1.0"
