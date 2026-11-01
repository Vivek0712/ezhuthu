"""The Ezhuthu ontology served over MCP (stdio), with the official ``mcp`` Python SDK.

Run it as a subprocess and talk MCP over its stdin/stdout::

    python -m ezhuthu.ontology.mcp_server            # serves ontology/ (the shipped, train-only build)
    python -m ezhuthu.ontology.mcp_server --root DIR # another build (a dir with lookups/ and letters_by_era.json)

Tools (one per function of :mod:`ezhuthu.ontology.lookup`, same arguments and records):

* ``find_entities(text)`` -> ``{"entities": [...]}``
* ``valid_letters(stage)`` -> ``{"stage": ..., "letters": [...]}``
* ``formulas_for(ruler)`` -> ``{"ruler": ..., "formulas": [...]}``
* ``entity(id)`` -> ``{"entity": {...} | null}``
* ``hints_for_gap(left, right, gap_chars?, limit?)`` -> ``{"hints": [...]}``

Each result is a JSON object (``structuredContent``, and the same JSON as text content). Bad input (Tamil
script instead of ISO-15919, text over ``MAX_TEXT_CHARS``, ``gap_chars < 1``, an unknown stage) comes back
as an MCP tool error carrying the lookup API's ``ValueError``/``KeyError`` message.

Nothing here touches the network or AWS. The server reads the same files the direct API reads; on an
AgentCore runtime it is started by the agent as a stdio subprocess in the same Python environment
(see ``ontology/COA.md``, "Serving over MCP").
"""

from __future__ import annotations

import argparse
import functools
import logging
import os
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ezhuthu.ontology import lookup

SERVER_NAME = "ezhuthu-ontology"
TOOL_NAMES = ("find_entities", "valid_letters", "formulas_for", "entity", "hints_for_gap")
ROOT_ENV = "EZHUTHU_ONTOLOGY_ROOT"

INSTRUCTIONS = (
    "Tamil epigraphy ontology (rulers, titles, royal formulas, places, temples, admin units, letters by "
    "script stage) built from train-split DHARMA editions. All text arguments are ISO-15919 (not Tamil "
    "script). Entity ids look like 'ez:ruler/rajaraja-i'. Derived data is CC BY-SA 4.0 (DHARMA)."
)


def _input_errors(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Report the lookup API's input errors (ValueError, TypeError, KeyError for an unknown stage) to the
    client with their message.
    Anything else stays an opaque 'Error executing tool' (the SDK keeps crash details on the server)."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except (ValueError, TypeError, KeyError) as exc:
            msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
            raise ToolError(f"{type(exc).__name__}: {msg}") from exc

    return wrapper


def build_server(root: str | None = None) -> MCPServer:
    """An MCP server whose tools answer from the ontology build in ``root`` (default: ``ontology/``)."""
    onto = lookup.load(root)  # load once at start so a broken build fails fast, not on the first call
    server = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS, version="0.1.0")

    @server.tool()
    @_input_errors
    def find_entities(text: str) -> dict[str, Any]:
        """Entities (rulers, titles, formulas, places, temples, admin units, deities, grant types, measures,
        taxes) mentioned in ISO-15919 text, with character spans.

        Args:
            text: ISO-15919 text (at most 50,000 characters).
        """
        return {"entities": onto.find_entities(text)}

    @server.tool()
    @_input_errors
    def valid_letters(stage: str) -> dict[str, Any]:
        """Base letters valid in a script stage, with Unicode glyphs and corpus counts.

        Args:
            stage: tutor level L1-L5 or a stage id such as 'chola-tamil', 'vatteluttu', 'tamil-brahmi-1'.
        """
        return {"stage": stage, "letters": onto.valid_letters(stage)}

    @server.tool()
    @_input_errors
    def formulas_for(ruler: str) -> dict[str, Any]:
        """Royal-praise formulas and epithets for a ruler: its own, then its dynasty's, then common ones.

        Args:
            ruler: ruler id, e.g. 'ez:ruler/rajaraja-i'.
        """
        return {"ruler": ruler, "formulas": onto.formulas_for(ruler)}

    @server.tool()
    @_input_errors
    def entity(id: str) -> dict[str, Any]:  # noqa: A002 - the MCP argument name is part of the contract
        """The full lookup record of one entity (contracts/ontology-lookup.schema.json), or null.

        Args:
            id: entity id, e.g. 'ez:ruler/rajaraja-i'.
        """
        return {"entity": onto.entity(id)}

    @server.tool()
    @_input_errors
    def hints_for_gap(left: str, right: str, gap_chars: int | None = None, limit: int = 10) -> dict[str, Any]:
        """Ontology entities that could fill a gap between two ISO-15919 contexts, best first. Each hint has
        id, kind, label, fill (folded key form, or null for a regnal slot), alt_fills, score and reason.

        Args:
            left: ISO-15919 text before the gap.
            right: ISO-15919 text after the gap.
            gap_chars: gap length in Tamil letters, if known (>= 1).
            limit: maximum number of hints.
        """
        return {"hints": onto.hints_for_gap(left, right, gap_chars, limit)}

    return server


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", help="ontology build dir (default: ontology/ or $EZHUTHU_ONTOLOGY_ROOT)")
    args = ap.parse_args(argv)
    # stdout is the MCP channel: logs go to stderr only
    logging.basicConfig(level=os.environ.get("EZHUTHU_MCP_LOG", "WARNING"))
    build_server(args.root or os.environ.get(ROOT_ENV) or None).run("stdio")


if __name__ == "__main__":
    main()
