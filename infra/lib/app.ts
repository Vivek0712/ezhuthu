import { existsSync } from 'node:fs';
import * as path from 'node:path';
import * as cdk from 'aws-cdk-lib';
import { EzhuthuAgentStack } from './agent-stack';
import { EzhuthuApiStack } from './api-stack';
import { EzhuthuAuthStack } from './auth-stack';
import { loadModelsConfig, REPO_ROOT } from './config';
import { EzhuthuDataStack } from './data-stack';
import { EzhuthuWebStack } from './web-stack';

export interface BuildOptions {
  agentCodeDir?: string;
  webDist?: string;
}

export function buildApp(app: cdk.App, opts: BuildOptions = {}) {
  const models = loadModelsConfig();
  const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: models.region };
  const webUrl = (app.node.tryGetContext('ezhuthu:webUrl') as string | undefined) || undefined;
  // Set when the runtime is managed outside CDK (AgentCore CLI / starter toolkit); the Agent stack is then skipped.
  const externalRuntimeArn = (app.node.tryGetContext('ezhuthu:agentRuntimeArn') as string | undefined) || undefined;
  const codeDir = opts.agentCodeDir ?? path.join(REPO_ROOT, 'infra', 'agentcore', 'build');
  if (!externalRuntimeArn && !existsSync(path.join(codeDir, 'agent_runtime.py')))
    throw new Error(`AgentCore code bundle missing at ${codeDir}. Run \`npm run package:agent\` in infra/ first.`);
  const tags = { project: 'ezhuthu', track: 'education' };

  const data = new EzhuthuDataStack(app, 'EzhuthuData', { env, tags });
  const domainPrefix =
    (app.node.tryGetContext('ezhuthu:cognitoDomainPrefix') as string | undefined) || `ezhuthu-${env.account ?? 'dev'}`;
  const auth = new EzhuthuAuthStack(app, 'EzhuthuAuth', { env, tags, webUrl, domainPrefix });
  const agent = externalRuntimeArn
    ? undefined
    : new EzhuthuAgentStack(app, 'EzhuthuAgent', { env, tags, table: data.table, models, codeDir });
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
  return { data, auth, agent, api, web };
}
