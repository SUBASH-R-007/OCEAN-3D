'use client';
import {
  clippedInstrumentPath,
  arrangeInstrumentLabels,
  instrumentIsFresh,
} from '@/lib/profiles';
/* oxlint-disable react/react-compiler -- Effects synchronize an owned imperative VTK scene. */
import { useEffect, useMemo, useRef, useState } from 'react';
import '@kitware/vtk.js/Rendering/Profiles/All';
import vtkGenericRenderWindow from '@kitware/vtk.js/Rendering/Misc/GenericRenderWindow';
import vtkImageData from '@kitware/vtk.js/Common/DataModel/ImageData';
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray';
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume';
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper';
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction';
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction';
import vtkImageMapper from '@kitware/vtk.js/Rendering/Core/ImageMapper';
import vtkImageSlice from '@kitware/vtk.js/Rendering/Core/ImageSlice';
import vtkPolyData from '@kitware/vtk.js/Common/DataModel/PolyData';
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper';
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor';
import vtkCoordinate from '@kitware/vtk.js/Rendering/Core/Coordinate';
import vtkPlane from '@kitware/vtk.js/Common/DataModel/Plane';
import { color, type Settings, type Volume, type Profile } from '@/lib/ocean';
import {
  colorRgb,
  displayScalar,
  encodeDisplayScalars,
  transferStops,
} from '@/lib/colorScale';
import { isosurface } from '@/lib/isosurface';
import { seedFlow, sameGrid, type FlowPath } from '@/lib/flow';
import {
  currentDepths,
  currentGlyphs,
  vectorScaleKm,
  projectedCurrent,
} from '@/lib/currents';
import { sectionMesh, triangleNormals } from '@/lib/sections';
import { loadCoastline, clipSegment, type Coastline } from '@/lib/geography';
import GeoOverview from './GeoOverview';
import { missionSegments } from '@/lib/missions';
import { RotateCcw, Maximize2 } from 'lucide-react';

function createScene(container: HTMLDivElement) {
  const owned: { delete: () => void }[] = [];
  const own = <T extends { delete: () => void }>(object: T) => {
    owned.push(object);
    return object;
  };
  const rw = vtkGenericRenderWindow.newInstance({
    background: [0.026, 0.052, 0.075],
  });
  rw.setContainer(container);
  rw.resize();
  const renderer = rw.getRenderer(),
    win = rw.getRenderWindow();
  const image = own(vtkImageData.newInstance()),
    scalars = own(
      vtkDataArray.newInstance({ name: 'ocean', values: new Float32Array(8) }),
    );
  image.getPointData().setScalars(scalars);
  const transfer = own(vtkColorTransferFunction.newInstance()),
    opacity = own(vtkPiecewiseFunction.newInstance()),
    sliceOpacity = own(vtkPiecewiseFunction.newInstance());
  const volumeMapper = own(vtkVolumeMapper.newInstance()),
    volume = own(vtkVolume.newInstance());
  volumeMapper.setInputData(image);
  volumeMapper.setMaximumSamplesPerRay(1400);
  volume.setMapper(volumeMapper);
  volume.setVisibility(false);
  volume.getProperty().setRGBTransferFunction(0, transfer);
  volume.getProperty().setScalarOpacity(0, opacity);
  volume.getProperty().setInterpolationTypeToNearest();
  volume.getProperty().setShade(false);
  renderer.addVolume(volume);
  const sliceMapper = own(vtkImageMapper.newInstance()),
    slice = own(vtkImageSlice.newInstance());
  sliceMapper.setInputData(image);
  sliceMapper.setSlicingMode(2);
  slice.setMapper(sliceMapper);
  slice.getProperty().setRGBTransferFunction(0, transfer);
  slice.getProperty().setPiecewiseFunction(0, sliceOpacity);
  slice.getProperty().setInterpolationTypeToNearest();
  slice.getProperty().setUseLookupTableScalarRange(true);
  renderer.addActor(slice);
  function geometry(rgb: number[], alpha = 1) {
    const data = own(vtkPolyData.newInstance()),
      mapper = own(vtkMapper.newInstance()),
      actor = own(vtkActor.newInstance());
    mapper.setInputData(data);
    actor.setMapper(mapper);
    actor.getProperty().setColor(rgb[0], rgb[1], rgb[2]);
    actor.getProperty().setOpacity(alpha);
    renderer.addActor(actor);
    return { data, mapper, actor };
  }
  const surface = geometry([0.4, 0.88, 0.82], 0.7),
    sectionX = geometry([1, 1, 1]),
    sectionY = geometry([1, 1, 1]),
    grid = geometry([0.22, 0.43, 0.53], 0.5),
    coast = geometry([0.7, 0.81, 0.82], 0.85),
    instruments = geometry([0.4, 0.84, 0.8], 0.7),
    missions = geometry([1, 0.7, 0.38], 0.85),
    arrows = geometry([0.81, 0.93, 0.96], 0.9),
    flow = geometry([0.27, 0.78, 0.9], 0.42),
    particles = geometry([0.74, 0.96, 1]);
  particles.actor.getProperty().setPointSize(4);
  const currentScalars = own(
    vtkDataArray.newInstance({
      name: 'Horizontal speed',
      values: new Float32Array(0),
    }),
  );
  const currentTransfer = own(vtkColorTransferFunction.newInstance());
  for (let i = 0; i <= 32; i++) {
    const value = i / 16;
    const rgb = color(value, 0, 2, 'viridis').match(/\d+/g)!.map(Number);
    currentTransfer.addRGBPoint(
      value,
      rgb[0] / 255,
      rgb[1] / 255,
      rgb[2] / 255,
    );
  }
  arrows.data.getPointData().setScalars(currentScalars);
  arrows.mapper.setLookupTable(currentTransfer);
  arrows.mapper.setUseLookupTableScalarRange(true);
  arrows.mapper.setScalarVisibility(true);
  arrows.actor.getProperty().setLighting(false);
  const surfaceNormals = own(
    vtkDataArray.newInstance({
      name: 'Normals',
      numberOfComponents: 3,
      values: new Float32Array(0),
    }),
  );
  surface.data.getPointData().setNormals(surfaceNormals);
  const sectionScalars = [sectionX, sectionY].map((section) => {
    const values = own(
      vtkDataArray.newInstance({
        name: 'Section values',
        values: new Float32Array(0),
      }),
    );
    section.data.getPointData().setScalars(values);
    section.mapper.setLookupTable(transfer);
    section.mapper.setUseLookupTableScalarRange(true);
    section.mapper.setScalarVisibility(true);
    section.actor.getProperty().setLighting(false);
    section.actor.setVisibility(false);
    return values;
  });
  surface.actor.getProperty().setAmbient(0.35);
  surface.actor.getProperty().setDiffuse(0.65);
  surface.actor.getProperty().setSpecular(0.18);
  const clipping = own(vtkPlane.newInstance());
  clipping.setNormal(1, 0, 0);
  const coordinate = own(vtkCoordinate.newInstance());
  coordinate.setCoordinateSystemToWorld();
  let labelUpdate = () => {};
  const modified = renderer.getActiveCamera().onModified(() => labelUpdate());
  const observer = new ResizeObserver(() => {
    rw.resize();
    renderer.resetCamera();
    renderer.getActiveCamera().zoom(1.12);
    win.render();
    labelUpdate();
  });
  observer.observe(container);
  return {
    rw,
    renderer,
    win,
    image,
    scalars,
    transfer,
    opacity,
    sliceOpacity,
    volumeMapper,
    volume,
    sliceMapper,
    slice,
    surface,
    surfaceNormals,
    sectionX,
    sectionY,
    sectionScalars,
    grid,
    coast,
    instruments,
    missions,
    arrows,
    currentScalars,
    flow,
    particles,
    clipping,
    coordinate,
    updateLabels: (fn: () => void) => {
      labelUpdate = fn;
    },
    dispose: () => {
      observer.disconnect();
      modified.unsubscribe();
      renderer.removeAllViewProps();
      owned.reverse().forEach((o) => o.delete());
      const interactor = rw.getInteractor();
      rw.delete();
      interactor.delete();
      renderer.delete();
      win.delete();
    },
  };
}
type Scene = ReturnType<typeof createScene>;
type Geometry = Scene['grid'];
function setLines(target: Geometry, points: number[], lines: number[]) {
  target.data.getPoints().setData(new Float32Array(points), 3);
  target.data.getLines().setData(new Uint32Array(lines));
  target.data.modified();
}
function dimensions(field: Volume, exaggeration: number) {
  const { longitude: lon, latitude: lat, depth } = field.axes;
  const cos = Math.cos(((lat[0] + lat.at(-1)!) * Math.PI) / 360),
    width = (lon.at(-1)! - lon[0]) * 111.32 * cos,
    height = (lat.at(-1)! - lat[0]) * 111.32;
  const thickness = ((depth.at(-1)! - depth[0]) / 1000) * exaggeration;
  return {
    width,
    height,
    thickness,
    origin: [0, 0, (-depth.at(-1)! / 1000) * exaggeration],
    spacing: [
      width / (field.dimensions[0] - 1),
      height / (field.dimensions[1] - 1),
      thickness / (field.dimensions[2] - 1),
    ],
    xyz: (lo: number, la: number, d: number) => [
      (lo - lon[0]) * 111.32 * cos,
      (la - lat[0]) * 111.32,
      (-d / 1000) * exaggeration,
    ],
  };
}

export default function OceanScene({
  field,
  settings,
  profiles,
  vectors,
  onSelect,
}: {
  field: Volume;
  settings: Settings;
  profiles: Profile[];
  vectors: Volume[];
  onSelect: (id: string) => void;
}) {
  const host = useRef<HTMLDivElement>(null),
    context = useRef<Scene | null>(null),
    reset = useRef(() => {}),
    domain = useRef('');
  const [labels, setLabels] = useState<
      {
        id: string;
        x: number;
        y: number;
        anchorX: number;
        anchorY: number;
        instrument: string;
        time: string;
        active: boolean;
        short: string;
      }[]
    >([]),
    [error, setError] = useState(''),
    [coastline, setCoastline] = useState<Coastline>([]),
    [flowStats, setFlowStats] = useState(''),
    [vectorStats, setVectorStats] = useState(''),
    [surfaceTriangles, setSurfaceTriangles] = useState(0);
  const [sectionPositions, setSectionPositions] = useState<number[]>([]);
  const setView = useRef((_: 'top' | 'front') => {});
  const encoded = useMemo(
    () => encodeDisplayScalars(field.values, settings.log),
    [field, settings.log],
  );
  useEffect(() => {
    if (!host.current) return;
    try {
      const scene = createScene(host.current);
      context.current = scene;
      return () => {
        context.current = null;
        scene.dispose();
      };
    } catch (e) {
      setError(
        `3D rendering unavailable: ${String(e)}. Profile analysis and exports remain available.`,
      );
    }
  }, []);
  useEffect(() => {
    let active = true;
    loadCoastline()
      .then((c) => {
        if (active) setCoastline(c);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  // Geometry/data changes keep the same renderer, camera, actors and GPU context.
  useEffect(() => {
    const c = context.current;
    if (!c) return;
    const d = dimensions(field, settings.exaggeration),
      [nx, ny, nz] = field.dimensions;
    c.image.setDimensions(nx, ny, nz);
    c.image.setOrigin(d.origin as [number, number, number]);
    c.image.setSpacing(d.spacing as [number, number, number]);
    c.volumeMapper.setSampleDistance(
      Math.max(
        Math.min(...d.spacing),
        Math.hypot(d.width, d.height, d.thickness) / 1200,
      ),
    );
    c.image.modified();
    const points: number[] = [],
      cells: number[] = [];
    const line = (a: number[], b: number[]) => {
      const n = points.length / 3;
      points.push(...a, ...b);
      cells.push(2, n, n + 1);
    };
    const bottom = d.origin[2],
      top = bottom + d.thickness;
    for (let i = 0; i <= 6; i++) {
      line(
        [(d.width * i) / 6, 0, bottom],
        [(d.width * i) / 6, d.height, bottom],
      );
      line(
        [0, (d.height * i) / 6, bottom],
        [d.width, (d.height * i) / 6, bottom],
      );
    }
    for (const z of [bottom, top]) {
      line([0, 0, z], [d.width, 0, z]);
      line([d.width, 0, z], [d.width, d.height, z]);
      line([d.width, d.height, z], [0, d.height, z]);
      line([0, d.height, z], [0, 0, z]);
    }
    for (const [x, y] of [
      [0, 0],
      [d.width, 0],
      [d.width, d.height],
      [0, d.height],
    ])
      line([x, y, bottom], [x, y, top]);
    setLines(c.grid, points, cells);
    const key = `${field.model_id}:${field.axes.longitude[0]}:${field.axes.latitude[0]}:${d.width}:${d.height}:${field.axes.depth[0]}:${field.axes.depth.at(-1)}`;
    reset.current = () => {
      const camera = c.renderer.getActiveCamera();
      camera.setParallelProjection(true);
      camera.setPosition(
        d.width * 1.2,
        -d.height * 1.45,
        Math.max(d.width, d.height) * 1.05,
      );
      camera.setFocalPoint(d.width / 2, d.height / 2, (bottom + top) / 2);
      camera.setViewUp(0, 0, 1);
      c.renderer.resetCamera();
      camera.zoom(1.12);
      c.renderer.resetCameraClippingRange();
      c.win.render();
    };
    setView.current = (view) => {
      const camera = c.renderer.getActiveCamera(),
        centre = [d.width / 2, d.height / 2, (bottom + top) / 2];
      camera.setFocalPoint(centre[0], centre[1], centre[2]);
      if (view === 'top') {
        camera.setPosition(
          centre[0],
          centre[1],
          top + Math.max(d.width, d.height) * 2,
        );
        camera.setViewUp(0, 1, 0);
      } else {
        camera.setPosition(
          centre[0],
          -Math.max(d.width, d.height) * 2,
          centre[2],
        );
        camera.setViewUp(0, 0, 1);
      }
      c.renderer.resetCamera();
      const size = c.rw.getApiSpecificRenderWindow().getSize(),
        aspect = size[0] / Math.max(1, size[1]);
      camera.setParallelScale(
        Math.max(
          (view === 'top' ? d.height : d.thickness) / 2,
          d.width / (2 * aspect),
        ) * 1.22,
      );
      c.renderer.resetCameraClippingRange();
      c.win.render();
    };
    if (domain.current !== key) {
      domain.current = key;
      reset.current();
    } else {
      c.renderer.resetCameraClippingRange();
      c.win.render();
    }
  }, [field, settings.exaggeration]);

  useEffect(() => {
    const c = context.current;
    if (!c) return;
    const [nx, ny, nz] = field.dimensions,
      plane = nx * ny;
    const values = new Float32Array(encoded.values.length);
    for (let z = 0; z < nz; z++)
      values.set(
        encoded.values.subarray((nz - 1 - z) * plane, (nz - z) * plane),
        z * plane,
      );
    c.scalars.setData(values);
    c.image.modified();
  }, [field, encoded]);

  // Display controls modify properties only; they do not recreate data or actors.
  useEffect(() => {
    const c = context.current;
    if (!c) return;
    const d = dimensions(field, settings.exaggeration),
      { min: lo, max: hi, sentinel } = encoded;
    c.transfer.removeAllPoints();
    c.opacity.removeAllPoints();
    c.sliceOpacity.removeAllPoints();
    c.transfer.addRGBPoint(sentinel, 0, 0, 0);
    c.opacity.addPoint(sentinel, 0);
    c.opacity.addPoint(sentinel + (lo - sentinel) * 0.01, 0);
    c.sliceOpacity.addPoint(sentinel, 0);
    c.sliceOpacity.addPoint(sentinel + (lo - sentinel) * 0.01, 0);
    for (const { x, rgb } of transferStops(
      {
        min: settings.min,
        max: settings.max,
        palette: settings.palette,
        log: settings.log,
      },
      encoded,
    )) {
      c.transfer.addRGBPoint(x, rgb[0] / 255, rgb[1] / 255, rgb[2] / 255);
    }
    c.opacity.addPoint(lo, settings.opacity * 0.12);
    c.opacity.addPoint(hi === lo ? lo + 1 : hi, settings.opacity * 0.67);
    c.sliceOpacity.addPoint(lo, 1);
    c.sliceOpacity.addPoint(hi === lo ? lo + 1 : hi, 1);
    c.volume
      .getProperty()
      .setScalarOpacityUnitDistance(0, Math.max(0.01, d.thickness / 12));
    c.volumeMapper.setSampleDistance(
      Math.max(
        Math.min(...d.spacing) * (settings.quality === 'detail' ? 0.45 : 1),
        Math.hypot(d.width, d.height, d.thickness) / 1200,
      ),
    );
    c.volumeMapper.setInteractionSampleDistanceFactor(2);
    c.volumeMapper.setImageSampleDistance(settings.flow ? 2 : 1);
    c.volumeMapper.setInitialInteractionScale(1.5);
    c.volumeMapper.setMaximumSamplesPerRay(1400);
    c.volume.setVisibility(settings.mode === 'volume');
    c.slice.setVisibility(
      settings.mode === 'slice' || settings.mode === 'sections',
    );
    c.surface.actor.setVisibility(
      settings.mode === 'isosurface' && (!settings.log || settings.iso > 0),
    );
    c.sectionX.actor.setVisibility(settings.mode === 'sections');
    c.sectionY.actor.setVisibility(settings.mode === 'sections');
    c.volume.getProperty().setShade(settings.quality === 'detail');
    c.volume.getProperty().setAmbient(0.65);
    c.volume.getProperty().setDiffuse(0.35);
    c.volume.getProperty().setSpecular(0.08);
    const dep = field.axes.depth;
    c.sliceMapper.setSlice(
      Math.max(
        0,
        Math.min(
          dep.length - 1,
          Math.round(
            ((dep.at(-1)! - settings.depth) / (dep.at(-1)! - dep[0])) *
              (dep.length - 1),
          ),
        ),
      ),
    );
    c.slice.getProperty().setOpacity(settings.opacity);
    c.sectionX.actor.getProperty().setOpacity(settings.opacity);
    c.sectionY.actor.getProperty().setOpacity(settings.opacity);
    c.volumeMapper.removeAllClippingPlanes();
    if (settings.cutaway > 0) {
      c.clipping.setOrigin((d.width * settings.cutaway) / 100, 0, 0);
      c.volumeMapper.addClippingPlane(c.clipping);
    }
    const rgb = colorRgb(
      settings.iso,
      settings.min,
      settings.max,
      settings.palette,
      settings.log,
    );
    c.surface.actor
      .getProperty()
      .setColor(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255);
    c.surface.actor.getProperty().setOpacity(settings.opacity);
    c.win.render();
  }, [
    field,
    encoded,
    settings.mode,
    settings.opacity,
    settings.min,
    settings.max,
    settings.palette,
    settings.log,
    settings.depth,
    settings.iso,
    settings.exaggeration,
    settings.cutaway,
    settings.quality,
    settings.flow,
  ]);

  useEffect(() => {
    const c = context.current;
    if (!c) return;
    c.instruments.actor.getProperty().setOpacity(settings.instrumentOpacity);
    c.missions.actor.getProperty().setOpacity(settings.instrumentOpacity);
    c.arrows.actor.getProperty().setOpacity(settings.currentOpacity);
    c.flow.actor.getProperty().setOpacity(settings.flowOpacity);
    c.particles.actor.getProperty().setOpacity(settings.flowOpacity);
    c.win.render();
  }, [
    settings.instrumentOpacity,
    settings.currentOpacity,
    settings.flowOpacity,
  ]);

  useEffect(() => {
    const c = context.current;
    if (!c || settings.mode !== 'isosurface') return;
    const d = dimensions(field, settings.exaggeration),
      mesh = isosurface(field, settings.iso, d.spacing, d.origin);
    c.surface.data.getPoints().setData(mesh.points, 3);
    c.surface.data.getPolys().setData(mesh.polys);
    c.surfaceNormals.setData(triangleNormals(mesh.points, mesh.polys), 3);
    c.surface.data.modified();
    setSurfaceTriangles(mesh.polys.length / 4);
    c.win.render();
  }, [field, settings.iso, settings.exaggeration, settings.mode]);

  useEffect(() => {
    const c = context.current;
    if (!c || settings.mode !== 'sections') return;
    const d = dimensions(field, settings.exaggeration),
      positions: number[] = [];
    [c.sectionX, c.sectionY].forEach((target, index) => {
      const mesh = sectionMesh(
        field,
        index === 0 ? 'longitude' : 'latitude',
        index === 0 ? settings.sectionX : settings.sectionY,
        settings.log,
      );
      const coordinates = new Float32Array(mesh.points.length);
      for (let i = 0; i < mesh.points.length; i += 3)
        coordinates.set(
          d.xyz(mesh.points[i], mesh.points[i + 1], mesh.points[i + 2]),
          i,
        );
      target.data.getPoints().setData(coordinates, 3);
      target.data.getPolys().setData(mesh.polys);
      c.sectionScalars[index].setData(
        new Float32Array(
          mesh.values.map((v) => displayScalar(v, settings.log)),
        ),
      );
      target.data.modified();
      positions.push(mesh.position);
    });
    setSectionPositions(positions);
    c.win.render();
  }, [
    field,
    settings.mode,
    settings.sectionX,
    settings.sectionY,
    settings.log,
    settings.exaggeration,
  ]);

  useEffect(() => {
    const c = context.current;
    if (!c) return;
    const d = dimensions(field, settings.exaggeration),
      lon = field.axes.longitude,
      lat = field.axes.latitude,
      bounds = [lon[0], lat[0], lon.at(-1)!, lat.at(-1)!];
    const points: number[] = [],
      links: number[] = [];
    for (const line of coastline)
      for (let i = 1; i < line.length; i++) {
        const segment = clipSegment(line[i - 1], line[i], bounds);
        if (!segment) continue;
        const n = points.length / 3;
        points.push(
          ...d.xyz(...segment[0], field.axes.depth[0]),
          ...d.xyz(...segment[1], field.axes.depth[0]),
        );
        links.push(2, n, n + 1);
      }
    setLines(c.coast, points, links);
    const inBounds = profiles.filter(
      (p) =>
        p.longitude >= bounds[0] &&
        p.longitude <= bounds[2] &&
        p.latitude >= bounds[1] &&
        p.latitude <= bounds[3],
    );
    const instrumentPoints: number[] = [],
      instrumentLinks: number[] = [];
    for (const p of inBounds) {
      if (p.path?.length) {
        for (const [a, b] of clippedInstrumentPath(
          p.path,
          bounds,
          field.axes.depth[0],
          field.axes.depth.at(-1)!,
        )) {
          const offset = instrumentPoints.length / 3;
          instrumentPoints.push(
            ...d.xyz(a[0], a[1], a[2]),
            ...d.xyz(b[0], b[1], b[2]),
          );
          instrumentLinks.push(2, offset, offset + 1);
        }
        continue;
      }
      const a = Math.max(
          field.axes.depth[0],
          p.depth_range?.[0] ?? field.axes.depth[0],
        ),
        b = Math.min(
          field.axes.depth.at(-1)!,
          p.depth_range?.[1] ?? field.axes.depth.at(-1)!,
        );
      if (a > b) continue;
      const n = instrumentPoints.length / 3;
      instrumentPoints.push(
        ...d.xyz(p.longitude, p.latitude, a),
        ...d.xyz(p.longitude, p.latitude, b),
      );
      instrumentLinks.push(2, n, n + 1);
    }
    setLines(c.instruments, instrumentPoints, instrumentLinks);
    c.instruments.actor.setVisibility(settings.instruments);
    const missionPoints: number[] = [],
      missionLinks: number[] = [];
    for (const [a, b] of missionSegments(profiles)) {
      const segment = clipSegment(
        [a.longitude, a.latitude],
        [b.longitude, b.latitude],
        bounds,
      );
      if (!segment) continue;
      const n = missionPoints.length / 3;
      missionPoints.push(
        ...d.xyz(...segment[0], field.axes.depth[0]),
        ...d.xyz(...segment[1], field.axes.depth[0]),
      );
      missionLinks.push(2, n, n + 1);
    }
    setLines(c.missions, missionPoints, missionLinks);
    c.missions.actor.setVisibility(settings.instruments);
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!host.current) return;
        const size = c.rw.getApiSpecificRenderWindow().getSize(),
          rect = host.current.getBoundingClientRect();
        setLabels(
          settings.instruments
            ? arrangeInstrumentLabels(
                inBounds.map((p) => {
                  c.coordinate.setValue(
                    d.xyz(p.longitude, p.latitude, field.axes.depth[0]) as [
                      number,
                      number,
                      number,
                    ],
                  );
                  const [x, y] = c.coordinate.getComputedDoubleDisplayValue(
                    c.renderer,
                  );
                  return {
                    id: p.id,
                    instrument: p.instrument,
                    time: p.time,
                    x: (x / size[0]) * rect.width,
                    y: (1 - y / size[1]) * rect.height,
                    active: instrumentIsFresh(p, field.time),
                    short: p.id.split(':').at(-1)!.replace('DEMO-', ''),
                  };
                }),
                rect.width,
                rect.height,
              )
            : [],
        );
      });
    };
    c.updateLabels(update);
    update();
    c.win.render();
    return () => {
      cancelAnimationFrame(frame);
      c.updateLabels(() => {});
    };
  }, [field, profiles, settings.instruments, settings.exaggeration, coastline]);

  useEffect(() => {
    const c = context.current;
    if (!c) return;
    c.arrows.actor.setVisibility(false);
    c.flow.actor.setVisibility(false);
    c.particles.actor.setVisibility(false);
    setFlowStats('');
    setVectorStats('');
    if (
      vectors.length !== 2 ||
      !sameGrid(vectors[0], vectors[1]) ||
      !sameGrid(field, vectors[0])
    ) {
      c.win.render();
      return;
    }
    const d = dimensions(field, settings.exaggeration);
    const scale = vectorScaleKm(field);
    const sampling = currentGlyphs(
      vectors[0],
      vectors[1],
      settings.currentScope,
      settings.depth,
      settings.currentLayers,
    );
    const points: number[] = [],
      links: number[] = [],
      speeds: number[] = [];
    for (const q of sampling.glyphs) {
      const [east, north] = projectedCurrent(field, q);
      const lengthFactor =
        settings.currentStyle === 'direction' ? 0.6 / q.speed : 1;
      const a = d.xyz(q.longitude, q.latitude, q.depth),
        b = [
          a[0] + east * scale * lengthFactor,
          a[1] + north * scale * lengthFactor,
          a[2],
        ],
        n = points.length / 3,
        angle = Math.atan2(north, east),
        size = Math.min(q.speed * scale * lengthFactor * 0.35, scale * 0.16);
      speeds.push(q.speed, q.speed, q.speed, q.speed);
      points.push(
        ...a,
        ...b,
        b[0] - size * Math.cos(angle - 0.5),
        b[1] - size * Math.sin(angle - 0.5),
        b[2],
        b[0] - size * Math.cos(angle + 0.5),
        b[1] - size * Math.sin(angle + 0.5),
        b[2],
      );
      links.push(2, n, n + 1, 2, n + 1, n + 2, 2, n + 1, n + 3);
    }
    setLines(c.arrows, points, links);
    c.currentScalars.setData(new Float32Array(speeds));
    c.arrows.data.modified();
    c.arrows.actor.setVisibility(settings.currents);
    if (settings.currents)
      setVectorStats(
        `${sampling.glyphs.length.toLocaleString()} vectors · ${sampling.depths.length} display depth${sampling.depths.length === 1 ? '' : 's'} · ${settings.currentStyle === 'direction' ? 'equal-length direction arrows' : `1 m/s = ${scale.toFixed(1)} km`}`,
      );
    let paths: FlowPath[] = [];
    if (settings.flow) {
      const layers = currentDepths(
        field,
        settings.currentScope,
        settings.depth,
        6,
      );
      paths = seedFlow(vectors[0], vectors[1], settings.depth, layers);
      const p: number[] = [],
        l: number[] = [];
      for (const path of paths) {
        const offset = p.length / 3;
        path.points.forEach((q) =>
          p.push(...d.xyz(q.longitude, q.latitude, q.depth)),
        );
        l.push(path.points.length, ...path.points.map((_, i) => offset + i));
      }
      setLines(c.flow, p, l);
      c.flow.actor.setVisibility(true);
      c.particles.actor.setVisibility(true);
      setFlowStats(
        `${paths.length} streamlines · ${layers.length} display depth${layers.length === 1 ? '' : 's'} · frozen ${field.time.slice(11, 16)} UTC`,
      );
    }
    let frame = 0,
      lastFrame = 0;
    const animate = (now: number) => {
      if (
        document.hidden ||
        now - lastFrame < 1000 / (settings.mode === 'volume' ? 8 : 16)
      ) {
        frame = requestAnimationFrame(animate);
        return;
      }
      lastFrame = now;
      const p: number[] = [],
        verts: number[] = [];
      for (const path of paths) {
        const duration = path.points.at(-1)!.elapsed_s,
          elapsed = ((now / 1000) * 10800) % Math.max(1, duration);
        let i = 1;
        while (i < path.points.length - 1 && path.points[i].elapsed_s < elapsed)
          i++;
        const a = path.points[i - 1],
          b = path.points[i],
          f = (elapsed - a.elapsed_s) / Math.max(1, b.elapsed_s - a.elapsed_s),
          n = p.length / 3;
        p.push(
          ...d.xyz(
            a.longitude + (b.longitude - a.longitude) * f,
            a.latitude + (b.latitude - a.latitude) * f,
            a.depth,
          ),
        );
        verts.push(1, n);
      }
      c.particles.data.getPoints().setData(new Float32Array(p), 3);
      c.particles.data.getVerts().setData(new Uint32Array(verts));
      c.particles.data.modified();
      c.win.render();
      lastFrame = performance.now();
      frame = requestAnimationFrame(animate);
    };
    c.win.render();
    if (
      paths.length &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    )
      frame = requestAnimationFrame(animate);
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [
    field,
    vectors,
    settings.currents,
    settings.flow,
    settings.currentScope,
    settings.currentLayers,
    settings.currentStyle,
    settings.mode,
    settings.depth,
    settings.exaggeration,
  ]);

  return (
    <div className="scene-wrap">
      <div
        ref={host}
        className="vtk-host"
        aria-label="Interactive 3D ocean. Drag to rotate; scroll to zoom."
      />
      {error && (
        <div className="scene-error" role="alert">
          {error}
        </div>
      )}
      <div
        className="scene-labels"
        style={{
          opacity: settings.instrumentOpacity,
          visibility: settings.instrumentOpacity === 0 ? 'hidden' : 'visible',
        }}
      >
        <svg className="instrument-leaders" aria-hidden="true">
          {labels.map((p) => (
            <g key={p.id}>
              <line x1={p.anchorX} y1={p.anchorY} x2={p.x} y2={p.y} />
              <circle cx={p.anchorX} cy={p.anchorY} r="3" />
            </g>
          ))}
        </svg>
        {labels.map((p) => (
          <button
            key={p.id}
            data-instrument={p.instrument}
            className={`marker ${p.id === settings.profile ? 'selected' : ''} ${p.active ? '' : 'stale'}`}
            style={{ left: p.x, top: p.y }}
            onClick={() => onSelect(p.id)}
            title={`${p.instrument} · ${p.short} · ${p.time}${p.active ? '' : ' · outside ±24 h'}`}
          >
            <i />
            {p.short}
          </button>
        ))}
      </div>
      <div className="scene-tools">
        <button
          onClick={() => setView.current('top')}
          aria-label="Top view"
          title="Top view"
        >
          TOP
        </button>
        <button
          onClick={() => setView.current('front')}
          aria-label="Front view"
          title="Front view"
        >
          FRONT
        </button>
        <button
          onClick={() => reset.current()}
          aria-label="Reset camera"
          title="Reset camera"
        >
          <RotateCcw size={17} />
        </button>
        <button
          aria-label="Fullscreen"
          title="Fullscreen"
          onClick={() => {
            const p = document.fullscreenElement
              ? document.exitFullscreen()
              : host.current?.parentElement?.requestFullscreen();
            p?.catch(() => setError('Fullscreen unavailable.'));
          }}
        >
          <Maximize2 size={17} />
        </button>
      </div>
      <GeoOverview field={field} profiles={profiles} />
      <div className="depth-label">
        {field.axes.depth[0]} m top
        <br />
        <span>{field.axes.depth.at(-1)} m extent</span>
        {(settings.mode === 'slice' || settings.mode === 'sections') && (
          <>
            <br />
            <span>
              Slice:{' '}
              {field.axes.depth
                .reduce((a, b) =>
                  Math.abs(b - settings.depth) < Math.abs(a - settings.depth)
                    ? b
                    : a,
                )
                .toFixed(1)}{' '}
              m
            </span>
          </>
        )}
      </div>
      {settings.mode === 'sections' && sectionPositions.length === 2 && (
        <div className="section-badge">
          {sectionPositions[0].toFixed(2)}°E × {sectionPositions[1].toFixed(2)}
          °N
          <br />
          <span>Intersecting sections · gaps stay open</span>
        </div>
      )}
      {settings.mode === 'isosurface' && settings.log && settings.iso <= 0 ? (
        <div className="contour-notice">
          This isovalue is nonpositive and hidden on a logarithmic scale. Choose
          a positive isovalue or a linear scale.
        </div>
      ) : (
        settings.mode === 'isosurface' &&
        surfaceTriangles === 0 && (
          <div className="contour-notice">
            No supported cells cross this isovalue. Adjust the value or
            displayed depth window.
          </div>
        )
      )}
      {(flowStats || vectorStats) && (
        <div className="flow-badge">
          {vectorStats && <div>{vectorStats}</div>}
          {vectorStats && (
            <div
              className="vector-speed-key"
              aria-label="Vector color: horizontal speed, 0 to 2 metres per second or greater"
            >
              <span>0</span>
              <i />
              <span>≥2 m/s</span>
            </div>
          )}
          {flowStats && <div>{flowStats}</div>}
          <span>
            Horizontal currents · vertical velocity unavailable
            {flowStats ? ' · motion ×10,800' : ''}
          </span>
        </div>
      )}
      <div className="scene-hint">
        Drag to orbit · Scroll to zoom · Vertical exaggeration{' '}
        {settings.exaggeration}×<br />
        <span>
          Regional equirectangular coordinates · opacity is a display choice
        </span>
      </div>
    </div>
  );
}
