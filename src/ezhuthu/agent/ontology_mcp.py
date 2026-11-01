"""The agent's ontology access over MCP: a Strands ``MCPClient`` talking stdio to ``ezhuthu.ontology.mcp_server``.

``McpOntology`` implements :class:`ezhuthu.agent.ontology_port.OntologyPort`, so the restorer and tutor use it
exactly like the direct API. It starts the server as a subprocess of the current Python
(``sys.executable -m ezhuthu.ontology.mcp_server``), so the server always runs in the agent's own environment
(locally, in tests and in the AgentCore runtime bundle). The same client is also a Strands tool provider:
``Agent(tools=[onto.client])`` gives an agent the five ontology tools directly.
"""

from __future__ import annotations

import atexit
import copy
import json
import logging
import os
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from strands.tools.mcp import MCPClient

from .ontology_port import Hint, ModuleOntology

log = logging.getLogger(__name__)

SERVER_MODULE = "ezhuthu.ontology.mcp_server"
TOOL_NAMES = ("find_entities", "valid_letters", "formulas_for", "entity", "hints_for_gap")
# Passed through to the server subprocess (the MCP SDK only inherits a safe minimal environment).
PASSTHROUGH_ENV = ("PYTHONPATH", "EZHUTHU_ONTOLOGY_ROOT", "EZHUTHU_MCP_LOG")


class McpOntologyError(RuntimeError):
    """The MCP server could not be started or a tool call failed for a reason other than bad input."""


def _import_roots() -> list[str]:
    """Directories that hold the ``ezhuthu`` package and the ``mcp`` SDK in *this* process. An AgentCore
    Direct Code Deploy bundle installs its wheels with ``--target`` and runs from the bundle root, so a child
    interpreter would not find them unless they are on its PYTHONPATH."""
    import mcp

    import ezhuthu

    roots: list[str] = []
    for mod in (ezhuthu, mcp):
        d = str(Path(mod.__file__).resolve().parents[1])
        if d not in roots:
            roots.append(d)
    return roots


def server_parameters(root: str | None = None) -> StdioServerParameters:
    """How to launch the ontology MCP server: this interpreter, ``-m ezhuthu.ontology.mcp_server``, with
    this process's import roots on PYTHONPATH (same environment, whatever the working directory)."""
    env = {k: os.environ[k] for k in PASSTHROUGH_ENV if os.environ.get(k)}
    paths = _import_roots() + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(paths))
    args = ["-m", SERVER_MODULE] + (["--root", root] if root else [])
    return StdioServerParameters(command=sys.executable, args=args, env=env)


def make_client(root: str | None = None, startup_timeout: int = 30) -> MCPClient:
    """A (not yet started) Strands MCPClient for the ontology server over stdio."""
    params = server_parameters(root)
    return MCPClient(lambda: stdio_client(params), startup_timeout=startup_timeout,
                     application_name="ezhuthu-agent")


class McpOntology:
    """OntologyPort over MCP. Results are the lookup API's records, sent as JSON over stdio."""

    name = "mcp:ezhuthu-ontology (stdio)"

    def __init__(self, client: MCPClient | None = None, *, root: str | None = None, startup_timeout: int = 30):
        self.client = client or make_client(root, startup_timeout)
        self._entity_cache: dict[str, dict[str, Any] | None] = {}
        self._lock = threading.Lock()
        self._closed = False
        try:
            self.client.start()
            tools = {t.tool_name for t in self.client.list_tools_sync()}
        except Exception as exc:
            raise McpOntologyError(f"ontology MCP server did not start: {exc}") from exc
        missing = sorted(set(TOOL_NAMES) - tools)
        if missing:
            self.close()
            raise McpOntologyError(f"ontology MCP server lacks tools {missing}")
        atexit.register(self.close)

    # ---- transport -----------------------------------------------------------------
    def call(self, tool: str, **arguments: Any) -> dict[str, Any]:
        """Call one tool and return its JSON object. Input errors raise ``ValueError`` (``KeyError`` for an unknown
        stage), like the direct API."""
        args = {k: v for k, v in arguments.items() if v is not None}
        res = self.client.call_tool_sync(f"ez-{uuid.uuid4().hex[:12]}", tool, args)
        text = "".join(c.get("text", "") for c in res.get("content", []) if isinstance(c, dict))
        if res.get("status") == "error":
            if "KeyError: " in text:  # unknown script stage, as the direct API raises it
                raise KeyError(text.split("KeyError: ", 1)[1])
            for marker in ("ValueError: ", "TypeError: "):  # the server's input-error prefix
                if marker in text:
                    raise ValueError(text.split(marker, 1)[1])
            raise McpOntologyError(text or f"MCP tool {tool} failed")
        data = res.get("structuredContent")
        if data is None:
            data = json.loads(text)
        return data

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.client.stop(None, None, None)
        except Exception:
            log.debug("MCP client stop failed", exc_info=True)

    # ---- OntologyPort --------------------------------------------------------------
    def hints_for_gap(self, left: str, right: str, gap_chars: int | None = None) -> list[Hint]:
        hints = self.call("hints_for_gap", left=left, right=right, gap_chars=gap_chars)["hints"]
        return [ModuleOntology._to_hint(h) for h in hints]

    def find_entities(self, text: str) -> list[Hint]:
        return [ModuleOntology._to_hint(e) for e in self.call("find_entities", text=text)["entities"]]

    def valid_letters(self, stage: str) -> set[str] | None:
        letters = self.call("valid_letters", stage=stage)["letters"]
        if letters is None:
            return None
        return {x.get("iso") or x.get("id") if isinstance(x, dict) else x for x in letters} - {None}

    def entity(self, entity_id: str) -> dict[str, Any] | None:
        # The restorer asks for the same few records per gap; records are immutable for a process.
        with self._lock:
            if entity_id in self._entity_cache:
                return copy.deepcopy(self._entity_cache[entity_id])
        rec = self.call("entity", id=entity_id)["entity"]
        with self._lock:
            if len(self._entity_cache) > 4096:
                self._entity_cache.clear()
            self._entity_cache[entity_id] = rec
        return copy.deepcopy(rec)

    # ---- extras beyond OntologyPort ------------------------------------------------
    def formulas_for(self, ruler: str) -> list[dict[str, Any]]:
        return self.call("formulas_for", ruler=ruler)["formulas"]

    def raw_hints_for_gap(self, left: str, right: str, gap_chars: int | None = None,
                          limit: int = 10) -> list[dict[str, Any]]:
        """The full hint records (fill, alt_fills, score, reason), not just the restore-API view."""
        return self.call("hints_for_gap", left=left, right=right, gap_chars=gap_chars, limit=limit)["hints"]
