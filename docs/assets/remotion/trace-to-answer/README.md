# Lerim Trace-To-Answer Motion

This Remotion project renders the public `docs/assets/lerim-trace-to-answer.gif`
asset used by the GitHub README.

The storyboard is Lerim-specific:

1. completed source sessions arrive
2. trace ribbons flow into the compiler core
3. the compiler filters, extracts, cites, and ranks
4. typed context records assemble into a lattice
5. a future agent receives cited context

## Render

```bash
npm install
npm run render
ffmpeg -y -i out/lerim-trace-to-answer.mp4 \
  -vf "fps=18,scale=960:-1:flags=lanczos,palettegen=stats_mode=diff" \
  out/palette.png
ffmpeg -y -i out/lerim-trace-to-answer.mp4 -i out/palette.png \
  -lavfi "fps=18,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" \
  ../../lerim-trace-to-answer.gif
```
