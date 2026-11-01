# Live wiring smoke (2026-11-01T19:59:40+00:00)

> Synthetic fixture inputs. This proves the wiring (Bedrock via Strands, Strands Decider, Graph + Swarm); it is **not** a quality measurement and must not be cited as one.

- Bedrock model calls: 0 (cap 6)
- Decider: strands-decider-2B-qwen3.5-v1-2610

- Note: Bedrock invocations this wave (CloudWatch AWS/Bedrock Invocations, 2026-11-01 19:57-19:58 UTC): Sonnet 4.6 = 3, Opus 4.6 = 1; total 4 (cap 6).
- Note: Sonnet call 1 and Opus call 1 are the restore_gap steps below (responses replayed here from the .cache/llm entries they wrote; 0 new calls in this regeneration).
- Note: Sonnet calls 2-3: tutor_team Swarm, first tutor turn, in two attempts. Both stopped with MaxTokensReachedException at max_tokens=700 (CloudWatch OutputTokenCount 700 each) while writing a long handoff_to_agent message; the Graph fell back to the template explanation. Fix: max_tokens=2000 and a prompt telling the tutor to hand off only its draft JSON. A live Swarm re-run needs >= 3 turns, which would exceed this wave's 6-call cap, so it is deferred to wave 2.
- Note: The first attempt also crashed after the Swarm step on UsageLedger.to_dict (dataclasses.asdict deep-copied a threading.Lock); fixed and regression-tested.

## restore_gap router=sonnet

```json
{
 "step": "restore_gap router=sonnet",
 "input": {
  "left": "mahādēvarkku nantā viḷakku ",
  "right": " vaitta āṭu toṇṇūṟu",
  "gap_chars": 7
 },
 "decision": "abstain",
 "decider_model": "strands-decider-2B-qwen3.5-v1-2610",
 "models_used": [
  "us.anthropic.claude-sonnet-4-6",
  "strands-decider-2B-qwen3.5-v1-2610"
 ],
 "top": [
  {
   "text": "oṉṟukku",
   "confidence": 0.491,
   "model": "sonnet",
   "sources": [
    "ngram",
    "parallel",
    "sonnet"
   ]
  },
  {
   "text": "nāṟpatu",
   "confidence": 0.1488,
   "model": "retrieval",
   "sources": [
    "ngram"
   ]
  },
  {
   "text": "oṉṟu",
   "confidence": 0.1357,
   "model": "sonnet",
   "sources": [
    "parallel",
    "sonnet"
   ]
  },
  {
   "text": "iraṇṭukku",
   "confidence": 0.087,
   "model": "sonnet",
   "sources": [
    "parallel",
    "sonnet"
   ]
  },
  {
   "text": "nālukku",
   "confidence": 0.0174,
   "model": "sonnet",
   "sources": [
    "sonnet"
   ]
  }
 ],
 "wall_ms": 813
}
```

## restore_gap router=opus

```json
{
 "step": "restore_gap router=opus",
 "input": {
  "left": "kōvicaiya kampavarmaṟku yāṇṭu ",
  "right": "",
  "gap_chars": 9
 },
 "decision": "abstain",
 "decider_model": "strands-decider-2B-qwen3.5-v1-2610",
 "models_used": [
  "us.anthropic.claude-opus-4-6-v1",
  "strands-decider-2B-qwen3.5-v1-2610"
 ],
 "top": [
  {
   "text": "nālāvatu",
   "confidence": 0.3722,
   "model": "opus",
   "sources": [
    "opus",
    "parallel"
   ]
  },
  {
   "text": "irupattir",
   "confidence": 0.2207,
   "model": "retrieval",
   "sources": [
    "parallel"
   ]
  },
  {
   "text": "pattāvatu",
   "confidence": 0.1562,
   "model": "opus",
   "sources": [
    "opus"
   ]
  },
  {
   "text": "mūṉṟāvatu",
   "confidence": 0.0466,
   "model": "opus",
   "sources": [
    "ngram",
    "opus",
    "parallel"
   ]
  },
  {
   "text": "aintāvatu",
   "confidence": 0.0304,
   "model": "opus",
   "sources": [
    "opus"
   ]
  }
 ],
 "wall_ms": 610
}
```

## lesson graph (tutor_team swarm)

```json
{
 "step": "lesson graph (tutor_team swarm)",
 "skipped": "--skip-swarm"
}
```

Restore-path tokens: input {}, output {}; swarm tokens: {'input_tokens': 0, 'output_tokens': 0}. Estimated restore-path cost $0.0 (list prices).

Models: 
