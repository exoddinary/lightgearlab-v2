# 3D LightGearLab logo for the menu: a moving gear socketed into the front of a cylindrical holder, a glass bulb inside
# with the zig-zag filament, and the screw base coming out of the back. Exports web/bulb.glb.
#   blender -b --factory-startup --python tools/build_bulb.py
#
# Axis along Blender +Y (front = -Y, so in three.js the front faces +Z); up is +Z.
# Objects: Bulb_Gear (turns about the axis), Bulb_Holder, Bulb_Glass, Bulb_Filament (glows), Bulb_Wires, Bulb_Base, Bulb_Threads.
import bpy, bmesh, math, os
from mathutils import Matrix, Vector

for o in list(bpy.data.objects): bpy.data.objects.remove(o)
scene = bpy.context.scene
SEG = 96
Z_TEETH, R_TIP, R_ROOT, R_HOLE = 12, 1.0, 0.84, 0.6      # gear proportions taken from the logo

def obj(name, build):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); build(bm); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); return ob

def ring_prism(bm, outer, inner, y0, y1):
    """Closed 2D outline (x, z) with one hole, extruded along y: a ring face, plus side walls."""
    def loop(pts, y): return [bm.verts.new((x, y, z)) for x, z in pts]
    o0, o1, i0, i1 = loop(outer, y0), loop(outer, y1), loop(inner, y0), loop(inner, y1)
    n, m = len(outer), len(inner)
    for i in range(n): bm.faces.new((o0[i], o1[i], o1[(i + 1) % n], o0[(i + 1) % n]))
    for i in range(m): bm.faces.new((i0[i], i0[(i + 1) % m], i1[(i + 1) % m], i1[i]))
    bm.verts.ensure_lookup_table()
    # caps: bridge outer and inner loops by angle (both loops are ordered by angle)
    for cap0, cap1, flip in ((o0, i0, True), (o1, i1, False)):
        k = 0
        for i in range(n):
            a = math.atan2(cap0[i].co.z, cap0[i].co.x)
            while k < m - 1 and math.atan2(cap1[(k + 1) % m].co.z, cap1[(k + 1) % m].co.x) % (2 * math.pi) <= a % (2 * math.pi) and False: k += 1
        bmesh.ops.bridge_loops(bm, edges=[]) if False else None
    return o0, o1, i0, i1

def annulus_faces(bm, o, i, flip):
    """Triangulate the band between two angle-ordered loops."""
    n, m = len(o), len(i)
    ang = lambda v: math.atan2(v.co.z, v.co.x) % (2 * math.pi)
    a, b = 0, 0
    oa = sorted(range(n), key=lambda k: ang(o[k])); ia = sorted(range(m), key=lambda k: ang(i[k]))
    while a < n or b < m:
        oi, ii = oa[a % n], ia[b % m]
        if b >= m or (a < n and ang(o[oa[(a + 1) % n]]) + (2 * math.pi if a + 1 >= n else 0) < ang(i[ia[(b + 1) % m]]) + (2 * math.pi if b + 1 >= m else 0)):
            tri = (o[oi], o[oa[(a + 1) % n]], i[ii]); a += 1
        else:
            tri = (o[oi], i[ia[(b + 1) % m]], i[ii]); b += 1
        try: bm.faces.new(tuple(reversed(tri)) if flip else tri)
        except ValueError: pass

def gear_outline(z, rt, rr):
    p = 2 * math.pi / z; pts = []
    for k in range(z):
        c = math.pi / 2 + k * p                           # a tooth straight up, like the logo
        for f, r in ((-0.5, rr), (-0.36, rr), (-0.24, rt), (0.24, rt), (0.36, rr)):
            a = c + f * p; pts.append((r * math.cos(a), r * math.sin(a)))
    return pts

def circle(r, n=SEG, a0=0.0): return [(r * math.cos(a0 + 2 * math.pi * k / n), r * math.sin(a0 + 2 * math.pi * k / n)) for k in range(n)]

def ring_obj(name, outer, inner, y0, y1):
    def build(bm):
        o0, o1, i0, i1 = ring_prism(bm, outer, inner, y0, y1)
        annulus_faces(bm, o0, i0, True); annulus_faces(bm, o1, i1, False)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(name, build)

def lathe(name, profile, seg=SEG, axis_y=True):
    """Solid of revolution about the Y axis; profile = [(r, y), ...] from front to back."""
    def build(bm):
        rings = []
        for r, y in profile:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / seg), y, r * math.sin(2 * math.pi * k / seg))) for k in range(seg)] if r > 1e-6 else [bm.verts.new((0, y, 0))])
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1 and len(b) == 1: continue      # two centre points in a row (the profile crosses the axis)
            if len(a) == 1: [bm.faces.new((a[0], b[(k + 1) % seg], b[k])) for k in range(seg)]
            elif len(b) == 1: [bm.faces.new((a[k], a[(k + 1) % seg], b[0])) for k in range(seg)]
            else: [bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k])) for k in range(seg)]
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(name, build)

def smooth(ob, ang=35):
    for p in ob.data.polygons: p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(ang))

def bevel(ob, w=0.012):
    md = ob.modifiers.new('bev', 'BEVEL'); md.width = w; md.segments = 2; md.limit_method = 'ANGLE'
    dg = bpy.context.evaluated_depsgraph_get(); ob.data = bpy.data.meshes.new_from_object(ob.evaluated_get(dg)); ob.modifiers.clear()

# Proportions measured off the logo (gear tip radius = 1): glass circle 0.69, filament across ±0.39 near the middle,
# base from the bottom of the circle down to -1.5, tapering 0.39 -> 0.27, with four slanted stripes.
R_HOLE = 0.69
# --- the moving gear: front plate, y -0.14..0
gear = ring_obj('Bulb_Gear', gear_outline(Z_TEETH, R_TIP, R_ROOT), circle(R_HOLE, 96, math.pi / 2), -0.14, 0.0)
bevel(gear); smooth(gear)

# --- holder: a short closed cylinder behind the gear, with a front lip the gear is socketed onto
holder = lathe('Bulb_Holder', [(R_HOLE, 0.0), (0.8, 0.0), (0.8, 0.03), (0.76, 0.05), (0.76, 0.34), (0.8, 0.36), (0.8, 0.42),
                                (0.0, 0.42), (0.0, 0.36), (0.72, 0.36), (0.72, 0.05), (R_HOLE, 0.05), (R_HOLE, 0.0)])
smooth(holder)
def screws(bm):
    for k in range(6):
        a = math.pi / 6 + k * math.pi / 3
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.04, radius2=0.04, depth=0.03,
                              matrix=Matrix.Translation((0.55 * math.cos(a), 0.435, 0.55 * math.sin(a))) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
# (no rear screws: they'd show through the glass as dots)

# --- glass: a dome bulging out through the gear's opening, closed into the holder behind
GR, GC = 0.66, -0.3                         # bulb radius and centre: it bulges ~0.8 in front of the gear face
glass_prof = [(0.0, GC - GR)] + [(GR * math.sin(t), GC - GR * math.cos(t)) for t in [i * math.pi / 22 for i in range(1, 15)]]
neck = glass_prof[-1][0]                    # past the equator, close in to the neck that passes through the gear
glass_prof += [(neck, 0.0), (neck, 0.34), (0.0, 0.34)]
glass = lathe('Bulb_Glass', glass_prof); smooth(glass, 60)

def wire(name, pts, r):
    """A round wire along a polyline."""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 3
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p, (x, y, z) in zip(sp.points, pts): p.co = (x, y, z, 1)
    ob = bpy.data.objects.new(name, cu); scene.collection.objects.link(ob)
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg)); bpy.data.objects.remove(ob); bpy.data.curves.remove(cu)
    m = bpy.data.objects.new(name, me); scene.collection.objects.link(m); return m

BY = 0.24
# --- filament: the logo's zig-zag across the middle, two support wires straight down into the base
zig, W, top, bot, yF = [], 0.36, 0.13, -0.08, GC
peaks = 5
for i in range(2 * peaks + 1):
    zig.append((-W + 2 * W * i / (2 * peaks), yF, top if i % 2 else bot))
filament = wire('Bulb_Filament', zig, 0.016); smooth(filament, 80)
leads = [wire('lead', [(s * W, yF, bot), (s * W * 0.95, yF + 0.05, -0.32), (s * 0.3, 0.05, -0.52), (s * 0.24, BY, -0.62)], 0.011) for s in (-1, 1)]
bm = bmesh.new()
for o in leads: bm.from_mesh(o.data); bpy.data.objects.remove(o)
me = bpy.data.meshes.new('Bulb_Wires'); bm.to_mesh(me); bm.free()
wires = bpy.data.objects.new('Bulb_Wires', me); scene.collection.objects.link(wires); smooth(wires, 80)

# --- the screw base (the logo's "tail"): below the circle, in front of the gear so the turning teeth pass behind it.
# A solid of revolution about the vertical axis, flattened front-to-back so it clears the gear plane.
BY, FLAT = 0.24, 0.5                        # base centre depth: the middle of the holder (y 0..0.42), clear of the gear
def vlathe(name, profile, seg=SEG):
    """Solid of revolution about the vertical (Z) axis; profile = [(r, z), ...] top to bottom."""
    def build(bm):
        rings = []
        for r, z in profile:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / seg), BY + FLAT * r * math.sin(2 * math.pi * k / seg), z)) for k in range(seg)]
                         if r > 1e-6 else [bm.verts.new((0, BY, z))])
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1: [bm.faces.new((a[0], b[k], b[(k + 1) % seg])) for k in range(seg)]
            elif len(b) == 1: [bm.faces.new((a[k], b[0], a[(k + 1) % seg])) for k in range(seg)]
            else: [bm.faces.new((a[k], b[k], b[(k + 1) % seg], a[(k + 1) % seg])) for k in range(seg)]
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(name, build)
base_prof = [(0.0, -0.5), (0.3, -0.5), (0.36, -0.6), (0.39, -0.76), (0.385, -0.82)] + \
            [(0.385 - (0.385 - 0.27) * (i / 10), -0.82 - 0.56 * i / 10) for i in range(1, 11)] + \
            [(0.27 * math.cos(t), -1.38 - 0.12 * math.sin(t)) for t in [i * math.pi / 2 / 8 for i in range(1, 9)]]
base = vlathe('Bulb_Base', base_prof); smooth(base, 40)
def threads(bm):
    n = 72
    for k in range(4):                                   # slanted bands, rising to the right like the logo's stripes
        zc = -0.95 - k * 0.12
        r = 0.385 - (0.385 - 0.27) * ((-0.82 - zc) / 0.56) + 0.014
        ring = []
        for j in range(n):
            a = 2 * math.pi * j / n
            x, yo = r * math.cos(a), FLAT * r * math.sin(a)
            z = zc + 0.05 * (x / r)
            ring.append([bm.verts.new((x * (1 + dr / r), BY + yo * (1 + dr / r), z + dz))
                         for dr, dz in ((-0.006, -0.024), (0.028, -0.012), (0.028, 0.012), (-0.006, 0.024))])
        for j in range(n):
            a0, a1 = ring[j], ring[(j + 1) % n]
            for q in range(4):
                bm.faces.new((a0[q], a1[q], a1[(q + 1) % 4], a0[(q + 1) % 4]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
thr = obj('Bulb_Threads', threads); smooth(thr, 60)

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'bulb.glb')
for o in scene.objects: o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                          export_animations=False, export_materials='NONE', export_draco_mesh_compression_enable=True)
print('BULB', out, os.path.getsize(out), {o.name: len(o.data.polygons) for o in scene.objects})
