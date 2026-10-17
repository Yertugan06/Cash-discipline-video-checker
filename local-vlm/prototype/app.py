"""Локальный прототип сервиса: веб-интерфейс + API по ТЗ (раздел 10).

Запуск:  python -m uvicorn app:app --host 127.0.0.1 --port 8080
API:     POST /api/v1/analyze  (multipart, поле file, заголовок X-API-Key) → {"job_id": ...}
         GET  /api/v1/jobs/{job_id}  (X-API-Key) → {"job_id", "status": processing|done|failed, "verdict", "violations": [...]}
"""
import os, queue, secrets, threading, time, traceback, uuid

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import pipeline

HERE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(HERE, 'uploads'); os.makedirs(UPLOADS, exist_ok=True)
TRACES = os.path.join(HERE, 'traces'); os.makedirs(TRACES, exist_ok=True)     # трассы обработки (кадры с рамками) — только локально
KEY_FILE = os.path.join(HERE, 'api_key.txt')
API_KEY = os.environ.get('API_KEY') or (open(KEY_FILE).read().strip() if os.path.exists(KEY_FILE) else None)
if not API_KEY:
    API_KEY = secrets.token_urlsafe(24); open(KEY_FILE, 'w').write(API_KEY)
print(f'[prototype] API key: {API_KEY}  (файл {KEY_FILE})', flush=True)

app = FastAPI(title='Проверка кассовой дисциплины по видео', version='0.2')
app.mount('/traces', StaticFiles(directory=TRACES, html=True), name='traces')
JOBS: dict = {}
Q: 'queue.Queue[str]' = queue.Queue()
ALLOWED = ('.mov', '.mp4', '.m4v', '.avi', '.mkv', '.webm')


def worker():
    while True:
        jid = Q.get()
        job = JOBS[jid]
        job.update(status='processing', started=time.time())
        try:
            def progress(stage, frac):
                job.update(stage=stage, progress=round(frac, 3))
            result, debug = pipeline.analyze(job['path'], progress, trace_dir=os.path.join(TRACES, jid), video_name=job['filename'])
            job.update(status='done', result=result, debug=debug, progress=1.0, stage='Готово')
        except Exception as e:                                         # noqa: BLE001
            traceback.print_exc()
            job.update(status='failed', error=f'{type(e).__name__}: {e}', stage='Ошибка')
        finally:
            job['finished'] = time.time()
            try:
                os.remove(job['path'])                                # видео не храним после обработки
            except OSError:
                pass
            Q.task_done()


threading.Thread(target=worker, daemon=True).start()


def check_key(x_api_key):
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail='invalid or missing X-API-Key')


async def submit(file: UploadFile):
    ext = os.path.splitext(file.filename or '')[1].lower() or '.mov'
    if ext not in ALLOWED:
        raise HTTPException(status_code=400, detail=f'unsupported file type {ext}')
    jid = uuid.uuid4().hex[:12]
    path = os.path.join(UPLOADS, jid + ext)
    with open(path, 'wb') as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)
    JOBS[jid] = {'status': 'queued', 'stage': 'В очереди', 'progress': 0.0, 'path': path, 'filename': file.filename,
                 'created': time.time(), 'queue_pos': Q.qsize() + 1}
    Q.put(jid)
    return jid


def public(jid):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(status_code=404, detail='job not found')
    if job['status'] == 'done':
        return {'job_id': jid, 'status': 'done', **job['result']}
    if job['status'] == 'failed':
        return {'job_id': jid, 'status': 'failed', 'error': job.get('error')}
    return {'job_id': jid, 'status': 'processing'}


# ---------------- API для жюри ----------------
@app.post('/api/v1/analyze')
async def api_analyze(file: UploadFile = File(None), x_api_key: str = Header(None)):
    check_key(x_api_key)                      # сначала ключ: без ключа всегда 401, даже если нет файла
    if file is None:
        raise HTTPException(status_code=400, detail='multipart field "file" is required')
    return {'job_id': await submit(file), 'status': 'processing'}


@app.get('/api/v1/jobs/{job_id}')
def api_job(job_id: str, x_api_key: str = Header(None)):
    check_key(x_api_key)
    return public(job_id)


# ---------------- веб-интерфейс ----------------
@app.get('/')
def index():
    return FileResponse(os.path.join(HERE, 'static', 'index.html'))


@app.post('/ui/analyze')
async def ui_analyze(file: UploadFile = File(...)):
    return {'job_id': await submit(file)}


@app.get('/ui/jobs/{job_id}')
def ui_job(job_id: str):
    out = public(job_id)
    job = JOBS[job_id]
    out.update(stage=job.get('stage'), progress=job.get('progress'), filename=job.get('filename'), debug=job.get('debug'),
               trace_url=f'/traces/{job_id}/index.html' if pipeline.CFG['trace'] else None,
               elapsed_s=round((job.get('finished') or time.time()) - job.get('started', time.time()), 1) if job.get('started') else 0)
    return JSONResponse(out)


@app.get('/health')
def health():
    return {'ok': True, 'model': pipeline.CFG['model'], 'queue': Q.qsize()}
