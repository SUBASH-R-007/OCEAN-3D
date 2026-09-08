import type { Volume } from './ocean';
import { sameGrid, sampleField } from './flow.ts';

export type CurrentScope = 'column' | 'slice';
export type CurrentGlyph = {
  longitude: number;
  latitude: number;
  depth: number;
  u: number;
  v: number;
  speed: number;
};

// Concentrate inspection layers near the surface, while retaining the deepest
// available level. These are display samples, not additional source resolution.
export function currentDepths(
  field: Volume,
  scope: CurrentScope,
  depth: number,
  count = 12,
) {
  const axis = field.axes.depth,
    top = axis[0],
    bottom = axis.at(-1)!;
  if (scope === 'slice') return [Math.max(top, Math.min(bottom, depth))];
  if (count === 0) return [...axis];
  const n = Math.max(2, Math.min(24, Math.round(count)));
  return Array.from(
    { length: n },
    (_, i) => top + (bottom - top) * (i / (n - 1)) ** 2,
  );
}

export function sampleCurrent(
  u: Volume,
  v: Volume,
  lon: number,
  lat: number,
  depth: number,
): CurrentGlyph | null {
  const east = sampleField(u, lon, lat, depth),
    north = sampleField(v, lon, lat, depth);
  if (east === null || north === null) return null;
  return {
    longitude: lon,
    latitude: lat,
    depth,
    u: east,
    v: north,
    speed: Math.hypot(east, north),
  };
}

export function currentGlyphs(
  u: Volume,
  v: Volume,
  scope: CurrentScope,
  depth: number,
  layers = 12,
  budget = 2304,
) {
  if (!sameGrid(u, v))
    throw new Error(
      'Current components must share model, time and every coordinate.',
    );
  if (!Number.isInteger(budget) || budget < 4 || budget > 10000)
    throw new Error('Invalid current glyph budget.');
  const depths = currentDepths(u, scope, depth, layers);
  if (budget < depths.length * 4)
    throw new Error('Glyph budget is too small for the selected depths.');
  const side = Math.max(2, Math.floor(Math.sqrt(budget / depths.length)));
  const indices = (n: number) => {
    const count = Math.min(n, side);
    return Array.from({ length: count }, (_, i) =>
      Math.round((i * (n - 1)) / (count - 1)),
    );
  };
  const glyphs: CurrentGlyph[] = [];
  for (const z of depths)
    for (const y of indices(u.dimensions[1]))
      for (const x of indices(u.dimensions[0])) {
        const q = sampleCurrent(
          u,
          v,
          u.axes.longitude[x],
          u.axes.latitude[y],
          z,
        );
        if (q && q.speed > 1e-6) glyphs.push(q);
      }
  return {
    glyphs,
    depths,
    sampledPositions:
      Math.min(side, u.dimensions[0]) *
      Math.min(side, u.dimensions[1]) *
      depths.length,
  };
}

export function vectorScaleKm(field: Volume) {
  const latitude = (field.axes.latitude[0] + field.axes.latitude.at(-1)!) / 2;
  const width =
    (field.axes.longitude.at(-1)! - field.axes.longitude[0]) *
    111.32 *
    Math.cos((latitude * Math.PI) / 180);
  const height =
    (field.axes.latitude.at(-1)! - field.axes.latitude[0]) * 111.32;
  return Math.min(width, height) / 28;
}

// Same regional equirectangular projection used by the scene. Longitude
// displacement grows toward the poles for an equal physical eastward velocity.
export function projectedCurrent(field: Volume, glyph: CurrentGlyph) {
  const middle =
    ((field.axes.latitude[0] + field.axes.latitude.at(-1)!) * Math.PI) / 360;
  const latitude = (glyph.latitude * Math.PI) / 180;
  return [
    (glyph.u * Math.cos(middle)) / Math.max(1e-6, Math.cos(latitude)),
    glyph.v,
  ];
}
