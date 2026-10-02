"""LightGearLab - "engine in a cube", procedural build for Blender 5.2.

GUI : Scripting workspace > Text Editor > Open > Run Script
CLI : Blender -b --factory-startup --python build_engine.py -- \
          [--save PATH] [--still PATH] [--frame N] [--stills DIR --frames 1,73,145]

Gear convention: every gear mesh is built about its local +Z axis with one
tooth centred on local +X at rotation 0 (for the internal ring: one ring TOOTH
on +X).  Bevel gears have their local origin at the pitch-cone apex and +Z
pointing from the apex out through the back of the gear.  All rotating parts
use rotation_mode 'ZYX' so rotation_euler[2] is the spin about the part's own
axis after the fixed base orientation in rotation_euler[0].

All motion comes from drivers that read ENGINE_Controller["crank_angle"].
"""

import bpy
import bmesh
import json
import math
import os
import sys
from math import pi, sin, cos, tan, atan, atan2, acos, sqrt, radians
from mathutils import Vector, Matrix
from mathutils.geometry import tessellate_polygon

# =============================== PARAMETERS ================================
COLLECTION = "LightGearEngine"
FPS = 24
FRAMES = 300                 # loop length (frames 1..FRAMES, FRAMES+1 == 1)
CRANK_TURNS = 5              # crank revolutions per loop (keeps every gear < 0.4 tooth pitch/frame)
MAX_PITCH_PER_FRAME = 0.4    # anti-aliasing limit on tooth motion per frame (wagon-wheel effect)
RESOLUTION = 1080
BRAND_TEXT = ""              # e.g. "LIGHTGEARLAB" adds raised text on the top plate

# cube frame (outer cube spans x,y in [-HALF, HALF], z in [0, 2*HALF])
HALF = 1.0
BEAM = 0.14
CORNER_HALF = 0.12
CORNER_CHAMFER = 0.035

# engine (inline twin, crankshaft along world Y)
CRANK_X, CRANK_Z = -0.50, 0.55
CRANK_R = 0.14               # throw
CWEIGHT_R = 0.16             # crank-web counterweight radius
ROD_L = 0.46                 # con-rod centre distance
CYL_Y = (-0.02, 0.44)        # cylinder centre planes (kept clear of the near corner beam in the hero view)
GUIDE_SIDE = 1               # crosshead guide rods on +X (far side from the camera)
PISTON_R = 0.105
JOURNAL_R = 0.045
CRANKPIN_R = 0.042
WRIST_R = 0.02

# gears (all 20 deg pressure angle; helical: normal PA)
PRESSURE_ANGLE = radians(20.0)
BACKLASH = 0.04              # total circumferential backlash per mesh, in modules
RING_BACKLASH = 0.06         # planet-ring mesh (restores ~0.04 m minimum play on the internal mesh)
FILLET = 0.25                # root fillet size, in modules
SHAFT_R = 0.03

SPUR_M = 0.03
Z_CRANK_PINION = 20
Z_SPUR_WHEEL = 30
SPUR_DIR = radians(10.0)     # direction of spur wheel centre seen from the crank
SPUR_FACE = 0.07
Y_SPUR = -0.64               # spur layer mid-plane

HELIX_MN = 0.024
HELIX_BETA = radians(25.0)
Z_HELIX_PINION = 18
Z_HELIX_WHEEL = 24
HELIX_FACE = 0.10
Y_HELIX = -0.78              # helical layer mid-plane (in front of the spur layer)
HELIX_SLICES = 8

BEVEL_M = 0.016
Z_BEVEL_PINION = 20          # on the horizontal shaft
Z_BEVEL_WHEEL = 30           # on the vertical shaft
BEVEL_FACE = 0.075
BEVEL_BACKLASH = 0.04

PLANET_M = 0.015
Z_SUN = 18
Z_PLANET = 27
Z_RING = 72
N_PLANETS = 3
PLANET_FACE = 0.08
CARRIER_HUB_R = 0.07         # small hub so the sun and its planet meshes show between the arms
CARRIER_BOSS_R = 0.055
CARRIER_LIFT = 0.025         # gap between the planets and the carrier plate
CARRIER_PHASE = radians(90.0)

TOP_PLATE_Z = (1.86, 1.96)

# camera / look
CAM_TARGET = (0.0, 0.0, 0.9)
CAM_AZIMUTH = radians(39.0)      # from the -Y (gear face) normal toward -X (engine face)
CAM_ELEVATION = radians(25.0)
CAM_DISTANCE = 6.6
CAM_LENS = 62.0
STUDIO_LIGHT = "paint.sl"

# colours (sRGB hex)
COL_FRAME = "#D9D4CB"
COL_PANEL = "#CFCAC0"
COL_ENGINE = "#C2BDB3"
COL_STEEL = "#868480"
COL_SPUR = "#9B9A97"
COL_HELIX = "#A4A19A"
COL_BEVEL = "#91979C"
COL_PLANET = "#9E9B94"
COL_CARRIER = "#C6C1B7"
COL_RING = "#BEB9AF"
COL_BG = "#7A7A7A"

# ============================ small math helpers ===========================


def inv(a):
    return tan(a) - a


def polar(r, a):
    return (r * cos(a), r * sin(a))


def srgb_to_linear(hexstr):
    h = hexstr.lstrip("#")
    out = []
    for i in range(3):
        c = int(h[2 * i:2 * i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def signed_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i][0], pts[i][1]
        x1, y1 = pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1]
        a += x0 * y1 - x1 * y0
    return 0.5 * a


def ccw(pts):
    return list(pts) if signed_area(pts) > 0 else list(reversed(pts))


def cw(pts):
    return list(pts) if signed_area(pts) < 0 else list(reversed(pts))


def circle(r, n=48, c=(0.0, 0.0), a0=0.0):
    return [(c[0] + r * cos(a0 + 2 * pi * i / n), c[1] + r * sin(a0 + 2 * pi * i / n)) for i in range(n)]


def hexagon(r_flat, a0=0.0):
    rc = r_flat / cos(pi / 6)
    return [(rc * cos(a0 + pi / 6 + i * pi / 3), rc * sin(a0 + pi / 6 + i * pi / 3)) for i in range(6)]


def convex_hull(points):
    pts = sorted(set((round(p[0], 9), round(p[1], 9)) for p in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def ang_norm(a):
    return (a + pi) % (2 * pi) - pi


# ============================== mesh builder ===============================


class MB:
    """Accumulates closed shells (verts/faces) for one mesh datablock."""

    def __init__(self):
        self.v = []
        self.f = []

    def ring(self, pts, z=None):
        base = len(self.v)
        for p in pts:
            self.v.append((p[0], p[1], z) if z is not None else (p[0], p[1], p[2]))
        return list(range(base, base + len(pts)))

    def strip(self, a, b, closed=True):
        n = len(a)
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            self.f.append((a[i], a[j], b[j], b[i]))

    def cap(self, loops, up=True):
        polys = [[(self.v[i][0], self.v[i][1]) for i in L] for L in loops]
        flat = [i for L in loops for i in L]
        for t in tessellate_polygon(polys):
            a, b, c = flat[t[0]], flat[t[1]], flat[t[2]]
            pa, pb, pc = self.v[a], self.v[b], self.v[c]
            cr = (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])
            if (cr > 0) != up:
                b, c = c, b
            self.f.append((a, b, c))

    def transform(self, start, M):
        for i in range(start, len(self.v)):
            self.v[i] = tuple(M @ Vector(self.v[i]))

    # ---- primitives (each returns nothing; optional matrix M places the shell)
    def prism(self, outer, holes=(), z0=0.0, z1=1.0, M=None):
        s = len(self.v)
        outer = ccw(outer)
        b = self.ring(outer, z0)
        t = self.ring(outer, z1)
        self.strip(b, t)
        hb_all, ht_all = [], []
        for h in holes:
            h = cw(h)
            hb = self.ring(h, z0)
            ht = self.ring(h, z1)
            self.strip(hb, ht)
            hb_all.append(hb)
            ht_all.append(ht)
        self.cap([t] + ht_all, up=True)
        self.cap([b] + hb_all, up=False)
        if M is not None:
            self.transform(s, M)

    def lathe(self, prof, n=48, M=None):
        """prof: list of (r, z); endpoints with r == 0 become poles."""
        s = len(self.v)
        rings = []
        for r, z in prof:
            if r < 1e-9:
                rings.append(("pole", self.ring([(0.0, 0.0)], z)[0]))
            else:
                rings.append(("ring", self.ring(circle(r, n), z)))
        for (ka, a), (kb, b) in zip(rings, rings[1:]):
            if ka == "ring" and kb == "ring":
                self.strip(a, b)
            elif ka == "pole" and kb == "ring":
                for i in range(n):
                    self.f.append((a, b[(i + 1) % n], b[i]))
            elif ka == "ring" and kb == "pole":
                for i in range(n):
                    self.f.append((a[i], a[(i + 1) % n], b))
        if rings[0][0] == "ring" and rings[-1][0] == "ring":
            # closed tube profile (first == last radius ring loop) - connect
            self.strip(rings[-1][1], rings[0][1])
        if M is not None:
            self.transform(s, M)

    def tube(self, r_out, r_in, z0, z1, n=48, M=None):
        self.lathe([(r_in, z0), (r_out, z0), (r_out, z1), (r_in, z1)], n, M)

    def cyl(self, r, z0, z1, n=32, M=None):
        self.lathe([(0, z0), (r, z0), (r, z1), (0, z1)], n, M)

    def box(self, c, size, chamfer=0.0):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for vt in bm.verts:
            vt.co = Vector((c[0] + vt.co.x * size[0], c[1] + vt.co.y * size[1], c[2] + vt.co.z * size[2]))
        if chamfer > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=chamfer, segments=1,
                            affect='EDGES', profile=0.5, clamp_overlap=True)
        self.add_bmesh(bm)
        bm.free()

    def add_bmesh(self, bm, M=None):
        s = len(self.v)
        idx = {}
        for i, vt in enumerate(bm.verts):
            idx[vt] = s + i
            self.v.append(tuple(vt.co))
        for fc in bm.faces:
            self.f.append(tuple(idx[vt] for vt in fc.verts))
        if M is not None:
            self.transform(s, M)


GEN_TAG = "lge_generated"


def finish_mesh(name, mb, smooth_angle=None, merge=0.0):
    me = bpy.data.meshes.new(name)
    me.from_pydata(mb.v, [], mb.f)
    me.validate(clean_customdata=False)
    bm = bmesh.new()
    bm.from_mesh(me)
    if merge > 0:
        # collapse sliver faces (Workbench shadow volumes streak on near-degenerate silhouettes)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
        bmesh.ops.dissolve_degenerate(bm, dist=merge * 0.1, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me[GEN_TAG] = True
    if smooth_angle is not None:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=smooth_angle)
    return me


# ============================ gear tooth geometry ==========================


def tooth_period(m, rp, rb, ra, rf, psi_p, half_period, n_inv=10, n_fil=4, n_tip=3, n_root=3):
    """One tooth period as (rho, d) pairs, d = angle from tooth centre,
    from d = -half_period (mid space, inclusive) to +half_period (exclusive), CCW."""
    f = FILLET * m
    alpha_p = acos(rb / rp)
    hw0 = psi_p + inv(alpha_p)

    def hw(rho):
        if rho <= rb:
            return hw0
        return hw0 - inv(acos(rb / rho))
    r0 = rf + f
    flank = []
    if r0 < rb:
        flank.append((r0, hw(r0)))
        rs = rb
    else:
        rs = r0
    t0 = sqrt(max(rs * rs / (rb * rb) - 1.0, 0.0))
    t1 = sqrt(ra * ra / (rb * rb) - 1.0)
    for i in range(n_inv):
        t = t0 + (t1 - t0) * i / (n_inv - 1)
        rho = rb * sqrt(1 + t * t)
        flank.append((rho, hw(rho)))
    if hw(ra) <= 0.002:
        raise ValueError("pointed tooth")
    psi_f = hw(r0)
    d_end = -(psi_f + f / rf)
    if -d_end >= half_period - 1e-6:
        raise ValueError("root fillet does not fit")
    P0 = polar(rf, d_end)
    Pc = polar(rf, -psi_f)
    P1 = polar(r0, -psi_f)
    fil = []
    for i in range(n_fil):
        t = i / n_fil
        x = (1 - t) ** 2 * P0[0] + 2 * t * (1 - t) * Pc[0] + t * t * P1[0]
        y = (1 - t) ** 2 * P0[1] + 2 * t * (1 - t) * Pc[1] + t * t * P1[1]
        fil.append((math.hypot(x, y), atan2(y, x)))
    prof = []
    for i in range(n_root):
        prof.append((rf, -half_period + (d_end + half_period) * i / n_root))
    prof += fil
    prof += [(rho, -h) for rho, h in flank]
    htip = hw(ra)
    for i in range(1, n_tip + 1):
        prof.append((ra, -htip + 2 * htip * i / (n_tip + 1)))
    prof += [(rho, h) for rho, h in reversed(flank)]
    prof += [(rho, -d) for rho, d in reversed(fil)]
    for i in range(1, n_root):
        prof.append((rf, -d_end + (half_period + d_end) * i / n_root))
    return prof


def outline_from_period(prof, z, phase=0.0, scale=1.0):
    pts = []
    for k in range(z):
        c = phase + 2 * pi * k / z
        for rho, d in prof:
            pts.append(polar(rho, c + d * scale))
    return pts


def spur_spec(m, z, backlash=BACKLASH, alpha=PRESSURE_ANGLE, mn=None):
    """returns dict with radii and one-period profile (transverse)."""
    mn = m if mn is None else mn
    rp = m * z / 2.0
    rb = rp * cos(alpha)
    ra = rp + mn
    rf = rp - 1.25 * mn
    s = pi * m / 2.0 - backlash * m / 2.0
    prof = tooth_period(mn, rp, rb, ra, rf, s / (2 * rp), pi / z)
    return dict(m=m, z=z, rp=rp, rb=rb, ra=ra, rf=rf, prof=prof)


def ring_spec(m, z, backlash=BACKLASH, alpha=PRESSURE_ANGLE):
    R = m * z / 2.0
    rb = R * cos(alpha)
    # space of the ring == external tooth (tip at R+1.25m, root at R-m)
    s_space = pi * m / 2.0 + backlash * m / 2.0
    prof = tooth_period(m, R, rb, R + 1.25 * m, R - m, s_space / (2 * R), pi / z, n_root=2)
    return dict(m=m, z=z, rp=R, rb=rb, ra=R - m, rf=R + 1.25 * m, prof=prof)


def kidney_window(r1, r2, beta_k, n, s, rc, narc=10):
    """Window between spoke k (centre angle beta_k) and spoke k+1, spoke width s."""
    b0, b1 = beta_k, beta_k + 2 * pi / n
    n0 = (-sin(b0), cos(b0))
    u0 = (cos(b0), sin(b0))
    n1 = (-sin(b1), cos(b1))
    u1 = (cos(b1), sin(b1))
    d = s / 2 + rc
    rin, rout = r1 + rc, r2 - rc

    def corner(nv, uv, dd, rho):
        t = sqrt(rho * rho - dd * dd)
        return (dd * nv[0] + t * uv[0], dd * nv[1] + t * uv[1])
    c1 = corner(n0, u0, d, rin)
    c2 = corner(n0, u0, d, rout)
    c3 = corner(n1, u1, -d, rout)
    c4 = corner(n1, u1, -d, rin)

    def arc(c, ta, tb, k=5):
        tb = ta + ((tb - ta) % (2 * pi))
        return [(c[0] + rc * cos(ta + (tb - ta) * i / k), c[1] + rc * sin(ta + (tb - ta) * i / k)) for i in range(k + 1)]
    pts = []
    pts += arc(c1, atan2(-c1[1], -c1[0]), atan2(-n0[1], -n0[0]))
    pts += arc(c2, atan2(-n0[1], -n0[0]), atan2(c2[1], c2[0]))
    a2, a3 = atan2(c2[1], c2[0]), atan2(c3[1], c3[0])
    a3 = a2 + ((a3 - a2) % (2 * pi))
    pts += [polar(r2, a2 + (a3 - a2) * i / narc) for i in range(1, narc)]
    pts += arc(c3, atan2(c3[1], c3[0]), atan2(n1[1], n1[0]))
    pts += arc(c4, atan2(n1[1], n1[0]), atan2(-c4[1], -c4[0]))
    a4, a1 = atan2(c4[1], c4[0]), atan2(c1[1], c1[0])
    a1 = a4 - ((a4 - a1) % (2 * pi))
    pts += [polar(r1, a4 + (a1 - a4) * i / narc) for i in range(1, narc)]
    return pts


def gear_disc(mb, slices, circles, holes=None, ncirc=96):
    # ncirc should be a multiple of the gear's symmetry order (point-set loop check)
    """Stepped gear disc.  slices: [(z, outline_pts_ccw)] bottom->top (symmetric).
    circles: [(R1, H1), ..., (Rn, None)] going inwards; Hi = half width of the
    annulus inside circle i; the last circle is the bore.  holes: {zone: [loops]},
    zone 0 = between outline and R1, zone i = between Ri and Ri+1."""
    holes = holes or {}
    rings = [mb.ring(ccw(p), z) for z, p in slices]
    for a, b in zip(rings, rings[1:]):
        mb.strip(a, b)
    outer_top, outer_bot = rings[-1], rings[0]
    h_prev = slices[-1][0]
    for i, (R, H) in enumerate(circles):
        circ = circle(R, ncirc)
        top_o = mb.ring(circ, h_prev)
        bot_o = mb.ring(circ, -h_prev)
        ht_l, hb_l = [], []
        for hl in holes.get(i, []):
            hl = cw(hl)
            ht = mb.ring(hl, h_prev)
            hb = mb.ring(hl, -h_prev)
            mb.strip(hb, ht)
            ht_l.append(ht)
            hb_l.append(hb)
        if i > 0 and not ht_l:      # plain circular annulus: structured quads
            mb.strip(outer_top, top_o)
            mb.strip(bot_o, outer_bot)
        else:
            mb.cap([outer_top, top_o] + ht_l, up=True)
            mb.cap([outer_bot, bot_o] + hb_l, up=False)
        if H is None:
            mb.strip(top_o, bot_o)
            break
        if abs(H - h_prev) > 1e-9:
            top_i = mb.ring(circ, H)
            bot_i = mb.ring(circ, -H)
            mb.strip(top_o, top_i)
            mb.strip(bot_i, bot_o)
        else:
            top_i, bot_i = top_o, bot_o
        outer_top, outer_bot = top_i, bot_i
        h_prev = H


def build_spur_mesh(name, spec, face, circles, holes=None, twist_rate=0.0, slices=2):
    mb = MB()
    ncirc = spec["z"] * int(math.ceil(96.0 / spec["z"]))
    sl = []
    for i in range(slices):
        z = -face / 2 + face * i / (slices - 1)
        sl.append((z, outline_from_period(spec["prof"], spec["z"], phase=twist_rate * z)))
    gear_disc(mb, sl, circles, holes, ncirc)
    return finish_mesh(name, mb, radians(32))


def build_ring_mesh(name, spec, face, r_out, phase):
    mb = MB()
    inner = outline_from_period(spec["prof"], spec["z"], phase=phase)
    mb.prism(circle(r_out, 144), [inner], -face / 2, face / 2)
    # outer flange lip
    mb.tube(r_out + 0.025, r_out - 0.01, -face / 2, -face / 2 + 0.03, 144)
    return finish_mesh(name, mb, radians(32))


def build_bevel_mesh(name, m, z, delta, A, face, backlash, hub_r, hub_len, bore_r, holes=None, inset=0.0):
    """Straight bevel gear, Tredgold back-cone approximation.
    Local origin at cone apex, +Z away from the apex."""
    r = m * z / 2.0
    rv = r / cos(delta)
    zv = z / cos(delta)
    spec_rb = rv * cos(PRESSURE_ANGLE)
    s = pi * m / 2.0 - backlash * m / 2.0
    prof = tooth_period(m, rv, spec_rb, rv + m, rv - 1.25 * m, s / (2 * rv), pi / zv, n_inv=10)
    P0z = A / cos(delta)
    cd, sd = cos(delta), sin(delta)

    def heel(rho, psi):
        return (rho * cd * cos(psi), rho * cd * sin(psi), P0z - rho * sd)
    Hraw = []
    psis = []
    for k in range(z):
        ck = 2 * pi * k / z
        for rho, d in prof:
            Hraw.append(heel(rho, ck + d / cd))
            psis.append(ck + d / cd)
    for i in range(1, len(psis)):          # strictly increasing azimuths for the inner ring
        if psis[i] <= psis[i - 1] + 1e-5:
            psis[i] = psis[i - 1] + 1e-5
    # inset: shorten the teeth at both ends (keeps heel/toe faces of the mate clear)
    hk = (A - inset) / A
    kk = (A - face + inset) / A
    H = [(hk * p[0], hk * p[1], hk * p[2]) for p in Hraw]
    T = [(kk * p[0], kk * p[1], kk * p[2]) for p in Hraw]
    rho2 = rv - 1.25 * m - 0.8 * m
    R2 = rho2 * cd * hk
    z2 = (P0z - rho2 * sd) * hk
    R2t = rho2 * cd * kk
    z2t = (P0z - rho2 * sd) * kk
    mb = MB()
    nc = z * int(math.ceil(120.0 / z))
    h_i = mb.ring(H)
    t_i = mb.ring(T)
    mb.strip(t_i, h_i)
    # heel / toe faces as radial quads (a tessellated cap would cut chords through the cone)
    h2 = mb.ring([(R2 * cos(a), R2 * sin(a), z2) for a in psis])
    t2 = mb.ring([(R2t * cos(a), R2t * sin(a), z2t) for a in psis])
    mb.strip(h_i, h2)
    mb.strip(t2, t_i)
    # back face (z2) R2 -> hub_r, hub cylinder, hub back, bore, front face (kk*z2)
    zf = z2t
    zb = z2 + hub_len
    hub_o = mb.ring(circle(hub_r, nc), z2)
    hub_b = mb.ring(circle(hub_r, nc), zb)
    bore_b = mb.ring(circle(bore_r, nc), zb)
    bore_f = mb.ring(circle(bore_r, nc), zf)
    hl_top, hl_bot = [], []
    for hl in (holes or []):
        hl = cw(hl)
        a = mb.ring(hl, z2)
        b = mb.ring(hl, zf)
        mb.strip(b, a)
        hl_top.append(a)
        hl_bot.append(b)
    mb.cap([h2, hub_o] + hl_top, up=True)
    mb.strip(hub_o, hub_b)
    mb.cap([hub_b, bore_b], up=True)
    mb.strip(bore_b, bore_f)
    mb.cap([t2, bore_f] + hl_bot, up=False)
    me = finish_mesh(name, mb, radians(32), merge=1e-5)
    info = dict(r=r, rv=rv, zv=zv, ra_heel=rv + m, z_back=zb, z_front=zf, R2=R2, z2=z2, kk=kk)
    return me, info


# ============================ scene bookkeeping ============================

def get_collection():
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col[GEN_TAG] = True
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


def cleanup():
    col = bpy.data.collections.get(COLLECTION)
    if col is not None:
        for ob in list(col.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        for c in list(col.children_recursive):
            bpy.data.collections.remove(c)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.cameras,
                 bpy.data.worlds, bpy.data.lights):
        for d in list(coll):
            if d.get(GEN_TAG) and d.users == 0:
                coll.remove(d)
    # factory default objects, only when untouched
    def close(a, b, tol=1e-3):
        return all(abs(x - y) < tol for x, y in zip(a, b))
    ob = bpy.data.objects.get("Cube")
    if ob and ob.type == 'MESH' and len(ob.data.vertices) == 8 and close(ob.location, (0, 0, 0)) \
            and close(ob.rotation_euler, (0, 0, 0)) and close(ob.scale, (1, 1, 1)) and close(ob.dimensions, (2, 2, 2)):
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    ob = bpy.data.objects.get("Light")
    if ob and ob.type == 'LIGHT' and close(ob.location, (4.0762, 1.0055, 5.9039)):
        bpy.data.objects.remove(ob, do_unlink=True)
    ob = bpy.data.objects.get("Camera")
    if ob and ob.type == 'CAMERA' and close(ob.location, (7.3589, -6.9258, 4.9583)):
        bpy.data.objects.remove(ob, do_unlink=True)


MATS = {}


def mat(name, hexcol):
    key = "LGE_" + name
    if key in MATS:
        return MATS[key]
    m = bpy.data.materials.new(key)
    m[GEN_TAG] = True
    lin = srgb_to_linear(hexcol)
    m.diffuse_color = (lin[0], lin[1], lin[2], 1.0)
    m.roughness = 0.6
    m.metallic = 0.0
    if m.node_tree is not None:
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = (lin[0], lin[1], lin[2], 1.0)
    MATS[key] = m
    return m


META = {"objects": {}, "gears": {}, "pairs": [], "rods": [], "sym": {}}


def make_obj(name, me, material, loc=(0, 0, 0), rot=(0, 0, 0), bevel=None, group="static",
             moving=False, sym=1, equiv=None, parent=None):
    col = get_collection()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if material is not None:
        me.materials.append(material)
    ob.rotation_mode = 'ZYX'
    ob.location = loc
    ob.rotation_euler = rot
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
    if bevel:
        md = ob.modifiers.new("Bevel", 'BEVEL')
        md.width = bevel
        md.segments = 2
        md.limit_method = 'ANGLE'
        md.angle_limit = radians(40)
        md.use_clamp_overlap = True
        md.harden_normals = True
    ob["lge_group"] = group
    META["objects"][name] = dict(group=group, moving=moving, equiv=equiv or name, sym=sym)
    return ob


DRIVERS = []


def add_driver(ob, path, index, expr, ctrl):
    fc = ob.driver_add(path, index) if index is not None else ob.driver_add(path)
    for md in list(fc.modifiers):
        fc.modifiers.remove(md)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    var = drv.variables.new()
    var.name = "c"
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'OBJECT'
    var.targets[0].id = ctrl
    var.targets[0].data_path = '["crank_angle"]'
    drv.expression = expr
    DRIVERS.append((ob.name, path, index, drv))
    return fc


def g(x):
    return "%.12g" % x


def lin_expr(P, R):
    return "%s + %s*c" % (g(P), g(R))


# ================================ the build ================================

def build():
    cleanup()
    MATS.clear()
    for k in META:
        META[k] = {} if isinstance(META[k], dict) else []
    DRIVERS.clear()
    scene = bpy.context.scene
    col = get_collection()

    M_FRAME = mat("Frame", COL_FRAME)
    M_PANEL = mat("Panel", COL_PANEL)
    M_ENGINE = mat("Engine", COL_ENGINE)
    M_STEEL = mat("Steel", COL_STEEL)
    M_SPUR = mat("Spur", COL_SPUR)
    M_HELIX = mat("Helical", COL_HELIX)
    M_BEVEL = mat("Bevel", COL_BEVEL)
    M_PLANET = mat("Planetary", COL_PLANET)
    M_RING = mat("Ring", COL_RING)
    M_CARRIER = mat("Carrier", COL_CARRIER)

    RX = radians(90)       # base orientation: local +Z -> world -Y (axis out of the front face)
    two_pi_N = 2 * pi * CRANK_TURNS

    # ---------------------------------------------------------- controller
    ctrl = bpy.data.objects.new("ENGINE_Controller", None)
    col.objects.link(ctrl)
    ctrl.empty_display_type = 'ARROWS'
    ctrl.empty_display_size = 0.25
    ctrl.location = (HALF + 0.4, -HALF - 0.4, 0)
    ctrl.hide_render = True
    ctrl["crank_angle"] = 0.0
    fc = ctrl.driver_add('["crank_angle"]')
    for md in list(fc.modifiers):
        fc.modifiers.remove(md)
    fc.driver.type = 'SCRIPTED'
    fc.driver.expression = "(frame - 1)*%s" % g(two_pi_N / FRAMES)
    DRIVERS.append((ctrl.name, '["crank_angle"]', None, fc.driver))

    # ----------------------------------------------------- layout (front view x,z)
    C = Vector((CRANK_X, CRANK_Z))
    sp1 = spur_spec(SPUR_M, Z_CRANK_PINION)
    sp2 = spur_spec(SPUR_M, Z_SPUR_WHEEL)
    a_s = sp1["rp"] + sp2["rp"]
    K = C + a_s * Vector((cos(SPUR_DIR), sin(SPUR_DIR)))
    mt = HELIX_MN / cos(HELIX_BETA)
    alpha_t = atan(tan(PRESSURE_ANGLE) / cos(HELIX_BETA))
    hp = spur_spec(mt, Z_HELIX_PINION, alpha=alpha_t, mn=HELIX_MN, backlash=BACKLASH * HELIX_MN / mt)
    hw = spur_spec(mt, Z_HELIX_WHEEL, alpha=alpha_t, mn=HELIX_MN, backlash=BACKLASH * HELIX_MN / mt)
    a_h = hp["rp"] + hw["rp"]
    # helical wheel straight above-left of K on the cube's centre line x = 0
    dz = sqrt(a_h * a_h - K.x * K.x)
    W = Vector((0.0, K.y + dz))
    assert (W - K).length - sp2["ra"] - SHAFT_R > 0.03, "helical-wheel shaft hits the spur wheel"
    assert (W - C).length - sp1["ra"] - SHAFT_R > 0.04
    assert K.y - sp2["ra"] > BEAM + 0.05 and K.x + sp2["ra"] < HALF - BEAM - 0.05
    assert W.y + hw["ra"] < TOP_PLATE_Z[0] - 0.1
    zb = W.y                          # bevel apex height (horizontal shaft axis)

    # =================================================== kinematics + phases
    # every angle = P + R * crank_angle (rad); Y-axis parts measured CCW seen from the front
    def mesh_ext(Pa, Ra, za, zbn, theta):
        return (theta + pi + pi / zbn + (za / zbn) * (theta - Pa), -(za / zbn) * Ra)

    ph = {}
    ph["crank"] = (0.0, 1.0)
    ph["crank_pinion"] = (0.0, 1.0)
    th_s = atan2(K.y - C.y, K.x - C.x)
    ph["spur_wheel"] = mesh_ext(0.0, 1.0, Z_CRANK_PINION, Z_SPUR_WHEEL, th_s)
    Rk = ph["spur_wheel"][1]
    ph["helix_pinion"] = (0.0, Rk)
    th_h = atan2(W.y - K.y, W.x - K.x)
    ph["helix_wheel"] = mesh_ext(0.0, Rk, Z_HELIX_PINION, Z_HELIX_WHEEL, th_h)
    Rh = ph["helix_wheel"][1]
    ph["bevel_pinion"] = (0.0, Rh)
    # bevel: both local +Z axes point away from the common apex
    #   pinion contact azimuth -pi/2 (bottom), wheel contact azimuth +pi/2 (front)
    #   dphi_w = -(zp/zw) dphi_p ; phase: phi_w = pi/2 + pi/zw - (zp/zw)(phi_p + pi/2)
    zp_, zw_ = Z_BEVEL_PINION, Z_BEVEL_WHEEL
    Pb, Rb = ph["bevel_pinion"]
    ph["bevel_wheel"] = (pi / 2 + pi / zw_ - (zp_ / zw_) * (Pb + pi / 2), -(zp_ / zw_) * Rb)
    # sun (local +Z = world +Z) is on the same shaft as the bevel wheel (local +Z = world -Z)
    Rs = -ph["bevel_wheel"][1]
    ph["sun"] = (0.0, Rs)
    Rc = Rs * Z_SUN / (Z_SUN + Z_RING)
    ph["carrier"] = (CARRIER_PHASE, Rc)
    # planets: world phase from the sun mesh, local spin = world - carrier
    planet_world = []
    for k in range(N_PLANETS):
        th0 = CARRIER_PHASE + 2 * pi * k / N_PLANETS
        # theta_k(c) = th0 + Rc c ; phi_s = Rs c
        Pw = th0 + pi + pi / Z_PLANET + (Z_SUN / Z_PLANET) * th0
        Rw = Rc + (Z_SUN / Z_PLANET) * (Rc - Rs)
        planet_world.append((Pw, Rw))
        ph["planet_%d" % k] = (Pw - CARRIER_PHASE, Rw - Rc)
    # planet spin relative to carrier: from sun mesh vs. from ring mesh (ring fixed)
    spin_sun = -(Rs - Rc) * Z_SUN / Z_PLANET
    spin_ring = -Rc * Z_RING / Z_PLANET
    assert abs(spin_sun - spin_ring) < 1e-12, (spin_sun, spin_ring)
    assert abs((Rw - Rc) - spin_sun) < 1e-12
    assert Z_RING == Z_SUN + 2 * Z_PLANET and (Z_SUN + Z_RING) % N_PLANETS == 0
    # ring phase that meshes planet 0, then verify all planets
    th0 = CARRIER_PHASE
    phi_R = th0 + pi / Z_RING + (Z_PLANET / Z_RING) * (planet_world[0][0] - th0)
    for k in range(N_PLANETS):
        thk = CARRIER_PHASE + 2 * pi * k / N_PLANETS
        need = thk + (Z_RING / Z_PLANET) * (phi_R - thk - pi / Z_RING)
        diff = (planet_world[k][0] - need) / (2 * pi / Z_PLANET)
        assert abs(diff - round(diff)) < 1e-9, ("planet/ring phase mismatch", k, diff)
    ring_phase = phi_R            # rotation of the ring object (tooth on +X convention)

    # ========================================================= FRAME
    e = HALF - BEAM / 2
    inner = HALF - BEAM
    ztop = 2 * HALF
    mb = MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            for zc in (BEAM / 2, ztop - BEAM / 2):
                mb.box((sx * e, sy * e, zc), (2 * CORNER_HALF,) * 3, CORNER_CHAMFER)
    make_obj("Frame_Corners", finish_mesh("Frame_Corners", mb), M_FRAME, bevel=0.006)

    mb = MB()
    L0 = e - CORNER_HALF
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((sx * e, sy * e, ztop / 2), (BEAM, BEAM, ztop - BEAM - 2 * CORNER_HALF), 0.0)
    for s in (-1, 1):
        for zc in (BEAM / 2, ztop - BEAM / 2):
            mb.box((0, s * e, zc), (2 * L0, BEAM, BEAM), 0.0)
            mb.box((s * e, 0, zc), (BEAM, 2 * L0, BEAM), 0.0)
    make_obj("Frame_Beams", finish_mesh("Frame_Beams", mb), M_FRAME, bevel=0.008)

    # inner lips around the two open faces (stepped border like the reference)
    mb = MB()
    lip = 0.045
    outer_sq = [(-inner, BEAM), (inner, BEAM), (inner, ztop - BEAM), (-inner, ztop - BEAM)]
    hole_sq = [(-inner + lip, BEAM + lip), (inner - lip, BEAM + lip), (inner - lip, ztop - BEAM - lip),
               (-inner + lip, ztop - BEAM - lip)]
    # rounded inner corners
    def rounded_rect(x0, z0, x1, z1, r, n=6):
        pts = []
        for (cx, cz, a0) in ((x1 - r, z0 + r, -pi / 2), (x1 - r, z1 - r, 0), (x0 + r, z1 - r, pi / 2), (x0 + r, z0 + r, pi)):
            for i in range(n + 1):
                a = a0 + (pi / 2) * i / n
                pts.append((cx + r * cos(a), cz + r * sin(a)))
        return pts
    hole_sq = rounded_rect(-inner + lip, BEAM + lip, inner - lip, ztop - BEAM - lip, 0.06)
    Mfront = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # (u,v,w)->(u,w,v)
    mb.prism(outer_sq, [hole_sq], -inner, -inner + 0.03, M=Mfront)
    Mleft = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))    # (u,v,w)->(w,u,v)
    mb.prism(outer_sq, [hole_sq], -inner, -inner + 0.03, M=Mleft)
    make_obj("Frame_Lips", finish_mesh("Frame_Lips", mb), M_FRAME, bevel=0.005)

    # feet
    mb = MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((sx * e, sy * e, BEAM / 2 - CORNER_HALF - 0.025), (0.19, 0.19, 0.05), 0.012)
    make_obj("Frame_Feet", finish_mesh("Frame_Feet", mb), M_FRAME, bevel=0.004)

    # panels: floor, back (+Y), right (+X), top
    mb = MB()
    mb.box((0, 0, 0.11), (2 * inner, 2 * inner, 0.06))
    make_obj("Panel_Floor", finish_mesh("Panel_Floor", mb), M_PANEL, bevel=0.004)

    mb = MB()
    back_y0, back_y1 = inner - 0.02, inner + 0.02
    mb.box((0, inner, ztop / 2), (2 * inner, 0.04, ztop - 2 * BEAM))
    # stiffening ribs on the inside of the back panel
    for xr in (-0.62, 0.62):
        mb.box((xr, back_y0 - 0.02, ztop / 2), (0.05, 0.04, ztop - 2 * BEAM))
    mb.box((0, back_y0 - 0.02, 1.62), (2 * inner, 0.04, 0.05))
    make_obj("Panel_Back", finish_mesh("Panel_Back", mb), M_PANEL, bevel=0.004)

    mb = MB()
    slots = []
    for i in range(6):
        yc = 0.05 + 0.1 * i
        slots.append(rounded_rect(yc - 0.025, 0.32, yc + 0.025, 0.78, 0.024, 5))
    outer_r = [(-inner, BEAM), (inner, BEAM), (inner, ztop - BEAM), (-inner, ztop - BEAM)]
    Mright = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    mb.prism(outer_r, slots, inner - 0.02, inner + 0.02, M=Mright)
    for zr in (0.95, 1.62):
        mb.box((inner - 0.04, 0.0, zr), (0.04, 2 * inner, 0.05))
    make_obj("Panel_Right", finish_mesh("Panel_Right", mb), M_PANEL, bevel=0.004)

    mb = MB()
    tz0, tz1 = TOP_PLATE_Z
    sq = [(-inner, -inner), (inner, -inner), (inner, inner), (-inner, inner)]
    mb.prism(sq, [circle(0.045, 48)], tz0, tz1)
    # raised seam strips on the top plate (panel look)
    for s in (-1, 1):
        mb.box((s * 0.74, 0, tz1 + 0.006), (0.03, 2 * inner - 0.1, 0.012))
        mb.box((0, s * 0.74, tz1 + 0.006), (2 * inner - 0.1, 0.03, 0.012))
    make_obj("Panel_Top", finish_mesh("Panel_Top", mb), M_FRAME, bevel=0.004)

    # ------------------------------------------------------------- bolts
    bolts = MB()

    def bolt(p, n, r=0.026, h=0.014):
        n = Vector(n).normalized()
        q = n.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        M = Matrix.Translation(Vector(p)) @ q
        bolts.prism(circle(r, 24), [hexagon(r * 0.42)], 0.0, h, M=M)
        bolts.cyl(r * 0.9, 0.0, h * 0.45, 20, M=M)

    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz, zc in ((-1, BEAM / 2), (1, ztop - BEAM / 2)):
                c = Vector((sx * e, sy * e, zc))
                for ax in range(3):
                    nrm = [0, 0, 0]
                    nrm[ax] = (sx, sy, sz)[ax]
                    p = c + Vector(nrm) * CORNER_HALF
                    if ax == 2 and sz < 0:
                        continue
                    bolt(p, nrm)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bolt((sx * 0.78, sy * 0.78, tz1), (0, 0, 1), 0.022, 0.012)

    # ========================================================= ENGINE (static)
    cx, cz = CRANK_X, CRANK_Z
    y1, y2 = CYL_Y
    ymid = 0.5 * (y1 + y2)
    gs = GUIDE_SIDE
    mb = MB()
    y_ped_front = Y_SPUR + 0.105                  # main bearing just behind the drive pinion
    by0, by1 = y_ped_front - 0.06, y2 + 0.30
    mb.box((cx, 0.5 * (by0 + by1), 0.165), (0.52, by1 - by0, 0.05), 0.01)
    ped_ys = (y_ped_front, y1 - 0.17, ymid, y2 + 0.17)

    def pillow(mbx, ccx, ccz, y, base_z, half_w, r_top, bore, thick):
        pts = [(ccx - half_w, base_z), (ccx + half_w, base_z), (ccx + half_w, base_z + 0.05)]
        for i in range(17):
            a = 0.0 + pi * i / 16
            pts.append((ccx + r_top * cos(a), ccz + r_top * sin(a)))
        pts.append((ccx - half_w, base_z + 0.05))
        M = Matrix.Translation((0, y, 0)) @ Mfront
        mbx.prism(pts, [circle(bore, 40, (ccx, ccz))], -thick / 2, thick / 2, M=M)
    for y in ped_ys:
        pillow(mb, cx, cz, y, 0.19, 0.13, 0.095, JOURNAL_R + 0.005, 0.07)
        for s_ in (-1, 1):
            bolt((cx + s_ * 0.06, y, cz + 0.077), (0, 0, 1), 0.016, 0.01)
    # rear columns carry the head block; an arm ties the head to the back panel.  The head is
    # set back on the camera side (-X) so it doesn't hide the pistons at top dead centre.
    yc_col = y2 + 0.25
    hx0, hx1 = cx - 0.125, cx + 0.22
    for x in (cx - 0.095, cx + 0.17):
        mb.box((x, yc_col, (0.19 + 1.30) / 2), (0.05, 0.05, 1.30 - 0.19), 0.006)
    hy0, hy1 = y1 - 0.135, yc_col + 0.04
    mb.box((0.5 * (hx0 + hx1), 0.5 * (hy0 + hy1), 1.36), (hx1 - hx0, hy1 - hy0, 0.12), 0.02)
    mb.box((cx, (hy1 + inner) / 2, 1.365), (0.16, inner - hy1 + 0.02, 0.07), 0.01)
    for y in CYL_Y:
        mb.cyl(0.115, 1.42, 1.46, 48, M=Matrix.Translation((cx, y, 0)))
        mb.cyl(0.05, 1.46, 1.49, 32, M=Matrix.Translation((cx, y, 0)))
        for bx, by in ((cx + 0.16, y), (cx + 0.11, y - 0.11), (cx + 0.11, y + 0.11)):
            bolt((bx, by, 1.42), (0, 0, 1), 0.018, 0.012)
        # crosshead guide rods on the far (+X) side only, so the camera sees pistons and rods
        mb.cyl(0.014, 0.79, 1.30, 20, M=Matrix.Translation((cx + gs * 0.145, y, 0)))
    # tie bar from the guide rods back to the rear column
    mb.box((cx + gs * 0.145, 0.5 * (y1 - 0.03 + yc_col), 0.78), (0.03, yc_col - y1 + 0.03, 0.03), 0.004)
    make_obj("Engine_Frame", finish_mesh("Engine_Frame", mb, radians(35)), M_ENGINE, bevel=0.005)

    # ========================================================= ENGINE (moving)
    # crankshaft: local z = -world y ; throw 1 at local +Y (world +Z at c = 0)
    mb = MB()
    loc_z = lambda yw: -yw
    jr = JOURNAL_R
    y_front_end = Y_SPUR - 0.075
    y1, y2 = CYL_Y
    mb.cyl(jr, loc_z(y1 - 0.09 + 0.005), loc_z(y_front_end), 40)
    mb.cyl(jr, loc_z(y2 - 0.085), loc_z(y1 + 0.085), 40)
    mb.cyl(jr, loc_z(y2 + 0.24), loc_z(y2 + 0.09 - 0.005), 40)
    pins_local = []
    for k, yc in enumerate(CYL_Y):
        side = 1 if k == 0 else -1
        pin_c = (0.0, side * CRANK_R)
        pins_local.append((0.0, side * CRANK_R, loc_z(yc)))
        mb.cyl(CRANKPIN_R, loc_z(yc + 0.045), loc_z(yc - 0.045), 40, M=Matrix.Translation((pin_c[0], pin_c[1], 0)))
        web_pts = circle(0.068, 32, pin_c) + circle(0.07, 24)
        for i in range(25):
            a = -side * pi / 2 + radians(-70 + 140 * i / 24)
            web_pts.append(polar(CWEIGHT_R, a))
        hull = convex_hull(web_pts)
        for y0, y1 in ((yc - 0.09, yc - 0.04), (yc + 0.04, yc + 0.09)):
            mb.prism(hull, [], loc_z(y1), loc_z(y0))
    crank = make_obj("Crankshaft", finish_mesh("Crankshaft", mb, radians(35)), M_ENGINE,
                     loc=(cx, 0, cz), rot=(RX, 0, 0), bevel=0.004, group="crank", moving=True, sym=1)
    add_driver(crank, "rotation_euler", 2, lin_expr(*ph["crank"]), ctrl)

    # con rods (origin at wrist pin, rod hangs along -Z) and pistons (origin at wrist pin)
    for k, yc in enumerate(CYL_Y):
        phase = 0.0 if k == 0 else pi
        mb = MB()
        Mr = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # local (u,v,w)->(u,w,v): plane XZ, thickness Y
        bar = convex_hull(circle(0.024, 24, (0, -0.055)) + circle(0.032, 24, (0, -ROD_L + 0.08)))
        mb.prism(bar, [], -0.016, 0.016, M=Mr)
        mb.prism(circle(0.038, 40), [circle(WRIST_R + 0.004, 32)], -0.025, 0.025, M=Mr)
        mb.prism(circle(0.066, 48, (0, -ROD_L)), [circle(CRANKPIN_R + 0.004, 40, (0, -ROD_L))], -0.03, 0.03, M=Mr)
        # rib flanges along the bar (I-section look)
        for s in (-1, 1):
            rib = convex_hull([(s * 0.015, -0.06), (s * 0.0235, -0.06), (s * 0.0315, -ROD_L + 0.085), (s * 0.0235, -ROD_L + 0.085)])
            mb.prism(rib, [], -0.026, 0.026, M=Mr)
        h0 = CRANK_Z + CRANK_R + ROD_L
        rod = make_obj("ConRod_%d" % (k + 1), finish_mesh("ConRod_%d" % (k + 1), mb, radians(35)), M_ENGINE,
                       loc=(cx, yc, h0), rot=(0, 0, 0), bevel=0.003, group="rod%d" % k, moving=True)
        rod.rotation_mode = 'XYZ'
        zexpr = "%s + %s*cos(c + %s) + sqrt(%s - %s*sin(c + %s)*sin(c + %s))" % (
            g(CRANK_Z), g(CRANK_R), g(phase), g(ROD_L * ROD_L), g(CRANK_R * CRANK_R), g(phase), g(phase))
        add_driver(rod, "location", 2, zexpr, ctrl)
        add_driver(rod, "rotation_euler", 1, "asin(%s*sin(c + %s))" % (g(CRANK_R / ROD_L), g(phase)), ctrl)
        META["rods"].append(dict(rod=rod.name, crank=crank.name, pin_local=list(pins_local[k]),
                                 piston="Piston_%d" % (k + 1), L=ROD_L))
        # piston: hollow skirt, ring grooves, wrist pin
        mb = MB()
        top, bot = 0.11, -0.075
        pr = PISTON_R
        prof = [(0, top), (pr - 0.006, top), (pr, top - 0.006)]
        zg = top - 0.022
        for gi in range(3):
            prof += [(pr, zg), (pr - 0.007, zg), (pr - 0.007, zg - 0.008), (pr, zg - 0.008)]
            zg -= 0.02
        prof += [(pr, bot), (0.08, bot), (0.08, 0.05), (0, 0.05)]
        mb.lathe(prof, 64)
        mb.cyl(WRIST_R, -pr + 0.004, pr - 0.004, 24, M=Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1))))
        pis = make_obj("Piston_%d" % (k + 1), finish_mesh("Piston_%d" % (k + 1), mb, radians(35)), M_ENGINE,
                       loc=(cx, yc, h0), bevel=0.002, group="piston%d" % k, moving=True)
        add_driver(pis, "location", 2, zexpr, ctrl)

    # ========================================================= GEARS
    def y_axis_gear(name, me, material, x, y, z, phase_key, group, sym, bevel=0.0025):
        ob = make_obj(name, me, material, loc=(x, y, z), rot=(RX, 0, ph[phase_key][0]), bevel=bevel,
                      group=group, moving=True, sym=sym)
        add_driver(ob, "rotation_euler", 2, lin_expr(*ph[phase_key]), ctrl)
        return ob

    def gear_meta(name, typ, spec, extra=None):
        d = dict(type=typ, z=spec["z"], m=spec["m"], rp=spec["rp"], ra=spec["ra"], rf=spec["rf"])
        if extra:
            d.update(extra)
        META["gears"][name] = d

    def shaft(name, x, z, y0, y1, r, phase_key, group, mtl=M_STEEL):
        mb = MB()
        mb.cyl(r, -y1, -y0, 48)
        ob = make_obj(name, finish_mesh(name, mb, radians(35)), mtl, loc=(x, 0, z), rot=(RX, 0, 0),
                      bevel=0.002, group=group, moving=True, sym=1)
        add_driver(ob, "rotation_euler", 2, lin_expr(*ph[phase_key]), ctrl)
        return ob

    def nut_mesh(name, r_flat, bore, h, washer=True):
        mb = MB()
        mb.prism(hexagon(r_flat), [circle(bore, 48)], 0.0, h)
        if washer:
            mb.tube(r_flat * 1.25, bore, -0.006, 0.0, 48)
        return finish_mesh(name, mb, radians(35))

    # ---- spur stage (crank pinion -> spur wheel)
    me = build_spur_mesh("Spur_CrankPinion", sp1, SPUR_FACE, [(0.225, 0.024), (0.095, 0.05), (JOURNAL_R + 0.001, None)])
    y_axis_gear("Spur_CrankPinion", me, M_SPUR, C.x, Y_SPUR, C.y, "crank_pinion", "crank", Z_CRANK_PINION)
    gear_meta("Spur_CrankPinion", "spur", sp1, dict(face=SPUR_FACE))
    me = nut_mesh("Nut_Crank", 0.055, JOURNAL_R + 0.001, 0.03)
    ob = make_obj("Nut_Crank", me, M_STEEL, loc=(C.x, Y_SPUR - 0.05 - 0.007, C.y), rot=(RX, 0, 0),
                  bevel=0.002, group="crank", moving=True, sym=6)
    add_driver(ob, "rotation_euler", 2, lin_expr(*ph["crank"]), ctrl)

    holes6 = [circle(0.062, 40, polar(0.302, pi / 6 + i * pi / 3), pi / 6 + i * pi / 3) for i in range(6)]
    me = build_spur_mesh("Spur_Wheel", sp2, SPUR_FACE, [(0.385, 0.021), (0.11, 0.046), (SHAFT_R + 0.001, None)],
                         holes={1: holes6})
    y_axis_gear("Spur_Wheel", me, M_SPUR, K.x, Y_SPUR, K.y, "spur_wheel", "shaftK", 6)
    gear_meta("Spur_Wheel", "spur", sp2, dict(holes=6, face=SPUR_FACE))
    META["pairs"].append(dict(a="Spur_CrankPinion", b="Spur_Wheel", type="external"))

    # ---- helical stage (pinion compounded on the spur wheel shaft -> helical wheel)
    twist_p = tan(HELIX_BETA) / hp["rp"]
    twist_w = -tan(HELIX_BETA) / hw["rp"]
    me = build_spur_mesh("Helical_Pinion", hp, HELIX_FACE, [(0.066, 0.06), (SHAFT_R + 0.001, None)],
                         twist_rate=twist_p, slices=HELIX_SLICES)
    y_axis_gear("Helical_Pinion", me, M_HELIX, K.x, Y_HELIX, K.y, "helix_pinion", "shaftK", Z_HELIX_PINION)
    gear_meta("Helical_Pinion", "helical", hp, dict(beta=HELIX_BETA, hand="right", mn=HELIX_MN, face=HELIX_FACE))
    spokes = [kidney_window(0.105, 0.235, i * pi / 3, 6, 0.045, 0.018) for i in range(6)]
    me = build_spur_mesh("Helical_Wheel", hw, HELIX_FACE, [(0.255, 0.028), (0.08, 0.06), (SHAFT_R + 0.001, None)],
                         holes={1: spokes}, twist_rate=twist_w, slices=HELIX_SLICES)
    y_axis_gear("Helical_Wheel", me, M_HELIX, W.x, Y_HELIX, W.y, "helix_wheel", "shaftH", 6)
    gear_meta("Helical_Wheel", "helical", hw, dict(beta=HELIX_BETA, hand="left", mn=HELIX_MN, spokes=6, face=HELIX_FACE))
    META["pairs"].append(dict(a="Helical_Pinion", b="Helical_Wheel", type="external"))

    # shaft K (spur wheel + helical pinion) : front nut -> back panel boss
    yK_front = Y_HELIX - HELIX_FACE / 2 - 0.05
    shaft("Shaft_K", K.x, K.y, yK_front, back_y0 - 0.005, SHAFT_R, "spur_wheel", "shaftK")
    mb = MB()
    mb.tube(0.05, SHAFT_R + 0.001, -(Y_SPUR - 0.046 - 0.002), -(Y_HELIX + 0.06 + 0.002), 48)
    ob = make_obj("Collar_K", finish_mesh("Collar_K", mb, radians(35)), M_STEEL, loc=(K.x, 0, K.y), rot=(RX, 0, 0),
                  bevel=0.002, group="shaftK", moving=True)
    add_driver(ob, "rotation_euler", 2, lin_expr(*ph["spur_wheel"]), ctrl)
    me = nut_mesh("Nut_K", 0.045, SHAFT_R + 0.001, 0.028)
    ob = make_obj("Nut_K", me, M_STEEL, loc=(K.x, Y_HELIX - 0.06 - 0.007, K.y), rot=(RX, 0, 0),
                  bevel=0.002, group="shaftK", moving=True, sym=6)
    add_driver(ob, "rotation_euler", 2, lin_expr(*ph["spur_wheel"]), ctrl)

    # ---- bevel pair: apex at (0, 0, zb)
    rP = BEVEL_M * Z_BEVEL_PINION / 2
    rW = BEVEL_M * Z_BEVEL_WHEEL / 2
    A = sqrt(rP * rP + rW * rW)
    dP = atan2(rP, rW)
    dW = pi / 2 - dP
    me, binfo_p = build_bevel_mesh("Bevel_Pinion", BEVEL_M, Z_BEVEL_PINION, dP, A, BEVEL_FACE, BEVEL_BACKLASH,
                                   0.06, 0.07, SHAFT_R + 0.001, inset=0.005)
    y_axis_gear("Bevel_Pinion", me, M_BEVEL, 0.0, 0.0, zb, "bevel_pinion", "shaftH", Z_BEVEL_PINION)
    META["gears"]["Bevel_Pinion"] = dict(type="bevel", z=Z_BEVEL_PINION, m=BEVEL_M, rp=rP, delta=dP, A=A,
                                         ra=binfo_p["ra_heel"], face=BEVEL_FACE)
    wheel_holes = [circle(0.02, 24, polar(0.105, pi / 6 + i * pi / 3), pi / 6 + i * pi / 3) for i in range(6)]
    me, binfo_w = build_bevel_mesh("Bevel_Wheel", BEVEL_M, Z_BEVEL_WHEEL, dW, A, BEVEL_FACE, BEVEL_BACKLASH,
                                   0.07, 0.06, SHAFT_R + 0.001, holes=wheel_holes)
    ob = make_obj("Bevel_Wheel", me, M_BEVEL, loc=(0, 0, zb), rot=(pi, 0, ph["bevel_wheel"][0]), bevel=0.0025,
                  group="shaftV", moving=True, sym=6)
    add_driver(ob, "rotation_euler", 2, lin_expr(*ph["bevel_wheel"]), ctrl)
    META["gears"]["Bevel_Wheel"] = dict(type="bevel", z=Z_BEVEL_WHEEL, m=BEVEL_M, rp=rW, delta=dW, A=A,
                                        ra=binfo_w["ra_heel"], face=BEVEL_FACE, holes=6)
    META["pairs"].append(dict(a="Bevel_Pinion", b="Bevel_Wheel", type="bevel"))

    # shaft H : helical wheel (front) -> bevel pinion (inside)
    yH_front = Y_HELIX - HELIX_FACE / 2 - 0.05
    yH_back = -binfo_p["z_front"] - 0.002
    shaft("Shaft_H", W.x, W.y, yH_front, yH_back, SHAFT_R, "helix_wheel", "shaftH")
    me = nut_mesh("Nut_H", 0.045, SHAFT_R + 0.001, 0.028)
    ob = make_obj("Nut_H", me, M_STEEL, loc=(W.x, Y_HELIX - 0.06 - 0.007, W.y), rot=(RX, 0, 0),
                  bevel=0.002, group="shaftH", moving=True, sym=6)
    add_driver(ob, "rotation_euler", 2, lin_expr(*ph["helix_wheel"]), ctrl)

    # ---- planetary on the top plate
    zg = tz1 + 0.005 + PLANET_FACE / 2
    ss = spur_spec(PLANET_M, Z_SUN)
    ps = spur_spec(PLANET_M, Z_PLANET)
    rs = ring_spec(PLANET_M, Z_RING, backlash=2 * RING_BACKLASH - BACKLASH)   # planet already gives BACKLASH/2
    rc = ss["rp"] + ps["rp"]
    me = build_spur_mesh("Sun", ss, PLANET_FACE, [(0.075, PLANET_FACE / 2 - 0.008), (0.05, PLANET_FACE / 2),
                                                  (SHAFT_R + 0.001, None)])
    ob = make_obj("Sun", me, M_PLANET, loc=(0, 0, zg), rot=(0, 0, ph["sun"][0]), bevel=0.002,
                  group="shaftV", moving=True, sym=Z_SUN)
    add_driver(ob, "rotation_euler", 2, lin_expr(*ph["sun"]), ctrl)
    gear_meta("Sun", "sun", ss, dict(face=PLANET_FACE))
    # carrier (output): 3-arm plate + pins + stepped round cap
    cz0 = zg + PLANET_FACE / 2 + CARRIER_LIFT
    mb = MB()
    arms = []
    for k in range(N_PLANETS):
        a = 2 * pi * k / N_PLANETS
        arms.append(convex_hull(circle(CARRIER_HUB_R, 48) + circle(CARRIER_BOSS_R, 48, polar(rc, a), a)))
    star = []
    NS = 360
    for i in range(NS):
        a = 2 * pi * i / NS
        best = CARRIER_HUB_R
        for hpoly in arms:
            # ray from origin, intersect convex polygon boundary
            dx, dy = cos(a), sin(a)
            for j in range(len(hpoly)):
                p, q = hpoly[j], hpoly[(j + 1) % len(hpoly)]
                ex, ey = q[0] - p[0], q[1] - p[1]
                den = dx * ey - dy * ex
                if abs(den) < 1e-12:
                    continue
                t = (p[0] * ey - p[1] * ex) / den
                u = (p[0] * dy - p[1] * dx) / den
                if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                    best = max(best, t)
        star.append(polar(best, a))
    pin_holes = []
    mb.prism(star, [circle(SHAFT_R + 0.006, 48)], cz0 - zg, cz0 - zg + 0.035)
    for k in range(N_PLANETS):
        pc = polar(rc, 2 * pi * k / N_PLANETS)
        mb.cyl(0.025, -PLANET_FACE / 2 + 0.004, cz0 - zg + 0.005, 24, M=Matrix.Translation((pc[0], pc[1], 0)))
        mb.lathe([(0, cz0 - zg + 0.045), (0.03, cz0 - zg + 0.045), (0.036, cz0 - zg + 0.038),
                  (0.036, cz0 - zg + 0.03), (0, cz0 - zg + 0.03)], 48, M=Matrix.Translation((pc[0], pc[1], 0)))
    hz = cz0 - zg + 0.035
    hr = CARRIER_HUB_R
    mb.lathe([(SHAFT_R + 0.006, hz - 0.01), (hr, hz - 0.01), (hr, hz + 0.025), (hr - 0.008, hz + 0.03),
              (hr - 0.014, hz + 0.03), (hr - 0.014, hz + 0.055), (hr - 0.02, hz + 0.06),
              (SHAFT_R + 0.006, hz + 0.06)], 96)
    carrier = make_obj("Carrier", finish_mesh("Carrier", mb, radians(35)), M_CARRIER, loc=(0, 0, zg),
                       rot=(0, 0, ph["carrier"][0]), bevel=0.003, group="carrier", moving=True, sym=N_PLANETS)
    add_driver(carrier, "rotation_euler", 2, lin_expr(*ph["carrier"]), ctrl)
    cap_top = zg + hz + 0.06
    # cap studs (static look on the rotating cap)
    # planets (children of carrier, local spin driven)
    planet_holes = [circle(0.021, 24, polar(0.108, i * 2 * pi / 9), i * 2 * pi / 9) for i in range(9)]
    for k in range(N_PLANETS):
        me = build_spur_mesh("Planet_%d" % (k + 1), ps, PLANET_FACE,
                             [(0.162, PLANET_FACE / 2 - 0.012), (0.05, PLANET_FACE / 2), (0.03, None)],
                             holes={1: planet_holes})
        pc = polar(rc, 2 * pi * k / N_PLANETS)
        ob = make_obj("Planet_%d" % (k + 1), me, M_PLANET, loc=(pc[0], pc[1], 0),
                      rot=(0, 0, ph["planet_%d" % k][0]), bevel=0.002, group="planet%d" % k, moving=True,
                      sym=9, equiv="planets", parent=carrier)
        add_driver(ob, "rotation_euler", 2, lin_expr(*ph["planet_%d" % k]), ctrl)
        gear_meta(ob.name, "planet", ps, dict(holes=9, face=PLANET_FACE))
        META["pairs"].append(dict(a="Sun", b=ob.name, type="external"))
        META["pairs"].append(dict(a="Ring", b=ob.name, type="internal"))
    # ring (fixed into the top plate)
    # ring outline period has a SPACE centred at d = 0, so bake in pi/zr -> ring TOOTH on +X
    me = build_ring_mesh("Ring", rs, PLANET_FACE + 0.01, rs["rf"] + 0.055, pi / Z_RING)
    make_obj("Ring", me, M_RING, loc=(0, 0, zg), rot=(0, 0, ring_phase), bevel=0.002,
             group="static", moving=False)
    META["gears"]["Ring"] = dict(type="ring", z=Z_RING, m=PLANET_M, rp=rs["rp"], ra=rs["ra"], rf=rs["rf"],
                                 face=PLANET_FACE + 0.01)
    for i in range(8):
        a = pi / 8 + i * pi / 4
        p = polar(rs["rf"] + 0.03, a)
        bolt((p[0], p[1], zg + (PLANET_FACE + 0.01) / 2), (0, 0, 1), 0.016, 0.01)

    # vertical shaft V : lower bracket -> through top plate -> sun -> carrier cap -> nut
    z_wheel_low = zb - binfo_w["z_back"]
    zV0 = z_wheel_low - 0.06
    zV1 = cap_top + 0.04
    mb = MB()
    mb.cyl(SHAFT_R, zV0, zV1, 48)
    ob = make_obj("Shaft_V", finish_mesh("Shaft_V", mb, radians(35)), M_STEEL, rot=(0, 0, 0), bevel=0.002,
                  group="shaftV", moving=True)
    add_driver(ob, "rotation_euler", 2, lin_expr(*ph["sun"]), ctrl)
    me = nut_mesh("Nut_V", 0.042, SHAFT_R + 0.001, 0.028, washer=False)
    ob = make_obj("Nut_V", me, M_STEEL, loc=(0, 0, cap_top + 0.001), rot=(0, 0, 0), bevel=0.002,
                  group="shaftV", moving=True, sym=6)
    add_driver(ob, "rotation_euler", 2, lin_expr(*ph["sun"]), ctrl)

    # ========================================================= gear supports (static)
    mb = MB()
    # back-panel boss for shaft K + mid pillow block
    Mback = lambda x, z: Matrix.Translation((x, 0, z)) @ Matrix.Rotation(RX, 4, 'X')
    mb.lathe([(SHAFT_R + 0.004, -(back_y0 - 0.075)), (0.075, -(back_y0 - 0.075)), (0.075, -(back_y0 - 0.02)),
              (0.1, -(back_y0 - 0.02)), (0.1, -(back_y0 + 0.01)), (SHAFT_R + 0.004, -(back_y0 + 0.01))], 48,
             M=Mback(K.x, K.y))
    pillow(mb, K.x, K.y, 0.15, 0.14, 0.1, 0.075, SHAFT_R + 0.004, 0.07)
    # hanger from the top plate for shaft H
    yh = -0.48
    mb.box((W.x, yh, (W.y + 0.05 + tz0) / 2 + 0.005), (0.07, 0.06, tz0 - (W.y + 0.05) + 0.01), 0.008)
    mb.lathe([(SHAFT_R + 0.004, -(yh + 0.035)), (0.065, -(yh + 0.035)), (0.065, -(yh - 0.035)),
              (SHAFT_R + 0.004, -(yh - 0.035))], 48, M=Mback(W.x, W.y))
    # top plate bearing housing for shaft V
    mb.lathe([(SHAFT_R + 0.004, tz0 - 0.08), (0.07, tz0 - 0.08), (0.07, tz0 - 0.03), (0.1, tz0 - 0.02),
              (0.1, tz0 + 0.001), (SHAFT_R + 0.004, tz0 + 0.001)], 48)
    # lower bracket for shaft V (arm from the back panel)
    zl1 = z_wheel_low - 0.008
    zl0 = zl1 - 0.075
    mb.lathe([(SHAFT_R + 0.004, zl0), (0.065, zl0), (0.065, zl1), (SHAFT_R + 0.004, zl1)], 48)
    mb.box((0, (0.05 + back_y0) / 2, zl0 + 0.025), (0.07, back_y0 - 0.05 + 0.01, 0.05), 0.006)
    make_obj("Gear_Supports", finish_mesh("Gear_Supports", mb, radians(35)), M_ENGINE, bevel=0.004)

    make_obj("Bolts", finish_mesh("Bolts", bolts, radians(35)), M_STEEL)

    # optional brand text on the top plate
    if BRAND_TEXT:
        cu = bpy.data.curves.new("LGE_BrandText", 'FONT')
        cu[GEN_TAG] = True
        cu.body = BRAND_TEXT
        cu.align_x = 'CENTER'
        cu.align_y = 'CENTER'
        cu.size = 0.065
        cu.extrude = 0.006
        tob = bpy.data.objects.new("BrandText", cu)
        col.objects.link(tob)
        tob.data.materials.append(M_FRAME)
        tob.location = (0.0, -0.69, tz1)

    # ========================================================= checks & table
    print_and_check(ph, planet_world, W, K, C, ring_phase)

    # ========================================================= scene settings
    setup_scene(scene, col)
    META["frames"] = FRAMES
    META["crank_turns"] = CRANK_TURNS
    META["fps"] = FPS
    scene["lge_meta"] = json.dumps(META)
    for ob_name, path, index, drv in DRIVERS:
        assert drv.is_simple_expression, ("driver is not a simple expression", ob_name, path, drv.expression)
    print("[LGE] %d drivers, all simple expressions (work with Auto Run Python Scripts off)" % len(DRIVERS))
    return scene


def print_and_check(ph, planet_world, W, K, C, ring_phase):
    N = CRANK_TURNS
    rows = [
        ("Spur_CrankPinion", "spur", Z_CRANK_PINION, SPUR_M, "crank_pinion", Z_CRANK_PINION),
        ("Spur_Wheel", "spur", Z_SPUR_WHEEL, SPUR_M, "spur_wheel", 6),
        ("Helical_Pinion", "helical", Z_HELIX_PINION, HELIX_MN, "helix_pinion", Z_HELIX_PINION),
        ("Helical_Wheel", "helical", Z_HELIX_WHEEL, HELIX_MN, "helix_wheel", 6),
        ("Bevel_Pinion", "bevel", Z_BEVEL_PINION, BEVEL_M, "bevel_pinion", Z_BEVEL_PINION),
        ("Bevel_Wheel", "bevel", Z_BEVEL_WHEEL, BEVEL_M, "bevel_wheel", 6),
        ("Sun", "sun", Z_SUN, PLANET_M, "sun", Z_SUN),
        ("Carrier", "carrier", 0, 0, "carrier", N_PLANETS),
    ]
    print("[LGE] %-17s %-8s %5s %7s %8s %12s %10s %9s" % ("name", "type", "teeth", "module", "pitch_D",
                                                           "ratio/crank", "turns/loop", "phase"))
    ok = True
    for name, typ, z, m, key, sym in rows:
        P, R = ph[key]
        turns = R * N
        dia = m * z * (1 / cos(HELIX_BETA) if typ == "helical" else 1.0)
        good = abs(turns * sym - round(turns * sym)) < 1e-9
        ok &= good
        print("[LGE] %-17s %-8s %5s %7.4f %8.4f %12.6f %10.5f %9.4f %s" % (
            name, typ, z or "-", m, dia, R, turns, P, "" if good else "<-- NOT LOOPING"))
    for k in range(N_PLANETS):
        Pw, Rw = planet_world[k]
        print("[LGE] %-17s %-8s %5d %7.4f %8.4f %12.6f %10.5f %9.4f  (world spin; local %.5f turns)" % (
            "Planet_%d" % (k + 1), "planet", Z_PLANET, PLANET_M, PLANET_M * Z_PLANET, Rw, Rw * N, Pw,
            ph["planet_%d" % k][1] * N))
    print("[LGE] %-17s %-8s %5d %7.4f %8.4f %12s %10s %9.4f" % ("Ring", "ring", Z_RING, PLANET_M,
                                                                 PLANET_M * Z_RING, "fixed", "0", ring_phase))
    # planets: planet k ends in slot k+j; its world phase must match the original occupant mod 2pi/9
    Rc = ph["carrier"][1]
    j = Rc * N * N_PLANETS
    assert abs(j - round(j)) < 1e-9, "carrier does not advance a whole number of planet pitches"
    j = int(round(j)) % N_PLANETS
    for k in range(N_PLANETS):
        end = planet_world[k][0] + planet_world[k][1] * 2 * pi * N
        start = planet_world[(k + j) % N_PLANETS][0]
        q = (end - start) / (2 * pi / 9)
        good = abs(q - round(q)) < 1e-9
        ok &= good
    # wagon-wheel guard: teeth must move well under half a tooth pitch per frame
    worst = (0.0, "")
    for name, typ, z, m, key, sym in rows:
        if z:
            fr = abs(ph[key][1]) * N * z / FRAMES
            worst = max(worst, (fr, name))
    for k in range(N_PLANETS):
        fr = max(abs(planet_world[k][1]), abs(ph["planet_%d" % k][1])) * N * Z_PLANET / FRAMES
        worst = max(worst, (fr, "Planet_%d" % (k + 1)))
    print("[LGE] fastest tooth motion: %.3f pitch/frame (%s), limit %.2f" % (worst[0], worst[1], MAX_PITCH_PER_FRAME))
    assert worst[0] <= MAX_PITCH_PER_FRAME + 1e-9, "gear teeth move too fast per frame (aliasing)"
    print("[LGE] crank turns/loop %d, frames %d @ %d fps; carrier %.4f turns/loop; loop closure %s" % (
        N, FRAMES, FPS, Rc * N, "OK" if ok else "FAILED"))
    assert ok, "loop does not close"


def setup_scene(scene, col):
    scene.frame_start = 1
    scene.frame_end = FRAMES
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = RESOLUTION
    scene.render.resolution_y = RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.display.render_aa = '16'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.studio_light = STUDIO_LIGHT
    sh.color_type = 'MATERIAL'
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sh.cavity_ridge_factor = 1.0
    sh.cavity_valley_factor = 1.0
    sh.curvature_ridge_factor = 0.6
    sh.curvature_valley_factor = 0.8
    sh.show_shadows = True
    sh.shadow_intensity = 0.45
    sh.show_specular_highlight = True
    sh.show_object_outline = False
    scene.display.light_direction = (-0.45, -0.35, 0.82)
    scene.display.shadow_shift = 0.1
    scene.display.shadow_focus = 0.1
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    # world (flat mid-grey background)
    wo = bpy.data.worlds.get("LGE_World")
    if wo is None:
        wo = bpy.data.worlds.new("LGE_World")
        wo[GEN_TAG] = True
    bg = srgb_to_linear(COL_BG)
    wo.color = bg
    scene.world = wo
    # camera
    cam_data = bpy.data.cameras.new("LGE_Camera")
    cam_data[GEN_TAG] = True
    cam_data.lens = CAM_LENS
    cam_data.sensor_width = 36
    cam_data.clip_start = 0.05
    cam_data.clip_end = 100
    cam = bpy.data.objects.new("LGE_Camera", cam_data)
    col.objects.link(cam)
    target = Vector(CAM_TARGET)
    d = Vector((-sin(CAM_AZIMUTH) * cos(CAM_ELEVATION), -cos(CAM_AZIMUTH) * cos(CAM_ELEVATION), sin(CAM_ELEVATION)))
    cam.location = target + d * CAM_DISTANCE
    direction = target - cam.location
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam


def parse_args():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    out = {"save": None, "still": None, "frame": 1, "stills": None, "frames": None}
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--save", "--still", "--stills", "--frames", "--frame") and i + 1 < len(args):
            out[a[2:]] = args[i + 1]
            i += 2
        else:
            i += 1
    return out


def render_still(scene, path, frame):
    scene.frame_set(int(frame))
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.filepath = os.path.abspath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.render.render(write_still=True)
    print("[LGE] rendered frame %s -> %s" % (frame, path))


def main():
    args = parse_args()
    scene = build()
    scene.frame_set(1)
    if args["save"]:
        p = os.path.abspath(args["save"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=p)
        print("[LGE] saved", p)
    if args["still"]:
        render_still(scene, args["still"], args["frame"])
    if args["stills"]:
        frames = [int(x) for x in (args["frames"] or "1").split(",")]
        for f in frames:
            render_still(scene, os.path.join(args["stills"], "frame_%04d.png" % f), f)
    scene.frame_set(1)


if __name__ == "__main__":
    main()
