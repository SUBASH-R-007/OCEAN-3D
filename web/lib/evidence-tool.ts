/* oxlint-disable react/react-compiler -- Ref supplies the latest committed evidence to a page-scoped tool. */
import { useEffect, useRef } from 'react';

type Registry = {
  registerTool: (
    tool: {
      name: string;
      title: string;
      description: string;
      inputSchema: object;
      annotations: object;
      execute: (input: unknown) => unknown;
    },
    options: { signal: AbortSignal },
  ) => void | Promise<void>;
};
export function useEvidenceTool(
  evidence: Record<string, unknown>,
  enabled = true,
) {
  const current = useRef(evidence);
  useEffect(() => {
    current.current = evidence;
  }, [evidence]);
  useEffect(() => {
    if (!enabled) return;
    const registry = (document as Document & { modelContext?: Registry })
      .modelContext;
    if (!registry?.registerTool) return;
    const lifecycle = new AbortController();
    try {
      Promise.resolve(
        registry.registerTool(
          {
            name: 'get_ocean_evidence',
            title: 'Read current ocean evidence',
            description:
              'Return the visible Ocean3D settings, model provenance and completed comparison metrics. This reads the current view; it does not fetch data, change settings or generate a forecast.',
            inputSchema: {
              type: 'object',
              properties: {},
              additionalProperties: false,
            },
            annotations: { readOnlyHint: true, untrustedContentHint: true },
            execute(input: unknown) {
              if (
                !input ||
                typeof input !== 'object' ||
                Array.isArray(input) ||
                Object.keys(input).length
              )
                throw new Error('Expected an empty object.');
              return current.current;
            },
          },
          { signal: lifecycle.signal },
        ),
      ).catch(() => {});
    } catch {
      /* Unsupported experimental registry leaves the visible workflow intact. */
    }
    return () => lifecycle.abort();
  }, [enabled]);
}
