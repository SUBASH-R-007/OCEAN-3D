import {
  observationOnly,
  profileChartRows,
  profileCsv,
  clippedInstrumentPath,
  arrangeInstrumentLabels,
} from '../lib/profiles.ts';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { evaluationRecord } from '../lib/evaluation.ts';

test('evaluation records remain unscored and reject invalid timing or empty evidence', () => {
  const result = evaluationRecord(
    'profile-evidence',
    'developer-practice',
    'P01',
    'Practice response, not a forecaster measurement.',
    1000,
    6500,
    { source: 'fixture' },
  );
  assert.equal(result.elapsed_seconds, 5.5);
  assert.equal(result.score, null);
  assert.equal(result.condition, 'developer-practice');
  for (const values of [
    [
      'profile-evidence',
      'ocean3d',
      'Actual Name',
      'Response with enough detail',
      1000,
      6500,
    ],
    ['profile-evidence', 'ocean3d', 'P01', 'Too short', 1000, 6500],
    [
      'profile-evidence',
      'ocean3d',
      'P01',
      'Response with enough detail',
      6500,
      1000,
    ],
  ])
    assert.throws(() => evaluationRecord(...values, {}));
});
import { isosurface } from '../lib/isosurface.ts';
import { validatedState, color, initial } from '../lib/ocean.ts';
import { integrateFlow, sampleField, seedFlow } from '../lib/flow.ts';
import {
  currentDepths,
  currentGlyphs,
  sampleCurrent,
} from '../lib/currents.ts';
import { clipSegment } from '../lib/geography.ts';
import { missionSegments } from '../lib/missions.ts';
import { decodeVolume, FrameCache } from '../lib/volumeProtocol.ts';
import { validRegion } from '../lib/region.ts';
import { subsetAtlas, subsetRelief } from '../lib/thermal.ts';
import {
  intersectRegion,
  latitudeLabel,
  longitudeLabel,
} from '../lib/geography.ts';

test('basin regions retain exact native frame, depth and count indices', () => {
  const values = Array.from({ length: 18 }, (_, i) => (i === 13 ? null : i));
  const a = {
    longitude: [50, 60, 70],
    latitude: [-10, 0, 10],
    depth: [5, 100],
    frames: [
      {
        time: '2026-01-15',
        temperature: values,
        local_count: values,
        influence_count: values,
      },
    ],
    schema: 'test',
    provenance: {},
    method: 'test',
  };
  const b = subsetAtlas(a, [60, 0, 70, 10]);
  assert.deepEqual(b.longitude, [60, 70]);
  assert.deepEqual(b.latitude, [0, 10]);
  assert.deepEqual(b.frames[0].temperature, [4, 5, 7, 8, null, 14, 16, 17]);
  assert.deepEqual(b.frames[0].local_count, b.frames[0].temperature);
  assert.throws(() => subsetAtlas(a, [0, 0, 5, 5]));
  assert.deepEqual(
    subsetRelief({ ...a, elevation: values.slice(0, 9) }, [60, 0, 70, 10])
      .elevation,
    [4, 5, 7, 8],
  );
  assert.deepEqual(
    intersectRegion([20, -20, 90, 20], [30, -10, 100, 30]),
    [30, -10, 90, 20],
  );
  assert.equal(latitudeLabel(-29.5), '29.5°S');
  assert.equal(longitudeLabel(300), '60.0°W');
});

function binaryFixture(values = [1, null, 3, 4, 5, 6, 7, 8]) {
  const meta = {
    model_id: 'fixture',
    variable: 'temperature',
    time: '2025-01-01T00:00:00Z',
    dimensions: [2, 2, 2],
    axes: { longitude: [80, 82], latitude: [10, 12], depth: [0, 100] },
    total_cells: 8,
    valid_cells: values.filter((v) => v !== null).length,
    encoding: { version: 1, dtype: '<f4', missing: 'NaN' },
  };
  const header = new TextEncoder().encode(JSON.stringify(meta));
  const length = header.length + ((4 - (header.length % 4)) % 4),
    buffer = new ArrayBuffer(8 + length + 32),
    bytes = new Uint8Array(buffer),
    view = new DataView(buffer);
  bytes.set([79, 67, 86, 49]);
  view.setUint32(4, length, true);
  bytes.fill(32, 8, 8 + length);
  bytes.set(header, 8);
  values.forEach((v, i) =>
    view.setFloat32(8 + length + i * 4, v === null ? NaN : v, true),
  );
  return buffer;
}

test('compact volume decoding preserves x-fast values and missing cells', () => {
  const decoded = decodeVolume(binaryFixture());
  assert.deepEqual(decoded.values, [1, null, 3, 4, 5, 6, 7, 8]);
  assert.deepEqual(decoded.axes.depth, [0, 100]);
  const invalid = binaryFixture();
  new DataView(invalid).setUint32(4, 1000000, true);
  assert.throws(() => decodeVolume(invalid), /metadata/);
  assert.throws(() => decodeVolume(binaryFixture().slice(0, -1)), /payload/);
  assert.throws(
    () => decodeVolume(binaryFixture([Infinity, 2, 3, 4, 5, 6, 7, 8])),
    /Infinite/,
  );
  const badMagic = binaryFixture();
  new Uint8Array(badMagic)[0] = 0;
  assert.throws(() => decodeVolume(badMagic), /Unsupported/);
});

test('frame memory accounting evicts least recently used data', () => {
  const frame = decodeVolume(binaryFixture());
  const cost =
    frame.values.length * 16 +
    JSON.stringify({ ...frame, values: [] }).length * 2;
  const cache = new FrameCache(cost * 2);
  cache.put('a', frame);
  cache.put('b', frame);
  cache.get('a');
  cache.put('c', frame);
  assert.equal(cache.get('b'), undefined);
  assert.equal(cache.get('a'), frame);
  assert.ok(cache.bytes <= cache.limit);
  cache.put('a', frame);
  assert.equal(cache.bytes, cost * 2);
});

test('saved geographic regions are finite ordered and model-bounded', () => {
  assert.equal(validRegion([82, 12, 86, 16], [80, 10, 90, 20]), true);
  for (const region of [
    [86, 12, 82, 16],
    [79, 12, 86, 16],
    [82, NaN, 86, 16],
    [82, 12, 86],
  ])
    assert.equal(validRegion(region, [80, 10, 90, 20]), false);
  assert.deepEqual(
    validatedState({ region: [82, 12, 86, 16] }).region,
    [82, 12, 86, 16],
  );
  assert.equal(validatedState({ region: [0, 0, 999, 30] }).region, null);
});

test('mission joins preserve time ordering and never bridge platforms or long gaps', () => {
  const cast = (id, trajectory_id, hour, longitude = 85) => ({
    id,
    trajectory_id,
    time: `2025-09-${hour > 48 ? '07' : '03'}T${String(hour % 24).padStart(2, '0')}:00:00Z`,
    longitude,
    latitude: 14,
  });
  const input = [
    cast('b', 'mission-a', 9),
    cast('a', 'mission-a', 6),
    cast('c', 'mission-b', 12),
    cast('d', 'mission-a', 72),
    cast('e', undefined, 13),
  ];
  assert.deepEqual(
    missionSegments(input).map((p) => p.map((x) => x.id)),
    [['a', 'b']],
  );
  assert.equal(input[0].id, 'b');
  assert.equal(
    missionSegments([cast('x', 'same', 6, 179), cast('y', 'same', 7, -179)])
      .length,
    0,
  );
});

test('saved variable plugins require catalog authorization', () => {
  assert.equal(
    validatedState({ variable: 'oxygen' }).variable,
    initial.variable,
  );
  assert.equal(
    validatedState({ variable: 'oxygen' }, ['oxygen']).variable,
    'oxygen',
  );
  assert.equal(
    validatedState({ variable: '__proto__' }, ['__proto__']).variable,
    initial.variable,
  );
});
import { sectionMesh, triangleNormals } from '../lib/sections.ts';
import {
  firstDownwardCrossing,
  pairedChange,
  surfaceGeometry,
  depthLens,
} from '../lib/thermal.ts';

test('first isotherm crossing is analytic, directional and native-bracket bounded', () => {
  const c = firstDownwardCrossing([5, 50, 100, 150], [29, 26, 21, 16], 20);
  assert.equal(c.depth, 110);
  assert.deepEqual(c.bracket, [100, 150]);
  assert.equal(
    firstDownwardCrossing([5, 50, 100], [19, 24, 18], 20).reason,
    'surface_below',
  );
  assert.equal(
    firstDownwardCrossing([5, 50, 100, 150], [25, 19, 25, 18], 20).depth,
    42.5,
  );
  assert.equal(firstDownwardCrossing([5, 50], [20, 18], 20).depth, 5);
  assert.equal(
    firstDownwardCrossing([5, 50], [22, 21], 20).reason,
    'not_reached',
  );
});
test('missing levels and large gaps censor first-crossing evidence', () => {
  assert.equal(
    firstDownwardCrossing([5, 50, 100, 150], [29, null, 23, 18], 20).reason,
    'missing',
  );
  assert.equal(
    firstDownwardCrossing([5, 50, 300], [29, 23, 18], 20).reason,
    'gap',
  );
  assert.equal(firstDownwardCrossing([5, 50], [29, NaN], 20).depth, null);
});
test('paired native-column changes retain sign, support minima and unavailable cells', () => {
  const atlas = {
    longitude: [80, 81],
    latitude: [10, 11],
    depth: [0, 100],
    frames: [
      {
        temperature: [30, 30, 30, 30, 10, 10, 10, 10],
        local_count: [2, 2, 2, 2, 1, 0, 1, 1],
        influence_count: Array(8).fill(8),
      },
      {
        temperature: [30, 30, 30, null, 15, 5, 20, null],
        local_count: Array(8).fill(1),
        influence_count: Array(8).fill(5),
      },
    ],
  };
  const result = pairedChange(atlas, 0, 1, 20);
  assert.equal(result.count, 3);
  assert.equal(result.localCount, 2);
  assert.ok(Math.abs(result.cells[0].delta - 50 / 3) < 1e-12);
  assert.equal(result.cells[1].delta, -10);
  assert.equal(result.cells[2].delta, 50);
  assert.equal(result.cells[3].delta, null);
  assert.equal(result.largest, 2);
  assert.ok(Math.abs(result.median - 50 / 3) < 1e-12);
});
test('thermal surface refinement reproduces a bilinear plane and leaves native holes open', () => {
  const mesh = surfaceGeometry([80, 81], [10, 11], [50, 70, 80, 100], 4);
  assert.equal(mesh.polys.length, 32 * 4);
  for (let i = 0; i < mesh.points.length; i += 3)
    assert.ok(
      Math.abs(
        mesh.points[i + 2] -
          (50 + 20 * (mesh.points[i] - 80) + 30 * (mesh.points[i + 1] - 10)),
      ) < 1e-10,
    );
  assert.equal(
    surfaceGeometry([80, 81], [10, 11], [50, null, 80, 100], 4).polys.length,
    0,
  );
});
test('focus depth lens is continuous, monotonic and uses the same transform for terrain', () => {
  assert.equal(depthLens(500, 1000), -500);
  assert.equal(depthLens(1500, 1000), -535);
  assert.equal(depthLens(-1000, 1000), 35);
  assert.ok(
    Math.abs(depthLens(500 - 1e-8, 1000) - depthLens(500 + 1e-8, 1000)) < 1e-7,
  );
  const values = [0, 100, 500, 1000, 5000].map((d) => depthLens(d, 1000));
  assert.ok(values.slice(1).every((v, i) => v < values[i]));
});

test('intersecting sections reproduce affine fields and geographic positions', () => {
  const field = velocity(0);
  field.values = [0, 10, 20, 30, 100, 110, 120, 130];
  const mesh = sectionMesh(field, 'longitude', 25);
  assert.equal(mesh.position, 82.5);
  assert.deepEqual(mesh.values, [2.5, 22.5, 102.5, 122.5]);
  assert.equal(mesh.polys.length, 8);
  assert.deepEqual(mesh.points.slice(0, 3), [82.5, 0, 0]);
  field.values[0] = null;
  assert.equal(sectionMesh(field, 'longitude', 25).polys.length, 0);
  assert.equal(sectionMesh(field, 'longitude', 100).polys.length, 8);
});

test('surface normals are finite unit vectors and section controls are bounded', () => {
  const normals = triangleNormals(
    new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    new Uint32Array([3, 0, 1, 2]),
  );
  assert.deepEqual([...normals], [0, 0, 1, 0, 0, 1, 0, 0, 1]);
  const s = validatedState({
    mode: 'sections',
    variable: 'analyzed_temperature',
    sectionX: 150,
    sectionY: -2,
    depthWindow: 'full',
  });
  assert.equal(s.sectionX, 100);
  assert.equal(s.sectionY, 0);
  assert.equal(s.mode, 'sections');
  assert.equal(s.depthWindow, 'full');
});

function velocity(value) {
  return {
    model_id: 'test',
    time: '2025-01-01T00:00:00Z',
    dimensions: [2, 2, 2],
    axes: { longitude: [80, 90], latitude: [0, 20], depth: [0, 100] },
    values: Array(8).fill(value),
  };
}
test('current column glyphs retain depth shear, signs, masks and matched times', () => {
  const u = velocity(1),
    v = velocity(0);
  u.values = [1, 1, 1, 1, -1, -1, -1, -1];
  const column = currentGlyphs(u, v, 'column', 20, 6);
  assert.equal(column.depths[0], 0);
  assert.equal(column.depths.at(-1), 100);
  assert.equal(column.glyphs.find((p) => p.depth === 0).u, 1);
  assert.equal(column.glyphs.find((p) => p.depth === 100).u, -1);
  const slice = currentGlyphs(u, v, 'slice', 75, 6);
  assert.deepEqual(slice.depths, [75]);
  assert.ok(slice.glyphs.every((p) => p.u === -0.5 && p.depth === 75));
  assert.deepEqual(currentDepths(u, 'column', 0, 0), [0, 100]);
  assert.throws(
    () => currentGlyphs(u, { ...v, time: 'different' }, 'column', 0),
    /share/,
  );
  u.values[0] = null;
  assert.equal(sampleCurrent(u, v, 80, 0, 0), null);
  assert.ok(
    !currentGlyphs(u, v, 'column', 0, 0).glyphs.some(
      (p) => p.longitude === 80 && p.latitude === 0 && p.depth === 0,
    ),
  );
});
test('column streamlines retain each seed depth and do not invent vertical velocity', () => {
  const u = velocity(0.01),
    v = velocity(0);
  const paths = seedFlow(u, v, 0, [0, 50, 100]);
  assert.deepEqual(
    [...new Set(paths.map((p) => p.points[0].depth))],
    [0, 50, 100],
  );
  assert.ok(
    paths.every((p) => p.points.every((q) => q.depth === p.points[0].depth)),
  );
  assert.equal(
    validatedState({ currentScope: 'slice', currentLayers: 24 }).currentScope,
    'slice',
  );
  assert.equal(validatedState({ currentLayers: 999 }).currentLayers, 12);
});
test('RK4 geographic current conversion matches analytical zonal displacement', () => {
  const u = velocity(1),
    v = velocity(0),
    path = integrateFlow(u, v, [85, 10], 50, 24),
    end = path.points.at(-1);
  const expected =
    85 + ((86400 / (6371000 * Math.cos((10 * Math.PI) / 180))) * 180) / Math.PI;
  assert.ok(Math.abs(end.longitude - expected) < 1e-10);
  assert.equal(end.latitude, 10);
  assert.equal(end.depth, 50);
  assert.equal(end.elapsed_s, 86400);
  const half = integrateFlow(u, v, [85, 10], 50, 24, 1800).points.at(-1);
  assert.ok(Math.abs(end.longitude - half.longitude) < 1e-10);
});
test('flow masks, stagnation and component-grid mismatch are explicit', () => {
  const u = velocity(1),
    v = velocity(0);
  u.values[0] = null;
  assert.equal(sampleField(u, 80, 0, 0), null);
  assert.equal(sampleField(u, 90, 20, 100), 1);
  assert.equal(
    integrateFlow(u, v, [85, 10], 50, 24).stop,
    'missing_or_boundary',
  );
  assert.equal(integrateFlow(v, v, [85, 10], 50, 24).stop, 'stagnant');
  assert.throws(
    () => integrateFlow(v, { ...v, time: '2025-01-02' }, [85, 10], 50),
    /share/,
  );
});
test('coastline clipping retains real intersections and rejects outside segments', () => {
  assert.deepEqual(clipSegment([-1, 0.5], [2, 0.5], [0, 0, 1, 1]), [
    [0, 0.5],
    [1, 0.5],
  ]);
  assert.equal(clipSegment([-1, 2], [2, 2], [0, 0, 1, 1]), null);
});

test('RK4 converges in a spatially varying field and reports its step budget', () => {
  const v = velocity(0),
    u = velocity(0);
  // dx/dt = k(x-80), latitude fixed at zero; exact exponential solution.
  const k = 1e-5,
    metresPerDegree = (6371000 * Math.PI) / 180;
  u.values = [
    0,
    10 * k * metresPerDegree,
    0,
    10 * k * metresPerDegree,
    0,
    10 * k * metresPerDegree,
    0,
    10 * k * metresPerDegree,
  ];
  const expected = 80 + Math.exp(k * 86400);
  const coarse = integrateFlow(u, v, [81, 0], 50, 24, 3600).points.at(-1);
  const fine = integrateFlow(u, v, [81, 0], 50, 24, 1800).points.at(-1);
  assert.ok(
    Math.abs(fine.longitude - expected) <
      Math.abs(coarse.longitude - expected) / 10,
  );
  assert.ok(Math.abs(fine.longitude - expected) < 2e-8);
  assert.equal(
    integrateFlow(velocity(1), v, [85, 10], 50, 24, 1).stop,
    'integration_limit',
  );
});

test('isosurfaces through exact grid vertices contain no degenerate triangles', () => {
  const field = { dimensions: [2, 2, 2], values: [0, 1, 1, 2, 1, 2, 2, 3] };
  const mesh = isosurface(field, 1, [1, 1, 1], [0, 0, 0]);
  assert.ok(mesh.polys.length > 0);
  for (let i = 0; i < mesh.points.length; i += 9) {
    const a = [0, 1, 2].map((k) => mesh.points[i + 3 + k] - mesh.points[i + k]);
    const b = [0, 1, 2].map((k) => mesh.points[i + 6 + k] - mesh.points[i + k]);
    assert.ok(
      Math.hypot(
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
      ) > 0,
    );
  }
});

test('contour of x has vertices only on the requested x plane', () => {
  const field = { dimensions: [2, 2, 2], values: [0, 1, 0, 1, 0, 1, 0, 1] };
  const mesh = isosurface(field, 0.5, [2, 3, 4], [10, 20, 30]);
  assert.ok(mesh.polys.length > 0);
  for (let i = 0; i < mesh.points.length; i += 3) {
    assert.equal(mesh.points[i], 11);
    assert.ok(mesh.points[i + 1] >= 20 && mesh.points[i + 1] <= 23);
    assert.ok(mesh.points[i + 2] >= 30 && mesh.points[i + 2] <= 34);
  }
});
test('masked cells and absent contours produce no spurious surfaces', () => {
  assert.equal(
    isosurface(
      { dimensions: [2, 2, 2], values: [null, 1, 0, 1, 0, 1, 0, 1] },
      0.5,
      [1, 1, 1],
      [0, 0, 0],
    ).points.length,
    0,
  );
  assert.equal(
    isosurface(
      { dimensions: [2, 2, 2], values: [0, 1, 0, 1, 0, 1, 0, 1] },
      2,
      [1, 1, 1],
      [0, 0, 0],
    ).points.length,
    0,
  );
});
test('view links reject invalid bounds and prototype keys', () => {
  const state = validatedState({
    min: 10,
    max: 5,
    palette: '__proto__',
    depth: -100,
    opacity: 50,
    index: 2.7,
    variable: 'unknown',
  });
  assert.ok(state.min < state.max);
  assert.equal(state.palette, 'thermal');
  assert.equal(state.depth, 0);
  assert.equal(state.opacity, 1);
  assert.equal(state.index, 3);
  assert.equal(state.variable, initial.variable);
});
test('log palettes and range clamping are finite', () => {
  assert.match(color(1, 0.1, 10, 'viridis', true), /^rgb\(/);
  assert.equal(color(-1, 0, 10), color(0, 0, 10));
  assert.equal(color(100, 0, 10), color(10, 0, 10));
});

import {
  colorRgb,
  colorRangeError,
  encodeDisplayScalars,
  scaleTicks,
  transferStops,
} from '../lib/colorScale.ts';

test('linear and logarithmic legends match palette positions over multiple decades', () => {
  const scale = { min: 0.001, max: 10, palette: 'viridis', log: true };
  assert.deepEqual(
    scaleTicks(scale).map((t) => t.value),
    [0.001, 0.01, 0.1, 1, 10],
  );
  assert.deepEqual(
    scaleTicks({ ...scale, min: -2, max: 2, log: false }).map((t) => t.value),
    [-2, -1, 0, 1, 2],
  );
  assert.deepEqual(colorRgb(0.001, 0.001, 10, 'viridis', true), [68, 1, 84]);
  assert.deepEqual(colorRgb(10, 0.001, 10, 'viridis', true), [253, 231, 37]);
  assert.deepEqual(
    colorRgb(0.1, 0.001, 10, 'viridis', true),
    colorRgb(0.5, 0, 1, 'viridis'),
  );
  assert.deepEqual(colorRgb(-1, 0.001, 10, 'viridis', true), [23, 38, 54]);
  assert.equal(color(0.5, 0, 1, '__proto__'), color(0.5, 0, 1, 'thermal'));
});

test('GPU display encoding masks nonpositive log samples without changing source values', () => {
  const source = [-4, 0, 0.000001, 0.001, 1, 1000, null, NaN];
  const copy = [...source];
  const encoded = encodeDisplayScalars(source, true);
  assert.deepEqual([...encoded.values].slice(2, 6), [-6, -3, 0, 3]);
  assert.equal(encoded.min, -6);
  assert.equal(encoded.max, 3);
  for (const index of [0, 1, 6, 7])
    assert.equal(encoded.values[index], encoded.sentinel);
  assert.ok(encoded.sentinel < encoded.min);
  assert.equal(encoded.excluded, 2);
  assert.deepEqual(source, copy);
  const linear = encodeDisplayScalars(source, false);
  assert.equal(linear.values[0], -4);
  assert.equal(linear.values[1], 0);
  const empty = encodeDisplayScalars([0, -1, null], true);
  assert.ok([...empty.values].every((x) => x === empty.sentinel));
  const constant = encodeDisplayScalars([1e8, 1e8, null], false);
  assert.ok(constant.sentinel < constant.min);
});

test('GPU transfer knots reproduce log palette colors and clamped endpoints', () => {
  const scale = { min: 0.001, max: 10, palette: 'viridis', log: true };
  const nodes = transferStops(scale, { min: -6, max: 3 });
  assert.equal(nodes[0].x, -6);
  assert.equal(nodes.at(-1).x, 3);
  assert.deepEqual(nodes[0].rgb, [68, 1, 84]);
  assert.deepEqual(nodes.at(-1).rgb, [253, 231, 37]);
  for (const node of nodes)
    assert.deepEqual(
      node.rgb,
      colorRgb(10 ** node.x, scale.min, scale.max, scale.palette, true),
    );
  assert.equal(nodes.length, 8);
});

test('nonpositive log section corners leave a gap instead of invalid colored faces', () => {
  const field = velocity(1);
  assert.equal(sectionMesh(field, 'longitude', 0, true).polys.length, 8);
  field.values[0] = 0;
  assert.equal(sectionMesh(field, 'longitude', 0, true).polys.length, 0);
  assert.equal(sectionMesh(field, 'longitude', 0, false).polys.length, 8);
});

test('range drafts reject blank, inverted, nonfinite and nonpositive log limits', () => {
  for (const [min, max, log] of [
    ['', '5', false],
    ['6', '5', false],
    ['5', '5', false],
    ['0', '5', true],
    ['-2', '5', true],
    ['1e309', '5', false],
  ])
    assert.ok(colorRangeError(min, max, log));
  assert.equal(colorRangeError('1e-6', '1e3', true), '');
  assert.equal(colorRangeError('-2', '2', false), '');
});

test('saved links retain independent opacity, exaggeration and scientific color limits', () => {
  const state = validatedState({
    opacity: 0,
    instrumentOpacity: -1,
    currentOpacity: 2,
    flowOpacity: 0.17,
    exaggeration: 800,
    min: 1e-6,
    max: 1e6,
    log: true,
  });
  assert.equal(state.opacity, 0);
  assert.equal(state.instrumentOpacity, 0);
  assert.equal(state.currentOpacity, 1);
  assert.equal(state.flowOpacity, 0.17);
  assert.equal(state.exaggeration, 600);
  assert.equal(state.min, 1e-6);
  assert.equal(state.max, 1e6);
  assert.equal(state.log, true);
  assert.equal(validatedState({ exaggeration: 0 }).exaggeration, 1);
  assert.equal(validatedState({}).instrumentOpacity, initial.instrumentOpacity);
  assert.equal(validatedState({ min: -1, max: 2, log: true }).log, false);
});

import { timelineIndices } from '../lib/timeline.ts';
import { openConnection } from '../lib/connection.ts';

test('required scientific deployments never substitute a bundled demo after API failure', async () => {
  const calls = [];
  const unavailable = async (url) => {
    calls.push(url);
    return new Response('unavailable', { status: 503 });
  };
  await assert.rejects(
    openConnection(true, true, unavailable),
    /Scientific API unavailable/,
  );
  assert.deepEqual(calls, ['/api/health']);
  await assert.rejects(
    openConnection(true, false, async () => new Response('', { status: 401 })),
    /authentication is required/,
  );
});

test('bundled deployments avoid API probes and readonly capabilities disable writes', async () => {
  const catalog = { models: [{ id: 'fixture' }], profiles: [] };
  const calls = [];
  const request = async (url) => {
    calls.push(url);
    return Response.json(
      url === '/api/health'
        ? { mode: 'scientific-api', status: 'ok' }
        : url === '/api/ready'
          ? {
              status: 'ready',
              capabilities: { imports: false, upstream_acquisition: false },
            }
          : catalog,
    );
  };
  const bundle = await openConnection(false, false, request);
  assert.equal(bundle.connected, false);
  assert.deepEqual(calls, ['/demo/catalog.json']);
  calls.length = 0;
  const replica = await openConnection(true, true, request);
  assert.equal(replica.connected, true);
  assert.equal(replica.writable, false);
  assert.equal(replica.upstream, false);
  assert.deepEqual(calls, ['/api/health', '/api/ready', '/api/catalog']);
});

test('ready and catalog contracts are checked before marking an API connected', async () => {
  const response = async (url) =>
    Response.json(
      url === '/api/health'
        ? { mode: 'scientific-api', status: 'ok' }
        : { status: 'not-ready' },
    );
  await assert.rejects(
    openConnection(true, true, response),
    /catalog is not ready/,
  );
  const invalid = async (url) =>
    Response.json(
      url === '/api/health'
        ? { mode: 'scientific-api', status: 'ok' }
        : url === '/api/ready'
          ? { status: 'ready' }
          : {},
    );
  await assert.rejects(openConnection(true, true, invalid), /invalid catalog/);
});
test('large timelines have bounded labels and retain first and final frames', () => {
  assert.deepEqual(timelineIndices(1), [0]);
  assert.deepEqual(timelineIndices(3), [0, 1, 2]);
  assert.deepEqual(timelineIndices(100000), [0, 25000, 50000, 74999, 99999]);
  assert.deepEqual(timelineIndices(0), []);
});

test('independent instrument profiles retain QC gaps, timestamps and source values', () => {
  const profile = {
    id: 'ARGO-TEST',
    instrument: 'Argo',
    time: '2023-09-01T12:00:00Z',
    longitude: 85,
    latitude: 14,
    synthetic: false,
    data_mode: 'D',
    source: 'test',
    samples: [
      {
        depth: 0,
        variable: 'chlorophyll',
        value: 1,
        qc: 1,
        source_qc: 2,
        adjusted: false,
        error: null,
      },
      {
        depth: 10,
        variable: 'chlorophyll',
        value: 99,
        qc: 4,
        source_qc: 4,
        adjusted: false,
        error: null,
      },
      {
        depth: 20,
        variable: 'chlorophyll',
        value: 2,
        qc: 2,
        adjusted: false,
        error: null,
      },
      {
        depth: 30,
        variable: 'chlorophyll',
        value: 3,
        qc: 1,
        adjusted: false,
        error: null,
        longitude: 85.1,
        latitude: 14.1,
        time: '2023-09-01T12:01:00Z',
      },
    ],
  };
  const strict = observationOnly(profile, 'chlorophyll', 'strict', {});
  assert.deepEqual(
    profileChartRows(strict).map((p) => p.value),
    [1, null, null, 3],
  );
  assert.equal(strict.metrics.count, 0);
  assert.equal(strict.metrics.qc_excluded, 2);
  assert.ok(strict.pairs.every((p) => p.model === null));
  assert.equal(strict.profile.time, profile.time);
  const relaxed = observationOnly(profile, 'chlorophyll', 'lenient', {});
  assert.deepEqual(
    profileChartRows(relaxed).map((p) => p.value),
    [1, null, 2, 3],
  );
  const csv = profileCsv(strict, 'mg/m³');
  assert.equal(csv.split('\n').length, 5);
  assert.ok(csv.includes('12:01:00Z'));
  assert.ok(csv.includes(',99,,,4,4,"false",'));
  assert.ok(csv.includes('"mg/m³"'));
  assert.equal(strict.samples[1].value, 99);
});

test('native instrument paths clip in longitude, latitude and depth without bridging gaps', () => {
  const path = [
    { longitude: -1, latitude: 0, depth: -10, time: 't' },
    { longitude: 2, latitude: 0, depth: 200, time: 't' },
    { longitude: 0, latitude: 0, depth: 20, time: 't', break_before: true },
  ];
  const segments = clippedInstrumentPath(path, [0, -1, 1, 1], 0, 100);
  assert.equal(segments.length, 1);
  assert.ok(Math.abs(segments[0][0][0]) < 1e-12);
  assert.ok(Math.abs(segments[0][0][2] - 60) < 1e-12);
  assert.equal(segments[0][1][2], 100);
  assert.equal(
    clippedInstrumentPath(
      [
        { longitude: 9, latitude: 9, depth: 0 },
        { longitude: 9, latitude: 9, depth: 20 },
      ],
      [0, -1, 1, 1],
      0,
      100,
    ).length,
    0,
  );
});

import { timeSeriesRows, instrumentIsFresh } from '../lib/profiles.ts';

test('station marker freshness uses actual timestamps rather than a continuous deployment span', () => {
  const station = {
    time: '2025-01-01T00:00:00Z',
    sample_times: ['2025-01-01T00:00:00Z', '2025-09-03T00:00:00Z'],
  };
  assert.equal(instrumentIsFresh(station, '2025-09-03T00:00:00Z'), true);
  assert.equal(instrumentIsFresh(station, '2025-06-03T00:00:00Z'), false);
  assert.equal(
    instrumentIsFresh({ time: station.time }, '2025-01-01T12:00:00Z'),
    true,
  );
});

test('station time series sort timestamps without shifting matched values or closing QC gaps', () => {
  const data = {
    profile: { time: '2025-09-03T00:00:00Z' },
    method: { qc_flags: [1] },
    samples: [
      { time: '2025-09-03T12:00:00Z', depth: 50, value: 27, qc: 1 },
      { time: '2025-09-03T00:00:00Z', depth: 50, value: 28, qc: 1 },
      { time: '2025-09-03T06:00:00Z', depth: 50, value: 99, qc: 4 },
    ],
    pairs: [
      { model: 27.1, residual: 0.1 },
      { model: 28.2, residual: 0.2 },
    ],
  };
  const rows = timeSeriesRows(data);
  assert.deepEqual(
    rows.map((r) => r.timestamp),
    [0, 6, 12].map((h) => Date.parse('2025-09-03T00:00:00Z') + h * 3600000),
  );
  assert.deepEqual(
    rows.map((r) => r.value),
    [28, null, 27],
  );
  assert.deepEqual(
    rows.map((r) => r.model),
    [28.2, null, 27.1],
  );
  assert.deepEqual(
    data.samples.map((r) => r.value),
    [27, 28, 99],
  );
});

test('surface-current series retains nominal depth and exact sample timestamps', () => {
  const data = {
    profile: { time: '2025-09-03T00:00:00Z' },
    method: { qc_flags: [1] },
    samples: [
      { time: '2025-09-03T01:00:00Z', depth: 0, value: 0.2, qc: 1 },
      { time: 'invalid', depth: 0, value: 0.3, qc: 1 },
    ],
    pairs: [
      { model: null, residual: null },
      { model: null, residual: null },
    ],
  };
  const rows = timeSeriesRows(data);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].depth, 0);
  assert.equal(rows[0].timestamp, Date.parse('2025-09-03T01:00:00Z'));
  assert.equal(rows[0].model, null);
});

test('nearby instrument labels preserve true anchors and remain separately selectable', () => {
  const placed = arrangeInstrumentLabels(
    Array.from({ length: 4 }, (_, i) => ({ id: String(i), x: 100, y: 100 })),
    400,
    300,
  );
  assert.equal(placed.length, 4);
  assert.equal(new Set(placed.map((p) => p.y)).size, 4);
  assert.ok(
    placed.every(
      (p) => p.anchorX === 100 && p.anchorY === 100 && p.y >= 14 && p.y <= 286,
    ),
  );
  assert.deepEqual(arrangeInstrumentLabels([{ x: -2, y: 4 }], 400, 300), []);
  const state = validatedState({
    ...initial,
    observationVariable: 'chlorophyll',
  });
  assert.equal(state.observationVariable, 'chlorophyll');
  assert.equal(
    validatedState({ ...initial, observationVariable: 'arbitrary' })
      .observationVariable,
    '',
  );
});
