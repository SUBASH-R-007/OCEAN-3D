import type { Catalog } from './ocean';

export async function openConnection(
  required: boolean,
  local: boolean,
  request: typeof fetch = fetch,
) {
  async function json<T>(path: string, timeout: number): Promise<T> {
    const response = await request(path, {
      signal: AbortSignal.timeout(timeout),
    });
    if (!response.ok) {
      if (response.status === 401 || response.status === 403)
        throw new Error(
          'Institutional authentication is required. Sign in through your institution’s gateway.',
        );
      throw new Error(
        `Scientific service returned HTTP ${response.status} at ${path}.`,
      );
    }
    return response.json() as Promise<T>;
  }
  if (required || local) {
    try {
      const health = await json<{ mode: string; status: string }>(
        '/api/health',
        5000,
      );
      if (health.mode !== 'scientific-api' || health.status !== 'ok')
        throw new Error('The proxy did not return the Ocean3D scientific API.');
      const ready = await json<{
        status: string;
        capabilities?: { imports: boolean; upstream_acquisition: boolean };
      }>('/api/ready', 5000);
      if (ready.status !== 'ready')
        throw new Error('The scientific data catalog is not ready.');
      const catalog = await json<Catalog>('/api/catalog', 30000);
      if (
        !Array.isArray(catalog.models) ||
        !catalog.models.length ||
        !Array.isArray(catalog.profiles)
      )
        throw new Error('The scientific service returned an invalid catalog.');
      return {
        catalog,
        connected: true,
        writable: ready.capabilities?.imports === true,
        upstream: ready.capabilities?.upstream_acquisition === true,
      };
    } catch (error) {
      if (required)
        throw new Error(
          `Scientific API unavailable. ${(error as Error).message} Check the service, then retry the connection.`,
        );
    }
  }
  return {
    catalog: (await json('/demo/catalog.json', 30000)) as Catalog,
    connected: false,
    writable: false,
    upstream: false,
  };
}
