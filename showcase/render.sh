#!/bin/sh
# Renders the showcase inside the Playwright image (Chromium + all system deps included):
#   docker run --rm -v "$PWD/showcase:/sc" -v showcase-nm:/w/node_modules \
#     mcr.microsoft.com/playwright:v1.65.1-noble sh /sc/render.sh [stills|video]
set -e
mkdir -p /w && cd /sc && tar --exclude=./node_modules --exclude=./out -cf - . | (cd /w && tar xf -)
cd /w
[ -d node_modules/remotion ] || npm ci --no-audit --no-fund
SHELL_BIN=$(ls -d /ms-playwright/chromium_headless_shell-*/chrome-*/headless_shell 2>/dev/null | head -1)
[ -n "$SHELL_BIN" ] || SHELL_BIN=$(ls -d /ms-playwright/chromium-*/chrome-linux*/chrome | head -1)
echo "browser: $SHELL_BIN"
node scripts/music.mjs 100
mkdir -p /sc/out
if [ "$1" = "stills" ]; then
  for f in 60 220 420 700 950 1150 1330 1560 1760 1950 2130; do
    npx remotion still Showcase /sc/out/still-$f.png --frame=$f --scale=0.5 \
      --browser-executable="$SHELL_BIN" 2>&1 | tail -1
  done
else
  npx remotion render Showcase /sc/out/showcase.mp4 --codec=h264 --crf=21 --concurrency=6 \
    --browser-executable="$SHELL_BIN" 2>&1 | tail -3
fi
