import { ArrowUpRight, Layers3, ScanLine } from 'lucide-react';
import { apiConnected, type ModelInfo, type Settings } from '@/lib/ocean';

export default function IncoisEvidence({
  model,
  settings,
  onChange,
}: {
  model: ModelInfo;
  settings: Settings;
  onChange: (s: Partial<Settings>) => void;
}) {
  const p = model.provenance,
    support = p.support_by_time?.[settings.index],
    hasSpread = model.variables.some((v) => v.id === 'temperature_spread');
  const fraction = support
    ? support.cells_with_local_observations / support.valid_cells
    : 0;
  return (
    <div className="incois-evidence">
      <div className="incois-source-tag">INCOIS · OFFICIAL DATA</div>
      <h3>The ocean, through Argo</h3>
      <p>
        {p.source}. Published analyzed fields retain their own spatial and
        temporal coverage.
      </p>
      <dl className="incois-facts">
        <div>
          <dt>Native horizontal grid</dt>
          <dd>1° × 1°</dd>
        </div>
        <div>
          <dt>Source depth levels</dt>
          <dd>24 · 5–2,000 m</dd>
        </div>
        <div>
          <dt>Loaded dates</dt>
          <dd>
            {model.times[0].slice(0, 10)} – {model.times.at(-1)!.slice(0, 10)}
          </dd>
        </div>
      </dl>
      <div className="incois-actions">
        <button
          onClick={() =>
            onChange({
              variable: 'analyzed_temperature',
              mode: 'sections',
              min: 2,
              max: 32,
              log: false,
              depth: 100,
              depthWindow: 'upper500',
              opacity: 0.95,
              exaggeration: 500,
            })
          }
        >
          <ScanLine size={17} />
          Intersect the water column
        </button>
        {hasSpread && (
          <button
            onClick={() =>
              onChange({
                variable: 'temperature_spread',
                mode: 'volume',
                min: 0,
                max: 4,
                log: false,
                iso: 1,
                depthWindow: 'upper500',
                opacity: 0.4,
                cutaway: 28,
              })
            }
          >
            <Layers3 size={17} />
            Inspect temperature spread
          </button>
        )}
      </div>
      {support && (
        <section className="native-support">
          <h4>Where observations contribute</h4>
          <strong>
            {Math.round(fraction * 100)}
            <span>%</span>
          </strong>
          <p>
            of valid temperature grid cells have at least one observation in
            their own 1° box.
          </p>
          <div className="support-bar" aria-hidden="true">
            <i style={{ width: `${fraction * 100}%` }} />
          </div>
          <dl>
            <div>
              <dt>Valid native cells</dt>
              <dd>{support.valid_cells.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Profiles in influence region</dt>
              <dd>{support.roi_count_range.join('–')}</dd>
            </div>
          </dl>
          <p className="source-caveat">
            Counts cover the full source domain and 5–2,000 m column, including
            areas outside any selected display region. Counts are per native
            grid cell and depth, not unique floats. Cells without local
            observations can use surrounding profiles. This is a coverage
            measure, not accuracy.
          </p>
        </section>
      )}
      <section className="source-definitions">
        <h4>Read the field correctly</h4>
        <p>
          <b>Temperature:</b> kept as analyzed temperature. The source does not
          specify potential versus in-situ convention; density and
          temperature-profile comparisons are unavailable.
        </p>
        {hasSpread ? (
          <p>
            <b>Spread:</b> the source standard deviation about the analyzed mean.
            It is not independent forecast error or a confidence interval.
          </p>
        ) : (
          <p>
            <b>Relative error:</b> the source labels and units are inconsistent.
            Original fields remain available in INCOIS sources; they are not
            treated as standard deviation or a confidence interval.
          </p>
        )}
        <p>
          <b>Time:</b> {p.temporal_resolution}. Playback switches published
          analyses; it does not simulate ocean evolution.
        </p>
      </section>
      <a href={p.metadata_url} target="_blank" rel="noreferrer">
        INCOIS product metadata <ArrowUpRight size={15} />
      </a>
      <a href={p.source_url} target="_blank" rel="noreferrer">
        Original INCOIS NetCDF subset <ArrowUpRight size={15} />
      </a>
      {apiConnected() && (
        <a
          href={`/api/export/subset.nc?model=${encodeURIComponent(model.id)}&variable=${settings.variable}&index=${settings.index}${settings.depthWindow === 'upper500' ? '&maximum_depth=500' : ''}${settings.region ? '&bbox=' + settings.region.join(',') : ''}`}
        >
          Export selected native field <ArrowUpRight size={15} />
        </a>
      )}
      {p.documentation_url && (
        <a href={p.documentation_url} target="_blank" rel="noreferrer">
          Objective-analysis methodology <ArrowUpRight size={15} />
        </a>
      )}
      <p className="source-caveat">
        Downloaded {p.retrieved_at?.slice(0, 10)}. A reproducible snapshot; no
        live synchronization.
      </p>
    </div>
  );
}
