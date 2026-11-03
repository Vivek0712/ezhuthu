#!/usr/bin/env bash
# 15 s teasers cut from the finished film (16:9 and a 9:16 reframe for LinkedIn), captions burned in.
# Called by ../compile.sh (stage "teaser"); needs $VID/ezhuthu-film.mp4.
#   seg 1  0.0 -  4.9  "These temple walls are written in Tamil. The letters are fading."
#   seg 2 47.1 - 53.7  the live hero reading the Thanjavur stone: letters, words, meaning
#   seg 3 172.1 - 176.2 lockup: "Ezhuthu. Let the stones speak again."
# 0.3 s dissolves + audio crossfades: 4.9 + 6.6 + 4.1 - 0.6 = 15.0 s.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VID="${VID:-/Users/vivekrajaps/tamil-script/ezhuthu-video}"
B="$VID/build/teaser"; mkdir -p "$B"
FILM="$VID/ezhuthu-film.mp4"
FONT="$VID/fonts/InstrumentSans.ttf"
PY="${PY:-python3}"
X264=(-c:v libx264 -preset slow -crf 17 -profile:v high -pix_fmt yuv420p -r 30 -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv)

# captions for the teaser timeline (film cues re-timed: seg2 offset -42.5 s, seg3 offset -161.2 s)
cat > "$B/teaser.srt" <<'SRT'
1
00:00:00,250 --> 00:00:02,773
These temple walls are written in Tamil.

2
00:00:02,773 --> 00:00:04,600
The letters are fading.

3
00:00:04,800 --> 00:00:07,379
On a Chola-period stone from Thanjavur,

4
00:00:07,379 --> 00:00:10,834
it reads the letters, the
words, then the meaning.

5
00:00:11,200 --> 00:00:14,122
Ezhuthu. Let the stones speak again.

6
00:00:14,122 --> 00:00:15,000
d3jz2k92ne5puo.cloudfront.net
SRT

# 1) base cut, 1920x1080, near-lossless intermediate
ffmpeg -y -v error \
  -ss 0 -t 4.9 -i "$FILM" -ss 47.1 -t 6.6 -i "$FILM" -ss 172.1 -t 4.1 -i "$FILM" \
  -filter_complex "\
[0:v]settb=1/30,setpts=PTS-STARTPTS[v0];[1:v]settb=1/30,setpts=PTS-STARTPTS[v1];[2:v]settb=1/30,setpts=PTS-STARTPTS[v2];\
[v0][v1]xfade=transition=fade:duration=0.3:offset=4.6,settb=1/30[v01];[v01][v2]xfade=transition=fade:duration=0.3:offset=10.9,trim=end_frame=450[v];\
[0:a]asetpts=PTS-STARTPTS[a0];[1:a]asetpts=PTS-STARTPTS[a1];[2:a]asetpts=PTS-STARTPTS[a2];\
[a0][a1]acrossfade=d=0.3[a01];[a01][a2]acrossfade=d=0.3,afade=t=out:st=14.4:d=0.6,atrim=end_sample=720000[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -preset veryfast -crf 10 -pix_fmt yuv420p -c:a pcm_f32le "$B/base.mkv"

# 2) two-pass loudnorm on the teaser audio (-14 LUFS, TP -1.5)
js=$(ffmpeg -hide_banner -nostats -i "$B/base.mkv" -vn -af "loudnorm=I=-14:TP=-1.5:LRA=20:print_format=json" -f null - 2>&1 | sed -n '/^{/,/^}/p')
g() { echo "$js" | awk -F'"' -v k="\"$1\"" '$0~k{print $4}'; }
LN="loudnorm=I=-14:TP=-1.5:LRA=20:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true,aresample=48000"

# 3) 16:9 teaser with captions
"$PY" "$HERE/captions.py" "$B/teaser.srt" "$FONT" "$B/caps-h" 1920 1080 40 104 > "$B/h.body"
{ echo "[0:v]null[vin];"; cat "$B/h.body"; } > "$B/h.graph"
args=(-i "$B/base.mkv"); while read -r f; do args+=(-i "$f"); done < "$B/caps-h/inputs.txt"
ffmpeg -y -v error "${args[@]}" -/filter_complex "$B/h.graph" -map "[vcap]" -map 0:a -af "$LN" \
  "${X264[@]}" -c:a aac -b:a 256k -ar 48000 -movflags +faststart "$VID/teaser-15s.mp4"

# 4) 9:16 reframe: blurred fill + full 16:9 frame at 1080 wide + header + captions under the picture
mkdir -p "$B/vcards"
node "$HERE/raster.mjs" "$HERE/vertical-header.html" "$B/vcards/header.png" 1080 1920 transparent
"$PY" "$HERE/captions.py" "$B/teaser.srt" "$FONT" "$B/caps-v" 1080 1920 46 520 2 > "$B/v.body2"
{
  echo "[0:v]split[a][b];"
  echo "[a]scale=-2:1920,crop=1080:1920,boxblur=40:2,eq=brightness=-0.22:saturation=0.8[bg];"
  echo "[b]scale=1080:-2[fg];"
  echo "[bg][fg]overlay=x=0:y=(H-h)/2-120[c0];"
  echo "[c0][1:v]overlay=0:0[vin];"
  cat "$B/v.body2"
} > "$B/v.graph"
args=(-i "$B/base.mkv" -loop 1 -t 15 -i "$B/vcards/header.png"); while read -r f; do args+=(-i "$f"); done < "$B/caps-v/inputs.txt"
ffmpeg -y -v error "${args[@]}" -/filter_complex "$B/v.graph" -map "[vcap]" -map 0:a -af "$LN" -t 15 \
  "${X264[@]}" -c:a aac -b:a 256k -ar 48000 -movflags +faststart "$VID/teaser-15s-vertical.mp4"
rm -rf "$B"
