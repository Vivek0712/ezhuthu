#!/usr/bin/env bash
# Runs the openCypher that the patched COA FalkorDBLexicalStore sends (Neptune DB
# queries with id(e)/id(subj)/id(t) rewritten to entityId/topicId) against a
# throwaway FalkorDB holding a 2-entity graphrag-shaped graph. Checks the dialect
# only: no COA or graphrag-toolkit code runs here.
set -euo pipefail
C=ezhuthu-falkordb-check
T=b0310331b8d553b7b3ebfbf51   # python -m ezhuthu.ontology.coa_store -> tenant
docker run -d --rm --name $C -p 127.0.0.1:6380:6379 falkordb/falkordb:latest >/dev/null
trap 'docker rm -f $C >/dev/null' EXIT
until docker exec $C redis-cli PING 2>/dev/null | grep -q PONG; do :; done
q(){ docker exec $C redis-cli GRAPH.QUERY check "$1"; }
L(){ printf '`__%s__%s__`' "$1" "$T"; }
q "CREATE (a:$(L SYS_Class) {value:'Ruler', count:2}), (b:$(L SYS_Class) {value:'Temple', count:1}),
 (a)-[:\`__SYS_RELATION__\` {value:'built', count:1}]->(b),
 (e1:$(L Entity) {entityId:'e1', value:'Rajaraja I', class:'Ruler'}), (e2:$(L Entity) {entityId:'e2', value:'Brihadisvara', class:'Temple'}),
 (f:$(L Fact) {value:'Rajaraja I built Brihadisvara'}), (e1)-[:\`__SUBJECT__\`]->(f), (e2)-[:\`__OBJECT__\`]->(f),
 (t:$(L Topic) {topicId:'t1', value:'Chola temples'}), (s:$(L Statement) {value:'x'})-[:\`__BELONGS_TO__\`]->(t)" >/dev/null
echo "# get_class_nodes";       q "MATCH (c:$(L SYS_Class)) RETURN c.value AS value, c.count AS count ORDER BY c.count DESC"
echo "# get_class_relations";   q "MATCH (s:$(L SYS_Class))-[r:\`__SYS_RELATION__\`]->(t:$(L SYS_Class)) RETURN s.value AS source_class, r.value AS predicate, t.value AS target_class, r.count AS count"
echo "# get_entities_by_class"; q "CYPHER classification='Ruler' limit=100 MATCH (e:$(L Entity)) WHERE e.class = \$classification RETURN e.entityId AS entity_id, e.value AS value, e.class AS classification LIMIT \$limit"
echo "# get_facts_for_entities";q "CYPHER entity_ids=['e1'] MATCH (subj:$(L Entity))-[:\`__SUBJECT__\`]->(f:$(L Fact)) WHERE subj.entityId IN \$entity_ids OPTIONAL MATCH (obj:$(L Entity))-[:\`__OBJECT__\`]->(f) RETURN subj.value AS subject_value, subj.class AS subject_class, f.value AS fact_value, obj.value AS object_value, obj.class AS object_class"
echo "# get_topics";            q "MATCH (t:$(L Topic)) OPTIONAL MATCH (s:$(L Statement))-[:\`__BELONGS_TO__\`]->(t) WITH t, count(s) AS stmt_count RETURN t.topicId AS topic_id, t.value AS value, stmt_count AS statement_count"
