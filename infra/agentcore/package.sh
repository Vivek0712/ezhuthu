#!/usr/bin/env bash
# Build the AgentCore Direct Code Deploy bundle: linux/arm64 wheels for Python 3.12, the ezhuthu
# package, and the agent_runtime.py entry point. CDK zips infra/agentcore/build as an S3 asset.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
out="$here/build"
req="$here/.requirements.txt"

rm -rf "$out"
mkdir -p "$out"
uv pip compile "$root/pyproject.toml" --extra agentcore \
  --python-version 3.12 --python-platform aarch64-manylinux_2_28 --quiet -o "$req"
uv pip install --quiet --target "$out" --python-version 3.12 --python-platform aarch64-manylinux_2_28 \
  --only-binary :all: -r "$req"
cp -R "$root/src/ezhuthu" "$out/ezhuthu"
cp "$here/agent_runtime.py" "$out/agent_runtime.py"
# config/models.yaml is the only source of model IDs; ship it next to the package.
mkdir -p "$out/config" && cp "$root/config/models.yaml" "$out/config/models.yaml"
# Ontology lookups (letters_by_era.json, lookups/*.json) next to the package.
mkdir -p "$out/ontology" && cp -R "$root/ontology/letters_by_era.json" "$root/ontology/lookups" "$out/ontology/"
# DHARMA-derived benchmark (CC BY-SA 4.0): retrieval corpus + inscription metadata, found via repo_root().
mkdir -p "$out/benchmark" && cp "$root"/benchmark/*.jsonl "$root/benchmark/DATA_CARD.md" "$out/benchmark/"
find "$out" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$out" -name '*.pyc' -delete
echo "bundle: $out ($(du -sh "$out" | cut -f1))"
