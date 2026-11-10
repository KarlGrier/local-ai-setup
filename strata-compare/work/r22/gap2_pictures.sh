#!/bin/bash
# gap2_pictures.sh - round 22, the pictures step (the user, 10-19), run by work/r22/gap2.sh inside gap 2 (queue held,
# test lock, 8080 down). The CPU picture reader as 0.2.0's setup builds and configures it for --vision cpu:
#   1 build      strata-vision from tools/vision against our llama.cpp checkout (0.2.0's pinned 3cf03257), CPU only,
#                native (STRATA_VISION_CUDA=OFF, STRATA_PORTABLE=OFF, as setup on this PC) -> engine-r22port/strata-vision
#   2 identity   eleven text replies on the fixed-computation twin without and with the reader loaded
#                (configs/r22portRT.json vs r22portRT-vision.json): must be identical
#   3 screenshot the way Jan sends one (work/r22/vision_check.py, a terminal screenshot from the port's docs): seconds
#                to the first answer token and to the end, the answer (judged by hand), the reader's RSS
#   4 speed      decode screen A B B A, reader off vs on (daily settings: r22port.json vs r22port-vision.json); the
#                guard's min MemAvailable / max RSS per arm
#   5 RAM        the full screen once each, reader on and off (32K / 64K / 120K prompts fill the chat cache): the
#                guard's min MemAvailable and max RSS - a long-context stand-in for a research report stage
# Output: results/r22/gap2/pictures/. A kernel error exits 3 (gap2.sh then stops with the gap open).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; O=results/r22/gap2/pictures; mkdir -p $O
B=$WS/configs/r22port.json BV=$WS/configs/r22port-vision.json RT=$WS/configs/r22portRT.json RTV=$WS/configs/r22portRT-vision.json
IMG=$WS/strata-r22port/docs/terminal-previews/serving-110-stages.png
say() { echo "--- $(date '+%F %T') pictures: $*"; }
kc() { bringup/lib/kcheck.sh "r22g2-pic-$1" || { say "KERNEL CHECK FAILED after $1"; exit 3; }; }

say "1 build the CPU picture reader"
LL=$(readlink -f strata/third_party/llama.cpp)
pgrep -f "work/r22/[b]uild_memguard.sh" > /dev/null || { setsid nohup work/r22/build_memguard.sh 3600 > /dev/null 2>&1 < /dev/null & }
rm -rf strata-r22port/build-vision
if ! (cd strata-r22port && nice -n 5 cmake -G Ninja -S tools/vision -B build-vision -DCMAKE_BUILD_TYPE=Release -DLLAMA_DIR="$LL" \
        -DSTRATA_VISION_CUDA=OFF -DSTRATA_PORTABLE=OFF > build-vision-configure.log 2>&1 \
      && nice -n 5 cmake --build build-vision --target strata-vision -j 16 > build-vision.log 2>&1); then
  tail -30 strata-r22port/build-vision.log > $O/build-fail.txt 2> /dev/null; say "READER BUILD FAILED ($O/build-fail.txt) - pictures skipped"; exit 1
fi
cp strata-r22port/build-vision/bin/strata-vision engine-r22port/strata-vision
sha256sum engine-r22port/strata-vision | tee engine-r22port/strata-vision.SHA256
sha256sum models/vision-r22/mmproj-Qwen3.8-Flash-Next-BF16.gguf | grep -q '^b1a82259702816a5330d7bd7607cd9676b11780e79ff7348c21103ff3ce49bd0 ' \
  || { say "mmproj SHA-256 is not the pinned one - pictures skipped"; exit 1; }

say "2 identity: text replies without and with the reader loaded (fixed-computation twin)"
bringup/lib/with_server.sh VI-off $RT -- "$P work/r22/vision_identity.py run http://127.0.0.1:8081 $O/identity-off.json" 2>&1 | grep -E "replies|ready|exited"
kc identity-off
bringup/lib/with_server.sh VI-on $RTV -- "$P work/r22/vision_identity.py run http://127.0.0.1:8081 $O/identity-on.json" 2>&1 | grep -E "replies|ready|exited"
kc identity-on
$P work/r22/vision_identity.py compare $O/identity-off.json $O/identity-on.json | tee $O/identity.txt

say "3 screenshot as Jan sends it"
bringup/lib/with_server.sh VC $BV -- "$P work/r22/vision_check.py http://127.0.0.1:8081 $IMG $WS/$O/answer" 2>&1 \
  | grep -E "reader RSS|first_answer|ready|exited" | tee $O/vision-check.txt
grep -ahE "^OK [0-9]+ [0-9]+ [0-9]+|picture|image encoder|vision" $(ls -t bringup/out/logs/server_VC_*.log | head -1) | tail -8 | cut -c1-200 | tee -a $O/vision-check.txt
kc screenshot

say "4 decode A B B A, reader off vs on"
SS=$(date -Iseconds | cut -c1-19)
for arm in "off-a $B" "on-a $BV" "on-b $BV" "off-b $B"; do
  set -- $arm
  bringup/lib/decscreen.sh r22-g2-V-$1 $2 > logs/r22/g2-V-$1.log 2>&1
  echo "arm $1: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200)" | tee -a $O/speed-arms.txt
  kc dec-$1
done
SINCE=$SS $P bringup/lib/ab_table.py OFF=r22-g2-V-off-a,r22-g2-V-off-b ON=r22-g2-V-on-a,r22-g2-V-on-b > $O/dec.md 2>&1
grep -iE '^\| *(decode|ms per|long|ttft)' $O/dec.md | head -6

say "5 RAM: full screen, reader on, then off"
for arm in "on $BV" "off $B"; do
  set -- $arm
  bringup/lib/fullscreen.sh r22-g2-VF-$1 $2 > logs/r22/g2-VF-$1.log 2>&1
  echo "full screen reader $1: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200)" | tee -a $O/ram.txt
  kc full-$1
done
say "done"
