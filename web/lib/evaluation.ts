import type { Settings } from './ocean';

export const evaluationTasks = [
  {
    id: 'profile-evidence',
    title: 'Assess model–observation agreement',
    prompt:
      'Inspect the real Argo profile, record the matched-level count and RMSE with units, and explain whether this establishes independent forecast skill.',
    settings: {
      model: 'reference-indian',
      variable: 'temperature',
      profile: '5904729-274-0',
      index: 0,
      mode: 'volume',
      min: 5,
      max: 31,
      instruments: true,
    },
  },
  {
    id: 'current-interpretation',
    title: 'Interpret depth-resolved currents',
    prompt:
      'Inspect currents at two depths. Record the source timestamp and depths, explain what the streamline animation represents, and state whether it can support a search-and-rescue drift prediction by itself.',
    settings: {
      model: 'hycom-currents-indian',
      variable: 'u',
      index: 0,
      mode: 'slice',
      min: -1,
      max: 1,
      depth: 100,
      currents: true,
      flow: true,
    },
  },
  {
    id: 'source-meaning',
    title: 'Check source meaning and freshness',
    prompt:
      'Identify the latest date in this fixed INCOIS case, its temperature definition and source resolution. Explain which of these facts limits an operational interpretation.',
    settings: {
      model: 'incois-mnt-mccreary-latest',
      variable: 'analyzed_temperature',
      index: 2,
      mode: 'volume',
      min: 2,
      max: 32,
      instruments: true,
    },
  },
] satisfies {
  id: string;
  title: string;
  prompt: string;
  settings: Partial<Settings>;
}[];

export function evaluationRecord(
  taskId: string,
  condition: string,
  participant: string,
  answer: string,
  started: number,
  finished: number,
  evidence: unknown,
) {
  if (
    !evaluationTasks.some((t) => t.id === taskId) ||
    !['usual-workflow', 'ocean3d', 'developer-practice'].includes(condition) ||
    !/^P[0-9]{2,4}$/.test(participant) ||
    answer.trim().length < 20 ||
    answer.length > 4000 ||
    !Number.isFinite(started) ||
    !Number.isFinite(finished) ||
    finished < started
  )
    throw Error(
      'Provide a participant code, condition and a substantive response.',
    );
  return {
    schema: 'ocean3d-evaluation-1',
    task_id: taskId,
    condition,
    participant,
    answer: answer.trim(),
    elapsed_seconds: (finished - started) / 1000,
    completed_at: new Date().toISOString(),
    score: null,
    evidence,
  };
}
