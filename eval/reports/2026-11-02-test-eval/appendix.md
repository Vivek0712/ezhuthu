## VAL vs TEST

The VAL choices did not all hold on TEST. On VAL (120-gap sample) the decider `noul-topk:3` beat self-report and
prerank on Sonnet candidates (0.1917 vs 0.1167 / 0.15); on TEST the decider and prerank are level. On full VAL the
5-gram baseline (0.2980) was already above copy (0.2415) and every retrieval strategy (best 0.2619). TEST has a much
larger share of single-letter gaps (68% vs 46%), so absolute numbers are not comparable across the two splits.
