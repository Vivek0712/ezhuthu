#!/usr/bin/env bash
# Ezhuthu film, audio v2: build stems + premix, two-pass loudnorm to -14 LUFS / < -1 dBTP, verify, export preview.
#
#   bash media/video/audio-v2/mix-v2.sh            # mix from the existing narration-v2.wav
#   RESYNTH=1 bash media/video/audio-v2/mix-v2.sh  # first re-render the narration with Amazon Polly (heisenberg)
#
# Output: /Users/vivekrajaps/tamil-script/ezhuthu-video/audio-v2/soundtrack-v2.wav (48 kHz, stereo, 24-bit,
#         exactly 8,640,000 samples = 180.000 s) and preview-opening.mp3 (first 30 s).
# Reads (never writes) media/video/storyboard.json and ezhuthu-video/audio/sfx.wav (v1 SFX stem).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT=/Users/vivekrajaps/tamil-script/ezhuthu-video/audio-v2
TOOLS="$HERE/tools"
mkdir -p "$OUT/check"

if [[ "${RESYNTH:-0}" == "1" ]]; then
  (cd "$TOOLS" && python3 synth_v2.py Arjun generative --lang en-IN --final)
fi

# 1. stems + premix (narration, ambience, music, bells, v1 SFX; envelope ducking under speech)
(cd "$TOOLS" && python3 build_v2.py)
PRE="$OUT/stems/premix.wav"

# 2. loudnorm pass 1 (measure)
TARGET_I=-14; TARGET_TP=-1.5; TARGET_LRA=11
M=$(ffmpeg -hide_banner -nostats -i "$PRE" -af "loudnorm=I=$TARGET_I:TP=$TARGET_TP:LRA=$TARGET_LRA:print_format=json" -f null - 2>&1 \
    | sed -n '/^{/,/^}/p')
echo "$M" > "$OUT/check/loudnorm-pass1.json"
get() { echo "$M" | python3 -c "import json,sys;print(json.load(sys.stdin)['$1'])"; }
MI=$(get input_i); MTP=$(get input_tp); MLRA=$(get input_lra); MTH=$(get input_thresh); OFF=$(get target_offset)
echo "pass1: I=$MI LUFS TP=$MTP dBTP LRA=$MLRA"

# 3. loudnorm pass 2 (apply, linear when possible), back to 48 kHz, pad/trim to exactly 180.000 s
ffmpeg -hide_banner -v error -y -i "$PRE" -af \
  "loudnorm=I=$TARGET_I:TP=$TARGET_TP:LRA=$TARGET_LRA:measured_I=$MI:measured_TP=$MTP:measured_LRA=$MLRA:measured_thresh=$MTH:offset=$OFF:linear=true:print_format=summary,aresample=48000,apad=whole_len=8640000,atrim=end_sample=8640000" \
  -ar 48000 -ac 2 -c:a pcm_s24le "$OUT/soundtrack-v2.wav"

# 4. verify
echo "--- ffprobe"
ffprobe -v error -show_entries stream=sample_rate,channels,codec_name,duration_ts:format=duration -of compact "$OUT/soundtrack-v2.wav"
echo "--- ebur128"
ffmpeg -hide_banner -nostats -i "$OUT/soundtrack-v2.wav" -af ebur128=peak=true+sample -f null - 2>&1 \
  | sed -n '/Summary:/,$p' | tee "$OUT/check/ebur128.txt"
(cd "$TOOLS" && python3 verify_v2.py)

# 5. preview (opening 30 s) + spectrograms
ffmpeg -hide_banner -v error -y -i "$OUT/soundtrack-v2.wav" -t 30 -af "afade=t=out:st=28.5:d=1.5" \
  -c:a libmp3lame -b:a 192k "$OUT/preview-opening.mp3"
ffmpeg -hide_banner -v error -y -i "$OUT/soundtrack-v2.wav" -lavfi "showspectrumpic=s=1800x600:legend=1:fscale=log:mode=combined" "$OUT/check/spectrogram-full.png"
ffmpeg -hide_banner -v error -y -i "$OUT/stems/bed.wav" -lavfi "showspectrumpic=s=1800x600:legend=1:fscale=log:mode=combined" "$OUT/check/spectrogram-bed.png"
ffmpeg -hide_banner -v error -y -t 30 -i "$OUT/soundtrack-v2.wav" -lavfi "showspectrumpic=s=1800x600:legend=1:fscale=log:mode=combined" "$OUT/check/spectrogram-opening.png"
echo "done: $OUT/soundtrack-v2.wav  $OUT/preview-opening.mp3"
