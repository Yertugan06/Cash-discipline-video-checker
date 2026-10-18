"""Validate eight actual runs, score allowlisted fields, stage a VM-private saved run."""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
from score import score

BASE = Path('/home/ubuntu/workspaces/datathon26-workers/shared/a23/base')
DATA = Path('/home/ubuntu/workspaces/datathon26-workers/shared/a23-mirrored')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from realtime.gateway import Item  # noqa: E402


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def private_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    path.chmod(0o600)


def prepare(out, originals=None):
    manifest=json.loads((HERE/'manifest.json').read_text())
    truth=json.loads((HERE/'scoring-truth.json').read_text())
    labels={c['file']:c['expected_verdict'] for c in truth['cases']}
    run=DATA/'api-newmain-run1'
    rows=[json.loads(line) for line in (run/'summary.jsonl').read_text().splitlines() if line.strip()]
    require(len(rows)==len(manifest['inputs'])==8, 'not ready: need exactly eight terminal rows')
    require(len({r['name'] for r in rows})==8, 'duplicate run input')
    pins=json.loads((run/'source-pins.json').read_text())
    for source in pins['source_pins']['files']:
        require(file_hash(BASE/source['path'])==source['sha256'], 'source pin mismatch')
    entries=[]; allowlisted={}; states=[]; provenance=[]
    for index,(row,expected) in enumerate(zip(rows,manifest['inputs'],strict=True),1):
        prefix=f'{index:02d}'; private=run/'privateRaw'
        video=DATA/'mirrored'/expected['file']
        raw_path=private/f'{prefix}-result.json'
        accepted_path=private/f'{prefix}-accepted.json'
        trace_path=private/f'{prefix}-trace.json'
        raw=json.loads(raw_path.read_text()); accepted=json.loads(accepted_path.read_text())
        trace=json.loads(trace_path.read_text())
        require(row['name']==expected['file'], f'input order mismatch at {prefix}')
        require(row['status']=='done' and raw['status']=='done', f'not done at {prefix}')
        require(row['verdict']==raw['verdict'], f'verdict mismatch at {prefix}')
        require(row['job_id']==raw['job_id']==accepted['job_id'], f'job mismatch at {prefix}')
        require(file_hash(video)==row['sha256']==expected['sha256']==trace['video_sha256'], f'video hash mismatch at {prefix}')
        cache=row['cache_provenance']
        require(cache['video_sha256']==expected['sha256'], f'cache video mismatch at {prefix}')
        require(cache['perception_cache_hit'] is False and trace['perception_cache_hit'] is False,
                f'perception not fresh at {prefix}')
        require(cache['visual_cache_hits']==0, f'visual cache not fresh at {prefix}')
        require(row['trace_status']=='available', f'trace unavailable at {prefix}')
        coverage=raw['coverage']
        require(coverage==row['coverage'], f'coverage mismatch at {prefix}')
        require(coverage['mode']=='full' and coverage['planned']>0 and coverage['done']==coverage['planned']
                and coverage['failed']==0 and coverage['deadline_hit'] is False, f'incomplete coverage at {prefix}')
        checks=trace.get('visual_checks',[])
        require(not any(c.get('cache_hit') is True for c in checks), f'raw visual cache hit at {prefix}')
        require(len(checks)==cache['visual_checks_count'], f'check count mismatch at {prefix}')
        unknown=sum(c.get('answer')=='unknown' for c in checks)
        allowlisted[row['name']]={'status':'done','verdict':raw['verdict'],'runtime_s':row['runtime_s'],
            'unknown_count':unknown,'violations':[{'rule_id':v['rule_id'],'timecode_sec':v['timecode_sec']} for v in raw['violations']]}
        finished=raw_path.stat().st_mtime
        started=finished-row['runtime_s']
        queued=min(started,accepted_path.stat().st_mtime-row['upload_s'])
        identity=f'a23-mirrored-{prefix}'
        item={'id':identity,'name':row['name'],'source':'upload','status':'done','job_id':raw['job_id'],
              'verdict':raw['verdict'],'label':labels[row['name']],'error':None,'queued_at':queued,
              'started_at':started,'finished_at':finished,'result':raw}
        try:
            validated=Item.model_validate(item).model_dump()
        except Exception:
            raise ValueError(f'gateway Item validation failed at {prefix}') from None
        require(validated['result']==raw, f'raw result modified at {prefix}')
        states.append(validated); entries.append((video,trace_path,identity,raw['job_id']))
        provenance.append({'id':identity,'file':row['name'],'video_sha256':expected['sha256'],
            'result_sha256':file_hash(raw_path),'trace_sha256':file_hash(trace_path),
            'accepted_file_mtime':accepted_path.stat().st_mtime,'result_file_mtime':finished,
            'runtime_s':row['runtime_s'],'coverage':coverage,'perception_cache_hit':False,
            'visual_cache_hits':0,'visual_checks':len(checks),'unknown_checks':unknown})
    source=json.loads(originals.read_text()) if originals else {}
    scored=score(manifest,truth,allowlisted,source)
    require(scored['accuracy_denominator']==8 and not scored['excluded'], 'not all eight scoreable')
    require(not out.exists(), 'publication directory already exists')
    out.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix=out.name+'.partial-',dir=out.parent))
    realtime=temporary/'realtime'; uploads=realtime/'uploads'; traces=temporary/'traces'
    for directory in [temporary,realtime,uploads,traces]:
        directory.mkdir(mode=0o700,parents=True,exist_ok=True); directory.chmod(0o700)
    for video,trace,identity,job in entries:
        destination=uploads/f'{identity}.mov'; shutil.copyfile(video,destination); destination.chmod(0o600)
        require(file_hash(video)==file_hash(destination), 'upload copy mismatch')
        destination=traces/f'{job}.json'; shutil.copyfile(trace,destination); destination.chmod(0o600)
        require(file_hash(trace)==file_hash(destination), 'trace copy mismatch')
    private_json(realtime/'state.a23-mirrored.json',states)
    private_json(realtime/'state.a23-mirrored.meta.json',{'attempt_prefix':'A23',
        'title':'Mirrored subset — 8 fresh API runs','source_commit':'4a3b9ea'})
    metadata={'source_commit':'4a3b9ea','source_commit_provenance':'parent supplied; matching pinned local source; server commit not exposed by API',
        'source_summary_sha256':file_hash(run/'summary.jsonl'),'source_pins_sha256':file_hash(run/'source-pins.json'),
        'timestamp_derivation':'approximate: finish=result file mtime; start=finish-reported runtime; queued=min(start,accepted file mtime-upload_s)',
        'gateway_Item_validated':8,'video_byte_copies_verified':8,'untouched_trace_copies_verified':8,
        'publication_target_requested':str(DATA/'publication'),'actual_staging_directory':str(out),
        'published_on_8103':False,'score':scored,'provenance':provenance,
        'original_comparison':'explicit source export supplied' if originals else 'not available; historical 32/40 and 29/40 outputs not substituted for requested 30/40',
        'limits':'Derived public development hflips; not held-out/new-angle. Expected CSV norms/reasons unverified. Raw media/results remain VM-private.'}
    private_json(temporary/'metadata.json',metadata)
    os.rename(temporary,out)
    private_json(HERE/'allowlisted-mirror-results.json',allowlisted)
    private_json(HERE/'score.json',scored)
    print(json.dumps({'bundle':str(out),'validated_items':8,'accuracy':scored['accuracy'],
        'confusion':scored['confusion'],'runtime':scored['runtime'],'unknown_checks':scored['unknown_count_total_known']}))
    return scored,metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--originals',type=Path)
    args=parser.parse_args()
    try:
        prepare(args.out,args.originals)
    except Exception as exc:
        # Never print validation input or private raw data.
        print(json.dumps({'status':'not_published','error_type':type(exc).__name__,
                          'reason':str(exc) if isinstance(exc,ValueError) else 'private filesystem/import failure'}))
        return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
