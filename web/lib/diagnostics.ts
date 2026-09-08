import { apiConnected, type Settings } from './ocean';
export interface Crossing {
  depth_m: number | null;
  status: string;
  bracket_m: number[] | null;
}
export interface ColumnDiagnostics {
  density_mld: Crossing;
  temperature_departure_depth: Crossing;
  barrier_layer: {
    signed_thickness_m: number | null;
    status: string;
    equivalent_density_delta_kg_m3: number | null;
    method?: string;
  };
  density_threshold_sensitivity: ({ delta_kg_m3: number } & Crossing)[];
  rows: {
    depth: number;
    theta: number | null;
    salinity: number | null;
    sigma0: number | null;
    conservative_temperature: number | null;
  }[];
  stratification: {
    depths: number[];
    n_squared_s2: (number | null)[];
    method: string;
  };
  valid_levels: number;
  total_levels: number;
  method: {
    reference_depth_m: number;
    density_increase_kg_m3: number;
    maximum_vertical_gap_m: number;
    equation_of_state: string;
  };
  limitations: string[];
  sources: string[];
  time: string;
}
export interface Diagnostics extends ColumnDiagnostics {
  longitude: number;
  latitude: number;
  observation?: ColumnDiagnostics;
  observation_unavailable?: string;
}
let bundle: Record<string, Diagnostics> | null = null;
export async function loadDiagnostics(
  s: Pick<Settings, 'model' | 'index' | 'profile'>,
  lon: number,
  lat: number,
  signal?: AbortSignal,
) {
  if (apiConnected()) {
    const url = `/api/diagnostics?model=${encodeURIComponent(s.model)}&index=${s.index}&longitude=${lon}&latitude=${lat}&profile=${encodeURIComponent(s.profile)}`;
    const r = await fetch(url, { signal });
    if (!r.ok)
      throw new Error(
        ((await r.json()) as { detail?: string }).detail ||
          'Column diagnostics unavailable.',
      );
    return (await r.json()) as Diagnostics;
  }
  if (!bundle) {
    const r = await fetch('/demo/diagnostics.json', { signal });
    if (!r.ok) throw new Error('Bundled diagnostics unavailable.');
    bundle = await r.json();
  }
  const result = bundle![`${s.model}:${s.profile}:${s.index}`];
  if (!result)
    throw new Error(
      'No bundled diagnostic for this model and instrument location.',
    );
  return result;
}
