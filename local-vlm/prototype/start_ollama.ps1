# Локальный сервер Ollama для прототипа (GPU, 127.0.0.1:11434).
# 2 параллельных запроса, flash attention и сжатый KV-кэш — чтобы 4B-модель влезала в 6 ГБ видеопамяти.
$env:OLLAMA_HOST = "127.0.0.1:11434"
$env:OLLAMA_NUM_PARALLEL = "2"
$env:OLLAMA_FLASH_ATTENTION = "1"
$env:OLLAMA_KV_CACHE_TYPE = "q8_0"
$env:OLLAMA_KEEP_ALIVE = "30m"
ollama serve
