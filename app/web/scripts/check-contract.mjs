// Fails if api/openapi.yaml drifts from contracts/restore-api.md or contracts/benchmark-item.schema.json.
// The markdown contract is the source of truth; the OpenAPI file is the machine-readable mirror.
import { readFileSync } from 'node:fs';
import { parse } from 'yaml';

const root = new URL('../', import.meta.url);
const repo = new URL('../../', root);
const md = readFileSync(new URL('contracts/restore-api.md', repo), 'utf8');
const bench = JSON.parse(readFileSync(new URL('contracts/benchmark-item.schema.json', repo), 'utf8'));
const spec = parse(readFileSync(new URL('api/openapi.yaml', root), 'utf8'));

const errors = [];
const found = new Set();
for (const m of md.matchAll(/\b(GET|POST|PUT|DELETE|PATCH)\s+`?(\/api\/[A-Za-z0-9_{}/-]+)/g)) {
  const method = m[1].toLowerCase();
  const path = m[2].replace(/\/$/, '');
  found.add(`${method} ${path}`);
  if (!spec.paths?.[path]?.[method]) errors.push(`contract endpoint missing from openapi: ${m[1]} ${path}`);
}
if (found.size < 9) errors.push(`expected at least 9 endpoints in the contract, parsed ${found.size}`);

const want = [...bench.required].sort().join(',');
const have = [...(spec.components.schemas.BenchmarkItem.required ?? [])].sort().join(',');
if (want !== have) errors.push(`BenchmarkItem.required drifted: contract=${want} openapi=${have}`);

// The tutor answer: a rules decision has no confidence, and the async lesson explanation arrives on /api/answer.
const answer = spec.components.schemas.AnswerResponse.properties;
const nullable = (p) => [p?.type].flat().includes('null');
if (/"decider_confidence":\s*0\.0\s*\|\s*null/.test(md) && !nullable(answer.decider_confidence))
  errors.push('contract allows decider_confidence null; openapi AnswerResponse.decider_confidence must be nullable');
if (md.includes('context_update') && !answer.context_update) errors.push('contract has context_update; openapi AnswerResponse lacks it');
if (/reviewing an item that is not\s+`pending` returns 409/.test(md) && !spec.paths['/api/queue/{id}'].post.responses['409'])
  errors.push('contract says a second review returns 409; openapi /api/queue/{id} lacks a 409 response');

const levels = spec.components.schemas.Level.enum.join(',');
if (levels !== 'L1,L2,L3,L4,L5') errors.push(`Level enum drifted: ${levels}`);

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}
console.log(`contract ok: ${found.size} endpoints mirrored`);
