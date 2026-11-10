#!/bin/bash
# install.sh - usability round: the four apps in user space (no sudo), each in its own folder under ~/.local/opt,
# every download checked against its published digest. Nothing is added to PATH or to your shell files; the launchers in
# configs/usability/ set what each app needs. Your own Codex (~/.codex, ~/.local/bin/codex) is not touched.
#   Node.js v24.22.0 (LTS, for dsh)        nodejs.org tarball, SHASUMS256.txt
#   OpenCode 2.0.30 (@opencode/cli)         npm registry platform package (the binary), sha512 integrity
#   DeepSeek Harness 0.2.0-rc.2 (dsh)       npm install --prefix with the Node above (no audit / fund calls)
#   Codex CLI 0.162.1 (rust-v0.162.1)       GitHub release codex-package (musl), sha256 digest from the release API
#   Jan 0.8.6                               GitHub release AppImage, sha256 digest from the release API
set -euo pipefail
OPT=$HOME/.local/opt; DL=$HOME/.cache/usability-downloads; mkdir -p "$OPT" "$DL"
step() { echo "=== $(date -Is) $*"; }
fetch() {   # fetch URL NAME: download once into $DL (kept for re-runs)
  [ -s "$DL/$2" ] && return 0
  curl -fsSL --retry 3 -o "$DL/$2.part" "$1"; mv "$DL/$2.part" "$DL/$2"
}
sha256ok() { echo "$2  $DL/$1" | sha256sum -c - ; }

step "Node.js v24.22.0"
NV=v24.22.0; NT=node-$NV-linux-x64.tar.xz
fetch https://nodejs.org/dist/$NV/SHASUMS256.txt node-$NV-SHASUMS256.txt
fetch https://nodejs.org/dist/$NV/$NT $NT
sha256ok $NT "$(grep " $NT\$" "$DL/node-$NV-SHASUMS256.txt" | cut -d' ' -f1)"
[ -x "$OPT/node-$NV/bin/node" ] || { mkdir -p "$OPT/node-$NV"; tar -xJf "$DL/$NT" -C "$OPT/node-$NV" --strip-components=1; }
"$OPT/node-$NV/bin/node" --version

step "OpenCode 2.0.30"
OV=2.0.30; OT=cli-linux-x64-$OV.tgz
fetch https://registry.npmjs.org/@opencode/cli-linux-x64/-/$OT $OT
want=$(curl -fsS https://registry.npmjs.org/@opencode%2Fcli-linux-x64/$OV | python3 -c "import json,sys; print(json.load(sys.stdin)['dist']['integrity'])")
got="sha512-$(openssl dgst -sha512 -binary "$DL/$OT" | base64 -w0)"
[ "$want" = "$got" ] && echo "$OT: integrity OK" || { echo "$OT: integrity MISMATCH ($got vs $want)"; exit 1; }
[ -d "$OPT/opencode-$OV" ] || { mkdir -p "$OPT/opencode-$OV"; tar -xzf "$DL/$OT" -C "$OPT/opencode-$OV" --strip-components=1; }
find "$OPT/opencode-$OV" -maxdepth 2 -type f | head -20

step "DeepSeek Harness 0.2.0-rc.2"
DV=0.2.0-rc.2
export PATH="$OPT/node-$NV/bin:$PATH" npm_config_cache="$DL/npm-cache" npm_config_update_notifier=false
[ -d "$OPT/dsh-$DV/node_modules/@deepseek-ai/dsh" ] || npm install --prefix "$OPT/dsh-$DV" --no-audit --no-fund "@deepseek-ai/dsh@$DV" 2>&1 | tail -15
ls "$OPT/dsh-$DV/node_modules/.bin/" | head

step "Codex CLI 0.162.1"
CV=0.162.1; CT=codex-package-x86_64-unknown-linux-musl.tar.gz
fetch https://github.com/openai/codex/releases/download/rust-v$CV/$CT codex-$CV-$CT
sha256ok codex-$CV-$CT a676f5722aae0d86cbe3764332f08eab1fdd89dc0a300b3ad4ffbf48611fa3e3
[ -d "$OPT/codex-$CV" ] || { mkdir -p "$OPT/codex-$CV"; tar -xzf "$DL/codex-$CV-$CT" -C "$OPT/codex-$CV"; }
find "$OPT/codex-$CV" -maxdepth 3 -type f -perm -u+x | head -10

step "Jan 0.8.6"
JV=0.8.6; JA=Jan_${JV}_amd64.AppImage
fetch https://github.com/janhq/jan/releases/download/v$JV/$JA $JA
sha256ok $JA 2fe70fb088473a7bdb499e5ce071d5a573c547556914825db989ec1dd1052066
mkdir -p "$OPT/jan-$JV"; [ -x "$OPT/jan-$JV/$JA" ] || { cp "$DL/$JA" "$OPT/jan-$JV/$JA"; chmod +x "$OPT/jan-$JV/$JA"; }
ls -la "$OPT/jan-$JV/"
step "install done"
