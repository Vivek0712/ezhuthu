import * as path from 'node:path';
import * as cdk from 'aws-cdk-lib';
import { EzhuthuAgentStack } from './agent-stack';
import { EzhuthuApiStack } from './api-stack';
import { EzhuthuAuthStack } from './auth-stack';
import { assertAgentBundle } from './bundle';
import { loadModelsConfig, REPO_ROOT } from './config';
import { EzhuthuDataStack } from './data-stack';
import { EzhuthuWebStack } from './web-stack';

export interface BuildOptions {
  agentCodeDir?: string;
  webDist?: string;
  /** Overrides the `ezhuthu:deciderSecretArn` context (bin/ezhuthu.ts looks the secret up when it is unset). */
  deciderSecretArn?: string;
}

/** Context value for "no hosted decider secret": anything that is not a Secrets Manager ARN. */
export function secretArnFromContext(v: unknown): string | undefined {
  return typeof v === 'string' && /^arn:aws[\w-]*:secretsmanager:/.test(v) ? v : undefined;
}

export function buildApp(app: cdk.App, opts: BuildOptions = {}) {
  const models = loadModelsConfig();
  const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: models.region };
  const webUrl = (app.node.tryGetContext('ezhuthu:webUrl') as string | undefined) || undefined;
  // Set when the runtime is managed outside CDK (AgentCore CLI / starter toolkit); the Agent stack is then skipped.
  const externalRuntimeArn = (app.node.tryGetContext('ezhuthu:agentRuntimeArn') as string | undefined) || undefined;
  const codeDir = opts.agentCodeDir ?? path.join(REPO_ROOT, 'infra', 'agentcore', 'build');
  if (!externalRuntimeArn) assertAgentBundle(codeDir);
  const deciderSecretArn = opts.deciderSecretArn ?? secretArnFromContext(app.node.tryGetContext('ezhuthu:deciderSecretArn'));
  const tags = { track: 'education' }; // Project=ezhuthu comes from the cost tags below (tag keys are case-insensitive in IAM)

  const budgetEmail =
    (app.node.tryGetContext('ezhuthu:budgetEmail') as string | undefined) || process.env.EZHUTHU_BUDGET_EMAIL || undefined;
  const data = new EzhuthuDataStack(app, 'EzhuthuData', { env, tags, budgetEmail });
  const domainPrefix =
    (app.node.tryGetContext('ezhuthu:cognitoDomainPrefix') as string | undefined) || `ezhuthu-${env.account ?? 'dev'}`;
  const auth = new EzhuthuAuthStack(app, 'EzhuthuAuth', { env, tags, webUrl, domainPrefix });
  const agent = externalRuntimeArn
    ? undefined
    : new EzhuthuAgentStack(app, 'EzhuthuAgent', { env, tags, table: data.table, models, codeDir, deciderSecretArn });
  const api = new EzhuthuApiStack(app, 'EzhuthuApi', {
    env,
    tags,
    table: data.table,
    runtimeArn: externalRuntimeArn ?? agent!.runtimeArn,
    userPool: auth.userPool,
    userPoolClient: auth.client,
    webUrl,
  });
  const web = new EzhuthuWebStack(app, 'EzhuthuWeb', {
    env,
    tags,
    apiId: api.api.apiId,
    webDist: opts.webDist ?? path.join(REPO_ROOT, 'app', 'web', 'dist'),
    runtimeConfig: { cognitoDomain: auth.domain.baseUrl(), cognitoClientId: auth.client.userPoolClientId },
  });
  // Cost allocation tags on every stack and resource.
  const costTags: Record<string, string> = { Project: 'ezhuthu', Owner: 'vivekraja', Env: 'hackathon', CostCenter: 'hero-credits' };
  for (const [k, v] of Object.entries(costTags)) cdk.Tags.of(app).add(k, v);
  return { data, auth, agent, api, web };
}
