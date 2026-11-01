import * as path from 'node:path';
import * as cdk from 'aws-cdk-lib';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import { HttpJwtAuthorizer } from 'aws-cdk-lib/aws-apigatewayv2-authorizers';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { NodejsFunction, OutputFormat } from 'aws-cdk-lib/aws-lambda-nodejs';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { ROUTES } from '../lambda/proxy/routes';

export interface EzhuthuApiStackProps extends cdk.StackProps {
  table: dynamodb.ITableV2;
  runtimeArn: string;
  userPool: cognito.IUserPool;
  userPoolClient: cognito.IUserPoolClient;
  webUrl?: string;
}

/** Throttling (requests/second, burst) for the public, unauthenticated routes. */
export const THROTTLE = {
  default: { rate: 20, burst: 40 },
  'POST /api/restore': { rate: 5, burst: 10 },
  'POST /api/corrections': { rate: 2, burst: 5 },
  'POST /api/evaluate': { rate: 1, burst: 2 },
} as const;

/**
 * /api/* : API Gateway HTTP API -> one Lambda proxy -> AgentCore Runtime (tutor/restore/evaluate)
 * or DynamoDB (corrections, review queue). No Lambda Function URLs (blocked on this account).
 */
export class EzhuthuApiStack extends cdk.Stack {
  public readonly api: apigw.HttpApi;

  constructor(scope: Construct, id: string, props: EzhuthuApiStackProps) {
    super(scope, id, props);

    const fn = new NodejsFunction(this, 'Proxy', {
      entry: path.join(__dirname, '..', 'lambda', 'proxy', 'index.ts'),
      handler: 'handler',
      runtime: lambda.Runtime.NODEJS_22_X,
      architecture: lambda.Architecture.ARM_64,
      memorySize: 512,
      // HTTP API integrations time out at 30 s, so the proxy (and its AgentCore call) must finish first.
      timeout: cdk.Duration.seconds(29),
      environment: {
        AGENT_RUNTIME_ARN: props.runtimeArn,
        AGENT_QUALIFIER: 'DEFAULT',
        TABLE_NAME: props.table.tableName,
        NODE_OPTIONS: '--enable-source-maps',
      },
      bundling: { minify: true, sourceMap: true, format: OutputFormat.CJS, target: 'node22', externalModules: [] },
      logGroup: new logs.LogGroup(this, 'ProxyLogs', { retention: logs.RetentionDays.ONE_MONTH, removalPolicy: cdk.RemovalPolicy.DESTROY }),
    });
    props.table.grantReadWriteData(fn);
    fn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: 'InvokeAgentRuntime',
        actions: ['bedrock-agentcore:InvokeAgentRuntime'],
        resources: [props.runtimeArn, `${props.runtimeArn}/*`],
      }),
    );

    const origins = ['http://localhost:5173', ...(props.webUrl ? [props.webUrl.replace(/\/$/, '')] : [])];
    this.api = new apigw.HttpApi(this, 'HttpApi', {
      apiName: 'ezhuthu-api',
      description: 'Ezhuthu tutor and restoration API (contracts/restore-api.md)',
      corsPreflight: {
        allowOrigins: origins,
        allowMethods: [apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.OPTIONS],
        allowHeaders: ['authorization', 'content-type'],
        maxAge: cdk.Duration.hours(1),
      },
    });

    const authorizer = new HttpJwtAuthorizer('Cognito', `https://cognito-idp.${this.region}.amazonaws.com/${props.userPool.userPoolId}`, {
      jwtAudience: [props.userPoolClient.userPoolClientId],
      identitySource: ['$request.header.Authorization'],
    });
    const integration = new HttpLambdaIntegration('ProxyIntegration', fn, {
      payloadFormatVersion: apigw.PayloadFormatVersion.VERSION_2_0,
    });
    for (const r of ROUTES) {
      this.api.addRoutes({
        path: r.path,
        methods: [r.method === 'GET' ? apigw.HttpMethod.GET : apigw.HttpMethod.POST],
        integration,
        ...(r.access === 'public' ? {} : { authorizer }),
      });
    }

    const stage = this.api.defaultStage!.node.defaultChild as apigw.CfnStage;
    stage.defaultRouteSettings = { throttlingRateLimit: THROTTLE.default.rate, throttlingBurstLimit: THROTTLE.default.burst };
    // RouteSettings is a raw JSON map in CloudFormation: CDK does not PascalCase its values, so write them as-is.
    stage.routeSettings = Object.fromEntries(
      Object.entries(THROTTLE)
        .filter(([k]) => k !== 'default')
        .map(([k, v]) => [k, { ThrottlingRateLimit: v.rate, ThrottlingBurstLimit: v.burst }]),
    );
    const accessLogs = new logs.LogGroup(this, 'AccessLogs', { retention: logs.RetentionDays.ONE_MONTH, removalPolicy: cdk.RemovalPolicy.DESTROY });
    stage.accessLogSettings = {
      destinationArn: accessLogs.logGroupArn,
      format: JSON.stringify({
        requestId: '$context.requestId',
        route: '$context.routeKey',
        status: '$context.status',
        latency: '$context.responseLatency',
        integrationError: '$context.integrationErrorMessage',
      }),
    };

    new cdk.CfnOutput(this, 'ApiEndpoint', { value: this.api.apiEndpoint });
  }
}
