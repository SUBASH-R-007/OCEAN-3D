/* oxlint-disable jsx-a11y/prefer-tag-over-role -- SVG charts need role=img with a named description. */
import { useEffect, useState } from 'react';
import {
  loadDiagnostics,
  type Diagnostics,
  type Crossing,
} from '@/lib/diagnostics';
import { fmt, download, type Settings, type Profile } from '@/lib/ocean';
import { Activity, ArrowDownToLine } from 'lucide-react';
function result(value: Crossing | undefined) {
  return value?.depth_m == null ? 'Unresolved' : `${fmt(value.depth_m, 1)} m`;
}
export default function DiagnosticsPanel({
  settings,
  profile,
  onData,
}: {
  settings: Settings;
  profile?: Profile;
  onData: (d: Diagnostics | null) => void;
}) {
  const [data, setData] = useState<Diagnostics | null>(null),
    [error, setError] = useState('');
  const { model, index, profile: profileId } = settings;
  useEffect(() => {
    const abort = new AbortController();
    let active = true;
    void Promise.resolve().then(() => {
      if (active) {
        setData(null);
        setError('');
        onData(null);
      }
    });
    if (profile)
      loadDiagnostics(
        { model, index, profile: profileId },
        profile.longitude,
        profile.latitude,
        abort.signal,
      )
        .then((d) => {
          if (active) {
            setData(d);
            onData(d);
          }
        })
        .catch((e) => {
          if (active && e.name !== 'AbortError') setError(e.message);
        });
    return () => {
      active = false;
      abort.abort();
    };
  }, [model, profileId, index, profile, onData]);
  if (!profile)
    return (
      <div className="empty-state">
        Select an instrument location to inspect its water column.
      </div>
    );
  if (error) return <output className="empty-state">{error}</output>;
  if (!data)
    return (
      <div className="empty-state">Computing water-column diagnostics…</div>
    );
  const rows = data.rows.filter(
      (r) => r.depth <= Math.min(500, data.rows.at(-1)!.depth),
    ),
    sigmas = rows.flatMap((r) => (r.sigma0 == null ? [] : [r.sigma0]));
  const min = Math.min(...sigmas),
    max = Math.max(...sigmas),
    deep = Math.max(1, ...rows.map((r) => r.depth));
  const x = (s: number) => 45 + ((s - min) / Math.max(0.1, max - min)) * 200,
    y = (z: number) => 25 + (z / deep) * 225;
  let path = '',
    previous = false;
  for (const r of rows) {
    if (r.sigma0 == null) {
      previous = false;
      continue;
    }
    path += `${previous ? 'L' : 'M'}${x(r.sigma0)},${y(r.depth)} `;
    previous = true;
  }
  return (
    <div className="diagnostics-panel">
      <section>
        <div className="label-row">
          <h3>
            <Activity size={15} /> Water-column physics
          </h3>
          <span className="good-tag">TEOS-10</span>
        </div>
        <p className="micro">
          At {profile.latitude.toFixed(3)}°N, {profile.longitude.toFixed(3)}°E
          <br />
          Model scene: {data.time.replace('T', ' ').replace('Z', ' UTC')}
          <br />
          Observed cast:{' '}
          {data.observation?.time.replace('T', ' ').replace('Z', ' UTC') ||
            'Unavailable'}
        </p>
        <div className="diagnostic-stat">
          <span>
            Density mixed-layer depth<small>Δσ₀ = 0.03 kg/m³ from 10 m</small>
          </span>
          <strong>{result(data.density_mld)}</strong>
        </div>
        <div className="diagnostic-stat">
          <span>
            Temperature departure depth<small>|Δθ| = 0.2°C from 10 m</small>
          </span>
          <strong>{result(data.temperature_departure_depth)}</strong>
        </div>
        <div className="diagnostic-stat">
          <span>
            Signed layer separation
            <small>
              Equivalent density criterion · {data.barrier_layer.status}
            </small>
          </span>
          <strong>
            {data.barrier_layer.signed_thickness_m == null
              ? 'Unresolved'
              : `${fmt(data.barrier_layer.signed_thickness_m, 1)} m`}
          </strong>
        </div>
        <p className="micro">
          Positive separation indicates a barrier layer; negative indicates
          compensation. This uses the temperature-equivalent density threshold,
          separate from the fixed 0.03 MLD.
        </p>
      </section>
      {!!sigmas.length && (
        <svg
          className="density-chart"
          viewBox="0 0 276 280"
          role="img"
          aria-label="TEOS-10 potential density anomaly versus model depth"
        >
          <title>
            Model sigma zero and resolved density mixed-layer crossing
          </title>
          {[0, 0.5, 1].map((t) => (
            <g key={t}>
              <line
                x1="45"
                x2="245"
                y1={25 + t * 225}
                y2={25 + t * 225}
                stroke="#29414f"
              />
              <text x="37" y={29 + t * 225} textAnchor="end">
                {Math.round(t * deep)}
              </text>
              <text x={45 + t * 200} y="15" textAnchor="middle">
                {fmt(min + t * (max - min), 1)}
              </text>
            </g>
          ))}
          <path d={path} fill="none" stroke="#71c4ff" strokeWidth="2.5" />
          {data.density_mld.depth_m != null &&
            data.density_mld.depth_m <= deep && (
              <g>
                <line
                  x1="45"
                  x2="245"
                  y1={y(data.density_mld.depth_m)}
                  y2={y(data.density_mld.depth_m)}
                  stroke="#f4c582"
                  strokeDasharray="4 3"
                />
                <text
                  x="245"
                  y={y(data.density_mld.depth_m) + 14}
                  textAnchor="end"
                >
                  MLD {fmt(data.density_mld.depth_m, 1)} m
                </text>
              </g>
            )}
          <text x="145" y="273" textAnchor="middle">
            σ₀ (kg/m³) · true depth (m)
          </text>
        </svg>
      )}
      <section>
        <h3>How sensitive is the answer?</h3>
        <p className="micro">
          Changing the density criterion changes the inferred depth. These are
          method choices, not confidence bounds.
        </p>
        <div className="sensitivity-grid">
          {data.density_threshold_sensitivity.map((d) => (
            <div key={d.delta_kg_m3}>
              <small>{d.delta_kg_m3} kg/m³</small>
              <b>{result(d)}</b>
            </div>
          ))}
        </div>
        <p className="micro">
          Crossing bracket:{' '}
          {data.density_mld.bracket_m
            ?.map((z) => `${fmt(z, 1)} m`)
            .join(' – ') || data.density_mld.status.replaceAll('_', ' ')}
          . No interpolation across vertical gaps above 150 m.
        </p>
        {data.observation && (
          <p className="observed-diagnostic">
            Observed density MLD: <b>{result(data.observation.density_mld)}</b>
            <br />
            <small>
              QC 1; observed timestamp above. Scene and observation times can
              differ.
            </small>
          </p>
        )}
        {data.observation_unavailable && (
          <p className="micro">Observation: {data.observation_unavailable}</p>
        )}
        <p className="micro">
          {data.valid_levels}/{data.total_levels} model levels inside scientific
          support. Negative N² values are preserved in the export. This is a
          diagnostic, not a hazard forecast.
        </p>
      </section>
      <button
        className="secondary-button full"
        onClick={() => download('ocean3d-column-diagnostics.json', data)}
      >
        <ArrowDownToLine size={15} /> Export diagnostics & methods
      </button>
      <div className="diagnostic-sources">
        <a
          href="https://doi.org/10.1029/2004JC002378"
          target="_blank"
          rel="noreferrer"
        >
          MLD method (2004)
        </a>
        <a
          href="https://doi.org/10.1029/2006JC003953"
          target="_blank"
          rel="noreferrer"
        >
          Barrier-layer method (2007)
        </a>
        <a href="https://www.teos-10.org/" target="_blank" rel="noreferrer">
          TEOS-10
        </a>
      </div>
    </div>
  );
}
