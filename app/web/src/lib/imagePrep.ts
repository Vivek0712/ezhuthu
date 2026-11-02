/**
 * Client-side photo preparation for POST /api/read (contracts/restore-api.md).
 *
 * Phones produce 3-12 MB photos. The agent takes at most 5 MB decoded, but the cloud proxy caps the request at 4.5 MB
 * of base64 JSON, which is about 3.3 MB of image: that is the effective limit, so it is the client's hard limit. We decode the photo in the browser (EXIF orientation applied), draw it at most MAX_SIDE px on the long
 * side and re-encode JPEG, lowering quality until it fits TARGET_BYTES. Re-encoding through a canvas also drops every
 * EXIF/GPS tag before anything leaves the device (the server strips them again).
 */
export const MAX_SIDE = 2048;
export const TARGET_BYTES = 1_500_000;
export const HARD_LIMIT_BYTES = 3_300_000;
export const TEXT_LIMIT_BYTES = 512 * 1024;
export const ACCEPT_IMAGES = 'image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif,.jpg,.jpeg,.png,.webp';
export const ACCEPT_TEXT = '.txt,.xml,text/plain,application/xml,text/xml';

export type PrepError = 'heic' | 'not_image' | 'too_large' | 'decode';

export class ImagePrepError extends Error {
  constructor(public readonly kind: PrepError) {
    super(kind);
    this.name = 'ImagePrepError';
  }
}

export interface PreparedPhoto {
  base64: string;
  mediaType: 'image/jpeg';
  width: number;
  height: number;
  bytes: number;
  originalBytes: number;
  previewUrl: string;
  /** The uploaded file's name (informational; the server never shows it to the model). */
  filename?: string;
}

/** Scale (w, h) to fit inside max on the long side, never upscaling. */
export function fitWithin(w: number, h: number, max = MAX_SIDE): { width: number; height: number } {
  const s = Math.min(1, max / Math.max(w, h));
  return { width: Math.max(1, Math.round(w * s)), height: Math.max(1, Math.round(h * s)) };
}

/** Bytes a base64 string decodes to. */
export function base64Bytes(b64: string): number {
  const pad = b64.endsWith('==') ? 2 : b64.endsWith('=') ? 1 : 0;
  return Math.floor((b64.length * 3) / 4) - pad;
}

export function isHeic(file: { name: string; type: string }): boolean {
  return /image\/hei[cf]/i.test(file.type) || /\.hei[cf]$/i.test(file.name);
}

export function looksLikeText(file: { name: string; type: string }): boolean {
  return /\.(txt|xml)$/i.test(file.name) || /^text\/|\/xml$/i.test(file.type);
}

/** JPEG qualities tried in order until the result fits TARGET_BYTES. */
export const QUALITY_STEPS = [0.86, 0.78, 0.7, 0.6, 0.5];

async function blobToBase64(blob: Blob): Promise<string> {
  const buf = new Uint8Array(await blob.arrayBuffer());
  let bin = '';
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  return btoa(bin);
}

async function decode(file: Blob): Promise<ImageBitmap | HTMLImageElement> {
  if (typeof createImageBitmap === 'function') {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' });
    } catch {
      /* fall through to <img>, which Safari uses for HEIC */
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = 'async';
    img.src = url;
    await img.decode();
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function preparePhoto(file: File): Promise<PreparedPhoto> {
  if (!file.type.startsWith('image/') && !isHeic(file)) throw new ImagePrepError('not_image');
  if (file.size > 40 * 1024 * 1024) throw new ImagePrepError('too_large');
  let src: ImageBitmap | HTMLImageElement;
  try {
    src = await decode(file);
  } catch {
    // Chrome/Firefox cannot decode HEIC; iOS Safari converts it to JPEG on upload.
    throw new ImagePrepError(isHeic(file) ? 'heic' : 'decode');
  }
  const w = 'naturalWidth' in src ? src.naturalWidth : src.width;
  const h = 'naturalHeight' in src ? src.naturalHeight : src.height;
  const size = fitWithin(w, h);
  const canvas = document.createElement('canvas');
  canvas.width = size.width;
  canvas.height = size.height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new ImagePrepError('decode');
  ctx.fillStyle = '#ffffff'; // transparent PNGs become white, not black
  ctx.fillRect(0, 0, size.width, size.height);
  ctx.drawImage(src, 0, 0, size.width, size.height);
  if ('close' in src) src.close();
  let blob: Blob | null = null;
  for (const q of QUALITY_STEPS) {
    blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, 'image/jpeg', q));
    if (blob && blob.size <= TARGET_BYTES) break;
  }
  if (!blob) throw new ImagePrepError('decode');
  if (blob.size > HARD_LIMIT_BYTES) throw new ImagePrepError('too_large');
  return {
    base64: await blobToBase64(blob),
    mediaType: 'image/jpeg',
    width: size.width,
    height: size.height,
    bytes: blob.size,
    originalBytes: file.size,
    previewUrl: URL.createObjectURL(blob),
    filename: file.name.slice(0, 200),
  };
}

export async function readTextFile(file: File): Promise<string> {
  if (file.size > TEXT_LIMIT_BYTES) throw new ImagePrepError('too_large');
  if (typeof file.text === 'function') return file.text();
  return new Promise((resolve, reject) => {
    const r = new FileReader(); // older Safari and jsdom lack Blob.text()
    r.onload = () => resolve(String(r.result ?? ''));
    r.onerror = () => reject(new ImagePrepError('decode'));
    r.readAsText(file, 'utf-8');
  });
}
