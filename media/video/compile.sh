#!/usr/bin/env bash
# Ezhuthu launch film: final assembly (ffmpeg).
#
#   media/video/compile.sh            # film + captions version + thumbnail + teasers + contact sheet
#   STAGES="film sheet" media/video/compile.sh   # only some stages (film captions thumb teaser sheet)
#
# Inputs (binaries live outside git, in $VID):
#   $VID/scenes/<id>.mp4          22 rendered scenes, exact storyboard windows (render.mjs)
#   $VID/audio-v2/soundtrack-v2.wav  the finished v2 soundtrack (audio-v2/mix-v2.sh: Polly narration, temple
#                                   ambience, original score, SFX; already -14 LUFS / -1.5 dBTP, 180.000 s). Used as is.
#   (fallback when SOUNDTRACK="" : $VID/audio-v2/narration-v2.wav + $VID/audio/music.wav + sfx.wav, mixed here)
#   media/video/storyboard.json   scene order and durations
#   media/video/audio-v2/captions-v2.srt  captions
# Outputs ($VID):
#   ezhuthu-film.mp4, ezhuthu-film-captions.mp4, thumbnail.png, teaser-15s.mp4, teaser-15s-vertical.mp4,
#   review/contact.png
# Spec: 1920x1080, 30 fps, H.264 High yuv420p, AAC 48 kHz, exactly 180.000 s; narration over music with the music
# ducked 12 dB under the voice; two-pass loudnorm to -14 LUFS integrated, true peak below -1 dBTP.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TOOLS="$HERE/compile"
VID="${VID:-/Users/vivekrajaps/tamil-script/ezhuthu-video}"
SB="$HERE/storyboard.json"
SRT="${SRT:-$HERE/audio-v2/captions-v2.srt}"
NARR="${NARR:-$VID/audio-v2/narration-v2.wav}"
MUSIC="${MUSIC:-$VID/audio/music.wav}"
SFX="${SFX:-$VID/audio/sfx.wav}"
[ -f "$VID/audio-v2/music-v2.wav" ] && MUSIC="${MUSIC_V2:-$VID/audio-v2/music-v2.wav}"
SOUNDTRACK="${SOUNDTRACK-$VID/audio-v2/soundtrack-v2.wav}"
FONT="$VID/fonts/InstrumentSans.ttf"
BUILD="$VID/build"
STAGES="${STAGES:-film captions thumb teaser sheet}"
PY="${PY:-python3}"

FILM="$VID/ezhuthu-film.mp4"
FILM_CAP="$VID/ezhuthu-film-captions.mp4"

TARGET_I=-14
TARGET_TP=-1.5
DUCK_DB=12
NARR_LUFS=-16      # stem targets before the mix (the final loudnorm sets the absolute level)
MUSIC_LUFS=-19
SFX_GAIN_DB=0
# 180 s of audio rounded down to whole AAC frames (1024 samples): the container duration is then the video's
# 5,400 frames = 180.000 s, with no AAC end padding sticking out past the picture.
AUDIO_SAMPLES=$(( (180 * 48000 / 1024) * 1024 ))

X264=(-c:v libx264 -preset slow -crf 17 -profile:v high -level 4.2 -pix_fmt yuv420p -r 30
      -g 60 -bf 2 -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv)
AAC=(-c:a aac -b:a 256k -ar 48000 -ac 2)

mkdir -p "$BUILD" "$VID/review"
log() { printf '\n== %s\n' "$*"; }
has() { [[ " $STAGES " == *" $1 "* ]]; }

df -h "$VID" | tail -1

lufs() {  # integrated loudness of a file
  ffmpeg -hide_banner -nostats -i "$1" -af ebur128=peak=true -f null - 2>&1 |
    awk '/Integrated loudness:/{f=1} f&&/ I:/{print $2; exit}'
}
true_peak() {
  ffmpeg -hide_banner -nostats -i "$1" -af ebur128=peak=true -f null - 2>&1 |
    awk '/True peak:/{f=1} f&&/Peak:/{print $2; exit}'
}

# ---------------------------------------------------------------- audio
mix_master() {  # $1 narration $2 music $3 sfx("-" for none) $4 out.wav $5 samples
  local n="$1" m="$2" s="$3" out="$4" samples="$5" tag
  tag="$(basename "$out" .wav)"
  ffmpeg -y -v error -i "$n" -ac 1 -ar 48000 -c:a pcm_f32le "$BUILD/$tag.n.wav"
  ffmpeg -y -v error -i "$m" -ac 2 -ar 48000 -c:a pcm_f32le "$BUILD/$tag.m.wav"
  [ "$s" != "-" ] && ffmpeg -y -v error -i "$s" -ac 2 -ar 48000 -c:a pcm_f32le "$BUILD/$tag.s.wav"
  local ln lm gn gm
  ln=$(lufs "$BUILD/$tag.n.wav"); lm=$(lufs "$BUILD/$tag.m.wav")
  gn=$(awk -v a="$NARR_LUFS" -v b="$ln" 'BEGIN{printf "%.2f", a-b}')
  gm=$(awk -v a="$MUSIC_LUFS" -v b="$lm" 'BEGIN{printf "%.2f", a-b}')
  echo "stems: narration $ln LUFS (gain $gn dB), music $lm LUFS (gain $gm dB)"
  "$PY" "$TOOLS/mix_audio.py" "$BUILD/$tag.n.wav" "$BUILD/$tag.m.wav" \
    "$( [ "$s" != "-" ] && echo "$BUILD/$tag.s.wav" || echo - )" \
    "$BUILD/$tag.premix.wav" "$gn" "$gm" "$SFX_GAIN_DB" "$DUCK_DB" "$samples"
  # two-pass loudnorm
  local js
  js=$(ffmpeg -hide_banner -nostats -i "$BUILD/$tag.premix.wav" \
        -af "loudnorm=I=$TARGET_I:TP=$TARGET_TP:LRA=20:print_format=json" -f null - 2>&1 |
       sed -n '/^{/,/^}/p')
  local mi mtp mlra mth off
  mi=$(echo "$js" | awk -F'"' '/"input_i"/{print $4}')
  mtp=$(echo "$js" | awk -F'"' '/"input_tp"/{print $4}')
  mlra=$(echo "$js" | awk -F'"' '/"input_lra"/{print $4}')
  mth=$(echo "$js" | awk -F'"' '/"input_thresh"/{print $4}')
  off=$(echo "$js" | awk -F'"' '/"target_offset"/{print $4}')
  echo "loudnorm pass 1: I $mi LUFS, TP $mtp dBTP, LRA $mlra LU"
  ffmpeg -y -v error -i "$BUILD/$tag.premix.wav" -af \
    "loudnorm=I=$TARGET_I:TP=$TARGET_TP:LRA=20:measured_I=$mi:measured_TP=$mtp:measured_LRA=$mlra:measured_thresh=$mth:offset=$off:linear=true,aresample=48000,atrim=end_sample=$samples" \
    -c:a pcm_f32le "$out"
  # Guard: if pass 2 had to fall back to dynamic mode or landed off target, finish with a static trim +
  # a true-peak limiter, then re-check.
  local oi otp
  oi=$(lufs "$out"); otp=$(true_peak "$out")
  echo "loudnorm pass 2: I $oi LUFS, TP $otp dBTP"
  if awk -v i="$oi" -v t="$otp" -v ti="$TARGET_I" 'BEGIN{exit !((i-ti)>0.5 || (ti-i)>0.5 || t>-1.2)}'; then
    local g
    g=$(awk -v i="$oi" -v ti="$TARGET_I" 'BEGIN{printf "%.2f", ti-i}')
    ffmpeg -y -v error -i "$out" -af "volume=${g}dB,alimiter=limit=0.80:attack=1:release=60:level=disabled,aresample=48000,atrim=end_sample=$samples" \
      -c:a pcm_f32le "$out.tmp.wav" && mv "$out.tmp.wav" "$out"
    echo "trim: I $(lufs "$out") LUFS, TP $(true_peak "$out") dBTP"
  fi
}

if has film; then
  log "audio: film mix"
  if [ -n "$SOUNDTRACK" ] && [ -f "$SOUNDTRACK" ]; then
    echo "soundtrack: $SOUNDTRACK (I $(lufs "$SOUNDTRACK") LUFS, TP $(true_peak "$SOUNDTRACK") dBTP)"
    ffmpeg -y -v error -i "$SOUNDTRACK" -ar 48000 -ac 2 -af "atrim=end_sample=$AUDIO_SAMPLES" -c:a pcm_f32le "$BUILD/film-mix.wav"
  elif [ "${SKIP_MIX:-0}" != 1 ]; then
    mix_master "$NARR" "$MUSIC" "$SFX" "$BUILD/film-mix.wav" "$AUDIO_SAMPLES"
  fi

  log "picture: join 22 scenes"
  "$PY" "$TOOLS/video_graph.py" "$SB" "$VID/scenes" "$BUILD/film.graph" "$BUILD/film.inputs"
  args=()
  while read -r f; do args+=(-i "$f"); done < "$BUILD/film.inputs"
  nin=$(wc -l < "$BUILD/film.inputs" | tr -d ' ')
  ffmpeg -y -hide_banner -v error -stats "${args[@]}" -i "$BUILD/film-mix.wav" \
    -/filter_complex "$BUILD/film.graph" -map "[vout]" -map "$nin:a" \
    "${X264[@]}" "${AAC[@]}" -movflags +faststart \
    -metadata title="Ezhuthu: an apprentice for Tamil epigraphy" \
    -metadata comment="Built with Strands Agents, on Amazon Bedrock AgentCore. Credits: media/video/CREDITS.md" \
    "$FILM"
fi

if has captions; then
  log "captions: burn $SRT"
  "$PY" "$TOOLS/captions.py" "$SRT" "$FONT" "$BUILD/caps" 1920 1080 40 104 > "$BUILD/caps.graph.body"
  { echo "[0:v]null[vin];"; cat "$BUILD/caps.graph.body"; } > "$BUILD/caps.graph"
  args=(-i "$FILM")
  while read -r f; do args+=(-i "$f"); done < "$BUILD/caps/inputs.txt"
  ffmpeg -y -hide_banner -v error -stats "${args[@]}" -/filter_complex "$BUILD/caps.graph" \
    -map "[vcap]" -map 0:a "${X264[@]}" -c:a copy -movflags +faststart \
    -metadata title="Ezhuthu: an apprentice for Tamil epigraphy (captions)" "$FILM_CAP"
fi

if has thumb; then
  log "thumbnail"
  VID="$VID" bash "$TOOLS/thumbnail.sh" "$VID/thumbnail.png"
fi

if has teaser; then
  log "teaser 15 s"
  VID="$VID" PY="$PY" bash "$TOOLS/teaser.sh"
fi

if has sheet; then
  log "contact sheet (every 3 s)"
  rm -rf "$BUILD/sheet" && mkdir -p "$BUILD/sheet"
  # frame k at (k-1)*3 s; the last sample is 177 s (frame 5310)
  ffmpeg -y -v error -i "$FILM" -vf "select='not(mod(n\,90))',scale=768:-2" -fps_mode vfr "$BUILD/sheet/f%04d.png"
  "$PY" "$TOOLS/sheet.py" "$BUILD/sheet" 3 6 "$FONT" "$VID/review/contact.png"
  rm -rf "$BUILD/sheet"
fi

log "verify"
for f in "$FILM" "$FILM_CAP" "$VID/teaser-15s.mp4" "$VID/teaser-15s-vertical.mp4"; do
  [ -f "$f" ] || continue
  printf '%s\n  ' "$(basename "$f")"
  ffprobe -v error -show_entries format=duration:stream=codec_name,profile,width,height,pix_fmt,r_frame_rate,sample_rate,nb_frames \
    -of compact=p=0:nk=0 "$f" | tr '\n' ' '
  printf '\n  loudness I %s LUFS, true peak %s dBTP\n' "$(lufs "$f")" "$(true_peak "$f")"
done
[ "${KEEP_BUILD:-0}" = 1 ] || rm -rf "$BUILD"
du -sh "$VID" | tail -1
