// The API catalog owns variable definitions, including administrator plugins.
import { decodeVolume, FrameCache } from './volumeProtocol.ts';
import { validRegion } from './region.ts';
import { observationOnly, type NativeProfile } from './profiles.ts';
import { palettes } from './colorScale.ts';
import { openConnection } from './connection.ts';
export { palettes, color } from './colorScale.ts';
export type Variable = string;
export type ViewMode = 'volume' | 'slice' | 'isosurface' | 'sections';
export interface Provenance {
  product?: DerivedProduct;
  title: string;
  source: string;
  synthetic: boolean;
  warning?: string;
  sha256?: string;
  version?: string;
  source_url?: string;
  source_download_url?: string;
  forecast_reference_times?: string[];
  forecast_lead_hours?: number[];
  license?: string;
  retrieved_at?: string;
  transformations?: string[];
  provider?: string;
  product_type?: string;
  metadata_url?: string;
  documentation_url?: string;
  spatial_resolution?: string;
  temporal_resolution?: string;
  temperature_definition?: string;
  source_sha256?: string;
  support_by_time?: {
    time: string;
    valid_cells: number;
    total_cells: number;
    cells_with_local_observations: number;
    roi_count_range: number[];
    local_count_range: number[];
  }[];
}
export interface ModelInfo {
  id: string;
  title: string;
  provenance: Provenance;
  variables: { id: Variable; label: string; unit: string; range: number[] }[];
  times: string[];
  depths: number[];
  bounds: number[];
  shape: Record<string, number>;
}
export interface Profile {
  source_profile_id?: string;
  sensor_id?: string;
  geometry?: 'profile' | 'time-series' | 'surface-current';
  station_id?: string;
  sample_times?: string[];
  id: string;
  instrument: string;
  longitude: number;
  latitude: number;
  time: string;
  data_mode: string;
  source: string;
  synthetic: boolean;
  depth_range?: number[];
  warning?: string;
  trajectory_id?: string;
  feature_type?: string;
  variables?: string[];
  source_url?: string;
  source_download_url?: string;
  sha256?: string;
  license?: string;
  conversion?: string;
  acknowledgement?: string;
  time_range?: string[];
  path?: {
    longitude: number;
    latitude: number;
    depth: number;
    time: string;
    break_before?: boolean;
  }[];
}
export interface Catalog {
  variables?: ModelInfo['variables'];
  models: ModelInfo[];
  profiles: Profile[];
  mode: string;
}
export interface Volume {
  model_id: string;
  variable: Variable;
  time: string;
  dimensions: number[];
  axes: { longitude: number[]; latitude: number[]; depth: number[] };
  values: (number | null)[];
  range: number[] | null;
  valid_cells: number;
  total_cells: number;
  method: string;
  provenance: Provenance;
  maximum_depth?: number | null;
  bbox?: number[];
  sampling?: {
    selected_source_cells: number;
    source_frame_cells: number;
    resolution: number;
    native_shape: Record<string, number>;
  };
}
export interface Comparison {
  model_id?: string;
  profile: Profile;
  variable: Variable;
  pairs: {
    time?: string;
    depth: number;
    value: number;
    model: number | null;
    residual: number | null;
    qc: number;
    adjusted: boolean;
    error: number | null;
  }[];
  samples?: {
    depth: number;
    value: number | null;
    qc: number;
    source_qc?: number | null;
    adjusted: boolean;
    error: number | null;
    variable: string;
    latitude?: number;
    longitude?: number;
    time?: string;
  }[];
  comparison_reason?: string | null;
  metrics: {
    count: number;
    total: number;
    qc_excluded: number;
    unmatched: number;
    bias: number | null;
    rmse: number | null;
    mae: number | null;
  };
  method: Record<string, unknown>;
  provenance: Provenance;
  limitations: string[];
}
export interface Coverage {
  cells: {
    longitude: number;
    latitude: number;
    distance_km: number | null;
    ocean: boolean;
  }[];
  eligible_profiles: number;
  time_window_hours: number;
  priority: { longitude: number; latitude: number; distance_km: number }[];
  method: string;
}
export interface Settings {
  model: string;
  variable: Variable;
  index: number;
  mode: ViewMode;
  depth: number;
  opacity: number;
  instrumentOpacity: number;
  currentOpacity: number;
  flowOpacity: number;
  exaggeration: number;
  palette: string;
  min: number;
  max: number;
  log: boolean;
  iso: number;
  instruments: boolean;
  currents: boolean;
  flow: boolean;
  currentScope: 'column' | 'slice';
  currentStyle: 'direction' | 'scaled';
  currentLayers: number;
  cutaway: number;
  quality: 'balanced' | 'detail';
  depthWindow: 'full' | 'upper500';
  sectionX: number;
  sectionY: number;
  qc: 'strict' | 'lenient';
  profile: string;
  observationVariable: string;
  region: number[] | null;
}
export const initial: Settings = {
  model: 'incois-mnt-mccreary-latest',
  variable: 'analyzed_temperature',
  index: 2,
  mode: 'volume',
  depth: 200,
  opacity: 0.28,
  instrumentOpacity: 0.7,
  currentOpacity: 0.9,
  flowOpacity: 0.42,
  exaggeration: 500,
  palette: 'thermal',
  min: 2,
  max: 32,
  log: false,
  iso: 20,
  instruments: true,
  currents: false,
  flow: false,
  currentScope: 'column',
  currentStyle: 'direction',
  currentLayers: 12,
  cutaway: 28,
  quality: 'balanced',
  depthWindow: 'upper500',
  sectionX: 48,
  sectionY: 48,
  qc: 'strict',
  profile: '',
  observationVariable: '',
  region: null,
};
export const fmt = (v: number | null | undefined, n = 2) =>
  v == null ? '—' : v.toFixed(n);
let base = '';
let connected = false;
let writable = false;
let upstream = false;
export function apiConnected() {
  return connected;
}
export const apiWritable = () => connected && writable;
export const apiSourceAccess = () => connected && upstream;
async function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(url, { signal });
  if (!r.ok) {
    let message = `Request failed (${r.status})`;
    try {
      message = ((await r.json()) as { detail?: string }).detail || message;
    } catch {}
    throw new Error(message);
  }
  return r.json() as Promise<T>;
}
export async function connect(): Promise<Catalog> {
  connected = writable = upstream = false;
  const result = await openConnection(
    import.meta.env.VITE_SCIENTIFIC_API === 'true',
    ['localhost', '127.0.0.1'].includes(location.hostname),
  );
  connected = result.connected;
  writable = result.writable;
  upstream = result.upstream;
  base = connected ? '/api' : '';
  return result.catalog;
}
export const reloadCatalog = () =>
  connected
    ? get<Catalog>(base + '/catalog')
    : get<Catalog>('/demo/catalog.json');
const volumeCache = new FrameCache();
export const loadVolume = async (
  s: Settings,
  variable = s.variable,
  signal?: AbortSignal,
) => {
  const key = `${connected}:${s.model}:${variable}:${s.index}:${s.depthWindow}:${connected ? s.quality : 'snapshot'}:${connected ? s.region?.join(',') : ''}`;
  const cached = volumeCache.get(key);
  if (cached) {
    return cached;
  }
  let field: Volume;
  if (connected) {
    const url = `${base}/volume.bin?model=${encodeURIComponent(s.model)}&variable=${encodeURIComponent(variable)}&index=${s.index}&resolution=${s.quality === 'detail' ? 64 : 36}${s.depthWindow === 'upper500' ? '&maximum_depth=500' : ''}${s.region ? '&bbox=' + s.region.join(',') : ''}`;
    const response = await fetch(url, { signal });
    if (!response.ok) {
      let message = `Volume request failed (${response.status}).`;
      try {
        message =
          ((await response.json()) as { detail?: string }).detail || message;
      } catch {}
      throw new Error(message);
    }
    field = decodeVolume(await response.arrayBuffer());
  } else
    field = await get<Volume>(
      `/demo/${s.model}/${variable}-${s.index}${s.depthWindow === 'upper500' ? '-upper500' : ''}.json`,
      signal,
    );
  signal?.throwIfAborted();
  volumeCache.put(key, field);
  return field;
};
let comparisons: Record<string, Comparison> | null = null;
let coverages: Record<string, Coverage> | null = null;
let instrumentIndex: Record<string, string> | null = null;
const nativeProfiles = new Map<string, NativeProfile>();
export async function loadComparison(s: Settings, signal?: AbortSignal) {
  if (connected)
    return get<Comparison>(
      `${base}/profiles/${encodeURIComponent(s.profile)}?model=${encodeURIComponent(s.model)}&variable=${s.variable}&qc=${s.qc}`,
      signal,
    );
  comparisons ??= await get('/demo/comparisons.json', signal);
  instrumentIndex ??= await get('/demo/instruments/index.json', signal);
  let profile = nativeProfiles.get(s.profile);
  if (!profile && instrumentIndex?.[s.profile]) {
    profile = await get<NativeProfile>(instrumentIndex[s.profile], signal);
    signal?.throwIfAborted();
    nativeProfiles.set(s.profile, profile);
  }
  const comparison =
    comparisons![`${s.model}:${s.profile}:${s.variable}:${s.qc}`];
  if (comparison)
    return {
      ...comparison,
      samples: profile?.samples.filter((row) => row.variable === s.variable),
    };
  if (!profile)
    throw new Error(
      'This instrument is not included in the bundled snapshot. Connect the scientific API.',
    );
  const catalog = await get<Catalog>('/demo/catalog.json', signal);
  const model = catalog.models.find((m) => m.id === s.model);
  if (!model) throw new Error('Model not found.');
  return observationOnly(profile, s.variable, s.qc, model.provenance);
}
export async function loadCoverage(s: Settings, signal?: AbortSignal) {
  if (connected)
    return get<Coverage>(
      `${base}/coverage?model=${encodeURIComponent(s.model)}&variable=${s.variable}&index=${s.index}&qc=${s.qc}`,
      signal,
    );
  coverages ??= await get('/demo/coverage.json', signal);
  return coverages![`${s.model}:${s.variable}:${s.index}:${s.qc}`];
}
export type ImportReport = {
  product?: DerivedProduct;
  kind: string;
  category: 'model' | 'observations';
  title: string;
  sha256: string;
  bytes: number;
  warnings: string[];
  variables: { id: string; label: string; unit: string; samples?: number }[];
  profile_count?: number;
  sample_count?: number;
  time_steps?: number;
  shape?: Record<string, number>;
  qc?: Record<string, number>;
  depth_range: number[];
  time_range: string[];
  bounds: number[];
};
export type ImportResult = {
  id: string;
  kind: string;
  duplicate?: boolean;
  report: ImportReport;
  detail?: string;
};
export type ImportFormat = {
  id: string;
  label: string;
  container: string;
  category: string;
  accept: string;
};
export const loadImportFormats = () =>
  get<{ formats: ImportFormat[] }>(`${base}/adapters`);
export type DerivedProduct = {
  id: string;
  label: string;
  kind: 'derived' | 'machine-learning';
  version: string;
  outputs: string[];
  method: string;
  limitations: string;
  lineage?: {
    generated_at: string;
    inputs: { id: string; sha256: string }[];
    validation: string;
    limitations: string;
    artifact_sha256?: string;
    training_data?: string;
    inference_domain?: string;
  };
};
export type ExtensionCatalog = {
  api_version: number;
  plugins: { id: string; label: string; version: string }[];
  sensors: {
    id: string;
    label: string;
    geometry: string;
    description: string;
  }[];
  products: DerivedProduct[];
  variables: { id: string; label: string; unit: string }[];
  formats: ImportFormat[];
};
export const loadExtensions = () => get<ExtensionCatalog>(`${base}/extensions`);
export async function inspectUpload(
  file: File,
  kind: string,
  signal?: AbortSignal,
) {
  if (!file.size || file.size > 50 * 1024 * 1024)
    throw new Error('Choose a nonempty file of at most 50 MiB.');
  const data = new FormData();
  data.append('file', file);
  const r = await fetch(
    `${base}/import/inspect?kind=${encodeURIComponent(kind)}`,
    { method: 'POST', body: data, signal },
  );
  const result = (await r.json()) as ImportReport & { detail?: string };
  if (!r.ok) throw new Error(result.detail || 'File validation failed.');
  return result;
}
export async function upload(
  file: File,
  kind: string,
  expectedSha256?: string,
) {
  if (file.size > 50 * 1024 * 1024)
    throw new Error('Import limit is 50 MiB. Subset large files upstream.');
  const digest = await crypto.subtle.digest(
    'SHA-256',
    await file.arrayBuffer(),
  );
  const sha256 = [...new Uint8Array(digest)]
    .map((v) => v.toString(16).padStart(2, '0'))
    .join('');
  if (expectedSha256 && sha256 !== expectedSha256)
    throw new Error(
      'The selected file changed after validation. Select it again.',
    );
  const data = new FormData();
  data.append('file', file);
  const r = await fetch(`${base}/import?kind=${encodeURIComponent(kind)}`, {
    method: 'POST',
    body: data,
    headers: { 'Idempotency-Key': sha256 + ':' + kind },
  });
  const result = (await r.json()) as ImportResult;
  if (!r.ok) throw new Error(result.detail || 'Import failed');
  return result;
}
export function download(
  name: string,
  data: unknown,
  type = 'application/json',
) {
  const blob = new Blob(
    [typeof data === 'string' ? data : JSON.stringify(data, null, 2)],
    { type },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Allow embedded browsers time to hand the object URL to their download host.
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
export function validatedState(
  raw: unknown,
  allowedVariables: string[] = [
    'temperature',
    'salinity',
    'u',
    'v',
    'chlorophyll',
    'analyzed_temperature',
    'temperature_spread',
  ],
): Settings {
  const s = { ...initial };
  if (!raw || typeof raw !== 'object') return s;
  const r = raw as Record<string, unknown>;
  if (validRegion(r.region)) s.region = [...r.region];
  for (const k of ['model', 'profile'] as const)
    if (typeof r[k] === 'string' && r[k].length < 200) s[k] = r[k];
  if (
    typeof r.variable === 'string' &&
    /^[a-z][a-z0-9_]{0,63}$/.test(r.variable) &&
    allowedVariables.includes(r.variable)
  )
    s.variable = r.variable as Variable;
  if (
    typeof r.observationVariable === 'string' &&
    allowedVariables.includes(r.observationVariable)
  )
    s.observationVariable = r.observationVariable;
  if (['volume', 'slice', 'isosurface', 'sections'].includes(String(r.mode)))
    s.mode = r.mode as ViewMode;
  if (['strict', 'lenient'].includes(String(r.qc)))
    s.qc = r.qc as Settings['qc'];
  if (r.currentScope === 'column' || r.currentScope === 'slice')
    s.currentScope = r.currentScope;
  if (r.currentStyle === 'direction' || r.currentStyle === 'scaled')
    s.currentStyle = r.currentStyle;
  if (
    typeof r.currentLayers === 'number' &&
    [0, 6, 12, 24].includes(r.currentLayers)
  )
    s.currentLayers = r.currentLayers;
  if (typeof r.palette === 'string' && Object.hasOwn(palettes, r.palette))
    s.palette = r.palette;
  for (const k of ['log', 'instruments', 'currents', 'flow'] as const)
    if (typeof r[k] === 'boolean') s[k] = r[k];
  const ranges = {
    index: [0, 100000],
    depth: [0, 12000],
    opacity: [0, 1],
    instrumentOpacity: [0, 1],
    currentOpacity: [0, 1],
    flowOpacity: [0, 1],
    exaggeration: [1, 600],
    min: [-1e30, 1e30],
    max: [-1e30, 1e30],
    iso: [-1e30, 1e30],
    cutaway: [0, 75],
    sectionX: [0, 100],
    sectionY: [0, 100],
  };
  for (const k of Object.keys(ranges) as (keyof typeof ranges)[])
    if (typeof r[k] === 'number' && Number.isFinite(r[k]))
      s[k] = Math.max(ranges[k][0], Math.min(ranges[k][1], r[k]));
  s.index = Math.round(s.index);
  if (r.quality === 'detail') s.quality = 'detail';
  if (r.depthWindow === 'upper500' || r.depthWindow === 'full')
    s.depthWindow = r.depthWindow;
  if (s.min >= s.max) {
    s.min = initial.min;
    s.max = initial.max;
  }
  if (s.min <= 0) s.log = false;
  return s;
}
