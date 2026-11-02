import { execFileSync } from 'node:child_process';

/** Secrets Manager name of the hosted Strands Decider key (config/models.yaml decider.cloud.secret_name). */
export const DECIDER_SECRET_NAME = 'ezhuthu/decider-api-key';

export type Runner = (cmd: string, args: string[]) => string;

const defaultRunner: Runner = (cmd, args) =>
  execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 20_000 });

const OVERRIDE_HINT =
  'Pass -c ezhuthu:deciderSecretArn=<arn> to pin the hosted decider, or -c ezhuthu:deciderSecretArn=none to ' +
  'synthesise the labelled fallback without a lookup.';

const firstLine = (t: string) => t.split('\n').map((l) => l.trim()).find((l) => l.length > 0) ?? '';

/** The error's message and the AWS CLI's captured stderr (execFileSync puts the CLI's message there). */
function errorParts(err: unknown): { message: string; stderr: string } {
  const e = err as { message?: unknown; stderr?: unknown };
  const stderr = typeof e?.stderr === 'string' ? e.stderr : Buffer.isBuffer(e?.stderr) ? e.stderr.toString('utf8') : '';
  return { message: typeof e?.message === 'string' ? e.message : String(err), stderr };
}

/**
 * The secret's full ARN if it exists, else undefined. Read-only (`secretsmanager:DescribeSecret`); it never creates
 * the secret. Only a definite "no secret" answer selects the fallback: ResourceNotFoundException, or a secret
 * scheduled for deletion (DeletedDate, where GetSecretValue would fail). Every other failure (no AWS CLI, timeout,
 * throttling, missing or wrong credentials, unparseable output) throws, so a deploy cannot quietly drop the hosted
 * decider and its GetSecretValue grant once the secret exists.
 */
export function lookupDeciderSecretArn(profile: string, region: string, run: Runner = defaultRunner): string | undefined {
  let out: string;
  try {
    out = run('aws', [
      'secretsmanager', 'describe-secret', '--secret-id', DECIDER_SECRET_NAME,
      '--profile', profile, '--region', region, '--output', 'json',
    ]);
  } catch (err) {
    const { message, stderr } = errorParts(err);
    if (/ResourceNotFoundException/.test(`${message}\n${stderr}`)) return undefined;
    const detail = [firstLine(message), firstLine(stderr)].filter((l) => l.length > 0).join(' / ') || 'unknown error';
    throw new Error(`ezhuthu: could not look up ${DECIDER_SECRET_NAME} with profile ${profile} in ${region}: ${detail}. ${OVERRIDE_HINT}`);
  }
  let d: { ARN?: unknown; DeletedDate?: unknown };
  try {
    d = JSON.parse(out) as { ARN?: unknown; DeletedDate?: unknown };
  } catch {
    throw new Error(`ezhuthu: unexpected describe-secret output for ${DECIDER_SECRET_NAME} (not JSON). ${OVERRIDE_HINT}`);
  }
  if (d.DeletedDate) return undefined; // scheduled for deletion: GetSecretValue would fail
  if (typeof d.ARN === 'string' && d.ARN.startsWith('arn:')) return d.ARN;
  throw new Error(`ezhuthu: describe-secret for ${DECIDER_SECRET_NAME} returned no ARN. ${OVERRIDE_HINT}`);
}
