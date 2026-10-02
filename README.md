# LightGearLab v2: engine cube

An animated "engine in a cube" (pistons, crankshaft, and spur, helical, bevel and planetary gears), built in Blender and told as a scroll story on the web with three.js + GSAP.

## Web

```bash
python3 -m http.server 8123 --directory web
```

Then open http://localhost:8123. The page has to be served over http, because browsers block loading `engine.glb` from a file.

- `web/index.html`: the whole experience (three.js 0.170 + GSAP 3.13 from CDN)
- `web/engine.glb`: the model, exported from Blender
- `web/lgl_logo.svg`: the LightGearLab logo

The scroll story runs: projection hero, the machine (process cards), strengths, any stack, take it apart, build it again, then the call to action.

## Blender

- `build_engine.py`: builds the whole model procedurally (Blender 5.2)
- `engine.blend`: the built model
- `tools/export_glb.py`: re-exports `web/engine.glb` from `engine.blend`
- `tools/check_engine.py`: gear mesh, clash and loop checks
- `tools/shot.mjs`: headless Chrome screenshots of the page

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b engine.blend --python tools/export_glb.py
```
