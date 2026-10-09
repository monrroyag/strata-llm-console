"""Analizador de configuración de Strata: hardware + config + historial."""
from __future__ import annotations
import json, subprocess
from collections import deque
from pathlib import Path
BASE=Path(__file__).resolve().parent; HIST=BASE/'data'/'history'
EXPERT_MIN_MIB=3000
KV_BPT={'fp16':273*1024,'int8':137*1024,'q4_0':68*1024,'k8v4':106*1024}

def _gpu():
    try:
        r=subprocess.run(['nvidia-smi','--query-gpu=memory.free,memory.total,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=6,check=True)
        rows=[]
        for line in r.stdout.splitlines():
            parts=[int(x.strip()) for x in line.split(',')[:3]]
            if len(parts)==3: rows.append(parts)
        if not rows: raise ValueError('nvidia-smi returned no GPU rows')
        return {'free_mib':sum(x[0] for x in rows),'total_mib':sum(x[1] for x in rows),'util_pct':round(sum(x[2] for x in rows)/len(rows),1),'gpu_count':len(rows),'measured':True}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'free_mib':None,'total_mib':None,'util_pct':None,'gpu_count':0,'measured':False}

def _ram():
    try:
        vals={}
        for line in Path('/proc/meminfo').read_text().splitlines():
            k,v=line.split(':',1);vals[k]=int(v.strip().split()[0])//1024
        return {'available_mib':vals.get('MemAvailable',0),'total_mib':vals.get('MemTotal',0),'measured':bool(vals.get('MemAvailable'))}
    except Exception:return {'available_mib':0,'total_mib':0,'measured':False}

def _setup(entry):
    if not entry:return {}
    try:
        cfg=json.loads((BASE/entry['config']).read_text());args=cfg.get('args',[]);out={'sampling':cfg.get('sampling') or {}};i=0
        while i<len(args):
            if str(args[i]).startswith('--') and i+1<len(args) and not str(args[i+1]).startswith('--'):
                out[args[i][2:].replace('-','_')]=args[i+1];i+=2
            else:out[str(args[i])[2:].replace('-','_')]=True;i+=1
        return out
    except (OSError,ValueError,KeyError):return {}

def _history(ctx,mid=None):
    rows=deque(maxlen=500);paths=[HIST/f'{mid}.jsonl'] if mid else list(HIST.glob('*.jsonl'))
    for p in paths:
        if not p.exists():continue
        try:
            with p.open(encoding='utf-8') as fh:
                for line in fh:
                    try:
                        r=json.loads(line)
                        if abs(int(r.get('max_context') or 0)-ctx)<=max(4096,ctx//20) and r.get('tok_s_mean'):rows.append(r)
                    except (ValueError,TypeError,json.JSONDecodeError):continue
        except OSError:continue
    return list(rows)

def _weights(entry):
    if not entry:return None
    root=Path(entry.get('gguf',''))
    if not root.exists():return None
    try:
        fs=list(root.glob('*.gguf')) if root.is_dir() else [root]
        return round(sum(x.stat().st_size for x in fs if x.is_file())/2**30,2)
    except OSError:return None

def _candidate(ctx,profile,kv,grow,resident,gpu,ram):
    bpt=KV_BPT[kv]; total=ctx*bpt/1024/1024; rt=resident or (32768 if grow else ctx)
    kv_vram=rt*bpt/1024/1024; kv_ram=max(0,total-kv_vram); reserve=700 if profile!='speed' else 450
    gpu_free=gpu.get('free_mib')
    gpu_total=gpu.get('total_mib')
    expert=(gpu_free if gpu_free is not None else 0)-kv_vram-reserve
    spec={'speed':8,'balanced':6,'long':4,'code':8}.get(profile,6); lookup={'speed':4,'balanced':8,'long':4,'code':8}.get(profile,8)
    feasible=bool(gpu.get('measured')) and expert>=EXPERT_MIN_MIB and kv_ram<=ram['available_mib']*.55; risks=[]
    if not gpu.get('measured'): risks.append('VRAM real no disponible: ejecuta nvidia-smi antes de aplicar')
    if kv_ram: risks.append('usa RAM/offload y puede depender de PCIe')
    if expert<5000: risks.append('poco margen para cache de expertos')
    score=expert*.55+spec*30+lookup*10-(0 if kv=='q4_0' else 180)+(450 if profile in ('speed','code') and not grow else 0)
    if not feasible:score-=100000
    return {'score':round(score),'feasible':feasible,'config':{'max_context':ctx,'kv':kv,'kv_grow':grow,'kv_resident':resident,'vram_reserve_mib':reserve,'spec':spec,'spec_min_p':.65 if profile=='speed' else .70,'lookup_chain':lookup,'suffix_draft':3,'prompt_cache':4 if ctx>100000 else 6,'prefill':'auto','expert_cache':'auto','adapt_every':1},'estimates':{'kv_total_mib':round(total),'kv_vram_mib':round(kv_vram),'kv_ram_mib':round(kv_ram),'expert_budget_mib':round(expert),'vram_total_mib':gpu_total,'vram_free_mib':gpu_free,'ram_available_mib':ram['available_mib']},'risks':risks,'why':_why(profile,kv,grow,resident,ctx)}

def _why(profile,kv,grow,resident,ctx):
    text={'speed':'prioriza decode y MTP','balanced':'equilibra velocidad, memoria y estabilidad','long':'prioriza estabilidad en contexto largo','code':'prioriza lookup para patrones de código'}.get(profile,'equilibra velocidad y estabilidad')
    return f'{text}; {kv} para {ctx:,} tokens; '+('KV dinámico con offload' if grow else 'KV residente en VRAM')+(f', residente {resident} tokens' if resident else '')+'.'

def optimize(target_ctx,profile='balanced',entry=None,prefer=None):
    ctx=max(4096,min(int(target_ctx),262144));profile=profile if profile in {'speed','balanced','long','code'} else 'balanced';gpu,ram=_gpu(),_ram();setup=_setup(entry);rows=_history(ctx,entry.get('id') if entry else None);opts=['q4_0','k8v4','int8'] if ctx<128000 else ['q4_0','k8v4'];cands=[]
    for kv in opts:
        for grow in (False,True):
            for resident in ((0,40960) if ctx>=128000 else (0,)):cands.append(_candidate(ctx,profile,kv,grow,resident,gpu,ram))
    cands.sort(key=lambda x:(-x['feasible'],-x['score']));best=cands[0] if cands and cands[0]['feasible'] else None;hist=sorted(rows,key=lambda x:-(x.get('tok_s_mean') or 0))[:3]
    confidence='alta' if best and hist and gpu.get('measured') and entry else 'media' if best and gpu.get('measured') else 'baja'
    if best and setup.get('kv')==best['config']['kv'] and gpu.get('measured') and hist:confidence='alta'
    confidence_reasons=[]
    if not gpu.get('measured'): confidence_reasons.append('GPU telemetry unavailable')
    elif gpu.get('gpu_count',1)>1: confidence_reasons.append(f"aggregated telemetry from {gpu['gpu_count']} GPUs")
    if not ram.get('measured'): confidence_reasons.append('RAM telemetry unavailable')
    if not entry: confidence_reasons.append('no model selected')
    if not setup: confidence_reasons.append('current model configuration unavailable')
    if not hist: confidence_reasons.append('no matching historical measurements')
    if entry and _weights(entry) is None: confidence_reasons.append('model weight size unavailable')
    if not confidence_reasons: confidence_reasons.append('hardware, current configuration and matching history are available')
    return {'target_context':ctx,'profile':profile,'analysis_mode':'hardware + configuration + local history','model':entry.get('id') if entry else None,'hardware':gpu,'ram':ram,'weights_gib':_weights(entry),'current_config':setup,'recommended':best,'alternatives':[x for x in cands if x is not best][:4],'historical_evidence':hist,'confidence':confidence,'confidence_reasons':confidence_reasons,'evidence':{'gpu_measured':bool(gpu.get('measured')),'ram_measured':bool(ram.get('measured')),'configuration_loaded':bool(setup),'historical_samples':len(rows),'weights_measured':_weights(entry) is not None},'constraints':['expert cache headroom >= 3000 MiB','KV RAM <= 55% of available RAM','one Strata instance per GPU on this machine'],'note':'Static recommendation cross-checked with local history; run measured evaluation for an SLO decision.','apply_endpoint':'POST /api/config with recommended.config + restart'}
