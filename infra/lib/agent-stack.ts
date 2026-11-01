import * as cdk from 'aws-cdk-lib';
import * as agentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3assets from 'aws-cdk-lib/aws-s3-assets';
import { Construct } from 'constructs';
import { bedrockResourceArns, type ModelsConfig } from './config';

export interface EzhuthuAgentStackProps extends cdk.StackProps {
  table: dynamodb.ITableV2;
  models: ModelsConfig;
  /** Directory produced by agentcore/package.sh (CDK zips it into an S3 asset). */
  codeDir: string;
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
    props.table.grantReadWriteData(role);
    code.grantRead(role);

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
        // The tutor's DynamoStore expects a pk-only table with a kind-index GSI; the shared table is pk+sk/gsi1,
        // so tutor sessions live in the microVM (one AgentCore session per learner keeps them warm).
        EZHUTHU_STORE: 'memory',
        // No hosted decider yet: confidences use the flagged fallback (decider_model "fallback:...").
        EZHUTHU_DECIDER: 'off',
      },
    });
    this.runtime.node.addDependency(role);
    this.runtimeArn = this.runtime.attrAgentRuntimeArn;

    new cdk.CfnOutput(this, 'AgentRuntimeArn', { value: this.runtimeArn });
    new cdk.CfnOutput(this, 'AgentRuntimeRoleArn', { value: role.roleArn });
  }
}
