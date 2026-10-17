#!/usr/bin/env bash
# Usage: fetch_model.sh <hf_repo> <revision> <dest>. Resumable; verifies LFS sha256.
set -u; R=$1; REV=$2; D=$3; mkdir -p "$D"; cd "$D"
curl -s "https://huggingface.co/api/models/$R/tree/$REV" | python3 -c "import sys,json; [print(f['path'], f.get('lfs',{}).get('size', f.get('size')), f.get('lfs',{}).get('oid','-')) for f in json.load(sys.stdin) if f['type']=='file']" > .files
while read f n oid; do
  for i in $(seq 1 20); do s=$(stat -c %s "$f" 2>/dev/null || echo 0); [ "$s" -eq "$n" ] && break
    curl -sSL --speed-time 60 --speed-limit 100000 -C - -o "$f" "https://huggingface.co/$R/resolve/$REV/$f"; done
done < .files
awk '$3!="-" {print $3"  "$1}' .files | sha256sum -c 2>&1 | tail -5; echo FETCH_DONE
