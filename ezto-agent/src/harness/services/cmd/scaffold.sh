#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# scaffold.sh —— 一键脚手架，创建一个 video-presentation 项目。
#
# 用法：
#   bash scripts/scaffold.sh <target-dir> [--theme=<id>]
#   bash scripts/scaffold.sh --list-themes
#
# 例子：
#   bash <path-to-web-video-presentation>/scripts/scaffold.sh ./presentation
#   bash <path-to-web-video-presentation>/scripts/scaffold.sh ./talk --theme=paper-press
#   bash <path-to-web-video-presentation>/scripts/scaffold.sh --list-themes
#
# 跑完后，看 SKILL.md "Phase 2.4 实现单章" + references/CHAPTER-CRAFT.md
# 了解每章怎么写。卡壳时翻 references/EXAMPLES/ 找完整章节 anchor。
#
# 之后切换主题，覆盖一个文件即可：
#   cp <path-to-web-video-presentation>/themes/<id>/tokens.css \
#      <project>/src/styles/tokens.css
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# ── 终端输出（同时流入 workflow ExecutionStream）──
_TOTAL_STEPS=4
_STEP=0

progress() {
  _STEP=$((_STEP + 1))
  echo "▸ [${_STEP}/${_TOTAL_STEPS}] $*"
}

ok() {
  echo "✓ $*"
}

detail() {
  echo "  · $*"
}

fail() {
  echo "✗ $*" >&2
}

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
TEMPLATES="$SKILL_DIR/assets/templates"
THEMES_DIR="$SKILL_DIR/assets/themes"
DEFAULT_THEME="midnight-press"

list_themes() {
  echo "可用主题（来自 ${THEMES_DIR}）:"
  echo
  for dir in "$THEMES_DIR"/*/; do
    [[ -d "$dir" ]] || continue
    local meta="$dir/theme.json"
    [[ -f "$meta" ]] || continue
    # 没有 jq，简单 grep + sed 提字段
    local id name desc
    id=$(grep -E '"id"' "$meta" | head -n1 | sed -E 's/.*"id":[[:space:]]*"([^"]+)".*/\1/')
    name=$(grep -E '"nameZh"' "$meta" | head -n1 | sed -E 's/.*"nameZh":[[:space:]]*"([^"]+)".*/\1/')
    desc=$(grep -E '"descriptionZh"' "$meta" | head -n1 | sed -E 's/.*"descriptionZh":[[:space:]]*"([^"]+)".*/\1/')
    printf "  • %-18s %s\n      %s\n\n" "$id" "$name" "$desc"
  done
  echo "用 --theme=<id> 选定一个。默认：${DEFAULT_THEME}。"
}

# ── 解析参数 ──
TARGET=""
THEME="$DEFAULT_THEME"
for arg in "$@"; do
  case "$arg" in
    --list-themes)
      list_themes
      exit 0
      ;;
    --theme=*)
      THEME="${arg#--theme=}"
      ;;
    --*)
      echo "✗ 未知参数: $arg" >&2
      exit 1
      ;;
    *)
      if [[ -z "$TARGET" ]]; then TARGET="$arg"; fi
      ;;
  esac
done

TARGET="${TARGET:-presentation}"
THEME_DIR="$THEMES_DIR/$THEME"
THEME_TOKENS="$THEME_DIR/tokens.css"

if [[ ! -d "$THEME_DIR" || ! -f "$THEME_TOKENS" ]]; then
  echo "✗ 找不到主题 '${THEME}'。可用主题：" >&2
  echo >&2
  for dir in "$THEMES_DIR"/*/; do
    [[ -d "$dir" ]] || continue
    echo "    • $(basename "$dir")" >&2
  done
  exit 1
fi

if [[ -d "$TARGET" && -n "$(ls -A "$TARGET" 2>/dev/null || true)" ]]; then
  echo "✗ 目标目录 '${TARGET}' 已存在且非空，已中止。" >&2
  exit 1
fi

if ! command -v npm >/dev/null; then
  fail "需要 npm，但在 PATH 里没找到。"
  exit 1
fi

# node_modules 缓存 — 首次安装后写入缓存，后续优先链接/恢复
_CACHE="$SKILL_DIR/runtime/cache/npm"

_restore_node_modules() {
  detail "命中依赖缓存，链接 node_modules"
  if ln -sfn "$_CACHE/node_modules" node_modules 2>/dev/null; then
    ok "依赖就绪（缓存）"
    return 0
  fi
  detail "缓存链接失败，改为 npm install"
  npm install --prefer-offline --no-audit --no-fund >/dev/null 2>&1
  ok "依赖就绪"
}

progress "创建 Vite + React + TS 项目 → ${TARGET}"
detail "主题 ${THEME}"

if [ -d "$_CACHE/node_modules" ]; then
  if ! npx --yes create-vite "$TARGET" --template react-ts --no-interactive >/dev/null 2>&1; then
    fail "create-vite 失败"
    exit 1
  fi
  cd "$TARGET"
  cp "$_CACHE/package-lock.json" . 2>/dev/null || true
  progress "安装依赖"
  _restore_node_modules
else
  if ! npx --yes create-vite "$TARGET" --template react-ts --no-interactive >/dev/null 2>&1; then
    fail "create-vite 失败"
    exit 1
  fi
  cd "$TARGET"
  progress "安装依赖"
  detail "首次安装，完成后写入缓存"
  npm install >/dev/null 2>&1
  npm install --save-dev tsx >/dev/null 2>&1
  detail "缓存 node_modules 供后续项目复用"
  mkdir -p "$_CACHE"
  cp -r node_modules "$_CACHE/"
  cp package-lock.json "$_CACHE/" 2>/dev/null || true
  ok "依赖就绪"
fi

progress "部署演示骨架"

# 干掉我们不要的 Vite 默认 boilerplate
rm -f \
  src/App.tsx src/App.css \
  src/main.tsx src/index.css \
  src/assets/react.svg \
  public/vite.svg \
  README.md
rmdir src/assets 2>/dev/null || true

# 把脚手架文件拷到项目根
mkdir -p \
  src/styles src/hooks src/components src/registry src/layouts \
  src/chapters/01-example \
  public scripts

cp "$TEMPLATES/vite.config.ts" .
cp "$TEMPLATES/index.html" .

cp "$TEMPLATES/src/main.tsx" src/main.tsx
cp "$TEMPLATES/src/App.tsx"  src/App.tsx

# tokens.css 来自所选主题
cp "$THEME_TOKENS"                          src/styles/tokens.css
cp "$TEMPLATES/src/styles/base.css"         src/styles/base.css
cp "$TEMPLATES/src/styles/animations.css"   src/styles/animations.css
cp "$TEMPLATES/src/styles/fonts.css"        src/styles/fonts.css

cp "$TEMPLATES/src/layouts/layouts.css"        src/layouts/layouts.css
cp "$TEMPLATES/src/layouts/LAYOUT-SYSTEM.md"   src/layouts/LAYOUT-SYSTEM.md

cp "$TEMPLATES/src/hooks/useStageScale.ts"   src/hooks/useStageScale.ts
cp "$TEMPLATES/src/hooks/useStepper.ts"      src/hooks/useStepper.ts
cp "$TEMPLATES/src/hooks/useAudioPlayer.ts"  src/hooks/useAudioPlayer.ts
cp "$TEMPLATES/src/hooks/useAutoMode.ts"     src/hooks/useAutoMode.ts

cp "$TEMPLATES/src/components/Stage.tsx"          src/components/Stage.tsx
cp "$TEMPLATES/src/components/MaskReveal.tsx"     src/components/MaskReveal.tsx
cp "$TEMPLATES/src/components/SceneChrome.tsx"    src/components/SceneChrome.tsx
cp "$TEMPLATES/src/components/GridSlot.tsx"     src/components/GridSlot.tsx
cp "$TEMPLATES/src/components/ProgressBar.tsx"    src/components/ProgressBar.tsx
cp "$TEMPLATES/src/components/ProgressBar.css"    src/components/ProgressBar.css
cp "$TEMPLATES/src/components/AutoStartGate.tsx"  src/components/AutoStartGate.tsx
cp "$TEMPLATES/src/components/AutoStartGate.css"  src/components/AutoStartGate.css
cp "$TEMPLATES/src/components/AutoToggle.tsx"     src/components/AutoToggle.tsx
cp "$TEMPLATES/src/components/AutoToggle.css"     src/components/AutoToggle.css

cp "$TEMPLATES/src/registry/types.ts"    src/registry/types.ts
cp "$TEMPLATES/src/registry/chapters.ts" src/registry/chapters.ts
cp "$TEMPLATES/src/registry/chapter-meta.ts" src/registry/chapter-meta.ts

cp "$TEMPLATES/src/chapters/01-example/Example.tsx"     src/chapters/01-example/Example.tsx
cp "$TEMPLATES/src/chapters/01-example/Example.css"     src/chapters/01-example/Example.css
cp "$TEMPLATES/src/chapters/01-example/narrations.ts"   src/chapters/01-example/narrations.ts

# Audio pipeline scripts (extract-narrations + synthesize-audio runner +
# pluggable TTS providers under tts-providers/).
cp "$TEMPLATES/scripts/extract-narrations.ts"  scripts/extract-narrations.ts
cp "$TEMPLATES/scripts/synthesize-audio.sh"    scripts/synthesize-audio.sh
chmod +x scripts/synthesize-audio.sh

mkdir -p scripts/tts-providers
cp "$TEMPLATES/scripts/tts-providers/README.md"   scripts/tts-providers/README.md
cp "$TEMPLATES/scripts/tts-providers/minimax.sh"  scripts/tts-providers/minimax.sh
cp "$TEMPLATES/scripts/tts-providers/openai.sh"   scripts/tts-providers/openai.sh

# Wire the audio scripts into npm so contributors don't have to remember
# the exact command. Uses node to merge into the existing package.json.
node -e '
const fs = require("fs");
const p = JSON.parse(fs.readFileSync("package.json", "utf8"));
p.scripts = Object.assign({}, p.scripts, {
  "extract-narrations": "tsx scripts/extract-narrations.ts",
  "synthesize-audio":   "bash scripts/synthesize-audio.sh",
});
fs.writeFileSync("package.json", JSON.stringify(p, null, 2) + "\n");
'

ok "骨架与主题已就位"

# 留个标记，以后能查这个项目从哪个主题起步的
{
  echo "$THEME"
} > .theme

# 跑一次 typecheck 确认接线 OK
progress "TypeScript 检查"
if npx tsc --noEmit >/dev/null 2>&1; then
  ok "Typecheck 通过"
else
  fail "Typecheck 失败 — 请查看上方错误输出"
  npx tsc --noEmit
  exit 1
fi

DEV_PORT=$(grep -E 'port:\s*[0-9]+' vite.config.ts 2>/dev/null | head -1 | sed -E 's/.*port:\s*([0-9]+).*/\1/')
DEV_PORT="${DEV_PORT:-5202}"
PREVIEW_URL="http://localhost:${DEV_PORT}"

cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✓ 演示项目已就绪
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  目录      ${TARGET}
  主题      ${THEME}
  预览      ${PREVIEW_URL}

  下一步
  ────────────────────────────────────────────
  开发      cd ${TARGET} && npm run dev
  旁白      npm run extract-narrations
  音频      npm run synthesize-audio
            换 TTS：PRESENTATION_TTS=<name> npm run synthesize-audio

  播放模式（URL 参数）
  ────────────────────────────────────────────
  手动      默认 — 点击 / 方向键推进
  伴音      ?audio=1 — 音频跟步，手动推进
  录屏      ?auto=1 — SPACE 启动，整片自动播完

  写章节    references/CHAPTER-CRAFT.md
  换主题    cp themes/<id>/tokens.css src/styles/tokens.css

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
