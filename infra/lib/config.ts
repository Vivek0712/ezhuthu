import { readFileSync } from 'node:fs';
import * as path from 'node:path';
import { parse } from 'yaml';

export const REPO_ROOT = path.resolve(__dirname, '..', '..');

export interface ModelsConfig {
  awsProfile: string;
  region: string;
  /** Model IDs the agents may call today (llm.default / escalate / cheap). */
  activeModelIds: string[];
  llm: Record<string, string>;
}

/** config/models.yaml is the only source of Bedrock model IDs (docs/TEAMS.md rule 5). */
export function loadModelsConfig(file = path.join(REPO_ROOT, 'config', 'models.yaml')): ModelsConfig {
  const doc = parse(readFileSync(file, 'utf8')) as {
    aws_profile: string;
    region: string;
    llm: Record<string, string>;
  };
  if (!doc?.llm?.default || !doc.llm.escalate) throw new Error(`${file}: llm.default and llm.escalate are required`);
  const active = ['default', 'escalate', 'cheap'].map((k) => doc.llm[k]).filter((v): v is string => !!v);
  return { awsProfile: doc.aws_profile, region: doc.region, activeModelIds: active, llm: doc.llm };
}

/**
 * IAM resources for invoking a model ID. Cross-region inference profiles ("us.anthropic...") need both the
 * profile ARN and the underlying foundation-model ARN in every region the profile routes to.
 */
export function bedrockResourceArns(modelId: string, partition: string, account: string): string[] {
  const geo = /^(us|eu|apac|global)\.(.+)$/.exec(modelId);
  const base = geo ? geo[2]! : modelId;
  const arns = [`arn:${partition}:bedrock:*::foundation-model/${base}`];
  if (geo) arns.push(`arn:${partition}:bedrock:*:${account}:inference-profile/${modelId}`);
  return arns;
}
