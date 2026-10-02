# Export engine.blend to web/engine.glb with the driver animation sampled.
#   blender -b engine.blend --python tools/export_glb.py
#
# For the exploded view, merged meshes (all bolts, all frame beams, ...) are split into one object per
# loose part, named <Prefix>_<NN>, with the origin at the part's own centre. engine.blend is not modified.
import bpy, os

SPLIT = {  # mesh object -> prefix of the separated parts
    "Bolts": "Bolt", "Frame_Beams": "Beam", "Frame_Corners": "Corner", "Frame_Feet": "Foot",
    "Frame_Lips": "Lip", "Engine_Frame": "EngineFrame", "Gear_Supports": "Support",
    "Panel_Back": "PanelBack", "Panel_Right": "PanelRight", "Panel_Top": "PanelTop",
}

s = bpy.context.scene
s.frame_start, s.frame_end = 1, 301  # frame 301 == frame 1, so the clip loops without a hitch
vl = bpy.context.view_layer
coll = bpy.data.collections["LightGearEngine"]

for src, prefix in SPLIT.items():
    ob = bpy.data.objects[src]
    for o in vl.objects:
        o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    parts = [o for o in vl.objects if o.select_get()]
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    # stable names: sort by position (x, then y, then z)
    parts.sort(key=lambda o: (round(o.location.x, 3), round(o.location.y, 3), round(o.location.z, 3)))
    for i, o in enumerate(parts, 1):
        o.name = f"{prefix}_{i:02d}"
        o.data.name = o.name
    print("SPLIT", src, "->", len(parts))

out = os.path.join(os.path.dirname(bpy.data.filepath), "web", "engine.glb")
for o in vl.objects:
    o.select_set(False)
for o in coll.all_objects:
    if o.type == 'MESH':
        o.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=out, export_format='GLB', use_selection=True,
    export_apply=True, export_animations=True, export_animation_mode='SCENE',
    export_frame_range=True, export_force_sampling=True, export_optimize_animation_size=True,
    export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
    export_cameras=False, export_lights=False, export_yup=True)
print("EXPORTED", out, os.path.getsize(out))
