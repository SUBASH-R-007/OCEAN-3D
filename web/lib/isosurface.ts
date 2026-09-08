// Marching tetrahedra; skip every cell containing missing values, avoiding false land surfaces.
import type { Volume } from './ocean';
export function isosurface(
  field: Volume,
  level: number,
  spacing: number[],
  origin: number[],
) {
  const [nx, ny, nz] = field.dimensions,
    points: number[] = [],
    polys: number[] = [];
  const corners = [
    [0, 0, 0],
    [1, 0, 0],
    [1, 1, 0],
    [0, 1, 0],
    [0, 0, 1],
    [1, 0, 1],
    [1, 1, 1],
    [0, 1, 1],
  ];
  const tets = [
    [0, 5, 1, 6],
    [0, 1, 2, 6],
    [0, 2, 3, 6],
    [0, 3, 7, 6],
    [0, 7, 4, 6],
    [0, 4, 5, 6],
  ];
  const edges = [
    [0, 1],
    [0, 2],
    [0, 3],
    [1, 2],
    [1, 3],
    [2, 3],
  ];
  for (let z = 0; z < nz - 1; z++)
    for (let y = 0; y < ny - 1; y++)
      for (let x = 0; x < nx - 1; x++) {
        const vals = corners.map(
          ([dx, dy, dz]) =>
            field.values[(nz - 1 - z - dz) * nx * ny + (y + dy) * nx + x + dx],
        );
        if (vals.some((v) => v === null || !Number.isFinite(v))) continue;
        for (const tet of tets) {
          const hits: number[][] = [];
          for (const [a, b] of edges) {
            const ia = tet[a],
              ib = tet[b],
              va = vals[ia]!,
              vb = vals[ib]!;
            if (va < level === vb < level) continue;
            const f = (level - va) / (vb - va);
            const hit = corners[ia].map(
              (v, k) =>
                origin[k] +
                ([x, y, z][k] + v + (corners[ib][k] - v) * f) * spacing[k],
            );
            // A contour through a vertex may hit it from several edges.
            if (
              !hits.some((p) => p.every((v, k) => Math.abs(v - hit[k]) < 1e-10))
            )
              hits.push(hit);
          }
          if (hits.length === 4) {
            // Sort the planar quad around its centroid to avoid crossing its diagonal.
            const c = [0, 1, 2].map(
                (k) => hits.reduce((s, p) => s + p[k], 0) / 4,
              ),
              u = hits[0].map((v, k) => v - c[k]);
            const b = hits[1].map((v, k) => v - c[k]),
              n = [
                u[1] * b[2] - u[2] * b[1],
                u[2] * b[0] - u[0] * b[2],
                u[0] * b[1] - u[1] * b[0],
              ],
              v = [
                n[1] * u[2] - n[2] * u[1],
                n[2] * u[0] - n[0] * u[2],
                n[0] * u[1] - n[1] * u[0],
              ];
            const norm = Math.hypot(...v);
            const un = Math.hypot(...u);
            hits.sort(
              (a, b) =>
                Math.atan2(
                  a.reduce((s, q, k) => s + ((q - c[k]) * v[k]) / norm, 0),
                  a.reduce((s, q, k) => s + ((q - c[k]) * u[k]) / un, 0),
                ) -
                Math.atan2(
                  b.reduce((s, q, k) => s + ((q - c[k]) * v[k]) / norm, 0),
                  b.reduce((s, q, k) => s + ((q - c[k]) * u[k]) / un, 0),
                ),
            );
          }
          for (let j = 1; j < hits.length - 1; j++) {
            const a = hits[j].map((v, k) => v - hits[0][k]),
              b = hits[j + 1].map((v, k) => v - hits[0][k]);
            if (
              Math.hypot(
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0],
              ) < 1e-12
            )
              continue;
            const start = points.length / 3;
            points.push(...hits[0], ...hits[j], ...hits[j + 1]);
            polys.push(3, start, start + 1, start + 2);
          }
        }
      }
  return { points: new Float32Array(points), polys: new Uint32Array(polys) };
}
