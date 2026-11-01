import * as path from 'node:path';
import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { beforeAll, describe, expect, it } from 'vitest';
import { buildApp } from '../lib/app';
import { bedrockResourceArns, loadModelsConfig } from '../lib/config';

let t: Record<'data' | 'auth' | 'agent' | 'api' | 'web', Template>;
beforeAll(() => {
  const app = new cdk.App({ context: { 'ezhuthu:webUrl': 'https://d123.cloudfront.net', '@aws-cdk/core:defaultCrossStackReferences': 'strong' } });
  const s = buildApp(app, {
    agentCodeDir: path.join(__dirname, 'fixtures', 'agent-code'),
    webDist: path.join(__dirname, 'fixtures', 'no-dist'),
  });
  t = {
    data: Template.fromStack(s.data),
    auth: Template.fromStack(s.auth),
    agent: Template.fromStack(s.agent!),
    api: Template.fromStack(s.api),
    web: Template.fromStack(s.web),
  };
});

describe('models config', () => {
  it('reads model IDs only from config/models.yaml and scopes IAM to them', () => {
    const m = loadModelsConfig();
    expect(m.region).toBe('us-east-1');
    expect(m.activeModelIds).toContain(m.llm.default);
    expect(bedrockResourceArns('us.anthropic.claude-sonnet-4-6', 'aws', '123')).toEqual([
      'arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-6',
      'arn:aws:bedrock:*:123:inference-profile/us.anthropic.claude-sonnet-4-6',
    ]);
  });
});

describe('AgentCore Runtime', () => {
  it('deploys the agent with Direct Code Deploy on Python 3.12 and model env from config', () => {
    const m = loadModelsConfig();
    t.agent.hasResourceProperties('AWS::BedrockAgentCore::Runtime', {
      AgentRuntimeName: 'ezhuthu_tutor',
      AgentRuntimeArtifact: {
        CodeConfiguration: { EntryPoint: ['agent_runtime.py'], Runtime: 'PYTHON_3_12', Code: { S3: Match.objectLike({}) } },
      },
      NetworkConfiguration: { NetworkMode: 'PUBLIC' },
      EnvironmentVariables: Match.objectLike({ EZHUTHU_MODEL_DEFAULT: m.llm.default, EZHUTHU_MODEL_ESCALATE: m.llm.escalate }),
    });
  });
  it('lets the runtime role invoke only the configured models', () => {
    const policies = t.agent.findResources('AWS::IAM::Policy');
    const stmts = Object.values(policies).flatMap((p) => (p as { Properties: { PolicyDocument: { Statement: { Sid?: string; Resource: unknown }[] } } }).Properties.PolicyDocument.Statement);
    const invoke = stmts.find((s) => s.Sid === 'InvokeConfiguredModels')!;
    const text = JSON.stringify(invoke.Resource);
    for (const id of loadModelsConfig().activeModelIds) expect(text).toContain(id);
    expect(text).not.toContain('claude-sonnet-5-5'); // future model stays out until the agreement is accepted
    expect(text).not.toMatch(/foundation-model\/\*/);
  });
});

describe('API', () => {
  it('uses an HTTP API with a Lambda proxy and never a Lambda Function URL', () => {
    t.api.resourceCountIs('AWS::ApiGatewayV2::Api', 1);
    t.api.hasResourceProperties('AWS::ApiGatewayV2::Api', { ProtocolType: 'HTTP' });
    for (const tpl of Object.values(t)) tpl.resourceCountIs('AWS::Lambda::Url', 0);
    t.api.hasResourceProperties('AWS::Lambda::Function', { Runtime: 'nodejs22.x', Timeout: 29, Architectures: ['arm64'] });
  });
  it('protects evaluate and the queue with the Cognito JWT authorizer and leaves Learn/Restore public', () => {
    const routes = Object.values(t.api.findResources('AWS::ApiGatewayV2::Route')).map(
      (r) => (r as { Properties: { RouteKey: string; AuthorizationType?: string } }).Properties,
    );
    const auth = Object.fromEntries(routes.map((r) => [r.RouteKey, r.AuthorizationType ?? 'NONE']));
    expect(auth).toMatchObject({
      'POST /api/evaluate': 'JWT',
      'GET /api/queue': 'JWT',
      'POST /api/queue/{id}': 'JWT',
      'POST /api/restore': 'NONE',
      'POST /api/lesson': 'NONE',
      'POST /api/answer': 'NONE',
      'GET /api/progress/{session_id}': 'NONE',
      'POST /api/corrections': 'NONE',
    });
    t.api.hasResourceProperties('AWS::ApiGatewayV2::Authorizer', { AuthorizerType: 'JWT' });
  });
  it('throttles the stage and the expensive public routes', () => {
    t.api.hasResourceProperties('AWS::ApiGatewayV2::Stage', {
      DefaultRouteSettings: { ThrottlingRateLimit: 20, ThrottlingBurstLimit: 40 },
      RouteSettings: Match.objectLike({ 'POST /api/restore': { ThrottlingRateLimit: 5, ThrottlingBurstLimit: 10 } }),
    });
  });
  it('grants the proxy InvokeAgentRuntime on the runtime only', () => {
    const json = JSON.stringify(t.api.findResources('AWS::IAM::Policy'));
    expect(json).toContain('bedrock-agentcore:InvokeAgentRuntime');
  });
});

describe('Cognito', () => {
  it('has an experts group and a public PKCE client with the web callback', () => {
    t.auth.hasResourceProperties('AWS::Cognito::UserPoolGroup', { GroupName: 'experts' });
    t.auth.hasResourceProperties('AWS::Cognito::UserPoolClient', {
      GenerateSecret: false,
      AllowedOAuthFlows: ['code'],
      CallbackURLs: ['http://localhost:5173/auth/callback', 'https://d123.cloudfront.net/auth/callback'],
    });
  });
});

describe('Web', () => {
  it('serves a private bucket through CloudFront with /api/* routed to the HTTP API', () => {
    t.web.hasResourceProperties('AWS::S3::Bucket', {
      PublicAccessBlockConfiguration: { BlockPublicAcls: true, BlockPublicPolicy: true, IgnorePublicAcls: true, RestrictPublicBuckets: true },
    });
    t.web.hasResourceProperties('AWS::CloudFront::Distribution', {
      DistributionConfig: Match.objectLike({
        CacheBehaviors: [Match.objectLike({ PathPattern: '/api/*', ViewerProtocolPolicy: 'https-only' })],
        DefaultCacheBehavior: Match.objectLike({ FunctionAssociations: [Match.objectLike({ EventType: 'viewer-request' })] }),
      }),
    });
    // No custom error responses: they would turn API 403/404 into index.html.
    const dist = Object.values(t.web.findResources('AWS::CloudFront::Distribution'))[0] as { Properties: { DistributionConfig: Record<string, unknown> } };
    expect(dist.Properties.DistributionConfig.CustomErrorResponses).toBeUndefined();
  });
  it('forwards Authorization to the API origin', () => {
    t.web.hasResourceProperties('AWS::CloudFront::CachePolicy', {
      CachePolicyConfig: Match.objectLike({
        ParametersInCacheKeyAndForwardedToOrigin: Match.objectLike({ HeadersConfig: { HeaderBehavior: 'whitelist', Headers: ['Authorization'] } }),
      }),
    });
  });
});

describe('DynamoDB', () => {
  it('is on-demand with TTL, PITR and the status index', () => {
    t.data.hasResourceProperties('AWS::DynamoDB::GlobalTable', {
      BillingMode: 'PAY_PER_REQUEST',
      TimeToLiveSpecification: { AttributeName: 'ttl', Enabled: true },
      GlobalSecondaryIndexes: [Match.objectLike({ IndexName: 'gsi1' })],
    });
  });
});

describe('external runtime', () => {
  it('skips the Agent stack and points the proxy at a runtime managed by the AgentCore CLI', () => {
    const arn = 'arn:aws:bedrock-agentcore:us-east-1:111122223333:runtime/ezhuthu_cli-abc';
    const app = new cdk.App({ context: { 'ezhuthu:agentRuntimeArn': arn, '@aws-cdk/core:defaultCrossStackReferences': 'strong' } });
    const s = buildApp(app, { agentCodeDir: path.join(__dirname, 'fixtures', 'missing'), webDist: path.join(__dirname, 'fixtures', 'no-dist') });
    expect(s.agent).toBeUndefined();
    Template.fromStack(s.api).hasResourceProperties('AWS::Lambda::Function', {
      Environment: { Variables: Match.objectLike({ AGENT_RUNTIME_ARN: arn }) },
    });
  });
});
