export type Point2 = [number, number];
export type Coastline = Point2[][];
let cache: Promise<Coastline> | null = null;
export function loadCoastline() {
  cache ??= fetch('/geography/coastline.geojson')
    .then((r) => {
      if (!r.ok) throw new Error('Coastline unavailable');
      return r.json();
    })
    .then((raw) =>
      (
        raw as {
          features: {
            geometry: { type: string; coordinates: Point2[] | Point2[][] };
          }[];
        }
      ).features.flatMap((f) =>
        f.geometry.type === 'LineString'
          ? [f.geometry.coordinates as Point2[]]
          : (f.geometry.coordinates as Point2[][]),
      ),
    );
  return cache;
}
// Liang–Barsky clipping preserves the actual segment at regional boundaries.
export function clipSegment(
  a: Point2,
  b: Point2,
  bounds: number[],
): [Point2, Point2] | null {
  const [w, s, e, n] = bounds,
    dx = b[0] - a[0],
    dy = b[1] - a[1];
  let lo = 0,
    hi = 1;
  const p = [-dx, dx, -dy, dy],
    q = [a[0] - w, e - a[0], a[1] - s, n - a[1]];
  for (let i = 0; i < 4; i++) {
    if (p[i] === 0) {
      if (q[i] < 0) return null;
      continue;
    }
    const t = q[i] / p[i];
    if (p[i] < 0) lo = Math.max(lo, t);
    else hi = Math.min(hi, t);
    if (lo > hi) return null;
  }
  return [
    [a[0] + lo * dx, a[1] + lo * dy],
    [a[0] + hi * dx, a[1] + hi * dy],
  ];
}
export const regions = [
  { id: 'indian', label: 'Indian Ocean', bounds: [30.5, -29.5, 119.5, 29.5] },
  { id: 'arabian', label: 'Arabian Sea', bounds: [50, -2, 78, 27] },
  { id: 'bay', label: 'Bay of Bengal', bounds: [79.5, 5.5, 95.5, 22.5] },
  { id: 'islands', label: 'Andaman & Nicobar', bounds: [90, 5, 99, 17] },
  {
    id: 'lakshadweep',
    label: 'Lakshadweep & west coast',
    bounds: [68, 5, 78, 22],
  },
  {
    id: 'equatorial',
    label: 'Equatorial Indian Ocean',
    bounds: [40, -10, 110, 10],
  },
  { id: 'south', label: 'Southern Indian Ocean', bounds: [35, -29.5, 115, -5] },
];
export function intersectRegion(a: number[], b: number[]): number[] | null {
  const r = [
    Math.max(a[0], b[0]),
    Math.max(a[1], b[1]),
    Math.min(a[2], b[2]),
    Math.min(a[3], b[3]),
  ];
  return r[0] < r[2] && r[1] < r[3] ? r : null;
}
export const longitudeLabel = (n: number) =>
  `${Math.abs(n > 180 ? n - 360 : n).toFixed(1)}°${(n > 180 ? n - 360 : n) < 0 ? 'W' : 'E'}`;
export const latitudeLabel = (n: number) =>
  `${Math.abs(n).toFixed(1)}°${n < 0 ? 'S' : 'N'}`;
