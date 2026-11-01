"""The agent's ontology access over MCP: a Strands ``MCPClient`` talking stdio to ``ezhuthu.ontology.mcp_server``.

``McpOntology`` implements :class:`ezhuthu.agent.ontology_port.OntologyPort`, so the restorer and tutor use it
exactly like the direct API. It starts the server as a subprocess of the current Python
(``sys.executable -m ezhuthu.ontology.mcp_server``), so the server always runs in the agent's own environment
(locally, in tests and in the AgentCore runtime bundle). The same client is also a Strands tool provider:
``Agent(tools=[onto.client])`` gives an agent the five ontology tools directly.

If the server process dies after start (crash, OOM kill), the next call restarts the same client once and
retries; if that fails too, ``McpOntology`` answers from the in-process lookup API and renames itself
``fallback:direct (mcp died)`` so ``/health`` shows it.
"""

from __future__ import annotations

import atexit
import contextlib
import copy
import json
import logging
import os
import sys
import threading
import uuid
import warnings
from collections.abc import Iterator
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


class _TransportError(McpOntologyError):
    """The connection to the server failed (as opposed to the server reporting a tool error)."""


# Strands' MCPClient wraps an exception raised while calling a tool (the server process is gone, the pipe
# is closed) in an error result with this text; the server's own tool errors start "Error executing tool".
_TRANSPORT_PREFIX = "Tool execution failed: "
# The server's input errors, after "Error executing tool <name>: " (see mcp_server._input_errors).
_INPUT_ERRORS = (("KeyError: ", KeyError), ("ValueError: ", ValueError), ("TypeError: ", ValueError))
FALLBACK_NAME = "fallback:direct (mcp died)"


@contextlib.contextmanager
def _no_unawaited_close_warning() -> Iterator[None]:
    """``MCPClient.stop`` on a client whose background loop has already ended (a failed start inside
    ``MCPClient.start``, a dead server) schedules its close coroutine on a loop that never runs again, so
    Python warns "coroutine 'MCPClient.stop.<locals>._set_close_event' was never awaited" when the loop is
    closed. Nothing is lost: the background thread has already exited. This is in Strands, not our call
    order, so filter exactly that warning, on purpose, around our start and stop calls."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"coroutine 'MCPClient\.stop\.<locals>\._set_close_event' "
                                r"was never awaited", category=RuntimeWarning)
        yield


def _stop_quietly(client: MCPClient) -> None:
    """Stop the client. stop() re-raises the connection error that ended a dead session; that is expected."""
    with _no_unawaited_close_warning():
        try:
            client.stop(None, None, None)
        except Exception:
            log.debug("MCP client stop reported an error", exc_info=True)


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
        self._root = root
        self._entity_cache: dict[str, dict[str, Any] | None] = {}
        self._lock = threading.Lock()
        self._restart_lock = threading.Lock()
        self._generation = 0  # bumped on each restart, so concurrent callers restart only once
        self._direct: Any = None  # the in-process lookup API, once the server is given up on
        self._closed = False
        self._start()
        atexit.register(self.close)

    def _start(self) -> None:
        try:
            with _no_unawaited_close_warning():  # a failed start runs stop() on a finished loop
                self.client.start()
            tools = {t.tool_name for t in self.client.list_tools_sync()}
        except Exception as exc:
            raise McpOntologyError(f"ontology MCP server did not start: {exc}") from exc
        missing = sorted(set(TOOL_NAMES) - tools)
        if missing:
            _stop_quietly(self.client)
            raise McpOntologyError(f"ontology MCP server lacks tools {missing}")

    @property
    def fell_back(self) -> bool:
        return self._direct is not None

    # ---- transport -----------------------------------------------------------------
    def call(self, tool: str, **arguments: Any) -> dict[str, Any]:
        """Call one tool and return its JSON object. Input errors raise ``ValueError`` (``KeyError`` for an unknown
        stage), like the direct API. A dead server is restarted once; if it stays dead the call (and every later
        one) is answered by the in-process lookup API and ``name`` becomes ``fallback:direct (mcp died)``."""
        args = {k: v for k, v in arguments.items() if v is not None}
        if self._direct is None:
            generation = self._generation
            try:
                return self._call_mcp(tool, args)
            except _TransportError as exc:
                if self._recover(generation, exc):
                    try:
                        return self._call_mcp(tool, args)
                    except _TransportError as exc2:
                        self._give_up(exc2)
        return self._call_direct(tool, args)

    def _call_mcp(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            res = self.client.call_tool_sync(f"ez-{uuid.uuid4().hex[:12]}", tool, args)
        except Exception as exc:  # e.g. MCPClientInitializationError: the session is not running
            raise _TransportError(f"{type(exc).__name__}: {exc}") from exc
        text = "".join(c.get("text", "") for c in res.get("content", []) if isinstance(c, dict))
        if res.get("status") == "error":
            if text.startswith(_TRANSPORT_PREFIX):
                raise _TransportError(text)
            prefix = f"Error executing tool {tool}: "
            if text.startswith(prefix):
                rest = text[len(prefix):]
                for marker, exc_type in _INPUT_ERRORS:  # the server's input errors, as the direct API raises them
                    if rest.startswith(marker):
                        raise exc_type(rest[len(marker):])
            raise McpOntologyError(text or f"MCP tool {tool} failed")
        data = res.get("structuredContent")
        if data is None:
            data = json.loads(text)
        return data

    def _recover(self, generation: int, exc: Exception) -> bool:
        """Restart the client after a transport failure seen at ``generation``. True if the caller should
        retry over MCP; False once the direct fallback is in place."""
        with self._restart_lock:
            if self._direct is not None or self._closed:
                return False
            if self._generation != generation:  # another thread already restarted it
                return True
            log.warning("ontology MCP server connection lost (%s); restarting it", exc)
            _stop_quietly(self.client)
            self._generation += 1
            try:
                self._start()
                return True
            except McpOntologyError as exc2:
                self._give_up(exc2, locked=True)
                return False

    def _give_up(self, exc: Exception, locked: bool = False) -> None:
        """Switch to the direct lookup API for good (``locked``: the caller holds ``_restart_lock``)."""
        if not locked:
            with self._restart_lock:
                self._give_up(exc, locked=True)
            return
        if self._direct is not None:
            return
        from ezhuthu.ontology import lookup

        log.error("ontology MCP server unusable after a restart (%s); answering from the direct lookup API", exc)
        self._direct = lookup.load(self._root or os.environ.get("EZHUTHU_ONTOLOGY_ROOT") or None)
        self.name = FALLBACK_NAME
        _stop_quietly(self.client)

    def _call_direct(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """The same JSON objects the server returns (ezhuthu.ontology.mcp_server), computed in-process."""
        d = self._direct
        if tool == "find_entities":
            return {"entities": d.find_entities(args["text"])}
        if tool == "valid_letters":
            return {"stage": args["stage"], "letters": d.valid_letters(args["stage"])}
        if tool == "formulas_for":
            return {"ruler": args["ruler"], "formulas": d.formulas_for(args["ruler"])}
        if tool == "entity":
            return {"entity": d.entity(args["id"])}
        if tool == "hints_for_gap":
            return {"hints": d.hints_for_gap(args["left"], args["right"], args.get("gap_chars"),
                                             args.get("limit", 10))}
        raise McpOntologyError(f"unknown ontology tool {tool!r}")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _stop_quietly(self.client)

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
