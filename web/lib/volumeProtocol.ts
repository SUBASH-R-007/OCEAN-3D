import type { Volume } from './ocean';

/** Display transport only; scientific NetCDF exports retain native precision. */
export function decodeVolume(buffer: ArrayBuffer): Volume {
  if (buffer.byteLength < 8 || buffer.byteLength > 4 * 1024 * 1024) throw new Error('Invalid volume packet length.');
  const bytes = new Uint8Array(buffer), view = new DataView(buffer);
  if (String.fromCharCode(...bytes.subarray(0, 4)) !== 'OCV1') throw new Error('Unsupported volume packet.');
  const length = view.getUint32(4, true), start = 8 + length;
  if (length > 1024 * 1024 || length % 4 || start > buffer.byteLength) throw new Error('Invalid volume metadata length.');
  const meta = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(8, start)));
  if (meta.encoding?.version !== 1 || meta.encoding?.dtype !== '<f4' || meta.encoding?.missing !== 'NaN') throw new Error('Unsupported volume encoding.');
  if (!Array.isArray(meta.dimensions) || meta.dimensions.length !== 3 || !meta.dimensions.every((n: unknown) => Number.isInteger(n) && Number(n) >= 2 && Number(n) <= 96)) throw new Error('Invalid volume dimensions.');
  const count = meta.dimensions.reduce((a: number, b: number) => a * b, 1);
  if (count > 64 * 64 * 96 || buffer.byteLength !== start + count * 4 || meta.total_cells !== count) throw new Error('Volume payload and dimensions disagree.');
  for (const [i, key] of ['longitude', 'latitude', 'depth'].entries()) {
    const axis = meta.axes?.[key];
    if (!Array.isArray(axis) || axis.length !== meta.dimensions[i] || !axis.every((v: unknown, j: number) => typeof v === 'number' && Number.isFinite(v) && (!j || v > axis[j - 1]))) throw new Error('Invalid volume coordinates.');
  }
  const values: (number | null)[] = [];
  values.length = count;
  let valid = 0;
  for (let i = 0; i < count; i++) {
    const value = view.getFloat32(start + i * 4, true);
    if (!Number.isFinite(value) && !Number.isNaN(value)) throw new Error('Infinite value in volume packet.');
    values[i] = Number.isNaN(value) ? null : value;
    if (values[i] !== null) valid++;
  }
  if (valid !== meta.valid_cells) throw new Error('Volume validity count disagrees.');
  return { ...meta, values } as Volume;
}

/** Conservative accounting for decoded scalar arrays; not a JS heap profiler. */
export class FrameCache {
  readonly entries = new Map<string, { frame: Volume; bytes: number }>();
  bytes = 0;
  readonly limit: number;
  constructor(limit = 48 * 1024 * 1024) { this.limit = limit; }
  get(key: string) {
    const entry = this.entries.get(key);
    if (entry) { this.entries.delete(key); this.entries.set(key, entry); }
    return entry?.frame;
  }
  put(key: string, frame: Volume) {
    const old = this.entries.get(key);
    if (old) { this.bytes -= old.bytes; this.entries.delete(key); }
    const bytes = frame.values.length * 16 + JSON.stringify({ ...frame, values: [] }).length * 2;
    if (bytes > this.limit) return;
    while (this.entries.size && (this.bytes + bytes > this.limit || this.entries.size >= 24)) {
      const first = this.entries.keys().next().value!;
      this.bytes -= this.entries.get(first)!.bytes;
      this.entries.delete(first);
    }
    this.entries.set(key, { frame, bytes }); this.bytes += bytes;
  }
}
