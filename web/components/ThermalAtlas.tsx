'use client';
/* oxlint-disable jsx-a11y/prefer-tag-over-role -- Scientific SVGs have accessible names and adjacent numeric controls. */
import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import {
  Layers3,
  ArrowDownUp,
  Mountain,
  ArrowDownToLine,
  ArrowUpRight,
  ScanLine,
  LocateFixed,
} from 'lucide-react';
import {
  column,
  pairedChange,
  thermalSurface,
  crossingAt,
  monthName,
  changeRGB,
  subsetAtlas,
  subsetRelief,
  suggestedProbe,
  type ThermalAtlas as AtlasData,
  type Relief,
} from '@/lib/thermal';
import { download, fmt } from '@/lib/ocean';
import { useEvidenceTool } from '@/lib/evidence-tool';
import { regions, longitudeLabel, latitudeLabel } from '@/lib/geography';
import { SourceChoice } from './SourceChoice';
import type { AtlasMode } from './AtlasRenderer';
import './atlas.css';
const Renderer = lazy(() => import('./AtlasRenderer'));
const layerColors = ['#ffb579', '#62e3cc', '#629dff'];
const reasons = {
  crossing: 'Supported crossing',
  surface_below: 'Already colder at the shallowest depth',
  missing: 'Missing native level before a crossing',
  gap: 'Native depth gap exceeds 150 m',
  not_reached: 'Threshold not reached in the supported column',
};
const deltaColor = (v: number | null) =>
  v == null ? '#10232d' : `rgb(${changeRGB(v).join(',')})`;
function Profiles({
  data,
  cell,
  before,
  index,
  threshold,
}: {
  data: AtlasData;
  cell: number;
  before: number;
  index: number;
  threshold: number;
}) {
  const x = (v: number) => 35 + ((v - 2) / 30) * 220,
    y = (v: number) => 18 + (v / 500) * 210;
  const path = (frame: number) => {
    let out = '',
      open = false;
    column(data, frame, cell).forEach((v, z) => {
      if (v == null || data.depth[z] > 500) {
        open = false;
        return;
      }
      out += `${open ? 'L' : 'M'}${x(v)},${y(data.depth[z])}`;
      open = true;
    });
    return out;
  };
  return (
    <svg
      className="atlas-profiles"
      viewBox="0 0 282 260"
      role="img"
      aria-label="Native INCOIS monthly temperature profiles at the selected grid column, depth in metres"
    >
      <title>
        Analyzed temperature, not individual instrument observations. Dashed
        line is the reference month.
      </title>
      {[0, 100, 200, 300, 500].map((d) => (
        <g key={d}>
          <line x1={35} x2={255} y1={y(d)} y2={y(d)} stroke="#243944" />
          <text x={29} y={y(d) + 4} textAnchor="end">
            {d}
          </text>
        </g>
      ))}
      {[10, 20, 30].map((t) => (
        <text key={t} x={x(t)} y={246} textAnchor="middle">
          {t}°C
        </text>
      ))}
      <line
        x1={x(threshold)}
        x2={x(threshold)}
        y1={18}
        y2={228}
        stroke="#afc5ce"
        strokeDasharray="2 5"
      />
      <path
        d={path(before)}
        fill="none"
        stroke="#a6bfd7"
        strokeWidth={2}
        strokeDasharray="5 4"
      />
      <path d={path(index)} fill="none" stroke="#64e7cf" strokeWidth={2.5} />
      {[before, index].map((frame, i) => {
        const c = crossingAt(data, frame, cell, threshold);
        return c.depth != null && c.depth <= 500 ? (
          <circle
            key={i}
            cx={x(threshold)}
            cy={y(c.depth)}
            r={4}
            fill={i ? '#64e7cf' : '#a6bfd7'}
          />
        ) : null;
      })}
      <text x={35} y={11}>
        DEPTH / m
      </text>
    </svg>
  );
}

export default function ThermalAtlas() {
  const [allData, setData] = useState<AtlasData | null>(null),
    [allRelief, setRelief] = useState<Relief | null>(null),
    [error, setError] = useState('');
  const [region, setRegion] = useState('indian');
  const regionInfo = regions.find((r) => r.id === region)!;
  const data = useMemo(
    () => (allData ? subsetAtlas(allData, regionInfo.bounds) : null),
    [allData, regionInfo],
  );
  const relief = useMemo(
    () => (allRelief ? subsetRelief(allRelief, regionInfo.bounds) : null),
    [allRelief, regionInfo],
  );
  const [mode, setMode] = useState<AtlasMode>('layers'),
    [index, setIndex] = useState(2),
    [before, setBefore] = useState(0),
    [threshold, setThreshold] = useState(20);
  const [storedCell, setCell] = useState(143),
    [upper, setUpper] = useState(4000),
    [peel, setPeel] = useState(12),
    [layers, setLayers] = useState([true, true, true]),
    [curtain, setCurtain] = useState(false);
  const [supportOnly, setSupportOnly] = useState(false);
  const cell = data
    ? Math.max(
        0,
        Math.min(storedCell, data.longitude.length * data.latitude.length - 1),
      )
    : 0;
  useEffect(() => {
    const controller = new AbortController();
    fetch('/demo/incois-mnt-mccreary-latest/thermal-structure.json', {
      signal: controller.signal,
    })
      .then((r) => {
        if (!r.ok)
          throw Error(
            'The verified INCOIS thermal packet could not be loaded.',
          );
        return r.json() as Promise<AtlasData>;
      })
      .then((d: AtlasData) => {
        if (d.schema !== 'ocean3d-thermal-atlas-1')
          throw Error('Unsupported thermal data version.');
        setData(d);
        setCell(suggestedProbe(d, 0, 2, 20));
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setError(String(e.message));
      });
    fetch('/geography/indian-relief.json', { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw Error('Relief unavailable');
        return r.json() as Promise<Relief>;
      })
      .then(setRelief)
      .catch(() => {});
    return () => controller.abort();
  }, []);
  const change = useMemo(
    () => (data ? pairedChange(data, before, index, threshold) : null),
    [data, before, index, threshold],
  );
  const surfaces = useMemo(
    () => (data ? [28, 24, 20].map((t) => thermalSurface(data, index, t)) : []),
    [data, index],
  );
  useEvidenceTool(
    data && change
      ? {
          view: 'ocean_lab',
          loading: false,
          mode,
          threshold_C: threshold,
          reference_time: data.frames[before].time,
          selected_time: data.frames[index].time,
          location: {
            longitude: data.longitude[cell % data.longitude.length],
            latitude: data.latitude[Math.floor(cell / data.longitude.length)],
          },
          crossings: change.cells[cell],
          domain_summary: {
            paired_native_columns: change.count,
            locally_supported_both: change.localCount,
            median_depth_change_m: change.median,
          },
          provenance: data.provenance,
          relief: relief?.provenance,
          method: data.method,
          display: {
            upper_depth_exaggeration: mode === 'relief' ? 35 : upper,
            deep_and_land_exaggeration: 35,
            peel_percent: peel,
            layers,
            curtain,
            local_pairs_only: supportOnly,
          },
        }
      : { view: 'ocean_lab', loading: !error, error },
  );
  if (error)
    return (
      <main className="atlas-loading" role="alert">
        {error}
        <p>The Explorer and existing datasets remain available above.</p>
      </main>
    );
  if (!data || !change)
    return (
      <main className="atlas-loading">
        <Layers3 size={32} />
        <h1>Opening the Indian Ocean</h1>
        <p>Loading the verified INCOIS native columns…</p>
      </main>
    );
  const nx = data.longitude.length,
    lon = data.longitude[cell % nx],
    lat = data.latitude[Math.floor(cell / nx)],
    selected = change.cells[cell];
  const largestLocal = change.cells
    .map((v, i) => ({ ...v, i }))
    .filter((v) => v.delta != null && v.locallySupported)
    .sort((a, b) => Math.abs(b.delta!) - Math.abs(a.delta!))[0]?.i;
  const largest = supportOnly ? largestLocal : change.largest;
  const date = monthName(data.frames[index].time),
    reference = monthName(data.frames[before].time);
  const setMonth = (value: number) => {
    setIndex(value);
    if (value === before) setBefore(value === 0 ? 1 : 0);
  };
  const exportInvestigation = () =>
    download('ocean3d-thermal-investigation.json', {
      schema: 'ocean3d-thermal-investigation-1',
      mode,
      threshold_C: threshold,
      reference_time: data.frames[before].time,
      selected_time: data.frames[index].time,
      location: { longitude: lon, latitude: lat },
      crossings: selected,
      columns: {
        depth_m: data.depth,
        reference_temperature_C: column(data, before, cell),
        selected_temperature_C: column(data, index, cell),
        reference_local_count: column(data, before, cell, 'local_count'),
        selected_local_count: column(data, index, cell, 'local_count'),
      },
      domain_summary: {
        paired_native_columns: change.count,
        locally_supported_both: change.localCount,
        median_depth_change_m: change.median,
      },
      settings: {
        upper_depth_exaggeration: mode === 'relief' ? 35 : upper,
        deep_and_land_exaggeration: 35,
        peel_percent: peel,
        layers,
        curtain,
        local_pairs_only: supportOnly,
      },
      method: data.method,
      provenance: data.provenance,
      relief: relief?.provenance,
      limitations: [
        'Monthly analyzed isotherm displacement is not parcel motion or a cause attribution.',
        'Counts are per native cell and depth, not unique floats or accuracy.',
        'Threshold surfaces use the first downward crossing; multiple crossings are not represented.',
        'Terrain and temperature have separate native grids; terrain does not repair INCOIS masks.',
      ],
    });
  return (
    <main className="thermal-atlas">
      <div className="atlas-heading">
        <div>
          <div className="atlas-kicker">
            OCEAN LAB <span>/</span> INCOIS · {regionInfo.label.toUpperCase()}
          </div>
          <h1>
            See what changes <em>beneath.</em>
          </h1>
          <p>
            Real basin relief. Three thermal layers. Every change traceable to
            its source.
          </p>
        </div>
        <button className="atlas-export" onClick={exportInvestigation}>
          <ArrowDownToLine size={16} /> Export investigation
        </button>
      </div>
      <div className="atlas-regionbar">
        <SourceChoice
          label="Ocean region"
          value={region}
          options={regions.map((r) => ({ value: r.id, label: r.label }))}
          onChange={(id) => {
            setRegion(id);
            const d = subsetAtlas(
              allData!,
              regions.find((r) => r.id === id)!.bounds,
            );
            setCell(suggestedProbe(d, before, index, threshold));
            setUpper(
              id === 'indian' || id === 'south' || id === 'equatorial'
                ? 4000
                : 1000,
            );
          }}
        />
        <p>
          {data.longitude.length} × {data.latitude.length} native columns ·{' '}
          {longitudeLabel(data.longitude[0])}–
          {longitudeLabel(data.longitude.at(-1)!)} ·{' '}
          {latitudeLabel(data.latitude[0])}–
          {latitudeLabel(data.latitude.at(-1)!)}
        </p>
      </div>
      <div className="atlas-workspace">
        <section className="atlas-stage" aria-label="3D ocean investigation">
          <div className="atlas-modebar">
            <div
              className="atlas-modes"
              role="group"
              aria-label="Ocean lab view"
            >
              {(
                [
                  ['layers', 'Thermal layers', Layers3],
                  ['change', 'Monthly change', ArrowDownUp],
                  ['relief', 'Basin relief', Mountain],
                ] as const
              ).map(([id, label, Icon]) => (
                <button
                  key={id}
                  className={mode === id ? 'active' : ''}
                  aria-pressed={mode === id}
                  onClick={() => {
                    setMode(id);
                    if (id !== 'change') setSupportOnly(false);
                  }}
                >
                  <Icon size={16} />
                  {label}
                </button>
              ))}
            </div>
            <span className="atlas-source-pill">OFFICIAL DATA · SNAPSHOT</span>
          </div>
          <div className="atlas-stage-title">
            <div>
              <span>
                {mode === 'layers'
                  ? 'THERMAL ARCHITECTURE'
                  : mode === 'change'
                    ? 'ISOTHERM DEPTH CHANGE'
                    : 'THE SHAPE OF THE BASIN'}
              </span>
              <h2>
                {mode === 'layers'
                  ? 'A layered ocean'
                  : mode === 'change'
                    ? `${threshold}°C · ${reference} → ${date}`
                    : regionInfo.label}
              </h2>
            </div>
            <span className="atlas-date">{date}</span>
          </div>
          <Suspense
            fallback={
              <div className="atlas-scene atlas-loading">
                Preparing GPU geometry…
              </div>
            }
          >
            <Renderer
              key={region}
              atlas={data}
              relief={relief}
              mode={mode}
              index={index}
              before={before}
              threshold={threshold}
              cell={cell}
              upper={mode === 'relief' ? 35 : upper}
              peel={peel}
              layers={layers}
              curtain={curtain}
              supportOnly={supportOnly}
              onProbe={setCell}
            />
          </Suspense>
          <div className="atlas-legend">
            {mode === 'layers' ? (
              [28, 24, 20].map((t, i) => (
                <label key={t}>
                  <input
                    type="checkbox"
                    checked={layers[i]}
                    onChange={(e) =>
                      setLayers(
                        layers.map((v, j) => (j === i ? e.target.checked : v)),
                      )
                    }
                  />
                  <i style={{ background: layerColors[i] }} />
                  {t}°C
                  <span>
                    {surfaces[i].filter((x) => x.depth != null).length} native
                    columns
                  </span>
                </label>
              ))
            ) : mode === 'change' ? (
              <>
                <span>
                  <i style={{ background: '#57a6ff' }} />
                  Shallower
                </span>
                <div className="atlas-delta-gradient" />
                <span>
                  Deeper
                  <i style={{ background: '#fa8b5f' }} />
                </span>
                <small>−50 m · 0 · +50 m / display saturation</small>
              </>
            ) : (
              <span>
                NOAA ETOPO 2022 · actual elevation geometry · temperature layers
                hidden
              </span>
            )}
          </div>
          {mode === 'layers' && (
            <div className="atlas-layer-note">
              Staggered cutaways reveal each layer at its computed depth.
            </div>
          )}
          {curtain && mode !== 'relief' && (
            <div className="atlas-curtain-scale">
              <span>Section temperature · 2°C</span>
              <i />
              <span>32°C</span>
            </div>
          )}
          <div className="atlas-timeline">
            <div>
              <span>MONTHLY ANALYSIS</span>
              <b>{date}</b>
            </div>
            <div className="atlas-months">
              {data.frames.map((f, i) => (
                <button
                  key={f.time}
                  aria-pressed={i === index}
                  className={i === index ? 'active' : ''}
                  onClick={() => setMonth(i)}
                >
                  <span>0{i + 1}</span>
                  {monthName(f.time)}
                </button>
              ))}
            </div>
          </div>
          <div className="atlas-scene-controls">
            <label>
              Upper-ocean depth lens <b>{upper}×</b>
              <input
                aria-label="Upper-ocean depth lens"
                type="range"
                min={400}
                max={6000}
                step={100}
                value={upper}
                disabled={mode === 'relief'}
                onChange={(e) => setUpper(Number(e.target.value))}
              />
            </label>
            <label>
              Peel back thermal layers <b>{peel}%</b>
              <input
                aria-label="Peel back thermal layers"
                type="range"
                min={0}
                max={65}
                step={1}
                value={peel}
                disabled={mode === 'relief' || supportOnly}
                onChange={(e) => setPeel(Number(e.target.value))}
              />
            </label>
            <button
              className={curtain ? 'active' : ''}
              aria-pressed={curtain}
              disabled={mode === 'relief' || supportOnly}
              onClick={() => setCurtain(!curtain)}
            >
              <ScanLine size={17} /> Cross-section at probe
            </button>
          </div>
        </section>
        <aside className="atlas-inspector" aria-label="Thermal change evidence">
          <div className="atlas-inspector-title">
            <span>THE CHANGE LENS</span>
            <ArrowDownUp size={18} />
          </div>
          <h2>How deep is {threshold}°C?</h2>
          <p>Compare the first downward crossing in two monthly analyses.</p>
          <div className="atlas-comparison-controls">
            <label>
              Reference month
              <select
                aria-label="Reference month"
                value={before}
                onChange={(e) => setBefore(Number(e.target.value))}
              >
                {data.frames.map((f, i) => (
                  <option key={f.time} value={i} disabled={i === index}>
                    {monthName(f.time)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Isotherm
              <select
                aria-label="Comparison isotherm"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
              >
                {[18, 20, 22, 24, 26, 28].map((t) => (
                  <option key={t} value={t}>
                    {t}°C
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="atlas-domain-stats">
            <div>
              <strong>
                {fmt(change.median, 1)}
                <small>m</small>
              </strong>
              <span>median · all paired columns</span>
            </div>
            <div>
              <strong>{change.count}</strong>
              <span>paired native columns</span>
            </div>
          </div>
          <button
            className="atlas-discovery"
            disabled={largest == null}
            onClick={() => {
              if (largest != null) setCell(largest);
              setMode('change');
            }}
          >
            <LocateFixed size={16} /> Inspect largest depth change
            <ArrowUpRight size={16} />
          </button>
          <div className="atlas-map-caption">
            <span>SELECT A NATIVE GRID COLUMN</span>
            <span>1° grid</span>
          </div>
          <svg
            className="atlas-cell-map"
            viewBox={`0 0 ${nx * 16} ${data.latitude.length * 16}`}
            role="img"
            aria-label="Selectable map of native INCOIS isotherm depth change. Blue means shallower, orange deeper; dark cells have no paired crossing or are hidden by the local-observation filter."
          >
            <title>
              Use the longitude and latitude selectors below for keyboard
              access. Map cells are native analysis columns.
            </title>
            {change.cells.map((c, i) => (
              <rect
                key={i}
                x={(i % nx) * 16}
                y={(data.latitude.length - 1 - Math.floor(i / nx)) * 16}
                width={14}
                height={14}
                rx={2}
                fill={deltaColor(
                  supportOnly && !c.locallySupported ? null : c.delta,
                )}
                stroke={i === cell ? '#fff' : 'none'}
                strokeWidth={2}
                onClick={() => setCell(i)}
                aria-hidden="true"
              >
                <title>
                  {longitudeLabel(data.longitude[i % nx])}{' '}
                  {latitudeLabel(data.latitude[Math.floor(i / nx)])}:{' '}
                  {c.delta == null
                    ? 'no paired crossing'
                    : `${c.delta.toFixed(1)} m`}
                </title>
              </rect>
            ))}
          </svg>
          <div className="atlas-probe-select">
            <label>
              Longitude
              <select
                aria-label="Probe longitude"
                value={cell % nx}
                onChange={(e) =>
                  setCell(Math.floor(cell / nx) * nx + Number(e.target.value))
                }
              >
                {data.longitude.map((v, i) => (
                  <option key={v} value={i}>
                    {longitudeLabel(v)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Latitude
              <select
                aria-label="Probe latitude"
                value={Math.floor(cell / nx)}
                onChange={(e) =>
                  setCell(Number(e.target.value) * nx + (cell % nx))
                }
              >
                {data.latitude.map((v, i) => (
                  <option key={v} value={i}>
                    {latitudeLabel(v)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="atlas-source-support">
            <span>LOCAL OBSERVATIONS AT BOTH CROSSINGS</span>
            <strong>
              {change.localCount}
              <small> / {change.count} paired columns</small>
            </strong>
            <p>
              Surrounding profiles can support the other columns. This count
              describes source support, not accuracy.
            </p>
            <label className="atlas-support-toggle">
              <input
                type="checkbox"
                checked={supportOnly}
                onChange={(e) => {
                  setSupportOnly(e.target.checked);
                  setMode('change');
                  setPeel(0);
                  setCurtain(false);
                  if (e.target.checked && largestLocal != null)
                    setCell(largestLocal);
                }}
              />
              Only pairs with local observations
            </label>
            {supportOnly && (
              <p>
                Showing {change.localCount} native pairs as points and depth
                connectors. A surface needs four adjacent eligible columns.
                Summary statistics above still describe all {change.count}{' '}
                pairs.
              </p>
            )}
            <div className="atlas-map-mini-legend">
              <i />
              Shallower · unchanged · deeper
            </div>
            <b>
              At this probe:{' '}
              {selected.delta == null
                ? 'no paired crossing'
                : `${selected.delta >= 0 ? '+' : ''}${selected.delta.toFixed(1)} m`}
            </b>
            <p>
              The profiles and native crossing brackets are directly below the
              scene.
            </p>
          </div>
        </aside>
        <section
          className="atlas-column-evidence"
          aria-label="Selected column evidence"
        >
          <div className="atlas-probe-heading">
            <span>SELECTED COLUMN</span>
            <h3>
              {longitudeLabel(lon)} · {latitudeLabel(lat)}
            </h3>
            <strong>
              {selected.delta == null
                ? 'No paired crossing'
                : `${selected.delta >= 0 ? '+' : ''}${selected.delta.toFixed(1)} m`}
              <small>
                {selected.delta == null
                  ? 'See native support below'
                  : selected.delta >= 0
                    ? ' deeper'
                    : ' shallower'}
              </small>
            </strong>
          </div>
          <div className="atlas-probe-chart">
            <Profiles
              data={data}
              cell={cell}
              before={before}
              index={index}
              threshold={threshold}
            />
            <div className="atlas-profile-legend">
              <span>
                <i />
                {reference} · reference
              </span>
              <span>
                <i />
                {date}
              </span>
            </div>
          </div>
          <div className="atlas-probe-details">
            <div className="atlas-brackets">
              {[selected.before, selected.after].map((c, i) => (
                <div key={i}>
                  <b>{i ? date : reference}</b>
                  <strong>{fmt(c.depth, 1)} m</strong>
                  <span>
                    {c.bracket
                      ? `Native bracket ${c.bracket[0]}–${c.bracket[1]} m`
                      : reasons[c.reason]}
                  </span>
                  <span>
                    {c.local == null
                      ? 'Local support unavailable'
                      : `${c.local} local · ${c.influence ?? '—'} in influence region`}
                  </span>
                </div>
              ))}
            </div>
            <p className="atlas-support-note">
              {selected.locallySupported
                ? 'Both crossing brackets have local observations.'
                : 'At least one crossing lacks local-box observations or is unavailable.'}{' '}
              Counts are minima over the two bracket levels; surrounding
              profiles may support the analysis.
            </p>
          </div>
        </section>
      </div>
      <section className="atlas-reading-guide">
        <div>
          <span>01 / GEOMETRY</span>
          <h3>Real shape, explicit scale</h3>
          <p>
            ETOPO 2022 relief is sampled at 0.25°. The upper 500 m is expanded
            for inspection; deeper relief and land use 35×. The depth transform
            is continuous, but its scale changes at 500 m.
          </p>
        </div>
        <div>
          <span>02 / EVIDENCE</span>
          <h3>A change you can inspect</h3>
          <p>
            {change.localCount} of {change.count} paired native columns have
            local observations at both months’ crossing brackets. Surface
            interpolation adds visual detail; every metric uses the original
            INCOIS 1° grid and 24 depths.
          </p>
        </div>
        <div>
          <span>03 / INTERPRETATION</span>
          <h3>Monthly structure, not motion</h3>
          <p>
            A deeper temperature surface is a change in the analyzed field. It
            does not establish vertical water motion, cause, forecast skill or
            an individual instrument track. Source temperature convention
            remains unspecified.
          </p>
        </div>
      </section>
      <div className="atlas-source-links">
        <a href={data.provenance.metadata_url} target="_blank" rel="noreferrer">
          INCOIS source metadata <ArrowUpRight size={14} />
        </a>
        <a
          href="https://www.ncei.noaa.gov/products/etopo-global-relief-model"
          target="_blank"
          rel="noreferrer"
        >
          NOAA ETOPO 2022 <ArrowUpRight size={14} />
        </a>
        <span>
          INCOIS retrieved {data.provenance.retrieved_at?.slice(0, 10)} ·
          monthly snapshots
        </span>
      </div>
    </main>
  );
}
