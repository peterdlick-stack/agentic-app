#!/usr/bin/env bash
# build-hub.sh — 编译和 OctoSense 桌面版 0.1.0-rc.5 配套的 `hub` 命令行（App Hub 提交 8347a489）。
#
# 用法（在 WSL / Linux 里）：
#   tools/win/build-hub.sh            # 源码放 ~/.context-dj-local/OctoSense-App-Hub-rc5
#   tools/win/build-hub.sh <目录>      # 源码放到指定目录
#   HUB_REV=<提交> tools/win/build-hub.sh   # 换成别的 App Hub 提交（例：rc.6 配套的
#                                        # 386359153ed6377b5f047bd9ed2767a6a2ac2bc7，未在桌面上实测）
#
# 产物：~/.context-dj-local/bin/hub（可用 CDJ_LOCAL 改根目录）。
# 只编译 hub 这一个命令（不编译 card-host、appstore 等），大约 5–10 分钟。
# 磁盘：编译目录约 0.5 GB，cargo 缓存约 0.9 GB。WSL 的虚拟磁盘在 C 盘上，C 盘紧张的话
# 先设置 CARGO_TARGET_DIR 到别的盘，编译完可以删掉它。
#
# 关于兄弟仓库：App Hub 的 Cargo.toml 用 [patch] 指向 ../makepad、../octoscript 等兄弟检出。
# hub 本身不依赖 makepad；如果这些兄弟目录不存在，本脚本会在这份专用检出里去掉这些
# [patch]（octoscript-ui-l0 改从 git 按 Cargo.toml 里钉死的 rev 取），所以 Cargo.lock 会被重新解析。
# 这份检出只用来编译 hub，不要在里面做别的开发。
set -euo pipefail

REV="${HUB_REV:-8347a489141c0e24cab564883db7c4592935a8b2}"   # rc.5 锁定的 App Hub 提交
LOCAL="${CDJ_LOCAL:-$HOME/.context-dj-local}"
DIR="${1:-$LOCAL/OctoSense-App-Hub-rc5}"
OUT="$LOCAL/bin/hub"

command -v cargo >/dev/null || { echo "需要 Rust 工具链（https://rustup.rs）"; exit 1; }
command -v git >/dev/null   || { echo "需要 git"; exit 1; }

mkdir -p "$DIR" "$LOCAL/bin"
if [ ! -d "$DIR/.git" ]; then
  git -C "$DIR" init -q
  git -C "$DIR" remote add origin https://github.com/OctoSense-org/OctoSense-App-Hub
fi
git -C "$DIR" fetch -q --depth 1 origin "$REV"
git -C "$DIR" checkout -q --force --detach FETCH_HEAD
echo "App Hub @ $(git -C "$DIR" rev-parse HEAD)"

PARENT="$(dirname "$DIR")"
if [ -d "$PARENT/makepad" ] && [ -d "$PARENT/octoscript" ] && [ -d "$PARENT/octoscript-makepad" ]; then
  echo "检测到兄弟检出，保留 [patch]"
else
  echo "没有兄弟检出：在这份检出里去掉指向兄弟目录的 [patch]"
  python3 - "$DIR/Cargo.toml" <<'EOF'
import sys
p = sys.argv[1]
out, skip = [], False
for line in open(p, encoding="utf-8").read().splitlines():
    if line.startswith('[patch."https://'):
        skip = True
        continue
    if line.startswith("[") and not line.startswith('[patch."'):
        skip = False
    if not skip:
        out.append(line)
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
EOF
fi

( cd "$DIR" && cargo build --release -p octosense-app-hub --bin hub )
TARGET="${CARGO_TARGET_DIR:-$DIR/target}"
cp "$TARGET/release/hub" "$OUT"
"$OUT" help | grep -q sign-manifest || { echo "FAIL: $OUT 缺少 sign-manifest"; exit 1; }
echo "OK: $OUT"
echo "（可以删除 $TARGET 释放空间；hub 已经复制出来了）"
