import benchmarkSchema from '../../../../contracts/benchmark-item.schema.json';

/** Validate a JSONL upload against contracts/benchmark-item.schema.json before it is sent to /api/evaluate. */
export interface JsonlReport {
  valid: number;
  errors: { line: number; message: string }[];
}

type Prop = { type?: string | string[]; enum?: unknown[]; minimum?: number };
const PROPS = benchmarkSchema.properties as Record<string, Prop>;
const REQUIRED: readonly string[] = benchmarkSchema.required;

function typeOk(value: unknown, type: string): boolean {
  switch (type) {
    case 'string':
      return typeof value === 'string';
    case 'integer':
      return Number.isInteger(value);
    case 'boolean':
      return typeof value === 'boolean';
    case 'null':
      return value === null;
    default:
      return true;
  }
}

export function validateRecord(rec: unknown): string[] {
  if (typeof rec !== 'object' || rec === null || Array.isArray(rec)) return ['not a JSON object'];
  const r = rec as Record<string, unknown>;
  const errs: string[] = [];
  for (const key of REQUIRED) if (!(key in r)) errs.push(`missing "${key}"`);
  for (const [key, value] of Object.entries(r)) {
    const p = PROPS[key];
    if (!p) continue;
    const types = Array.isArray(p.type) ? p.type : p.type ? [p.type] : [];
    if (types.length && !types.some((t) => typeOk(value, t))) errs.push(`"${key}" should be ${types.join(' or ')}`);
    if (p.enum && !p.enum.includes(value)) errs.push(`"${key}" must be one of ${p.enum.join(', ')}`);
    if (typeof p.minimum === 'number' && typeof value === 'number' && value < p.minimum)
      errs.push(`"${key}" must be >= ${p.minimum}`);
  }
  return errs;
}

export function validateJsonl(text: string, maxErrors = 20): JsonlReport {
  const report: JsonlReport = { valid: 0, errors: [] };
  const lines = text.split(/\r?\n/);
  lines.forEach((raw, i) => {
    const line = raw.trim();
    if (!line) return;
    let rec: unknown;
    try {
      rec = JSON.parse(line);
    } catch {
      if (report.errors.length < maxErrors) report.errors.push({ line: i + 1, message: 'invalid JSON' });
      return;
    }
    const errs = validateRecord(rec);
    if (errs.length) {
      if (report.errors.length < maxErrors) report.errors.push({ line: i + 1, message: errs.join('; ') });
    } else report.valid += 1;
  });
  return report;
}
