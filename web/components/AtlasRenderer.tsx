'use client';
/* oxlint-disable react/react-compiler -- Effects synchronize an owned VTK scene. */
import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import '@kitware/vtk.js/Rendering/Profiles/Geometry';
import vtkGenericRenderWindow from '@kitware/vtk.js/Rendering/Misc/GenericRenderWindow';
import vtkPolyData from '@kitware/vtk.js/Common/DataModel/PolyData';
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray';
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper';
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor';
import vtkCellPicker from '@kitware/vtk.js/Rendering/Core/CellPicker';
import vtkCoordinate from '@kitware/vtk.js/Rendering/Core/Coordinate';
import vtkPlane from '@kitware/vtk.js/Common/DataModel/Plane';
import { Crosshair, RotateCcw, Orbit, MoveUpRight } from 'lucide-react';
import {
  thermalSurface,
  surfaceGeometry,
  pairedChange,
  depthLens,
  changeRGB,
  type ThermalAtlas,
  type Relief,
} from '@/lib/thermal';
import { triangleNormals, sectionMesh } from '@/lib/sections';
import { color, type Volume } from '@/lib/ocean';
import { longitudeLabel, latitudeLabel } from '@/lib/geography';

export type AtlasMode = 'layers' | 'change' | 'relief';
export const layerColors = ['#ffb579', '#62e3cc', '#629dff'];
const rgb = (hex: string) =>
  hex.startsWith('#')
    ? [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
    : hex.match(/[\d.]+/g)!.map(Number);
const changeRgb = changeRGB;

function scene(container: HTMLDivElement) {
  const owned: { delete: () => void }[] = [];
  const own = <T extends { delete: () => void }>(o: T) => {
    owned.push(o);
    return o;
  };
  const rw = vtkGenericRenderWindow.newInstance({
    background: [0.024, 0.043, 0.062],
  });
  rw.setContainer(container);
  rw.resize();
  const renderer = rw.getRenderer(),
    win = rw.getRenderWindow();
  renderer.setTwoSidedLighting(true);
  function mesh(lighting = true) {
    const data = own(vtkPolyData.newInstance()),
      mapper = own(vtkMapper.newInstance()),
      actor = own(vtkActor.newInstance());
    const normals = own(
      vtkDataArray.newInstance({
        name: 'Normals',
        numberOfComponents: 3,
        values: new Float32Array(0),
      }),
    );
    const colors = own(
      vtkDataArray.newInstance({
        name: 'Colors',
        numberOfComponents: 3,
        values: new Uint8Array(0),
      }),
    );
    data.getPointData().setNormals(normals);
    data.getPointData().setScalars(colors);
    mapper.setInputData(data);
    mapper.setScalarModeToUsePointData();
    mapper.setColorModeToDirectScalars();
    actor.setMapper(mapper);
    actor.getProperty().setInterpolationToPhong();
    actor.getProperty().setAmbient(0.42);
    actor.getProperty().setDiffuse(0.58);
    actor.getProperty().setSpecular(0.28);
    actor.getProperty().setSpecularPower(32);
    actor.getProperty().setLighting(lighting);
    actor.setVisibility(false);
    renderer.addActor(actor);
    return { data, mapper, actor, normals, colors };
  }
  const terrain = mesh(),
    surfaces = Array.from({ length: 5 }, () => mesh()),
    curtain = mesh(false),
    ribs = mesh(false),
    probe = mesh(false),
    graticule = mesh(false);
  for (const item of [ribs, probe, graticule]) item.actor.setPickable(false);
  probe.actor.getProperty().setLineWidth(2);
  probe.actor.getProperty().setPointSize(9);
  const planes = surfaces.map(() => {
    const plane = own(vtkPlane.newInstance());
    plane.setNormal(1, 0, 0);
    return plane;
  });
  const picker = own(vtkCellPicker.newInstance());
  picker.setPickFromList(true);
  picker.addPickList(terrain.actor);
  picker.addPickList(ribs.actor);
  surfaces.forEach((x) => picker.addPickList(x.actor));
  const coordinate = own(vtkCoordinate.newInstance());
  coordinate.setCoordinateSystemToWorld();
  let resize = () => {};
  const observer = new ResizeObserver(() => {
    rw.resize();
    resize();
    win.render();
  });
  observer.observe(container);
  return {
    rw,
    renderer,
    win,
    terrain,
    surfaces,
    curtain,
    ribs,
    probe,
    graticule,
    planes,
    picker,
    coordinate,
    onResize: (f: () => void) => {
      resize = f;
    },
    dispose: () => {
      observer.disconnect();
      renderer.removeAllViewProps();
      owned.reverse().forEach((x) => x.delete());
      const interactor = rw.getInteractor();
      rw.delete();
      interactor.delete();
      renderer.delete();
      win.delete();
    },
  };
}
type Scene = ReturnType<typeof scene>;
type Mesh = Scene['terrain'];
function setMesh(
  target: Mesh,
  points: number[],
  polys: Uint32Array,
  colors: number[],
) {
  const p = new Float32Array(points);
  target.data.getPoints().setData(p, 3);
  target.data.getPolys().setData(polys);
  target.normals.setData(triangleNormals(p, polys), 3);
  target.colors.setData(new Uint8Array(colors), 3);
  target.data.modified();
  target.actor.setVisibility(polys.length > 0);
}
function setLines(
  target: Mesh,
  points: number[],
  lines: number[],
  colors: number[],
) {
  target.data.getPoints().setData(new Float32Array(points), 3);
  target.data.getLines().setData(new Uint32Array(lines));
  target.colors.setData(new Uint8Array(colors), 3);
  target.data.modified();
  target.actor.setVisibility(points.length > 0);
}

export default function AtlasRenderer({
  atlas,
  relief,
  mode,
  index,
  before,
  threshold,
  cell,
  upper,
  peel,
  layers,
  curtain,
  supportOnly,
  onProbe,
}: {
  atlas: ThermalAtlas;
  relief: Relief | null;
  mode: AtlasMode;
  index: number;
  before: number;
  threshold: number;
  cell: number;
  upper: number;
  peel: number;
  layers: boolean[];
  curtain: boolean;
  supportOnly: boolean;
  onProbe: (cell: number) => void;
}) {
  const bounds = useMemo(
    () => [
      atlas.longitude[0],
      atlas.latitude[0],
      atlas.longitude.at(-1)!,
      atlas.latitude.at(-1)!,
    ],
    [atlas.longitude, atlas.latitude],
  );
  const factor =
    111.32 * Math.cos(((bounds[1] + bounds[3]) * 0.5 * Math.PI) / 180);
  const world = useCallback(
    (lon: number, lat: number, depth: number, lens: number) => [
      (lon - bounds[0]) * factor,
      (lat - bounds[1]) * 111.32,
      depthLens(depth, lens),
    ],
    [bounds, factor],
  );
  const host = useRef<HTMLDivElement>(null),
    context = useRef<Scene | null>(null),
    home = useRef(() => {});
  const [error, setError] = useState(''),
    [picking, setPicking] = useState(false),
    [orbit, setOrbit] = useState(false);
  const [geolabels, setGeolabels] = useState<
    { name: string; x: number; y: number }[]
  >([]);
  const [northAngle, setNorthAngle] = useState(0);
  const pointer = useRef([0, 0]);
  const width = (bounds[2] - bounds[0]) * factor,
    height = (bounds[3] - bounds[1]) * 111.32;
  useEffect(() => {
    if (!host.current) return;
    let c: Scene;
    try {
      c = scene(host.current);
      context.current = c;
    } catch (e) {
      setError(`This device could not initialize the 3D scene: ${String(e)}`);
      return;
    }
    return () => {
      context.current = null;
      c.dispose();
    };
  }, []);
  useEffect(() => {
    const c = context.current;
    if (!c) return;
    home.current = () => {
      const camera = c.renderer.getActiveCamera();
      camera.setParallelProjection(true);
      camera.setPosition(width * 1.13, -height * 1.3, width * 0.94);
      camera.setFocalPoint(width * 0.51, height * 0.52, -230);
      camera.setViewUp(0, 0, 1);
      const size = c.rw.getApiSpecificRenderWindow().getSize(),
        aspect = size[0] / Math.max(1, size[1]);
      camera.setParallelScale(Math.max(height * 0.58, (width * 0.53) / aspect));
      c.renderer.resetCameraClippingRange();
      c.win.render();
    };
    c.onResize(() => {
      const size = c.rw.getApiSpecificRenderWindow().getSize();
      c.renderer
        .getActiveCamera()
        .setParallelScale(
          Math.max(
            height * 0.58,
            (width * 0.53) / (size[0] / Math.max(1, size[1])),
          ),
        );
      c.renderer.resetCameraClippingRange();
    });
    home.current();
  }, [width, height]);
  useEffect(() => {
    const c = context.current;
    if (!c || !host.current) return;
    const update = () => {
      if (!host.current) return;
      const size = c.rw.getApiSpecificRenderWindow().getSize(),
        rect = host.current.getBoundingClientRect();
      const project = (lon: number, lat: number, d: number) => {
        const p = world(lon, lat, d, upper);
        c.coordinate.setValue(p as [number, number, number]);
        const [x, y] = c.coordinate.getComputedDoubleDisplayValue(c.renderer);
        return {
          x: (x * rect.width) / size[0],
          y: rect.height - (y * rect.height) / size[1],
        };
      };
      setGeolabels(
        (
          [
            ['INDIA', 80, 19, -600],
            ['SRI LANKA', 80.7, 7.1, -600],
            ['MYANMAR', 96.8, 20.5, -700],
            ['ANDAMAN SEA', 96, 11, 0],
            ['ARABIAN SEA', 64, 15, 0],
            ['BAY OF BENGAL', 87, 15, 0],
            ['AFRICA', 38, 0, -600],
            ['MADAGASCAR', 47, -20, -600],
            ['INDIAN OCEAN', 76, -16, 0],
            ['INDONESIA', 110, -4, -600],
          ] as const
        )
          .filter(
            ([, lon, lat]) =>
              lon >= bounds[0] &&
              lon <= bounds[2] &&
              lat >= bounds[1] &&
              lat <= bounds[3],
          )
          .map(([name, lon, lat, d]) => ({ name, ...project(lon, lat, d) }))
          .filter(
            (p) =>
              p.x > 35 &&
              p.x < rect.width - 55 &&
              p.y > 95 &&
              p.y < rect.height - 75,
          ),
      );
      const a = project(87, 14, 0),
        b = project(87, 15, 0);
      setNorthAngle((Math.atan2(b.x - a.x, a.y - b.y) * 180) / Math.PI);
    };
    const listener = c.renderer.getActiveCamera().onModified(update);
    const observer = new ResizeObserver(update);
    observer.observe(host.current);
    update();
    return () => {
      listener.unsubscribe();
      observer.disconnect();
    };
  }, [upper, world, bounds]);
  useEffect(() => {
    const c = context.current;
    if (!c) return;
    if (!relief) {
      c.terrain.actor.setVisibility(false);
      return;
    }
    const coords: number[] = [],
      colors: number[] = [],
      polys: number[] = [];
    const nx = relief.longitude.length;
    relief.elevation.forEach((v, i) => {
      coords.push(
        ...world(
          relief.longitude[i % nx],
          relief.latitude[Math.floor(i / nx)],
          -(v ?? 0),
          upper,
        ),
      );
      const elevation = v ?? 0;
      const col =
        elevation > 0
          ? color(elevation, 0, 3000, 'viridis')
          : color(-elevation, 0, 4800, 'ice');
      // Land and basin use a separate subdued relief ramp, never temperature colors.
      colors.push(
        ...(elevation >= 0
          ? [
              94 + Math.min(elevation / 30, 45),
              119 + Math.min(elevation / 60, 20),
              102,
            ]
          : rgb(col).map((x) => Math.round(x * 0.6))),
      );
    });
    for (let y = 0; y < relief.latitude.length - 1; y++)
      for (let x = 0; x < nx - 1; x++) {
        const a = y * nx + x,
          b = a + 1,
          d = a + nx,
          e = d + 1;
        if ([a, b, d, e].every((i) => relief.elevation[i] != null))
          polys.push(3, a, b, e, 3, a, e, d);
      }
    setMesh(c.terrain, coords, new Uint32Array(polys), colors);
    c.terrain.actor.getProperty().setOpacity(1);
    const points: number[] = [],
      lines: number[] = [],
      lineColors: number[] = [];
    for (const lat of Array.from(
      { length: 5 },
      (_, i) => bounds[1] + ((bounds[3] - bounds[1]) * i) / 4,
    )) {
      const n = points.length / 3;
      points.push(
        ...world(bounds[0], lat, 0, upper),
        ...world(bounds[2], lat, 0, upper),
      );
      lines.push(2, n, n + 1);
      lineColors.push(53, 87, 101, 53, 87, 101);
    }
    for (const lon of Array.from(
      { length: 5 },
      (_, i) => bounds[0] + ((bounds[2] - bounds[0]) * i) / 4,
    )) {
      const n = points.length / 3;
      points.push(
        ...world(lon, bounds[1], 0, upper),
        ...world(lon, bounds[3], 0, upper),
      );
      lines.push(2, n, n + 1);
      lineColors.push(53, 87, 101, 53, 87, 101);
    }
    setLines(c.graticule, points, lines, lineColors);
    c.graticule.actor.getProperty().setOpacity(0.4);
    c.renderer.resetCameraClippingRange();
    c.win.render();
  }, [relief, upper, world, bounds]);
  useEffect(() => {
    const c = context.current;
    if (!c) return;
    c.surfaces.forEach((x) => x.actor.setVisibility(false));
    const nx = atlas.longitude.length;
    const change = pairedChange(atlas, before, index, threshold);
    const sets =
      mode === 'layers'
        ? [28, 24, 20].map((t, i) => ({
            values: thermalSurface(atlas, index, t).map((c) => c.depth),
            actor: i,
            enabled: layers[i],
            rgb: rgb(layerColors[i]),
          }))
        : mode === 'change'
          ? [
              {
                values: change.cells.map((v) =>
                  v.delta != null && (!supportOnly || v.locallySupported)
                    ? v.before.depth
                    : null,
                ),
                actor: 3,
                enabled: true,
                rgb: [167, 195, 219],
              },
              {
                values: change.cells.map((v) =>
                  v.delta != null && (!supportOnly || v.locallySupported)
                    ? v.after.depth
                    : null,
                ),
                actor: 4,
                enabled: true,
                rgb: [240, 180, 120],
              },
            ]
          : [];
    const ribPoints: number[] = [],
      ribLines: number[] = [],
      ribColors: number[] = [];
    for (const s of sets) {
      if (!s.enabled) continue;
      const mesh = surfaceGeometry(
          atlas.longitude,
          atlas.latitude,
          s.values,
          mode === 'change' && s.actor === 3
            ? 1
            : atlas.longitude.length * atlas.latitude.length > 1000
              ? 3
              : 5,
        ),
        points: number[] = [],
        colors: number[] = [];
      for (let i = 0; i < mesh.points.length; i += 3) {
        points.push(
          ...world(
            mesh.points[i],
            mesh.points[i + 1],
            mesh.points[i + 2],
            upper,
          ),
        );
        if (mode === 'change' && s.actor === 4) {
          const a = mesh.nativeCell[i / 3],
            x = a % nx,
            y = Math.floor(a / nx);
          const u =
            (mesh.points[i] - atlas.longitude[x]) /
            (atlas.longitude[x + 1] - atlas.longitude[x]);
          const v =
            (mesh.points[i + 1] - atlas.latitude[y]) /
            (atlas.latitude[y + 1] - atlas.latitude[y]);
          colors.push(
            ...changeRgb(
              change.cells[a].delta! * (1 - u) * (1 - v) +
                change.cells[a + 1].delta! * u * (1 - v) +
                change.cells[a + nx].delta! * (1 - u) * v +
                change.cells[a + nx + 1].delta! * u * v,
            ),
          );
        } else colors.push(...s.rgb);
      }
      const target = c.surfaces[s.actor];
      setMesh(target, points, mesh.polys, colors);
      target.actor
        .getProperty()
        .setOpacity(mode === 'change' ? (s.actor === 3 ? 0.48 : 1) : 1);
      target.actor.getProperty().setLighting(mode !== 'change');
      target.actor
        .getProperty()
        .setRepresentation(mode === 'change' && s.actor === 3 ? 1 : 2);
      target.mapper.removeAllClippingPlanes();
      const cut =
        mode === 'layers' ? Math.min(85, peel + (2 - s.actor) * 18) : peel;
      const plane = c.planes[s.actor];
      if (cut > 0) {
        plane.setOrigin(
          world(
            atlas.longitude[0] +
              ((atlas.longitude.at(-1)! - atlas.longitude[0]) * cut) / 100,
            0,
            0,
            upper,
          )[0],
          0,
          0,
        );
        target.mapper.addClippingPlane(plane);
      }
      if (mode === 'layers')
        for (let y = 0; y < atlas.latitude.length; y += 2)
          for (let x = 0; x < nx - 1; x++) {
            const a = y * nx + x,
              b = a + 1;
            if (
              s.values[a] == null ||
              s.values[b] == null ||
              (x / (nx - 1)) * 100 < cut
            )
              continue;
            const n = ribPoints.length / 3;
            ribPoints.push(
              ...world(
                atlas.longitude[x],
                atlas.latitude[y],
                s.values[a]!,
                upper,
              ),
              ...world(
                atlas.longitude[x + 1],
                atlas.latitude[y],
                s.values[b]!,
                upper,
              ),
            );
            ribLines.push(2, n, n + 1);
            ribColors.push(...s.rgb, ...s.rgb);
          }
    }
    if (mode === 'change')
      change.cells.forEach((v, i) => {
        if (
          v.delta == null ||
          (supportOnly && !v.locallySupported) ||
          ((i % nx) / (nx - 1)) * 100 < peel
        )
          return;
        const n = ribPoints.length / 3,
          lon = atlas.longitude[i % nx],
          lat = atlas.latitude[Math.floor(i / nx)];
        ribPoints.push(
          ...world(lon, lat, v.before.depth!, upper),
          ...world(lon, lat, v.after.depth!, upper),
        );
        ribLines.push(2, n, n + 1);
        ribColors.push(...changeRgb(v.delta), ...changeRgb(v.delta));
      });
    setLines(c.ribs, ribPoints, ribLines, ribColors);
    c.ribs.actor.setPickable(mode === 'change');
    c.ribs.data
      .getVerts()
      .setData(
        new Uint32Array(
          mode === 'change'
            ? Array.from({ length: ribPoints.length / 3 }, (_, i) => [
                1,
                i,
              ]).flat()
            : [],
        ),
      );
    c.ribs.actor.getProperty().setPointSize(4);
    c.ribs.data.modified();
    c.ribs.actor.getProperty().setOpacity(mode === 'change' ? 0.85 : 0.28);
    c.renderer.resetCameraClippingRange();
    c.win.render();
  }, [
    atlas,
    index,
    before,
    threshold,
    mode,
    layers,
    peel,
    upper,
    supportOnly,
    world,
  ]);
  useEffect(() => {
    const c = context.current;
    if (!c) return;
    const nx = atlas.longitude.length,
      lon = atlas.longitude[cell % nx],
      lat = atlas.latitude[Math.floor(cell / nx)];
    const p = [...world(lon, lat, -30, upper), ...world(lon, lat, 400, upper)];
    setLines(c.probe, p, [2, 0, 1], [240, 248, 255, 240, 248, 255]);
    c.curtain.actor.setVisibility(curtain && mode !== 'relief');
    if (curtain && mode !== 'relief') {
      const field = {
        axes: {
          longitude: atlas.longitude,
          latitude: atlas.latitude,
          depth: atlas.depth,
        },
        dimensions: [nx, atlas.latitude.length, atlas.depth.length],
        values: atlas.frames[index].temperature,
      } as Volume;
      const mesh = sectionMesh(
        field,
        'latitude',
        (100 * (lat - atlas.latitude[0])) /
          (atlas.latitude.at(-1)! - atlas.latitude[0]),
      );
      const points: number[] = [],
        colors: number[] = [];
      for (let i = 0; i < mesh.points.length; i += 3) {
        points.push(
          ...world(
            mesh.points[i],
            mesh.points[i + 1],
            mesh.points[i + 2],
            upper,
          ),
        );
        colors.push(...rgb(color(mesh.values[i / 3], 2, 32)));
      }
      // Restrict the curtain to the same upper 500 m focus as the layer lens.
      const polys: number[] = [];
      for (let i = 0; i < mesh.polys.length; i += 4)
        if (
          [mesh.polys[i + 1], mesh.polys[i + 2], mesh.polys[i + 3]].every(
            (id) => mesh.points[id * 3 + 2] <= 500,
          )
        )
          polys.push(...mesh.polys.slice(i, i + 4));
      setMesh(c.curtain, points, new Uint32Array(polys), colors);
      c.curtain.actor.getProperty().setOpacity(0.88);
    }
    c.renderer.resetCameraClippingRange();
    c.win.render();
  }, [atlas, index, cell, upper, curtain, mode, world]);
  useEffect(() => {
    const c = context.current;
    if (!c || !orbit) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setOrbit(false);
      return;
    }
    let frame = 0,
      last = 0;
    const tick = (now: number) => {
      if (now - last > 40) {
        c.renderer.getActiveCamera().azimuth(Math.min(now - last, 100) * 0.003);
        last = now;
        c.renderer.resetCameraClippingRange();
        c.win.render();
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [orbit]);
  const pick = (clientX: number, clientY: number) => {
    const c = context.current;
    if (!c || !host.current || !picking) return;
    const rect = host.current.getBoundingClientRect(),
      size = c.rw.getApiSpecificRenderWindow().getSize();
    c.picker.pick(
      [
        ((clientX - rect.left) * size[0]) / rect.width,
        ((rect.bottom - clientY) * size[1]) / rect.height,
        0,
      ],
      c.renderer,
    );
    if (c.picker.getCellId() < 0) return;
    const p = c.picker.getPickPosition(),
      lon = p[0] / factor + bounds[0],
      lat = p[1] / 111.32 + bounds[1];
    if (
      lon < atlas.longitude[0] ||
      lon > atlas.longitude.at(-1)! ||
      lat < atlas.latitude[0] ||
      lat > atlas.latitude.at(-1)!
    )
      return;
    const nearest = (axis: number[], v: number) =>
      axis.reduce(
        (best, x, i) => (Math.abs(x - v) < Math.abs(axis[best] - v) ? i : best),
        0,
      );
    onProbe(
      nearest(atlas.latitude, lat) * atlas.longitude.length +
        nearest(atlas.longitude, lon),
    );
  };
  return (
    <div className={`atlas-scene ${picking ? 'is-picking' : ''}`}>
      <div
        className="atlas-vtk"
        ref={host}
        aria-label="Interactive Indian Ocean terrain and thermal surfaces. Drag to orbit, scroll to zoom."
        onPointerDown={(e) => {
          pointer.current = [e.clientX, e.clientY];
          setOrbit(false);
        }}
        onPointerUp={(e) => {
          if (
            Math.hypot(
              e.clientX - pointer.current[0],
              e.clientY - pointer.current[1],
            ) < 5
          )
            pick(e.clientX, e.clientY);
        }}
      />
      {error && (
        <div className="atlas-render-error" role="alert">
          {error}
        </div>
      )}
      <div className="atlas-scene-toolbar">
        <button
          className={picking ? 'active' : ''}
          onClick={() => setPicking(!picking)}
          aria-pressed={picking}
        >
          <Crosshair size={16} /> Probe
        </button>
        <button
          className={orbit ? 'active' : ''}
          onClick={() => setOrbit(!orbit)}
          aria-pressed={orbit}
        >
          <Orbit size={16} /> Orbit
        </button>
        <button
          onClick={() => {
            setOrbit(false);
            home.current();
          }}
          aria-label="Reset atlas camera"
        >
          <RotateCcw size={17} />
        </button>
        <button
          onClick={() => {
            setOrbit(false);
            const c = context.current;
            if (!c) return;
            const camera = c.renderer.getActiveCamera();
            camera.setPosition(width / 2, height / 2, 5000);
            camera.setFocalPoint(width / 2, height / 2, 0);
            camera.setViewUp(0, 1, 0);
            camera.setParallelScale(height * 0.58);
            c.renderer.resetCameraClippingRange();
            c.win.render();
          }}
          aria-label="Atlas top view"
        >
          <MoveUpRight size={17} />
        </button>
      </div>
      <div className="atlas-scene-key">
        <span className="atlas-live-dot" /> INCOIS × NOAA NCEI
        <span>
          {longitudeLabel(bounds[0])}–{longitudeLabel(bounds[2])} ·{' '}
          {latitudeLabel(bounds[1])}–{latitudeLabel(bounds[3])}
        </span>
      </div>
      <div className="atlas-orientation">
        N<span style={{ transform: `rotate(${northAngle}deg)` }}>↑</span>
      </div>
      <div className="atlas-geolabels" aria-hidden="true">
        {geolabels.map((p) => (
          <span key={p.name} style={{ left: p.x, top: p.y }}>
            {p.name}
          </span>
        ))}
      </div>
      <div className="atlas-depth-key">
        <b>DEPTH LENS</b>
        <span>0–500 m · {upper}×</span>
        <span>Below 500 m & land · 35×</span>
      </div>
      <div className="atlas-scene-caption">
        {picking
          ? 'Click a surface to select the nearest INCOIS grid column.'
          : 'Drag to orbit · Scroll to zoom · Explore a column with Probe'}
        <span>
          {relief
            ? 'ETOPO 2022 relief · 0.25° extract · geographic context'
            : 'Relief unavailable · temperature analysis remains usable'}
        </span>
      </div>
    </div>
  );
}
