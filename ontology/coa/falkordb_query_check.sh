#!/usr/bin/env bash
# Runs the openCypher that the patched COA FalkorDBLexicalStore sends (Neptune DB
# queries with id(e)/id(subj)/id(t) rewritten to entityId/topicId) against a
# throwaway FalkorDB holding a 2-entity graphrag-shaped graph, and fails unless
# every query returns the expected values. Checks the dialect only: no COA or
# graphrag-toolkit code runs here.
set -euo pipefail
IMAGE=falkordb/falkordb@sha256:725b74d400124862c9e0f318c56bfb3c55b97cd7f301d9dfe8685980fb3c8195  # graph module 4.22.3
C=ezhuthu-falkordb-check
T=b0310331b8d553b7b3ebfbf51   # python -m ezhuthu.ontology.coa_store -> tenant
docker run -d --rm --name $C -p 127.0.0.1:6380:6379 "$IMAGE" >/dev/null
trap 'docker rm -f $C >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 60); do
  docker exec $C redis-cli PING 2>/dev/null | grep -q PONG && break
  sleep 0.5
done
docker exec $C redis-cli PING | grep -q PONG || { echo "FalkorDB did not start" >&2; exit 1; }

q(){ docker exec $C redis-cli GRAPH.QUERY check "$1"; }
L(){ printf '`__%s__%s__`' "$1" "$T"; }
fail=0
# expect <name> <query> <expected line>... : each expected line must appear verbatim in the output.
expect(){
  local name=$1 query=$2 out; shift 2
  out=$(q "$query")
  echo "# $name"; echo "$out"
  for want in "$@"; do
    if ! grep -qxF -- "$want" <<<"$out"; then echo "FAIL $name: missing '$want'" >&2; fail=1; fi
  done
}

q "CREATE (a:$(L SYS_Class) {value:'Ruler', count:2}), (b:$(L SYS_Class) {value:'Temple', count:1}),
 (a)-[:\`__SYS_RELATION__\` {value:'built', count:1}]->(b),
 (e1:$(L Entity) {entityId:'e1', value:'Rajaraja I', class:'Ruler'}), (e2:$(L Entity) {entityId:'e2', value:'Brihadisvara', class:'Temple'}),
 (f:$(L Fact) {value:'Rajaraja I built Brihadisvara'}), (e1)-[:\`__SUBJECT__\`]->(f), (e2)-[:\`__OBJECT__\`]->(f),
 (t:$(L Topic) {topicId:'t1', value:'Chola temples'}), (s:$(L Statement) {value:'x'})-[:\`__BELONGS_TO__\`]->(t)" >/dev/null

expect get_class_nodes \
  "MATCH (c:$(L SYS_Class)) RETURN c.value AS value, c.count AS count ORDER BY c.count DESC" \
  Ruler 2 Temple 1
expect get_class_relations \
  "MATCH (s:$(L SYS_Class))-[r:\`__SYS_RELATION__\`]->(t:$(L SYS_Class)) RETURN s.value AS source_class, r.value AS predicate, t.value AS target_class, r.count AS count" \
  Ruler built Temple 1
expect get_entities_by_class \
  "CYPHER classification='Ruler' limit=100 MATCH (e:$(L Entity)) WHERE e.class = \$classification RETURN e.entityId AS entity_id, e.value AS value, e.class AS classification LIMIT \$limit" \
  e1 "Rajaraja I" Ruler
expect get_facts_for_entities \
  "CYPHER entity_ids=['e1'] MATCH (subj:$(L Entity))-[:\`__SUBJECT__\`]->(f:$(L Fact)) WHERE subj.entityId IN \$entity_ids OPTIONAL MATCH (obj:$(L Entity))-[:\`__OBJECT__\`]->(f) RETURN subj.value AS subject_value, subj.class AS subject_class, f.value AS fact_value, obj.value AS object_value, obj.class AS object_class" \
  "Rajaraja I" Ruler "Rajaraja I built Brihadisvara" Brihadisvara Temple
expect get_topics \
  "MATCH (t:$(L Topic)) OPTIONAL MATCH (s:$(L Statement))-[:\`__BELONGS_TO__\`]->(t) WITH t, count(s) AS stmt_count RETURN t.topicId AS topic_id, t.value AS value, stmt_count AS statement_count" \
  t1 "Chola temples" 1
# The rewrite is needed: id() on FalkorDB is an internal integer, not graphrag's entityId.
expect "id(e) is internal" \
  "MATCH (e:$(L Entity)) WHERE e.entityId = 'e1' RETURN id(e) = 'e1' AS same" \
  false

[ $fail -eq 0 ] && echo "OK: all FalkorDBLexicalStore queries returned the expected rows" || exit 1
