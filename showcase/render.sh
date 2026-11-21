#!/bin/sh
# Renders inside node:22-bookworm: sh render.sh [stills|video]
set -e
apt-get update -qq >/dev/null && apt-get install -y -qq libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 libxkbcommon-dev libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 fonts-noto-color-emoji >/dev/null
mkdir -p /w && cd /sc && tar --exclude=./node_modules --exclude=./out -cf - . | (cd /w && tar xf -)
cd /w
node scripts/music.mjs 76
mkdir -p /sc/out
if [ "$1" = "stills" ]; then
  for f in 60 220 420 700 950 1150 1330 1560 1760 1950 2130; do
    npx remotion still Showcase /sc/out/still-$f.png --frame=$f --scale=0.5 2>&1 | tail -1
  done
else
  npx remotion render Showcase /sc/out/showcase.mp4 --codec=h264 --crf=18 --concurrency=6 2>&1 | tail -3
fi
