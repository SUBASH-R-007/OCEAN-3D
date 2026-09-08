'use client';
import './advanced.css';
/* Effects synchronize asynchronous scientific queries; dependencies intentionally track query fields, not display controls. */
/* oxlint-disable react/react-compiler, react-hooks/exhaustive-deps, jsx-a11y/prefer-tag-over-role, nextjs/no-html-link-for-pages */
import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Database,
  Globe2,
  Layers3,
  MapPin,
  Pause,
  Play,
  Radio,
  Save,
  Share2,
  ShieldCheck,
  SlidersHorizontal,
  Waves,
} from 'lucide-react';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  initial,
  connect,
  loadVolume,
  loadComparison,
  loadCoverage,
  apiConnected,
  apiWritable,
  reloadCatalog,
  type ImportResult,
  download,
  fmt,
  color,
  validatedState,
  type Settings,
  type Catalog,
  type Volume,
  type Comparison,
  type Coverage,
  type Variable,
} from '@/lib/ocean';
import DiagnosticsPanel from '@/components/DiagnosticsPanel';
import ResearchReport from '@/components/ResearchReport';
import EvaluationPanel from '@/components/EvaluationPanel';
import IncoisEvidence from '@/components/IncoisEvidence';
import CurrentEvidence from '@/components/CurrentEvidence';
import LearningGuide, { lessons } from '@/components/LearningGuide';
import ServicePanel from '@/components/ServicePanel';
import IngestionPanel from '@/components/IngestionPanel';
import ExtensionPanel, { ProductDetails } from '@/components/ExtensionPanel';
import TimeSeriesChart from '@/components/TimeSeriesChart';
import ColorScaleEditor, { ColorLegend } from '@/components/ColorScaleEditor';
import { displayScalar } from '@/lib/colorScale';
import RegionControl from '@/components/RegionControl';
import { validRegion } from '@/lib/region';
import { latitudeLabel, longitudeLabel } from '@/lib/geography';
import { timelineIndices } from '@/lib/timeline';
import type { Diagnostics } from '@/lib/diagnostics';
import { seedFlow, sameGrid } from '@/lib/flow';
import { currentDepths, currentGlyphs, vectorScaleKm } from '@/lib/currents';
import { useEvidenceTool } from '@/lib/evidence-tool';
import { profileChartRows, profileCsv } from '@/lib/profiles';
const OceanScene = lazy(() => import('@/components/OceanRenderer'));
const ThermalAtlas = lazy(() => import('@/components/ThermalAtlas'));
const SourceLibrary = lazy(() => import('@/components/SourceLibrary'));
function Pick({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (s: string) => void;
}) {
  return (
    <Select value={value} onValueChange={(v) => v && onChange(String(v))}>
      <SelectTrigger className="pick" aria-label={label}>
        <SelectValue>
          {options.find((o) => o.value === value)?.label || value}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
function Range({
  label,
  value,
  min,
  max,
  step = 1,
  unit = '',
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  onChange: (n: number) => void;
}) {
  return (
    <div className="range-control">
      <div className="label-row">
        <span>{label}</span>
        <output>
          {value.toFixed(step < 1 ? 2 : 0)}
          {unit}
        </output>
      </div>
      <Slider
        aria-label={label}
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={(v) => onChange(Array.isArray(v) ? v[0] : v)}
      />
      <div className="range-limits">
        <span>
          {min}
          {unit}
        </span>
        <span>
          {max}
          {unit}
        </span>
      </div>
    </div>
  );
}
function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="toggle-row">
      <span>{label}</span>
      <Switch aria-label={label} checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
function ProfileChart({ data, unit }: { data: Comparison; unit: string }) {
  const vals = data.pairs.flatMap((p) => [
    p.value,
    ...(p.model == null ? [] : [p.model]),
  ]);
  if (!vals.length)
    return (
      <div className="empty-state">
        This profile has no eligible measurements for the selected variable.
      </div>
    );
  const min = Math.min(...vals) - 0.2,
    max = Math.max(...vals) + 0.2,
    deep = Math.max(1, ...data.pairs.map((p) => p.depth));
  const x = (v: number) => 44 + ((v - min) / (max - min)) * 206,
    y = (z: number) => 32 + (z / deep) * 246;
  const chartRows = profileChartRows(data);
  const pointStride = Math.max(1, Math.ceil(data.pairs.length / 200));
  function path(key: 'value' | 'model') {
    let d = '',
      previous = false;
    for (const p of chartRows) {
      const value = p[key];
      if (value == null) {
        previous = false;
        continue;
      }
      d += `${previous ? 'L' : 'M'}${x(value)},${y(p.depth)} `;
      previous = true;
    }
    return d;
  }
  return (
    <svg
      className="profile-chart"
      viewBox="0 0 276 320"
      role="img"
      aria-label={`${data.metrics.count ? 'Observed and modeled' : 'Observed'} ${data.variable} profiles versus depth in metres`}
    >
      <title>
        Native instrument profile; model values appear only where a supported
        match exists
      </title>
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line
            x1="44"
            x2="250"
            y1={32 + t * 246}
            y2={32 + t * 246}
            stroke="#243742"
            strokeDasharray="3 4"
          />
          <text x="35" y={36 + t * 246} textAnchor="end">
            {Math.round(deep * t)}
          </text>
        </g>
      ))}
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <text x={44 + t * 206} y="19" textAnchor="middle">
            {fmt(min + (max - min) * t, 1)}
          </text>
          <line
            x1={44 + t * 206}
            x2={44 + t * 206}
            y1="30"
            y2="280"
            stroke="#20313b"
          />
        </g>
      ))}
      <path
        d={path('model')}
        fill="none"
        stroke="#edac76"
        strokeWidth="2"
        strokeDasharray="5 4"
      />
      <path d={path('value')} fill="none" stroke="#54d6ca" strokeWidth="2.5" />
      {data.pairs
        .filter((_, i) => i % pointStride === 0 || i === data.pairs.length - 1)
        .map((p, i) => (
          <circle
            key={i}
            cx={x(p.value)}
            cy={y(p.depth)}
            r="2.7"
            fill="#54d6ca"
          >
            <title>
              {p.depth} m: {p.value.toFixed(3)} {unit}; QC {p.qc}
            </title>
          </circle>
        ))}
      <text x="147" y="310" textAnchor="middle">
        {unit} · depth increases downward
      </text>
      <text transform="translate(12 185) rotate(-90)" textAnchor="middle">
        Depth (m)
      </text>
    </svg>
  );
}
export default function Home() {
  const [s, set] = useState<Settings>(initial),
    [catalog, setCatalog] = useState<Catalog | null>(null),
    [field, setField] = useState<Volume | null>(null),
    [comparisonResult, setComparison] = useState<Comparison | null>(null),
    [coverage, setCoverage] = useState<Coverage | null>(null),
    [vectors, setVectors] = useState<Volume[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [lesson, setLesson] = useState(0);
  const [tab, setTab] = useState('atlas'),
    [analysisTab, setAnalysisTab] = useState('source'),
    [playing, setPlaying] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [initialized, setInitialized] = useState(false),
    [controlsOpen, setControlsOpen] = useState(false),
    [sectionLat, setSectionLat] = useState(14);
  const selectedProfile = catalog?.profiles.find((p) => p.id === s.profile);
  const observationIsSeries =
    selectedProfile?.geometry === 'time-series' ||
    selectedProfile?.geometry === 'surface-current';
  const observationVariable = selectedProfile?.variables?.includes(
    s.observationVariable,
  )
    ? s.observationVariable
    : selectedProfile?.variables?.includes(s.variable)
      ? s.variable
      : selectedProfile?.variables?.includes('temperature')
        ? 'temperature'
        : selectedProfile?.variables?.[0] || 'temperature';
  const observationDefinition = (
    catalog?.variables || catalog?.models.flatMap((m) => m.variables)
  )?.find((v) => v.id === observationVariable);
  const observationUnit = observationDefinition?.unit || '';
  const comparison =
    comparisonResult?.profile.id === s.profile &&
    comparisonResult?.variable === observationVariable &&
    comparisonResult?.model_id === s.model &&
    JSON.stringify(comparisonResult.method.qc_flags) ===
      JSON.stringify(s.qc === 'strict' ? [1] : [1, 2])
      ? comparisonResult
      : null;
  const [profileError, setProfileError] = useState('');
  const change = (patch: Partial<Settings>) =>
    set((current) => ({
      ...current,
      ...(patch.model ? { region: null } : {}),
      ...patch,
    }));
  useEffect(() => {
    let alive = true;
    connect()
      .then((c) => {
        if (!alive) return;
        let state = initial;
        try {
          if (location.hash.startsWith('#view=')) {
            setTab('explorer');
            state = validatedState(
              JSON.parse(decodeURIComponent(location.hash.slice(6))),
              c.models.flatMap((m) => m.variables.map((v) => v.id)),
            );
          } else if (localStorage.getItem('ocean3d-view'))
            state = validatedState(
              JSON.parse(localStorage.getItem('ocean3d-view')!),
              c.models.flatMap((m) => m.variables.map((v) => v.id)),
            );
        } catch {}
        const model = c.models.find((m) => m.id === state.model) || c.models[0];
        state = {
          ...state,
          model: model.id,
          index: Math.min(state.index, model.times.length - 1),
          depth: Math.max(
            model.depths[0],
            Math.min(state.depth, model.depths.at(-1)!),
          ),
        };
        if (model.depths[0] >= 500) state.depthWindow = 'full';
        if (!apiConnected() || !validRegion(state.region, model.bounds))
          state.region = null;
        if (state.depthWindow === 'upper500')
          state.depth = Math.min(state.depth, 500);
        if (!model.variables.some((v) => v.id === state.variable))
          state.variable = model.variables[0].id;
        if (model.provenance.provider === 'INCOIS') state.profile = '';
        else if (!c.profiles.some((p) => p.id === state.profile))
          state.profile = c.profiles[0]?.id || '';
        setCatalog(c);
        set(state);
        setInitialized(true);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    if (!initialized) return;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    loadVolume(s, s.variable, controller.signal)
      .then((f) => {
        if (controller.signal.aborted) return;
        setField(f);
        setLoading(false);
      })
      .catch((e) => {
        if (e.name !== 'AbortError') {
          setError(e.message);
          setLoading(false);
          setField(null);
        }
      });
    return () => controller.abort();
  }, [
    initialized,
    s.model,
    s.variable,
    s.index,
    s.depthWindow,
    s.region,
    s.quality,
  ]);
  useEffect(() => {
    if (!initialized) return;
    if (!s.profile) {
      setComparison(null);
      setProfileError('');
      return;
    }
    const controller = new AbortController();
    setComparison(null);
    setProfileError('');
    loadComparison({ ...s, variable: observationVariable }, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted)
          setComparison({ ...value, model_id: s.model });
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setProfileError(e.message);
      });
    return () => controller.abort();
  }, [initialized, s.profile, s.model, observationVariable, s.qc]);
  useEffect(() => {
    if (!initialized) return;
    const controller = new AbortController();
    setCoverage(null);
    loadCoverage(s, controller.signal)
      .then(setCoverage)
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      });
    return () => controller.abort();
  }, [initialized, s.model, s.variable, s.index, s.qc]);
  useEffect(() => {
    setVectors([]);
    if (!initialized || (!s.currents && !s.flow)) return;
    const controller = new AbortController();
    Promise.all([
      loadVolume(s, 'u', controller.signal),
      loadVolume(s, 'v', controller.signal),
    ])
      .then(setVectors)
      .catch((e) => {
        if (e.name !== 'AbortError')
          setError('Current components unavailable: ' + e.message);
      });
    return () => controller.abort();
  }, [
    initialized,
    s.currents,
    s.flow,
    s.model,
    s.index,
    s.depthWindow,
    s.region,
    s.quality,
  ]);
  useEffect(() => {
    if (!playing || loading || !catalog || !field) return;
    const frameTime = catalog.models.find((m) => m.id === s.model)?.times[
      s.index
    ];
    if (
      field.model_id !== s.model ||
      field.variable !== s.variable ||
      field.time !== frameTime
    )
      return;
    if (
      (s.currents || s.flow) &&
      (vectors.length !== 2 ||
        !sameGrid(field, vectors[0]) ||
        !sameGrid(vectors[0], vectors[1]))
    )
      return;
    const timer = setTimeout(
      () =>
        change({
          index:
            (s.index + 1) %
            (catalog.models.find((m) => m.id === s.model)?.times.length || 6),
        }),
      1100,
    );
    return () => clearTimeout(timer);
  }, [
    playing,
    loading,
    s.index,
    s.model,
    s.variable,
    catalog,
    s.currents,
    s.flow,
    field,
    vectors,
  ]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(''), 4500);
    return () => clearTimeout(timer);
  }, [notice]);
  const model = catalog?.models.find((m) => m.id === s.model),
    variable = model?.variables.find((v) => v.id === s.variable),
    unit = variable?.unit || '°C',
    stamp = model?.times[s.index],
    displayMaximum = Math.min(
      model?.depths.at(-1) || 1000,
      s.depthWindow === 'upper500' ? 500 : 12000,
    ),
    fieldMatches =
      field?.model_id === s.model &&
      field.variable === s.variable &&
      field.time === stamp &&
      (!apiConnected() ||
        (field.sampling?.resolution === (s.quality === 'detail' ? 64 : 36) &&
          JSON.stringify(field.bbox) ===
            JSON.stringify(s.region || model?.bounds))) &&
      (field.maximum_depth ?? null) ===
        (s.depthWindow === 'upper500' ? 500 : null);
  const visibleProfiles = useMemo(
    () =>
      (catalog?.profiles || []).filter((p) => {
        const b = s.region || model?.bounds;
        return (
          !!b &&
          p.synthetic === model?.provenance.synthetic &&
          p.longitude >= b[0] &&
          p.longitude <= b[2] &&
          p.latitude >= b[1] &&
          p.latitude <= b[3]
        );
      }),
    [catalog, s.model, model?.provenance.synthetic, s.region],
  );
  const profileOptions = visibleProfiles.map((p) => ({
    value: p.id,
    label: `${p.instrument} · ${p.id.split(':').at(-1)!} · ${p.time.slice(0, 10)}`,
  }));
  const metric = comparison?.metrics;
  useEvidenceTool(
    {
      settings: s,
      model: model ?? null,
      comparison: comparison
        ? {
            profile: comparison.profile,
            metrics: comparison.metrics,
            method: comparison.method,
            limitations: comparison.limitations,
          }
        : null,
      rendering: field
        ? {
            time: field.time,
            dimensions: field.dimensions,
            bbox: field.bbox,
            sampling: field.sampling,
            method: field.method,
          }
        : null,
      loading,
    },
    tab === 'explorer' || tab === 'learn',
  );
  function chooseVariable(v: Variable) {
    const info = model?.variables.find((a) => a.id === v);
    if (info)
      change({
        variable: v,
        min: info.range[0],
        max: info.range[1],
        iso: (info.range[0] + info.range[1]) / 2,
        log: false,
      });
  }
  function chooseModel(id: string) {
    const next = catalog?.models.find((m) => m.id === id);
    if (!next) return;
    setDiagnostics(null);
    const v =
      next.variables.find((v) => v.id === 'analyzed_temperature') ||
      next.variables[0];
    change({
      model: id,
      region: null,
      mode: 'volume',
      index: 0,
      variable: v.id,
      min: v.range[0],
      max: v.range[1],
      iso: (v.range[0] + v.range[1]) / 2,
      depth: Math.max(next.depths[0], Math.min(200, next.depths.at(-1)!)),
      log: false,
      currents: false,
      flow: false,
      cutaway: next.provenance.provider === 'INCOIS' ? 28 : 0,
      depthWindow:
        id === 'reference-indian' || next.provenance.provider === 'INCOIS'
          ? 'upper500'
          : 'full',
      exaggeration: Math.max(
        1,
        Math.min(
          600,
          Math.round(
            ((next.bounds[2] - next.bounds[0]) * 111 * 0.25) /
              (Math.min(
                next.depths.at(-1)!,
                id === 'reference-indian' ||
                  next.provenance.provider === 'INCOIS'
                  ? 500
                  : 12000,
              ) /
                1000),
          ),
        ),
      ),
      profile:
        next.provenance.provider === 'INCOIS'
          ? ''
          : catalog!.profiles.find(
              (p) =>
                p.longitude >= next.bounds[0] &&
                p.longitude <= next.bounds[2] &&
                p.latitude >= next.bounds[1] &&
                p.latitude <= next.bounds[3] &&
                p.synthetic === next.provenance.synthetic,
            )?.id || s.profile,
    });
    setSectionLat((next.bounds[1] + next.bounds[3]) / 2);
    setPlaying(false);
  }
  function exportEvidence() {
    if (loading || !fieldMatches || field?.time !== stamp) return;
    if (
      (s.currents || s.flow) &&
      (vectors.length !== 2 ||
        !sameGrid(field, vectors[0]) ||
        !sameGrid(vectors[0], vectors[1]))
    )
      return;
    download('ocean3d-evidence.json', {
      schema: 'ocean3d.evidence.v1',
      exported_at: new Date().toISOString(),
      settings: s,
      model,
      comparison,
      coverage,
      diagnostics: analysisTab === 'physics' ? diagnostics : null,
      flow:
        s.flow &&
        field &&
        vectors.length === 2 &&
        sameGrid(field, vectors[0]) &&
        sameGrid(vectors[0], vectors[1])
          ? {
              method:
                'RK4, frozen scene time, each path at fixed physical depth, 120 h maximum, 3600 s maximum step with quarter-cell displacement cap; vertical velocity unavailable; no diffusion',
              paths: seedFlow(
                vectors[0],
                vectors[1],
                s.depth,
                currentDepths(field, s.currentScope, s.depth, 6),
              ),
            }
          : null,
      currents:
        s.currents &&
        field &&
        vectors.length === 2 &&
        sameGrid(field, vectors[0]) &&
        sameGrid(vectors[0], vectors[1])
          ? {
              ...currentGlyphs(
                vectors[0],
                vectors[1],
                s.currentScope,
                s.depth,
                s.currentLayers,
              ),
              components: ['eastward', 'northward'],
              vertical_velocity: 'not supplied',
              units: 'm/s',
              arrow_style: s.currentStyle,
              arrow_km_per_m_s:
                s.currentStyle === 'scaled' ? vectorScaleKm(field) : null,
              color_quantity: 'horizontal_speed',
              color_range_m_s: [0, 2],
              time: field.time,
              provenance: vectors[0].provenance,
            }
          : null,
      rendering: field
        ? {
            model_id: field.model_id,
            variable: field.variable,
            time: field.time,
            maximum_depth: field.maximum_depth ?? null,
            bbox: field.bbox,
            sampling: field.sampling,
            dimensions: field.dimensions,
            method: field.method,
          }
        : null,
    });
    setNotice('Evidence exported with settings, provenance and exclusions.');
  }
  function exportCsv() {
    if (!comparison) return;
    download(
      'ocean3d-profile.csv',
      profileCsv(comparison, observationUnit),
      'text/csv',
    );
  }
  async function importFile(result: ImportResult) {
    setError('');
    try {
      const c = await reloadCatalog();
      setCatalog(c);
      if (
        result.report?.category === 'model' ||
        c.models.some((m) => m.id === result.id)
      ) {
        const m = c.models.find((m) => m.id === result.id)!;
        const v = m.variables[0];
        change({
          model: m.id,
          index: 0,
          variable: v.id,
          min: v.range[0],
          max: v.range[1],
          depth: m.depths[0],
          iso: (v.range[0] + v.range[1]) / 2,
          log: false,
          currents: false,
          flow: false,
          cutaway: 0,
          depthWindow: 'full',
          exaggeration: Math.max(
            1,
            Math.min(
              600,
              Math.round(
                ((m.bounds[2] - m.bounds[0]) * 111 * 0.25) /
                  (m.depths.at(-1)! / 1000),
              ),
            ),
          ),
        });
      } else {
        const imported = c.profiles.find((p) =>
          p.id.startsWith(result.id + ':'),
        );
        if (!imported) throw new Error('The adapter returned no profiles.');
        const compatible = c.models.find(
          (m) =>
            m.provenance.synthetic === imported.synthetic &&
            imported.longitude >= m.bounds[0] &&
            imported.longitude <= m.bounds[2] &&
            imported.latitude >= m.bounds[1] &&
            imported.latitude <= m.bounds[3] &&
            m.variables.some((v) => imported.variables?.includes(v.id)),
        );
        const variable = compatible?.variables.find((v) =>
          imported.variables?.includes(v.id),
        );
        if (compatible && variable) {
          const time = Date.parse(imported.time);
          const index = compatible.times.reduce(
            (best, t, i) =>
              Math.abs(Date.parse(t) - time) <
              Math.abs(Date.parse(compatible.times[best]) - time)
                ? i
                : best,
            0,
          );
          change({
            model: compatible.id,
            index,
            variable: variable.id,
            min: variable.range[0],
            max: variable.range[1],
            profile: imported.id,
            instruments: true,
            flow: false,
            currents: false,
            log: false,
          });
        } else change({ profile: imported.id, instruments: true });
      }
      setTab('explorer');
      setAnalysisTab(
        c.models.some((m) => m.id === result.id) ? 'source' : 'profile',
      );
      setNotice(
        result.duplicate
          ? 'This exact file was already imported; its existing dataset is open.'
          : 'File validated and imported with SHA-256 provenance.',
      );
    } catch (e) {
      setError((e as Error).message);
      throw e;
    }
  }
  function startLesson(step: number) {
    setLesson(step);
    setPlaying(false);
    setAnalysisTab('profile');
    set({
      ...initial,
      model: 'demo-bob',
      index: 2,
      profile: 'DEMO-ARGO-01',
      depthWindow: 'full',
      depth: 100,
      currents: false,
      flow: false,
      instruments: true,
      cutaway: 0,
      ...lessons[step].settings,
    });
    setTab('learn');
  }
  function inspectProfile(p: import('@/lib/ocean').Profile) {
    const target = catalog?.models.find(
      (m) =>
        m.provenance.synthetic === p.synthetic &&
        p.longitude >= m.bounds[0] &&
        p.longitude <= m.bounds[2] &&
        p.latitude >= m.bounds[1] &&
        p.latitude <= m.bounds[3] &&
        m.variables.some((v) => !p.variables || p.variables.includes(v.id)),
    );
    if (!target) {
      setError(
        'No loaded model covers this profile. Import a matching model to compare it.',
      );
      return;
    }
    chooseModel(target.id);
    const variable =
      target.variables.find(
        (v) =>
          v.id === s.variable && (!p.variables || p.variables.includes(v.id)),
      ) ||
      target.variables.find((v) => !p.variables || p.variables.includes(v.id))!;
    const time = Date.parse(p.time);
    const index = target.times.reduce(
      (best, t, i) =>
        Math.abs(Date.parse(t) - time) <
        Math.abs(Date.parse(target.times[best]) - time)
          ? i
          : best,
      0,
    );
    change({
      profile: p.id,
      variable: variable.id,
      min: variable.range[0],
      max: variable.range[1],
      log: false,
      index,
      instruments: true,
    });
    setTab('explorer');
    setAnalysisTab('profile');
  }
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Ocean3D home">
          <span className="brand-icon">
            <Waves />
          </span>
          <span>
            OCEAN<span className="brand-accent">3D</span>
            <small>OCEAN EVIDENCE WORKBENCH</small>
          </span>
        </a>
        <Tabs
          value={tab}
          onValueChange={(v) =>
            v === 'learn' ? startLesson(lesson) : setTab(String(v))
          }
        >
          <TabsList variant="line" className="main-tabs">
            <TabsTrigger value="atlas">
              <Waves />
              Ocean lab
            </TabsTrigger>
            <TabsTrigger value="explorer">
              <Layers3 />
              Explorer
            </TabsTrigger>
            <TabsTrigger value="data">
              <Database />
              Data catalog
            </TabsTrigger>
            <TabsTrigger value="sources">
              <Globe2 />
              INCOIS sources
            </TabsTrigger>
            <TabsTrigger value="learn">
              <BookOpen />
              Learn
            </TabsTrigger>
            <TabsTrigger value="research">
              <BookOpen />
              Research & methods
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="top-actions">
          <span className="sih-tag">
            SIH <b>26067</b>
          </span>
          {tab === 'explorer' && (
            <>
              <button
                className="icon-button"
                aria-label="Save view"
                title="Save view in this browser"
                onClick={() => {
                  try {
                    localStorage.setItem('ocean3d-view', JSON.stringify(s));
                    setNotice('View saved in this browser.');
                  } catch {
                    setError(
                      'Browser storage unavailable. Use Export evidence.',
                    );
                  }
                }}
              >
                <Save size={17} />
              </button>
              <button
                className="primary-button"
                onClick={exportEvidence}
                disabled={
                  loading ||
                  !fieldMatches ||
                  field?.time !== stamp ||
                  ((s.currents || s.flow) &&
                    (!field ||
                      vectors.length !== 2 ||
                      !sameGrid(field, vectors[0]) ||
                      !sameGrid(vectors[0], vectors[1])))
                }
              >
                <ArrowDownToLine size={16} /> Export evidence
              </button>
            </>
          )}
        </div>
      </header>
      <EvaluationPanel
        visible={tab === 'research'}
        evidence={{
          settings: s,
          model: catalog?.models.find((m) => m.id === s.model)?.provenance,
        }}
        onOpen={(settings) => {
          if (!catalog?.models.some((m) => m.id === settings.model))
            throw Error(
              'The fixed evaluation dataset is unavailable in this deployment.',
            );
          setPlaying(false);
          setDiagnostics(null);
          change({
            ...initial,
            ...settings,
            observationVariable: settings.variable || 'temperature',
          });
          setAnalysisTab(settings.profile ? 'profile' : 'source');
          setTab('explorer');
        }}
      />
      {error && (
        <div className="error-banner" role="alert">
          {error}
          {!initialized && (
            <button onClick={() => location.reload()}>Retry connection</button>
          )}
          <button onClick={() => setError('')} aria-label="Dismiss error">
            ×
          </button>
        </div>
      )}
      {notice && (
        <output className="toast">
          <Check size={16} />
          {notice}
        </output>
      )}
      {tab === 'atlas' && (
        <Suspense
          fallback={<div className="loading-state">Opening Ocean lab…</div>}
        >
          <ThermalAtlas />
        </Suspense>
      )}
      {tab === 'sources' && (
        <Suspense
          fallback={
            <div className="loading-state">Opening INCOIS sources…</div>
          }
        >
          <SourceLibrary
            onOpen={async (id, time) => {
              const c = await reloadCatalog();
              setCatalog(c);
              const m = c.models.find((v) => v.id === id);
              if (!m)
                throw Error(
                  'This full-column snapshot is not registered with the running API. Restart it to load the new catalogue.',
                );
              const v =
                m.variables.find((v) => v.id === 'analyzed_temperature') ||
                m.variables[0];
              setDiagnostics(null);
              setPlaying(false);
              setProfileError('');
              setAnalysisTab('source');
              change({
                model: id,
                variable: v.id,
                index: Math.max(0, m.times.indexOf(time)),
                region: null,
                mode: 'volume',
                profile: '',
                min: v.range[0],
                max: v.range[1],
                iso: 20,
                log: false,
                currents: false,
                flow: false,
                depthWindow: 'full',
                depth: 200,
                exaggeration: 600,
                cutaway: 28,
              });
              setTab('explorer');
            }}
          />
        </Suspense>
      )}
      {(tab === 'explorer' || tab === 'learn') && (
        <>
          {tab === 'learn' && (
            <LearningGuide
              step={lesson}
              onStep={startLesson}
              onExit={() => setTab('explorer')}
            />
          )}
          <div className="contextbar">
            <div>
              <span className="eyebrow">WORKSPACE</span>
              <ChevronRight size={14} />
              <strong>{model?.title || 'Bay of Bengal'}</strong>
              <span className="region-tag">
                {model?.bounds
                  .map((v, i) => (i % 2 ? latitudeLabel(v) : longitudeLabel(v)))
                  .join(' / ')}
              </span>
            </div>
            <span className="status-pill">
              <i />
              {apiConnected()
                ? apiWritable()
                  ? 'Scientific API connected'
                  : 'Read-only archive service'
                : 'Bundled data snapshot'}
            </span>
          </div>
          <main className="workspace">
            <aside
              className={`controls ${controlsOpen ? 'is-open' : ''}`}
              id="ocean-controls"
            >
              <div className="panel-heading">
                <SlidersHorizontal size={16} />
                <h2>Explore the water column</h2>
                <button
                  className="mobile-controls-toggle"
                  aria-expanded={controlsOpen}
                  aria-controls="ocean-controls"
                  onClick={() => setControlsOpen(!controlsOpen)}
                >
                  {controlsOpen ? 'Hide controls' : 'Show controls'}
                </button>
              </div>
              <section>
                <span className="eyebrow">MODEL DATASET</span>
                <Pick
                  label="Model dataset"
                  value={s.model}
                  onChange={chooseModel}
                  options={
                    catalog?.models.map((m) => ({
                      value: m.id,
                      label: m.title,
                    })) || [
                      {
                        value: 'demo-bob',
                        label: 'Bay of Bengal demonstration',
                      },
                    ]
                  }
                />
                <div className="source-line">
                  <span className="source-dot" />
                  {model?.provenance.synthetic
                    ? 'Synthetic · reproducible fixture'
                    : model?.provenance.provider === 'INCOIS'
                      ? 'INCOIS · official analyzed fields'
                      : 'Real data · source metadata retained'}
                </div>
              </section>
              <section>
                <span className="eyebrow">OCEAN VARIABLE</span>
                <div className="variable-list">
                  {model?.variables.map((v) => (
                    <button
                      key={v.id}
                      className={s.variable === v.id ? 'active' : ''}
                      onClick={() => chooseVariable(v.id)}
                    >
                      <span className={`variable-dot ${v.id}`} />
                      {v.label}
                      <small>{v.unit}</small>
                      {s.variable === v.id && <Check size={14} />}
                    </button>
                  ))}
                </div>
              </section>
              {model && (
                <RegionControl
                  key={s.model}
                  bounds={model.bounds}
                  region={s.region}
                  connected={apiConnected()}
                  onChange={(region) =>
                    change({ region, profile: '', sectionX: 50, sectionY: 50 })
                  }
                />
              )}
              <section>
                <span className="eyebrow">RENDER MODE</span>
                <Tabs
                  value={s.mode}
                  onValueChange={(v) => change({ mode: v as Settings['mode'] })}
                >
                  <TabsList className="segmented">
                    <TabsTrigger value="volume">Volume</TabsTrigger>
                    <TabsTrigger value="slice">Slice</TabsTrigger>
                    <TabsTrigger value="isosurface">Isosurface</TabsTrigger>
                    <TabsTrigger value="sections">Sections</TabsTrigger>
                  </TabsList>
                </Tabs>
                <Pick
                  label="Display depth window"
                  value={s.depthWindow}
                  options={[
                    { value: 'full', label: 'Full water column' },
                    ...(model && model.depths[0] < 500
                      ? [{ value: 'upper500', label: 'Upper ocean · 0–500 m' }]
                      : []),
                  ]}
                  onChange={(value) => {
                    const depthWindow = value as Settings['depthWindow'];
                    change({
                      depthWindow,
                      depth: Math.max(
                        model?.depths[0] || 0,
                        Math.min(
                          s.depth,
                          value === 'upper500'
                            ? 500
                            : model?.depths.at(-1) || 1000,
                        ),
                      ),
                    });
                  }}
                />
                <Range
                  label={
                    s.mode === 'volume'
                      ? model?.provenance.provider === 'INCOIS'
                        ? 'Section depth'
                        : 'Current vector depth'
                      : 'Depth slice'
                  }
                  value={s.depth}
                  min={model?.depths[0] || 0}
                  max={displayMaximum}
                  unit=" m"
                  onChange={(depth) => change({ depth })}
                />
                {s.mode === 'sections' && (
                  <>
                    <Range
                      label="North–south plane"
                      value={s.sectionX}
                      min={0}
                      max={100}
                      unit="%"
                      onChange={(sectionX) => change({ sectionX })}
                    />
                    <Range
                      label="East–west plane"
                      value={s.sectionY}
                      min={0}
                      max={100}
                      unit="%"
                      onChange={(sectionY) => change({ sectionY })}
                    />
                    <p className="micro">
                      Move two vertical planes through the volume. Geographic
                      positions appear in the scene; missing cells remain open.
                    </p>
                  </>
                )}
                {s.mode === 'isosurface' && (
                  <Range
                    label={`Isovalue (${unit})`}
                    value={s.iso}
                    min={
                      Math.floor(
                        Math.min(field?.range?.[0] ?? s.min, s.iso) * 100,
                      ) / 100
                    }
                    max={
                      Math.ceil(
                        Math.max(
                          field?.range?.[1] ?? s.max,
                          s.iso,
                          (field?.range?.[0] ?? s.min) + 0.01,
                        ) * 100,
                      ) / 100
                    }
                    step={0.01}
                    onChange={(iso) => change({ iso })}
                  />
                )}
                <Range
                  label="Field opacity"
                  value={s.opacity * 100}
                  min={0}
                  max={100}
                  unit="%"
                  onChange={(opacity) => change({ opacity: opacity / 100 })}
                />
                <p className="micro">
                  Applies to the active field view. Volume transparency
                  accumulates through the water column; 0% hides the field.
                </p>
                {s.mode === 'volume' && (
                  <Range
                    label="Volume cutaway"
                    value={s.cutaway}
                    min={0}
                    max={75}
                    unit="%"
                    onChange={(cutaway) => change({ cutaway })}
                  />
                )}
                <Pick
                  label="Render quality"
                  value={s.quality}
                  options={[
                    { value: 'balanced', label: 'Balanced · interactive' },
                    {
                      value: 'detail',
                      label: 'Detail · fine sampling + lighting',
                    },
                  ]}
                  onChange={(quality) =>
                    change({ quality: quality as Settings['quality'] })
                  }
                />
                <Range
                  label="Vertical exaggeration"
                  value={s.exaggeration}
                  min={1}
                  max={600}
                  unit="×"
                  onChange={(exaggeration) => change({ exaggeration })}
                />
              </section>
              <section>
                <span className="eyebrow">OVERLAYS</span>
                {s.model !== 'incois-bob' && (
                  <>
                    <Toggle
                      label="Instrument profiles"
                      checked={s.instruments}
                      onChange={(instruments) => change({ instruments })}
                    />
                    {s.instruments && (
                      <Range
                        label="Instrument opacity"
                        value={s.instrumentOpacity * 100}
                        min={0}
                        max={100}
                        unit="%"
                        onChange={(opacity) =>
                          change({ instrumentOpacity: opacity / 100 })
                        }
                      />
                    )}
                  </>
                )}
                {model?.variables.some((v) => v.id === 'u') &&
                  model.variables.some((v) => v.id === 'v') && (
                    <>
                      <Toggle
                        label="Current vectors"
                        checked={s.currents}
                        onChange={(currents) => change({ currents })}
                      />
                      <Toggle
                        label="Animated streamlines"
                        checked={s.flow}
                        onChange={(flow) => change({ flow })}
                      />
                      {s.currents && (
                        <Range
                          label="Current vector opacity"
                          value={s.currentOpacity * 100}
                          min={0}
                          max={100}
                          unit="%"
                          onChange={(opacity) =>
                            change({ currentOpacity: opacity / 100 })
                          }
                        />
                      )}
                      {s.flow && (
                        <Range
                          label="Streamline opacity"
                          value={s.flowOpacity * 100}
                          min={0}
                          max={100}
                          unit="%"
                          onChange={(opacity) =>
                            change({ flowOpacity: opacity / 100 })
                          }
                        />
                      )}
                      <Pick
                        label="Current depth coverage"
                        value={s.currentScope}
                        options={[
                          { value: 'column', label: 'Throughout the column' },
                          { value: 'slice', label: 'Selected depth' },
                        ]}
                        onChange={(scope) =>
                          change({
                            currentScope: scope as Settings['currentScope'],
                          })
                        }
                      />
                      <Pick
                        label="Vector appearance"
                        value={s.currentStyle}
                        options={[
                          {
                            value: 'direction',
                            label: 'Direction arrows · speed by color',
                          },
                          {
                            value: 'scaled',
                            label: 'Length and color by speed',
                          },
                        ]}
                        onChange={(style) =>
                          change({
                            currentStyle: style as Settings['currentStyle'],
                          })
                        }
                      />
                      {s.currentScope === 'column' && (
                        <Pick
                          label="Vector depth layers"
                          value={String(s.currentLayers)}
                          options={[
                            { value: '6', label: '6 depth layers' },
                            { value: '12', label: '12 depth layers' },
                            { value: '24', label: '24 depth layers' },
                            { value: '0', label: 'Every display depth' },
                          ]}
                          onChange={(layers) =>
                            change({ currentLayers: Number(layers) })
                          }
                        />
                      )}
                      <p className="micro">
                        Arrows show eastward and northward velocity; their
                        display scale is labelled in the scene. Color shows
                        horizontal speed. Streamlines hold each depth fixed in
                        the selected model frame. Vertical velocity is
                        unavailable. Column views sample multiple depths;
                        missing cells stay empty.
                      </p>
                    </>
                  )}
                <div className="source-line">
                  {model?.provenance.provider === 'INCOIS'
                    ? 'This product contains analyzed temperature and salinity, not depth-resolved current velocities.'
                    : 'Faded markers fall outside ±24 h.'}
                </div>
              </section>
              <section className="color-section">
                <span className="eyebrow">COLOR SCALE</span>
                <Pick
                  label="Color palette"
                  value={s.palette}
                  options={[
                    { value: 'thermal', label: 'Thermal · cool to warm' },
                    { value: 'viridis', label: 'Viridis · perceptual' },
                    { value: 'ice', label: 'Ice · sequential' },
                    { value: 'balance', label: 'Balance · diverging' },
                  ]}
                  onChange={(palette) => change({ palette })}
                />
                <ColorScaleEditor
                  key={`${s.model}:${s.variable}:${s.min}:${s.max}:${s.log}`}
                  scale={s}
                  unit={unit}
                  defaults={variable?.range || [initial.min, initial.max]}
                  field={fieldMatches && !loading ? field : null}
                  onChange={change}
                />
              </section>
            </aside>
            <div className="center-column">
              <section className="visual-panel">
                <div
                  className="scene-presets"
                  aria-label="Demonstration journeys"
                >
                  <span>EXPLORE A QUESTION</span>
                  {catalog?.models.some((m) => m.id === 'incois-bob') && (
                    <button
                      className="incois-journey"
                      onClick={() => {
                        chooseModel('incois-bob');
                        change({
                          index: 2,
                          mode: 'volume',
                          opacity: 0.38,
                          quality: 'detail',
                        });
                      }}
                    >
                      INCOIS · Bay of Bengal
                    </button>
                  )}
                  <button
                    onClick={() => {
                      chooseModel('demo-bob');
                      change({
                        model: 'demo-bob',
                        index: 2,
                        variable: 'temperature',
                        mode: 'volume',
                        cutaway: 38,
                        exaggeration: 360,
                        min: 6,
                        max: 30,
                        iso: 20,
                        opacity: 0.35,
                      });
                      setAnalysisTab('physics');
                    }}
                  >
                    Water-column structure
                  </button>
                  {catalog?.models.some(
                    (m) => m.id === 'hycom-currents-indian',
                  ) && (
                    <button
                      onClick={() => {
                        chooseModel('hycom-currents-indian');
                        change({
                          model: 'hycom-currents-indian',
                          index: 2,
                          variable: 'u',
                          mode: 'volume',
                          depth: 100,
                          depthWindow: 'full',
                          currents: true,
                          flow: false,
                          currentScope: 'column',
                          currentStyle: 'direction',
                          currentLayers: 12,
                          instruments: false,
                          exaggeration: 400,
                          min: -1,
                          max: 1,
                          palette: 'balance',
                          iso: 0.2,
                          opacity: 0.1,
                          profile: '',
                        });
                      }}
                    >
                      Real current circulation
                    </button>
                  )}
                  {catalog?.models.some(
                    (m) => m.id === 'hycom-currents-indian',
                  ) && (
                    <button
                      onClick={() => {
                        chooseModel('hycom-currents-indian');
                        change({
                          instruments: true,
                          currents: false,
                          flow: false,
                          variable: 'temperature',
                          observationVariable: '',
                          min: 5,
                          max: 31,
                          palette: 'thermal',
                          opacity: 0.14,
                          depthWindow: 'full',
                        });
                        setAnalysisTab('profile');
                      }}
                    >
                      Real instrument overlays
                    </button>
                  )}
                  {catalog?.models.some((m) => m.id === 'reference-indian') && (
                    <button
                      onClick={() => {
                        chooseModel('reference-indian');
                        setAnalysisTab('profile');
                      }}
                    >
                      Real-data validation
                    </button>
                  )}
                </div>
                <div className="visual-heading">
                  <div>
                    <div className="eyebrow">
                      {s.mode === 'volume'
                        ? '3D VOLUME'
                        : s.mode === 'slice'
                          ? 'HORIZONTAL SECTION'
                          : s.mode === 'sections'
                            ? 'INTERSECTING 3D SECTIONS'
                            : 'ISOSURFACE'}
                    </div>
                    <h1>
                      {variable?.label || 'Potential temperature'}
                      <span>{unit}</span>
                    </h1>
                  </div>
                  <span className="render-chip">
                    <i />
                    WebGL 2
                  </span>
                </div>
                {model?.provenance.synthetic && (
                  <div className="demo-label">
                    DEMONSTRATION DATA{' '}
                    <span>Analytic field · not an operational forecast</span>
                  </div>
                )}
                {model && !model.provenance.synthetic && (
                  <div className="real-label">
                    {model.provenance.product
                      ? 'DERIVED PRODUCT'
                      : 'REAL DATA CASE'}{' '}
                    <span>
                      {model?.provenance.provider === 'INCOIS'
                        ? 'INCOIS Argo analysis · 1° grid · source dates and metadata retained'
                        : model.provenance.source}
                    </span>
                  </div>
                )}
                <ColorLegend scale={s} unit={unit} />
                {loading && field && fieldMatches && (
                  <div className="frame-loading" role="status">
                    Updating… showing {field.variable} at{' '}
                    {field.time.replace('T', ' ').replace('Z', ' UTC')} until
                    the new frame arrives.
                  </div>
                )}
                {field && fieldMatches ? (
                  <Suspense
                    fallback={
                      <div className="loading-state">
                        Preparing the 3D renderer…
                      </div>
                    }
                  >
                    <OceanScene
                      field={field}
                      settings={s}
                      profiles={visibleProfiles}
                      vectors={vectors}
                      onSelect={(profile) => {
                        change({ profile });
                        setAnalysisTab('profile');
                      }}
                    />
                  </Suspense>
                ) : (
                  <div className="loading-state">
                    <Waves size={32} />
                    {loading
                      ? 'Loading the ocean subset…'
                      : 'No field available. Check the dataset and connection.'}
                  </div>
                )}
                <div className="visual-footer">
                  <span>
                    <span className="legend-dot" />{' '}
                    {model?.provenance.provider === 'INCOIS'
                      ? 'INCOIS analyzed field'
                      : 'Instrument observations'}
                  </span>
                  <span>
                    {field
                      ? `${field.valid_cells.toLocaleString()} valid display samples`
                      : ''}
                  </span>
                  <span>Regional coordinates · metres</span>
                </div>
              </section>
              <section className="timeline">
                <div className="timeline-top">
                  <span className="eyebrow">TIME EXPLORER</span>
                  <strong>
                    {stamp && s.model === 'incois-bob'
                      ? new Date(stamp).toLocaleString('en-GB', {
                          month: 'long',
                          year: 'numeric',
                          timeZone: 'UTC',
                        }) + ' · monthly analysis'
                      : stamp
                        ? new Date(stamp).toLocaleString('en-GB', {
                            day: '2-digit',
                            month: 'short',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                            timeZone: 'UTC',
                          }) + ' UTC'
                        : 'Loading…'}
                  </strong>
                  <span>
                    Step {s.index + 1} / {model?.times.length || 6}
                  </span>
                </div>
                <div className="timeline-controls">
                  <button
                    className="play-button"
                    disabled={model?.times.length === 1}
                    onClick={() => setPlaying(!playing)}
                    aria-label={
                      playing ? 'Pause time animation' : 'Play time animation'
                    }
                  >
                    {playing ? <Pause size={18} /> : <Play size={18} />}
                  </button>
                  <div className="timeline-range">
                    {model?.times.length === 1 ? (
                      <p className="micro">
                        One selected source time. Choose another date in INCOIS
                        sources.
                      </p>
                    ) : (
                      <Slider
                        aria-label="Time step"
                        value={[s.index]}
                        min={0}
                        max={(model?.times.length || 6) - 1}
                        step={1}
                        onValueChange={(v) => {
                          setPlaying(false);
                          change({ index: Array.isArray(v) ? v[0] : v });
                        }}
                      />
                    )}
                    <div className="timeline-ticks">
                      {model &&
                        timelineIndices(model.times.length).map((i) => (
                          <button
                            key={model.times[i]}
                            className={i === s.index ? 'active' : ''}
                            onClick={() => change({ index: i })}
                          >
                            {new Date(model.times[i]).toLocaleString('en-GB', {
                              day: '2-digit',
                              month: 'short',
                              ...([model.times[i - 1], model.times[i + 1]].some(
                                (t) =>
                                  t?.slice(0, 10) ===
                                  model.times[i].slice(0, 10),
                              )
                                ? ({
                                    hour: '2-digit',
                                    minute: '2-digit',
                                  } as const)
                                : {}),
                              timeZone: 'UTC',
                            })}
                          </button>
                        ))}
                    </div>
                  </div>
                  <span className="timeline-speed">
                    {model?.times.length === 1
                      ? 'Single frame'
                      : '1 step / 1.1 s'}
                  </span>
                </div>
              </section>
              <section className="section-panel">
                <div className="section-heading">
                  <div>
                    <div className="eyebrow">BELOW THE SURFACE</div>
                    <h2>East–west section</h2>
                  </div>
                  <div className="section-lat">
                    <label htmlFor="section-latitude">Latitude</label>
                    <input
                      id="section-latitude"
                      type="number"
                      step="0.5"
                      min={model?.bounds[1] || 6}
                      max={model?.bounds[3] || 22}
                      value={sectionLat}
                      onChange={(e) => setSectionLat(Number(e.target.value))}
                    />
                    <span>°N</span>
                  </div>
                </div>
                {field && fieldMatches && (
                  <SectionChart
                    field={field}
                    latitude={sectionLat}
                    settings={s}
                  />
                )}
                <p className="micro">
                  Nearest displayed latitude. Gaps preserve missing cells; the
                  API also supports arbitrary endpoint transects.
                </p>
              </section>
            </div>
            <aside className="analysis-panel">
              <div className="panel-heading">
                <Activity size={17} />
                <h2>Evidence lens</h2>
                <span className="new-tag">EVIDENCE</span>
              </div>
              <>
                <Tabs
                  value={analysisTab}
                  onValueChange={(v) => setAnalysisTab(String(v))}
                >
                  <TabsList className="analysis-tabs">
                    <TabsTrigger value="profile">Instruments</TabsTrigger>
                    <TabsTrigger value="source">Source</TabsTrigger>
                    <TabsTrigger value="coverage">Coverage gaps</TabsTrigger>
                    <TabsTrigger value="physics">Physics</TabsTrigger>
                  </TabsList>
                </Tabs>
                {analysisTab === 'source' ? (
                  model?.id === 'hycom-currents-indian' ? (
                    <CurrentEvidence
                      model={model}
                      vectors={
                        fieldMatches &&
                        field &&
                        vectors.length === 2 &&
                        sameGrid(field, vectors[0])
                          ? vectors
                          : []
                      }
                      depth={s.depth}
                    />
                  ) : model?.provenance.provider === 'INCOIS' ? (
                    <IncoisEvidence
                      model={model}
                      settings={s}
                      onChange={change}
                    />
                  ) : (
                    <section className="instrument-section">
                      <h3>Model source</h3>
                      <p>{model?.provenance.source}</p>
                      <p>{model?.provenance.warning}</p>
                      <ProductDetails product={model?.provenance.product} />
                    </section>
                  )
                ) : analysisTab === 'profile' ? (
                  <>
                    <section className="instrument-section">
                      <div className="label-row">
                        <span className="eyebrow">SELECT INSTRUMENT</span>
                        <Radio size={15} />
                      </div>
                      <Pick
                        label="Select instrument"
                        value={s.profile}
                        options={profileOptions}
                        onChange={(profile) =>
                          change({ profile, instruments: true })
                        }
                      />
                      <Pick
                        label="Observation variable"
                        value={observationVariable}
                        options={(selectedProfile?.variables || []).map(
                          (id) => ({
                            value: id,
                            label:
                              catalog?.models
                                .flatMap((m) => m.variables)
                                .find((v) => v.id === id)?.label || id,
                          }),
                        )}
                        onChange={(observationVariable) =>
                          change({ observationVariable })
                        }
                      />
                      <p className="micro">
                        {visibleProfiles.length} instrument records in this
                        region. Faded markers are outside ±24 h of the model
                        frame.
                      </p>
                      {comparison && (
                        <>
                          <div className="instrument-meta">
                            <span>
                              <MapPin size={13} />
                              {latitudeLabel(comparison.profile.latitude)},{' '}
                              {longitudeLabel(comparison.profile.longitude)}
                            </span>
                            <span>{comparison.profile.instrument}</span>
                          </div>
                          <p className="micro">
                            Observation:{' '}
                            {comparison.profile.time
                              .replace('T', ' ')
                              .replace('Z', ' UTC')}
                            <br />
                            {comparison.profile.time_range && (
                              <>
                                Series / cast ends{' '}
                                {comparison.profile.time_range[1]
                                  .replace('T', ' ')
                                  .replace('Z', ' UTC')}
                                <br />
                              </>
                            )}
                            {comparison.profile.synthetic
                              ? `Synthetic observations · ${comparison.profile.data_mode}`
                              : `Data mode: ${comparison.profile.data_mode}`}
                          </p>
                          {comparison.profile.warning && (
                            <p className="profile-warning">
                              {comparison.profile.warning}
                            </p>
                          )}
                        </>
                      )}
                    </section>
                    <div className="chart-header">
                      <h3>
                        {observationDefinition?.label || observationVariable}{' '}
                        {selectedProfile?.geometry === 'time-series' ||
                        selectedProfile?.geometry === 'surface-current'
                          ? 'through time'
                          : 'through depth'}
                      </h3>
                      <span className="chart-key">
                        <i /> Observed{' '}
                        {Boolean(comparison?.metrics.count) && (
                          <>
                            <i className="modeled" /> Model
                          </>
                        )}
                      </span>
                    </div>
                    {comparison ? (
                      comparison.profile.geometry === 'time-series' ||
                      comparison.profile.geometry === 'surface-current' ? (
                        <TimeSeriesChart
                          data={comparison}
                          unit={observationUnit}
                        />
                      ) : (
                        <ProfileChart
                          data={comparison}
                          unit={observationUnit}
                        />
                      )
                    ) : (
                      <div className="empty-state">
                        {profileError ||
                          (s.profile
                            ? 'Loading instrument profile…'
                            : 'Select a marker or an instrument above to inspect its depth profile.')}
                      </div>
                    )}
                    {comparison?.comparison_reason && (
                      <p className="profile-warning" role="status">
                        {comparison.comparison_reason}
                      </p>
                    )}
                    {comparison && (
                      <div className="instrument-source">
                        <p className="micro">{comparison.profile.source}</p>
                        <p className="micro">{comparison.profile.conversion}</p>
                        <details className="micro">
                          <summary>Provenance and reuse</summary>
                          {comparison.profile.source_profile_id && (
                            <p>
                              Source profile:{' '}
                              {comparison.profile.source_profile_id}
                            </p>
                          )}
                          <p>{comparison.profile.acknowledgement}</p>
                          <p>{comparison.profile.license}</p>
                          <p>
                            Source SHA-256:{' '}
                            {comparison.profile.sha256 ||
                              'See imported source manifest'}
                          </p>
                        </details>
                        {comparison.profile.source_url && (
                          <a
                            href={comparison.profile.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Instrument source metadata ↗
                          </a>
                        )}
                        {comparison.profile.source_download_url && (
                          <a
                            href={comparison.profile.source_download_url}
                            download
                          >
                            Download instrument source ↓
                          </a>
                        )}
                      </div>
                    )}
                    <section className="evidence-metrics">
                      <div className="metric">
                        <small>RMSE</small>
                        <strong>
                          {fmt(metric?.rmse)}
                          <span>{observationUnit}</span>
                        </strong>
                      </div>
                      <div className="metric">
                        <small>Mean bias</small>
                        <strong>
                          {metric?.bias != null && metric.bias > 0 ? '+' : ''}
                          {fmt(metric?.bias)}
                          <span>{observationUnit}</span>
                        </strong>
                      </div>
                    </section>
                    <section>
                      <div className="label-row">
                        <h3>
                          <ShieldCheck size={15} /> Quality policy
                        </h3>
                        <span className="good-tag">
                          {s.qc === 'strict' ? 'QC 1' : 'QC 1 + 2'}
                        </span>
                      </div>
                      <Pick
                        label="Quality policy"
                        value={s.qc}
                        options={[
                          {
                            value: 'strict',
                            label: 'Strict · good data only (1)',
                          },
                          {
                            value: 'lenient',
                            label: 'Include probably good (1, 2)',
                          },
                        ]}
                        onChange={(qc) => change({ qc: qc as Settings['qc'] })}
                      />
                      <div className="quality-summary">
                        <div>
                          <span>
                            {observationIsSeries
                              ? 'Matched samples'
                              : 'Matched levels'}
                          </span>
                          <b>
                            {metric?.count ?? '—'} / {metric?.total ?? '—'}
                          </b>
                        </div>
                        <div>
                          <span>Excluded by QC / missing</span>
                          <b>{metric?.qc_excluded ?? '—'}</b>
                        </div>
                        <div>
                          <span>Observed without a model match</span>
                          <b>{metric?.unmatched ?? '—'}</b>
                        </div>
                      </div>
                      <p className="micro">
                        4D interpolation at the observation coordinates and
                        timestamps. Bias = model − observation. No extrapolation
                        across model bounds or gaps over 48 hours.
                      </p>
                    </section>
                    <div className="insight-note">
                      <ShieldCheck size={18} />
                      <p>
                        Agreement is evidence, not a guarantee.
                        <span>
                          Assimilated observations are not independent
                          validation. Instrument errors do not describe total
                          model uncertainty.
                        </span>
                      </p>
                    </div>
                    <button
                      className="secondary-button full"
                      onClick={exportCsv}
                      disabled={!comparison}
                    >
                      <ArrowDownToLine size={15} /> Download instrument profile
                    </button>
                    {apiConnected() && comparison && (
                      <div className="standard-exports">
                        <a
                          href={`/api/export/column.covjson?model=${encodeURIComponent(s.model)}&variable=${s.variable}&index=${s.index}&longitude=${comparison.profile.longitude}&latitude=${comparison.profile.latitude}`}
                          download
                        >
                          Model column · CoverageJSON
                        </a>
                        <a
                          href={`/api/export/subset.nc?model=${encodeURIComponent(s.model)}&variable=${s.variable}&index=${s.index}${s.depthWindow === 'upper500' ? '&maximum_depth=500' : ''}${s.region ? '&bbox=' + s.region.join(',') : ''}`}
                          download
                        >
                          Native grid · CF NetCDF
                        </a>
                      </div>
                    )}
                  </>
                ) : analysisTab === 'physics' ? (
                  <DiagnosticsPanel
                    settings={s}
                    profile={visibleProfiles.find((p) => p.id === s.profile)}
                    onData={setDiagnostics}
                  />
                ) : (
                  <CoveragePanel coverage={coverage} />
                )}
              </>
            </aside>
          </main>
          <footer className="app-footer">
            <span>
              <Waves size={14} />
              Ocean3D <span>·</span> SIH26067 / MoES–INCOIS problem statement
            </span>
            <button
              onClick={() => {
                const url = new URL(location.href);
                url.hash = 'view=' + encodeURIComponent(JSON.stringify(s));
                if (!navigator.clipboard) {
                  setError(
                    'Clipboard unavailable. Export evidence to save the view.',
                  );
                  return;
                }
                navigator.clipboard
                  .writeText(url.href)
                  .then(() =>
                    setNotice(
                      'View link copied. Imported datasets must also exist on the recipient’s server.',
                    ),
                  )
                  .catch(() =>
                    setError(
                      'Clipboard unavailable. Export evidence to save the view.',
                    ),
                  );
              }}
            >
              <Share2 size={13} /> Copy view link
            </button>
          </footer>
        </>
      )}
      {tab === 'data' && (
        <main className="content-page">
          <div className="page-heading">
            <div>
              <div className="eyebrow">DATA CATALOG</div>
              <h1>Know what you are looking at.</h1>
              <p>
                Model fields and observations keep their source, quality flags
                and scientific meaning.
              </p>
            </div>
            <Database size={42} />
          </div>
          <div className="data-grid">
            <ServicePanel models={catalog?.models || []} />
            <section className="wide-card">
              <h2>Available model datasets</h2>
              {catalog?.models.map((m) => (
                <div className="dataset-row" key={m.id}>
                  <div className="dataset-icon">
                    <Layers3 size={24} />
                  </div>
                  <div>
                    <h3>{m.title}</h3>
                    <p>{m.provenance.source}</p>
                    {m.provenance.source_url && (
                      <p className="micro">
                        <a
                          href={m.provenance.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Original data subset
                        </a>{' '}
                        · {m.provenance.license}
                      </p>
                    )}
                    <span
                      className={
                        m.provenance.synthetic ? 'amber-tag' : 'good-tag'
                      }
                    >
                      {m.provenance.synthetic
                        ? 'SYNTHETIC DEMONSTRATION'
                        : m.provenance.product
                          ? 'DERIVED PRODUCT'
                          : m.provenance.provider === 'INCOIS'
                            ? 'INCOIS · OFFICIAL SOURCE'
                            : 'REAL DATA'}
                    </span>
                    <p className="micro">
                      {m.variables.length} variables · {m.times.length} times ·{' '}
                      {m.depths.length} depths
                      <br />
                      {m.provenance.sha256 && `SHA-256: ${m.provenance.sha256}`}
                    </p>
                  </div>
                  <button
                    className="icon-button"
                    aria-label={`Explore ${m.title}`}
                    onClick={() => {
                      chooseModel(m.id);
                      setTab('explorer');
                    }}
                  >
                    <ArrowRight size={20} />
                  </button>
                </div>
              ))}
            </section>
            <IngestionPanel onImported={importFile} />
            <ExtensionPanel />
            <section className="wide-card">
              <h2>Observation inventory</h2>
              <p className="mission-caption">
                Amber joins in 3D connect recorded casts from the same mission,
                in timestamp order with a 48-hour gap limit. They do not
                reconstruct the underwater route.
              </p>
              <div className="inventory-table">
                <table>
                  <thead>
                    <tr>
                      <th>Profile</th>
                      <th>Instrument</th>
                      <th>Timestamp UTC</th>
                      <th>Origin</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(catalog?.profiles || []).map((p) => (
                      <tr key={p.id}>
                        <td>
                          <button onClick={() => inspectProfile(p)}>
                            {p.id.split(':').at(-1)}
                          </button>
                        </td>
                        <td>{p.instrument}</td>
                        <td>{p.time.replace('T', ' ').replace('Z', '')}</td>
                        <td>{p.synthetic ? 'Synthetic' : 'Imported'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </main>
      )}
      {tab === 'research' && <ResearchReport />}
    </div>
  );
}
function CoveragePanel({ coverage }: { coverage: Coverage | null }) {
  if (!coverage)
    return <div className="empty-state">Calculating coverage…</div>;
  const max = Math.max(1, ...coverage.cells.map((c) => c.distance_km || 0));
  return (
    <div className="coverage-panel">
      <div className="eyebrow">OBSERVATION SUPPORT</div>
      <h2>Where evidence is sparse</h2>
      <p>
        Distance to a quality-eligible profile within ±
        {coverage.time_window_hours} hours of the displayed model time.
      </p>
      <div
        className="coverage-grid"
        role="img"
        aria-label="Coverage map; north at top, east at right"
      >
        {[...coverage.cells]
          .sort((a, b) => b.latitude - a.latitude || a.longitude - b.longitude)
          .map((c, i) => (
            <div
              key={i}
              style={{
                background: !c.ocean
                  ? '#0a161f'
                  : c.distance_km == null
                    ? '#33404b'
                    : color(c.distance_km, 0, max, 'viridis'),
              }}
              title={`${c.latitude}°N ${c.longitude}°E: ${!c.ocean ? 'missing/land' : c.distance_km == null ? 'no eligible observation' : c.distance_km + ' km'}`}
            />
          ))}
      </div>
      <div className="range-limits">
        <span>North ↑ · East →</span>
        <span>
          {coverage.eligible_profiles
            ? `0–${max.toFixed(0)} km`
            : 'Distance unavailable'}
        </span>
      </div>
      <div className="quality-summary">
        <div>
          <span>Eligible profiles</span>
          <b>{coverage.eligible_profiles}</b>
        </div>
      </div>
      <h3>Least-observed locations</h3>
      {coverage.priority.length ? (
        coverage.priority.map((p, i) => (
          <div className="priority-row" key={i}>
            <span>0{i + 1}</span>
            <div>
              {p.latitude.toFixed(2)}°N, {p.longitude.toFixed(2)}°E
              <small>{p.distance_km.toFixed(0)} km from nearest profile</small>
            </div>
          </div>
        ))
      ) : (
        <p className="empty-state">
          No eligible observation support for this time and variable.
        </p>
      )}
      <div className="insight-note">
        <ShieldCheck size={18} />
        <p>
          Coverage is not uncertainty.
          <span>
            This heuristic helps inspect sampling gaps. It does not estimate
            model error, depth coverage, or a safe vessel route.
          </span>
        </p>
      </div>
    </div>
  );
}
function SectionChart({
  field,
  latitude,
  settings,
}: {
  field: Volume;
  latitude: number;
  settings: Settings;
}) {
  const [nx, ny, nz] = field.dimensions,
    j = Math.max(
      0,
      Math.min(
        ny - 1,
        Math.round(
          ((latitude - field.axes.latitude[0]) /
            (field.axes.latitude.at(-1)! - field.axes.latitude[0])) *
            (ny - 1),
        ),
      ),
    );
  return (
    <svg
      viewBox="0 0 800 180"
      className="section-chart"
      role="img"
      aria-label={`East west ${settings.variable} section at ${field.axes.latitude[j].toFixed(2)} degrees north`}
    >
      <title>
        Nearest displayed latitude: {field.axes.latitude[j].toFixed(2)}°N
      </title>
      {Array.from({ length: nz }, (_, z) =>
        Array.from({ length: nx }, (_, x) => {
          const value = field.values[z * nx * ny + j * nx + x];
          return (
            <rect
              aria-hidden="true"
              key={`${x}-${z}`}
              x={48 + (x * 730) / nx}
              y={12 + (z * 130) / nz}
              width={730 / nx + 0.1}
              height={130 / nz + 0.1}
              fill={
                !Number.isFinite(displayScalar(value, settings.log))
                  ? '#12202a'
                  : color(
                      value!,
                      settings.min,
                      settings.max,
                      settings.palette,
                      settings.log,
                    )
              }
            >
              <title>
                {field.axes.longitude[x].toFixed(2)}°E ·{' '}
                {field.axes.depth[z].toFixed(0)} m:{' '}
                {value == null ? 'Missing' : value.toFixed(3)}
              </title>
            </rect>
          );
        }),
      )}
      <text x="39" y="22" textAnchor="end">
        {field.axes.depth[0]} m
      </text>
      <text x="39" y="141" textAnchor="end">
        {field.axes.depth.at(-1)} m
      </text>
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <text key={t} x={48 + t * 730} y="167" textAnchor="middle">
          {(
            field.axes.longitude[0] +
            t * (field.axes.longitude.at(-1)! - field.axes.longitude[0])
          ).toFixed(1)}
          °E
        </text>
      ))}
    </svg>
  );
}
