import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { Construct } from 'constructs';

export interface EzhuthuAuthStackProps extends cdk.StackProps {
  /** Public web origin (https://dxxxx.cloudfront.net). Empty on the first deploy; see infra/README.md. */
  webUrl?: string;
  /** Globally unique Cognito domain prefix. */
  domainPrefix: string;
}

/**
 * Cognito protects Test uploads (any signed-in user) and the Review queue (group "experts").
 * Learn and Restore stay public. The SPA uses authorization code + PKCE with no client secret.
 */
export class EzhuthuAuthStack extends cdk.Stack {
  public readonly userPool: cognito.UserPool;
  public readonly client: cognito.UserPoolClient;
  public readonly domain: cognito.UserPoolDomain;

  constructor(scope: Construct, id: string, props: EzhuthuAuthStackProps) {
    super(scope, id, props);

    this.userPool = new cognito.UserPool(this, 'Users', {
      userPoolName: 'ezhuthu-users',
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      standardAttributes: { email: { required: true, mutable: true } },
      passwordPolicy: { minLength: 10, requireDigits: true, requireLowercase: true, requireUppercase: false, requireSymbols: false },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      featurePlan: cognito.FeaturePlan.ESSENTIALS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    new cognito.CfnUserPoolGroup(this, 'Experts', {
      userPoolId: this.userPool.userPoolId,
      groupName: 'experts',
      description: 'Epigraphy reviewers: may read and act on the review queue',
    });

    const origins = ['http://localhost:5173', ...(props.webUrl ? [props.webUrl.replace(/\/$/, '')] : [])];
    this.client = this.userPool.addClient('WebClient', {
      userPoolClientName: 'ezhuthu-web',
      generateSecret: false,
      authFlows: { userSrp: true },
      preventUserExistenceErrors: true,
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
        callbackUrls: origins.map((o) => `${o}/auth/callback`),
        logoutUrls: origins.map((o) => `${o}/`),
      },
      supportedIdentityProviders: [cognito.UserPoolClientIdentityProvider.COGNITO],
    });

    this.domain = this.userPool.addDomain('Domain', { cognitoDomain: { domainPrefix: props.domainPrefix } });

    new cdk.CfnOutput(this, 'UserPoolId', { value: this.userPool.userPoolId });
    new cdk.CfnOutput(this, 'WebClientId', { value: this.client.userPoolClientId });
    new cdk.CfnOutput(this, 'CognitoDomain', { value: this.domain.baseUrl() });
  }
}
