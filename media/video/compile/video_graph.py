"""Build the ffmpeg filtergraph that joins the 22 rendered scene clips into the 180.000 s picture track.

Scene clips (ezhuthu-video/scenes/<id>.mp4) are rendered to their exact storyboard windows. A dissolve of D frames
at a boundary would normally shorten the film by D frames, so each side of a dissolve is padded by D/2 frames
(tpad clone: a held frame, invisible under the dissolve) before xfade. Net length is unchanged and every cut stays
on its storyboard time, which keeps picture and narration in sync.

Usage: python3 video_graph.py STORYBOARD_JSON SCENES_DIR OUT_GRAPH OUT_INPUTS
"""
import json
import sys

FPS = 30

# Boundary transitions, keyed by the id of the scene that ENDS at the boundary.
# (xfade transition, frames). frames must be even. Missing key = hard cut / match cut.
TRANSITIONS = {
    "a1-01-cold-open": ("fade", 12),         # stone macro -> Madurai aerial
    "a1-02-place": ("fade", 16),             # M1 -> M2 crossfade at 14.0
    "a1-04-damage": ("fade", 12),            # Shore Temple -> Arachalur documentation
    "a1-06-slow": ("fade", 18),              # the lamp glow carries into the title
    "a2-07-title": ("fade", 14),             # title -> live hero
    "a2-09-practice": ("smoothleft", 10),    # whip-pan right into Restore
    "a2-11-restore-open": ("fade", 18),      # the '?' becomes the first pipeline node
    "a4-19-who": ("fade", 14),               # people -> proof
    "a4-21-knows": ("fade", 20),             # 'it knows' -> close, back in Madurai
    # a3-12 .. a3-18: match cuts along the pipeline spine; a3-18 -> a4-19: hard cut on the 145.0 downbeat.
}


def main(sb_path, scenes_dir, out_graph, out_inputs):
    scenes = json.load(open(sb_path))
    inputs, chains = [], []
    n = len(scenes)
    for i, s in enumerate(scenes):
        inputs.append(f"{scenes_dir}/{s['id']}.mp4")
        frames = round(s["duration_s"] * FPS)
        pre = TRANSITIONS.get(scenes[i - 1]["id"], (None, 0))[1] // 2 if i > 0 else 0
        post = TRANSITIONS.get(s["id"], (None, 0))[1] // 2 if i < n - 1 else 0
        f = (f"[{i}:v]trim=end_frame={frames},setpts=PTS-STARTPTS,fps={FPS},"
             f"scale=in_range=full:out_range=limited:in_color_matrix=bt709:out_color_matrix=bt709,"
             f"format=yuv420p,setsar=1")
        if pre or post:
            f += f",tpad=start={pre}:start_mode=clone:stop={post}:stop_mode=clone"
        chains.append(f + f",settb=1/{FPS}[s{i}]")
    # chain
    cur, cur_len = "s0", None
    lens = []
    for i, s in enumerate(scenes):
        frames = round(s["duration_s"] * FPS)
        pre = TRANSITIONS.get(scenes[i - 1]["id"], (None, 0))[1] // 2 if i > 0 else 0
        post = TRANSITIONS.get(s["id"], (None, 0))[1] // 2 if i < n - 1 else 0
        lens.append(frames + pre + post)
    cur_len = lens[0]
    for i in range(1, n):
        prev_id = scenes[i - 1]["id"]
        out = f"j{i}"
        if prev_id in TRANSITIONS:
            kind, d = TRANSITIONS[prev_id]
            off = (cur_len - d) / FPS
            chains.append(f"[{cur}][s{i}]xfade=transition={kind}:duration={d / FPS:.6f}:offset={off:.6f},settb=1/{FPS}[{out}]")
            cur_len = cur_len - d + lens[i]
        else:
            chains.append(f"[{cur}][s{i}]concat=n=2:v=1:a=0,settb=1/{FPS}[{out}]")
            cur_len = cur_len + lens[i]
        cur = out
    total = round(sum(s["duration_s"] for s in scenes) * FPS)
    assert cur_len == total, (cur_len, total)
    chains.append(f"[{cur}]trim=end_frame={total},setpts=PTS-STARTPTS[vout]")
    open(out_graph, "w").write(";\n".join(chains) + "\n")
    open(out_inputs, "w").write("\n".join(inputs) + "\n")
    print(f"graph: {n} scenes, {total} frames ({total / FPS:.3f} s), {len(TRANSITIONS)} dissolves")


if __name__ == "__main__":
    main(*sys.argv[1:5])
