/* oxlint-disable jsx-a11y/prefer-tag-over-role -- Inline SVG supplies an accessible scientific chart. */
import { useMemo, useState } from 'react';
import type { ModelInfo, Volume } from '@/lib/ocean';
import { sameGrid } from '@/lib/flow';
import { sampleCurrent } from '@/lib/currents';
import { latitudeLabel, longitudeLabel } from '@/lib/geography';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export default function CurrentEvidence({
  model,
  vectors,
  depth,
}: {
  model: ModelInfo;
  vectors: Volume[];
  depth: number;
}) {
  const [chosen, setChosen] = useState<{ lon: number; lat: number } | null>(
    null,
  );
  const u = vectors[0],
    v = vectors[1];
  const ready = !!u && !!v && sameGrid(u, v);
  const frameIndex = ready ? model.times.indexOf(u.time) : -1;
  const fallback = useMemo(() => {
    if (!ready) return null;
    const lon = (u.axes.longitude[0] + u.axes.longitude.at(-1)!) / 2;
    const lat = (u.axes.latitude[0] + u.axes.latitude.at(-1)!) / 2;
    let best: { lon: number; lat: number } | null = null,
      distance = Infinity;
    for (const y of u.axes.latitude)
      for (const x of u.axes.longitude) {
        const d = (x - lon) ** 2 + (y - lat) ** 2;
        if (d < distance && sampleCurrent(u, v, x, y, u.axes.depth[0])) {
          best = { lon: x, lat: y };
          distance = d;
        }
      }
    return best;
  }, [ready, u, v]);
  const point =
    chosen &&
    ready &&
    u.axes.longitude.includes(chosen.lon) &&
    u.axes.latitude.includes(chosen.lat)
      ? chosen
      : fallback;
  const rows =
    ready && point
      ? u.axes.depth.map((z) => sampleCurrent(u, v, point.lon, point.lat, z))
      : [];
  const selected =
    ready && point ? sampleCurrent(u, v, point.lon, point.lat, depth) : null;
  const max = Math.max(0.1, ...rows.map((row) => row?.speed || 0));
  const bottom = ready ? u.axes.depth.at(-1)! : 1,
    top = ready ? u.axes.depth[0] : 0;
  let path = '',
    open = false;
  rows.forEach((row) => {
    if (!row) {
      open = false;
      return;
    }
    path += `${open ? 'L' : 'M'}${48 + (row.speed / max) * 182},${25 + ((row.depth - top) / (bottom - top)) * 240} `;
    open = true;
  });
  const bearing =
    selected && selected.speed > 1e-6
      ? ((Math.atan2(selected.u, selected.v) * 180) / Math.PI + 360) % 360
      : null;
  return (
    <section
      className="current-evidence"
      aria-label="Current source and depth evidence"
    >
      <span className="eyebrow">HYCOM · REAL FORECAST SNAPSHOT</span>
      <h3>Currents through depth</h3>
      <p>
        Eastward and northward velocity at all 40 source depths, 0–5,000 m. Land
        and missing levels remain empty.
      </p>
      <p className="micro">{model.provenance.temporal_resolution}</p>
      {ready && point ? (
        <>
          <div className="current-probe-controls">
            <Select
              value={String(point.lon)}
              onValueChange={(value) =>
                setChosen({ ...point, lon: Number(value) })
              }
            >
              <SelectTrigger aria-label="Current probe longitude">
                <SelectValue>{longitudeLabel(point.lon)}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {u.axes.longitude.map((x) => (
                  <SelectItem key={x} value={String(x)}>
                    {longitudeLabel(x)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={String(point.lat)}
              onValueChange={(value) =>
                setChosen({ ...point, lat: Number(value) })
              }
            >
              <SelectTrigger aria-label="Current probe latitude">
                <SelectValue>{latitudeLabel(point.lat)}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {u.axes.latitude.map((y) => (
                  <SelectItem key={y} value={String(y)}>
                    {latitudeLabel(y)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <p className="micro">
            Loaded {u.time.replace('T', ' ').replace('Z', ' UTC')}
            {model.provenance.forecast_reference_times?.[frameIndex] && (
              <>
                <br />
                Initialized{' '}
                {model.provenance.forecast_reference_times[frameIndex]
                  .replace('T', ' ')
                  .replace('Z', ' UTC')}{' '}
                · lead +{model.provenance.forecast_lead_hours?.[frameIndex]} h
              </>
            )}
          </p>
          <svg
            viewBox="0 0 260 300"
            role="img"
            aria-label="Horizontal current speed versus depth at the selected location. Gaps are missing values."
          >
            {[0, 0.5, 1].map((f) => (
              <g key={f}>
                <line
                  x1="48"
                  x2="230"
                  y1={25 + 240 * f}
                  y2={25 + 240 * f}
                  stroke="#29414c"
                />
                <text x="42" y={29 + 240 * f} textAnchor="end">
                  {Math.round(top + (bottom - top) * f)}
                </text>
              </g>
            ))}
            <path d={path} fill="none" stroke="#62dbca" strokeWidth="2" />
            <text x="48" y="285">
              0
            </text>
            <text x="230" y="285" textAnchor="end">
              {max.toFixed(2)} m/s
            </text>
            <text x="48" y="14">
              DEPTH / m
            </text>
            {selected && (
              <circle
                cx={48 + (selected.speed / max) * 182}
                cy={25 + ((depth - top) / (bottom - top)) * 240}
                r="4"
                fill="#ffd48a"
              />
            )}
          </svg>
          <dl className="current-readout">
            <div>
              <dt>At {depth.toFixed(0)} m</dt>
              <dd>
                {selected ? `${selected.speed.toFixed(3)} m/s` : 'Missing'}
              </dd>
            </div>
            <div>
              <dt>Eastward / northward</dt>
              <dd>
                {selected
                  ? `${selected.u.toFixed(3)} / ${selected.v.toFixed(3)} m/s`
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>Direction towards</dt>
              <dd>
                {bearing === null ? '—' : `${bearing.toFixed(0)}° from north`}
              </dd>
            </div>
          </dl>
          <p className="micro">
            Probe samples the bounded display grid. Speed is √(u²+v²); direction
            is horizontal. No extrapolation through missing values.
          </p>
        </>
      ) : (
        <p className="micro">
          Enable Current vectors or Animated streamlines to inspect the velocity
          components.
        </p>
      )}
      <p className="micro">
        Horizontal stride 12 in this downloaded basin subset; all source depths
        retained. Streamlines freeze one timestamp and hold depth fixed.
        Vertical velocity is not provided.
      </p>
      <a href={model.provenance.metadata_url} target="_blank" rel="noreferrer">
        Official HYCOM metadata ↗
      </a>
      <a href={model.provenance.source_download_url} download>
        Download source current NetCDF ↓
      </a>
    </section>
  );
}
