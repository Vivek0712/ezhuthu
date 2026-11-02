"""Offline smoke test of the AgentCore code bundle (agentcore/build), run inside linux/arm64 Python 3.12.

    npm run smoke:agent      # docker run --platform linux/arm64 python:3.12-slim ... (see package.json)

It imports only from the bundle (PYTHONPATH=<bundle>, cwd elsewhere, no repo checkout), then checks that:
1. the agent's ontology is the bundled MCP server over stdio (``mcp:...``), not the direct fallback, and that a
   tool call round-trips through the child process;
2. ``EZHUTHU_STORE=dynamodb`` builds the pk/sk DynamoStore from ``EZHUTHU_TABLE`` (no AWS call is made);
3. the decider backend the stack sets without a key secret (``fallback``) resolves to the no-decider fallback;
4. the AgentCore entry module imports.
Exit code 0 means every check passed. No network, no AWS credentials, no model calls.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    os.environ.update({"EZHUTHU_ONTOLOGY": "mcp", "EZHUTHU_STORE": "dynamodb", "EZHUTHU_TABLE": "smoke-table",
                       "EZHUTHU_DECIDER_BACKEND": "fallback", "AWS_REGION": "us-east-1",
                       "EZHUTHU_CACHE_DIR": "/tmp/ezhuthu-cache"})
    os.environ.pop("EZHUTHU_FIXTURES", None)
    bundle = os.environ.get("PYTHONPATH", "").split(os.pathsep)[0]
    out: dict[str, object] = {"python": sys.version.split()[0], "platform": sys.platform, "cwd": os.getcwd()}

    import ezhuthu

    out["ezhuthu_from"] = os.path.dirname(ezhuthu.__file__)
    assert bundle and out["ezhuthu_from"].startswith(bundle), f"ezhuthu imported from {out['ezhuthu_from']}, not the bundle"

    from ezhuthu.agent.ontology_port import get_ontology

    onto = get_ontology()
    out["ontology"] = onto.name
    assert onto.name.startswith("mcp:"), f"ontology is {onto.name!r}, expected the bundled MCP server"
    hits = onto.find_entities("matirai koṇṭa kō-p-parakēcari-panmarkku yāṇṭu")
    out["find_entities"] = [getattr(h, "label", str(h)) for h in hits][:3]
    assert hits, "MCP find_entities returned nothing for a Chola regnal title"
    hints = onto.hints_for_gap("svasti ", " matirai")
    out["hints_for_gap"] = [getattr(h, "label", str(h)) for h in hints][:3]
    assert hints, "MCP hints_for_gap returned nothing after \"svasti \""
    assert onto.name.startswith("mcp:"), f"ontology fell back to {onto.name!r} during the tool calls"
    close = getattr(onto, "close", None)
    if callable(close):
        close()

    from ezhuthu.api.storage import DynamoStore, store_from_env

    store = store_from_env()
    assert isinstance(store, DynamoStore), type(store).__name__
    assert DynamoStore.key("session", "s-1") == {"pk": "SESSION#s-1", "sk": "STATE"}
    out["store"] = f"DynamoStore({store.table.name}, index={store.index})"

    from ezhuthu.agent.decider import NoDecider, default_decider

    dec = default_decider()
    assert isinstance(dec, NoDecider), type(dec).__name__
    out["decider"] = "fallback (NoDecider)"

    import ezhuthu.agentcore_app as entry

    assert hasattr(entry, "app"), "ezhuthu.agentcore_app has no 'app'"
    out["entrypoint"] = type(entry.app).__name__

    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("bundle smoke: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
