"""Заглушка OpenAI-совместимого сервера для проверки «трубы» без GPU (localhost:8000).
python tests/mock_vlm_server.py  → затем run_vlm.py --model mock ...
"""
import json, random
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = {"cashier_at_desk": True, "cashier_in_room": True, "people_cashier_side": 1, "clients_at_desk": 0, "person_at_door": False,
        "collector_present": False, "desk_cash": False, "desk_bag": False, "desk_documents": False, "desk_personal_items": False,
        "desk_food_drink": False, "phone_in_cashier_hand": False, "id_document_visible": False, "counting_machine_in_use": False,
        "detector_in_use": False, "safe_door": "closed", "key_in_safe_lock": "no", "laptop_screen": "unlocked", "room_door": "closed",
        "cash_in_hands_of": "nobody", "cashier_action": "working_on_laptop", "other": ""}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        native = self.path.startswith('/api/chat')                     # нативный API Ollama
        last = body['messages'][-1]
        n_img = len(last.get('images', [])) if native else sum(1 for c in last['content'] if c.get('type') == 'image_url')
        fmt = body.get('format') if native else (body.get('response_format') or {}).get('json_schema', {}).get('schema', {})
        props = fmt.get('properties', {}) if isinstance(fmt, dict) else {}
        if 'safe_box' in props:
            out = {"safe_found": True, "safe_box": [600, 300, 800, 500], "laptop_found": True, "laptop_box": [500, 350, 650, 450],
                   "door_found": True, "door_box": [0, 50, 300, 600]}
        elif 'key_in_lock' in props: out = {"safe_door": "closed", "key_in_lock": "yes"}
        elif 'screen' in props: out = {"screen": "lock_screen"}
        elif set(props) == {'door'}: out = {"door": "open"}
        elif 'answer' in props: out = {"answer": "yes", "evidence": "заглушка"}
        elif 'rule_id' in props: out = {"rule_id": "NONE", "evidence": "заглушка"}
        else:
            out = dict(BASE); out['desk_cash'] = random.random() < 0.2
        msg = {"role": "assistant", "content": json.dumps(out, ensure_ascii=False)}
        resp = {"message": msg, "done": True} if native else {"choices": [{"message": msg}], "usage": {"images": n_img}}
        data = json.dumps(resp).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def do_GET(self):                                                  # /v1/models (vLLM) и /api/tags (Ollama)
        data = json.dumps({"data": [{"id": "mock"}], "models": [{"name": "mock"}]}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def log_message(self, *a): pass


if __name__ == '__main__':
    print('mock VLM on http://localhost:8000/v1'); HTTPServer(('127.0.0.1', 8000), H).serve_forever()
