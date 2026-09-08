'use client';
/* oxlint-disable jsx-a11y/prefer-tag-over-role -- The legend is a composite HTML graphic with readable numeric ticks. */
import { useMemo, useState } from 'react';
import { Switch } from '@/components/ui/switch';
import type { Volume } from '@/lib/ocean';
import {
  colorRangeError,
  formatScaleValue,
  paletteStops,
  scaleTicks,
  type ColorScale,
} from '@/lib/colorScale';

export function ColorLegend({
  scale,
  unit,
}: {
  scale: ColorScale;
  unit: string;
}) {
  return (
    <div
      className="scene-scale"
      role="img"
      aria-label={`Color legend: ${scale.min} to ${scale.max} ${unit}, ${scale.log ? 'logarithmic' : 'linear'}`}
    >
      <div className="scale-heading">
        <span>{unit}</span>
        <small>{scale.log ? 'LOGARITHMIC' : 'LINEAR'}</small>
      </div>
      <div
        className="scale-bar"
        style={{
          background: `linear-gradient(90deg,${paletteStops(scale.palette).join(',')})`,
        }}
      />
      <div className="scale-ticks">
        {scaleTicks(scale).map((tick) => (
          <span
            key={tick.position}
            title={String(tick.value)}
            style={{ left: `${tick.position * 100}%` }}
          >
            {formatScaleValue(tick.value)}
          </span>
        ))}
      </div>
    </div>
  );
}

// Parent keys this editor by the applied range, variable and mode. Drafts never reach the renderer.
export default function ColorScaleEditor({
  scale,
  unit,
  defaults,
  field,
  onChange,
}: {
  scale: ColorScale;
  unit: string;
  defaults: number[];
  field: Volume | null;
  onChange: (patch: { min: number; max: number; log: boolean }) => void;
}) {
  const [minimum, setMinimum] = useState(String(scale.min));
  const [maximum, setMaximum] = useState(String(scale.max));
  const [message, setMessage] = useState('');
  const invalid = colorRangeError(minimum, maximum, scale.log);
  const dirty = minimum !== String(scale.min) || maximum !== String(scale.max);
  const extent = useMemo(() => {
    let min = Infinity,
      max = -Infinity,
      excluded = 0;
    for (const value of field?.values ?? []) {
      if (value == null || !Number.isFinite(value)) continue;
      if (scale.log && value <= 0) {
        excluded++;
        continue;
      }
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
    return { min, max, excluded };
  }, [field, scale.log]);
  function apply(log = scale.log) {
    const error = colorRangeError(minimum, maximum, log);
    if (error) {
      setMessage(error);
      return;
    }
    onChange({ min: Number(minimum), max: Number(maximum), log });
  }
  function fit() {
    if (!Number.isFinite(extent.min)) return;
    let { min, max } = extent;
    if (min === max) {
      const padding = scale.log
        ? min * 0.05
        : Math.max(Math.abs(min) * 0.05, 0.01);
      min -= padding;
      max += padding;
    }
    onChange({ min, max, log: scale.log });
  }
  return (
    <>
      <div
        className="color-ramp"
        style={{
          background: `linear-gradient(90deg,${paletteStops(scale.palette).join(',')})`,
        }}
      />
      <form
        onSubmit={(event) => {
          event.preventDefault();
          apply();
        }}
      >
        <div className="color-inputs">
          <label>
            Min ({unit})
            <input
              type="number"
              step="any"
              aria-label="Color minimum"
              aria-invalid={Boolean(invalid)}
              aria-describedby="color-range-feedback"
              value={minimum}
              onChange={(e) => {
                setMinimum(e.target.value);
                setMessage('');
              }}
            />
          </label>
          <label>
            Max ({unit})
            <input
              type="number"
              step="any"
              aria-label="Color maximum"
              aria-invalid={Boolean(invalid)}
              aria-describedby="color-range-feedback"
              value={maximum}
              onChange={(e) => {
                setMaximum(e.target.value);
                setMessage('');
              }}
            />
          </label>
        </div>
        <div className="color-actions">
          <button type="submit" disabled={Boolean(invalid) || !dirty}>
            Apply range
          </button>
          <button
            type="button"
            disabled={!Number.isFinite(extent.min)}
            onClick={fit}
          >
            Fit current frame
          </button>
          <button
            type="button"
            onClick={() =>
              onChange({ min: defaults[0], max: defaults[1], log: false })
            }
          >
            Reset variable range
          </button>
        </div>
        <p
          id="color-range-feedback"
          className={invalid || message ? 'scale-error' : 'micro'}
          role="status"
        >
          {invalid ||
            message ||
            (dirty
              ? 'Range changes are pending. Apply them together.'
              : 'Range stays fixed during time animation.')}
        </p>
      </form>
      <div className="toggle-row">
        <span>Logarithmic scale</span>
        <Switch
          aria-label="Logarithmic scale"
          checked={scale.log}
          onCheckedChange={(log) => apply(log)}
        />
      </div>
      <p className="micro">
        Values outside the range use the end colors. Missing values stay empty.
        {scale.log
          ? ` Nonpositive values are hidden (${extent.excluded.toLocaleString()} in this frame).`
          : ''}
      </p>
      {Number.isFinite(extent.min) && (
        <p className="micro">
          {scale.log ? 'Positive frame range' : 'Current frame range'}:{' '}
          {formatScaleValue(extent.min)}–{formatScaleValue(extent.max)} {unit}
        </p>
      )}
    </>
  );
}
