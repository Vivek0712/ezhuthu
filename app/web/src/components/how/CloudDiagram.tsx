import { useMemo } from 'react';
import { useI18n } from '../../i18n/I18nProvider';
import { Diagram, useNarrow, type DEdge, type DLayout, type DNode } from './Diagram';

// Every box is a resource in infra/ (AWS CDK): EzhuthuWeb (S3 + CloudFront, /api/* to the HTTP API),
// EzhuthuApi (API Gateway HTTP API, JWT authorizer from the Cognito pool, Lambda proxy Node 22 arm64, 29 s timeout),
// EzhuthuAgent (Bedrock AgentCore Runtime "ezhuthu_tutor", Python 3.12, ontology MCP server bundled; IAM invoke on the
// two model IDs in config/models.yaml; secretsmanager:GetSecretValue only when the decider secret exists),
// EzhuthuData (DynamoDB table), EzhuthuAuth (Cognito user pool, "experts" group). The hosted Strands Decider API is
// outside these stacks (config/models.yaml decider.cloud.url).
const EDGES: DEdge[] = [
  { id: 'browser-cf', from: 'browser', to: 'cf' },
  { id: 'cf-s3', from: 'cf', to: 's3' },
  { id: 'cf-api', from: 'cf', to: 'api' },
  { id: 'api-cognito', from: 'api', to: 'cognito', dashed: true },
  { id: 'api-lambda', from: 'api', to: 'lambda' },
  { id: 'lambda-agent', from: 'lambda', to: 'agent' },
  { id: 'lambda-ddb', from: 'lambda', to: 'ddb' },
  { id: 'agent-ddb', from: 'agent', to: 'ddb' },
  { id: 'agent-bedrock', from: 'agent', to: 'bedrock' },
  { id: 'agent-secrets', from: 'agent', to: 'secrets', kind: 'branch', dashed: true },
  { id: 'agent-decider', from: 'agent', to: 'decider', kind: 'branch', dashed: true },
];

const W = 154;
const H = 76;
const col = (i: number) => 10 + i * 172;
const WIDE: DLayout = {
  width: col(5) + W + 10,
  height: 16 + 2 * 112,
  w: W,
  h: H,
  at: {
    browser: [col(0), 16],
    cf: [col(1), 16],
    api: [col(2), 16],
    lambda: [col(3), 16],
    agent: [col(4), 16],
    bedrock: [col(5), 16],
    s3: [col(1), 128],
    cognito: [col(2), 128],
    ddb: [col(3), 128],
    secrets: [col(4), 128],
    decider: [col(5), 128],
  },
};
const L = 8;
const R = 198;
const r = (i: number) => 10 + i * 92;
const NARROW: DLayout = {
  width: 360,
  height: r(6) + H + 10,
  w: 154,
  h: H,
  at: {
    browser: [L, r(0)],
    cf: [L, r(1)],
    s3: [R, r(1)],
    api: [L, r(2)],
    cognito: [R, r(2)],
    lambda: [L, r(3)],
    ddb: [R, r(3)],
    agent: [L, r(4)],
    secrets: [R, r(4)],
    bedrock: [L, r(5)],
    decider: [R, r(5)],
  },
};

/** A compact AWS architecture diagram; every box is verified against infra/. */
export function CloudDiagram() {
  const { t } = useI18n();
  const narrow = useNarrow();
  const nodes: DNode[] = useMemo(
    () => [
      { id: 'browser', label: t('hw.c.browser'), sub: t('hw.c.browserSub'), tone: 'io' },
      // AWS service names are product names, the same in both languages.
      { id: 'cf', label: 'Amazon CloudFront', sub: t('hw.c.cloudfrontSub'), tone: 'aws' },
      { id: 's3', label: 'Amazon S3', sub: t('hw.c.s3Sub'), tone: 'data' },
      { id: 'api', label: 'Amazon API Gateway', sub: t('hw.c.apigwSub'), tone: 'aws' },
      { id: 'cognito', label: 'Amazon Cognito', sub: t('hw.c.cognitoSub'), tone: 'people' },
      { id: 'lambda', label: 'AWS Lambda', sub: t('hw.c.lambdaSub'), tone: 'aws' },
      { id: 'ddb', label: 'Amazon DynamoDB', sub: t('hw.c.dynamoSub'), tone: 'data' },
      { id: 'agent', label: 'Bedrock AgentCore Runtime', sub: t('hw.c.agentcoreSub'), tone: 'agent' },
      { id: 'bedrock', label: 'Amazon Bedrock', sub: 'Claude Sonnet 4.6 · Opus 4.6', tone: 'model' },
      { id: 'secrets', label: 'AWS Secrets Manager', sub: t('hw.c.secretsSub'), tone: 'branch' },
      { id: 'decider', label: 'Strands Decider API', sub: t('hw.c.deciderSub'), tone: 'branch' },
    ],
    [t],
  );
  return (
    <figure className="cloud" data-testid="cloud">
      <div className="flow-canvas">
        <Diagram id="cloud" nodes={nodes} edges={EDGES} layout={narrow ? NARROW : WIDE} title={t('hw.cloudTitle')} testId="cloud-svg" labelLines={2} />
      </div>
      <figcaption className="hint-text">{t('hw.cloudNote')}</figcaption>
    </figure>
  );
}
