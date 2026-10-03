# Geneva drive for the Mobile Apps page: builds the model and exports web/geneva.glb.
#   blender -b --factory-startup --python tools/build_geneva.py
#
# 4-slot Geneva: driver pin radius A, centre distance C = A / sin(pi/4), wheel radius B = C cos(pi/4).
# Objects (origins on their rotation axes, axes along +Z): "Driver" (locking disc + crank + pin + collar),
# "Geneva" (slotted wheel + collar), "Base" (plate, bosses, shafts, bolts). The page drives the rotations.
import bpy, bmesh, math, os
from mathutils import Matrix, Vector

N, A = 4, 1.0
C = A / math.sin(math.pi / N)
B = C * math.cos(math.pi / N)
PIN_R, LOCK_R, T = 0.11, 0.56, 0.18          # pin radius, locking disc radius, wheel thickness
Z0 = 0.30                                      # wheel plane (bottom) above the base top
SEG = 128

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
scene = bpy.context.scene

def mesh_obj(name, build):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); build(bm); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); return ob

def cyl(bm, r, h, x=0, y=0, z=0, seg=SEG):
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h,
                          matrix=Matrix.Translation((x, y, z + h / 2)))

def box(bm, sx, sy, sz, x=0, y=0, z=0, rot=0):
    m = Matrix.Translation((x, y, z + sz / 2)) @ Matrix.Rotation(rot, 4, 'Z') @ Matrix.Diagonal((sx, sy, sz, 1))
    bmesh.ops.create_cube(bm, size=1, matrix=m)

def hexnut(bm, r, h, x=0, y=0, z=0):
    cyl(bm, r, h, x, y, z, seg=6)

def boolean(target, cutter, op='DIFFERENCE'):
    md = target.modifiers.new('b', 'BOOLEAN'); md.object = cutter; md.operation = op; md.solver = 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.clear(); old = target.data; target.data = me; bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter)

def join(objs, name):
    bm = bmesh.new()
    for o in objs:
        tmp = o.data.copy(); tmp.transform(o.matrix_world); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    for o in objs: bpy.data.objects.remove(o)
    return mesh_obj(name, lambda b: (b.from_mesh(_m(bm)),))

def _m(bm):
    me = bpy.data.meshes.new('_t'); bm.to_mesh(me); return me

def finish(ob, angle=30):
    me = ob.data
    for p in me.polygons: p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(angle))

# ---------- Geneva wheel (centre at the origin of its own object, placed at x = C) ----------
wheel = mesh_obj('Geneva', lambda bm: cyl(bm, B + 0.08, T, z=Z0))
for k in range(N):                              # radial slots at 45° + k·90°, ending in a round
    ang = math.radians(45 + 90 * k); r0, r1 = C - A - 0.08, B + 0.4
    mid = (r0 + r1) / 2
    # (one cutter per shape: the exact solver needs closed, non-overlapping cutters)
    boolean(wheel, mesh_obj('c', lambda bm: box(bm, r1 - r0, 2 * (PIN_R + 0.02), T + 0.2, math.cos(ang) * mid, math.sin(ang) * mid, Z0 - 0.1, ang)))
    boolean(wheel, mesh_obj('c', lambda bm: cyl(bm, PIN_R + 0.02, T + 0.2, math.cos(ang) * r0, math.sin(ang) * r0, Z0 - 0.1, 48)))
for k in range(N):                              # concave locking arcs facing the driver's disc
    ang = math.radians(90 * k)
    cut = mesh_obj('c', lambda bm: cyl(bm, LOCK_R + 0.03, T + 0.2, math.cos(ang) * C, math.sin(ang) * C, Z0 - 0.1))
    boolean(wheel, cut)
boolean(wheel, mesh_obj('c', lambda bm: cyl(bm, 0.09, T + 0.2, z=Z0 - 0.1, seg=48)))
gcollar = mesh_obj('gc', lambda bm: (cyl(bm, 0.2, 0.08, z=Z0 + T, seg=64), hexnut(bm, 0.13, 0.1, z=Z0 + T + 0.08)))
geneva = join([wheel, gcollar], 'Geneva')

# ---------- Driver: locking disc with its clearance cut, crank arm above it, pin reaching down ----------
disc = mesh_obj('Driver', lambda bm: cyl(bm, LOCK_R, T, z=Z0))
boolean(disc, mesh_obj('c', lambda bm: cyl(bm, B + 0.2, T + 0.2, C, 0, Z0 - 0.1)))
arm = mesh_obj('arm', lambda bm: (box(bm, A, 0.2, 0.09, A / 2, 0, Z0 + T + 0.02),
                                  cyl(bm, 0.1, 0.09, A, 0, Z0 + T + 0.02, 64),
                                  cyl(bm, PIN_R, T + 0.06, A, 0, Z0 - 0.02, 64),
                                  cyl(bm, 0.2, 0.11, z=Z0 + T, seg=64), hexnut(bm, 0.13, 0.1, z=Z0 + T + 0.11)))
driver = join([disc, arm], 'Driver')

# ---------- Base: plate, bearing bosses, shafts, corner bolts ----------
def base_build(bm):
    box(bm, C + 2.0, 2.3, 0.16, C / 2, 0, -0.16)
    for x in (0, C):
        cyl(bm, 0.3, Z0 - 0.04, x, 0, 0, 64)        # boss
        cyl(bm, 0.085, Z0 + T + 0.2, x, 0, 0, 48)   # shaft
    for x in (-0.7, C + 0.7):
        for y in (-0.9, 0.9):
            hexnut(bm, 0.09, 0.06, x, y, 0)
base = mesh_obj('Base', base_build)
bev = base.modifiers.new('bev', 'BEVEL'); bev.width = 0.02; bev.segments = 2; bev.limit_method = 'ANGLE'
dg = bpy.context.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(base.evaluated_get(dg)); base.modifiers.clear(); base.data = me

# origins on the rotation axes
geneva.location = (C, 0, 0)   # (the wheel is built around its own axis)
for ob in (geneva, driver, base): finish(ob)

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'geneva.glb')
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True, export_yup=True,
                          export_draco_mesh_compression_enable=True, export_animations=False, export_materials='NONE')
print('GENEVA', out, os.path.getsize(out), 'C=%.4f B=%.4f' % (C, B),
      {o.name: len(o.data.polygons) for o in (geneva, driver, base)})
