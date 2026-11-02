#!/bin/bash
set -e
cd /root/ft
(command -v gcc >/dev/null) || (apt-get update -qq && apt-get install -y -qq gcc g++ >/dev/null)
pip install -q "strands-decider[cuda]==0.2.0" "transformers==5.22.1" "peft==0.21.2" 2>&1 | tail -3
python - <<'PY'
from huggingface_hub import snapshot_download as s
print(s('StrandsAgents/strands-decider-2B-qwen3.5-v1-2610', revision='216d1ccb46a9e9b036eb9187b248db98480f77d4'))
print(s('Qwen/Qwen3.5-2B-Base', revision='b1485b2fa6dfa1287294f269f5fb618e03d52d7c'))
import torch, transformers, peft
print(torch.__version__, transformers.__version__, peft.__version__, torch.cuda.get_device_name(0))
try:
    import fla; print('fla', fla.__version__)
except Exception as e: print('fla missing', e)
PY
echo SETUP_OK
