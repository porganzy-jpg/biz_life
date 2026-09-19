# -*- coding: utf-8 -*-
"""3층 천국 버스 — 스타일라이즈드 저폴리 모델 + 턴테이블 렌더.
blender -b --python blender_bus.py -- <out_dir> [frames]
"""
import bpy, sys, os, math
argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "."
FRAMES = int(argv[1]) if len(argv) > 1 else 24
NIGHT = len(argv) > 2 and argv[2] == "night"
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def hexcol(h): h=h.lstrip('#'); return tuple(int(h[i:i+2],16)/255 for i in (0,2,4))
def mat(name, hexc, rough=0.6, emit=None, strength=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*hexcol(hexc), 1); b.inputs["Roughness"].default_value = rough
    if emit: b.inputs["Emission Color"].default_value = (*hexcol(emit),1); b.inputs["Emission Strength"].default_value = strength
    return m
M = dict(orange=mat("orange","#E8734A"), cream=mat("cream","#F6E7C8"), wood=mat("wood","#8B5A2B",0.8),
         roof=mat("roof","#C94E3B"), sky=mat("skyblue","#87CEEB"), dark=mat("dark","#3A2E2A",0.9),
         tire=mat("tire","#2B2B2B",0.95), glass=mat("glass","#FFD27A",0.3,"#FFB347",6.0),
         green=mat("green","#7BC67E"), pink=mat("pink","#F2A7B5"), white=mat("white","#FAFAFA"),
         chrome=mat("chrome","#D9D9D9",0.2))
root = bpy.data.objects.new("BusRoot", None); sc.collection.objects.link(root)

def add(prim, name, loc, scale, m, rot=(0,0,0), parent=root, **kw):
    getattr(bpy.ops.mesh, prim)(location=loc, rotation=rot, **kw)
    o = bpy.context.object; o.name = name; o.scale = scale; o.data.materials.append(m); o.parent = parent
    bpy.ops.object.shade_smooth() if prim != "primitive_cube_add" else None
    return o
cube = lambda n,l,s,m,**k: add("primitive_cube_add", n, l, [v/2 for v in s], m, **k)
cyl  = lambda n,l,s,m,rot=(0,0,0),**k: add("primitive_cylinder_add", n, l, s, m, rot, vertices=32, **k)

# ── 1F 트럭 베이스 (오렌지) ──
cube("F1", (0,0,1.05), (6.0,2.6,1.7), M["orange"])
cube("Bumper", (3.05,0,0.45), (0.3,2.7,0.35), M["chrome"])
for y in (-0.85, 0.85): add("primitive_uv_sphere_add","Headlight",(3.1,y,0.9),(0.22,0.22,0.22),M["glass"])
cube("Cab", (2.2,0,1.05), (1.3,2.62,1.3), M["cream"])           # 운전석 크림색
cube("Windshield", (2.86,0,1.25), (0.05,2.0,0.8), M["glass"])
for x in (-2.0, 1.4):                                              # 바퀴 4개
    for y in (-1.35, 1.35):
        cyl(f"Wheel", (x,y,0.55), (0.55,0.55,0.18), M["tire"], rot=(math.pi/2,0,0))
        cyl(f"Hub", (x,y*1.02,0.55), (0.28,0.28,0.20), M["chrome"], rot=(math.pi/2,0,0))
# 1F 창문
for x in (-2.4,-1.2,0.0,1.0):
    for y in (-1.32,1.32): cube("Win1",(x,y,1.25),(0.7,0.06,0.6),M["glass"])
# ── 2F 나무 오두막 (크림+나무) ──
cube("F2", (-0.3,0,2.7), (5.2,2.4,1.6), M["cream"])
for i in range(6): cube("Plank",(-0.3,0,2.05+i*0.27),(5.24,2.44,0.06),M["wood"])
for x in (-2.2,-1.0,0.2,1.4):
    for y in (-1.22,1.22):
        cube("Win2",(x,y,2.8),(0.7,0.06,0.7),M["glass"])
        cube("Curtain",(x+0.25,y*1.03,2.8),(0.22,0.04,0.72),[M["pink"],M["sky"],M["green"],M["roof"]][int(abs(x*3))%4])
        cube("Flowerbox",(x,y*1.06,2.4),(0.7,0.14,0.14),M["wood"])
        add("primitive_uv_sphere_add","Flower",(x,y*1.1,2.52),(0.14,0.1,0.1),M["pink"])
# ── 3F 옥상 정원 + 지붕 ──
cube("F3", (-0.8,0,3.95), (4.0,2.1,0.9), M["sky"])
cube("Deck", (-0.8,0,3.52), (5.2,2.5,0.08), M["wood"])
for x in (-3.3,1.7):
    for y in (-1.2,1.2): cyl("Post",(x,y,3.95),(0.05,0.05,0.45),M["white"])
for y in (-1.2,1.2): cube("Rail",(-0.8,y,4.35),(5.0,0.06,0.06),M["white"])
add("primitive_cone_add","Roof",(-0.8,0,4.75),(2.6,1.5,0.5),M["roof"],vertices=4,rot=(0,0,math.pi/4))
cyl("Chimney",(0.4,0.5,4.9),(0.15,0.15,0.5),M["roof"])
for i,(x,c) in enumerate(((-2.5,"pink"),(-1.7,"sky"),(-0.9,"green"),(-0.1,"white"))):  # 빨래
    cube("Laundry",(x,-1.1,4.15),(0.5,0.03,0.4),M[c])
cube("Line",(-1.3,-1.1,4.36),(3.4,0.02,0.02),M["dark"])
cyl("Flagpole",(-3.0,0.9,5.1),(0.03,0.03,0.6),M["white"]); cube("Flag",(-2.8,0.9,5.5),(0.4,0.02,0.25),M["orange"])
for x in (-2.8,-1.2,0.6):  # 옥상 화분/풀
    add("primitive_uv_sphere_add","Bush",(x,0.6,3.75),(0.3,0.3,0.25),M["green"])
# ── 바닥 원판 + 조명 + 카메라 ──
cyl("Ground",(0,0,-0.02),(9,9,0.02),M["green"],parent=None)
bpy.ops.object.light_add(type='SUN', location=(6,-6,9), rotation=(math.radians(48),0,math.radians(40))); bpy.context.object.data.energy = 4.0
bpy.ops.object.light_add(type='AREA', location=(-5,5,5)); bpy.context.object.data.energy = 600; bpy.context.object.data.size = 6
w = bpy.data.worlds.new("W"); w.use_nodes = True; bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (*hexcol("#7EC8F0"),1); bg.inputs[1].default_value = 0.7; sc.world = w
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'; sc.view_settings.exposure = -0.35
if NIGHT:
    bg.inputs[0].default_value = (*hexcol('#2C3E6B'),1); bg.inputs[1].default_value = 0.25; sc.view_settings.exposure = -0.6
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and o.data.type == 'SUN': o.data.energy = 0.35; o.data.color = (0.6,0.7,1.0)
        if o.type == 'LIGHT' and o.data.type == 'AREA': o.data.energy = 80; o.data.color = (0.5,0.6,1.0)
    M['glass'].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 3.5
    M['green'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*hexcol('#2F4A3A'),1)
cam_dist, cam_h = 16.5, 6.0
bpy.ops.object.camera_add(location=(cam_dist*math.cos(math.radians(-40)), cam_dist*math.sin(math.radians(-40)), cam_h))
cam = bpy.context.object; sc.camera = cam
tgt = bpy.data.objects.new("Target", None); sc.collection.objects.link(tgt); tgt.location=(-0.3,0,2.4)
c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis='TRACK_NEGATIVE_Z'; c.up_axis='UP_Y'
cam.data.lens = 45
# ── 턴테이블 ──
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
root.rotation_euler = (0,0,0); root.keyframe_insert("rotation_euler", frame=1)
root.rotation_euler = (0,0,math.radians(360)); root.keyframe_insert("rotation_euler", frame=FRAMES+1)
sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.engine = 'BLENDER_EEVEE'; sc.eevee.taa_render_samples = 24
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
sc.render.image_settings.file_format = 'PNG'; sc.render.film_transparent = False
# GLB (게임용)
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name != "Ground": o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,"heaven_bus.glb"), export_format='GLB', use_selection=True)
# 히어로 스틸 + 턴테이블
if NIGHT:
    sc.frame_set(1); sc.render.filepath = os.path.join(OUT,"bus_night.png"); bpy.ops.render.render(write_still=True)
else:
    sc.frame_set(1); sc.render.filepath = os.path.join(OUT,"bus_hero.png"); bpy.ops.render.render(write_still=True)
    sc.render.filepath = os.path.join(OUT,"turntable","f_"); bpy.ops.render.render(animation=True)
print("BUS DONE", bpy.app.version_string, "frames", FRAMES)
