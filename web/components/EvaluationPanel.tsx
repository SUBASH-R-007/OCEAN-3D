'use client';
import { useState } from 'react';
import { download, type Settings } from '@/lib/ocean';
import { evaluationTasks, evaluationRecord } from '@/lib/evaluation';
import { SourceChoice } from './SourceChoice';

export default function EvaluationPanel({
  visible,
  onOpen,
  evidence,
}: {
  visible: boolean;
  onOpen: (s: Partial<Settings>) => void;
  evidence: unknown;
}) {
  const [participant, setParticipant] = useState('P01'),
    [condition, setCondition] = useState('developer-practice'),
    [task, setTask] = useState(evaluationTasks[0].id),
    [active, setActive] = useState<{ id: string; start: number } | null>(null),
    [answer, setAnswer] = useState(''),
    [error, setError] = useState(''),
    [records, setRecords] = useState<ReturnType<typeof evaluationRecord>[]>([]);
  if (!visible && !active) return null;
  const current = evaluationTasks.find((t) => t.id === (active?.id || task))!;
  const begin = () => {
    setError('');
    if (!/^P[0-9]{2,4}$/.test(participant)) {
      setError('Use a pseudonymous code such as P01.');
      return;
    }
    try {
      if (condition !== 'usual-workflow')
        onOpen({
          ...current.settings,
          log: false,
          region: null,
          depthWindow: 'full',
          palette: 'thermal',
        });
      setActive({ id: task, start: performance.now() });
      setAnswer('');
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const finish = () => {
    try {
      if (!active) return;
      const row = evaluationRecord(
        active.id,
        condition,
        participant,
        answer,
        active.start,
        performance.now(),
        evidence,
      );
      setRecords((r) => [...r, row]);
      setActive(null);
      setAnswer('');
      setError('');
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <section className="learning-guide" aria-label="Forecaster evaluation">
      <h2>
        {active ? 'Timed evaluation in progress' : 'Forecaster evaluation'}
      </h2>
      <p>
        Compare the same tasks with Ocean3D and the usual workflow. Results stay
        in this page until exported; no names or contact details are collected.
        Developer practice is not evidence of forecaster performance.
      </p>
      {error && <p role="alert">{error}</p>}
      {!active ? (
        <div className="source-controls">
          <label>
            Participant code
            <input
              aria-label="Participant code"
              value={participant}
              onChange={(e) => setParticipant(e.target.value)}
              maxLength={5}
            />
          </label>
          <SourceChoice
            label="Evaluation condition"
            value={condition}
            onChange={setCondition}
            options={[
              { value: 'developer-practice', label: 'Developer practice' },
              { value: 'ocean3d', label: 'Ocean3D' },
              { value: 'usual-workflow', label: 'Usual workflow' },
            ]}
          />
          <SourceChoice
            label="Evaluation task"
            value={task}
            onChange={setTask}
            options={evaluationTasks.map((t) => ({
              value: t.id,
              label: t.title,
            }))}
          />
          <button type="button" onClick={begin}>
            Start timed task
          </button>
        </div>
      ) : null}
      <h3>{current.title}</h3>
      <p>{current.prompt}</p>
      {active && (
        <>
          <label>
            Response and supporting evidence
            <textarea
              aria-label="Evaluation response"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              maxLength={4000}
              rows={3}
              style={{ width: '100%' }}
            />
          </label>
          <button type="button" onClick={finish}>
            Finish and record task
          </button>
          <button
            type="button"
            onClick={() => {
              setActive(null);
              setAnswer('');
            }}
          >
            Cancel trial
          </button>
          <p>
            Elapsed time includes time spent in other tabs or tools. The
            facilitator scores correctness separately.
          </p>
        </>
      )}
      <p>
        {records.length} completed trial{records.length === 1 ? '' : 's'} ·
        Unscored responses
      </p>
      <button
        type="button"
        disabled={!records.length || !!active}
        onClick={() =>
          download(
            'ocean3d-evaluation.json',
            JSON.stringify(
              { schema: 'ocean3d-evaluation-session-1', trials: records },
              null,
              2,
            ),
            'application/json',
          )
        }
      >
        Export evaluation results
      </button>
    </section>
  );
}
