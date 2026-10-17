# ForteBank Datathon 26 — набор для проверки локальных VLM на NVIDIA Brev

## Что в архиве
```
forte_brev_kit/
├── START_HERE.md          ← этот файл
├── brev_kit/              ← скрипты, анкета, промпты, золотые данные, кодекс норм (подробно — brev_kit/README.md)
├── videos/                ← 42 видео датасета (X-1.mov … X-48.mov; X-47 = X-4, X-48 = X-5 — скрипты их пропускают)
├── labels/open_labels.xlsx← исходная разметка организаторов (метки уже перенесены в brev_kit/data/)
└── research/              ← таблица норм (codex_norms.xlsx), таблица нарушений, архитектура
```
Имена видео переведены на латиницу: `X-12.mov` вместо кириллической `Х-12.mov`, чтобы не было проблем с распаковкой на Linux. Скрипты понимают оба варианта.

## Быстрый старт на машине Brev
```bash
unzip forte_brev_kit.zip && cd forte_brev_kit/brev_kit
bash setup_brev.sh Qwen/Qwen3.5-9B             # ffmpeg, vLLM, веса модели (один раз)

# терминал 1 (tmux) — сервер модели ТОЛЬКО на localhost
source ~/venv/bin/activate
vllm serve ~/models/Qwen3.5-9B --served-model-name Qwen/Qwen3.5-9B --host 127.0.0.1 --port 8000 \
     --max-model-len 16384 --gpu-memory-utilization 0.90 --limit-mm-per-prompt '{"image": 4}'

# терминал 2 — кадры и этапы проверки
source ~/venv/bin/activate
python scripts/extract_frames.py --videos ../videos --out work/gold_frames --gold data/gold_states.csv
python scripts/extract_frames.py --videos ../videos --out work/frames --fps 2

# этап 1: точность анкеты на золотых кадрах
python scripts/run_vlm.py --gold-frames work/gold_frames/gold_frames.json --model Qwen/Qwen3.5-9B --out runs/q35_9b_gold
python scripts/eval_states.py --pred runs/q35_9b_gold/states --gold data/gold_states.csv --out runs/q35_9b_gold/report_states.md

# этап 2: все видео → правила → метрики как у жюри
python scripts/run_vlm.py --frames work/frames --model Qwen/Qwen3.5-9B --out runs/q35_9b --step 1.0 --workers 8
python scripts/timeline_rules.py --states runs/q35_9b/states --out runs/q35_9b/violations
python scripts/eval_videos.py --violations runs/q35_9b/violations --run-meta runs/q35_9b/run_meta.json --out runs/q35_9b/report_videos.md
```
Этапы 3–5 (проверка кандидатов, новые типы, скорость, свои ролики), цели по метрикам и таблица результатов — в `brev_kit/README.md`.

## Проверка без GPU (у себя на ноутбуке)
```bash
cd brev_kit
python tests/mock_vlm_server.py &                              # заглушка сервера на localhost:8000
python scripts/run_vlm.py --gold-frames work/gold_frames/gold_frames.json --model mock --out runs/mock
python tests/make_fixture_states.py tests/fx && python scripts/timeline_rules.py --states tests/fx --out tests/fxv
```

## Обязательно
- **Только локальные модели.** Никаких облачных AI-API, в том числе размещённых NVIDIA NIM / build.nvidia.com: за это дисквалификация.
- **Только лицензии Apache-2.0 или MIT.** Нельзя YOLO/Ultralytics и Qwen2.5-VL-3B.
- **Данные — только для хакатона.** После хакатона удалить видео с машины Brev.
- **Бюджет почасовой.** Останавливайте машину, когда она не работает. Пороги правил подбираются без GPU, по сохранённым `runs/*/states`.
