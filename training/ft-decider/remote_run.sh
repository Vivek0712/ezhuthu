#!/bin/bash
# Unattended: base VAL score, two LR variants (1 epoch over choice3+noul TRAIN), VAL score of every checkpoint.
cd /root/ft
export HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1
B=/root/.cache/huggingface/hub/models--StrandsAgents--strands-decider-2B-qwen3.5-v1-2610/snapshots/216d1ccb46a9e9b036eb9187b248db98480f77d4
T1='{"choice":1.0,"noul":1.0}'
VAL="data/val.choice3.jsonl data/val.noul.jsonl"
mkdir -p scores runs
python ft_decider.py score --device cuda --ckpt $B --temps "$T1" --out scores/base.val.jsonl $VAL > logs_base_score.log 2>&1
for V in A:5e-5:5e-4 B:1e-4:1e-3; do
  IFS=: read name lr hlr <<< "$V"
  python ft_decider.py train --device cuda --ckpt $B --train data/train.choice3.jsonl data/train.noul.jsonl \
    --out runs/$name --lr $lr --head-lr $hlr --accum 16 --epochs 1 --save-at 145,290,435 --grad-ckpt --seed 0 \
    > logs_train_$name.log 2>&1
  for c in runs/$name/checkpoint-*; do
    python ft_decider.py score --device cuda --ckpt $c --temps "$T1" --out scores/$name-$(basename $c).val.jsonl $VAL \
      > logs_score_$name-$(basename $c).log 2>&1
  done
done
touch DONE
