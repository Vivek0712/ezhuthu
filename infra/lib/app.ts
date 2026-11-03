import * as path from 'node:path';
import * as cdk from 'aws-cdk-lib';
import { EzhuthuAgentStack } from './agent-stack';
import { EzhuthuApiStack } from './api-stack';
import { EzhuthuAuthStack } from './auth-stack';
import { assertAgentBundle } from './bundle';
import { loadModelsConfig, REPO_ROOT } from './config';
import { EzhuthuDataStack } from './data-stack';
import { webOrigins } from './web-origins';
import { EzhuthuWebStack, type WebCustomDomain } from './web-stack';

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

function ctxString(app: cdk.App, key: string): string | undefined {
  const v = app.node.tryGetContext(key) as unknown;
  return typeof v === 'string' && v.trim() ? v.trim() : undefined;
}

/**
 * Optional custom domain from context: `ezhuthu:domainName`, `ezhuthu:hostedZoneId`, `ezhuthu:hostedZoneName`.
 * All three or none; a partial set fails the synth rather than silently dropping the domain.
 */
export function customDomainFromContext(app: cdk.App): WebCustomDomain | undefined {
  const domainName = ctxString(app, 'ezhuthu:domainName');
  const hostedZoneId = ctxString(app, 'ezhuthu:hostedZoneId');
  const hostedZoneName = ctxString(app, 'ezhuthu:hostedZoneName');
  if (!domainName && !hostedZoneId && !hostedZoneName) return undefined;
  if (!domainName || !hostedZoneId || !hostedZoneName) {
    throw new Error('ezhuthu:domainName, ezhuthu:hostedZoneId and ezhuthu:hostedZoneName must be set together');
  }
  const zone = hostedZoneName.replace(/\.$/, '');
  if (domainName !== zone && !domainName.endsWith(`.${zone}`)) {
    throw new Error(`ezhuthu:domainName ${domainName} is not inside hosted zone ${zone}`);
  }
  return { domainName, hostedZoneId, hostedZoneName: zone };
}

/**
 * Every public web origin: `ezhuthu:webUrl` (the CloudFront URL), any `ezhuthu:webUrls` (array or comma-separated
 * string) and `https://<ezhuthu:domainName>`. Cognito and API CORS allow all of them.
 */
export function webUrlsFromContext(app: cdk.App, custom?: WebCustomDomain): string[] {
  const raw = app.node.tryGetContext('ezhuthu:webUrls') as unknown;
  const extra = Array.isArray(raw) ? raw.map(String) : typeof raw === 'string' ? raw.split(',') : [];
  return webOrigins(ctxString(app, 'ezhuthu:webUrl'), [...extra, ...(custom ? [`https://${custom.domainName}`] : [])]);
}

export function buildApp(app: cdk.App, opts: BuildOptions = {}) {
  const models = loadModelsConfig();
  const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: models.region };
  const customDomain = customDomainFromContext(app);
  const webUrls = webUrlsFromContext(app, customDomain);
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
  const auth = new EzhuthuAuthStack(app, 'EzhuthuAuth', { env, tags, webUrls, domainPrefix });
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
    webUrls,
  });
  const web = new EzhuthuWebStack(app, 'EzhuthuWeb', {
    env,
    tags,
    apiId: api.api.apiId,
    webDist: opts.webDist ?? path.join(REPO_ROOT, 'app', 'web', 'dist'),
    runtimeConfig: { cognitoDomain: auth.domain.baseUrl(), cognitoClientId: auth.client.userPoolClientId },
    customDomain,
  });
  // Cost allocation tags on every stack and resource.
  const costTags: Record<string, string> = { Project: 'ezhuthu', Owner: 'vivekraja', Env: 'hackathon', CostCenter: 'hero-credits' };
  for (const [k, v] of Object.entries(costTags)) cdk.Tags.of(app).add(k, v);
  return { data, auth, agent, api, web };
}
