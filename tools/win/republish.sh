#!/usr/bin/env bash
# republish.sh — 把 bundle/ 签名后发布到本地商店（mirror），给 Windows 原生 OctoSense rc.5 安装/更新用。
#
# 用法（在 WSL / Linux 里，从仓库任意位置运行）：
#   tools/win/republish.sh                 # 发布已提交的 HEAD，序号自动 +1
#   tools/win/republish.sh --worktree      # 发布工作区里的 bundle/（含未提交的改动）
#   tools/win/republish.sh --ref <提交>     # 发布指定提交
#   tools/win/republish.sh 7               # 手动指定序号（版本号 = <manifest 版本>-local.7）
#
# 环境变量（都有默认值）：
#   CDJ_WIN_ROOT  本地数据根目录，必须和 start-dev.ps1 的 -Root 是同一个目录（WSL 里的写法）。
#                 默认：仓库旁边的 context-dj-win（例：仓库在 /mnt/f/work/agentic-app，
#                 则为 /mnt/f/work/context-dj-win，Windows 里就是 F:\work\context-dj-win）
#   CDJ_KEYS      一次性密钥目录，默认 ~/.context-dj-local/keys（第一次运行时自动生成）
#   HUB           hub 命令，默认 ~/.context-dj-local/bin/hub，没有就用 PATH 里的 hub
#
# 版本号每次必须比上次大，商店才会出现“更新”。仓库里的 bundle/ 不会被改动：所有修改
# （版本号、盖戳、签名）都只在副本里做。密钥只用于本机彩排，和官方 App Hub 提交无关。
set -euo pipefail

usage() { sed -n '2,20p' "$0"; exit "${1:-0}"; }

N="" ; REF="HEAD" ; WORKTREE=0
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --worktree) WORKTREE=1 ;;
    --ref) REF="${2:?--ref 需要一个提交}"; shift ;;
    [0-9]*) N="$1" ;;
    *) echo "未知参数：$1"; usage 1 ;;
  esac
  shift
done

REPO="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
LOCAL="${CDJ_LOCAL:-$HOME/.context-dj-local}"
ROOT="${CDJ_WIN_ROOT:-$(dirname "$REPO")/context-dj-win}"
K="${CDJ_KEYS:-$LOCAL/keys}"
if [ -z "${HUB:-}" ]; then
  if [ -x "$LOCAL/bin/hub" ]; then HUB="$LOCAL/bin/hub"; else HUB="$(command -v hub || true)"; fi
fi
[ -n "$HUB" ] && [ -x "$HUB" ] || { echo "找不到 hub：先运行 tools/win/build-hub.sh，或设置 HUB"; exit 1; }
"$HUB" help | grep -q sign-manifest || { echo "FAIL: $HUB 太旧，缺少 sign-manifest"; exit 1; }

M="$ROOT/mirror"
B="$(mktemp -d "${TMPDIR:-/tmp}/cdj-build.XXXXXX")"
trap 'rm -rf "$B"' EXIT
mkdir -p "$M"

# 1. 一次性密钥：没有就生成，有就沿用（hub keygen 不会覆盖已有文件）
if [ ! -e "$K/anchor.key" ] && [ ! -e "$K/working.key" ] && [ ! -e "$K/publisher.key" ]; then
  echo "== 第一次运行：在 $K 生成一次性密钥 =="
  mkdir -p "$K"; chmod 700 "$K"
  "$HUB" keygen "$K/publisher.key" > "$K/publisher.pub"
  "$HUB" keygen "$K/anchor.key"    > "$K/anchor.pub"
  "$HUB" keygen "$K/working.key"   > "$K/working.pub"
  "$HUB" certify --anchor "$K/anchor.key" --working "$K/working.key" > "$K/working.cert"
fi
for f in publisher.key publisher.pub anchor.pub working.key working.cert; do
  [ -s "$K/$f" ] || { echo "FAIL: 密钥不完整，缺 $K/$f。不要只删一部分；整组重建需要同时换一个新的 CDJ_WIN_ROOT/mirror"; exit 1; }
done
PUB="$(cat "$K/publisher.pub")"
ANCHOR="$(cat "$K/anchor.pub")"
if [ -s "$M/catalog.json" ]; then
  "$HUB" verify "$M/catalog.json" --anchor "$ANCHOR" >/dev/null 2>&1 || {
    echo "FAIL: $M/catalog.json 不是用这组密钥签的（换过密钥或 CDJ_WIN_ROOT 指错了）"; exit 1; }
fi
cp "$K/anchor.pub" "$ROOT/anchor.pub"   # start-dev.ps1 从这里读商店的信任锚（公钥）

# 2. 导出副本（LF 字节）
if [ "$WORKTREE" = 1 ]; then
  cp -r "$REPO/bundle" "$B/bundle"
  COMMIT="$(git -C "$REPO" rev-parse HEAD)"
  SRC="工作区（HEAD $COMMIT）"
  if [ -n "$(git -C "$REPO" status --porcelain -- bundle)" ]; then SRC="工作区（HEAD $COMMIT + 未提交改动）"; fi
else
  git -C "$REPO" archive "$REF" bundle | tar -x -C "$B"
  COMMIT="$(git -C "$REPO" rev-parse "$REF^{commit}")"
  SRC="提交 $COMMIT"
fi
if grep -rlI $'\r' "$B/bundle" --include='*.splash' --include='*.json' --include='*.md' --include='*.svg' >/dev/null; then
  echo "FAIL: 副本里有 CRLF 文本文件（见 .gitattributes）："
  grep -rlI $'\r' "$B/bundle" --include='*.splash' --include='*.json' --include='*.md' --include='*.svg'
  exit 1
fi

# 3. 版本号：<manifest 里的版本，去掉旧后缀>-local.<N>
if [ -z "$N" ]; then
  N="$(python3 - "$M/catalog.json" <<'EOF'
import json, re, sys
try:
    text = open(sys.argv[1], encoding="utf-8").read()
except FileNotFoundError:
    print(1); sys.exit()
print(max([int(n) for n in re.findall(r'context-dj[^"]*?-local\.(\d+)', text)] + [0]) + 1)
EOF
)"
fi
VER="$(python3 - "$B/bundle/manifest.json" "$N" <<'EOF'
import json, sys
p, n = sys.argv[1], sys.argv[2]
m = json.load(open(p, encoding="utf-8"))
v = m["version"].split("-")[0] + "-local." + n
m["version"] = v
with open(p, "w", encoding="utf-8", newline="\n") as f:
    json.dump(m, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(v)
EOF
)"
echo "== 发布 context-dj $VER，来源：$SRC =="

# 4. 盖戳、签名、检查
"$HUB" stamp "$B/bundle"
"$HUB" sign-manifest "$B/bundle" --key "$K/publisher.key" --key-id kyber-local
"$HUB" check "$B/bundle" --publisher-key "kyber-local=$PUB"

# 5. 发布到本地商店并验证
"$HUB" publish "$B/bundle" --catalog "$M/catalog.json" --key "$K/working.key" \
  --anchor-cert "$(cat "$K/working.cert")" --anchor "$ANCHOR" \
  --publisher kyber-local --publisher-key "kyber-local=$PUB" \
  --repo https://github.com/peterdlick-stack/agentic-app --commit "$COMMIT" \
  --out "$M"
"$HUB" verify "$M/catalog.json" --anchor "$ANCHOR"

echo "== 完成：$VER 已在 $M =="
echo "下一步（Windows）：用 tools\\win\\start-dev.ps1 重启 OctoSense → App Hub → 情境 DJ → Update/Install"
