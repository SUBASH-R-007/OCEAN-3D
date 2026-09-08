'use client';
import { useEffect, useState } from 'react';
import {
  apiConnected,
  loadExtensions,
  type ExtensionCatalog,
  type DerivedProduct,
} from '@/lib/ocean';

export function ProductDetails({ product }: { product?: DerivedProduct }) {
  if (!product) return null;
  return (
    <section
      aria-label="Derived product provenance"
      className="instrument-section"
    >
      <h3>
        {product.kind === 'machine-learning'
          ? 'ML-derived product'
          : 'Derived product'}{' '}
        · {product.version}
      </h3>
      <p>{product.label}</p>
      <p>{product.method}</p>
      <p className="profile-warning">{product.limitations}</p>
      {product.lineage && (
        <>
          <p>Generated: {product.lineage.generated_at}</p>
          <p>{product.lineage.validation}</p>
          <p>{product.lineage.limitations}</p>
          <details className="micro">
            <summary>Inputs and model provenance</summary>
            {product.lineage.training_data && (
              <p>Training data: {product.lineage.training_data}</p>
            )}
            {product.lineage.inference_domain && (
              <p>Inference domain: {product.lineage.inference_domain}</p>
            )}
            {product.lineage.artifact_sha256 && (
              <p style={{ overflowWrap: 'anywhere' }}>
                Artifact SHA-256: {product.lineage.artifact_sha256}
              </p>
            )}
            {product.lineage.inputs.map((source) => (
              <p key={source.id} style={{ overflowWrap: 'anywhere' }}>
                {source.id} · {source.sha256}
              </p>
            ))}
          </details>
        </>
      )}
    </section>
  );
}

export default function ExtensionPanel() {
  const [catalog, setCatalog] = useState<ExtensionCatalog | null>(null),
    [error, setError] = useState('');
  const connected = apiConnected();
  useEffect(() => {
    let active = true;
    if (connected)
      loadExtensions()
        .then((c) => {
          if (active) setCatalog(c);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [connected]);
  return (
    <section className="wide-card" aria-label="Installed extensions">
      <h2>Installed extensions</h2>
      <p>
        Sensor formats, new variables and derived products join the same
        catalog, viewer and export workflow.
      </p>
      {!connected ? (
        <p>
          Connect the scientific API to inspect this deployment’s extensions.
        </p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : !catalog ? (
        <p>Loading installed extensions…</p>
      ) : (
        <>
          <p>
            {catalog.plugins.length} extension packs · {catalog.formats.length}{' '}
            import formats · {catalog.products.length} registered derived
            products
          </p>
          <details>
            <summary>Sensor contracts</summary>
            {catalog.sensors.map((sensor) => (
              <div key={sensor.id}>
                <h3>{sensor.label}</h3>
                <p>{sensor.description}</p>
              </div>
            ))}
          </details>
          <details>
            <summary>Extension versions and variables</summary>
            {catalog.plugins.map((p) => (
              <p key={p.id}>
                {p.label} · {p.version}
              </p>
            ))}
            {catalog.variables.map((v) => (
              <p key={v.id}>
                {v.label} · {v.unit}
              </p>
            ))}
          </details>
          <details>
            <summary>Derived products</summary>
            {catalog.products.length ? (
              catalog.products.map((p) => (
                <ProductDetails key={p.id} product={p} />
              ))
            ) : (
              <p>
                No product definitions are installed. An administrator can
                register externally computed model outputs, including ML
                products, with their provenance.
              </p>
            )}
          </details>
        </>
      )}
      <p className="micro">
        Administrators install reviewed extension code. Scientific file uploads
        cannot install plugins or execute model files.
      </p>
    </section>
  );
}
