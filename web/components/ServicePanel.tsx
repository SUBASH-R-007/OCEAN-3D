'use client';
import { useState } from 'react';
import { apiConnected, type ModelInfo } from '@/lib/ocean';
import './services.css';

export default function ServicePanel({models}:{models:ModelInfo[]}) {
  const [id,setId]=useState('incois-bob'), [variable,setVariable]=useState('analyzed_temperature'), [depth,setDepth]=useState('0');
  const m=models.find(m=>m.id===id)||models[0];
  if (!m) return null;
  const v=m.variables.find(v=>v.id===variable)||m.variables[0];
  const zi=Math.min(Number(depth),m.depths.length-1);
  const root='/api/ogc/', layer=`${m.id}:${v.id}`, coverage=`${layer}:${zi}`;
  const map=root+'wms?'+new URLSearchParams({SERVICE:'WMS',VERSION:'1.3.0',REQUEST:'GetMap',LAYERS:layer,STYLES:'thermal',CRS:'CRS:84',BBOX:m.bounds.join(','),WIDTH:'400',HEIGHT:'320',FORMAT:'image/png',TRANSPARENT:'TRUE',TIME:m.times.at(-1)!,ELEVATION:String(-m.depths[zi])});
  const nc=root+'wcs?'+new URLSearchParams({SERVICE:'WCS',VERSION:'1.0.0',REQUEST:'GetCoverage',COVERAGE:coverage,CRS:'EPSG:4326',BBOX:m.bounds.join(','),FORMAT:'NetCDF',TIME:m.times.at(-1)!});
  return <section className="wide-card services-panel"><span className="eyebrow">PORTAL INTEROPERABILITY</span><h2>Use the same data in another tool</h2><p>WMS serves a map at an advertised time and depth. WCS returns the native numerical grid with its missing cells and coordinates.</p>
    {apiConnected()?<><div className="service-controls"><label>Service dataset<select aria-label="Service dataset" value={m.id} onChange={e=>{setId(e.target.value);setDepth('0');}}>{models.map(m=><option key={m.id} value={m.id}>{m.title}</option>)}</select></label><label>Service variable<select aria-label="Service variable" value={v.id} onChange={e=>setVariable(e.target.value)}>{m.variables.map(v=><option key={v.id} value={v.id}>{v.label}</option>)}</select></label><label>Native depth<select aria-label="Service native depth" value={String(zi)} onChange={e=>setDepth(e.target.value)}>{m.depths.map((z,i)=><option value={i} key={i}>{z} m</option>)}</select></label></div><div className="service-links"><a href={root+'wms?SERVICE=WMS&REQUEST=GetCapabilities'} target="_blank" rel="noreferrer">WMS 1.3 capabilities ↗</a><a href={root+'wcs?SERVICE=WCS&REQUEST=GetCapabilities'} target="_blank" rel="noreferrer">WCS 1.0 capabilities ↗</a><a href={map} target="_blank" rel="noreferrer">Open selected WMS map ↗</a><a href={nc}>Download native WCS coverage ↓</a></div><p className="micro">Latest available timestamp: {m.times.at(-1)}. One native depth per WCS coverage; no reprojection or resampling. WMS supports EPSG:4326 and CRS:84. Full OGC certification has not been claimed.</p></>:<p className="service-offline">These services run with the scientific API on your institution’s server. This bundled preview includes the datasets and learning tools; connect the self-hosted API for imports and WMS/WCS access.</p>}
  </section>;
}
