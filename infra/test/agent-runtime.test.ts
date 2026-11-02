import { cpSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import * as path from 'node:path';
import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { describe, expect, it } from 'vitest';
import { AGENT_KEY_PREFIXES } from '../lib/agent-stack';
import { buildApp, secretArnFromContext } from '../lib/app';
import { assertAgentBundle, missingBundleFiles, REQUIRED_BUNDLE_FILES } from '../lib/bundle';
import { DECIDER_SECRET_NAME, lookupDeciderSecretArn } from '../lib/decider-secret';

const FIXTURE = path.join(__dirname, 'fixtures', 'agent-code');
const SECRET_ARN = 'arn:aws:secretsmanager:us-east-1:111122223333:secret:ezhuthu/decider-api-key-AbCdEf';

type Stmt = { Sid?: string; Action: string | string[]; Resource: unknown; Condition?: Record<string, Record<string, unknown>> };

function synth(opts: { deciderSecretArn?: string; context?: Record<string, string> } = {}) {
  const app = new cdk.App({ context: { '@aws-cdk/core:defaultCrossStackReferences': 'strong', ...(opts.context ?? {}) } });
  const s = buildApp(app, { agentCodeDir: FIXTURE, webDist: path.join(__dirname, 'fixtures', 'no-dist'), deciderSecretArn: opts.deciderSecretArn });
  const agent = Template.fromStack(s.agent!);
  const stmts = Object.values(agent.findResources('AWS::IAM::Policy')).flatMap(
    (p) => (p as { Properties: { PolicyDocument: { Statement: Stmt[] } } }).Properties.PolicyDocument.Statement,
  );
  const env = (Object.values(agent.findResources('AWS::BedrockAgentCore::Runtime'))[0] as {
    Properties: { EnvironmentVariables: Record<string, unknown> };
  }).Properties.EnvironmentVariables;
  return { s, agent, stmts, env, data: Template.fromStack(s.data) };
}
const actions = (st: Stmt) => (Array.isArray(st.Action) ? st.Action : [st.Action]);

describe('agent runtime: DynamoDB sessions', () => {
  const { stmts, env } = synth();

  it('persists tutor sessions in the shared table', () => {
    expect(env.EZHUTHU_STORE).toBe('dynamodb');
    expect(env.EZHUTHU_TABLE).toBeDefined(); // DynamoStore reads the table name from EZHUTHU_TABLE
  });

  it('grants only GetItem/PutItem on the agent-owned key prefixes and Query on gsi1', () => {
    const dynamo = stmts.filter((st) => actions(st).some((a) => a.startsWith('dynamodb:')));
    const all = dynamo.flatMap(actions).sort();
    expect(all).toEqual(['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:Query']);
    for (const banned of ['dynamodb:Scan', 'dynamodb:DeleteItem', 'dynamodb:UpdateItem', 'dynamodb:BatchWriteItem', 'dynamodb:*'])
      expect(all).not.toContain(banned);

    const items = dynamo.find((st) => st.Sid === 'TableItemsOwnKeys')!;
    expect(items.Condition).toEqual({ 'ForAllValues:StringLike': { 'dynamodb:LeadingKeys': [...AGENT_KEY_PREFIXES] } });
    expect(JSON.stringify(items.Resource)).not.toContain('/index/');

    const query = dynamo.find((st) => st.Sid === 'QueueIndexQuery')!;
    expect(actions(query)).toEqual(['dynamodb:Query']);
    expect(JSON.stringify(query.Resource)).toContain('/index/gsi1');
  });

  it('matches the table layout the store expects (pk + sk, gsi1, ttl)', () => {
    synth().data.hasResourceProperties('AWS::DynamoDB::GlobalTable', {
      KeySchema: [
        { AttributeName: 'pk', KeyType: 'HASH' },
        { AttributeName: 'sk', KeyType: 'RANGE' },
      ],
      TimeToLiveSpecification: { AttributeName: 'ttl', Enabled: true },
      GlobalSecondaryIndexes: [
        Match.objectLike({
          IndexName: 'gsi1',
          KeySchema: [
            { AttributeName: 'gsi1pk', KeyType: 'HASH' },
            { AttributeName: 'gsi1sk', KeyType: 'RANGE' },
          ],
        }),
      ],
    });
  });
});

describe('agent runtime: ontology over MCP', () => {
  it('runs the bundled MCP ontology server', () => {
    expect(synth().env.EZHUTHU_ONTOLOGY).toBe('mcp');
  });

  it('accepts a bundle with the MCP server, the mcp SDK and the ontology data', () => {
    expect(missingBundleFiles(FIXTURE)).toEqual([]);
    expect(REQUIRED_BUNDLE_FILES).toContain('ezhuthu/ontology/mcp_server.py');
    expect(REQUIRED_BUNDLE_FILES).toContain('mcp/client/stdio.py');
  });

  it('refuses to synthesise from a bundle that cannot start the MCP server', () => {
    const dir = mkdtempSync(path.join(tmpdir(), 'ezhuthu-bundle-'));
    try {
      cpSync(FIXTURE, dir, { recursive: true });
      rmSync(path.join(dir, 'mcp'), { recursive: true });
      rmSync(path.join(dir, 'ontology', 'lookups'), { recursive: true });
      expect(missingBundleFiles(dir)).toEqual(['mcp/__init__.py', 'mcp/client/stdio.py', 'mcp/server/stdio.py', 'ontology/lookups/*.json']);
      expect(() => assertAgentBundle(dir)).toThrow(/ontology MCP server; missing: mcp\/__init__.py/);
      const app = new cdk.App();
      expect(() => buildApp(app, { agentCodeDir: dir, webDist: dir })).toThrow(/missing: mcp/);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('agent runtime: decider backend', () => {
  it('uses the labelled fallback and no Secrets Manager access when the key secret does not exist', () => {
    const { env, stmts, agent } = synth();
    expect(env.EZHUTHU_DECIDER_BACKEND).toBe('fallback');
    expect(env).not.toHaveProperty('EZHUTHU_DECIDER'); // "off" would override the backend switch
    expect(JSON.stringify(stmts)).not.toContain('secretsmanager');
    agent.hasOutput('DeciderBackend', { Value: Match.stringLikeRegexp('^fallback') });
  });

  it('uses the hosted decider and reads only that secret when it exists', () => {
    const { env, stmts, agent } = synth({ deciderSecretArn: SECRET_ARN });
    expect(env.EZHUTHU_DECIDER_BACKEND).toBe('hosted');
    const sm = stmts.filter((st) => actions(st).some((a) => a.startsWith('secretsmanager:')));
    expect(sm).toHaveLength(1);
    expect(actions(sm[0]!)).toEqual(['secretsmanager:GetSecretValue']);
    expect(sm[0]!.Resource).toBe(SECRET_ARN);
    agent.hasOutput('DeciderBackend', { Value: Match.stringLikeRegexp('^hosted') });
  });

  it('leaves the restorer configuration to the bundled config/models.yaml and calibration.json on both paths', () => {
    // The deployed restorer config and its calibration are chosen on VAL (eval/reports/2026-11-02-deployed-config.md);
    // an env override here would silently run something else (tests/agent/test_runtime_restorer_config.py).
    for (const { env } of [synth(), synth({ deciderSecretArn: SECRET_ARN })]) {
      expect(env).not.toHaveProperty('EZHUTHU_RESTORER_STRATEGY');
      expect(env).not.toHaveProperty('EZHUTHU_CALIBRATION');
      expect(env).not.toHaveProperty('EZHUTHU_CONFIG');
    }
  });

  it('reads the secret ARN from context, and treats anything else as "no secret"', () => {
    expect(synth({ context: { 'ezhuthu:deciderSecretArn': SECRET_ARN } }).env.EZHUTHU_DECIDER_BACKEND).toBe('hosted');
    expect(synth({ context: { 'ezhuthu:deciderSecretArn': 'none' } }).env.EZHUTHU_DECIDER_BACKEND).toBe('fallback');
    expect(secretArnFromContext('')).toBeUndefined();
    expect(secretArnFromContext(SECRET_ARN)).toBe(SECRET_ARN);
  });

  it('looks the secret up read-only; only a missing or deleted secret means fallback', () => {
    const calls: string[][] = [];
    const found = lookupDeciderSecretArn('heisenberg', 'us-east-1', (cmd, args) => {
      calls.push([cmd, ...args]);
      return JSON.stringify({ ARN: SECRET_ARN, Name: DECIDER_SECRET_NAME });
    });
    expect(found).toBe(SECRET_ARN);
    expect(calls[0]!.slice(0, 5)).toEqual(['aws', 'secretsmanager', 'describe-secret', '--secret-id', DECIDER_SECRET_NAME]);
    expect(calls[0]).toContain('heisenberg');
    const missing = lookupDeciderSecretArn('heisenberg', 'us-east-1', () => {
      throw new Error('An error occurred (ResourceNotFoundException) when calling the DescribeSecret operation');
    });
    expect(missing).toBeUndefined();
    expect(lookupDeciderSecretArn('p', 'r', () => JSON.stringify({ ARN: SECRET_ARN, DeletedDate: '2026-11-01' }))).toBeUndefined();
    // execFileSync puts the CLI's message on err.stderr; that alone must also count as "not found".
    expect(lookupDeciderSecretArn('p', 'r', () => {
      throw Object.assign(new Error('Command failed: aws secretsmanager describe-secret'), {
        stderr: 'An error occurred (ResourceNotFoundException) when calling the DescribeSecret operation: not found',
      });
    })).toBeUndefined();
  });

  it('throws (with the override hint) on any other lookup failure instead of silently synthesising the fallback', () => {
    const failures: Array<() => string> = [
      () => { throw Object.assign(new Error('spawnSync aws ENOENT'), { code: 'ENOENT' }); },
      () => { throw Object.assign(new Error('spawnSync aws ETIMEDOUT'), { code: 'ETIMEDOUT' }); },
      () => { throw Object.assign(new Error('Command failed'), { stderr: 'An error occurred (ThrottlingException) when calling the DescribeSecret operation: Rate exceeded' }); },
      () => { throw Object.assign(new Error('Command failed'), { stderr: 'The config profile (heisenberg) could not be found' }); },
      () => { throw Object.assign(new Error('Command failed'), { stderr: 'An error occurred (AccessDeniedException) when calling the DescribeSecret operation' }); },
      () => 'not json',
      () => JSON.stringify({ Name: DECIDER_SECRET_NAME }),
    ];
    for (const run of failures) {
      expect(() => lookupDeciderSecretArn('heisenberg', 'us-east-1', run)).toThrow(/ezhuthu:deciderSecretArn=<arn>.*ezhuthu:deciderSecretArn=none/);
    }
    expect(() => lookupDeciderSecretArn('heisenberg', 'us-east-1', failures[2]!)).toThrow(/ThrottlingException/);
  });
});

describe('agent runtime: logs, tags, budget', () => {
  const { agent, data, s } = synth();

  it('keeps runtime logs for 14 days', () => {
    agent.hasResourceProperties('Custom::LogRetention', {
      RetentionInDays: 14,
      LogGroupName: Match.objectLike({ 'Fn::Join': Match.arrayWith([Match.arrayWith(['/aws/bedrock-agentcore/runtimes/'])]) }),
    });
  });

  it('gives the LogRetention helper a scoped role, not logs:* on "*"', () => {
    const fns = agent.findResources('AWS::Lambda::Function');
    const helper = Object.entries(fns).find(([id]) => id.startsWith('LogRetention'));
    expect(helper).toBeDefined();
    const roleRef = (helper![1] as { Properties: { Role: { 'Fn::GetAtt': [string, string] } } }).Properties.Role['Fn::GetAtt'][0];
    const roles = agent.findResources('AWS::IAM::Role');
    const role = roles[roleRef] as { Properties: { ManagedPolicyArns?: unknown; Policies: Array<{ PolicyDocument: { Statement: Array<{ Action: string[]; Resource: unknown[] }> } }> } };
    expect(role.Properties.ManagedPolicyArns).toBeUndefined();
    const stmts = role.Properties.Policies.flatMap((p) => p.PolicyDocument.Statement);
    for (const st of stmts) {
      expect(st.Resource).not.toContain('*');
      const text = JSON.stringify(st.Resource);
      expect(text.includes('/aws/bedrock-agentcore/runtimes/') || text.includes('/aws/lambda/EzhuthuAgent*-LogRetention*')).toBe(true);
    }
    expect(stmts.flatMap((st) => st.Action).sort()).toEqual(
      ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:DeleteRetentionPolicy', 'logs:PutLogEvents', 'logs:PutRetentionPolicy'],
    );
    // No separate IAM::Policy may widen the helper's role (LogRetentionFunction's default '*' statement).
    for (const pol of Object.values(agent.findResources('AWS::IAM::Policy'))) {
      expect(JSON.stringify((pol as { Properties: { Roles: unknown } }).Properties.Roles)).not.toContain(roleRef);
    }
  });

  it('keeps every log group in every stack at 14 days', () => {
    for (const stack of [s.data, s.auth, s.agent!, s.api, s.web]) {
      const groups = Template.fromStack(stack).findResources('AWS::Logs::LogGroup');
      for (const g of Object.values(groups)) expect((g as { Properties: { RetentionInDays?: number } }).Properties.RetentionInDays).toBe(14);
    }
  });

  it('tags the runtime and its role with the cost tags', () => {
    const tags = { Project: 'ezhuthu', Owner: 'vivekraja', Env: 'hackathon', CostCenter: 'hero-credits' };
    agent.hasResourceProperties('AWS::BedrockAgentCore::Runtime', { Tags: Match.objectLike(tags) });
    for (const [Key, Value] of Object.entries(tags))
      agent.hasResourceProperties('AWS::IAM::Role', { Tags: Match.arrayWith([{ Key, Value }]) });
  });

  it('leaves the USD 50 monthly budget unchanged', () => {
    data.hasResourceProperties('AWS::Budgets::Budget', {
      Budget: Match.objectLike({ BudgetName: 'ezhuthu-monthly', BudgetLimit: { Amount: 50, Unit: 'USD' } }),
    });
  });

  it('emails the budget alert only to the address given at deploy time', () => {
    const withEmail = synth({ context: { 'ezhuthu:budgetEmail': 'alerts@example.org' } }).data;
    withEmail.hasResourceProperties('AWS::Budgets::Budget', {
      NotificationsWithSubscribers: [Match.objectLike({ Subscribers: [{ SubscriptionType: 'EMAIL', Address: 'alerts@example.org' }] })],
    });
    const prev = process.env.EZHUTHU_BUDGET_EMAIL;
    delete process.env.EZHUTHU_BUDGET_EMAIL;
    try {
      const none = synth().data;
      none.hasResourceProperties('AWS::Budgets::Budget', { NotificationsWithSubscribers: Match.absent() });
    } finally {
      if (prev !== undefined) process.env.EZHUTHU_BUDGET_EMAIL = prev;
    }
  });
});
