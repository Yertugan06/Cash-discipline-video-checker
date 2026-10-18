# Owner D2-1: native-source small-object recognition

Own `backend/f1/perception.py`, new `backend/f1/object_refinement.py` if useful, associated new
tests `tests/test_object_refinement.py`, and `attempts/A21-deadline/recognition/` only.
Do not edit detector.py, rules.py, events.py, config, knowledge or other worker files.

Deliver a SMALL runnable fixed-input comparison using existing A13 labels: current full+desk
processing versus label-independent overlapping native-source crops/tiles and optionally short
temporal inputs. First compare OWLv2 within the same model; separate any local Qwen3-VL-4B
comparison. Current OWLv2 resizes to640. Inspect Models.objects and remapping carefully. Crop
geometry must be general across cameras, never fixed to known cash locations. Full-frame label
truth applies to union outputs, not each crop; sequence asks about the central frame.

The first goal is genuine TP improvement without declaring ID/phone/desk texture to be cash.
No object boxes are gold: report localization limits rather than claiming an oracle ceiling.
Avoid large rewrites, novel trackers, background blobs or deployment changes. A conservative
opt-in refinement hook is acceptable only after a real comparison; otherwise return the measured
diagnostic and keep current runtime unchanged. Do not make unmeasured improvements default.

Find cached weights locally. A13 frames/gold are in attempts/A13-detection-spike/scripts/spike_test.py
and logs; videos under ~/data/open/videos. Use actual local inference, never cloud image tools.
If sandbox blocks GPU, write a directly runnable script with CLI, a `gpu-command.json` argv list,
and progress marker GPU_RUN_READY promptly, then run CPU tests. Orchestrator executes GPU commands.
Do not wait until the end to provide a runnable probe. Target first script within20min.

Report TP/FP/FN/TN/unknown separately per class/variant, invalid outputs, inference time, model
revision and input sizes. Include clean negatives. No claims from an imported historical score.
