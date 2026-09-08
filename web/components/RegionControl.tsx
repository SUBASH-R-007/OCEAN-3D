'use client';
import { useState } from 'react';
import { validRegion } from '@/lib/region';
import { regions, intersectRegion } from '@/lib/geography';
import './services.css';

export default function RegionControl({
  bounds,
  region,
  connected,
  onChange,
}: {
  bounds: number[];
  region: number[] | null;
  connected: boolean;
  onChange: (region: number[] | null) => void;
}) {
  const [draft, setDraft] = useState((region || bounds).map(String)),
    [error, setError] = useState('');
  return (
    <section className="region-control">
      <span className="eyebrow">GEOGRAPHIC REGION</span>
      {connected ? (
        <>
          <p>
            Concentrate the display grid on a smaller area. Native data and
            missing cells stay unchanged.
          </p>
          <div className="source-presets">
            {regions.map((r) => {
              const next = intersectRegion(r.bounds, bounds);
              return next ? (
                <button
                  key={r.id}
                  onClick={() => {
                    setDraft(next.map(String));
                    setError('');
                    onChange(next);
                  }}
                >
                  {r.label}
                </button>
              ) : null;
            })}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const next = draft.map((v) =>
                v.trim() === '' ? NaN : Number(v),
              );
              if (!validRegion(next, bounds)) {
                setError('Enter an ordered region inside the model bounds.');
                return;
              }
              setError('');
              onChange(next);
            }}
          >
            <div className="region-inputs">
              {['West °E', 'South °N', 'East °E', 'North °N'].map(
                (label, i) => (
                  <label key={label}>
                    {label}
                    <input
                      aria-label={label}
                      type="number"
                      step="any"
                      value={draft[i]}
                      onChange={(e) =>
                        setDraft(
                          draft.map((v, j) => (j === i ? e.target.value : v)),
                        )
                      }
                    />
                  </label>
                ),
              )}
            </div>
            {error && <p role="alert">{error}</p>}
            <div className="region-actions">
              <button type="submit">Apply region</button>
              <button
                type="button"
                disabled={!region}
                onClick={() => {
                  setDraft(bounds.map(String));
                  setError('');
                  onChange(null);
                }}
              >
                Full domain
              </button>
            </div>
          </form>
          {region && (
            <p className="region-active">
              Active: {region[0]}–{region[2]}°E · {region[1]}–{region[3]}°N
            </p>
          )}
        </>
      ) : (
        <p>
          Connect the scientific API to request a geographic subset. This
          snapshot contains the full regional display.
        </p>
      )}
    </section>
  );
}
