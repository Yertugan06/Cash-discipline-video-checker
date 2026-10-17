# brev_kit — проверка локальных VLM на NVIDIA Brev

**Цель.** Подобрать локальную VLM и пороги правил так, чтобы сервис:
- не пропускал нарушения;
- давал минимум ложных срабатываний;
- попадал в таймкод;
- укладывался в 5 минут на видео.

**Как устроен конвейер.**
- **Модель только описывает кадр.** Она заполняет анкету состояний ([FEATURES.md](FEATURES.md)).
- **Решение о нарушении принимает код.** Таймкод берётся из таймлайна, норма — из кодекса по ID.

```
видео → extract_frames.py → run_vlm.py (анкета) → timeline_rules.py (правила) → verify_candidates.py (да/нет)
      → other_to_codex.py (новые типы) → eval_videos.py (метрики как у жюри)
```

## 0. Правила игры (за нарушение — дисквалификация или минус баллы)
- **Только локально.** Модель крутится на арендованной машине внутри нашего сервиса.
  - Запрещено: облачные AI-API, в том числе размещённые NVIDIA NIM / build.nvidia.com, OpenAI, Gemini и т. п.
  - Скачать веса с Hugging Face один раз можно. Дальше сервер работает без сети.
- **Только лицензии с коммерческим использованием** (Apache-2.0 или MIT).
  - YOLO / Ultralytics (AGPL) — нельзя.
  - Qwen2.5-VL-**3B** — нельзя: лицензия qwen-research.
  - Таблица ниже проверена по карточкам Hugging Face на 17.10.2026.
- **Нельзя:** распознавать лица и использовать звук.
- **Данные** — только для хакатона. После хакатона удалить видео с машины Brev.
- **Бюджет $50, оплата почасовая.** Останавливайте машину, когда она не работает: состояния и кадры сохраняются на диске, правила можно подбирать без GPU.

## 1. Модели для теста (лицензии проверены на huggingface.co 17.10.2026)
| Роль | Модель (HF) | Лицензия | Комментарий |
|---|---|---|---|
| VLM, быстрая | `Qwen/Qwen3.5-4B` | Apache-2.0 | базовая точка, влезает в 24 ГБ |
| VLM, основная | `Qwen/Qwen3.5-9B` | Apache-2.0 | **кандидат №1**, 24–48 ГБ |
| VLM, альтернатива | `Qwen/Qwen3-VL-8B-Instruct` | Apache-2.0 | сравнить с Qwen3.5-9B |
| VLM, альтернатива | `OpenGVLab/InternVL3_5-8B` | Apache-2.0 | другая архитектура |
| VLM, крупная | `Qwen/Qwen3.6-35B-A3B-FP8` | Apache-2.0 | MoE (активно ~3B): быстрая для размера, нужна 48–80 ГБ |
| VLM, крупная | `Qwen/Qwen3.6-27B-FP8` | Apache-2.0 | плотная, 48–80 ГБ |
| VLM, маленькая | `Qwen/Qwen3-VL-2B-Instruct`, `Qwen/Qwen3.5-2B` | Apache-2.0 | если не успеваем по времени |
| Эмбеддинги (поиск по кодексу) | `BAAI/bge-m3` или `Qwen/Qwen3-Embedding-0.6B` | MIT / Apache-2.0 | для `other_to_codex.py` |
| Детекция (на потом) | `IDEA-Research/grounding-dino-base`, `google/owlv2-base-patch16-ensemble`, `microsoft/Florence-2-large`, `PekingU/rtdetr_v2_r50vd` | Apache-2.0 / MIT | зоны стола, сейфа, двери, люди |
| Сегментация (на потом) | `facebook/sam2.1-hiera-base-plus` | Apache-2.0 | кропы сейфа, двери, экрана |

Перед использованием всё равно откройте карточку модели и убедитесь, что лицензия не изменилась. Если vLLM не поддерживает архитектуру конкретной модели, возьмите другую из таблицы или SGLang.

## 2. Что передать на машину
1. Папку `brev_kit/` целиком (в ней уже лежат кодекс норм, золотые данные и скрипты).
2. Видео: `open/open/videos/*.mov` — 42 файла (40 уникальных: X-47 = X-4, X-48 = X-5) и `open/open/open_labels.xlsx` (для справки, метки уже в `data/`).

Копировать через `scp`/`rsync` по SSH: Brev создаёт SSH-доступ к инстансу. Можно и загрузкой через Jupyter, если он поднят.

## 3. Запуск на Brev
```bash
bash setup_brev.sh Qwen/Qwen3.5-9B          # ffmpeg, venv, vllm, веса
# терминал 1 (tmux): сервер модели на localhost
source ~/venv/bin/activate
vllm serve ~/models/Qwen3.5-9B --served-model-name Qwen/Qwen3.5-9B --host 127.0.0.1 --port 8000 \
     --max-model-len 16384 --gpu-memory-utilization 0.90 --limit-mm-per-prompt '{"image": 4}'
# терминал 2: кадры (один раз)
python scripts/extract_frames.py --videos ~/data/videos --out work/gold_frames --gold data/gold_states.csv
python scripts/extract_frames.py --videos ~/data/videos --out work/frames --fps 2
```
Проверить «трубу» без GPU можно у себя: `python tests/mock_vlm_server.py` и дальше те же команды с `--model mock`. Синтетические таймлайны для проверки правил: `python tests/make_fixture_states.py`.

## 4. Как проверять — по этапам
Для каждого запуска создавайте папку `runs/<модель>_<вариант>` и заносите результат в таблицу (раздел 5).

### Этап 1. Анкета на золотых кадрах (32 кадра, 56 проверок, минуты)
```bash
python scripts/run_vlm.py --gold-frames work/gold_frames/gold_frames.json --model Qwen/Qwen3.5-9B --out runs/q35_9b_gold
python scripts/eval_states.py --pred runs/q35_9b_gold/states --gold data/gold_states.csv --out runs/q35_9b_gold/report_states.md
```
- **Что смотреть:** точность по полям и список ошибок (кадр, поле, ожидалось, ответ модели).
- **Цель:** ≥ 90 % по критичным полям — `cashier_at_desk`, `desk_cash`, `desk_bag`, `safe_door`, `laptop_screen`, `room_door`, `people_cashier_side`, `clients_at_desk`.
- **`key_in_safe_lock`:** трудное поле (мелкий объект). Попробуйте `--max-side 1024` и `1280`.
- **Если поле стабильно ошибается:** уточните его определение в `prompts/questionnaire.txt` и сохраните как новую версию промпта (`--prompts prompts_v2/`).
- **Прогнать все модели из таблицы.** По итогам этапа оставить 1–2 лучших.

### Этап 2. Все 40 видео → правила → метрики как у жюри
```bash
python scripts/run_vlm.py --frames work/frames --model Qwen/Qwen3.5-9B --out runs/q35_9b --step 1.0 --workers 8
python scripts/timeline_rules.py --states runs/q35_9b/states --out runs/q35_9b/violations
python scripts/eval_videos.py --violations runs/q35_9b/violations --run-meta runs/q35_9b/run_meta.json --out runs/q35_9b/report_videos.md
```
- **Вердикт.** FN — пропуск, он недопустим. Цель: FN = 0 из 21, FP на чистых ≤ 2 из 19.
- **Таймкод.** Доля меток в ±1, ±3, ±5 с. Цель: ≥ 80 % в ±3 с.
- **ID нормы.** Совпадение с `expected_codex_ids`. Цель: ≥ 90 %.
- **Таблица «По меткам».** Здесь разбирайте каждый пропуск и ложное срабатывание:
  1. Откройте `runs/.../states/X-NN.jsonl` около этой секунды.
  2. Определите, кто ошибся — анкета (модель) или правило (порог).

**Подбор порогов — без GPU, по сохранённым состояниям:** `timeline_rules.py --params my_params.json`. Параметры перечислены в словаре `P` в начале файла: `min_away_s`, `leave_anchor` (`desk` или `room`), `safe_open_s`, `door_open_s`, `collector_quick_s` и др.

### Этап 3. Проверка кандидатов и открытый мир
```bash
python scripts/verify_candidates.py --violations runs/q35_9b/violations --frames work/frames --model Qwen/Qwen3.5-9B
python scripts/other_to_codex.py   --violations runs/q35_9b/violations --frames work/frames --model Qwen/Qwen3.5-9B --embedder ~/models/bge-m3
python scripts/eval_videos.py --violations runs/q35_9b/violations --only-verified --run-meta runs/q35_9b/run_meta.json
```
- **Цель проверки кандидатов:** FP падают, а FN не растут. Если проверка «убивает» настоящие нарушения, отключите её для этого правила.
- **Открытый мир:** посмотрите, что модель пишет в `other`, и какие ID нормы выбирает. Для кодекса это источник идей новых правил.

### Этап 4. Скорость (лимит жюри — 5 минут на видео)
- В `report_videos.md` смотрите раздел «Скорость»: среднее время и худшее видео. Самое длинное — X-14, 142 с.
- **Цель:** худшее видео < 150 с вместе с проверкой.
- **Как ускорить:**
  - `--step 1.5` или `2.0`;
  - `--max-side 640`;
  - FP8-версия модели;
  - больше `--workers` (vLLM сам собирает запросы в батчи);
  - модель меньше.

  Каждое ускорение проверяйте на этапе 2: не появились ли FN.
- Учтите, что жюри может прислать несколько видео одновременно.

### Этап 5. Устойчивость
- Свои 10–20 роликов с телефона: другой угол и нарушения из листа «Новые типы» в `research/Кодекс_норм.xlsx`.
- Добавьте их метки в `data/gt_violations.csv` и `data/videos.csv`, затем прогоните этап 2.

## 5. Таблица результатов (заполнять после каждого запуска)
| Дата | Модель / квант | GPU | max_side | step | Промпт | Поля, крит. % | Вердикт % | FN | FP чист. | ±3 с | ID нормы | с/видео ср/макс | $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | v1 | | | | | | | | |

## Файлы
- `schema/questionnaire_v1.json` — схема анкеты; `prompts/` — промпты (анкета, проверка, выбор нормы).
- `data/gold_states.csv` — эталонные состояния 32 кадров (56 проверок, сверены по кадрам вручную).
- `data/gt_violations.csv` — 22 метки нарушений с допустимыми ID норм; `data/videos.csv` — список видео, сетапы, дубликаты.
- `codex/codex_verified.json` — 217 норм с дословными цитатами и ссылками на adilet (источник истины для норм).
- `scripts/` — конвейер; `tests/` — заглушка сервера и синтетические таймлайны.
