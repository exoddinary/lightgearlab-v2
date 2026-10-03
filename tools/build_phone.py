# 3D phone for the Mobile Apps hero: front screen + a clockwork back with meshing gears. Exports web/phone.glb.
#   blender -b --factory-startup --python tools/build_phone.py
#
# Objects: "Body" (rounded slab with a recessed back pocket + camera bump), "Screen" (flat plane with UVs, gets the app
# image on the page), "Gear_0".."Gear_4" (origins on their axles, axes along the phone's normal, Z here), "Pins"
# (axles + caps). The page turns the gears with the meshing rule; phone faces +Z = screen, -Z = back.
import bpy, bmesh, math, os
from mathutils import Matrix

W, H, D, R = 0.75, 1.55, 0.085, 0.13          # width, height, depth, corner radius (metres-ish units)
M = 0.016                                      # gear module
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
scene = bpy.context.scene

def obj(name, build):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); build(bm); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); return ob

def rrect(w, h, r, seg=12):
    pts = []
    for cx, cy, a0 in ((w/2-r, h/2-r, 0), (-w/2+r, h/2-r, 90), (-w/2+r, -h/2+r, 180), (w/2-r, -h/2+r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg); pts.append((cx + r*math.cos(a), cy + r*math.sin(a)))
    return pts

def prism(bm, pts, z0, z1):
    v0 = [bm.verts.new((x, y, z0)) for x, y in pts]; v1 = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(list(reversed(v0))); bm.faces.new(v1)
    n = len(pts)
    for i in range(n): bm.faces.new((v0[i], v0[(i+1) % n], v1[(i+1) % n], v1[i]))

def gear_pts(z, m):
    rp = m*z/2; ro, rr = rp + m, rp - 1.25*m; p = 2*math.pi/z; pts = []
    for i in range(z):
        a = i*p
        for f, r in ((-0.29, rr), (-0.17, ro), (0.17, ro), (0.29, rr)):
            pts.append((r*math.cos(a + f*p), r*math.sin(a + f*p)))
        for k in range(1, 4):                       # root arc to the next tooth
            t = a + 0.29*p + (0.42*p)*k/4; pts.append((rr*math.cos(t), rr*math.sin(t)))
    return pts

def boolean(target, cutter):
    md = target.modifiers.new('b', 'BOOLEAN'); md.object = cutter; md.operation = 'DIFFERENCE'; md.solver = 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.clear(); old = target.data; target.data = me; bpy.data.meshes.remove(old); bpy.data.objects.remove(cutter)

def smooth(ob, ang=30):
    for p in ob.data.polygons: p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(ang))

# body, with a pocket in the back for the movement (open, like a watch caseback window)
body = obj('Body', lambda bm: prism(bm, rrect(W, H, R, 16), -D/2, D/2))
POCKET_Y = -0.13                               # pocket sits low, clear of the camera bump
pocket = obj('c', lambda bm: prism(bm, rrect(W - 0.09, H - 0.36, R - 0.04, 16), -D/2 - 0.05, -D/2 + 0.035))
pocket.location.y = POCKET_Y
boolean(body, pocket)
bev = body.modifiers.new('bev', 'BEVEL'); bev.width = 0.012; bev.segments = 3; bev.limit_method = 'ANGLE'
dg = bpy.context.evaluated_depsgraph_get(); body.data = bpy.data.meshes.new_from_object(body.evaluated_get(dg)); body.modifiers.clear()
smooth(body)
# camera bump (top-left of the back) with two lenses
cam = obj('Camera', lambda bm: (prism(bm, rrect(0.25, 0.25, 0.07, 10), -D/2 - 0.03, -D/2 + 0.001),
                                 prism(bm, [(0.05*math.cos(t)-0.055, 0.05*math.sin(t)+0.055) for t in [i*math.pi/24 for i in range(48)]], -D/2 - 0.045, -D/2 - 0.02),
                                 prism(bm, [(0.05*math.cos(t)+0.055, 0.05*math.sin(t)-0.055) for t in [i*math.pi/24 for i in range(48)]], -D/2 - 0.045, -D/2 - 0.02)))
cam.location = (W/2 - 0.19, H/2 - 0.19, 0)     # viewed from the back this lands top-left
smooth(cam)

# screen: a plane just above the front face, UV 0..1 over the full display
def screen_build(bm):
    sw, sh = W - 0.05, H - 0.05
    pts = rrect(sw, sh, R - 0.025, 16)
    vs = [bm.verts.new((x, y, D/2 + 0.0015)) for x, y in pts]
    f = bm.faces.new(vs); uv = bm.loops.layers.uv.new()
    for l in f.loops: l[uv].uv = (l.vert.co.x/sw + 0.5, l.vert.co.y/sh + 0.5)
screen = obj('Screen', screen_build)

# gear train in the back pocket: same module, centre distance m(z1+z2)/2 (+ a hair of backlash)
plan = [(22, 0.0, 0.26), (12, 50, None), (18, 130, None), (10, 50, None), (16, 130, None)]   # zig-zag down the pocket
zb = -D/2 + 0.035                              # pocket floor
gears, cx, cy, prev = [], 0.0, 0.0, None
for i, (z, ang, y0) in enumerate(plan):
    if prev:
        d = M*(prev[0] + z)/2 + 0.08*M; t = math.radians(-ang)
        cx, cy = prev[1] + math.cos(t)*d, prev[2] + math.sin(t)*d
    else:
        cx, cy = -0.07, y0
    g = obj(f'Gear_{i}', lambda bm, z=z: prism(bm, gear_pts(z, M), -0.012, 0.0))
    hole = obj('c', lambda bm, z=z: prism(bm, [(M*z*0.16*math.cos(t), M*z*0.16*math.sin(t)) for t in [k*math.pi/16 for k in range(32)]], -0.03, 0.02))
    boolean(g, hole)
    g.location = (cx, cy, zb - 0.002 - (0.006 if i % 2 else 0))   # alternate layers so meshing teeth never touch faces
    smooth(g, 40)
    gears.append((z, cx, cy)); prev = (z, cx, cy)
def pins_build(bm):
    for z, x, y in gears:
        prism(bm, [(x + 0.012*math.cos(t), y + 0.012*math.sin(t)) for t in [k*math.pi/12 for k in range(24)]], zb - 0.026, zb + 0.001)
        prism(bm, [(x + 0.02*math.cos(t), y + 0.02*math.sin(t)) for t in [k*math.pi/3 for k in range(6)]], zb - 0.03, zb - 0.022)
pins = obj('Pins', pins_build); smooth(pins)

# check: the train has to fit inside the pocket
xs = [x for _, x, _ in gears]; ys = [y for _, _, y in gears]
print('TRAIN x %.3f..%.3f y %.3f..%.3f (pocket x ±%.3f, y %.3f..%.3f)' % (min(xs), max(xs), min(ys), max(ys), (W-0.09)/2, POCKET_Y-(H-0.36)/2, POCKET_Y+(H-0.36)/2))
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'phone.glb')
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True, export_yup=True,
                          export_draco_mesh_compression_enable=True, export_animations=False, export_materials='NONE')
print('PHONE', out, os.path.getsize(out), [(z, round(x, 3), round(y, 3)) for z, x, y in gears])
