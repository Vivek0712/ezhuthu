/** The try-it passages, imported synchronously. App code loads them lazily through loadSamples() in './index'. */
import type { Sample } from '.';
import samplesJson from './samples.json';

export const SAMPLES = samplesJson as Sample[];
