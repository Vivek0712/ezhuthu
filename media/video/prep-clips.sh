#!/usr/bin/env bash
# Prepare the moving-image sources the HTML scenes seek into, and the 4096 px photo plates.
#   bash media/video/prep-clips.sh
# Writes (outside git) to $EZ_VIDEO_DIR (default ~/tamil-script/ezhuthu-video):
#   clips/<name>.mp4   all-intra H.264 trims (every frame a keyframe), so window.__seek() lands frame-exact and fast
#   stock/web/<id>.jpg photo plates, long side 4096 px (Ken Burns, grade and grain are applied in the scene HTML)
# Trim points follow storyboard.json; each clip keeps 0.5 s of handle either side where the source allows.
set -euo pipefail
V="${EZ_VIDEO_DIR:-$HOME/tamil-script/ezhuthu-video}"
mkdir -p "$V/clips" "$V/stock/web"

intra() { # src out start duration [extra vf]
  local vf="fps=30,setsar=1,format=yuv420p${5:+,$5}"
  ffmpeg -v error -y -ss "$3" -i "$1" -t "$4" -an -vf "$vf" -c:v libx264 -preset medium -crf 17 -g 1 -keyint_min 1 \
    -pix_fmt yuv420p -movflags +faststart "$V/clips/$2.mp4"
  echo "clips/$2.mp4  $(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of csv=p=0 "$V/clips/$2.mp4") frames"
}

# Stock: v05 Tanjavur Song Devotee (Rainer Halama, CC BY-SA 4.0); storyboard in 3.0 -> 6.6 s (+ dissolve handle)
intra "$V/stock/v05-tanjavur-song-devotee.webm" v05 2.4 4.8
# Live-site captures (own work)
F="$V/footage"
intra "$F/home-hero.mp4"       home-hero       2.5 21.5
intra "$F/practice.mp4"        practice        0   10.5
intra "$F/practice-mobile.mp4" practice-mobile 0   10.1
intra "$F/restore-fill.mp4"    restore-fill    0   34
intra "$F/restore-open.mp4"    restore-open    1.5 25.5
intra "$F/how.mp4"             how             1.6 7

# Photo plates
for id in p01 p17 p04 p14 p11 p20b p32 p09 p26 p07 p15 p13 p35 p10 p05; do
  f=$(ls "$V/stock/$id-"*.jpg | head -1)
  [ -f "$V/stock/web/$id.jpg" ] || [ "$id" = p17 ] || ffmpeg -v error -y -i "$f" \
    -vf "scale='if(gt(iw,ih),min(4096,iw),-2)':'if(gt(iw,ih),-2,min(4096,ih))'" -q:v 2 "$V/stock/web/$id.jpg"
done
# p17 is used at its full 6000 px (deepest macro push-in in a1-01 / a1-04)
cp -n "$V/stock/"p17-*.jpg "$V/stock/web/p17.jpg" 2>/dev/null || true
du -sh "$V/clips" "$V/stock/web"
