import { execFileSync } from 'node:child_process';

/** Secrets Manager name of the hosted Strands Decider key (config/models.yaml decider.cloud.secret_name). */
export const DECIDER_SECRET_NAME = 'ezhuthu/decider-api-key';

export type Runner = (cmd: string, args: string[]) => string;

const defaultRunner: Runner = (cmd, args) =>
  execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 20_000 });

/**
 * The secret's full ARN if it exists and is readable with `profile`, else undefined. Read-only
 * (`secretsmanager:DescribeSecret`); it never creates the secret. Any failure (no AWS CLI, no credentials,
 * ResourceNotFoundException, scheduled deletion) means "no hosted decider": the runtime then uses the
 * labelled fallback.
 */
export function lookupDeciderSecretArn(profile: string, region: string, run: Runner = defaultRunner): string | undefined {
  try {
    const out = run('aws', [
      'secretsmanager', 'describe-secret', '--secret-id', DECIDER_SECRET_NAME,
      '--profile', profile, '--region', region, '--output', 'json',
    ]);
    const d = JSON.parse(out) as { ARN?: string; DeletedDate?: unknown };
    if (d.DeletedDate) return undefined; // scheduled for deletion: GetSecretValue would fail
    return typeof d.ARN === 'string' && d.ARN.startsWith('arn:') ? d.ARN : undefined;
  } catch {
    return undefined;
  }
}
