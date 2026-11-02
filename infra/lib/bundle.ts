import { existsSync, readdirSync } from 'node:fs';
import * as path from 'node:path';

/**
 * Files the AgentCore code bundle (agentcore/package.sh) must contain so that the runtime serves the agent with
 * the ontology over MCP: the agent spawns `python -m ezhuthu.ontology.mcp_server` as a stdio child process
 * (src/ezhuthu/agent/ontology_mcp.py), which needs the `mcp` SDK, Strands' MCP client and the ontology data next
 * to the package (ezhuthu.ontology.lookup resolves `<bundle>/ontology` itself).
 */
export const REQUIRED_BUNDLE_FILES = [
  'agent_runtime.py',
  'config/models.yaml',
  'ezhuthu/agentcore_app.py',
  'ezhuthu/agent/ontology_mcp.py',
  'ezhuthu/ontology/mcp_server.py',
  'ezhuthu/ontology/lookup.py',
  'mcp/__init__.py',
  'mcp/client/stdio.py',
  'mcp/server/stdio.py',
  'strands/tools/mcp/__init__.py',
  'ontology/letters_by_era.json',
] as const;

/** Missing paths (relative to `dir`); empty when the bundle can run the ontology MCP server. */
export function missingBundleFiles(dir: string): string[] {
  const missing: string[] = REQUIRED_BUNDLE_FILES.filter((f) => !existsSync(path.join(dir, f)));
  const lookups = path.join(dir, 'ontology', 'lookups');
  const hasLookups = existsSync(lookups) && readdirSync(lookups).some((f) => f.endsWith('.json'));
  if (!hasLookups) missing.push('ontology/lookups/*.json');
  return missing;
}

export function assertAgentBundle(dir: string): void {
  if (!existsSync(path.join(dir, 'agent_runtime.py')))
    throw new Error(`AgentCore code bundle missing at ${dir}. Run \`npm run package:agent\` in infra/ first.`);
  const missing = missingBundleFiles(dir);
  if (missing.length)
    throw new Error(
      `AgentCore code bundle at ${dir} cannot run the ontology MCP server; missing: ${missing.join(', ')}. ` +
        'Re-run `npm run package:agent` in infra/.',
    );
}
