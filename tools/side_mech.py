# Side mechanism for the closed right-hand panel (Panel_Right, outer face at x = PANEL_X): a crank gear whose pin
# rides in a slotted rocker; a toothed sector on the rocker rolls a rack back and forth in a guide.
# Called from tools/export_glb.py (engine.blend itself is not changed). The page animates it (index.html).
#
# Objects (Blender coords; the panel plane is y/z, normal +X; viewed from outside, +y is to the right):
#   Side_Gear   origin on the gear axle; crank pin at +Z (r = CRANK_R) at rest
#   Side_Rocker origin on the pivot; arm along +Z at rest; sector teeth around -Z
#   Side_Rack   origin on the rack's pitch line, under the pivot; slides along y
#   Side_Base   fixed: rack guide, bosses, axle caps, screws
# Kinematics (page): rocker angle a = atan2(r sin t, D + r cos t) about the panel normal; rack moves -SECTOR_R * a.
import bpy, bmesh, math
from mathutils import Matrix

PANEL_X = 0.88                 # outer face of Panel_Right
M = 0.022                      # module, shared by sector and rack so they mesh
Z_GEAR, Z_SECTOR = 28, 24      # crank gear teeth; teeth of the full circle the sector is cut from
GEAR_YZ = (-0.42, 1.42)        # gear axle (y, z); left of the vents (vents are at y 0.03..0.58, z 0.32..0.78)
PIVOT_YZ = (-0.42, 0.92)       # rocker pivot, straight below the gear
CRANK_R = 0.2                  # crank pin radius on the gear
D = GEAR_YZ[1] - PIVOT_YZ[1]   # gear axle to pivot (0.5): rocker swings ±asin(r/D) ≈ ±23.6°
SECTOR_R = M * Z_SECTOR / 2    # sector pitch radius (0.264)
SECTOR_HALF = math.radians(42)
SEG = 96

def _obj(name, build, mat):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); build(bm); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    return ob

def _prism(bm, pts, x0, x1):
    """2D outline (y, z) extruded along x."""
    v0 = [bm.verts.new((x0, y, z)) for y, z in pts]; v1 = [bm.verts.new((x1, y, z)) for y, z in pts]
    bm.faces.new(list(reversed(v0))); bm.faces.new(v1)
    n = len(pts)
    for i in range(n): bm.faces.new((v0[i], v0[(i + 1) % n], v1[(i + 1) % n], v1[i]))

def _circle(r, cy=0.0, cz=0.0, n=SEG):
    return [(cy + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]

def _rect(y0, z0, y1, z1):
    return [(y0, z0), (y1, z0), (y1, z1), (y0, z1)]

def _tooth_ring(z, m, a0, a1, offset):
    """Involute-ish trapezoid teeth from angle a0 to a1 (radians); a tooth gap centred at `offset`."""
    rp = m * z / 2; ro, rr = rp + m, rp - 1.25 * m; p = 2 * math.pi / z; pts = []
    k0, k1 = math.floor((a0 - offset) / p), math.ceil((a1 - offset) / p)
    for k in range(k0, k1 + 1):
        c = offset + (k + 0.5) * p                     # tooth centre (gaps at offset + k·p)
        for f, r in ((-0.29, rr), (-0.17, ro), (0.17, ro), (0.29, rr)):
            a = c + f * p
            if a0 <= a <= a1: pts.append((r * math.cos(a), r * math.sin(a)))
    return pts

def _gear_outline(z, m):
    return _tooth_ring(z, m, -math.pi, math.pi - 1e-6, -math.pi / z)   # a tooth on +y

def _boolean(target, cutter, op='DIFFERENCE'):
    bpy.context.scene.collection.objects.link(target) if not target.users_collection else None
    bpy.context.scene.collection.objects.link(cutter)
    md = target.modifiers.new('b', 'BOOLEAN'); md.object = cutter; md.operation = op; md.solver = 'EXACT'
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.clear(); old = target.data; target.data = me; bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter)

def _finish(ob, angle=30):
    for p in ob.data.polygons: p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(angle))

def _mat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    if m.node_tree:
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        if bsdf: bsdf.inputs['Base Color'].default_value = (*rgb, 1)
    return m

def build(collection):
    steel = bpy.data.materials.get('LGE_Steel') or _mat('LGE_Steel', (0.24, 0.23, 0.22))
    frame = bpy.data.materials.get('LGE_Frame') or _mat('LGE_Frame', (0.69, 0.66, 0.6))
    accent = _mat('LGE_SideGear', (0.72, 0.36, 0.12))
    X = PANEL_X
    gy, gz = GEAR_YZ; py, pz = PIVOT_YZ

    # --- crank gear (layer x 0.895..0.93): rim + web with lightening holes, crank pin reaching through the rocker slot
    gear = _obj('Side_Gear', lambda bm: _prism(bm, _gear_outline(Z_GEAR, M), X + 0.015, X + 0.05), accent)
    rp = M * Z_GEAR / 2
    for k in range(6):
        a = math.pi / 6 + k * math.pi / 3
        if abs(math.cos(a) - 0) < 1e-6 and math.sin(a) > 0: continue
        cy, cz = 0.62 * rp * math.cos(a), 0.62 * rp * math.sin(a)
        if abs(cy) < 0.02 and cz > 0: continue
        _boolean(gear, _obj('c', lambda bm, cy=cy, cz=cz: _prism(bm, _circle(0.055, cy, cz, 48), X, X + 0.07), steel))
    pin = _obj('p', lambda bm: (_prism(bm, _circle(0.022, 0, CRANK_R, 40), X + 0.045, X + 0.105),
                                _prism(bm, _circle(0.034, 0, CRANK_R, 40), X + 0.097, X + 0.109)), steel)
    gear_parts = [gear, pin]

    # --- rocker (layer x 0.94..0.97): pivot hub, slotted arm up, sector frame down, teeth on the sector arc
    T0, T1 = X + 0.06, X + 0.09
    rocker = _obj('Side_Rocker', lambda bm: _prism(bm, _circle(0.075, 0, 0, 64), T0, T1), steel)
    arm_top = D + CRANK_R + 0.07
    _boolean(rocker, _obj('c', lambda bm: _prism(bm, _rect(-0.055, 0.02, 0.055, arm_top), T0, T1), steel), 'UNION')
    _boolean(rocker, _obj('c', lambda bm: _prism(bm, _circle(0.055, 0, arm_top, 48), T0, T1), steel), 'UNION')
    teeth = _tooth_ring(Z_SECTOR, M, -math.pi / 2 - SECTOR_HALF, -math.pi / 2 + SECTOR_HALF, -math.pi / 2)
    r_in = SECTOR_R - 1.25 * M - 0.07
    inner_arc = [(r_in * math.cos(a), r_in * math.sin(a)) for a in
                 [(-math.pi / 2 + SECTOR_HALF) - 2 * SECTOR_HALF * i / 40 for i in range(41)]]
    sector_pts = teeth + inner_arc
    _boolean(rocker, _obj('c', lambda bm: _prism(bm, sector_pts, T0, T1), steel), 'UNION')
    for s in (-1, 1):                                   # two spokes from the hub to the sector ends
        a = -math.pi / 2 + s * (SECTOR_HALF - 0.12)
        ca, sa = math.cos(a), math.sin(a)
        L = r_in + 0.02; w = 0.03
        spoke = [(-sa * w, ca * w), (ca * L - sa * w, sa * L + ca * w), (ca * L + sa * w, sa * L - ca * w), (sa * w, -ca * w)]
        _boolean(rocker, _obj('c', lambda bm, sp=spoke: _prism(bm, sp, T0, T1), steel), 'UNION')
    slot0, slot1 = D - CRANK_R - 0.03, D + CRANK_R + 0.03
    _boolean(rocker, _obj('c', lambda bm: _prism(bm, _rect(-0.026, slot0, 0.026, slot1), T0 - 0.01, T1 + 0.01), steel))
    for zc in (slot0, slot1):
        _boolean(rocker, _obj('c', lambda bm, zc=zc: _prism(bm, _circle(0.026, 0, zc, 40), T0 - 0.01, T1 + 0.01), steel))
    _boolean(rocker, _obj('c', lambda bm: _prism(bm, _circle(0.024, 0, 0, 40), T0 - 0.01, T1 + 0.01), steel))

    # --- rack (same layer as the sector): teeth up, a tooth under the pivot at rest
    p = math.pi * M
    rack_len = 0.56
    def rack_build(bm):
        top, root, base = M, -1.25 * M, -1.25 * M - 0.05
        pts = [(-rack_len / 2, base), (rack_len / 2, base)]
        k = math.floor(rack_len / 2 / p)
        upper = []
        for i in range(-k, k + 1):
            c = i * p
            upper += [(c - 0.27 * p - 1.25 * M * 0.36, root), (c - 0.15 * p, top), (c + 0.15 * p, top), (c + 0.27 * p + 1.25 * M * 0.36, root)]
        upper = [q for q in upper if -rack_len / 2 < q[0] < rack_len / 2]
        pts += [(rack_len / 2, root)] + list(reversed(upper)) + [(-rack_len / 2, root)]
        _prism(bm, pts, T0, T1)
    rack = _obj('Side_Rack', rack_build, steel)

    # --- fixed parts: rack guide channel with end stops and screws, bosses for both axles, hex caps
    rack_z = pz - SECTOR_R
    guide_len = rack_len + 2 * SECTOR_R * math.asin(CRANK_R / D) + 0.06
    def base_build(bm):
        gz0 = rack_z - 1.25 * M - 0.05
        _prism(bm, _rect(py - guide_len / 2, gz0 - 0.07, py + guide_len / 2, gz0 - 0.004), X, X + 0.1)         # guide shelf
        _prism(bm, _rect(py - guide_len / 2, gz0 - 0.07, py + guide_len / 2, gz0 - 0.03), X, X + 0.115)       # front lip
        for yc in (py - guide_len / 2 + 0.05, py + guide_len / 2 - 0.05):
            _prism(bm, _circle(0.018, yc, gz0 - 0.05, 6), X + 0.115, X + 0.13)                                 # screws
        for (yc, zc, r, x1) in ((gy, gz, 0.07, X + 0.015), (py, pz, 0.08, X + 0.06)):
            _prism(bm, _circle(r, yc, zc, 64), X, x1)                                                          # bosses
        _prism(bm, _circle(0.02, gy, gz, 32), X, X + 0.062)                                                    # gear axle
        _prism(bm, _circle(0.03, gy, gz, 6), X + 0.05, X + 0.058)                                              # gear nut
        _prism(bm, _circle(0.021, py, pz, 32), X, X + 0.1)                                                     # pivot axle
        _prism(bm, _circle(0.036, py, pz, 6), X + 0.09, X + 0.104)                                             # pivot nut
    base = _obj('Side_Base', base_build, frame)

    # join the gear's pin into the gear
    bm = bmesh.new()
    for o in gear_parts:
        o.data.transform(o.matrix_world); bm.from_mesh(o.data)
    me = bpy.data.meshes.new('Side_Gear'); bm.to_mesh(me); bm.free()
    for o in gear_parts: bpy.data.objects.remove(o)
    gear = bpy.data.objects.new('Side_Gear', me); gear.data.materials.append(accent)

    # origins on the axes: gear axle, pivot, rack pitch point under the pivot
    for ob in (gear, rocker, rack, base):
        if not ob.users_collection: collection.objects.link(ob)
        elif collection not in ob.users_collection:
            for c in ob.users_collection: c.objects.unlink(ob)
            collection.objects.link(ob)
    gear.data.transform(Matrix.Translation((0, 0, 0))); gear.location = (0, gy, gz)
    rocker.location = (0, py, pz)
    rack.location = (0, py, rack_z)
    for ob in (gear, rocker, rack, base): _finish(ob)

    # --- "hello" LED sign: Yellowtail channel letters on a slim raceway, hung from the rack on two L-brackets, so it
    # slides with the rack. Letters face +X; the page makes them glow.
    import os
    font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'Yellowtail.ttf')
    glow = _mat('LGE_Hello', (1.0, 0.81, 0.35))
    if glow.node_tree:
        bsdf = glow.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            bsdf.inputs['Emission Color'].default_value = (1.0, 0.81, 0.35, 1)
            bsdf.inputs['Emission Strength'].default_value = 4.0
    cu = bpy.data.curves.new('Side_Hello', 'FONT')
    cu.font = bpy.data.fonts.load(font_path, check_existing=True)
    HELLO_W = 0.76                                   # sign width (letters ~0.35 tall), filling the space under the rack
    cu.body = 'hello'; cu.align_x = 'CENTER'; cu.size = HELLO_W / 1.303
    cu.extrude = 0.015; cu.bevel_depth = 0.004; cu.bevel_resolution = 1; cu.resolution_u = 5
    txt = bpy.data.objects.new('Side_HelloTxt', cu); collection.objects.link(txt)
    SIGN_Z = 0.235                                   # baseline; letters reach ~0.34 above it, up to the rack guide
    SIGN_DY = 0.1                                    # sign sits a little right of the rack's centre (clear of the corner post)
    SX = X + 0.17                                    # letter centre plane (depth ±0.019)
    # text: reading direction +X -> +y, up +Y -> +z, face +Z -> +x
    txt.matrix_world = Matrix(((0, 0, 1, SX), (1, 0, 0, py + SIGN_DY), (0, 1, 0, SIGN_Z), (0, 0, 0, 1)))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(txt.evaluated_get(dg)); me.transform(txt.matrix_world)
    bpy.data.objects.remove(txt); bpy.data.curves.remove(cu)
    hello = bpy.data.objects.new('Side_Hello', me); hello.data.materials.clear(); hello.data.materials.append(glow)
    collection.objects.link(hello)
    def mount_build(bm):
        rz0, rz1 = SIGN_Z + 0.12, SIGN_Z + 0.16                                           # raceway behind the letters
        _prism(bm, _rect(py + SIGN_DY - 0.33, rz0, py + SIGN_DY + 0.33, rz1), X + 0.13, X + 0.152)
        tab_z0, tab_z1 = rack_z - 1.25 * M - 0.02, rack_z - 1.25 * M - 0.004              # on the rack body
        for dy in (-0.15, 0.24):                       # both within the rack (±0.28)
            _prism(bm, _rect(py + dy - 0.016, tab_z0, py + dy + 0.016, tab_z1), X + 0.09, X + 0.152)   # tab off the rack
            _prism(bm, _rect(py + dy - 0.016, rz0, py + dy + 0.016, tab_z1), X + 0.136, X + 0.152)     # strap down
            _prism(bm, _circle(0.011, py + dy, (rz0 + rz1) / 2, 6), X + 0.152, X + 0.158)            # bolt
    mount = _obj('Side_HelloMount', mount_build, steel); collection.objects.link(mount)
    for ob in (hello, mount):
        _finish(ob, 50)
        mw = ob.matrix_world.copy(); ob.parent = rack; ob.matrix_parent_inverse = rack.matrix_world.inverted(); ob.matrix_world = mw
    print('SIDE', {o.name: len(o.data.polygons) for o in (gear, rocker, rack, base, hello, mount)}, 'rack_z %.3f' % rack_z,
          'hello dims', tuple(round(v, 3) for v in hello.dimensions))
    return gear, rocker, rack, base
