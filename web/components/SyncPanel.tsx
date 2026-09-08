'use client';
import { useEffect, useState, useRef } from 'react';
import { apiConnected } from '@/lib/ocean';

const dateLabel = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
};

type SyncStatus = {
  status: string;
  enabled: boolean;
  can_run: boolean;
  interval_seconds: number;
  last_attempt: string | null;
  last_success: string | null;
  next_check: string | null;
  error: string | null;
  revision?: string;
  current_product?: string;
  products: {
    id: string;
    title: string;
    status: string;
    source_end: string;
    data_time?: string;
    retained_data_time?: string;
    detail?: string;
  }[];
};

export default function SyncPanel({
  revision,
  onRefresh,
}: {
  revision?: string;
  onRefresh: () => void;
}) {
  const [status, setStatus] = useState<SyncStatus | null>(null),
    [error, setError] = useState(''),
    [queued, setQueued] = useState(false);
  const connected = apiConnected();
  const queuedAfter = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (!connected) return;
    let active = true;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const r = await fetch('/api/sync/status', {
          signal: controller.signal,
          cache: 'no-store',
        });
        if (!r.ok) throw Error(`Refresh status unavailable (${r.status})`);
        const value = (await r.json()) as SyncStatus;
        if (active) {
          setStatus(value);
          setError('');
          if (
            value.status === 'running' ||
            (queuedAfter.current !== undefined &&
              value.last_attempt !== queuedAfter.current)
          ) {
            setQueued(false);
            queuedAfter.current = undefined;
          }
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    void poll();
    const timer = setInterval(poll, 10000);
    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
    };
  }, [connected]);
  const run = async () => {
    setError('');
    setQueued(true);
    queuedAfter.current = status?.last_attempt;
    try {
      const r = await fetch('/api/sync/run', { method: 'POST' });
      if (!r.ok) throw Error(((await r.json()) as { detail: string }).detail);
    } catch (e) {
      setError((e as Error).message);
      setQueued(false);
      queuedAfter.current = undefined;
    }
  };
  if (!connected)
    return (
      <section className="source-note">
        <strong>Bundled source snapshot</strong>
        <p>
          Connect the scientific API for source synchronization. This copy does
          not refresh itself.
        </p>
      </section>
    );
  return (
    <section className="source-note" aria-label="INCOIS synchronization">
      <h2>Source freshness</h2>
      {error && <p role="alert">{error}</p>}
      {!status ? (
        <p>Reading refresh status…</p>
      ) : (
        <>
          <p>
            <strong>
              {queued
                ? 'Check queued'
                : status.status === 'running'
                  ? 'Checking INCOIS'
                  : status.status === 'ok'
                    ? 'Refresh completed'
                    : status.status === 'partial'
                      ? 'Some products could not refresh'
                      : status.status === 'error'
                        ? 'Refresh failed'
                        : 'Waiting for a source check'}
            </strong>{' '}
            ·{' '}
            {status.enabled
              ? `Automatic checks every ${status.interval_seconds / 3600} hours`
              : 'Automatic checks are disabled'}
          </p>
          <p>
            Last attempt:{' '}
            {status.last_attempt
              ? dateLabel(status.last_attempt)
              : 'Not checked'}{' '}
            · Last published catalogue:{' '}
            {status.last_success
              ? dateLabel(status.last_success)
              : 'Bundled snapshot only'}
          </p>
          {status.next_check && (
            <p>Next scheduled check: {dateLabel(status.next_check)}</p>
          )}
          {status.current_product && <p>Checking {status.current_product}…</p>}
          {status.error && <output>{status.error}</output>}
          <p>
            A successful download can still contain historical data. Read each
            product’s source dates; polling does not make an analysis a
            real-time forecast.
          </p>
          <div className="source-controls">
            <button
              type="button"
              className="primary-button"
              disabled={
                !status.can_run || queued || status.status === 'running'
              }
              onClick={() => void run()}
            >
              Check INCOIS now
            </button>
            <button
              type="button"
              onClick={onRefresh}
              disabled={!status.revision || status.status === 'running'}
            >
              {status.revision && status.revision !== revision
                ? 'Load updated source catalogue'
                : 'Reload source catalogue'}
            </button>
          </div>
          <details>
            <summary>
              Product refresh results ({status.products.length})
            </summary>
            {status.products.map((p) => (
              <div key={p.id}>
                <h3>{p.title}</h3>
                <p>
                  {p.status} · Published coverage ends {p.source_end}
                </p>
                {(p.data_time || p.retained_data_time) && (
                  <p>
                    Available packet date: {p.data_time || p.retained_data_time}
                  </p>
                )}
                {p.detail && <p>{p.detail}</p>}
              </div>
            ))}
          </details>
        </>
      )}
    </section>
  );
}
