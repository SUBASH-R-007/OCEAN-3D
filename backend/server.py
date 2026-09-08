"""Validated institutional server entry point: python -m backend.server."""
from dataclasses import dataclass
import os
from typing import Mapping


@dataclass(frozen=True)
class ServerSettings:
    mode: str = 'writable'
    workers: int = 1
    max_active: int = 6
    host: str = '127.0.0.1'
    port: int = 8000

    @property
    def readonly(self):
        return self.mode == 'readonly'

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None):
        env = os.environ if env is None else env
        mode = env.get('OCEAN_MODE', 'writable')
        if mode not in ('writable', 'readonly'):
            raise ValueError('OCEAN_MODE must be writable or readonly.')
        def integer(name, default, low, high):
            try: value = int(env.get(name, str(default)))
            except ValueError as exc: raise ValueError(f'{name} must be an integer.') from exc
            if not low <= value <= high: raise ValueError(f'{name} must be between {low} and {high}.')
            return value
        workers = integer('OCEAN_WORKERS', env.get('WEB_CONCURRENCY', '1'), 1, 8)
        if mode == 'writable' and workers != 1:
            raise ValueError('Writable imports require OCEAN_WORKERS=1. Use readonly mode for multiple immutable archive workers.')
        return cls(mode, workers, integer('OCEAN_MAX_ACTIVE', 6, 1, 32),
                   env.get('OCEAN_HOST', '127.0.0.1'), integer('OCEAN_PORT', 8000, 1, 65535))


def main():
    import uvicorn
    config = ServerSettings.from_env()
    uvicorn.run('backend.api:app', host=config.host, port=config.port,
                workers=config.workers, timeout_keep_alive=5,
                timeout_graceful_shutdown=120, server_header=False,
                proxy_headers=False)


if __name__ == '__main__':
    main()
