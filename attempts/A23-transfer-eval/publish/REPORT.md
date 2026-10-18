Published A23 synthetic saved run at 2026-10-18T05:22:58.714540+00:00.

URL: http://127.0.0.1:8103/compare?run=a23-synthetic; evaluation: http://127.0.0.1:8103/evaluation.

All3 actual saved API results validated with gateway.Item and backend.DoneJob. They are done/no_violation with null labels. Expected labels are unknown; accuracy is unscored. Wall runtimes: t1.mp4 32.95s, t2.mp4 14.16s, t3.mp4 18.18s. Scene calibration is weak/missing; all9 safe checks were unknown. The configured local safe-only model is Qwen3-VL-4B-Instruct. No training/fine-tuning was performed. No mirror completion or A24 training claim is made.

Existing run files preserved byte-for-byte: state.a20-baseline-cached-replay.json: 42, state.live.json: 42, state.no-vlm-validated.json: 42, state.visual-verifier-v1.json: 42. Only new state.a23-synthetic.json, its sidecar and three persistent upload copies were created. Each uploaded video SHA matches its actual API input. evaluation.json retains original summary/clips and all baseline audit data; only A21 source provenance was corrected to 5fae84bc10415111a04b5982d156727ca80f788a and the A23 attempt report was added. Live state, annotations, descriptions, existing historical runs, jobs, services and credentials were not changed.

Timestamp limits: queued_at is inferred from accepted-response artifact mtime minus measured upload_s. started_at is accepted-response artifact mtime, not a measured server-start event. finished_at is actual result-file mtime. Gateway elapsed time therefore differs slightly from the separately recorded API wall runtime. No absolute server execution time is invented.

Checked: deployment flag present before publication;3 real Item/DoneJob validations; atomic new-file/idempotence/conflict assertions; preserved-file hashes; media-free GET /api/runs and compact saved run (3done/3no_violation/3null labels); video byte-range HTTP status and trace HTTP status only. Checks: [{"id": "a23-synthetic-01", "video_status": 206, "trace_status": 200}, {"id": "a23-synthetic-02", "video_status": 206, "trace_status": 200}, {"id": "a23-synthetic-03", "video_status": 206, "trace_status": 200}].

No frames/base64/video bytes or credentials appear in this report. The worker sandbox initially rejected publication with Errno30 on shared runtime/uploads before any file was written; the parent executes publication outside that sandbox.
