'use client';
/* oxlint-disable jsx-a11y/prefer-tag-over-role -- Scientific SVG charts use named img roles and adjacent numeric controls. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Globe2, Layers3, ArrowUpRight, Download, Search } from 'lucide-react';
import { SourceChoice } from './SourceChoice';
import {
  apiConnected,
  apiSourceAccess,
  color,
  download,
  fmt,
} from '@/lib/ocean';
import {
  regions,
  intersectRegion,
  longitudeLabel,
  latitudeLabel,
  loadCoastline,
  clipSegment,
  type Coastline,
} from '@/lib/geography';
import './sources.css';
import SyncPanel from './SyncPanel';

interface Product {
  catalog_revision?: string;
  sync_error?: string;
  id: string;
  title: string;
  kind: 'volume' | 'surface' | 'observations';
  institution: string;
  start: string;
  end: string;
  bounds: number[];
  times?: string[];
  variables: {
    id: string;
    label: string;
    units: string;
    source_units?: string;
  }[];
  metadata_url: string;
  note: string;
  model_id?: string;
  snapshot?: { path: string; time: string };
  vertical_axis?: { name: string; values: number[]; units: string } | null;
  status?: string;
}
interface SourceCatalog {
  revision?: string;
  products: Product[];
  retrieved_at: string;
  scope: string;
  source_url: string;
}
interface Grid {
  product: string;
  time: string;
  longitude: number[];
  latitude: number[];
  fields: Record<string, (number | null)[]>;
  source_url: string;
  native_source_url?: string;
  source_sha256: string;
  retrieved_at: string;
  sampling: Record<string, { stride: number; native_cells: number }>;
  vertical_index: number;
}
async function request<T>(
  url: string,
  signal?: AbortSignal,
  body?: object,
): Promise<T> {
  const r = await fetch(url, {
    signal,
    ...(body
      ? {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      : {}),
  });
  if (!r.ok) {
    let message = `Source request failed (${r.status})`;
    try {
      message = ((await r.json()) as { detail?: string }).detail || message;
    } catch {}
    throw Error(message);
  }
  return r.json();
}
type Coast = {
  features: {
    geometry: {
      type: string;
      coordinates: number[][] | number[][][] | number[][][][];
    };
  }[];
};
function GridMap({
  grid,
  variable,
  palette,
  range,
  onProbe,
}: {
  grid: Grid;
  variable: string;
  palette: string;
  range: number[];
  onProbe: (i: number) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null),
    [coast, setCoast] = useState<Coast | null>(null);
  useEffect(() => {
    const c = new AbortController();
    fetch('/geography/coastline.geojson', { signal: c.signal })
      .then((r) => r.json() as Promise<Coast>)
      .then(setCoast)
      .catch(() => {});
    return () => c.abort();
  }, []);
  useEffect(() => {
    const canvas = ref.current,
      values = grid.fields[variable];
    if (!canvas || !values) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const w = 1000,
      h = 540,
      pad = 42,
      nx = grid.longitude.length,
      ny = grid.latitude.length;
    canvas.width = w;
    canvas.height = h;
    const [west, east] = [grid.longitude[0], grid.longitude.at(-1)!],
      [south, north] = [grid.latitude[0], grid.latitude.at(-1)!];
    const x = (lon: number) =>
        pad + ((lon - west) / (east - west)) * (w - pad * 2),
      y = (lat: number) =>
        h - pad - ((lat - south) / (north - south)) * (h - pad * 2);
    ctx.fillStyle = '#091b28';
    ctx.fillRect(0, 0, w, h);
    ctx.save();
    ctx.beginPath();
    ctx.rect(pad, pad, w - 2 * pad, h - 2 * pad);
    ctx.clip();
    for (let j = 0; j < ny; j++)
      for (let i = 0; i < nx; i++) {
        const v = values[j * nx + i];
        if (v == null) continue;
        const lo =
            i === 0 ? west : (grid.longitude[i - 1] + grid.longitude[i]) / 2,
          hi =
            i === nx - 1
              ? east
              : (grid.longitude[i] + grid.longitude[i + 1]) / 2;
        const la =
            j === 0 ? south : (grid.latitude[j - 1] + grid.latitude[j]) / 2,
          lb =
            j === ny - 1
              ? north
              : (grid.latitude[j] + grid.latitude[j + 1]) / 2;
        ctx.fillStyle = color(v, range[0], range[1], palette);
        ctx.fillRect(
          x(lo),
          y(lb),
          Math.max(0.5, x(hi) - x(lo)),
          Math.max(0.5, y(la) - y(lb)),
        );
      }
    ctx.strokeStyle = '#cde4ea';
    ctx.lineWidth = 0.7;
    for (const f of coast?.features || []) {
      const lines =
        f.geometry.type === 'LineString'
          ? [f.geometry.coordinates as number[][]]
          : f.geometry.type === 'MultiPolygon'
            ? (f.geometry.coordinates as number[][][][]).flat()
            : (f.geometry.coordinates as number[][][]);
      for (const line of lines) {
        ctx.beginPath();
        let previous: number | null = null;
        for (const p of line) {
          const lon = west >= 0 && p[0] < 0 ? p[0] + 360 : p[0];
          if (previous == null || Math.abs(lon - previous) > 180)
            ctx.moveTo(x(lon), y(p[1]));
          else ctx.lineTo(x(lon), y(p[1]));
          previous = lon;
        }
        ctx.stroke();
      }
    }
    ctx.restore();
    ctx.font = '14px system-ui';
    ctx.fillStyle = '#b6cdd9';
    ctx.textAlign = 'center';
    for (let i = 0; i < 5; i++) {
      const lon = west + ((east - west) * i) / 4;
      ctx.fillText(longitudeLabel(lon), x(lon), h - 16);
    }
    ctx.textAlign = 'left';
    for (let j = 0; j < 5; j++) {
      const lat = south + ((north - south) * j) / 4;
      ctx.fillText(latitudeLabel(lat), 3, y(lat) - 5);
    }
  }, [grid, variable, palette, range, coast]);
  return (
    <canvas
      ref={ref}
      className="source-map"
      aria-label="Geographic source grid. Missing cells remain dark; coastline is geographic context. Select a cell to read its native value."
      onClick={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        const fx = Math.max(
            0,
            Math.min(1, ((1000 * (e.clientX - r.left)) / r.width - 42) / 916),
          ),
          fy = Math.max(
            0,
            Math.min(1, ((540 * (e.clientY - r.top)) / r.height - 42) / 456),
          );
        const lo =
            grid.longitude[0] +
            fx * (grid.longitude.at(-1)! - grid.longitude[0]),
          la =
            grid.latitude.at(-1)! -
            fy * (grid.latitude.at(-1)! - grid.latitude[0]);
        const nearest = (a: number[], v: number) =>
          a.reduce(
            (b, n, i) => (Math.abs(n - v) < Math.abs(a[b] - v) ? i : b),
            0,
          );
        onProbe(
          nearest(grid.latitude, la) * grid.longitude.length +
            nearest(grid.longitude, lo),
        );
      }}
    />
  );
}
function GridProduct({
  p,
  onOpen,
}: {
  p: Product;
  onOpen: (id: string, time: string) => Promise<void>;
}) {
  const [grid, setGrid] = useState<Grid | null>(null),
    [variable, setVariable] = useState(
      p.variables.find((v) =>
        [
          'T_ANALYZED',
          'TEMP',
          'SST',
          'sst',
          'CHL',
          'CHLOROPHYLL',
          'wind_speed',
          'WIND_SPEED',
          'ASST',
          'MLD',
        ].includes(v.id),
      )?.id || p.variables[0].id,
    ),
    [index, setIndex] = useState(p.times!.length - 1),
    [depth, setDepth] = useState(0),
    [bbox, setBbox] = useState(p.bounds.map(String)),
    [palette, setPalette] = useState('thermal'),
    [busy, setBusy] = useState(true),
    [error, setError] = useState(''),
    [cell, setCell] = useState(0);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => {
    const c = new AbortController();
    abort.current = c;
    (p.catalog_revision && !p.snapshot
      ? Promise.reject(
          Error(
            'No validated synchronized packet is available. Review refresh results or request a bounded selection below.',
          ),
        )
      : request<Grid>(p.snapshot?.path || '/incois/' + p.id + '.json', c.signal)
    )
      .then((d) => {
        setGrid(d);
        setCell(0);
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setBusy(false);
      });
    return () => abort.current?.abort();
  }, [p]);
  const values = grid?.fields[variable],
    range = useMemo(() => {
      let lo = Infinity,
        hi = -Infinity;
      for (const v of values || [])
        if (v != null) {
          lo = Math.min(lo, v);
          hi = Math.max(hi, v);
        }
      return Number.isFinite(lo) ? [lo, hi === lo ? hi + 1 : hi] : [0, 1];
    }, [values]);
  const meta = p.variables.find((v) => v.id === variable)!;
  const loaded = async () => {
    abort.current?.abort();
    const c = new AbortController();
    abort.current = c;
    setBusy(true);
    setError('');
    setGrid(null);
    try {
      const bounds = bbox.map((v) => (v.trim() === '' ? NaN : Number(v)));
      if (!bounds.every(Number.isFinite))
        throw Error('Enter four finite geographic bounds.');
      const q = new URLSearchParams({
        product: p.id,
        variable,
        index: String(index),
        depth: String(depth),
        bbox: bounds.join(','),
        revision: p.catalog_revision || 'bundled',
      });
      setGrid(await request<Grid>('/api/incois/grid?' + q, c.signal));
      setCell(0);
    } catch (e) {
      if (!c.signal.aborted) setError(String((e as Error).message));
    } finally {
      if (!c.signal.aborted) setBusy(false);
    }
  };
  const open = async () => {
    setBusy(true);
    setError('');
    try {
      if (index === p.times!.length - 1 && p.model_id)
        await onOpen(p.model_id, p.times![index]);
      else {
        const model = await request<{ id: string }>(
          '/api/incois/open',
          undefined,
          { product: p.id, index, revision: p.catalog_revision || 'bundled' },
        );
        await onOpen(model.id, p.times![index]);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="source-detail" aria-label="Selected source product">
      <div className="source-product-heading">
        <span className="eyebrow">
          {p.kind === 'volume'
            ? '24-LEVEL WATER COLUMN'
            : 'SURFACE / DIAGNOSTIC FIELD'}
        </span>
        <h2>{p.title}</h2>
        <p>{p.note}</p>
        {p.sync_error && (
          <p role="status">
            Latest refresh failed: {p.sync_error}. Any retained packet keeps its
            original timestamp.
          </p>
        )}
      </div>
      <div className="source-controls">
        <SourceChoice
          label="Source variable"
          value={variable}
          options={p.variables.map((v) => ({
            value: v.id,
            label: `${v.label} · ${v.id}`,
          }))}
          onChange={setVariable}
          disabled={busy}
        />
        <SourceChoice
          label="Palette"
          value={palette}
          options={['thermal', 'viridis', 'ice', 'balance'].map((v) => ({
            value: v,
            label: v,
          }))}
          onChange={setPalette}
        />
        <label>
          Archive date
          <input
            aria-label="Archive date"
            type="date"
            min={p.start.slice(0, 10)}
            max={p.end.slice(0, 10)}
            value={p.times![index].slice(0, 10)}
            disabled={busy || !apiSourceAccess()}
            onInput={(e) => {
              if (!e.currentTarget.value) return;
              const date = Date.parse(e.currentTarget.value);
              setIndex(
                p.times!.reduce(
                  (b, t, i) =>
                    Math.abs(Date.parse(t) - date) <
                    Math.abs(Date.parse(p.times![b]) - date)
                      ? i
                      : b,
                  0,
                ),
              );
            }}
          />
        </label>
        {p.vertical_axis && (
          <SourceChoice
            label={
              p.kind === 'volume'
                ? 'Source depth'
                : 'Published vertical coordinate'
            }
            value={String(depth)}
            options={p.vertical_axis.values.map((z, i) => ({
              value: String(i),
              label: `${z} ${p.vertical_axis!.units}`,
            }))}
            onChange={(s) => setDepth(Number(s))}
            disabled={busy || !apiSourceAccess()}
          />
        )}
      </div>
      <div className="source-selection">
        <span>
          Selected source timestamp: <b>{p.times![index].replace('T', ' ')}</b>{' '}
          · {index + 1} / {p.times!.length.toLocaleString()} archived steps
        </span>
        <div>
          <button
            disabled={busy || !apiSourceAccess() || index === 0}
            onClick={() => setIndex(index - 1)}
          >
            Previous
          </button>
          <button
            disabled={
              busy || !apiSourceAccess() || index === p.times!.length - 1
            }
            onClick={() => setIndex(index + 1)}
          >
            Next
          </button>
        </div>
      </div>
      <details className="source-region">
        <summary>
          Geographic selection · {longitudeLabel(p.bounds[0])}–
          {longitudeLabel(p.bounds[2])}, {latitudeLabel(p.bounds[1])}–
          {latitudeLabel(p.bounds[3])}
        </summary>
        <div className="source-presets">
          <button onClick={() => setBbox(p.bounds.map(String))}>
            Full coverage
          </button>
          {regions.map((r) => {
            const b = intersectRegion(r.bounds, p.bounds);
            return b ? (
              <button key={r.id} onClick={() => setBbox(b.map(String))}>
                {r.label}
              </button>
            ) : null;
          })}
        </div>
        <div className="region-inputs">
          {['Source west', 'Source south', 'Source east', 'Source north'].map(
            (label, i) => (
              <label key={label}>
                {label}
                <input
                  aria-label={label}
                  value={bbox[i]}
                  type="number"
                  step="any"
                  onChange={(e) =>
                    setBbox(bbox.map((v, j) => (j === i ? e.target.value : v)))
                  }
                />
              </label>
            ),
          )}
        </div>
        <p>
          Longitude uses this source’s native convention. Surface display
          selects at most 240 cells per axis by a documented stride; it does not
          average or interpolate values.
        </p>
      </details>
      <div className="source-actions">
        <button
          className="primary-button"
          disabled={busy || !apiSourceAccess()}
          onClick={loaded}
        >
          Load selection
        </button>
        {p.kind === 'volume' && (
          <button
            disabled={
              busy || (!apiSourceAccess() && index !== p.times!.length - 1)
            }
            onClick={open}
          >
            <Layers3 size={16} /> Open full water column in 3D
          </button>
        )}
        <a href={p.metadata_url} target="_blank" rel="noreferrer">
          Source metadata <ArrowUpRight size={14} />
        </a>
      </div>
      {!apiSourceAccess() && (
        <p className="source-note">
          Bundled snapshot: all listed variables at the newest archived time and
          first source level. Historical and regional requests require a
          scientific API with upstream acquisition enabled.
        </p>
      )}
      {error && (
        <p role="alert" className="source-error">
          {error}
        </p>
      )}
      {busy && <output>Loading the selected INCOIS data…</output>}
      {grid && values && (
        <>
          <div className="source-loaded">
            <b>Loaded {grid.time.replace('T', ' ')}</b>
            <span>
              {meta.label} · {meta.units}
              {p.vertical_axis
                ? ` · source level ${p.vertical_axis.values[grid.vertical_index]} ${p.vertical_axis.units}`
                : ''}
            </span>
          </div>
          <GridMap
            grid={grid}
            variable={variable}
            palette={palette}
            range={range}
            onProbe={setCell}
          />
          <div className="source-scale">
            <span>
              {fmt(range[0])} {meta.units}
            </span>
            <i
              style={{
                background: `linear-gradient(90deg,${Array.from({ length: 8 }, (_, i) => color(range[0] + ((range[1] - range[0]) * i) / 7, range[0], range[1], palette)).join(',')})`,
              }}
            />
            <span>
              {fmt(range[1])} {meta.units}
            </span>
          </div>
          <div className="source-probe">
            <label>
              Grid-cell index
              <input
                aria-label="Grid-cell index"
                type="number"
                min={0}
                max={values.length - 1}
                value={cell}
                onChange={(e) =>
                  setCell(
                    Math.max(
                      0,
                      Math.min(values.length - 1, Number(e.target.value) || 0),
                    ),
                  )
                }
              />
            </label>
            <output>
              {longitudeLabel(grid.longitude[cell % grid.longitude.length])},{' '}
              {latitudeLabel(
                grid.latitude[Math.floor(cell / grid.longitude.length)],
              )}{' '}
              ·{' '}
              <b>
                {values[cell] == null
                  ? 'Missing'
                  : fmt(values[cell], 4) + ' ' + meta.units}
              </b>
            </output>
          </div>
          <p className="source-note">
            {values.filter((v) => v != null).length.toLocaleString()} /{' '}
            {values.length.toLocaleString()} finite source samples. Stride:
            longitude {grid.sampling.longitude.stride}, latitude{' '}
            {grid.sampling.latitude.stride}. Dark cells are missing, not zero.
          </p>
          <div className="source-actions">
            <button
              onClick={() =>
                download('incois-' + p.id + '-selection.json', grid)
              }
            >
              <Download size={16} /> Export displayed source data
            </button>
            <a
              href={grid.native_source_url || grid.source_url}
              target="_blank"
              rel="noreferrer"
            >
              Native NetCDF selection <ArrowUpRight size={14} />
            </a>
          </div>
          <details>
            <summary>Source verification</summary>
            <p className="source-hash">SHA-256 {grid.source_sha256}</p>
            <p>Retrieved {grid.retrieved_at}</p>
            {meta.source_units && (
              <p>
                Source units “{meta.source_units}” corrected to counts for this
                observation-count variable.
              </p>
            )}
          </details>
        </>
      )}
      {grid && !values && (
        <p className="source-note">
          Load the selection to retrieve this variable.
        </p>
      )}
    </section>
  );
}

type Channel = {
  depth: number | null;
  temp: number | null;
  psal: number | null;
  pres: number | null;
  qc: { pres: number; temp: number; psal: number };
};
interface Observations {
  start: string;
  end: string;
  source_rows: number;
  source_url: string;
  source_sha256: string;
  method: string;
  profiles: {
    id: string;
    float: string;
    cycle: number;
    direction: string;
    longitude: number;
    latitude: number;
    time: string;
    time_qc: number;
    levels: { raw: Channel; adjusted: Channel }[];
  }[];
}
function ObservationMap({
  profiles,
  selected,
  onSelect,
}: {
  profiles: Observations['profiles'];
  selected: string;
  onSelect: (id: string) => void;
}) {
  const [coast, setCoast] = useState<Coastline>([]);
  useEffect(() => {
    let active = true;
    loadCoastline()
      .then((c) => {
        if (active) setCoast(c);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  const b = [
    Math.max(-180, Math.min(30, ...profiles.map((p) => p.longitude - 5))),
    Math.max(-90, Math.min(-30, ...profiles.map((p) => p.latitude - 5))),
    Math.min(180, Math.max(120, ...profiles.map((p) => p.longitude + 5))),
    Math.min(90, Math.max(30, ...profiles.map((p) => p.latitude + 5))),
  ];
  const x = (v: number) => 35 + ((v - b[0]) / (b[2] - b[0])) * 730,
    y = (v: number) => 300 - ((v - b[1]) / (b[3] - b[1])) * 265;
  const path = coast
    .flatMap((line) =>
      line.slice(1).flatMap((point, i) => {
        if (Math.abs(point[0] - line[i][0]) > 180) return [];
        const seg = clipSegment(line[i], point, b);
        return seg
          ? [`M${x(seg[0][0])},${y(seg[0][1])}L${x(seg[1][0])},${y(seg[1][1])}`]
          : [];
      }),
    )
    .join(' ');
  return (
    <svg
      className="source-observation-map"
      viewBox="0 0 800 340"
      role="img"
      aria-label="Geographic locations of the selected INCOIS Argo profiles"
    >
      <title>
        Select a marker or use the Argo profile selector below. Locations retain
        the published coordinates; position quality flags are not exposed by the
        source table.
      </title>
      <path d={path} fill="none" stroke="#89aebc" strokeWidth={1} />
      {profiles.map((p) => (
        <g
          key={p.id}
          onClick={() => onSelect(p.id)}
          style={{ cursor: 'pointer' }}
        >
          <circle
            cx={x(p.longitude)}
            cy={y(p.latitude)}
            r={p.id === selected ? 7 : 5}
            fill={p.id === selected ? '#ffe19a' : '#61dabc'}
            stroke="#153445"
            strokeWidth={2}
          />
          <title>
            {p.float} · {p.time} · {longitudeLabel(p.longitude)},{' '}
            {latitudeLabel(p.latitude)}
          </title>
        </g>
      ))}
      <text x={35} y={323}>
        {longitudeLabel(b[0])}
      </text>
      <text x={700} y={323}>
        {longitudeLabel(b[2])}
      </text>
      <text x={5} y={20}>
        {latitudeLabel(b[3])}
      </text>
      <text x={5} y={300}>
        {latitudeLabel(b[1])}
      </text>
    </svg>
  );
}
function ObservationProduct({ p }: { p: Product }) {
  const [packet, setPacket] = useState<Observations | null>(null),
    [selected, setSelected] = useState(''),
    [channel, setChannel] = useState('raw'),
    [variable, setVariable] = useState<'temp' | 'psal'>('temp'),
    [start, setStart] = useState(p.end.slice(0, 10)),
    [busy, setBusy] = useState(true),
    [error, setError] = useState('');
  const abort = useRef<AbortController | null>(null);
  const load = async (remote = false) => {
    abort.current?.abort();
    const c = new AbortController();
    abort.current = c;
    setBusy(true);
    setError('');
    setPacket(null);
    try {
      const end = new Date(
        Math.min(Date.parse(start) + 86400000 - 1000, Date.parse(p.end)),
      ).toISOString();
      const from = new Date(
        Math.max(Date.parse(start), Date.parse(p.start)),
      ).toISOString();
      const url = remote
        ? '/api/incois/observations?' +
          new URLSearchParams({
            start: from,
            end,
            revision: p.catalog_revision || 'bundled',
          })
        : p.snapshot?.path || '/incois/Indian_ARGO_Floats.json';
      const d = await request<Observations>(url, c.signal);
      setPacket(d);
      setSelected(d.profiles[0]?.id || '');
    } catch (e) {
      if (!c.signal.aborted) setError((e as Error).message);
    } finally {
      if (!c.signal.aborted) setBusy(false);
    }
  };
  useEffect(() => {
    const c = new AbortController();
    abort.current = c;
    (p.catalog_revision && !p.snapshot
      ? Promise.reject(
          Error('No validated synchronized observation packet is available.'),
        )
      : request<Observations>(
          p.snapshot?.path || '/incois/Indian_ARGO_Floats.json',
          c.signal,
        )
    )
      .then((d) => {
        setPacket(d);
        setSelected(d.profiles[0]?.id || '');
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!c.signal.aborted) setBusy(false);
      });
    return () => c.abort();
  }, [p.catalog_revision, p.snapshot]);
  const profile = packet?.profiles.find((v) => v.id === selected),
    levels =
      profile?.levels
        .map((v) => v[channel as 'raw' | 'adjusted'])
        .filter((v) => v.depth != null)
        .sort((a, b) => a.depth! - b.depth!) || [];
  const points = levels.filter(
    (v) =>
      v[variable] != null &&
      [1, 2].includes(profile!.time_qc) &&
      [1, 2].includes(v.qc.pres) &&
      [1, 2].includes(v.qc[variable]),
  );
  const lo = variable === 'temp' ? -2 : 25,
    hi = variable === 'temp' ? 35 : 40,
    maxDepth = Math.max(2000, ...points.map((v) => v.depth!));
  let path = '',
    drawing = false;
  for (const l of levels) {
    const good = points.includes(l);
    if (!good) {
      drawing = false;
      continue;
    }
    path += `${drawing ? 'L' : 'M'}${55 + ((l[variable]! - lo) / (hi - lo)) * 410},${25 + (l.depth! / maxDepth) * 365}`;
    drawing = true;
  }
  return (
    <section className="source-detail">
      <span className="eyebrow">INDIVIDUAL IN-SITU OBSERVATIONS</span>
      <h2>{p.title}</h2>
      <p>{p.note}</p>
      <div className="source-controls">
        <label>
          Observation day (UTC)
          <input
            type="date"
            aria-label="Observation day"
            min={p.start.slice(0, 10)}
            max={p.end.slice(0, 10)}
            value={start}
            onInput={(e) => setStart(e.currentTarget.value)}
            disabled={busy || !apiSourceAccess()}
          />
        </label>
        <button
          disabled={busy || !apiSourceAccess() || !start}
          onClick={() => load(true)}
        >
          Load observation day
        </button>
      </div>
      <p className="source-note">
        The public table spans {p.start.slice(0, 10)} to {p.end.slice(0, 10)}.
        Request any day; the newest archived day is bundled. A day without
        records is reported by the source.
      </p>
      {error && <p role="alert">{error}</p>}
      {busy && <output>Retrieving INCOIS profiles…</output>}
      {packet && (
        <>
          <p>
            {packet.profiles.length} profiles · {packet.source_rows} source
            levels · {packet.start} to {packet.end}
          </p>
          <ObservationMap
            profiles={packet.profiles}
            selected={selected}
            onSelect={setSelected}
          />
          <div className="source-controls">
            <SourceChoice
              label="Argo profile"
              value={selected}
              options={packet.profiles.map((v) => ({
                value: v.id,
                label: `${v.float} · cycle ${v.cycle} ${v.direction}`,
              }))}
              onChange={setSelected}
            />
            <SourceChoice
              label="Measurement channel"
              value={channel}
              options={['adjusted', 'raw'].map((v) => ({ value: v, label: v }))}
              onChange={setChannel}
            />
            <SourceChoice
              label="Profile variable"
              value={variable}
              options={[
                { value: 'temp', label: 'In-situ temperature · °C' },
                { value: 'psal', label: 'Practical salinity · PSU' },
              ]}
              onChange={(s) => setVariable(s as 'temp' | 'psal')}
            />
          </div>
          {profile && (
            <>
              <p>
                {profile.time} · {longitudeLabel(profile.longitude)},{' '}
                {latitudeLabel(profile.latitude)}
              </p>
              <svg
                className="source-profile"
                viewBox="0 0 520 440"
                role="img"
                aria-label="Quality-filtered INCOIS depth profile"
              >
                <title>
                  Strict quality flags 1 and 2; missing or failed levels break
                  the line.
                </title>
                {[0, 0.25, 0.5, 0.75, 1].map((f) => (
                  <g key={f}>
                    <line
                      x1={55}
                      x2={465}
                      y1={25 + 365 * f}
                      y2={25 + 365 * f}
                      stroke="#294454"
                    />
                    <text x={4} y={30 + 365 * f}>
                      {Math.round(maxDepth * f)} m
                    </text>
                    <text x={55 + 410 * f} y={420}>
                      {fmt(lo + (hi - lo) * f, 1)}
                    </text>
                  </g>
                ))}
                <path d={path} fill="none" stroke="#64e7cf" strokeWidth={2} />
              </svg>
              <p>
                {points.length} / {levels.length} levels pass time, pressure and
                variable QC.{' '}
                {points.length === 0
                  ? 'No valid values in this channel. Select raw to inspect separately.'
                  : ''}
              </p>
            </>
          )}
          <p>{packet.method}</p>
          <div className="source-actions">
            <button
              onClick={() => download('incois-argo-observations.json', packet)}
            >
              Export profiles and original QC
            </button>
            <a href={packet.source_url} target="_blank" rel="noreferrer">
              Exact source table <ArrowUpRight size={14} />
            </a>
          </div>
          <p className="source-hash">SHA-256 {packet.source_sha256}</p>
        </>
      )}
    </section>
  );
}

export default function SourceLibrary({
  onOpen,
}: {
  onOpen: (id: string, time: string) => Promise<void>;
}) {
  const [catalog, setCatalog] = useState<SourceCatalog | null>(null),
    [selected, setSelected] = useState('incois_argo_mnt_McCreary'),
    [search, setSearch] = useState(''),
    [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const c = new AbortController();
    request<SourceCatalog>(
      apiConnected() ? '/api/incois/catalog' : '/incois/catalog.json',
      c.signal,
    )
      .then((value) => {
        setCatalog(value);
        setError('');
        setSelected((old) =>
          value.products.some((p) => p.id === old) ? old : value.products[0].id,
        );
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      });
    return () => c.abort();
  }, [reload]);
  if (error)
    return (
      <section className="source-note">
        <p role="alert">{error}</p>
        <button type="button" onClick={() => setReload((v) => v + 1)}>
          Retry source catalogue
        </button>
      </section>
    );
  if (!catalog) return <p>Opening the INCOIS source library…</p>;
  const product = catalog.products.find((p) => p.id === selected)!;
  return (
    <main className="source-library">
      {apiConnected() && !apiSourceAccess() && (
        <p className="source-note">
          Read-only archive service: installed 3D datasets remain available. New
          upstream selections are managed by your administrator on the ingestion
          service.
        </p>
      )}
      <div className="source-heading">
        <div>
          <span className="eyebrow">INCOIS SOURCE LIBRARY</span>
          <h1>Follow the data, across the ocean.</h1>
          <p>
            {catalog.products.length} public products · all published dates
            indexed · full source geography
          </p>
        </div>
        <Globe2 size={46} />
      </div>
      <SyncPanel
        revision={catalog.revision}
        onRefresh={() => setReload((n) => n + 1)}
      />
      <div className="source-layout">
        <aside className="source-list">
          <label className="source-search">
            <Search size={17} />
            <input
              aria-label="Find a source"
              placeholder="Find a product or variable"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          {[...catalog.products]
            .sort(
              (a, b) =>
                (a.kind === 'volume' ? 0 : 1) - (b.kind === 'volume' ? 0 : 1),
            )
            .filter((p) =>
              (p.title + ' ' + p.variables.map((v) => v.label).join(' '))
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((p) => (
              <button
                key={p.id}
                aria-pressed={selected === p.id}
                onClick={() => setSelected(p.id)}
              >
                <span>
                  {p.kind === 'volume'
                    ? 'WATER COLUMN'
                    : p.kind === 'surface'
                      ? 'SURFACE'
                      : 'INSTRUMENTS'}
                </span>
                <b>{p.title}</b>
                <small>
                  {p.start.slice(0, 4)}–{p.end.slice(0, 4)} ·{' '}
                  {p.variables.length} fields
                </small>
              </button>
            ))}
        </aside>
        {product.kind === 'observations' &&
        product.id !== 'Indian_ARGO_Floats' ? (
          <section className="source-detail">
            <h2>{product.title}</h2>
            <p>
              This source is indexed. Its native observation layout needs a
              reviewed adapter before records can be displayed.
            </p>
            <a href={product.metadata_url} target="_blank" rel="noreferrer">
              Inspect official source metadata
            </a>
          </section>
        ) : product.kind === 'observations' ? (
          <ObservationProduct
            key={product.id + (catalog.revision || 'bundled')}
            p={product}
          />
        ) : (
          <GridProduct
            key={product.id + (catalog.revision || 'bundled')}
            p={product}
            onOpen={onOpen}
          />
        )}
      </div>
      <footer className="source-footer">
        {catalog.scope} Catalogue retrieved {catalog.retrieved_at.slice(0, 10)}.{' '}
        <a href={catalog.source_url} target="_blank" rel="noreferrer">
          Official catalogue
        </a>
      </footer>
    </main>
  );
}
