#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { buildApp } from '../lib/app';
import { loadModelsConfig } from '../lib/config';
import { DECIDER_SECRET_NAME, lookupDeciderSecretArn } from '../lib/decider-secret';

const app = new cdk.App();

// Hosted decider only when its key exists in Secrets Manager. Pass `-c ezhuthu:deciderSecretArn=<arn>` to pin it,
// or `-c ezhuthu:deciderSecretArn=none` to force the labelled fallback without an AWS lookup. The lookup throws on
// anything but "found", "not found" or "scheduled for deletion", so a CLI/credential problem stops the synth.
let deciderSecretArn: string | undefined;
const pinned = app.node.tryGetContext('ezhuthu:deciderSecretArn') as string | undefined;
if (pinned === undefined && !app.node.tryGetContext('ezhuthu:agentRuntimeArn')) {
  const models = loadModelsConfig();
  deciderSecretArn = lookupDeciderSecretArn(models.awsProfile, models.region);
  process.stderr.write(
    deciderSecretArn
      ? `ezhuthu: hosted decider enabled (${DECIDER_SECRET_NAME} found)\n`
      : `ezhuthu: ${DECIDER_SECRET_NAME} not found; the agent runtime uses the labelled fallback decider\n`,
  );
}

buildApp(app, { deciderSecretArn });
app.synth();
