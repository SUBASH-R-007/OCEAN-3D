import type { Volume } from './ocean';

export type FlowPoint = {
  longitude: number;
  latitude: number;
  depth: number;
  elapsed_s: number;
  speed_m_s: number;
};
export type FlowPath = {
  points: FlowPoint[];
  stop: 'horizon' | 'missing_or_boundary' | 'stagnant' | 'integration_limit';
};
const R = 6371000;
const radians = Math.PI / 180;

// Sample physical coordinates, never the vertically exaggerated display mesh.
export function sampleField(
  field: Volume,
  lon: number,
  lat: number,
  depth: number,
): number | null {
  const queries = [lon, lat, depth];
  const axes = [field.axes.longitude, field.axes.latitude, field.axes.depth];
  const lower: number[] = [],
    fractions: number[] = [];
  for (let d = 0; d < 3; d++) {
    const a = axes[d],
      q = queries[d];
    if (!Number.isFinite(q) || q < a[0] || q > a.at(-1)!) return null;
    let low = 0,
      high = a.length - 1;
    while (high - low > 1) {
      const mid = (low + high) >> 1;
      if (a[mid] <= q) low = mid;
      else high = mid;
    }
    lower.push(low);
    fractions.push((q - a[low]) / (a[high] - a[low]));
  }
  const [nx, ny] = field.dimensions;
  let result = 0;
  for (let dz = 0; dz < 2; dz++)
    for (let dy = 0; dy < 2; dy++)
      for (let dx = 0; dx < 2; dx++) {
        const w =
          (dx ? fractions[0] : 1 - fractions[0]) *
          (dy ? fractions[1] : 1 - fractions[1]) *
          (dz ? fractions[2] : 1 - fractions[2]);
        if (w === 0) continue;
        const v =
          field.values[
            (lower[2] + dz) * nx * ny + (lower[1] + dy) * nx + lower[0] + dx
          ];
        if (v == null || !Number.isFinite(v)) return null;
        result += w * v;
      }
  return result;
}

export function sameGrid(a: Volume, b: Volume) {
  return (
    a.model_id === b.model_id &&
    a.time === b.time &&
    a.dimensions.join() === b.dimensions.join() &&
    (['longitude', 'latitude', 'depth'] as const).every(
      (k) =>
        a.axes[k].length === b.axes[k].length &&
        a.axes[k].every((x, i) => x === b.axes[k][i]),
    )
  );
}

export function integrateFlow(
  u: Volume,
  v: Volume,
  seed: [number, number],
  depth: number,
  horizonHours = 120,
  stepSeconds = 3600,
): FlowPath {
  if (!sameGrid(u, v))
    throw new Error(
      'Flow components must share model, time and all coordinates.',
    );
  if (
    !(
      horizonHours > 0 &&
      horizonHours <= 240 &&
      stepSeconds > 0 &&
      stepSeconds <= 3600
    )
  )
    throw new Error('Invalid bounded flow integration settings.');
  const velocity = (x: number, y: number) => {
    if (Math.abs(y) > 85) return null;
    const east = sampleField(u, x, y, depth),
      north = sampleField(v, x, y, depth);
    if (east == null || north == null) return null;
    return [
      east / (R * Math.cos(y * radians)) / radians,
      north / R / radians,
      Math.hypot(east, north),
    ];
  };
  const dx = Math.min(
    ...u.axes.longitude.slice(1).map((x, i) => x - u.axes.longitude[i]),
  );
  const dy = Math.min(
    ...u.axes.latitude.slice(1).map((x, i) => x - u.axes.latitude[i]),
  );
  let x = seed[0],
    y = seed[1],
    elapsed = 0;
  const points: FlowPoint[] = [];
  for (let step = 0; step < 2048; step++) {
    const a = velocity(x, y);
    if (!a) return { points, stop: 'missing_or_boundary' };
    points.push({
      longitude: x,
      latitude: y,
      depth,
      elapsed_s: elapsed,
      speed_m_s: a[2],
    });
    if (elapsed >= horizonHours * 3600) return { points, stop: 'horizon' };
    if (a[2] < 1e-5) return { points, stop: 'stagnant' };
    // Limit movement to a quarter of a grid cell per stage to protect narrow masks.
    const dt = Math.min(
      stepSeconds,
      horizonHours * 3600 - elapsed,
      (0.25 * dx) / Math.max(Math.abs(a[0]), 1e-15),
      (0.25 * dy) / Math.max(Math.abs(a[1]), 1e-15),
    );
    const b = velocity(x + (a[0] * dt) / 2, y + (a[1] * dt) / 2);
    if (!b) return { points, stop: 'missing_or_boundary' };
    const c = velocity(x + (b[0] * dt) / 2, y + (b[1] * dt) / 2);
    if (!c) return { points, stop: 'missing_or_boundary' };
    const d = velocity(x + c[0] * dt, y + c[1] * dt);
    if (!d) return { points, stop: 'missing_or_boundary' };
    x += (dt * (a[0] + 2 * b[0] + 2 * c[0] + d[0])) / 6;
    y += (dt * (a[1] + 2 * b[1] + 2 * c[1] + d[1])) / 6;
    elapsed += dt;
  }
  return { points, stop: 'integration_limit' };
}

export function seedFlow(
  u: Volume,
  v: Volume,
  depth: number,
  layers: number[] = [depth],
) {
  const paths: FlowPath[] = [];
  const side = layers.length === 1 ? 7 : 4;
  for (const layer of layers)
    for (let j = 1; j <= side; j++)
      for (let i = 1; i <= side; i++) {
        const lon =
          u.axes.longitude[0] +
          ((u.axes.longitude.at(-1)! - u.axes.longitude[0]) * i) / (side + 1);
        const lat =
          u.axes.latitude[0] +
          ((u.axes.latitude.at(-1)! - u.axes.latitude[0]) * j) / (side + 1);
        const path = integrateFlow(u, v, [lon, lat], layer);
        if (path.points.length > 1) paths.push(path);
      }
  return paths;
}
