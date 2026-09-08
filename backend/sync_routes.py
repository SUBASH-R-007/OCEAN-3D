from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router=APIRouter(prefix='/api/sync')


@router.get('/status')
def status():
    from .api import SYNC
    if SYNC is None:raise HTTPException(503,'Synchronization service is starting.')
    return SYNC.status()


@router.post('/run',status_code=202)
def run():
    from .api import SYNC
    if SYNC is None:raise HTTPException(503,'Synchronization service is starting.')
    if not SYNC.trigger():raise HTTPException(409,'A check is already queued/running or the 60-second retry interval has not elapsed.')
    return {'status':'queued'}


@router.get('/snapshot/{revision}/{product}')
def snapshot(revision:str,product:str):
    from .api import SYNC
    if SYNC is None:raise HTTPException(503,'Synchronization service is starting.')
    return FileResponse(SYNC.snapshot_path(revision,product),media_type='application/json',headers={'Cache-Control':'no-store'})
