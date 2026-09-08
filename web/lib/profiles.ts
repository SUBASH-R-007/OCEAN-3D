import type { Comparison, Profile, Provenance } from './ocean';

export type NativeProfile = Profile & {
  samples: NonNullable<Comparison['samples']>;
};

export function clippedInstrumentPath(
  path: NonNullable<Profile['path']>,
  bounds: number[],
  top: number,
  bottom: number,
) {
  const segments: [number[], number[]][] = [];
  for (let i = 1; i < path.length; i++) {
    if (path[i].break_before) continue;
    const a = [path[i - 1].longitude, path[i - 1].latitude, path[i - 1].depth],
      b = [path[i].longitude, path[i].latitude, path[i].depth];
    if (![...a, ...b].every(Number.isFinite)) continue;
    const low = [bounds[0], bounds[1], top],
      high = [bounds[2], bounds[3], bottom];
    let start = 0,
      end = 1;
    for (let axis = 0; axis < 3; axis++) {
      const delta = b[axis] - a[axis];
      if (delta === 0) {
        if (a[axis] < low[axis] || a[axis] > high[axis]) end = -1;
        continue;
      }
      const t1 = (low[axis] - a[axis]) / delta,
        t2 = (high[axis] - a[axis]) / delta;
      start = Math.max(start, Math.min(t1, t2));
      end = Math.min(end, Math.max(t1, t2));
    }
    if (end > start)
      segments.push([
        a.map((x, j) => x + (b[j] - x) * start),
        a.map((x, j) => x + (b[j] - x) * end),
      ]);
  }
  return segments;
}

export function arrangeInstrumentLabels<T extends { x: number; y: number }>(
  labels: T[],
  width: number,
  height: number,
) {
  const placed: (T & { anchorX: number; anchorY: number })[] = [];
  for (const label of labels) {
    if (
      !Number.isFinite(label.x + label.y) ||
      label.x < 0 ||
      label.y < 0 ||
      label.x > width ||
      label.y > height
    )
      continue;
    const x = Math.max(10, Math.min(Math.max(10, width - 178), label.x));
    const candidates = Array.from(
      { length: Math.max(1, Math.floor((height - 28) / 28)) },
      (_, i) => 14 + i * 28,
    ).sort((a, b) => Math.abs(a - label.y) - Math.abs(b - label.y));
    const y =
      candidates.find((y) =>
        placed.every(
          (p) => Math.abs(p.x - x) >= 178 || Math.abs(p.y - y) >= 27,
        ),
      ) ?? Math.max(14, Math.min(height - 14, label.y));
    placed.push({ ...label, anchorX: label.x, anchorY: label.y, x, y });
  }
  return placed;
}

export function observationOnly(
  profile: NativeProfile,
  variable: string,
  qc: 'strict' | 'lenient',
  provenance: Provenance,
): Comparison {
  const samples = profile.samples.filter((row) => row.variable === variable);
  const allowed = qc === 'strict' ? [1] : [1, 2];
  const pairs = samples
    .filter(
      (row) =>
        row.value != null &&
        Number.isFinite(row.value) &&
        allowed.includes(row.qc),
    )
    .map((row) => ({ ...row, value: row.value!, model: null, residual: null }));
  const { samples: _, ...meta } = profile;
  return {
    profile: meta,
    variable,
    samples,
    pairs,
    metrics: {
      count: 0,
      total: samples.length,
      qc_excluded: samples.length - pairs.length,
      unmatched: pairs.length,
      bias: null,
      rmse: null,
      mae: null,
    },
    provenance,
    method: { qc_flags: allowed },
    comparison_reason:
      'Observed profile shown independently. A native model comparison for this instrument and variable is not bundled; connect the scientific API to evaluate matching coordinates, dates and variable definitions.',
    limitations: [
      'No model values or skill metrics are inferred from display-grid imagery.',
    ],
  };
}

export function profileChartRows(data: Comparison) {
  const allowed = (data.method.qc_flags as number[] | undefined) || [1];
  if (!data.samples) return data.pairs;
  let cursor = 0;
  return data.samples.map((row) => {
    if (
      row.value == null ||
      !Number.isFinite(row.value) ||
      !allowed.includes(row.qc)
    )
      return { ...row, value: null, model: null, residual: null };
    const pair = data.pairs[cursor++];
    return {
      ...row,
      model: pair?.model ?? null,
      residual: pair?.residual ?? null,
    };
  });
}

export function profileCsv(data: Comparison, unit: string) {
  const display = profileChartRows(data);
  const rows = data.samples || data.pairs;
  const quote = (value: string | number | boolean | null | undefined) => {
    if (value == null) return '';
    if (typeof value === 'number') return String(value);
    const text = String(value);
    return (
      '"' +
      (/^[=+@-]/.test(text) ? "'" + text : text).replaceAll('"', '""') +
      '"'
    );
  };
  return [
    'profile_id,instrument,variable,unit,observation_time_utc,longitude,latitude,depth_m,observation,model,model_minus_observation,qc,source_qc,included_by_qc,adjusted',
    ...rows.map((row, i) => {
      const native = row as NonNullable<Comparison['samples']>[number];
      return [
        data.profile.id,
        data.profile.instrument,
        data.variable,
        unit,
        native.time || data.profile.time,
        native.longitude ?? data.profile.longitude,
        native.latitude ?? data.profile.latitude,
        row.depth,
        row.value,
        display[i].model,
        display[i].residual,
        row.qc,
        native.source_qc,
        display[i].value !== null,
        row.adjusted,
      ]
        .map(quote)
        .join(',');
    }),
  ].join('\n');
}

export function timeSeriesRows(data: Comparison) {
  return profileChartRows(data)
    .map((row) => ({
      ...row,
      timestamp: Date.parse(('time' in row && row.time) || data.profile.time),
    }))
    .filter((row) => Number.isFinite(row.timestamp))
    .sort((a, b) => a.timestamp - b.timestamp);
}

export function instrumentIsFresh(
  profile: Pick<Profile, 'time' | 'sample_times'>,
  fieldTime: string,
) {
  const target = Date.parse(fieldTime);
  return (profile.sample_times || [profile.time]).some(
    (time) => Math.abs(Date.parse(time) - target) <= 86400000,
  );
}
