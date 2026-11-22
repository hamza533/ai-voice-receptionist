# Showcase video (Remotion)

A ~75-second product video built from **real screenshots of the running app** plus an
animated recreation of the in-call screen. Output: `docs/images/showcase.mp4` and
`docs/images/demo.gif`.

## Regenerate

1. Start the stack with demo data and the e2e admin:
   ```bash
   docker compose up -d --build
   docker compose exec api python -m app.seed --demo --reset
   echo "luma-e2e-owner-pass" | docker compose exec -T api python -m app.cli create-admin --email owner@luma.example.com
   ```
2. Capture screenshots (writes `public/shots/*.png`):
   ```bash
   docker run --rm --network ai-voice-receptionist_default -v "$PWD/showcase:/sc" \
     -e BASE=http://web:3000 mcr.microsoft.com/playwright:v1.65.1-noble \
     sh -c "cd /tmp && npm i playwright@1.65.1 && node /sc/capture/capture.mjs /sc/public/shots"
   ```
3. Render (generates the original music bed in `public/music.wav` first):
   ```bash
   docker run --rm -v "$PWD/showcase:/sc" node:22-bookworm sh /sc/render.sh video
   ```

Preview interactively with `npm i && npx remotion studio`.

- `scripts/music.mjs` synthesises an original, royalty-free soundtrack.
- Sound effects are Remotion's public SFX (`remotion.media`).
- Remotion is free for individuals and teams of up to 3 (see remotion.dev/license).
