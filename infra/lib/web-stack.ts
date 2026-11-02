import { existsSync } from 'node:fs';
import * as cdk from 'aws-cdk-lib';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as targets from 'aws-cdk-lib/aws-route53-targets';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import { Construct } from 'constructs';

export interface EzhuthuWebStackProps extends cdk.StackProps {
  /** HTTP API id; CloudFront serves /api/* from it so the app stays same-origin. */
  apiId: string;
  /** app/web/dist; deployed only if it exists at synth time. */
  webDist: string;
  /** Written to /config.json so the SPA needs no rebuild when Cognito values change. */
  runtimeConfig: { cognitoDomain: string; cognitoClientId: string };
  /** Optional custom domain (e.g. ezhuthu.sparrowdecider.com) served in addition to the CloudFront domain. */
  customDomain?: WebCustomDomain;
}

/** An existing Route 53 public hosted zone that holds `domainName`. The stack must be in us-east-1 (CloudFront ACM). */
export interface WebCustomDomain {
  domainName: string;
  hostedZoneId: string;
  hostedZoneName: string;
}

// Paths without a file extension are SPA routes and are served index.html. /api/* never reaches this function.
const SPA_REWRITE = `function handler(event) {
  var r = event.request;
  if (r.uri.indexOf('.') === -1) { r.uri = '/index.html'; }
  return r;
}`;

export class EzhuthuWebStack extends cdk.Stack {
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props: EzhuthuWebStackProps) {
    super(scope, id, props);

    const bucket = new s3.Bucket(this, 'Site', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const headers = new cloudfront.ResponseHeadersPolicy(this, 'Headers', {
      securityHeadersBehavior: {
        contentTypeOptions: { override: true },
        frameOptions: { frameOption: cloudfront.HeadersFrameOption.DENY, override: true },
        referrerPolicy: { referrerPolicy: cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN, override: true },
        strictTransportSecurity: { accessControlMaxAge: cdk.Duration.days(365), includeSubdomains: true, override: true },
        contentSecurityPolicy: {
          override: true,
          contentSecurityPolicy:
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; " +
            "connect-src 'self' https://*.amazoncognito.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://*.amazoncognito.com",
        },
      },
    });

    // Authorization must be part of the cache key to reach the origin on GET (/api/queue). TTL stays ~0 and the
    // API answers Cache-Control: no-store, so nothing is cached in practice.
    const apiCache = new cloudfront.CachePolicy(this, 'ApiCache', {
      comment: 'Ezhuthu /api/*: forward Authorization, effectively uncached',
      minTtl: cdk.Duration.seconds(0),
      defaultTtl: cdk.Duration.seconds(0),
      maxTtl: cdk.Duration.seconds(1),
      headerBehavior: cloudfront.CacheHeaderBehavior.allowList('Authorization'),
      queryStringBehavior: cloudfront.CacheQueryStringBehavior.all(),
      cookieBehavior: cloudfront.CacheCookieBehavior.none(),
    });

    const custom = props.customDomain;
    let zone: route53.IHostedZone | undefined;
    let certificate: acm.ICertificate | undefined;
    if (custom) {
      zone = route53.HostedZone.fromHostedZoneAttributes(this, 'Zone', {
        hostedZoneId: custom.hostedZoneId,
        zoneName: custom.hostedZoneName,
      });
      // CloudFront only accepts ACM certificates from us-east-1; this stack runs there (config/models.yaml region).
      certificate = new acm.Certificate(this, 'Cert', {
        domainName: custom.domainName,
        validation: acm.CertificateValidation.fromDns(zone),
      });
    }

    this.distribution = new cloudfront.Distribution(this, 'Cdn', {
      comment: 'Ezhuthu web app',
      ...(custom ? { domainNames: [custom.domainName], certificate } : {}),
      defaultRootObject: 'index.html',
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      priceClass: cloudfront.PriceClass.PRICE_CLASS_200, // includes India edge locations
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(bucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        responseHeadersPolicy: headers,
        compress: true,
        functionAssociations: [
          {
            eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
            function: new cloudfront.Function(this, 'SpaRewrite', {
              code: cloudfront.FunctionCode.fromInline(SPA_REWRITE),
              runtime: cloudfront.FunctionRuntime.JS_2_0,
            }),
          },
        ],
      },
      additionalBehaviors: {
        '/api/*': {
          origin: new origins.HttpOrigin(`${props.apiId}.execute-api.${this.region}.amazonaws.com`),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: apiCache,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
          responseHeadersPolicy: headers,
        },
      },
    });

    const config = s3deploy.Source.jsonData('config.json', props.runtimeConfig);
    const hasDist = existsSync(props.webDist);
    if (!hasDist) cdk.Annotations.of(this).addWarningV2('ezhuthu:web-dist', `${props.webDist} not built; only config.json is deployed`);
    new s3deploy.BucketDeployment(this, 'Deploy', {
      sources: hasDist ? [s3deploy.Source.asset(props.webDist, { exclude: ['mockServiceWorker.js', '**/*.map'] }), config] : [config],
      destinationBucket: bucket,
      distribution: this.distribution,
      distributionPaths: ['/*'],
      prune: hasDist,
      memoryLimit: 512,
    });

    const cloudFrontUrl = `https://${this.distribution.distributionDomainName}`;
    if (custom) {
      const target = route53.RecordTarget.fromAlias(new targets.CloudFrontTarget(this.distribution));
      new route53.ARecord(this, 'AliasA', { zone: zone!, recordName: custom.domainName, target });
      new route53.AaaaRecord(this, 'AliasAaaa', { zone: zone!, recordName: custom.domainName, target });
    }
    new cdk.CfnOutput(this, 'WebUrl', { value: custom ? `https://${custom.domainName}` : cloudFrontUrl });
    new cdk.CfnOutput(this, 'CloudFrontUrl', { value: cloudFrontUrl });
    new cdk.CfnOutput(this, 'SiteBucket', { value: bucket.bucketName });
  }
}
