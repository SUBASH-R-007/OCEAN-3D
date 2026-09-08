import type { Volume } from './ocean';
import { sampleField } from './flow.ts';

// A cross-section is sampled in geographic coordinates before display exaggeration.
// A face is emitted only when all four corners are supported; holes stay open.
export function sectionMesh(
  field: Volume,
  axis: 'longitude' | 'latitude',
  percent: number,
  positiveOnly = false,
) {
  const fixed = field.axes[axis];
  const position =
    fixed[0] +
    ((fixed.at(-1)! - fixed[0]) * Math.max(0, Math.min(100, percent))) / 100;
  const across = field.axes[axis === 'longitude' ? 'latitude' : 'longitude'];
  const points: number[] = [],
    values: number[] = [],
    polys: number[] = [];
  for (const depth of field.axes.depth)
    for (const along of across) {
      const lon = axis === 'longitude' ? position : along;
      const lat = axis === 'latitude' ? position : along;
      points.push(lon, lat, depth);
      const value = sampleField(field, lon, lat, depth) ?? NaN;
      values.push(positiveOnly && value <= 0 ? NaN : value);
    }
  const n = across.length;
  for (let z = 0; z < field.axes.depth.length - 1; z++)
    for (let x = 0; x < n - 1; x++) {
      const ids = [
        z * n + x,
        z * n + x + 1,
        (z + 1) * n + x + 1,
        (z + 1) * n + x,
      ];
      if (ids.every((i) => Number.isFinite(values[i])))
        polys.push(3, ids[0], ids[1], ids[2], 3, ids[0], ids[2], ids[3]);
    }
  return { position, points, values, polys: new Uint32Array(polys) };
}

export function triangleNormals(points: Float32Array, polys: Uint32Array) {
  const normals = new Float32Array(points.length);
  for (let i = 0; i < polys.length; i += 4) {
    const a = polys[i + 1] * 3,
      b = polys[i + 2] * 3,
      c = polys[i + 3] * 3;
    const u = [0, 1, 2].map((k) => points[b + k] - points[a + k]);
    const v = [0, 1, 2].map((k) => points[c + k] - points[a + k]);
    const n = [
      u[1] * v[2] - u[2] * v[1],
      u[2] * v[0] - u[0] * v[2],
      u[0] * v[1] - u[1] * v[0],
    ];
    const length = Math.hypot(...n);
    if (length > 0)
      for (const id of [a, b, c])
        for (let k = 0; k < 3; k++) normals[id + k] += n[k] / length;
  }
  for (let i = 0; i < normals.length; i += 3) {
    const length = Math.hypot(normals[i], normals[i + 1], normals[i + 2]);
    if (length > 0) for (let k = 0; k < 3; k++) normals[i + k] /= length;
  }
  return normals;
}
