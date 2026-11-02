import * as cdk from 'aws-cdk-lib';
import * as agentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3assets from 'aws-cdk-lib/aws-s3-assets';
import { Construct } from 'constructs';
import { bedrockResourceArns, type ModelsConfig } from './config';

export interface EzhuthuAgentStackProps extends cdk.StackProps {
  table: dynamodb.ITableV2;
  models: ModelsConfig;
  /** Directory produced by agentcore/package.sh (CDK zips it into an S3 asset). */
  codeDir: string;
  /**
   * Full ARN of the Secrets Manager secret holding the hosted Strands Decider key (config/models.yaml
   * decider.cloud.secret_name). Set only when that secret exists; without it the runtime uses the labelled
   * fallback decider (decider_source "fallback" / "rules") and is granted no Secrets Manager access at all.
   */
  deciderSecretArn?: string;
}

/** DynamoDB key prefixes the agent's DynamoStore writes (src/ezhuthu/api/storage.py); the proxy owns SESSION#<id>/META. */
export const AGENT_KEY_PREFIXES = ['SESSION#*', 'CORRECTION#*', 'QUEUE#*', 'READTOKEN#*'] as const;

/** How the runtime's decider is configured; exported for tests and the stack output. */
export function deciderEnv(secretArn: string | undefined): { backend: 'hosted' | 'fallback'; label: string } {
  return secretArn
    ? { backend: 'hosted', label: 'hosted (Secrets Manager ezhuthu/decider-api-key)' }
    : { backend: 'fallback', label: 'fallback (no ezhuthu/decider-api-key secret; decider_source=fallback/rules)' };
}

/**
 * Amazon Bedrock AgentCore Runtime hosting the Strands agent graph (Restorer, Lesson Builder, Tutor,
 * Assessor) via Direct Code Deploy: a Python 3.12 zip on S3, entry point agent_runtime.py.
 */
export class EzhuthuAgentStack extends cdk.Stack {
  public readonly runtimeArn: string;
  public readonly runtime: agentcore.CfnRuntime;

  constructor(scope: Construct, id: string, props: EzhuthuAgentStackProps) {
    super(scope, id, props);

    const code = new s3assets.Asset(this, 'AgentCode', { path: props.codeDir });

    const role = new iam.Role(this, 'RuntimeRole', {
      description: 'Execution role for the Ezhuthu Strands agents on Bedrock AgentCore Runtime',
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com', {
        conditions: {
          StringEquals: { 'aws:SourceAccount': this.account },
          ArnLike: { 'aws:SourceArn': `arn:${this.partition}:bedrock-agentcore:${this.region}:${this.account}:*` },
        },
      }),
    });
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'InvokeConfiguredModels',
        // The Converse APIs are authorized by these two actions.
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: props.models.activeModelIds.flatMap((m) => bedrockResourceArns(m, this.partition, this.account)),
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'Logs',
        actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents', 'logs:DescribeLogStreams', 'logs:DescribeLogGroups'],
        resources: [`arn:${this.partition}:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*`],
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'Observability',
        actions: ['xray:PutTraceSegments', 'xray:PutTelemetryRecords', 'xray:GetSamplingRules', 'xray:GetSamplingTargets', 'cloudwatch:PutMetricData'],
        resources: ['*'], // these actions do not support resource-level permissions
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'WorkloadIdentity',
        actions: ['bedrock-agentcore:GetWorkloadAccessToken', 'bedrock-agentcore:GetWorkloadAccessTokenForJWT', 'bedrock-agentcore:GetWorkloadAccessTokenForUserId'],
        resources: [
          `arn:${this.partition}:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
          `arn:${this.partition}:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/*`,
        ],
      }),
    );
    // Least privilege on the shared pk/sk table: the agent's DynamoStore only gets, puts (a conditional put for
    // reviews) and queries the review queue on gsi1. No Scan, Delete, Update or batch calls. LeadingKeys limits the
    // partition keys to the SESSION#, CORRECTION# and QUEUE# prefixes, but IAM cannot condition on the sort key, so
    // the role can also write the proxy-owned SESSION#<id>/META item; the agent code (sk=STATE) leaves it alone.
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'TableItemsOwnKeys',
        actions: ['dynamodb:GetItem', 'dynamodb:PutItem'],
        resources: [props.table.tableArn],
        conditions: { 'ForAllValues:StringLike': { 'dynamodb:LeadingKeys': [...AGENT_KEY_PREFIXES] } },
      }),
    );
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'QueueIndexQuery',
        actions: ['dynamodb:Query'],
        resources: [`${props.table.tableArn}/index/gsi1`],
      }),
    );
    code.grantRead(role);

    const decider = deciderEnv(props.deciderSecretArn);
    if (props.deciderSecretArn) {
      role.addToPolicy(
        new iam.PolicyStatement({
          sid: 'ReadDeciderKey',
          actions: ['secretsmanager:GetSecretValue'],
          resources: [props.deciderSecretArn],
        }),
      );
    }

    this.runtime = new agentcore.CfnRuntime(this, 'Runtime', {
      agentRuntimeName: 'ezhuthu_tutor',
      description: 'Ezhuthu tutor and restoration agents, built with Strands Agents',
      roleArn: role.roleArn,
      agentRuntimeArtifact: {
        codeConfiguration: {
          code: { s3: { bucket: code.s3BucketName, prefix: code.s3ObjectKey } },
          entryPoint: ['agent_runtime.py'],
          runtime: 'PYTHON_3_12',
        },
      },
      networkConfiguration: { networkMode: 'PUBLIC' },
      protocolConfiguration: 'HTTP',
      lifecycleConfiguration: { idleRuntimeSessionTimeout: 900, maxLifetime: 28800 },
      environmentVariables: {
        EZHUTHU_TABLE: props.table.tableName,
        EZHUTHU_MODELS_FILE: 'config/models.yaml',
        EZHUTHU_MODEL_DEFAULT: props.models.llm.default!,
        EZHUTHU_MODEL_ESCALATE: props.models.llm.escalate!,
        EZHUTHU_MODEL_CHEAP: props.models.llm.cheap ?? props.models.llm.default!,
        EZHUTHU_LIVE: '1',
        EZHUTHU_CACHE_DIR: '/tmp/ezhuthu-cache', // the bundle directory is read-only
        // Tutor sessions (SESSION#<id>/STATE), corrections and the review queue persist in the shared table
        // (EZHUTHU_TABLE), so a recycled microVM does not lose a learner's progress.
        EZHUTHU_STORE: 'dynamodb',
        // The ontology is served by the bundled MCP server (stdio child process); a failed start is reported as
        // "fallback:direct (mcp unavailable)" in /health.
        EZHUTHU_ONTOLOGY: 'mcp',
        EZHUTHU_DECIDER_BACKEND: decider.backend,
      },
    });
    this.runtime.node.addDependency(role);
    this.runtimeArn = this.runtime.attrAgentRuntimeArn;

    // AgentCore creates the runtime's log group itself (/aws/bedrock-agentcore/runtimes/<id>-DEFAULT), so set
    // its retention with a LogRetention custom resource instead of owning the group (which would clash on deploy).
    const runtimeLogGroup = `/aws/bedrock-agentcore/runtimes/${this.runtime.attrAgentRuntimeId}-DEFAULT`;
    new logs.LogRetention(this, 'RuntimeLogRetention', {
      logGroupName: runtimeLogGroup,
      retention: logs.RetentionDays.TWO_WEEKS,
      role: logRetentionRole(this, runtimeLogGroup),
    });

    new cdk.CfnOutput(this, 'AgentRuntimeArn', { value: this.runtimeArn });
    new cdk.CfnOutput(this, 'AgentRuntimeRoleArn', { value: role.roleArn });
    new cdk.CfnOutput(this, 'DeciderBackend', { value: decider.label });
  }
}

/**
 * A least-privilege role for CDK's LogRetention helper Lambda. The default role carries AWSLambdaBasicExecutionRole
 * and logs:PutRetentionPolicy/DeleteRetentionPolicy on '*'. On Create the handler creates the target group if needed
 * and sets its retention, then does the same for its own /aws/lambda/<fn> group (1 day), and it writes its own logs.
 * So this role allows exactly that: the runtime log group, and the helper's own group, whose CloudFormation-generated
 * name is "<stack name, truncated>-LogRetention<hash>-<suffix>". The role is immutable, so LogRetentionFunction
 * cannot add its '*' statement to it.
 */
export function logRetentionRole(stack: cdk.Stack, targetLogGroup: string): iam.IRole {
  const groupArn = (name: string) => `arn:${stack.partition}:logs:${stack.region}:${stack.account}:log-group:${name}`;
  const helperGroup = `/aws/lambda/${stack.stackName.slice(0, 20)}*-LogRetention*`;
  const groups = [targetLogGroup, helperGroup].flatMap((g) => [groupArn(g), `${groupArn(g)}:*`]);
  const role = new iam.Role(stack, 'LogRetentionRole', {
    assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
    description: 'CDK LogRetention helper: sets retention on the AgentCore runtime log group and its own log group only',
    inlinePolicies: {
      LogRetention: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            sid: 'SetRetention',
            actions: ['logs:CreateLogGroup', 'logs:PutRetentionPolicy', 'logs:DeleteRetentionPolicy'],
            resources: groups,
          }),
          new iam.PolicyStatement({
            sid: 'OwnLogs',
            actions: ['logs:CreateLogStream', 'logs:PutLogEvents'],
            resources: [`${groupArn(helperGroup)}:*`],
          }),
        ],
      }),
    },
  });
  return role.withoutPolicyUpdates();
}
