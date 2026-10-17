"""Общие функции для brev_kit: ID видео, загрузка схемы/кодекса/промптов, вызов локального OpenAI-совместимого сервера (vLLM/SGLang)."""
import base64, io, json, os, re, time, urllib.request, urllib.error

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def video_id(name: str) -> str:
    """'Х-12.mov' (кириллица) / 'X-12.mov' / 'x12' -> 'X-12'."""
    m = re.search(r'(\d+)', os.path.basename(name))
    return f'X-{int(m.group(1))}' if m else os.path.splitext(os.path.basename(name))[0]


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_schema(path=None):
    return load_json(path or os.path.join(KIT, 'schema', 'questionnaire_v1.json'))


def load_prompt(name, prompts_dir=None):
    with open(os.path.join(prompts_dir or os.path.join(KIT, 'prompts'), name), encoding='utf-8') as f:
        return f.read()


def load_codex(path=None):
    rows = load_json(path or os.path.join(KIT, 'codex', 'codex_verified.json'))
    return {r['id']: r for r in rows}


def image_to_data_url(path, max_side=768, quality=90):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    if max_side and max(im.size) > max_side:
        k = max_side / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=quality)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def chat_ollama(base_url, model, system, user_text, image_paths, schema, max_side, temperature, max_tokens, timeout):
    """Нативный API Ollama (/api/chat): format = JSON-схема, think = false. Так же модель будет работать на ноутбуках."""
    root = re.sub(r'/v1/?$', '', base_url.rstrip('/'))
    imgs = [image_to_data_url(p, max_side).split(',', 1)[1] for p in image_paths]
    body = {'model': model, 'stream': False, 'think': False, 'format': schema if schema is not None else 'json',
            'options': {'temperature': temperature, 'num_predict': max_tokens, 'num_ctx': 8192},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user_text, 'images': imgs}]}
    try:
        resp = _post(root + '/api/chat', body, {}, timeout)
    except urllib.error.HTTPError as e:
        if e.code == 400 and b'think' in e.read():          # модель без режима рассуждений — повтор без флага
            body.pop('think'); resp = _post(root + '/api/chat', body, {}, timeout)
        else:
            raise
    return resp['message'].get('content') or ''


def chat(base_url, model, system, user_text, image_paths, schema=None, structured='json_schema',
         max_side=768, temperature=0.0, max_tokens=500, api_key='EMPTY', timeout=120):
    """Один запрос к ЛОКАЛЬНОМУ серверу. structured: json_schema / guided_json (vLLM, SGLang — http://127.0.0.1:8000/v1),
    ollama (Ollama — http://127.0.0.1:11434), none. Возвращает (parsed_json|None, raw_text, latency_s, error)."""
    if structured == 'ollama':
        t0 = time.time()
        try:
            raw = chat_ollama(base_url, model, system, user_text, image_paths, schema, max_side, temperature, max_tokens, timeout)
        except urllib.error.HTTPError as e:
            return None, '', time.time() - t0, f'HTTP {e.code}: {e.read()[:300]!r}'
        except Exception as e:
            return None, '', time.time() - t0, f'{type(e).__name__}: {e}'
        obj = parse_json(raw)
        return obj, raw, time.time() - t0, None if obj is not None else 'not JSON'
    content =[{'type': 'image_url', 'image_url': {'url': image_to_data_url(p, max_side)}} for p in image_paths]
    content.append({'type': 'text', 'text': user_text})
    body = {'model': model, 'temperature': temperature, 'max_tokens': max_tokens,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}]}
    if schema is not None and structured == 'json_schema':
        body['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'out', 'schema': schema, 'strict': True}}
    elif schema is not None and structured == 'guided_json':          # старые версии vLLM
        body['guided_json'] = schema
    req = urllib.request.Request(base_url.rstrip('/') + '/chat/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        return None, '', time.time() - t0, f'HTTP {e.code}: {e.read()[:300]!r}'
    except Exception as e:
        return None, '', time.time() - t0, f'{type(e).__name__}: {e}'
    lat = time.time() - t0
    raw = resp['choices'][0]['message'].get('content') or ''
    obj = parse_json(raw)
    return obj, raw, lat, None if obj is not None else 'not JSON'


def parse_json(raw):
    """JSON из ответа модели (снимает ```json-обёртку, ищет первый {...}). None, если не разобрать."""
    txt = re.sub(r'^```(?:json)?|```$', '', (raw or '').strip()).strip()
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r'\{.*\}', txt, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
        return None


def validate_state(state, schema):
    """Проверяет ответ по схеме анкеты (без внешних библиотек). Возвращает список ошибок."""
    errs = []
    props = schema['properties']
    for k in schema['required']:
        if k not in state:
            errs.append(f'missing {k}'); continue
        p, v = props[k], state[k]
        if p.get('type') == 'boolean' and not isinstance(v, bool): errs.append(f'{k} not bool')
        if p.get('type') == 'integer' and not (isinstance(v, int) and not isinstance(v, bool)): errs.append(f'{k} not int')
        if 'enum' in p and v not in p['enum']: errs.append(f'{k}={v!r} not in enum')
    return errs
