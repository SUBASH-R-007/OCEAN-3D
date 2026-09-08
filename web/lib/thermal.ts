import type { Provenance } from './ocean';

export const changeRGB = (value: number) => {
  const t = Math.min(1, Math.abs(value) / 50),
    neutral = [215, 230, 230],
    end = value >= 0 ? [250, 139, 95] : [87, 166, 255];
  return neutral.map((v, i) => Math.round(v + (end[i] - v) * t));
};

export interface ThermalFrame {
  time: string;
  temperature: (number | null)[];
  local_count: (number | null)[];
  influence_count: (number | null)[];
}
export interface ThermalAtlas {
  schema: string;
  provenance: Provenance;
  longitude: number[];
  latitude: number[];
  depth: number[];
  frames: ThermalFrame[];
  method: string;
}
export interface Relief {
  longitude: number[];
  latitude: number[];
  elevation: (number | null)[];
  provenance: {
    title: string;
    source_url: string;
    sha256: string;
    resolution: string;
    license: string;
  };
}

/** Subset every depth and frame with identical native indices; never resample. */
export function subsetAtlas(
  atlas: ThermalAtlas,
  bounds: number[],
): ThermalAtlas {
  const xx = atlas.longitude
    .map((v, i) => ({ v, i }))
    .filter((p) => p.v >= bounds[0] && p.v <= bounds[2]);
  const yy = atlas.latitude
    .map((v, i) => ({ v, i }))
    .filter((p) => p.v >= bounds[1] && p.v <= bounds[3]);
  if (xx.length < 2 || yy.length < 2)
    throw Error('The region has fewer than two native grid columns per axis.');
  const cells = atlas.longitude.length * atlas.latitude.length;
  const subset = (a: (number | null)[]) =>
    atlas.depth.flatMap((_, z) =>
      yy.flatMap((y) =>
        xx.map((x) => a[z * cells + y.i * atlas.longitude.length + x.i]),
      ),
    );
  return {
    ...atlas,
    longitude: xx.map((p) => p.v),
    latitude: yy.map((p) => p.v),
    frames: atlas.frames.map((f) => ({
      ...f,
      temperature: subset(f.temperature),
      local_count: subset(f.local_count),
      influence_count: subset(f.influence_count),
    })),
  };
}
export function subsetRelief(relief: Relief, bounds: number[]): Relief {
  const xx = relief.longitude
    .map((v, i) => ({ v, i }))
    .filter((p) => p.v >= bounds[0] && p.v <= bounds[2]);
  const yy = relief.latitude
    .map((v, i) => ({ v, i }))
    .filter((p) => p.v >= bounds[1] && p.v <= bounds[3]);
  return {
    ...relief,
    longitude: xx.map((p) => p.v),
    latitude: yy.map((p) => p.v),
    elevation: yy.flatMap((y) =>
      xx.map((x) => relief.elevation[y.i * relief.longitude.length + x.i]),
    ),
  };
}

export function suggestedProbe(
  atlas: ThermalAtlas,
  before: number,
  after: number,
  threshold: number,
): number {
  const paired = pairedChange(atlas, before, after, threshold).cells;
  const candidates = paired
    .map((p, i) => ({ ...p, i }))
    .filter((p) => p.delta != null);
  const local = candidates.filter((p) => p.locallySupported),
    eligible = local.length ? local : candidates;
  const cx = (atlas.longitude[0] + atlas.longitude.at(-1)!) / 2,
    cy = (atlas.latitude[0] + atlas.latitude.at(-1)!) / 2;
  const distance = (i: number) =>
    (atlas.longitude[i % atlas.longitude.length] - cx) ** 2 +
    (atlas.latitude[Math.floor(i / atlas.longitude.length)] - cy) ** 2;
  if (!eligible.length) return 0;
  return eligible.reduce(
    (best, p) => (distance(p.i) < distance(best) ? p.i : best),
    eligible[0].i,
  );
}
export type Crossing = {
  depth: number | null;
  bracket: [number, number] | null;
  indices: [number, number] | null;
  reason: 'crossing' | 'surface_below' | 'missing' | 'gap' | 'not_reached';
};

// Return the first shallow-to-deep crossing. Missing levels before it censor the
// result: later finite levels must not manufacture a first crossing across a gap.
export function firstDownwardCrossing(
  depth: number[],
  values: (number | null)[],
  threshold: number,
  maxGap = 150,
): Crossing {
  const empty = (reason: Crossing['reason']): Crossing => ({
    depth: null,
    bracket: null,
    indices: null,
    reason,
  });
  if (
    !Number.isFinite(threshold) ||
    depth.length !== values.length ||
    !depth.length
  )
    return empty('missing');
  if (values[0] == null || !Number.isFinite(values[0])) return empty('missing');
  if (values[0] < threshold) return empty('surface_below');
  if (values[0] === threshold)
    return {
      depth: depth[0],
      bracket: [depth[0], depth[0]],
      indices: [0, 0],
      reason: 'crossing',
    };
  for (let z = 1; z < depth.length; z++) {
    const a = values[z - 1],
      b = values[z];
    if (a == null || b == null || !Number.isFinite(a) || !Number.isFinite(b))
      return empty('missing');
    if (!(depth[z] > depth[z - 1]) || depth[z] - depth[z - 1] > maxGap)
      return empty('gap');
    if (a > threshold && b <= threshold)
      return {
        depth:
          depth[z - 1] +
          ((depth[z] - depth[z - 1]) * (a - threshold)) / (a - b),
        bracket: [depth[z - 1], depth[z]],
        indices: [z - 1, z],
        reason: 'crossing',
      };
  }
  return empty('not_reached');
}
export function column(
  atlas: ThermalAtlas,
  frame: number,
  cell: number,
  key: keyof Omit<ThermalFrame, 'time'> = 'temperature',
) {
  const n = atlas.longitude.length * atlas.latitude.length;
  return atlas.depth.map((_, z) => atlas.frames[frame][key][z * n + cell]);
}
export function crossingAt(
  atlas: ThermalAtlas,
  frame: number,
  cell: number,
  threshold: number,
) {
  const result = firstDownwardCrossing(
    atlas.depth,
    column(atlas, frame, cell),
    threshold,
  );
  const local = column(atlas, frame, cell, 'local_count'),
    influence = column(atlas, frame, cell, 'influence_count');
  const minimum = (values: (number | null)[]) =>
    result.indices &&
    result.indices.every((i) => values[i] != null && Number.isFinite(values[i]))
      ? Math.min(...result.indices.map((i) => values[i]!))
      : null;
  return { ...result, local: minimum(local), influence: minimum(influence) };
}
export function thermalSurface(
  atlas: ThermalAtlas,
  frame: number,
  threshold: number,
) {
  return Array.from(
    { length: atlas.longitude.length * atlas.latitude.length },
    (_, i) => crossingAt(atlas, frame, i, threshold),
  );
}
export function pairedChange(
  atlas: ThermalAtlas,
  before: number,
  after: number,
  threshold: number,
) {
  const a = thermalSurface(atlas, before, threshold),
    b = thermalSurface(atlas, after, threshold);
  const cells = a.map((v, i) => ({
    before: v,
    after: b[i],
    delta: v.depth != null && b[i].depth != null ? b[i].depth! - v.depth : null,
    locallySupported:
      v.local != null && v.local > 0 && b[i].local != null && b[i].local! > 0,
  }));
  const paired = cells
    .map((v, i) => ({ ...v, i }))
    .filter((v) => v.delta != null);
  const sorted = paired.map((v) => v.delta!).sort((x, y) => x - y);
  const mid = Math.floor(sorted.length / 2);
  return {
    cells,
    count: paired.length,
    localCount: paired.filter((v) => v.locallySupported).length,
    median: sorted.length
      ? sorted.length % 2
        ? sorted[mid]
        : (sorted[mid - 1] + sorted[mid]) / 2
      : null,
    largest:
      paired.sort((x, y) => Math.abs(y.delta!) - Math.abs(x.delta!))[0]?.i ??
      null,
  };
}

// Rendering interpolation is confined to complete native quadrilaterals. It
// changes mesh tessellation, never the native-grid crossing or change metrics.
export function surfaceGeometry(
  lon: number[],
  lat: number[],
  depths: (number | null)[],
  subdivisions = 5,
) {
  const points: number[] = [],
    polys: number[] = [],
    nativeCell: number[] = [];
  const n = lon.length,
    at = (x: number, y: number) => y * n + x;
  for (let y = 0; y < lat.length - 1; y++)
    for (let x = 0; x < n - 1; x++) {
      const ids = [at(x, y), at(x + 1, y), at(x, y + 1), at(x + 1, y + 1)];
      if (ids.some((i) => depths[i] == null || !Number.isFinite(depths[i])))
        continue;
      const start = points.length / 3;
      for (let j = 0; j <= subdivisions; j++)
        for (let i = 0; i <= subdivisions; i++) {
          const u = i / subdivisions,
            v = j / subdivisions;
          const d =
            depths[ids[0]]! * (1 - u) * (1 - v) +
            depths[ids[1]]! * u * (1 - v) +
            depths[ids[2]]! * (1 - u) * v +
            depths[ids[3]]! * u * v;
          points.push(
            lon[x] + (lon[x + 1] - lon[x]) * u,
            lat[y] + (lat[y + 1] - lat[y]) * v,
            d,
          );
          nativeCell.push(ids[0]);
        }
      const width = subdivisions + 1;
      for (let j = 0; j < subdivisions; j++)
        for (let i = 0; i < subdivisions; i++) {
          const a = start + j * width + i,
            b = a + 1,
            c = a + width,
            d = c + 1;
          polys.push(3, a, b, d, 3, a, d, c);
        }
    }
  return { points, polys: new Uint32Array(polys), nativeCell };
}
export const monthName = (time: string) =>
  new Date(time).toLocaleDateString('en-GB', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
export const depthLens = (depth: number, upper: number) =>
  depth < 0
    ? (-depth * 35) / 1000
    : -(Math.min(depth, 500) * upper + Math.max(0, depth - 500) * 35) / 1000;
