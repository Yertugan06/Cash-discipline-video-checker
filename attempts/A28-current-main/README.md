# Current main validation and resource log

Application source: `653b09c`, datathon2, one checker. UI: http://localhost:8105/.
Actual current-profile results: http://localhost:8103/?run=a28-main-vlm90.
Performance controls: http://localhost:8103/?run=a28-performance-controls.

`performance.jsonl` is the single CPU/RAM/GPU/VRAM log. Samples use UTC and a
two-second interval. Its final `final_api_window_summary` uses accepted/result
artifact timestamps to exclude idle time from workload averages. Earlier phase
averages include time after responses; use the final API-window summaries.
Checker CPU uses100% per core; system CPU is normalized across the VM. RSS sums
include shared/mapped pages and differ from system RAM usage. GPU values are
VM-wide; each GPU process has an ownership flag. Peaks are observed samples.

Both40-video actual API passes agree on30/40 (TP11/TN19/FN10/FP0), using unchanged
cached detections. These are public development clips, not unseen or cold40
accuracy. All12 returned findings have structured citation fields and m:ss
observations;36 evidence JPEGs were validated on the VM. No image bytes were
exported.48 focused backend tests,23 gateway tests,4 frontend test files, build,
and the Russian/English browser demo check passed.

The first cold X21 mirror ran72.77s but all8 safe checks hit the45s request limit.
The runtime now permits90s per request within the same90s total visual budget.
The restart/bootstrap recheck used cached perception and warmer OS files:20.15s,
15 uncached visual checks, no warnings. This is not proof of a completely cold
disk-cache startup. The additional X20 mirror used fresh perception with the VLM
already resident:29.58s,10 uncached visual checks, no warnings. Its actual verdict
remains `no_violation` despite the violation label; execution success is not a
detection improvement.

For that fresh-CV/warm-VLM window, system CPU averaged27.0% (peak40.0%); GPU
averaged23.5% (peak69%); observed VRAM peak11024MiB and system RAM peak4807.5MiB.
All failure and success measurements remain in the same log. The existing
`attempts/A23-transfer-eval/boot_checker.py` accepts `--visual-request-timeout 90`;
its default remains45s.
