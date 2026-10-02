"""Self-check for the LightGearLab engine.

Blender -b /path/engine.blend --python tools/check_engine.py [-- --frames 30]

Checks, at many frames across the loop:
  * every meshing pair (spur, helical, bevel, sun-planet, planet-ring) has zero
    triangle overlaps AND real engagement (teeth interleave by ~2 modules)
  * no moving part overlaps the static frame or any other part, including parts
    on its own shaft (shafts sit in bores with clearance, so nothing is exempt)
  * con-rod eyes stay on the crank pin / wrist pin centres
  * frame 1 and frame FRAMES+1 are the same pose: base meshes as point sets AND
    the evaluated (Bevel-modifier) surfaces by surface-to-surface distance
  * no gear's teeth move more than MAX_PITCH tooth pitches per frame (wagon-wheel aliasing)
  * gear meshes are manifold with outward normals, all drivers are simple
Exit code 0 = all pass, 1 = failure.
"""
import bpy
import bmesh
import json
import math
import sys
import time
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
N_FRAMES = 48
LOOP_SURF_TOL = 5e-4      # 0.5 mm, about 0.2 px at 1080 px for the hero framing
MAX_PITCH = 0.4
if "--frames" in argv:
    N_FRAMES = int(argv[argv.index("--frames") + 1])

scene = bpy.context.scene
meta = json.loads(scene["lge_meta"])
F = meta["frames"]
OBJ = meta["objects"]
GEARS = meta["gears"]
PAIRS = meta["pairs"]
fails = []
t_start = time.time()


def log(*a):
    print("[CHECK]", *a)


def world_mesh(ob, dg):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world.copy()
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return verts, polys


def aabb(verts):
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def aabb_hit(a, b, pad=1e-4):
    return all(a[i] <= b[i + 3] + pad and b[i] <= a[i + 3] + pad for i in range(3))


def axis_of(ob):
    mw = ob.matrix_world
    return mw.translation.copy(), (mw.to_3x3() @ Vector((0, 0, 1))).normalized()


def dist_to_axis(p, o, u):
    d = p - o
    return (d - u * d.dot(u)).length


objs = {n: bpy.data.objects[n] for n in OBJ if n in bpy.data.objects}
missing = [n for n in OBJ if n not in bpy.data.objects]
if missing:
    fails.append("missing objects: %s" % missing)

# ------------------------------------------------------------ static checks
bad_drv = []
n_drv = 0
for ob in list(objs.values()) + [bpy.data.objects.get("ENGINE_Controller")]:
    if ob is None or ob.animation_data is None:
        continue
    for fc in ob.animation_data.drivers:
        n_drv += 1
        if not fc.driver.is_simple_expression:
            bad_drv.append((ob.name, fc.data_path, fc.driver.expression))
log("drivers: %d, non-simple: %d" % (n_drv, len(bad_drv)))
if bad_drv:
    fails.append("non-simple drivers %s" % bad_drv)

for name in GEARS:
    ob = objs[name]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume(signed=True)
    bm.free()
    ok = nm == 0 and vol > 0
    if not ok:
        fails.append("gear mesh %s: non-manifold edges %d, signed volume %.6f" % (name, nm, vol))
log("gear meshes manifold with outward normals: %s" % ("OK" if not any("gear mesh" in f for f in fails) else "FAIL"))

# ------------------------------------------------------------ per-frame checks
groups = {}
for n, d in OBJ.items():
    groups.setdefault(d["group"], []).append(n)
moving = [n for n, d in OBJ.items() if d["moving"] and n in objs]
static = [n for n, d in OBJ.items() if not d["moving"] and n in objs]

frames = sorted(set(1 + int(round(i * F / N_FRAMES)) + (i % 3) for i in range(N_FRAMES)))
frames = [f for f in frames if f <= F]
dg = bpy.context.evaluated_depsgraph_get()
scene.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
static_data = {}
for n in static:
    v, p = world_mesh(objs[n], dg)
    static_data[n] = (BVHTree.FromPolygons(v, p), aabb(v))

pair_stats = {(p["a"], p["b"]): {"ov": 0, "eng": []} for p in PAIRS}
clash = {}
rod_err = 0.0
for f in frames:
    scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    data = {}
    for n in moving:
        v, p = world_mesh(objs[n], dg)
        data[n] = (BVHTree.FromPolygons(v, p), aabb(v), v)
    alld = dict(static_data)
    alld.update({k: (d[0], d[1]) for k, d in data.items()})
    # meshing pairs
    for pr in PAIRS:
        a, b = pr["a"], pr["b"]
        ba = alld[a][0]
        bb = alld[b][0]
        ov = len(ba.overlap(bb))
        pair_stats[(a, b)]["ov"] += ov
        ga, gb = GEARS[a], GEARS[b]
        oa, ua = axis_of(objs[a])
        ob_, ub = axis_of(objs[b])
        if pr["type"] == "external":
            vb = data[b][2] if b in data else world_mesh(objs[b], dg)[0]
            va = data[a][2] if a in data else world_mesh(objs[a], dg)[0]
            d1 = ga["ra"] - min(dist_to_axis(p, oa, ua) for p in vb)
            d2 = gb["ra"] - min(dist_to_axis(p, ob_, ub) for p in va)
            mod = ga.get("mn", ga["m"])
            eng = min(d1, d2) / mod
        elif pr["type"] == "internal":
            vb = data[b][2]
            d1 = max(dist_to_axis(p, oa, ua) for p in vb) - ga["ra"]
            eng = d1 / ga["m"]
        else:  # bevel: angular penetration of B into A's tip cone (and vice versa)
            va = data[a][2]
            vb = data[b][2]
            apex = oa

            def pen(g, u, verts):
                tip = g["delta"] + math.atan(g["m"] / g["A"])
                mn = min(math.acos(max(-1, min(1, (p - apex).normalized().dot(u)))) for p in verts if (p - apex).length > 1e-6)
                return (tip - mn) * g["A"]
            eng = min(pen(ga, ua, vb), pen(gb, ub, va)) / ga["m"]
        pair_stats[(a, b)]["eng"].append(eng)
    # general clash test between different rigid bodies
    names = list(alld.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            na, nb = names[i], names[j]
            if not OBJ[na]["moving"] and not OBJ[nb]["moving"]:
                continue
            if not aabb_hit(alld[na][1], alld[nb][1]):
                continue
            ov = len(alld[na][0].overlap(alld[nb][0]))
            if ov:
                key = (na, nb)
                c = clash.setdefault(key, [0, []])
                c[0] += ov
                c[1].append(f)
    # rod eyes
    for r in meta["rods"]:
        rod = objs[r["rod"]]
        crank = objs[r["crank"]]
        pis = objs[r["piston"]]
        big = rod.matrix_world @ Vector((0, 0, -r["L"]))
        pin = crank.matrix_world @ Vector(r["pin_local"])
        small = rod.matrix_world.translation
        wrist = pis.matrix_world.translation
        rod_err = max(rod_err, (big - pin).length, (small - wrist).length)

# non-meshing external gears sharing a depth layer need tip-circle clearance
meshing = {(p["a"], p["b"]) for p in PAIRS} | {(p["b"], p["a"]) for p in PAIRS}
tip_min = None
for f in frames[:6]:
    scene.frame_set(f)
    names_g = [n for n, g in GEARS.items() if g["type"] not in ("bevel", "ring") and "face" in g]
    for i in range(len(names_g)):
        for j in range(i + 1, len(names_g)):
            a, b = names_g[i], names_g[j]
            if (a, b) in meshing:
                continue
            oa, ua = axis_of(objs[a])
            ob_, ub = axis_of(objs[b])
            if abs(ua.dot(ub)) < 0.999:
                continue
            axial = abs((ob_ - oa).dot(ua))
            if axial > (GEARS[a]["face"] + GEARS[b]["face"]) / 2:
                continue                      # different depth layers
            gap = dist_to_axis(ob_, oa, ua) - GEARS[a]["ra"] - GEARS[b]["ra"]
            if tip_min is None or gap < tip_min[0]:
                tip_min = (gap, a, b)
if tip_min is not None:
    log("same-layer non-meshing tip clearance: min %.4f (%s / %s)" % tip_min)
    if tip_min[0] <= 0.005:
        fails.append("tip clearance %.4f %s/%s" % tip_min)

log("frames tested (%d): %s" % (len(frames), frames))
log("%-34s %-9s %9s %10s %10s" % ("meshing pair", "type", "overlaps", "eng_min/m", "eng_max/m"))
for pr in PAIRS:
    st = pair_stats[(pr["a"], pr["b"])]
    emin, emax = min(st["eng"]), max(st["eng"])
    ok = st["ov"] == 0 and emin > 1.0
    log("%-34s %-9s %9d %10.3f %10.3f %s" % (pr["a"] + " / " + pr["b"], pr["type"], st["ov"], emin, emax,
                                            "OK" if ok else "FAIL"))
    if not ok:
        fails.append("pair %s/%s overlaps=%d engagement_min=%.3f m" % (pr["a"], pr["b"], st["ov"], emin))
if clash:
    for (a, b), (n, fr) in sorted(clash.items()):
        log("CLASH %s <-> %s : %d tri pairs, frames %s" % (a, b, n, fr[:8]))
        fails.append("clash %s <-> %s" % (a, b))
else:
    log("no clashes between rigid bodies / frame (%d moving, %d static objects)" % (len(moving), len(static)))
log("max con-rod eye error: %.2e" % rod_err)
if rod_err > 1e-4:
    fails.append("rod eye error %.2e" % rod_err)

# ------------------------------------------------------------ loop closure
def pose_points(f):
    scene.frame_set(f)
    pts = {}
    for n in moving:
        ob = objs[n]
        mw = ob.matrix_world
        eq = OBJ[n]["equiv"]
        pts.setdefault(eq, []).extend(mw @ v.co for v in ob.data.vertices)
    return pts


p1 = pose_points(1)
p2 = pose_points(F + 1)
worst = (0.0, "")
for eq, pts in p1.items():
    kd = KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    d = max(kd.find(q)[2] for q in p2[eq])
    if d > worst[0]:
        worst = (d, eq)
log("loop closure frame 1 vs %d, base meshes: max point deviation %.2e (%s)" % (F + 1, worst[0], worst[1] or "-"))
if worst[0] > 1e-4:
    fails.append("loop closure deviation %.2e on %s" % worst)


def eval_surfaces(f):
    scene.frame_set(f)
    dg_ = bpy.context.evaluated_depsgraph_get()
    out = {}
    for n in moving:
        v, p = world_mesh(objs[n], dg_)
        d = out.setdefault(OBJ[n]["equiv"], ([], []))
        base = len(d[0])
        d[0].extend(v)
        d[1].extend(tuple(i + base for i in poly) for poly in p)
    return out


s1 = eval_surfaces(1)
s2 = eval_surfaces(F + 1)
worst = (0.0, "")
for eq in s1:
    for (va, pa), (vb, pb) in ((s1[eq], s2[eq]), (s2[eq], s1[eq])):
        tree = BVHTree.FromPolygons(va, pa)
        d = max(tree.find_nearest(q)[3] for q in vb)
        if d > worst[0]:
            worst = (d, eq)
log("loop closure frame 1 vs %d, evaluated surfaces: max surface distance %.2e (%s)" % (F + 1, worst[0], worst[1] or "-"))
if worst[0] > LOOP_SURF_TOL:
    fails.append("evaluated loop closure surface distance %.2e on %s" % worst)

# wagon-wheel guard: tooth motion per frame, measured from the evaluated world matrices
scene.frame_set(1)
m1 = {n: objs[n].matrix_world.to_quaternion() for n in GEARS}
scene.frame_set(2)
fastest = (0.0, "")
for n, g_ in GEARS.items():
    q = objs[n].matrix_world.to_quaternion().rotation_difference(m1[n])
    ang = abs(q.angle)
    ang = min(ang, 2 * math.pi - ang)
    fr = ang * g_["z"] / (2 * math.pi)
    fastest = max(fastest, (fr, n))
log("fastest tooth motion: %.3f pitch/frame (%s), limit %.2f" % (fastest[0], fastest[1], MAX_PITCH))
if fastest[0] > MAX_PITCH:
    fails.append("teeth move %.3f pitch/frame on %s (aliasing)" % fastest)
scene.frame_set(1)

log("time %.1fs" % (time.time() - t_start))
if fails:
    log("RESULT: FAIL (%d)" % len(fails))
    for f_ in fails:
        log("  -", f_)
    sys.exit(1)
log("RESULT: ALL CHECKS PASSED")
sys.exit(0)
