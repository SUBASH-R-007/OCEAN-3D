"""Summarize assessor-scored paired trials; practice, unscored and unmatched trials are excluded."""
import argparse
import json
from pathlib import Path
import statistics


def summarize(documents):
    groups={};excluded=0
    for document in documents:
        if document.get('schema')!='ocean3d-evaluation-session-1':raise ValueError('Unsupported evaluation session.')
        for trial in document['trials']:
            if trial.get('condition') not in ('ocean3d','usual-workflow') or type(trial.get('score')) is not int or trial['score'] not in (0,1):excluded+=1;continue
            if type(trial.get('elapsed_seconds')) not in (int,float) or not 0<trial['elapsed_seconds']<86400:raise ValueError('Invalid trial duration.')
            key=(trial['participant'],trial['task_id'])
            pair=groups.setdefault(key,{})
            if trial['condition'] in pair:raise ValueError('Duplicate participant/task/condition; predeclare how repeated trials are handled.')
            pair[trial['condition']]=trial
    pairs=[p for p in groups.values() if set(p)=={'ocean3d','usual-workflow'}]
    return dict(paired_tasks=len(pairs),participants=len({key[0] for key,value in groups.items() if set(value)=={'ocean3d','usual-workflow'}}),
        excluded_practice_or_unscored=excluded,unpaired_tasks=len(groups)-len(pairs),
        correct={c:sum(p[c]['score'] for p in pairs) for c in ('ocean3d','usual-workflow')},
        median_time_difference_seconds=statistics.median(p['ocean3d']['elapsed_seconds']-p['usual-workflow']['elapsed_seconds'] for p in pairs) if pairs else None,
        interpretation='Descriptive paired task results only. Negative time difference means faster with Ocean3D. Repeated tasks within a participant are not independent; no significance, operational skill or population-wide benefit is inferred.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('sessions',type=Path,nargs='+');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=summarize([json.loads(path.read_text(encoding='utf-8')) for path in args.sessions])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
