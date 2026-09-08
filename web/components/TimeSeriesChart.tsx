'use client';
/* Inline SVG needs an accessible graphic role; it cannot be replaced by an HTML img. */
/* oxlint-disable jsx-a11y/prefer-tag-over-role */
import { timeSeriesRows } from '@/lib/profiles';
import type { Comparison } from '@/lib/ocean';

export default function TimeSeriesChart({
  data,
  unit,
}: {
  data: Comparison;
  unit: string;
}) {
  const rows = timeSeriesRows(data);
  const values = rows.flatMap((r) =>
    [r.value, r.model].filter((v): v is number => v != null),
  );
  if (!values.length)
    return (
      <p className="empty-state">
        No eligible time-series values for this variable and quality policy.
      </p>
    );
  const first = rows[0].timestamp,
    last = rows.at(-1)!.timestamp;
  const low = values.reduce((a, b) => Math.min(a, b), Infinity),
    high = values.reduce((a, b) => Math.max(a, b), -Infinity);
  const padding = Math.max((high - low) * 0.1, 0.01),
    min = low - padding,
    max = high + padding;
  const x = (t: number) => 48 + ((t - first) / Math.max(last - first, 1)) * 210,
    y = (v: number) => 240 - ((v - min) / (max - min)) * 200;
  const path = (key: 'value' | 'model') => {
    let previous = false;
    return rows
      .map((row) => {
        if (row[key] == null) {
          previous = false;
          return '';
        }
        const point = `${previous ? 'L' : 'M'}${x(row.timestamp)},${y(row[key])}`;
        previous = true;
        return point;
      })
      .join(' ');
  };
  return (
    <div aria-label="Station time series">
      <p className="micro">
        {data.profile.geometry === 'surface-current'
          ? 'Surface-current samples · nominal 0 m'
          : `Fixed depth ${data.profile.depth_range?.[0]} m`}{' '}
        · UTC
      </p>
      <svg
        className="profile-chart"
        viewBox="0 0 284 290"
        role="img"
        aria-label={`${data.variable} versus time at a fixed station; ${unit}`}
      >
        <title>
          Reported station samples in timestamp order. Missing or rejected
          samples break the line.
        </title>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line
              x1="48"
              x2="258"
              y1={40 + f * 200}
              y2={40 + f * 200}
              stroke="#243742"
            />
            <text x="42" y={44 + f * 200} textAnchor="end">
              {(max - f * (max - min)).toFixed(2)}
            </text>
          </g>
        ))}
        <path
          d={path('model')}
          fill="none"
          stroke="#edac76"
          strokeWidth="2"
          strokeDasharray="5 4"
        />
        <path
          d={path('value')}
          fill="none"
          stroke="#54d6ca"
          strokeWidth="2.5"
        />
        {(['model', 'value'] as const).flatMap((key) =>
          rows
            .filter(
              (r, i) =>
                r[key] != null &&
                (i % Math.max(1, Math.ceil(rows.length / 200)) === 0 ||
                  i === rows.length - 1),
            )
            .map((r, i) => (
              <circle
                key={`${key}-${i}`}
                cx={x(r.timestamp)}
                cy={y(r[key]!)}
                r="3"
                fill={key === 'model' ? '#0b1c26' : '#54d6ca'}
                stroke={key === 'model' ? '#edac76' : '#54d6ca'}
              >
                <title>
                  {key === 'model' ? 'Model' : 'Observed'}{' '}
                  {new Date(r.timestamp).toISOString()}: {r[key]} {unit}; QC{' '}
                  {r.qc}
                </title>
              </circle>
            )),
        )}
        <text x="48" y="264">
          {new Date(first).toISOString().slice(11, 16)}
        </text>
        <text x="258" y="264" textAnchor="end">
          {new Date(last).toISOString().slice(11, 16)}
        </text>
        <text x="150" y="285" textAnchor="middle">
          Time (UTC) · {unit}
        </text>
      </svg>
      <p className="micro">
        {new Date(first).toISOString()} → {new Date(last).toISOString()}. Lines
        connect reported samples; rejected/missing samples leave gaps.
      </p>
    </div>
  );
}
