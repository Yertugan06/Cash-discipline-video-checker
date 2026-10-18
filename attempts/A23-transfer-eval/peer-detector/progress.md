# Peer detector review D2-2

05:06 UTC initial source result: clone pin verified as 15d60a51fc5eebd6b91fff2b43866dd75dff13d7. No checkpoint is tracked or present in this clone; models/ contains only README.md. Its documented fine-tuned checkpoint is a local directory models/rtdetr_cashier, not a download URL. Checking public release/model metadata before concluding availability.

The actual builder has 17 classes and splits by video identifier. Exported annotations, split manifest and fine-tuned model config are absent. Training supports --all, which explicitly puts validation images in training. README/metrics cannot establish independent performance. No model/repo code executed, pixels inspected, GPU used, dependencies installed or production changed.

05:06 UTC public metadata result: GitHub releases=[], tags=[], license endpoint404; HF rtdetr_cashier search=[] and Hotel-zulu author=[]. README explicitly says the custom archive accompanies their submission; no archive URL. Transfer is BLOCKED, not GPU_RUN_READY. Published base is COCO80 only, pinned5650961749fa93567c0d46fc7f43ea4f9e914107, with model.safetensors; it is not the custom detector.

05:07 UTC first runnable CPU artifact: audit.py verified peer pin, extracted17class map with AST only, read77CSV epochs, and rescored our frozen20A13 numeric records. Cash TP/FN/TN/FP: OWL0/7/4/0; GDINO1/6/3/1; Qwen2.5VL0/7/4/0. ID TP/FN/TN/FP: OWL1/0/0/1; GDINO0/1/0/1; Qwen0/1/0/1. No neural inference occurred. Preparing report and fixed20-frame conditional plan; no framework or production hook.
