# Запуск на ноутбуке с Windows + Ollama (модель работает локально, интернет нужен только для первого скачивания весов).
#   powershell -ExecutionPolicy Bypass -File run_local.ps1                         # этап 1: анкета на золотых кадрах, qwen3-vl:4b
#   powershell -ExecutionPolicy Bypass -File run_local.ps1 -Model qwen3.5:4b       # другая модель (нужна свежая Ollama)
#   powershell -ExecutionPolicy Bypass -File run_local.ps1 -Stage all              # + все видео → правила → метрики как у жюри
param(
  [string]$Model = "qwen3-vl:4b-instruct",
  [string]$Videos = "$PSScriptRoot\..\videos",
  [ValidateSet("gold", "all")][string]$Stage = "gold",
  [double]$Step = 2.0,
  [int]$MaxSide = 768,
  [int]$Workers = 2
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
foreach ($c in "ollama", "ffmpeg", "ffprobe", "python") {
  if (-not (Get-Command $c -ErrorAction SilentlyContinue)) { throw "Не найдено в PATH: $c" }
}

# 1) сервер Ollama на 127.0.0.1:11434
try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://127.0.0.1:11434/api/tags | Out-Null }
catch {
  Write-Host ">>> запускаю ollama serve"
  $env:OLLAMA_NUM_PARALLEL = "$Workers"
  Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
  Start-Sleep -Seconds 5
}
Write-Host ">>> Ollama: $(ollama --version)"

# 2) веса модели (один раз)
ollama pull $Model
python -m pip install -q pillow requests

# 3) этап 1 — анкета на золотых кадрах
if (-not (Test-Path "work\gold_frames\gold_frames.json")) {
  python scripts\extract_frames.py --videos $Videos --out work\gold_frames --gold data\gold_states.csv
}
$tag = ($Model -replace '[:./]', '_')
python scripts\run_vlm.py --gold-frames work\gold_frames\gold_frames.json --model $Model --structured ollama `
  --base-url http://127.0.0.1:11434 --out "runs\$($tag)_gold" --workers $Workers --max-side $MaxSide
python scripts\eval_states.py --pred "runs\$($tag)_gold\states" --gold data\gold_states.csv --out "runs\$($tag)_gold\report_states.md"

# 4) этап 2 — все видео (по желанию)
if ($Stage -eq "all") {
  if (-not (Test-Path "work\frames\X-1\frames.json")) {
    python scripts\extract_frames.py --videos $Videos --out work\frames --fps 2
  }
  python scripts\run_vlm.py --frames work\frames --model $Model --structured ollama --base-url http://127.0.0.1:11434 `
    --out "runs\$tag" --step $Step --workers $Workers --max-side $MaxSide
  python scripts\timeline_rules.py --states "runs\$tag\states" --out "runs\$tag\violations"
  python scripts\eval_videos.py --violations "runs\$tag\violations" --run-meta "runs\$tag\run_meta.json" --out "runs\$tag\report_videos.md"
}
Write-Host ">>> Готово. Отчёты: runs\$($tag)_gold\report_states.md" $(if ($Stage -eq "all") { "и runs\$tag\report_videos.md" })
