'use client';
import { useEffect, useRef, useState } from 'react';
import { Upload, ArrowDownToLine, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ProductDetails } from './ExtensionPanel';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import {
  apiConnected,
  apiWritable,
  loadImportFormats,
  inspectUpload,
  upload,
  download,
  type ImportFormat,
  type ImportReport,
  type ImportResult,
} from '@/lib/ocean';

export default function IngestionPanel({
  onImported,
}: {
  onImported: (result: ImportResult) => Promise<void>;
}) {
  const [formats, setFormats] = useState<ImportFormat[]>([]);
  const [kind, setKind] = useState('auto');
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const pending = useRef<AbortController | null>(null);
  const connected = apiConnected();
  const writable = apiWritable();
  useEffect(() => {
    let alive = true;
    if (connected)
      loadImportFormats()
        .then((r) => {
          if (!Array.isArray(r.formats))
            throw new Error(
              'Import format discovery is unavailable. Connect to the updated scientific API and reload this page.',
            );
          if (alive) setFormats(r.formats);
        })
        .catch((e) => {
          if (alive) setError(e.message);
        });
    return () => {
      alive = false;
      pending.current?.abort();
    };
  }, [connected]);
  async function validate(selected: File | null, adapter: string) {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setFile(selected);
    setReport(null);
    setError('');
    if (!selected) {
      setBusy('');
      return;
    }
    setBusy('Validating file…');
    try {
      const result = await inspectUpload(selected, adapter, controller.signal);
      if (!controller.signal.aborted) setReport(result);
    } catch (e) {
      if (!controller.signal.aborted) setError((e as Error).message);
    } finally {
      if (!controller.signal.aborted) setBusy('');
    }
  }
  async function commit() {
    if (!file || !report || busy) return;
    setBusy('Adding dataset…');
    setError('');
    try {
      const result = await upload(file, report.kind, report.sha256);
      await onImported(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }
  return (
    <section className="wide-card import-card" aria-label="Data ingestion">
      <Upload size={27} />
      <h2>Bring your ocean data</h2>
      <p>
        Choose a NetCDF model or instrument file, or a long or wide text table.
        Review its variables, units and quality before adding it to the catalog.
      </p>
      <Select
        value={kind}
        disabled={!!busy}
        onValueChange={(v) => {
          if (v) {
            setKind(String(v));
            void validate(file, String(v));
          }
        }}
      >
        <SelectTrigger aria-label="Import format" className="pick">
          <SelectValue>
            {kind === 'auto'
              ? 'Detect format automatically'
              : formats.find((f) => f.id === kind)?.label || kind}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="auto">Detect format automatically</SelectItem>
          {formats.map((f) => (
            <SelectItem key={f.id} value={f.id}>
              {f.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <label className={`upload-zone ${!writable ? 'disabled' : ''}`}>
        <Upload size={22} />
        <strong>
          {busy ||
            (writable
              ? 'Choose a scientific data file'
              : connected
                ? 'Read-only archive: imports are managed by your administrator'
                : 'Connect the scientific API to import data')}
        </strong>
        <span>50 MiB maximum · original file preserved on import</span>
        <input
          aria-label="Import scientific data file"
          type="file"
          accept={
            kind === 'auto'
              ? '.nc,.nc4,.cdf,.csv,.tsv,.txt,.asc'
              : formats.find((f) => f.id === kind)?.accept
          }
          disabled={!writable || !!busy}
          onChange={(e) => {
            void validate(e.target.files?.[0] || null, kind);
            e.target.value = '';
          }}
        />
      </label>
      {error && (
        <p role="alert" className="import-error">
          {error}
        </p>
      )}
      {report && (
        <div className="import-report" aria-label="File validation report">
          <h3>
            <Check size={17} /> Validated · {report.title}
          </h3>
          <p>
            {formats.find((f) => f.id === report.kind)?.label || report.kind} ·{' '}
            {(report.bytes / 1024).toFixed(1)} KiB
          </p>
          <dl>
            <div>
              <dt>{report.category === 'model' ? 'Time steps' : 'Profiles'}</dt>
              <dd>{report.time_steps ?? report.profile_count}</dd>
            </div>
            <div>
              <dt>
                {report.category === 'model'
                  ? 'Grid shape'
                  : 'Variable samples'}
              </dt>
              <dd>
                {report.shape
                  ? Object.entries(report.shape)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(' · ')
                  : report.sample_count?.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt>Depth range</dt>
              <dd>{report.depth_range.map((n) => n.toFixed(2)).join('–')} m</dd>
            </div>
            <div>
              <dt>Observation / model times</dt>
              <dd>{report.time_range.join(' → ')}</dd>
            </div>
          </dl>
          <div className="import-variable-table">
            <table>
              <thead>
                <tr>
                  <th>Variable</th>
                  <th>Canonical unit</th>
                  {report.category === 'observations' && <th>Samples</th>}
                </tr>
              </thead>
              <tbody>
                {report.variables.map((v) => (
                  <tr key={v.id}>
                    <td>{v.label}</td>
                    <td>{v.unit}</td>
                    {report.category === 'observations' && (
                      <td>{v.samples?.toLocaleString()}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.qc && (
            <p>
              QC: {report.qc.good || 0} good · {report.qc.probably_good || 0}{' '}
              probably good · {report.qc.excluded || 0} excluded/unknown ·{' '}
              {report.qc.missing || 0} missing
            </p>
          )}
          {!!report.warnings.length && (
            <ul>
              {report.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          <ProductDetails product={report.product} />
          <p className="micro">
            Validation confirms the supported structure, units and decoding; it
            does not establish scientific accuracy. No data has been registered
            yet.
          </p>
          <details>
            <summary>File checksum</summary>
            <code>{report.sha256}</code>
          </details>
          <div className="import-actions">
            <Button onClick={() => void commit()} disabled={!!busy}>
              Add validated dataset
            </Button>
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() => download('ocean3d-import-validation.json', report)}
            >
              Download validation report
            </Button>
          </div>
        </div>
      )}
      <p className="micro">
        Text: comma, tab, semicolon, pipe or whitespace; UTF-8 and quoted
        fields. Depth is positive down in m/km. Temperature denotes potential
        temperature. Explicit units are converted; omitted built-in units use
        the documented canonical units and are reported above. Missing QC
        remains unknown.
      </p>
      <p className="micro">
        Models: regional rectilinear CF grids with Gregorian time and physical
        depth. Curvilinear/sigma grids require an adapter or upstream
        conversion. CF profiles support orthogonal, incomplete,
        contiguous-ragged and indexed-ragged arrays.
      </p>
      <details className="micro">
        <summary>Synthetic extension examples</summary>
        <p>
          Contract fixtures only. These are not measured sensor data or trained
          ML predictions.
        </p>
        {['mooring.csv', 'adcp.csv', 'hf-radar.csv', 'ml-output.nc'].map(
          (name) => (
            <p key={name}>
              <a href={'/examples/extensions/synthetic-' + name}>
                Download synthetic {name}
              </a>
            </p>
          ),
        )}
      </details>
      <div className="import-actions">
        <Button
          variant="outline"
          onClick={() =>
            download(
              'observations-template.csv',
              'profile_id,instrument,longitude,latitude,time,depth,variable,value,unit,qc,synthetic\nMY-CAST-01,CTD,85,14,2025-09-03T12:00:00Z,10,temperature,28.2,degree_celsius,1,true\n',
              'text/csv',
            )
          }
        >
          <ArrowDownToLine size={15} /> Long CSV template
        </Button>
        <a href="/examples/observations-wide.csv" download>
          Wide CSV example
        </a>
        <a href="/examples/synthetic-glider.nc" download>
          CF glider example
        </a>
      </div>
    </section>
  );
}
