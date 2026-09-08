"""Public INCOIS source-library routes; data requests are bounded by the API gate."""
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from .incois_catalog import read_catalog, product_for, grid_packet, acquire_volume

router=APIRouter(prefix='/api/incois')


@router.get('/catalog')
def catalog(): return read_catalog()


@router.get('/grid')
def grid(product:str,variable:str,index:int=Query(...,ge=0),depth:int=Query(0,ge=0),bbox:str|None=None,resolution:int=Query(240,ge=16,le=480),revision:str|None=None):
    bounds=tuple(float(x) for x in bbox.split(',')) if bbox else None
    return grid_packet(product_for(product,revision),[variable],index,depth,bounds,resolution)


@router.get('/observations')
def observations(start:str,end:str,bbox:str|None=None,revision:str|None=None):
    from .incois_observations import observation_packet
    return observation_packet(start,end,tuple(float(v) for v in bbox.split(',')) if bbox else None,revision)


class OpenVolume(BaseModel):
    product:str
    index:int
    revision:str|None=None


@router.post('/open')
def open_volume(body:OpenVolume):
    from .api import LOCK,MODELS
    product=product_for(body.product,body.revision)
    # The remote IO is separate from scientific reads, which remain responsive.
    with LOCK:
        if len(MODELS)>=32: raise HTTPException(409,'32 models are already loaded. Restart the service to clear on-demand selections.')
    model,_=acquire_volume(product,body.index)
    with LOCK:
        if model.id in MODELS: model.close()
        elif len(MODELS)>=32:
            model.close();raise HTTPException(409,'Model capacity reached.')
        else: MODELS[model.id]=model
        return MODELS[model.id].catalog()
