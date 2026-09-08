export interface ColorScale {
  min: number;
  max: number;
  palette: string;
  log: boolean;
}

export const palettes: Record<string, string[]> = {
  thermal: ['#172b68', '#226ea8', '#21b8b0', '#b2d968', '#ffcf67', '#ed694e'],
  viridis: ['#440154', '#414487', '#2a788e', '#22a884', '#7ad151', '#fde725'],
  ice: ['#11274d', '#245d83', '#39a1b3', '#8cd8d1', '#e9f6ea'],
  balance: [
    '#2166ac',
    '#67a9cf',
    '#d1e5f0',
    '#f7f7f7',
    '#fddbc7',
    '#ef8a62',
    '#b2182b',
  ],
};
export const paletteStops = (name: string) =>
  Object.hasOwn(palettes, name) ? palettes[name] : palettes.thermal;

export function colorRangeError(
  minimum: string,
  maximum: string,
  log: boolean,
) {
  if (!minimum.trim() || !maximum.trim()) return 'Enter both color limits.';
  const min = Number(minimum),
    max = Number(maximum);
  if (![min, max].every((v) => Number.isFinite(v) && Math.abs(v) <= 1e30))
    return 'Use finite color limits between −1e30 and 1e30.';
  if (min >= max) return 'Maximum must be greater than minimum.';
  if (log && min <= 0) return 'Logarithmic scales require a positive minimum.';
  return '';
}

export const displayScalar = (value: number | null, log: boolean) =>
  value == null || !Number.isFinite(value) || (log && value <= 0)
    ? NaN
    : log
      ? Math.log10(value)
      : value;

export function scaleValue(t: number, min: number, max: number, log = false) {
  if (t === 0) return min;
  if (t === 1) return max;
  return log
    ? 10 ** ((1 - t) * Math.log10(min) + t * Math.log10(max))
    : (1 - t) * min + t * max;
}

export function colorRgb(
  value: number,
  min: number,
  max: number,
  palette = 'thermal',
  log = false,
) {
  const lo = displayScalar(min, log),
    hi = displayScalar(max, log);
  const position = (displayScalar(value, log) - lo) / (hi - lo);
  if (!Number.isFinite(position) || !(lo < hi)) return [23, 38, 54];
  const stops = paletteStops(palette);
  const t = Math.max(0, Math.min(1, position)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(t)),
    f = t - i;
  return [1, 3, 5].map((offset) => {
    const a = parseInt(stops[i].slice(offset, offset + 2), 16);
    const b = parseInt(stops[i + 1].slice(offset, offset + 2), 16);
    return Math.round(a + (b - a) * f);
  });
}

export function color(
  value: number,
  min: number,
  max: number,
  palette = 'thermal',
  log = false,
) {
  return `rgb(${colorRgb(value, min, max, palette, log).join(',')})`;
}

export function scaleTicks(scale: ColorScale) {
  return [0, 0.25, 0.5, 0.75, 1].map((position) => ({
    position,
    value: scaleValue(position, scale.min, scale.max, scale.log),
  }));
}

export function formatScaleValue(value: number) {
  if (value === 0) return '0';
  if (Math.abs(value) < 0.001 || Math.abs(value) >= 10000)
    return value.toExponential(2);
  return String(Number(value.toPrecision(4)));
}

// Transform only display scalars. Native values, coordinates and exported data stay unchanged.
// Encoding the logarithm before GPU lookup avoids a linear texture losing low decades.
export function encodeDisplayScalars(values: (number | null)[], log: boolean) {
  let min = Infinity,
    max = -Infinity,
    excluded = 0;
  const encoded = new Float32Array(values.length);
  values.forEach((v, i) => {
    const x = displayScalar(v, log);
    encoded[i] = x;
    if (Number.isFinite(encoded[i])) {
      min = Math.min(min, encoded[i]);
      max = Math.max(max, encoded[i]);
    } else if (v != null && Number.isFinite(v)) excluded++;
  });
  if (!Number.isFinite(min)) {
    min = 0;
    max = 1;
  }
  const sentinel = Math.fround(
    min - Math.max(1, max - min, Math.abs(min) * 0.01) * 0.1,
  );
  for (let i = 0; i < encoded.length; i++)
    if (!Number.isFinite(encoded[i])) encoded[i] = sentinel;
  return { values: encoded, min, max, sentinel, excluded };
}

// Include each palette knot, and clamp colors outside the requested limits.
export function transferStops(
  scale: ColorScale,
  domain: { min: number; max: number },
) {
  const lo = displayScalar(scale.min, scale.log),
    hi = displayScalar(scale.max, scale.log);
  const positions = new Set([domain.min, domain.max]);
  paletteStops(scale.palette).forEach((_, i, stops) => {
    const x = (1 - i / (stops.length - 1)) * lo + (i / (stops.length - 1)) * hi;
    if (x >= domain.min && x <= domain.max) positions.add(x);
  });
  return [...positions]
    .sort((a, b) => a - b)
    .map((x) => ({
      x,
      rgb: colorRgb(x, lo, hi, scale.palette),
    }));
}
