import bpy
import math
import datetime
import os
import random
import gpu
import traceback
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Euler, Quaternion
from bpy_extras.io_utils import ImportHelper
from bpy.props import (
    EnumProperty, FloatProperty, IntProperty, PointerProperty,
    StringProperty, CollectionProperty, BoolProperty,
)

bl_info = {
    "name": "Logic Substepp'n",
    "author": "Royal",
    "version": (9, 7, 2),
    "blender": (5, 0, 0),
    "location": "View3D > N Panel > Logic Substepp'n",
    "description": "Logic Cockpit™: Smoov'mnt Curves, DeckFlow™, Recoil Micro-steps, and No Touchy Kinematic Safety.",
    "category": "Logic Substepp'n",
}

# Global Crash Cache & AAAA Physics Memory
_LS_CRASH_TRACE = ""
_QUANTUM_LUT = {}
_PHYSICS_VELOCITY = {}

# -------------------------------------------------------
# THE MASSIVE KINEMATIC LIBRARY (NO TOUCHY)
# -------------------------------------------------------

DOMAIN_TYPES = [
    ('MECHANICAL', "Mechanical / Hard Surface", ""),
    ('LIFEFORM', "Lifeforms", ""),
    ('PLANT', "Flora / Organics", "")
]

MATTER_MECHANICAL = [
    ('TUNGSTEN', "Tungsten (19,250)", ""), ('GOLD', "Gold (19,300)", ""),
    ('STEEL', "Steel (7,850)", ""), ('TITANIUM', "Titanium (4,500)", ""),
    ('ALUMINUM', "Aluminum (2,700)", ""), ('CARBON_FIBER', "Carbon Fiber (1,600)", ""),
    ('KEVLAR', "Kevlar (1,440)", ""), ('POLYCARBONATE', "Polycarbonate (1,200)", ""),
    ('ABS_PLASTIC', "ABS Plastic (1,060)", ""), ('RUBBER_HARD', "Tire Rubber (1,150)", ""),
    ('RUBBER_SOFT', "Silicone Rubber (900)", ""), ('FOAM', "Polyurethane Foam (50)", ""),
    ('CONCRETE', "Concrete (2,400)", ""), ('LEATHER', "Leather (950)", ""),
    ('CLOTH', "Silk/Cotton (150)", "")
]

MATTER_LIFEFORM = [
    ('ENAMEL', "Tooth Enamel (2,900)", ""), ('CORTICAL_BONE', "Cortical Bone (1,900)", ""),
    ('CHITIN', "Chitin Shell (1,400)", ""), ('KERATIN', "Keratin/Claw (1,300)", ""),
    ('CARTILAGE', "Cartilage (1,100)", ""), ('MUSCLE_FLEXED', "Muscle Flexed (1,090)", ""),
    ('MUSCLE_RELAXED', "Muscle Relaxed (1,060)", ""), ('SKIN', "Skin (1,100)", ""),
    ('FAT', "Adipose Fat (900)", ""), ('DRAGON_SCALE', "Dragon Scale (1,500)", ""),
    ('REPTILE_SCALE', "Reptile Scale (1,300)", ""), ('ANIMAL_HIDE', "Thick Hide (1,100)", ""),
    ('HAIR', "Packed Hair (400)", ""), ('FUR', "Thick Fur (150)", ""),
    ('FEATHER_STIFF', "Stiff Feathers (300)", ""), ('FEATHER_DOWN', "Down Feathers (50)", "")
]

MATTER_PLANT = [
    ('IRONWOOD', "Ironwood (1,210)", ""), ('OAK', "Oak Wood (800)", ""),
    ('PINE', "Pine Wood (500)", ""), ('BAMBOO', "Bamboo (400)", ""),
    ('BALSA', "Balsa Wood (160)", ""), ('BARK', "Tree Bark (450)", ""),
    ('VINE', "Fibrous Vine (600)", ""), ('AMBER', "Solid Amber (1,070)", ""),
    ('KELP', "Wet Kelp (1,000)", ""), ('CACTUS', "Cactus Body (950)", ""),
    ('LEAF', "Green Leaf (800)", ""), ('MUSHROOM', "Fungi Cap (300)", ""),
    ('PEAT', "Wet Peat (600)", "")
]

DENSITY_MAP = {
    'TUNGSTEN': 19250, 'GOLD': 19300, 'STEEL': 7850, 'TITANIUM': 4500, 'ALUMINUM': 2700,
    'CARBON_FIBER': 1600, 'KEVLAR': 1440, 'POLYCARBONATE': 1200, 'ABS_PLASTIC': 1060,
    'RUBBER_HARD': 1150, 'RUBBER_SOFT': 900, 'FOAM': 50, 'CONCRETE': 2400, 'LEATHER': 950, 'CLOTH': 150,
    'ENAMEL': 2900, 'CORTICAL_BONE': 1900, 'CHITIN': 1400, 'KERATIN': 1300, 'CARTILAGE': 1100,
    'MUSCLE_FLEXED': 1090, 'MUSCLE_RELAXED': 1060, 'SKIN': 1100, 'FAT': 900, 'DRAGON_SCALE': 1500,
    'REPTILE_SCALE': 1300, 'ANIMAL_HIDE': 1100, 'HAIR': 400, 'FUR': 150, 'FEATHER_STIFF': 300, 'FEATHER_DOWN': 50,
    'IRONWOOD': 1210, 'OAK': 800, 'PINE': 500, 'BAMBOO': 400, 'BALSA': 160, 'BARK': 450,
    'VINE': 600, 'AMBER': 1070, 'KELP': 1000, 'CACTUS': 950, 'LEAF': 800, 'MUSHROOM': 300, 'PEAT': 600
}

def update_deck_mass(self, context):
    if hasattr(self, "physics_matter"):
        density = DENSITY_MAP.get(self.physics_matter, 1000.0)
        self.mass = max(0.001, density / 1000.0)

def get_deck_massive_library(self, context):
    if self.physics_domain == 'MECHANICAL': return MATTER_MECHANICAL
    elif self.physics_domain == 'LIFEFORM': return MATTER_LIFEFORM
    elif self.physics_domain == 'PLANT': return MATTER_PLANT
    return MATTER_MECHANICAL
    
# -------------------------------------------------------
# AAAA MATH CORE (Catmull-Rom & fBm Noise)
# -------------------------------------------------------
def catmull_rom_vec(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2.0 * p1) + (-p0 + p2) * t + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3)

def fbm_noise(x, octaves=3, persistence=0.5, lacunarity=2.0):
    total, freq, amp, max_val = 0.0, 1.0, 1.0, 0.0
    for i in range(octaves):
        total += math.sin(x * freq) * amp
        max_val += amp
        amp *= persistence
        freq *= lacunarity
    return total / max_val if max_val > 0 else 0.0

def evaluate_micro_step(mapping, raw_t):
    steps = mapping.steps; n = len(steps)
    if n == 0: return Vector((0,0,0)), Euler((0,0,0)), Vector((1,1,1))
    if n == 1: return Vector((steps[0].loc_x, steps[0].loc_y, steps[0].loc_z)), Euler((steps[0].rot_x, steps[0].rot_y, steps[0].rot_z)), Vector((steps[0].scl_x, steps[0].scl_y, steps[0].scl_z))
    
    clamped_t = max(0.0, min(raw_t, n - 1.0))
    idx = int(clamped_t); t = clamped_t - idx
    i0 = max(0, idx - 1); i1 = idx; i2 = min(n - 1, idx + 1); i3 = min(n - 1, idx + 2)
    s0, s1, s2, s3 = steps[i0], steps[i1], steps[i2], steps[i3]
    
    preset = s1.smoov_preset
    blend = s1.smoov_blend
    t_lin = t
    
    if preset == 'BEZIER': t_curve = t * t * (3.0 - 2.0 * t)
    elif preset == 'VISCOUS': t_curve = t * t * t
    elif preset == 'CLAMPED': t_curve = 1.0 - (1.0 - t) * (1.0 - t)
    elif preset == 'STEP': t_curve = 0.0
    else: t_curve = t_lin
    
    if preset not in ('LINEAR', 'STEP'):
        t = t_lin * (1.0 - blend) + t_curve * blend
    else:
        t = t_curve
    
    v0, v1, v2, v3 = Vector((s0.loc_x, s0.loc_y, s0.loc_z)), Vector((s1.loc_x, s1.loc_y, s1.loc_z)), Vector((s2.loc_x, s2.loc_y, s2.loc_z)), Vector((s3.loc_x, s3.loc_y, s3.loc_z))
    loc = catmull_rom_vec(v0, v1, v2, v3, t)
    
    q1, q2 = Euler((s1.rot_x, s1.rot_y, s1.rot_z)).to_quaternion(), Euler((s2.rot_x, s2.rot_y, s2.rot_z)).to_quaternion()
    rot = q1.slerp(q2, t).to_euler()
    
    sc0, sc1, sc2, sc3 = Vector((s0.scl_x, s0.scl_y, s0.scl_z)), Vector((s1.scl_x, s1.scl_y, s1.scl_z)), Vector((s2.scl_x, s2.scl_y, s2.scl_z)), Vector((s3.scl_x, s3.scl_y, s3.scl_z))
    scl = catmull_rom_vec(sc0, sc1, sc2, sc3, t)
    return loc, rot, scl
    
# -------------------------------------------------------
# VIEWPORT GHOSTING (ARC DRAW HANDLER)
# -------------------------------------------------------
_ls_draw_handler = None

def draw_ghost_arcs():
    context = bpy.context
    s = context.scene
    if not hasattr(s, "logic_sub_mappings") or not s.logic_sub_mappings: return
    
    try: shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    except: shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(3.0)
    
    for d_idx, deck in enumerate(s.logic_sub_decks):
        if not deck.driven_object: continue
        m = get_active_mapping(s, d_idx, create=False)
        if not m: continue
        
        drv_obj, drv_bone, drv_is_bone = get_driven_target(s, d_idx)
        if not drv_obj: continue
        if drv_is_bone and not drv_bone: continue
        
        origin = drv_bone.matrix.translation if drv_is_bone else drv_obj.matrix_world.translation
        
        for tag in m.tags:
            if tag.type == 'GROUPIE' and tag.show_ghosting:
                active = [i for i, gs in enumerate(tag.group_steps) if gs.is_active]
                if len(active) < 2: continue
                
                coords = []
                for i in active:
                    if i < len(m.steps):
                        st = m.steps[i]
                        gr = m.gear_ratio
                        coords.append(origin + Vector((st.loc_x * gr, st.loc_y * gr, st.loc_z * gr)))
                
                if coords:
                    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": coords})
                    shader.uniform_float("color", (0.0, 1.0, 1.0, 0.8))
                    batch.draw(shader)
                    
                    dot_coords = []
                    for i in range(len(active) - 1):
                        start_idx = active[i]
                        for micro in range(1, 10):
                            t_val = start_idx + (micro / 10.0)
                            loc, _, _ = evaluate_micro_step(m, t_val)
                            dot_coords.append(origin + (loc * m.gear_ratio))
                    
                    if dot_coords:
                        try: dot_shader = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
                        except: dot_shader = gpu.shader.from_builtin('3D_POINT_UNIFORM_COLOR')
                        gpu.state.point_size_set(4.0)
                        dot_batch = batch_for_shader(dot_shader, 'POINTS', {"pos": dot_coords})
                        dot_shader.uniform_float("color", (1.0, 0.8, 0.0, 1.0))
                        dot_batch.draw(dot_shader)

# -------------------------------------------------------
# SYSTEM UTILS & LOGGING
# -------------------------------------------------------
def get_substeppn_path(sub_path=""):
    if not bpy.data.filepath: return None  
    base_dir = os.path.join(bpy.path.abspath("//"), "script", "plugins", "LogicLink", "Substeppn")
    full_path = os.path.join(base_dir, sub_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    return full_path

def ls_log(scene, msg):
    scene.logic_sub_status_msg = msg
    txt_name = "LogicSub_Activity_Log.txt"
    txt = bpy.data.texts.get(txt_name)
    if not txt: txt = bpy.data.texts.new(txt_name)
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {msg}"
    txt.write(log_entry + "\n")
    print(f"Logic Substepp'n: {log_entry}")
    ext_path = get_substeppn_path("system/log/Activity_Log.txt")
    if ext_path:
        try:
            with open(ext_path, "a", encoding="utf-8") as f: f.write(log_entry + "\n")
        except: pass

def get_logic_target(scene):
    o = scene.logic_sub_object
    if o and o.type == 'ARMATURE' and getattr(scene, "logic_sub_bone_name", "") in o.pose.bones: 
        return o, o.pose.bones[scene.logic_sub_bone_name], True
    return o, None, False

def get_driven_target(scene, specific_deck_idx=None):
    if not hasattr(scene, "logic_sub_decks"): return None, None, False
    idx = scene.logic_sub_active_deck_idx if specific_deck_idx is None else specific_deck_idx
    if not scene.logic_sub_decks or idx < 0 or idx >= len(scene.logic_sub_decks): return None, None, False
    
    deck = scene.logic_sub_decks[idx]
    o = deck.driven_object
    if o and o.type == 'ARMATURE' and deck.driven_bone in o.pose.bones: 
        return o, o.pose.bones[deck.driven_bone], True
    return o, None, False

def get_active_mapping(scene, specific_deck_idx=None, create=False, force_dir=None):
    t_obj, t_bone, _ = get_logic_target(scene)
    d_obj, d_bone, _ = get_driven_target(scene, specific_deck_idx)
    t_n = t_bone.name if t_bone else (t_obj.name if t_obj else "")
    d_n = d_bone.name if d_bone else (d_obj.name if d_obj else "")
    if not t_n or not d_n: return None
    
    direction = force_dir if force_dir else scene.logic_sub_direction
    dir_suffix = f"__{direction}"
    k = f"{t_n}__TO__{d_n}{dir_suffix}"
    
    for m in scene.logic_sub_mappings:
        if m.name == k: return m
        
    if create:
        m = scene.logic_sub_mappings.add()
        m.name = k
        return m
    return None

def update_data_text(scene):
    if getattr(scene, "logic_sub_is_syncing", False): return
    if not hasattr(scene, "logic_sub_mappings") or not scene.logic_sub_mappings: return
    
    text_name = "LogicSub_Data.txt"
    txt = bpy.data.texts.get(text_name)
    if not txt: txt = bpy.data.texts.new(text_name)
        
    lines = ["=== LOGIC SUBSTEPP'N MASTER DATA ==="]
    
    for mapping in scene.logic_sub_mappings:
        lines.append(f"COMBINATION: {mapping.name.replace('__TO__', ' ➔ ')} | TARGET: {mapping.target_max:.4f}")
        header = f"{'Step':<5} | {'Loc X':<7} | {'Loc Y':<7} | {'Loc Z':<7} | {'Rot X':<7} | {'Rot Y':<7} | {'Rot Z':<7} | {'Scl X':<7} | {'Scl Y':<7} | {'Scl Z':<7} | {'Status':<8}"
        lines.append(header)
        lines.append("-" * len(header))
        
        for i, step in enumerate(mapping.steps):
            rx, ry, rz = math.degrees(step.rot_x), math.degrees(step.rot_y), math.degrees(step.rot_z)
            line = f"{i:<5} | {step.loc_x:>7.3f} | {step.loc_y:>7.3f} | {step.loc_z:>7.3f} | {rx:>7.3f} | {ry:>7.3f} | {rz:>7.3f} | {step.scl_x:>7.3f} | {step.scl_y:>7.3f} | {step.scl_z:>7.3f} | {step.status}"
            lines.append(line)
            
            if step.step_label or step.smoov_preset != 'LINEAR' or step.smoov_blend != 1.0:
                lines.append(f"    -> SMOOV: {step.smoov_preset} | BLEND: {step.smoov_blend:.3f} | TENS: {step.smoov_tension:.3f} | LABEL: {step.step_label}")
            
            for mc in step.mod_con_states:
                if mc.type == 'MOD': lines.append(f"    -> MOD: {mc.name} | View: {1 if mc.show_viewport else 0}")
                else: lines.append(f"    -> {mc.type}: {mc.name} | Inf: {mc.influence:.3f}")
                
                for tp in mc.tracked_props:
                    val_str = f"{tp.val_float:.4f}" if tp.prop_type == 'FLOAT' else (f"{tp.val_int}" if tp.prop_type == 'INT' else f"{1 if tp.val_bool else 0}")
                    lines.append(f"        => {tp.prop_name} : {val_str} : {tp.prop_type}")
        lines.append("\n")
        
    txt_content = "\n".join(lines)
    txt.clear(); txt.write(txt_content)
    
    ext_path = get_substeppn_path("data/autosave/LogicSub_Data_Autosave.txt")
    if ext_path:
        try:
            with open(ext_path, "w", encoding="utf-8") as f: f.write(txt_content)
        except: pass

def apply_logic_transform(context):
    s = context.scene
    trig_obj, trig_bone, trig_is_bone = get_logic_target(s)
    if not trig_obj: return
    
    active_mapping = get_active_mapping(s, create=False)
    if active_mapping:
        t = s.logic_sub_current_step / max(1, active_mapping.substeps)
        v = active_mapping.target_max * t
        if s.logic_sub_direction == 'NEG': v = -v
            
        final = math.radians(v) if 'ROT' in s.logic_sub_channel else v
        trig_tgt = trig_bone if trig_is_bone else trig_obj
        idx = {'X':0,'Y':1,'Z':2}[s.logic_sub_channel[-1]]
        
        if 'LOC' in s.logic_sub_channel: trig_tgt.location[idx] = final
        elif 'ROT' in s.logic_sub_channel: trig_tgt.rotation_euler[idx] = final
        elif 'SCL' in s.logic_sub_channel: trig_tgt.scale[idx] = final

    if getattr(s, "logic_sub_is_previewing", False): return

    if hasattr(s, "logic_sub_decks"):
        for d_idx, deck in enumerate(s.logic_sub_decks):
            mapping = get_active_mapping(s, d_idx, create=False)
            if not mapping or len(mapping.steps) == 0: continue
            
            read_step = s.logic_sub_current_step + mapping.phase_offset
            read_step = max(0, min(read_step, len(mapping.steps) - 1))
            
            step = mapping.steps[read_step]
            gr = mapping.gear_ratio
            
            d_obj, d_bone, d_is_bone = get_driven_target(s, d_idx)
            if not d_obj: continue
            
            d_tgt = d_bone if d_is_bone else d_obj
            d_tgt.location = (step.loc_x * gr, step.loc_y * gr, step.loc_z * gr)
            if d_tgt.rotation_mode not in {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'}: d_tgt.rotation_mode = 'XYZ'
            d_tgt.rotation_euler = (step.rot_x * gr, step.rot_y * gr, step.rot_z * gr)
            d_tgt.scale = (1.0 + (step.scl_x - 1.0) * gr, 1.0 + (step.scl_y - 1.0) * gr, 1.0 + (step.scl_z - 1.0) * gr)
            
            d_obj.update_tag(refresh={'OBJECT', 'DATA'})

def update_global_substeps(self, context):
    s = context.scene
    if getattr(s, "logic_sub_is_syncing", False): return 
    
    active_m = get_active_mapping(s, create=False)
    if not active_m: return
    
    target_len = max(1, active_m.substeps + 1)
    s.logic_sub_current_step = min(s.logic_sub_current_step, active_m.substeps)
    
    t_obj, t_bone, _ = get_logic_target(s)
    if not t_obj: return
    t_n = t_bone.name if t_bone else t_obj.name
    
    for m in s.logic_sub_mappings:
        if m.name.startswith(f"{t_n}__TO__"):
            m.substeps = active_m.substeps
            while len(m.steps) < target_len: m.steps.add()
            while len(m.steps) > target_len: m.steps.remove(len(m.steps)-1)
            
            for tag in m.tags:
                if tag.type == 'GROUPIE':
                    while len(tag.group_steps) < target_len: tag.group_steps.add()
                    while len(tag.group_steps) > target_len: tag.group_steps.remove(len(tag.group_steps)-1)
                
    update_data_text(s); apply_logic_transform(context)

def update_driven_from_slider(self, context):
    s = context.scene
    if getattr(s, "logic_sub_is_capturing", False) or getattr(s, "logic_sub_is_syncing", False): return
    if hasattr(self, "status"): self.status = 'EDITED'
    update_data_text(s); apply_logic_transform(context)

def get_available_mc_props(self, context):
    path = self.path_from_id()
    try:
        if 'logic_sub_mappings["' in path:
            m_name = path.split('logic_sub_mappings["')[1].split('"]')[0]
            target_deck_idx = context.scene.logic_sub_active_deck_idx
            for d_idx, d in enumerate(context.scene.logic_sub_decks):
                m = get_active_mapping(context.scene, d_idx, create=False)
                if m and m.name == m_name:
                    target_deck_idx = d_idx
                    break
            drv_obj, drv_bone, drv_is_bone = get_driven_target(context.scene, target_deck_idx)
        else:
            drv_obj, drv_bone, drv_is_bone = get_driven_target(context.scene)
    except:
        drv_obj, drv_bone, drv_is_bone = get_driven_target(context.scene)
        
    if not drv_obj: return [('NONE', "Select a Target", "")]
    try:
        mc = drv_obj.modifiers.get(self.name) if self.type == 'MOD' else (drv_obj.constraints.get(self.name) if self.type == 'CON' else drv_bone.constraints.get(self.name))
        items = [(k, p.name, "") for k, p in mc.bl_rna.properties.items() if p.type in {'FLOAT', 'INT', 'BOOLEAN'} and not p.is_array and not p.is_readonly]
        return items if items else [('NONE', "No Props", "")]
    except: return [('NONE', "Error", "")]

# -------------------------------------------------------
# SCRUBBER UPDATE HOOKS (BI-DIRECTIONAL SYNC)
# -------------------------------------------------------

def update_scrubber(self, context):
    if getattr(self, "logic_sub_is_syncing", False): return
    self.logic_sub_is_syncing = True
    
    m = get_active_mapping(self, create=False)
    subs = m.substeps if m else 1
    if self.logic_sub_current_step > subs: self.logic_sub_current_step = subs
        
    if self.logic_sub_direction == 'NEG': self.logic_sub_full_scrubber = -self.logic_sub_current_step
    else: self.logic_sub_full_scrubber = self.logic_sub_current_step
        
    apply_logic_transform(context)
    context.view_layer.update()
    self.logic_sub_is_syncing = False

def update_full_scrubber(self, context):
    if getattr(self, "logic_sub_is_syncing", False): return
    self.logic_sub_is_syncing = True
    
    m = get_active_mapping(self, create=False)
    subs = m.substeps if m else 1
    
    val = self.logic_sub_full_scrubber
    if val > subs: val = subs; self.logic_sub_full_scrubber = val
    if val < -subs: val = -subs; self.logic_sub_full_scrubber = val
    
    target_dir = 'NEG' if val < 0 else 'POS'
    if self.logic_sub_direction != target_dir: self.logic_sub_direction = target_dir
    self.logic_sub_current_step = abs(val)
    
    apply_logic_transform(context)
    context.view_layer.update()
    self.logic_sub_is_syncing = False

# -------------------------------------------------------
# DATA CLASSES
# -------------------------------------------------------

class LogicSubClipboard(bpy.types.PropertyGroup):
    has_data: BoolProperty(default=False)
    loc_x: FloatProperty(); loc_y: FloatProperty(); loc_z: FloatProperty()
    rot_x: FloatProperty(); rot_y: FloatProperty(); rot_z: FloatProperty()
    scl_x: FloatProperty(); scl_y: FloatProperty(); scl_z: FloatProperty()

class LogicSubDeckItem(bpy.types.PropertyGroup):
    driven_object: PointerProperty(type=bpy.types.Object)
    driven_bone: StringProperty()
    
    physics_domain: EnumProperty(items=DOMAIN_TYPES, name="Domain", default='MECHANICAL', update=update_deck_mass)
    physics_matter: EnumProperty(items=get_deck_massive_library, name="Matter", update=update_deck_mass)
    
    mass: FloatProperty(name="Mass", default=1.0, min=0.001)
    drag: FloatProperty(name="Drag", default=0.7, min=0.0, max=1.0)
    spring_tension: FloatProperty(name="Spring", default=0.15, min=0.0, max=1.0)
    
    collider_target: PointerProperty(type=bpy.types.Object, name="Collider Target")
    collider_bone: StringProperty(name="Collider Bone")
    collider_margin: FloatProperty(name="Base Margin", default=0.015, min=0.001, max=1.0)

class LogicSubTrackedProp(bpy.types.PropertyGroup):
    prop_name: StringProperty()
    prop_type: EnumProperty(items=[('FLOAT','',''),('INT','',''),('BOOL','','')])
    val_float: FloatProperty(update=update_driven_from_slider)
    val_int: IntProperty(update=update_driven_from_slider)
    val_bool: BoolProperty(update=update_driven_from_slider)

class LogicSubModConState(bpy.types.PropertyGroup):
    name: StringProperty(); type: StringProperty()
    influence: FloatProperty(default=1.0, update=update_driven_from_slider)
    show_viewport: BoolProperty(default=True, update=update_driven_from_slider)
    tracked_props: CollectionProperty(type=LogicSubTrackedProp)
    prop_selector: EnumProperty(items=get_available_mc_props)
    locked_groupie: StringProperty(name="Lock to Groupie")

class LogicSubDrivenStep(bpy.types.PropertyGroup):
    status: EnumProperty(items=[('UNSET','',''),('SET','',''),('EDITED','','')], default='UNSET')
    
    smoov_preset: EnumProperty(
        items=[('LINEAR', 'Linear (Machine)', 'Direct A to B'), 
               ('BEZIER', 'Bezier Smoov', 'Smooth Ease-In and Ease-Out'), 
               ('VISCOUS', 'Viscous (Drag)', 'Heavy ease-in, snap out'), 
               ('CLAMPED', 'Clamped (Snappy)', 'Snap in, heavy ease-out'), 
               ('STEP', 'Step (Hold)', 'Hold position until next step')], 
        name="Smoov Curve", default='LINEAR',
        update=update_driven_from_slider
    )
    smoov_blend: FloatProperty(name="Curve Power", default=1.0, min=0.0, max=1.0, update=update_driven_from_slider)
    smoov_tension: FloatProperty(name="Tension", default=0.5, min=0.0, max=1.0, update=update_driven_from_slider)
    show_smoov_panel: BoolProperty(name="Show Smoov'mnt Panel", default=False)
    step_label: StringProperty(name="Label", default="", update=update_driven_from_slider)

    is_selected_for_batch: BoolProperty()
    show_mod_cons: BoolProperty()
    show_quick_math: BoolProperty()
    show_shuffle: BoolProperty()
    show_nested_deck: BoolProperty(default=False)
    show_cursor_tools: BoolProperty(default=False)
    
    is_bookmarked: BoolProperty(default=False)
    has_snapshot: BoolProperty(default=False)
    snap_loc_x: FloatProperty(); snap_loc_y: FloatProperty(); snap_loc_z: FloatProperty()
    snap_rot_x: FloatProperty(); snap_rot_y: FloatProperty(); snap_rot_z: FloatProperty()
    snap_scl_x: FloatProperty(); snap_scl_y: FloatProperty(); snap_scl_z: FloatProperty()

    qm_loc_x: BoolProperty(); qm_loc_y: BoolProperty(); qm_loc_z: BoolProperty()
    qm_rot_x: BoolProperty(); qm_rot_y: BoolProperty(); qm_rot_z: BoolProperty()
    qm_scl_x: BoolProperty(); qm_scl_y: BoolProperty(); qm_scl_z: BoolProperty()
    qm_val: FloatProperty(name="Value")
    qm_op: EnumProperty(items=[('ADD', 'Add', ''), ('SUB', 'Subtract', ''), ('MULT', 'Multiply', ''), ('DIV', 'Divide', ''), ('INV', 'Invert (* -1)', ''), ('DEC', 'Decimalize (x0.1)', '')])

    loc_x: FloatProperty(update=update_driven_from_slider); loc_y: FloatProperty(update=update_driven_from_slider); loc_z: FloatProperty(update=update_driven_from_slider)
    rot_x: FloatProperty(subtype='ANGLE', update=update_driven_from_slider); rot_y: FloatProperty(subtype='ANGLE', update=update_driven_from_slider); rot_z: FloatProperty(subtype='ANGLE', update=update_driven_from_slider)
    scl_x: FloatProperty(default=1.0, update=update_driven_from_slider); scl_y: FloatProperty(default=1.0, update=update_driven_from_slider); scl_z: FloatProperty(default=1.0, update=update_driven_from_slider)
    mod_con_states: CollectionProperty(type=LogicSubModConState)

class LogicSubTagStep(bpy.types.PropertyGroup): is_active: BoolProperty(default=False)

class LogicSubTag(bpy.types.PropertyGroup):
    name: StringProperty(default="New Track")
    type: EnumProperty(items=[('SEG','Seg',''),('GROUPIE','Groupie','')], default='SEG')
    target_step: IntProperty(default=0, min=0)
    group_steps: CollectionProperty(type=LogicSubTagStep)
    is_selected_for_bridge: BoolProperty(default=False)
    frame_gap: IntProperty(name="Frame Gap", default=5, min=1)
    
    is_expanded: BoolProperty(default=False)
    ease_type: EnumProperty(items=[('LINEAR', 'Linear', ''), ('EASE_IN', 'Ease In', ''), ('EASE_OUT', 'Ease Out', ''), ('EASE_IN_OUT', 'Ease In/Out', ''), ('OVERSHOOT', 'Overshoot', ''), ('BOUNCE', 'Bounce', ''), ('ELASTIC', 'Elastic', '')], default='LINEAR')
    bake_mode: EnumProperty(items=[('ONCE', 'Play Once', ''), ('LOOP', 'Loop', ''), ('PING_PONG', 'Ping-Pong', '')], default='ONCE')
    loop_count: IntProperty(name="Loops", default=1, min=1)
    time_warp: EnumProperty(items=[('CONSTANT', 'Constant', ''), ('ACCEL', 'Accelerate', ''), ('DECEL', 'Decelerate', '')], default='CONSTANT')
    use_jitter: BoolProperty(name="Jitter", default=False)
    jitter_intensity: FloatProperty(name="Intensity", default=0.05, min=0.0)
    extract_root: BoolProperty(name="Root Motion", default=False)
    root_bone: StringProperty(name="Root Bone")
    push_to_nla: BoolProperty(name="Push to NLA", default=False)
    show_ghosting: BoolProperty(name="Show Arc", default=False)

class LogicSubMapping(bpy.types.PropertyGroup):
    name: StringProperty()
    steps: CollectionProperty(type=LogicSubDrivenStep)
    tags: CollectionProperty(type=LogicSubTag)
    target_max: FloatProperty(name="Target Value", default=1.0, update=update_driven_from_slider)
    substeps: IntProperty(name="Resolution", default=16, min=1, update=update_global_substeps)
    phase_offset: IntProperty(name="Phase Offset", default=0, update=update_driven_from_slider)
    gear_ratio: FloatProperty(name="Gear Ratio", default=1.0, update=update_driven_from_slider)

class LogicSubBatchSettings(bpy.types.PropertyGroup):
    operation: EnumProperty(items=[('SET', 'Set', ''), ('ADD', 'Inc', ''), ('MIRROR', 'Invert', ''), ('INTERP', 'Interp', '')], default='SET')
    is_progressive: BoolProperty(name="Progressive (Multiplier)", default=False)
    use_loc_x: BoolProperty(); val_loc_x: FloatProperty(); use_loc_y: BoolProperty(); val_loc_y: FloatProperty(); use_loc_z: BoolProperty(); val_loc_z: FloatProperty()
    use_rot_x: BoolProperty(); val_rot_x: FloatProperty(subtype='ANGLE'); use_rot_y: BoolProperty(); val_rot_y: FloatProperty(subtype='ANGLE'); use_rot_z: BoolProperty(); val_rot_z: FloatProperty(subtype='ANGLE')
    use_scl_x: BoolProperty(); val_scl_x: FloatProperty(default=1.0); use_scl_y: BoolProperty(); val_scl_y: FloatProperty(default=1.0); use_scl_z: BoolProperty(); val_scl_z: FloatProperty(default=1.0)
    snap_target_obj: PointerProperty(type=bpy.types.Object, name="Target Origin Object")
    
# -------------------------------------------------------
# AUTO-GENERATED DRIVERS SCRIPT BUILDER
# -------------------------------------------------------
def generate_driver_script(scene):
    text_name = "LogicSub_Driver_Core.py"
    txt = bpy.data.texts.get(text_name)
    if not txt: txt = bpy.data.texts.new(text_name)
        
    lines = [
        "import bpy", "import math", "",
        "# LOGIC SUBSTEPP'N - AUTO-GENERATED DRIVER CORE", "", "LS_DATA = {"
    ]
    
    for mapping in scene.logic_sub_mappings:
        combo_key = mapping.name
        lines.append(f"    '{combo_key}': {{")
        lines.append(f"        'target_max': {mapping.target_max},")
        lines.append(f"        'substeps': {max(1, mapping.substeps)},")
        lines.append(f"        'phase_offset': {mapping.phase_offset},")
        lines.append(f"        'gear_ratio': {mapping.gear_ratio},")
        lines.append(f"        'tags': {{")
        for tag in mapping.tags:
            if tag.type == 'SEG': lines.append(f"            '{tag.name}': {tag.target_step},")
            elif tag.type == 'GROUPIE':
                active_group = [i for i, gs in enumerate(tag.group_steps) if gs.is_active]
                lines.append(f"            '{tag.name}': {active_group},")
        lines.append(f"        }},")
        lines.append(f"        'data': [")
        
        for i, step in enumerate(mapping.steps):
            mc_data = {}
            for mc in step.mod_con_states:
                is_active_phase = True
                if mc.locked_groupie:
                    for tag in mapping.tags:
                        if tag.name == mc.locked_groupie and tag.type == 'GROUPIE':
                            if i >= len(tag.group_steps) or not tag.group_steps[i].is_active: is_active_phase = False
                            break
                mc_id = f"{mc.type}_{mc.name}"
                if mc.type == 'MOD': mc_data[mc_id + "_view"] = float(mc.show_viewport) if is_active_phase else 0.0
                else: mc_data[mc_id + "_inf"] = mc.influence if is_active_phase else 0.0
                for tp in mc.tracked_props:
                    val = tp.val_float if tp.prop_type == 'FLOAT' else (tp.val_int if tp.prop_type == 'INT' else float(tp.val_bool))
                    mc_data[mc_id + "_" + tp.prop_name] = val

            mc_str = str(mc_data)
            lines.append(f"            {{'loc_x': {step.loc_x}, 'loc_y': {step.loc_y}, 'loc_z': {step.loc_z}, "
                         f"'rot_x': {step.rot_x}, 'rot_y': {step.rot_y}, 'rot_z': {step.rot_z}, "
                         f"'scl_x': {step.scl_x}, 'scl_y': {step.scl_y}, 'scl_z': {step.scl_z}, "
                         f"'smoov': '{step.smoov_preset}', 'blend': {step.smoov_blend}, 'tension': {step.smoov_tension}, 'mc': {mc_str}}},")
        lines.append("        ]")
        lines.append("    },")
    
    lines.extend([
        "}", "",
        "def ls_eval(base_combo_name, prop_name, target_val):",
        "    if target_val >= 0:",
        "        combo_name = base_combo_name + '__POS'",
        "        t_val = target_val",
        "    else:",
        "        combo_name = base_combo_name + '__NEG'",
        "        t_val = abs(target_val)",
        "    if combo_name not in LS_DATA:",
        "        alt_combo = base_combo_name + ('__NEG' if target_val >= 0 else '__POS')",
        "        if alt_combo in LS_DATA:",
        "            block = LS_DATA[alt_combo]",
        "            if prop_name in block['data'][0]: return block['data'][0][prop_name]",
        "            return block['data'][0]['mc'].get(prop_name, 0.0)",
        "        return 0.0",
        "    block = LS_DATA[combo_name]",
        "    target_max = block['target_max']",
        "    substeps = block['substeps']",
        "    phase_offset = block.get('phase_offset', 0)",
        "    gear_ratio = block.get('gear_ratio', 1.0)",
        "    data = block['data']",
        "    if target_max == 0: return 0.0",
        "    step_size = target_max / substeps",
        "    t_val = t_val + (phase_offset * step_size)",
        "    t_val = max(0.0, min(t_val, target_max))",
        "    segment = int(t_val // step_size)",
        "    if segment >= substeps: segment = substeps - 1",
        "    t1 = segment * step_size",
        "    t2 = (segment + 1) * step_size",
        "    factor = (t_val - t1) / (t2 - t1) if t2 != t1 else 0.0",
        "    d1 = data[segment]",
        "    d2 = data[segment + 1] if segment + 1 < len(data) else data[segment]",
        "    preset = d1.get('smoov', 'LINEAR')",
        "    blend = d1.get('blend', 1.0)",
        "    t_lin = factor",
        "    if preset == 'BEZIER': factor = factor * factor * (3.0 - 2.0 * factor)",
        "    elif preset == 'VISCOUS': factor = factor * factor * factor",
        "    elif preset == 'CLAMPED': factor = 1.0 - (1.0 - factor) * (1.0 - factor)",
        "    elif preset == 'STEP': factor = 0.0",
        "    if preset not in ('LINEAR', 'STEP'): factor = t_lin * (1.0 - blend) + factor * blend",
        "    if prop_name in d1: v1, v2 = d1[prop_name], d2[prop_name]",
        "    else: v1 = d1['mc'].get(prop_name, 0.0); v2 = d2['mc'].get(prop_name, 0.0)",
        "    if prop_name.startswith('scl_'):",
        "        v1 = 1.0 + (v1 - 1.0) * gear_ratio",
        "        v2 = 1.0 + (v2 - 1.0) * gear_ratio",
        "    elif prop_name in ('loc_x', 'loc_y', 'loc_z', 'rot_x', 'rot_y', 'rot_z'):",
        "        v1 *= gear_ratio; v2 *= gear_ratio",
        "    return v1 + (v2 - v1) * factor",
        "", "import bpy", "bpy.app.driver_namespace['ls_eval'] = ls_eval",
    ])
    
    script_content = "\n".join(lines)
    txt.clear(); txt.write(script_content)
    
    ctx = bpy.context.copy(); ctx['edit_text'] = txt
    with bpy.context.temp_override(**ctx): bpy.ops.text.run_script()
        
    ext_path = get_substeppn_path("system/drivers/LogicSub_Driver_Core.py")
    if ext_path:
        try:
            with open(ext_path, "w", encoding="utf-8") as f: f.write(script_content)
        except: pass

def create_single_driver(target_obj, target_bone, drv_target, prop_data_path, array_index, base_combo_name, eval_key, channel_type):
    if array_index is not None: fcurve = drv_target.driver_add(prop_data_path, array_index)
    else: fcurve = drv_target.driver_add(prop_data_path)
    driver = fcurve.driver; driver.type = 'SCRIPTED'
    
    for var in driver.variables: driver.variables.remove(var)
    var = driver.variables.new(); var.name = "t_val"; var.type = 'TRANSFORMS'
    
    t = var.targets[0]; t.id = target_obj
    if target_bone: t.bone_target = target_bone.name
        
    if channel_type == 'LOC_X': t.transform_type = 'LOC_X'
    elif channel_type == 'LOC_Y': t.transform_type = 'LOC_Y'
    elif channel_type == 'LOC_Z': t.transform_type = 'LOC_Z'
    elif channel_type == 'ROT_X': t.transform_type = 'ROT_X'
    elif channel_type == 'ROT_Y': t.transform_type = 'ROT_Y'
    elif channel_type == 'ROT_Z': t.transform_type = 'ROT_Z'
    elif channel_type == 'SCL_X': t.transform_type = 'SCALE_X'
    elif channel_type == 'SCL_Y': t.transform_type = 'SCALE_Y'
    elif channel_type == 'SCL_Z': t.transform_type = 'SCALE_Z'
    
    t.transform_space = 'LOCAL_SPACE'
    driver.expression = f"ls_eval('{base_combo_name}', '{eval_key}', t_val)"

def sync_from_data_text(context, raw_text=None):
    scene = context.scene
    
    if raw_text is None:
        txt = bpy.data.texts.get("LogicSub_Data.txt")
        if not txt: return
        raw_text = txt.as_string()
        
    current_mapping = None
    current_step = None
    current_mc_state = None
    scene.logic_sub_is_syncing = True 
    
    try:
        for text in raw_text.splitlines():
            text = text.strip()
            if not text: continue
            
            if text.startswith("COMBINATION:"):
                parts = text.split("|")
                combo_name = parts[0].split("COMBINATION:")[1].strip().replace(" ➔ ", "__TO__").replace(" -> ", "__TO__")
                
                target_val = None
                if len(parts) > 1 and "TARGET:" in parts[1]:
                    try: target_val = float(parts[1].split("TARGET:")[1].strip())
                    except: pass

                current_mapping = None
                for m in scene.logic_sub_mappings:
                    if m.name == combo_name:
                        current_mapping = m
                        break
                if not current_mapping:
                    current_mapping = scene.logic_sub_mappings.add()
                    current_mapping.name = combo_name
                    
                if target_val is not None:
                    current_mapping.target_max = target_val
                    
                continue
            
            if current_mapping and "|" in text and not text.startswith("Step") and not text.startswith("->") and not text.startswith("=>"):
                parts = [p.strip() for p in text.split("|")]
                if len(parts) >= 11:
                    try:
                        step_idx = int(parts[0])
                        while len(current_mapping.steps) <= step_idx: current_mapping.steps.add()
                        if step_idx > 0: current_mapping.substeps = max(current_mapping.substeps, step_idx)
                            
                        step = current_mapping.steps[step_idx]
                        current_step = step
                        current_mc_state = None
                        
                        step.loc_x = float(parts[1]); step.loc_y = float(parts[2]); step.loc_z = float(parts[3])
                        step.rot_x = math.radians(float(parts[4]))
                        step.rot_y = math.radians(float(parts[5]))
                        step.rot_z = math.radians(float(parts[6]))
                        step.scl_x = float(parts[7]); step.scl_y = float(parts[8]); step.scl_z = float(parts[9])
                        step.status = 'EDITED'
                    except ValueError: pass 
            
            elif text.startswith("-> SMOOV:") and current_step:
                parts = text.replace("-> SMOOV:", "").split("|")
                for p in parts:
                    p = p.strip()
                    if p.startswith("BLEND:"): current_step.smoov_blend = float(p.split(":")[1].strip())
                    elif p.startswith("TENS:"): current_step.smoov_tension = float(p.split(":")[1].strip())
                    elif p.startswith("LABEL:"): current_step.step_label = p.replace("LABEL:", "").strip()
                    elif p in ['LINEAR', 'BEZIER', 'VISCOUS', 'CLAMPED', 'STEP']: current_step.smoov_preset = p

            elif text.startswith("->") and current_step and "SMOOV" not in text:
                parts = text.replace("->", "").split("|")
                if len(parts) == 2:
                    id_part = parts[0].strip()
                    val_part = parts[1].strip()
                    
                    if ":" in id_part:
                        mc_type, mc_name = id_part.split(":", 1)
                        mc_type, mc_name = mc_type.strip(), mc_name.strip()
                        
                        mc_state = None
                        for mc in current_step.mod_con_states:
                            if mc.name == mc_name and mc.type == mc_type:
                                mc_state = mc
                                break
                        if not mc_state:
                            mc_state = current_step.mod_con_states.add()
                            mc_state.name = mc_name; mc_state.type = mc_type
                        
                        if "Inf:" in val_part: mc_state.influence = float(val_part.split(":")[1].strip())
                        elif "View:" in val_part: mc_state.show_viewport = bool(int(val_part.split(":")[1].strip()))
                        
                        current_mc_state = mc_state
            
            elif text.startswith("=>") and current_mc_state:
                parts = text.replace("=>", "").split(":")
                if len(parts) == 3:
                    p_name, p_val, p_type = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    tp = None
                    for existing_tp in current_mc_state.tracked_props:
                        if existing_tp.prop_name == p_name:
                            tp = existing_tp
                            break
                    if not tp:
                        tp = current_mc_state.tracked_props.add()
                        tp.prop_name = p_name; tp.prop_type = p_type
                        
                    if p_type == 'FLOAT': tp.val_float = float(p_val)
                    elif p_type == 'INT': tp.val_int = int(p_val)
                    elif p_type == 'BOOL': tp.val_bool = bool(int(p_val))
                            
    finally:
        scene.logic_sub_is_syncing = False
    
    m = get_active_mapping(scene, create=False)
    if m: m.substeps = m.substeps 
        
    apply_logic_transform(context)
    update_data_text(scene)

# -------------------------------------------------------
# ASYNC PREVIEW TIMER (ELASTOMERIC PHYSICS)
# -------------------------------------------------------

def preview_step_callback():
    global _PHYSICS_VELOCITY
    try:
        context = bpy.context
        if not context or not context.scene: return 0.05
        s = context.scene
        if not getattr(s, "logic_sub_is_previewing", False): return None
        
        mapping = get_active_mapping(s, create=False)
        if not mapping:
            s.logic_sub_is_previewing = False; return None
            
        subs = max(1, mapping.substeps)
        target = getattr(s, "logic_sub_preview_target", -1)
        mode = s.logic_sub_preview_mode
        scope = s.logic_sub_preview_scope
        
        # 1. Playhead Advancement
        if scope == 'FULL':
            next_val = s.logic_sub_full_scrubber + s.logic_sub_preview_direction
            if mode == 'LOOP':
                if next_val > subs: next_val = -subs 
            elif mode == 'BOUNCE':
                if next_val >= subs:
                    next_val = subs; s.logic_sub_preview_direction = -1
                elif next_val <= -subs:
                    next_val = -subs; s.logic_sub_preview_direction = 1
            s.logic_sub_full_scrubber = next_val
            t_val = abs(next_val) + mapping.phase_offset
        else:
            if target != -1 and s.logic_sub_current_step >= target:
                s.logic_sub_is_previewing = False; s.logic_sub_preview_target = -1; return None
                
            next_step = s.logic_sub_current_step + (1 if mode == 'LOOP' and target == -1 else s.logic_sub_preview_direction)
            if mode == 'LOOP' and target == -1:
                if next_step > subs: next_step = 0
            elif mode == 'BOUNCE' and target == -1:
                if next_step >= subs:
                    next_step = subs; s.logic_sub_preview_direction = -1
                elif next_step <= 0:
                    next_step = 0; s.logic_sub_preview_direction = 1
            s.logic_sub_current_step = next_step
            t_val = next_step + mapping.phase_offset

        # 2. Elastomeric Physics
        for d_idx, deck in enumerate(s.logic_sub_decks):
            m_deck = get_active_mapping(s, d_idx, create=False)
            if not m_deck or len(m_deck.steps) == 0: continue
            
            d_obj, d_bone, is_bone = get_driven_target(s, d_idx)
            if not d_obj: continue
            tgt = d_bone if is_bone else d_obj
            key = f"{d_obj.name}_{d_bone.name if is_bone else ''}"
            
            if key not in _PHYSICS_VELOCITY: _PHYSICS_VELOCITY[key] = {'v_loc': Vector((0,0,0)), 'v_rot': Euler((0,0,0))}
            
            target_loc, target_rot, _ = evaluate_micro_step(m_deck, t_val)
            gr = m_deck.gear_ratio
            
            k = getattr(deck, "spring_tension", 0.15)
            d = getattr(deck, "drag", 0.7)
            m_weight = getattr(deck, "mass", 1.0)
            
            accel_loc = ((target_loc * gr) - tgt.location) * (k / m_weight)
            _PHYSICS_VELOCITY[key]['v_loc'] += accel_loc
            _PHYSICS_VELOCITY[key]['v_loc'] *= (1.0 - d)
            tgt.location += _PHYSICS_VELOCITY[key]['v_loc']
            
            if tgt.rotation_mode not in {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'}: tgt.rotation_mode = 'XYZ'
            target_rot_v = Vector((target_rot.x, target_rot.y, target_rot.z)) * gr
            curr_rot_v = Vector((tgt.rotation_euler.x, tgt.rotation_euler.y, tgt.rotation_euler.z))
            accel_rot = (target_rot_v - curr_rot_v) * (k / m_weight)
            
            v_rot_vec = Vector((_PHYSICS_VELOCITY[key]['v_rot'].x, _PHYSICS_VELOCITY[key]['v_rot'].y, _PHYSICS_VELOCITY[key]['v_rot'].z))
            v_rot_vec += accel_rot
            v_rot_vec *= (1.0 - d)
            _PHYSICS_VELOCITY[key]['v_rot'] = Euler((v_rot_vec.x, v_rot_vec.y, v_rot_vec.z))
            
            tgt.rotation_euler.x += _PHYSICS_VELOCITY[key]['v_rot'].x
            tgt.rotation_euler.y += _PHYSICS_VELOCITY[key]['v_rot'].y
            tgt.rotation_euler.z += _PHYSICS_VELOCITY[key]['v_rot'].z
            
        fps = s.logic_sub_preview_fps if s.logic_sub_preview_fps > 0 else 24
        for area in context.screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()
        return 1.0 / fps
    except Exception as e:
        print("Smoov'mnt Preview Error:", e)
        try: bpy.context.scene.logic_sub_is_previewing = False
        except: pass
        return None
# -------------------------------------------------------
# CORE SYSTEM OPERATORS
# -------------------------------------------------------

class LOGICSUB_OT_preview_play(bpy.types.Operator):
    bl_idname = "logicsub.preview_play"
    bl_label = "Toggle Preview Play"
    
    def execute(self, context):
        s = context.scene
        s.logic_sub_is_previewing = not s.logic_sub_is_previewing
        if s.logic_sub_is_previewing:
            s.logic_sub_preview_target = -1
            s.logic_sub_preview_direction = 1
            fps = s.logic_sub_preview_fps if s.logic_sub_preview_fps > 0 else 24
            bpy.app.timers.register(preview_step_callback, first_interval=1.0 / fps)
        return {'FINISHED'}

class LOGICSUB_OT_apply_no_touchy_math(bpy.types.Operator):
    bl_idname = "logicsub.apply_no_touchy_math"
    bl_label = "Enforce Kinematic Boundaries"
    bl_description = "Calculates margin mathematically from the mass density and applies rigid collision limits"
    deck_idx: IntProperty(default=-1)
    
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        
        deck = s.logic_sub_decks[d_idx]
        target_obj = deck.collider_target
        if not target_obj:
            self.report({'WARNING'}, "No Touchy Target selected!")
            return {'CANCELLED'}
            
        drv_obj, drv_bone, is_bone = get_driven_target(s, d_idx)
        if not drv_obj: return {'CANCELLED'}
        
        density = DENSITY_MAP.get(deck.physics_matter, 1000.0)
        margin_multiplier = 1000.0 / density
        final_margin = deck.collider_margin * margin_multiplier
        
        tgt = drv_bone if is_bone else drv_obj
        con_name = f"NoTouchy_{deck.physics_matter}"
        
        con = tgt.constraints.get(con_name)
        if not con:
            con = tgt.constraints.new('LIMIT_DISTANCE')
            con.name = con_name
            
        con.target = target_obj
        if target_obj.type == 'ARMATURE' and deck.collider_bone:
            con.subtarget = deck.collider_bone
            
        con.distance = final_margin
        con.limit_mode = 'LIMITDIST_OUTSIDE' # FIXED ENUM FOR BLENDER 4.0+
        
        m = get_active_mapping(s, d_idx, create=False)
        if m: bpy.ops.logicsub.set_driven_step(step=s.logic_sub_current_step, deck_override=d_idx)
        
        self.report({'INFO'}, f"Enforced {deck.physics_matter} ({final_margin:.4f}m) margin on {tgt.name}")
        return {'FINISHED'}

class LOGICSUB_OT_execute_backslide(bpy.types.Operator):
    bl_idname = "logicsub.execute_backslide"
    bl_label = "Execute Backslide Groove"
    def execute(self, context):
        s = context.scene
        source_dir = s.logic_sub_direction
        target_dir = 'NEG' if source_dir == 'POS' else 'POS'
        
        s.logic_sub_is_syncing = True
        affected_count = 0
        try:
            for d_idx in range(len(s.logic_sub_decks)):
                m_source = get_active_mapping(s, d_idx, create=False, force_dir=source_dir)
                if not m_source or len(m_source.steps) == 0: continue
                
                m_target = get_active_mapping(s, d_idx, create=True, force_dir=target_dir)
                if not m_target: continue 
                
                m_target.substeps = m_source.substeps
                target_len = max(1, m_target.substeps + 1)
                while len(m_target.steps) < target_len: m_target.steps.add()
                
                scale_factor = 1.0
                if m_source.target_max != 0.0: scale_factor = m_target.target_max / m_source.target_max
                s_base = m_source.steps[0]; t_base = m_target.steps[0]
                
                for i in range(target_len):
                    if i >= len(m_source.steps): continue
                    s_step = m_source.steps[i]; t_step = m_target.steps[i]
                    
                    if s.logic_sub_inv_loc_x: t_step.loc_x = t_base.loc_x - (s_step.loc_x - s_base.loc_x) * scale_factor
                    if s.logic_sub_inv_loc_y: t_step.loc_y = t_base.loc_y - (s_step.loc_y - s_base.loc_y) * scale_factor
                    if s.logic_sub_inv_loc_z: t_step.loc_z = t_base.loc_z - (s_step.loc_z - s_base.loc_z) * scale_factor
                    if s.logic_sub_inv_rot_x: t_step.rot_x = t_base.rot_x - (s_step.rot_x - s_base.rot_x) * scale_factor
                    if s.logic_sub_inv_rot_y: t_step.rot_y = t_base.rot_y - (s_step.rot_y - s_base.rot_y) * scale_factor
                    if s.logic_sub_inv_rot_z: t_step.rot_z = t_base.rot_z - (s_step.rot_z - s_base.rot_z) * scale_factor
                    if s.logic_sub_inv_scl_x: t_step.scl_x = t_base.scl_x - (s_step.scl_x - s_base.scl_x) * scale_factor
                    if s.logic_sub_inv_scl_y: t_step.scl_y = t_base.scl_y - (s_step.scl_y - s_base.scl_y) * scale_factor
                    if s.logic_sub_inv_scl_z: t_step.scl_z = t_base.scl_z - (s_step.scl_z - s_base.scl_z) * scale_factor
                    
                    t_step.status = 'EDITED'
                    affected_count += 1
        finally: s.logic_sub_is_syncing = False
            
        update_data_text(s); apply_logic_transform(context)
        ls_log(s, f"Backslide Groove: Inverted {affected_count} steps to {target_dir}.")
        s.logic_sub_direction = target_dir
        return {'FINISHED'}

class LOGICSUB_OT_copy_deck(bpy.types.Operator):
    bl_idname = "logicsub.copy_deck"
    bl_label = "Copy Deck To..."
    source_deck_idx: IntProperty()
    target_deck_idx: IntProperty()
    invert: BoolProperty(name="Invert Axes (* -1)", default=False)
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
        
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "target_deck_idx", text="Target Deck Index (0-based)")
        layout.prop(self, "invert")
        
    def execute(self, context):
        s = context.scene
        m_source = get_active_mapping(s, self.source_deck_idx, create=False)
        m_target = get_active_mapping(s, self.target_deck_idx, create=True)
        if not m_source or not m_target: return {'CANCELLED'}
        
        m_target.substeps = m_source.substeps
        while len(m_target.steps) < len(m_source.steps): m_target.steps.add()
        
        for i, s_step in enumerate(m_source.steps):
            t_step = m_target.steps[i]
            inv = -1.0 if self.invert else 1.0
            t_step.loc_x = s_step.loc_x * inv; t_step.loc_y = s_step.loc_y * inv; t_step.loc_z = s_step.loc_z * inv
            t_step.rot_x = s_step.rot_x * inv; t_step.rot_y = s_step.rot_y * inv; t_step.rot_z = s_step.rot_z * inv
            t_step.scl_x = s_step.scl_x; t_step.scl_y = s_step.scl_y; t_step.scl_z = s_step.scl_z
            t_step.status = 'EDITED'
        return {'FINISHED'}

class LOGICSUB_OT_tween_all_steps(bpy.types.Operator):
    bl_idname = "logicsub.tween_all_steps"
    bl_label = "Magic Tween (Start to End)"
    bl_description = "Interpolates all steps between Step 0 and the Last Step"
    deck_idx: IntProperty()
    def execute(self, context):
        s = context.scene
        m = get_active_mapping(s, self.deck_idx, create=False)
        if not m or len(m.steps) < 3: return {'CANCELLED'}
        
        s1 = m.steps[0]
        s2 = m.steps[-1]
        total = len(m.steps) - 1
        
        for i in range(1, total):
            f = i / total
            step = m.steps[i]
            step.loc_x = s1.loc_x + (s2.loc_x - s1.loc_x) * f
            step.loc_y = s1.loc_y + (s2.loc_y - s1.loc_y) * f
            step.loc_z = s1.loc_z + (s2.loc_z - s1.loc_z) * f
            step.rot_x = s1.rot_x + (s2.rot_x - s1.rot_x) * f
            step.rot_y = s1.rot_y + (s2.rot_y - s1.rot_y) * f
            step.rot_z = s1.rot_z + (s2.rot_z - s1.rot_z) * f
            step.scl_x = s1.scl_x + (s2.scl_x - s1.scl_x) * f
            step.scl_y = s1.scl_y + (s2.scl_y - s1.scl_y) * f
            step.scl_z = s1.scl_z + (s2.scl_z - s1.scl_z) * f
            step.status = 'EDITED'
        update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_generate_recoil(bpy.types.Operator):
    bl_idname = "logicsub.generate_recoil"
    bl_label = "Add Recoil (5% Overshoot)"
    step_idx: IntProperty()
    deck_idx: IntProperty(default=-1)
    
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        m = get_active_mapping(s, d_idx, create=True)
        if not m or self.step_idx == 0 or self.step_idx >= len(m.steps): return {'CANCELLED'}
        
        prev = m.steps[self.step_idx - 1]
        curr = m.steps[self.step_idx]
        
        m.steps.add()
        for i in range(len(m.steps)-1, self.step_idx, -1):
            s_to = m.steps[i]; s_from = m.steps[i-1]
            s_to.loc_x = s_from.loc_x; s_to.loc_y = s_from.loc_y; s_to.loc_z = s_from.loc_z
            s_to.rot_x = s_from.rot_x; s_to.rot_y = s_from.rot_y; s_to.rot_z = s_from.rot_z
            s_to.scl_x = s_from.scl_x; s_to.scl_y = s_from.scl_y; s_to.scl_z = s_from.scl_z
            s_to.smoov_preset = s_from.smoov_preset
            s_to.smoov_blend = s_from.smoov_blend
            s_to.smoov_tension = s_from.smoov_tension
            s_to.step_label = s_from.step_label
            
        overshoot = m.steps[self.step_idx]
        overshoot.step_label = "Impact (Overshoot)"
        overshoot.smoov_preset = 'CLAMPED'
        
        overshoot.loc_x = curr.loc_x + ((curr.loc_x - prev.loc_x) * 0.05)
        overshoot.loc_y = curr.loc_y + ((curr.loc_y - prev.loc_y) * 0.05)
        overshoot.loc_z = curr.loc_z + ((curr.loc_z - prev.loc_z) * 0.05)
        overshoot.rot_x = curr.rot_x + ((curr.rot_x - prev.rot_x) * 0.05)
        overshoot.rot_y = curr.rot_y + ((curr.rot_y - prev.rot_y) * 0.05)
        overshoot.rot_z = curr.rot_z + ((curr.rot_z - prev.rot_z) * 0.05)
        
        if self.step_idx + 1 < len(m.steps):
            settle = m.steps[self.step_idx + 1]
            settle.step_label = "Settle"
            settle.smoov_preset = 'VISCOUS'
        
        update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_copy_error(bpy.types.Operator):
    bl_idname = "logicsub.copy_error"
    bl_label = "Open Crash Log"
    def execute(self, context):
        global _LS_CRASH_TRACE
        txt_name = "LogicSub_Crash_Report.txt"
        txt = bpy.data.texts.get(txt_name)
        if not txt: txt = bpy.data.texts.new(txt_name)
        txt.clear()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        txt.write(f"=== LOGIC SUBSTEPP'N CRASH REPORT ===\n[{timestamp}]\n\nERROR TRACEBACK:\n----------------------------------------\n")
        txt.write(_LS_CRASH_TRACE if _LS_CRASH_TRACE else "No recent crash data captured.")
        txt.write("\n" + "-" * 40 + "\n")
        found = False
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR': area.spaces.active.text = txt; found = True; break
        if not found:
            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
            context.screen.areas[-1].type = 'TEXT_EDITOR'; context.screen.areas[-1].spaces.active.text = txt
        return {'FINISHED'}

class LOGICSUB_OT_add_deck(bpy.types.Operator):
    bl_idname = "logicsub.add_deck"
    bl_label = "Add Deck"
    def execute(self, context):
        context.scene.logic_sub_decks.add()
        context.scene.logic_sub_active_deck_idx = len(context.scene.logic_sub_decks) - 1
        return {'FINISHED'}

class LOGICSUB_OT_remove_deck(bpy.types.Operator):
    bl_idname = "logicsub.remove_deck"
    bl_label = "Remove Deck"
    def execute(self, context):
        s = context.scene
        if len(s.logic_sub_decks) > 0:
            s.logic_sub_decks.remove(s.logic_sub_active_deck_idx)
            s.logic_sub_active_deck_idx = max(0, min(s.logic_sub_active_deck_idx, len(s.logic_sub_decks) - 1))
        return {'FINISHED'}

class LOGICSUB_OT_move_deck(bpy.types.Operator):
    bl_idname = "logicsub.move_deck"
    bl_label = "Move Deck"
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])

    def execute(self, context):
        s = context.scene
        idx = s.logic_sub_active_deck_idx
        list_length = len(s.logic_sub_decks)
        if list_length < 2: return {'CANCELLED'}

        new_idx = idx - 1 if self.direction == 'UP' else idx + 1
        if 0 <= new_idx < list_length:
            s.logic_sub_decks.move(idx, new_idx)
            s.logic_sub_active_deck_idx = new_idx
        return {'FINISHED'}

class LOGICSUB_OT_init_mapping(bpy.types.Operator):
    bl_idname = "logicsub.init_mapping"
    bl_label = "Initialize Deck Mapping"
    def execute(self, context):
        m = get_active_mapping(context.scene, create=True)
        if m and len(m.steps) == 0: m.steps.add()
        return {'FINISHED'}

class LOGICSUB_OT_toggle_nested_decks(bpy.types.Operator):
    bl_idname = "logicsub.toggle_nested_decks"
    bl_label = "Global Deck Unlock"
    step_idx: IntProperty()
    def execute(self, context):
        s = context.scene
        active_idx = s.logic_sub_active_deck_idx
        target_state = True
        for i in range(len(s.logic_sub_decks)):
            if i == active_idx: continue
            m = get_active_mapping(s, i, create=False)
            if m and self.step_idx < len(m.steps):
                target_state = not m.steps[self.step_idx].show_nested_deck
                break
        for i in range(len(s.logic_sub_decks)):
            if i == active_idx: continue
            m = get_active_mapping(s, i, create=False)
            if m and self.step_idx < len(m.steps): m.steps[self.step_idx].show_nested_deck = target_state
        return {'FINISHED'}

class LOGICSUB_OT_step_tool(bpy.types.Operator):
    bl_idname = "logicsub.step_tool"
    bl_label = "Step Transform Tool"
    action: StringProperty()
    step_idx: IntProperty()
    deck_idx: IntProperty()
    
    def execute(self, context):
        s = context.scene
        orig_mode = context.mode
        
        if self.action in ['ORIGIN_TO_CURSOR', 'ORIGIN_TO_GEOM']:
            if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        
        drv_obj, drv_bone, is_bone = get_driven_target(s, self.deck_idx)
        
        # FIXED: Proper context override to prevent select_all.poll() failures
        if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        for obj in context.view_layer.objects: obj.select_set(False)
        
        if drv_obj:
            drv_obj.select_set(True)
            context.view_layer.objects.active = drv_obj
            
        if is_bone and drv_obj and self.action in ['CURSOR_TO_SEL', 'SEL_TO_CURSOR']:
            bpy.ops.object.mode_set(mode='POSE')
            for b in drv_obj.data.bones: b.select = False
            drv_obj.data.bones[drv_bone.name].select = True
            drv_obj.data.bones.active = drv_obj.data.bones[drv_bone.name]
        
        override = context.copy()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                override['area'] = area
                override['region'] = area.regions[0]
                break
                
        with context.temp_override(**override):
            if self.action == 'CURSOR_TO_SEL':
                bpy.ops.view3d.snap_cursor_to_selected()
            elif self.action == 'SEL_TO_CURSOR':
                bpy.ops.view3d.snap_selected_to_cursor(use_offset=False)
                bpy.ops.logicsub.set_driven_step(step=self.step_idx, deck_override=self.deck_idx)
            elif self.action == 'CURSOR_TO_WORLD':
                context.scene.cursor.location = (0,0,0)
            elif self.action == 'ORIGIN_TO_CURSOR':
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
            elif self.action == 'ORIGIN_TO_GEOM':
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
            
        if context.mode != orig_mode:
            try: bpy.ops.object.mode_set(mode=orig_mode)
            except: pass
        return {'FINISHED'}

class LOGICSUB_OT_wand_snap(bpy.types.Operator):
    bl_idname = "logicsub.wand_snap"
    bl_label = "Magic Wand Snap"
    step_idx: IntProperty()
    deck_idx: IntProperty()
    def execute(self, context):
        s = context.scene
        bpy.ops.logicsub.step_tool(action='SEL_TO_CURSOR', step_idx=self.step_idx, deck_idx=self.deck_idx)
        m = get_active_mapping(s, self.deck_idx)
        if m and self.step_idx < len(m.steps) - 1:
            s.logic_sub_current_step = self.step_idx + 1
            apply_logic_transform(context)
            context.view_layer.update()
        return {'FINISHED'}

class LOGICSUB_OT_isolate_target(bpy.types.Operator):
    bl_idname = "logicsub.isolate_target"
    bl_label = "Lock & Isolate Viewport"
    deck_idx: IntProperty()
    def execute(self, context):
        s = context.scene
        drv_obj, _, _ = get_driven_target(s, self.deck_idx)
        if not drv_obj: return {'CANCELLED'}
        
        is_isolated = True
        for obj in context.view_layer.objects:
            if obj != drv_obj and not obj.hide_get():
                is_isolated = False; break
                
        if is_isolated:
            for obj in context.view_layer.objects: obj.hide_set(False)
        else:
            for obj in context.view_layer.objects:
                if obj != drv_obj: obj.hide_set(True)
                else: obj.hide_set(False)
        return {'FINISHED'}

class LOGICSUB_OT_reset_step_transforms(bpy.types.Operator):
    bl_idname = "logicsub.reset_step_transforms"
    bl_label = "Reset Transforms to Zero"
    step_idx: IntProperty()
    deck_idx: IntProperty()
    def execute(self, context):
        s = context.scene
        m = get_active_mapping(s, self.deck_idx, create=True)
        if m and self.step_idx < len(m.steps):
            step = m.steps[self.step_idx]
            s.logic_sub_is_syncing = True
            step.loc_x = step.loc_y = step.loc_z = 0.0
            step.rot_x = step.rot_y = step.rot_z = 0.0
            step.scl_x = step.scl_y = step.scl_z = 1.0
            step.status = 'EDITED'
            s.logic_sub_is_syncing = False
            update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_snapshot_step(bpy.types.Operator):
    bl_idname = "logicsub.snapshot_step"
    bl_label = "Snapshot Tools"
    action: StringProperty()
    step_idx: IntProperty()
    deck_idx: IntProperty()
    def execute(self, context):
        s = context.scene
        m = get_active_mapping(s, self.deck_idx, create=True)
        if not m or self.step_idx >= len(m.steps): return {'CANCELLED'}
        step = m.steps[self.step_idx]
        
        if self.action == 'SAVE':
            step.snap_loc_x = step.loc_x; step.snap_loc_y = step.loc_y; step.snap_loc_z = step.loc_z
            step.snap_rot_x = step.rot_x; step.snap_rot_y = step.rot_y; step.snap_rot_z = step.rot_z
            step.snap_scl_x = step.scl_x; step.snap_scl_y = step.scl_y; step.snap_scl_z = step.scl_z
            step.has_snapshot = True
        elif self.action == 'RESTORE':
            if not step.has_snapshot: return {'CANCELLED'}
            s.logic_sub_is_syncing = True
            step.loc_x = step.snap_loc_x; step.loc_y = step.snap_loc_y; step.loc_z = step.snap_loc_z
            step.rot_x = step.snap_rot_x; step.rot_y = step.snap_rot_y; step.rot_z = step.snap_rot_z
            step.scl_x = step.snap_scl_x; step.scl_y = step.snap_scl_y; step.scl_z = step.snap_scl_z
            step.status = 'EDITED'
            s.logic_sub_is_syncing = False
            update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_bridge_to_next(bpy.types.Operator):
    bl_idname = "logicsub.bridge_to_next"
    bl_label = "Bridge/Interpolate to Next"
    step_idx: IntProperty()
    deck_idx: IntProperty()
    def execute(self, context):
        s = context.scene
        m = get_active_mapping(s, self.deck_idx, create=True)
        if not m or self.step_idx >= len(m.steps) - 1: return {'CANCELLED'}
        
        s1 = m.steps[self.step_idx]; s2 = m.steps[self.step_idx + 1]
        s.logic_sub_is_syncing = True
        if self.step_idx + 2 < len(m.steps):
            s3 = m.steps[self.step_idx + 2]
            s2.loc_x = (s1.loc_x + s3.loc_x) / 2.0; s2.loc_y = (s1.loc_y + s3.loc_y) / 2.0; s2.loc_z = (s1.loc_z + s3.loc_z) / 2.0
            s2.rot_x = (s1.rot_x + s3.rot_x) / 2.0; s2.rot_y = (s1.rot_y + s3.rot_y) / 2.0; s2.rot_z = (s1.rot_z + s3.rot_z) / 2.0
            s2.scl_x = (s1.scl_x + s3.scl_x) / 2.0; s2.scl_y = (s1.scl_y + s3.scl_y) / 2.0; s2.scl_z = (s1.scl_z + s3.scl_z) / 2.0
        else:
            s2.loc_x = s1.loc_x; s2.loc_y = s1.loc_y; s2.loc_z = s1.loc_z
            s2.rot_x = s1.rot_x; s2.rot_y = s1.rot_y; s2.rot_z = s1.rot_z
            s2.scl_x = s1.scl_x; s2.scl_y = s1.scl_y; s2.scl_z = s1.scl_z
            
        s2.status = 'EDITED'
        s.logic_sub_is_syncing = False
        update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_exec(bpy.types.Operator):
    bl_idname = "logicsub.exec"
    bl_label = "Apply Substep"
    mode: EnumProperty(items=[('NAV', "Nav", ""), ('JUMP', "Jump", ""), ('UPDATE', "Update", "")])
    delta: IntProperty(default=0)
    step: IntProperty(default=0)
    def execute(self, context):
        s = context.scene
        mapping = get_active_mapping(s, create=True)
        if not mapping: return {'CANCELLED'}
        if self.mode == 'NAV': s.logic_sub_current_step = max(0, min(s.logic_sub_current_step + self.delta, mapping.substeps))
        elif self.mode == 'JUMP': s.logic_sub_current_step = self.step
        elif self.mode == 'UPDATE': s.logic_sub_current_step = max(0, min(s.logic_sub_current_step, mapping.substeps))
        return {'FINISHED'}

class LOGICSUB_OT_exec_full(bpy.types.Operator):
    bl_idname = "logicsub.exec_full"
    bl_label = "Apply Full Substep"
    val: IntProperty(default=0)
    def execute(self, context):
        context.scene.logic_sub_full_scrubber = self.val
        return {'FINISHED'}

class LOGICSUB_OT_play_to_step(bpy.types.Operator):
    bl_idname = "logicsub.play_to_step"
    bl_label = "Play to Step"
    target_step: IntProperty(default=0)
    def execute(self, context):
        s = context.scene
        mapping = get_active_mapping(s, create=False)
        if not mapping: return {'CANCELLED'}
        s.logic_sub_current_step = 0
        s.logic_sub_preview_target = self.target_step
        s.logic_sub_preview_direction = 1
        s.logic_sub_is_previewing = True
        s.logic_sub_preview_scope = 'SINGLE'
        apply_logic_transform(context); context.view_layer.update()
        fps = s.logic_sub_preview_fps if s.logic_sub_preview_fps > 0 else 24
        bpy.app.timers.register(preview_step_callback, first_interval=1.0 / fps)
        return {'FINISHED'}

class LOGICSUB_OT_set_driven_step(bpy.types.Operator):
    bl_idname = "logicsub.set_driven_step"
    bl_label = "Capture Viewport State"
    step: IntProperty(default=0)
    deck_override: IntProperty(default=-1)
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_override == -1 else self.deck_override
        mapping = get_active_mapping(s, d_idx, create=True)
        if not mapping: return {'CANCELLED'}
        steps = mapping.steps
        while len(steps) < max(1, mapping.substeps + 1): steps.add()
        drv_obj, drv_bone, drv_is_bone = get_driven_target(s, d_idx)
        if not drv_obj: return {'CANCELLED'}

        tgt = drv_bone if drv_is_bone else drv_obj
        vals = steps[self.step]
        s.logic_sub_is_capturing = True
        gr = mapping.gear_ratio if mapping.gear_ratio != 0 else 1.0

        vals.loc_x = tgt.location[0] / gr; vals.loc_y = tgt.location[1] / gr; vals.loc_z = tgt.location[2] / gr
        if tgt.rotation_mode not in {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'}: tgt.rotation_mode = 'XYZ'
        vals.rot_x = tgt.rotation_euler[0] / gr; vals.rot_y = tgt.rotation_euler[1] / gr; vals.rot_z = tgt.rotation_euler[2] / gr
        vals.scl_x = 1.0 + (tgt.scale[0] - 1.0) / gr; vals.scl_y = 1.0 + (tgt.scale[1] - 1.0) / gr; vals.scl_z = 1.0 + (tgt.scale[2] - 1.0) / gr

        existing_mcs = {f"{mc.type}_{mc.name}": mc for mc in vals.mod_con_states}
        live_mcs = []
        if not drv_is_bone:
            for mod in drv_obj.modifiers: live_mcs.append(('MOD', mod))
            for con in drv_obj.constraints: live_mcs.append(('CON', con))
        else:
            for con in drv_bone.constraints: live_mcs.append(('BCON', con))
            
        live_keys = [f"{t}_{m.name}" for t, m in live_mcs]
        for i in range(len(vals.mod_con_states) - 1, -1, -1):
            if f"{vals.mod_con_states[i].type}_{vals.mod_con_states[i].name}" not in live_keys:
                vals.mod_con_states.remove(i)

        for mc_type, live_mc in live_mcs:
            key = f"{mc_type}_{live_mc.name}"
            mc = existing_mcs[key] if key in existing_mcs else vals.mod_con_states.add()
            mc.name = live_mc.name; mc.type = mc_type
            if mc_type == 'MOD': mc.show_viewport = live_mc.show_viewport
            else: mc.influence = live_mc.influence
            
            for tp in mc.tracked_props:
                if hasattr(live_mc, tp.prop_name):
                    val = getattr(live_mc, tp.prop_name)
                    if tp.prop_type == 'FLOAT': tp.val_float = float(val)
                    elif tp.prop_type == 'INT': tp.val_int = int(val)
                    elif tp.prop_type == 'BOOL': tp.val_bool = bool(val)

        vals.status = 'SET'
        s.logic_sub_is_capturing = False
        update_data_text(s)
        return {'FINISHED'}
        
class LOGICSUB_OT_flip_step(bpy.types.Operator):
    bl_idname = "logicsub.flip_step"
    bl_label = "Flip Step"
    step_idx: IntProperty()
    deck_idx: IntProperty(default=-1)
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        m = get_active_mapping(s, d_idx, create=True)
        if not m or self.step_idx >= len(m.steps): return {'CANCELLED'}
        step = m.steps[self.step_idx]; s.logic_sub_is_syncing = True
        step.loc_x *= -1; step.loc_y *= -1; step.loc_z *= -1
        step.rot_x *= -1; step.rot_y *= -1; step.rot_z *= -1
        step.status = 'EDITED'
        s.logic_sub_is_syncing = False
        update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_shuffle_channels(bpy.types.Operator):
    bl_idname = "logicsub.shuffle_channels"
    bl_label = "Shuffle Step Channels"
    step_idx: IntProperty(); deck_idx: IntProperty(default=-1); mode: StringProperty() 
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        mapping = get_active_mapping(s, d_idx, create=True)
        if not mapping or self.step_idx >= len(mapping.steps): return {'CANCELLED'}
        step = mapping.steps[self.step_idx]; s.logic_sub_is_syncing = True
        try:
            if self.mode == 'AXIS_FWD': 
                step.loc_x, step.loc_y, step.loc_z = step.loc_z, step.loc_x, step.loc_y
                step.rot_x, step.rot_y, step.rot_z = step.rot_z, step.rot_x, step.rot_y
                step.scl_x, step.scl_y, step.scl_z = step.scl_z, step.scl_x, step.scl_y
            elif self.mode == 'AXIS_BWD': 
                step.loc_x, step.loc_y, step.loc_z = step.loc_y, step.loc_z, step.loc_x
                step.rot_x, step.rot_y, step.rot_z = step.rot_y, step.rot_z, step.rot_x
                step.scl_x, step.scl_y, step.scl_z = step.scl_y, step.scl_z, step.scl_x
            elif self.mode == 'TYPE_FWD': 
                lx, ly, lz = step.loc_x, step.loc_y, step.loc_z
                rx, ry, rz = step.rot_x, step.rot_y, step.rot_z
                sx, sy, sz = step.scl_x, step.scl_y, step.scl_z
                step.loc_x, step.loc_y, step.loc_z = sx, sy, sz
                step.rot_x, step.rot_y, step.rot_z = math.radians(lx), math.radians(ly), math.radians(lz)
                step.scl_x, step.scl_y, step.scl_z = math.degrees(rx), math.degrees(ry), math.degrees(rz)
            elif self.mode == 'TYPE_BWD': 
                lx, ly, lz = step.loc_x, step.loc_y, step.loc_z
                rx, ry, rz = step.rot_x, step.rot_y, step.rot_z
                sx, sy, sz = step.scl_x, step.scl_y, step.scl_z
                step.loc_x, step.loc_y, step.loc_z = math.degrees(rx), math.degrees(ry), math.degrees(rz)
                step.rot_x, step.rot_y, step.rot_z = math.radians(sx), math.radians(sy), math.radians(sz)
                step.scl_x, step.scl_y, step.scl_z = lx, ly, lz
            elif self.mode == 'TYPE_SMART':
                lx, ly, lz = step.loc_x, step.loc_y, step.loc_z
                rx, ry, rz = step.rot_x, step.rot_y, step.rot_z
                sx, sy, sz = step.scl_x, step.scl_y, step.scl_z
                step.loc_x = math.degrees(rx) * 0.0174533; step.loc_y = math.degrees(ry) * 0.0174533; step.loc_z = math.degrees(rz) * 0.0174533
                step.rot_x = math.radians(lx); step.rot_y = math.radians(ly); step.rot_z = math.radians(lz)
                step.scl_x = 1.0 + rx; step.scl_y = 1.0 + ry; step.scl_z = 1.0 + rz
            step.status = 'EDITED'
        finally: s.logic_sub_is_syncing = False
        update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_copy_clipboard(bpy.types.Operator):
    bl_idname = "logicsub.copy_clipboard"
    bl_label = "Copy Step to Clipboard"
    idx: IntProperty()
    deck_idx: IntProperty(default=-1)
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        m = get_active_mapping(s, d_idx, create=True)
        if not m or self.idx >= len(m.steps): return {'CANCELLED'}
        source = m.steps[self.idx]; cb = s.logic_sub_clipboard
        cb.loc_x = source.loc_x; cb.loc_y = source.loc_y; cb.loc_z = source.loc_z
        cb.rot_x = source.rot_x; cb.rot_y = source.rot_y; cb.rot_z = source.rot_z
        cb.scl_x = source.scl_x; cb.scl_y = source.scl_y; cb.scl_z = source.scl_z; cb.has_data = True
        return {'FINISHED'}

class LOGICSUB_OT_paste_clipboard(bpy.types.Operator):
    bl_idname = "logicsub.paste_clipboard"
    bl_label = "Paste from Clipboard"
    idx: IntProperty()
    deck_idx: IntProperty(default=-1)
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        m = get_active_mapping(s, d_idx, create=True)
        if not m or self.idx >= len(m.steps): return {'CANCELLED'}
        target = m.steps[self.idx]; cb = s.logic_sub_clipboard
        if not cb.has_data: return {'CANCELLED'}
        s.logic_sub_is_syncing = True
        target.loc_x = cb.loc_x; target.loc_y = cb.loc_y; target.loc_z = cb.loc_z
        target.rot_x = cb.rot_x; target.rot_y = cb.rot_z; target.rot_z = cb.rot_z
        target.scl_x = cb.scl_x; target.scl_y = cb.scl_y; target.scl_z = cb.scl_z
        target.status = 'EDITED'
        s.logic_sub_is_syncing = False
        update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_copy_step(bpy.types.Operator):
    bl_idname = "logicsub.copy_step"
    bl_label = "Copy Step"
    source_idx: IntProperty(); target_idx: IntProperty(); deck_idx: IntProperty(default=-1)
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        m = get_active_mapping(s, d_idx, create=True)
        if not m or self.source_idx >= len(m.steps) or self.target_idx >= len(m.steps): return {'CANCELLED'}
        s_step, t_step = m.steps[self.source_idx], m.steps[self.target_idx]
        context.scene.logic_sub_is_syncing = True
        t_step.loc_x = s_step.loc_x; t_step.loc_y = s_step.loc_y; t_step.loc_z = s_step.loc_z
        t_step.rot_x = s_step.rot_x; t_step.rot_y = s_step.rot_y; t_step.rot_z = s_step.rot_z
        t_step.scl_x = s_step.scl_x; t_step.scl_y = s_step.scl_y; t_step.scl_z = s_step.scl_z
        t_step.status = 'EDITED'
        context.scene.logic_sub_is_syncing = False
        update_data_text(context.scene); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_quick_math_propagate(bpy.types.Operator):
    bl_idname = "logicsub.quick_math_propagate"
    bl_label = "Propagate Quick Math"
    step_idx: IntProperty()
    direction: StringProperty()
    deck_idx: IntProperty(default=-1)
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        m = get_active_mapping(s, d_idx, create=True)
        if not m or self.step_idx >= len(m.steps): return {'CANCELLED'}
        
        base = m.steps[self.step_idx]
        op, v = base.qm_op, base.qm_val

        def apply_qm(prev, op, v, is_rot):
            v_eff = math.radians(v) if is_rot and op in ('ADD', 'SUB') else v
            if op == 'ADD': return prev + v_eff
            elif op == 'SUB': return prev - v_eff
            elif op == 'MULT': return prev * v
            elif op == 'DIV': return prev / v if v != 0.0 else prev
            elif op == 'INV': return prev * -1.0
            elif op == 'DEC': return prev * 0.1
            return prev

        s.logic_sub_is_syncing = True
        try:
            rng = range(self.step_idx + 1, len(m.steps)) if self.direction == 'TO_END' else range(self.step_idx - 1, -1, -1)
            for i in rng:
                prev = m.steps[i - 1 if self.direction == 'TO_END' else i + 1]
                curr = m.steps[i]
                if base.qm_loc_x: curr.loc_x = apply_qm(prev.loc_x, op, v, False)
                if base.qm_loc_y: curr.loc_y = apply_qm(prev.loc_y, op, v, False)
                if base.qm_loc_z: curr.loc_z = apply_qm(prev.loc_z, op, v, False)
                if base.qm_rot_x: curr.rot_x = apply_qm(prev.rot_x, op, v, True)
                if base.qm_rot_y: curr.rot_y = apply_qm(prev.rot_y, op, v, True)
                if base.qm_rot_z: curr.rot_z = apply_qm(prev.rot_z, op, v, True)
                if base.qm_scl_x: curr.scl_x = apply_qm(prev.scl_x, op, v, False)
                if base.qm_scl_y: curr.scl_y = apply_qm(prev.scl_y, op, v, False)
                if base.qm_scl_z: curr.scl_z = apply_qm(prev.scl_z, op, v, False)
                curr.status = 'EDITED'
        finally: s.logic_sub_is_syncing = False
        update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_add_tracked_prop(bpy.types.Operator):
    bl_idname = "logicsub.add_tracked_prop"
    bl_label = "Add Tracked Property"
    step_idx: IntProperty(); mc_name: StringProperty(); mc_type: StringProperty(); deck_idx: IntProperty(default=-1)
    def execute(self, context):
        scene = context.scene
        d_idx = scene.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        mapping = get_active_mapping(scene, d_idx, create=True)
        if not mapping or self.step_idx >= len(mapping.steps): return {'CANCELLED'}
        step = mapping.steps[self.step_idx]
        mc_state = None
        for mc in step.mod_con_states:
            if mc.name == self.mc_name and mc.type == self.mc_type: mc_state = mc; break
        if not mc_state or mc_state.prop_selector == 'NONE': return {'CANCELLED'}
        prop_name = mc_state.prop_selector
        for tp in mc_state.tracked_props:
            if tp.prop_name == prop_name: return {'CANCELLED'}
        drv_obj, drv_bone, drv_is_bone = get_driven_target(scene, d_idx)
        live_mc = None
        if self.mc_type == 'MOD' and not drv_is_bone: live_mc = drv_obj.modifiers.get(self.mc_name)
        elif self.mc_type == 'CON' and not drv_is_bone: live_mc = drv_obj.constraints.get(self.mc_name)
        elif self.mc_type == 'BCON' and drv_is_bone: live_mc = drv_bone.constraints.get(self.mc_name)
        
        if not live_mc or not hasattr(live_mc, prop_name): return {'CANCELLED'}
        val = getattr(live_mc, prop_name)
        prop_type = 'FLOAT'
        if isinstance(val, bool): prop_type = 'BOOL'
        elif isinstance(val, int): prop_type = 'INT'
        
        tp = mc_state.tracked_props.add()
        tp.prop_name = prop_name; tp.prop_type = prop_type
        scene.logic_sub_is_capturing = True
        if prop_type == 'FLOAT': tp.val_float = float(val)
        elif prop_type == 'INT': tp.val_int = int(val)
        elif prop_type == 'BOOL': tp.val_bool = bool(val)
        scene.logic_sub_is_capturing = False
        update_data_text(scene)
        return {'FINISHED'}

class LOGICSUB_OT_remove_tracked_prop(bpy.types.Operator):
    bl_idname = "logicsub.remove_tracked_prop"
    bl_label = "Remove Tracked Property"
    step_idx: IntProperty(); mc_name: StringProperty(); mc_type: StringProperty(); prop_name: StringProperty(); deck_idx: IntProperty(default=-1)
    def execute(self, context):
        d_idx = context.scene.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        mapping = get_active_mapping(context.scene, d_idx, create=True)
        if not mapping or self.step_idx >= len(mapping.steps): return {'CANCELLED'}
        step = mapping.steps[self.step_idx]
        for mc in step.mod_con_states:
            if mc.name == self.mc_name and mc.type == self.mc_type:
                for i, tp in enumerate(mc.tracked_props):
                    if tp.prop_name == self.prop_name:
                        mc.tracked_props.remove(i); update_data_text(context.scene); return {'FINISHED'}
        return {'CANCELLED'}

class LOGICSUB_OT_batch_select_all(bpy.types.Operator):
    bl_idname = "logicsub.batch_select_all"
    bl_label = "Batch Select"
    state: BoolProperty(default=True)
    def execute(self, context):
        mapping = get_active_mapping(context.scene, create=True)
        if mapping:
            for step in mapping.steps: step.is_selected_for_batch = self.state
        return {'FINISHED'}

class LOGICSUB_OT_batch_apply(bpy.types.Operator):
    bl_idname = "logicsub.batch_apply"
    bl_label = "Apply Batch Values"
    def execute(self, context):
        s = context.scene
        mapping = get_active_mapping(s, create=True)
        b = s.logic_sub_batch
        if not mapping: return {'CANCELLED'}

        s.logic_sub_is_syncing = True
        try:
            sel = [i for i, step in enumerate(mapping.steps) if step.is_selected_for_batch]
            if not sel: return {'CANCELLED'}
            
            if b.operation == 'INTERP' and len(sel) > 2:
                s1, s2 = mapping.steps[sel[0]], mapping.steps[sel[-1]]
                for i in sel[1:-1]:
                    f = (i - sel[0]) / (sel[-1] - sel[0])
                    if i >= len(mapping.steps): continue
                    step = mapping.steps[i]
                    if b.use_loc_x: step.loc_x = s1.loc_x + (s2.loc_x - s1.loc_x) * f
                    if b.use_loc_y: step.loc_y = s1.loc_y + (s2.loc_y - s1.loc_y) * f
                    if b.use_loc_z: step.loc_z = s1.loc_z + (s2.loc_z - s1.loc_z) * f
                    if b.use_rot_x: step.rot_x = s1.rot_x + (s2.rot_x - s1.rot_x) * f
                    if b.use_rot_y: step.rot_y = s1.rot_y + (s2.rot_y - s1.rot_y) * f
                    if b.use_rot_z: step.rot_z = s1.rot_z + (s2.rot_z - s1.rot_z) * f
                    if b.use_scl_x: step.scl_x = s1.scl_x + (s2.scl_x - s1.scl_x) * f
                    if b.use_scl_y: step.scl_y = s1.scl_y + (s2.scl_y - s1.scl_y) * f
                    if b.use_scl_z: step.scl_z = s1.scl_z + (s2.scl_z - s1.scl_z) * f
                    step.status = 'EDITED'
            else:
                for seq_idx, step_idx in enumerate(sel):
                    if step_idx >= len(mapping.steps): continue
                    step = mapping.steps[step_idx]
                    m_val = (seq_idx + 1) if b.is_progressive else 1

                    if b.operation == 'SET':
                        if b.use_loc_x: step.loc_x = b.val_loc_x * m_val
                        if b.use_loc_y: step.loc_y = b.val_loc_y * m_val
                        if b.use_loc_z: step.loc_z = b.val_loc_z * m_val
                        if b.use_rot_x: step.rot_x = b.val_rot_x * m_val
                        if b.use_rot_y: step.rot_y = b.val_rot_y * m_val
                        if b.use_rot_z: step.rot_z = b.val_rot_z * m_val
                        if b.use_scl_x: step.scl_x = b.val_scl_x * m_val
                        if b.use_scl_y: step.scl_y = b.val_scl_y * m_val
                        if b.use_scl_z: step.scl_z = b.val_scl_z * m_val
                    elif b.operation == 'ADD':
                        if b.use_loc_x: step.loc_x += (b.val_loc_x * m_val)
                        if b.use_loc_y: step.loc_y += (b.val_loc_y * m_val)
                        if b.use_loc_z: step.loc_z += (b.val_loc_z * m_val)
                        if b.use_rot_x: step.rot_x += (b.val_rot_x * m_val)
                        if b.use_rot_y: step.rot_y += (b.val_rot_y * m_val)
                        if b.use_rot_z: step.rot_z += (b.val_rot_z * m_val)
                        if b.use_scl_x: step.scl_x += (b.val_scl_x * m_val)
                        if b.use_scl_y: step.scl_y += (b.val_scl_y * m_val)
                        if b.use_scl_z: step.scl_z += (b.val_scl_z * m_val)
                    elif b.operation == 'MIRROR':
                        if b.use_loc_x: step.loc_x *= -1
                        if b.use_loc_y: step.loc_y *= -1
                        if b.use_loc_z: step.loc_z *= -1
                        if b.use_rot_x: step.rot_x *= -1
                        if b.use_rot_y: step.rot_y *= -1
                        if b.use_rot_z: step.rot_z *= -1
                        if b.use_scl_x: step.scl_x *= -1
                        if b.use_scl_y: step.scl_y *= -1
                        if b.use_scl_z: step.scl_z *= -1
                    step.status = 'EDITED'
        finally: s.logic_sub_is_syncing = False
        update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_advanced_batch_snap(bpy.types.Operator):
    bl_idname = "logicsub.advanced_batch_snap"
    bl_label = "Advanced Batch Snap Macro"
    def execute(self, context):
        s = context.scene
        b = s.logic_sub_batch
        target_obj = b.snap_target_obj
        if not target_obj: return {'CANCELLED'}
        d_idx = s.logic_sub_active_deck_idx
        mapping = get_active_mapping(s, d_idx, create=True)
        if not mapping: return {'CANCELLED'}
        sel = [i for i, step in enumerate(mapping.steps) if step.is_selected_for_batch]
        if not sel: return {'CANCELLED'}
        drv_obj, drv_bone, is_bone = get_driven_target(s, d_idx)
        if not drv_obj: return {'CANCELLED'}
        
        orig_step = s.logic_sub_current_step
        orig_mode = context.mode
        s.logic_sub_is_syncing = True 
        try:
            if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
            for step_idx in sel:
                s.logic_sub_current_step = step_idx
                apply_logic_transform(context)
                context.view_layer.update() 
                
                depsgraph = context.evaluated_depsgraph_get()
                eval_target = target_obj.evaluated_get(depsgraph)
                context.scene.cursor.location = eval_target.matrix_world.translation.copy()
                
                for obj in context.view_layer.objects: obj.select_set(False)
                drv_obj.select_set(True)
                context.view_layer.objects.active = drv_obj
                
                if is_bone:
                    bpy.ops.object.mode_set(mode='POSE')
                    for bn in drv_obj.data.bones: bn.select = False
                    drv_obj.data.bones[drv_bone.name].select = True
                    drv_obj.data.bones.active = drv_obj.data.bones[drv_bone.name]
                
                override = context.copy()
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        override['area'] = area
                        override['region'] = area.regions[0]
                        break
                with context.temp_override(**override): bpy.ops.view3d.snap_selected_to_cursor(use_offset=False)
                context.view_layer.update()
                
                if is_bone: bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.logicsub.set_driven_step(step=step_idx, deck_override=d_idx)
        finally:
            if context.mode != orig_mode:
                try: bpy.ops.object.mode_set(mode=orig_mode)
                except: pass
            s.logic_sub_current_step = orig_step
            s.logic_sub_is_syncing = False
            apply_logic_transform(context); context.view_layer.update(); update_data_text(s)
        return {'FINISHED'}

class LOGICSUB_OT_auto_limit_bounds(bpy.types.Operator):
    bl_idname = "logicsub.auto_limit_bounds"
    bl_label = "Auto-Limit Bounds"
    deck_idx: IntProperty(default=-1)
    def execute(self, context):
        s = context.scene
        d_idx = s.logic_sub_active_deck_idx if self.deck_idx == -1 else self.deck_idx
        mapping = get_active_mapping(s, d_idx, create=False)
        if not mapping or len(mapping.steps) == 0: return {'CANCELLED'}

        drv_obj, drv_bone, drv_is_bone = get_driven_target(s, d_idx)
        if not drv_obj: return {'CANCELLED'}
        tgt = drv_bone if drv_is_bone else drv_obj

        gr = mapping.gear_ratio if mapping.gear_ratio != 0 else 1.0
        min_loc = [float('inf')] * 3; max_loc = [float('-inf')] * 3
        min_rot = [float('inf')] * 3; max_rot = [float('-inf')] * 3
        min_scl = [float('inf')] * 3; max_scl = [float('-inf')] * 3

        for step in mapping.steps:
            lx, ly, lz = step.loc_x * gr, step.loc_y * gr, step.loc_z * gr
            min_loc = [min(min_loc[0], lx), min(min_loc[1], ly), min(min_loc[2], lz)]
            max_loc = [max(max_loc[0], lx), max(max_loc[1], ly), max(max_loc[2], lz)]

            rx, ry, rz = step.rot_x * gr, step.rot_y * gr, step.rot_z * gr
            min_rot = [min(min_rot[0], rx), min(min_rot[1], ry), min(min_rot[2], rz)]
            max_rot = [max(max_rot[0], rx), max(max_rot[1], ry), max(max_rot[2], rz)]

            sx, sy, sz = 1.0 + (step.scl_x - 1.0) * gr, 1.0 + (step.scl_y - 1.0) * gr, 1.0 + (step.scl_z - 1.0) * gr
            min_scl = [min(min_scl[0], sx), min(min_scl[1], sy), min(min_scl[2], sz)]
            max_scl = [max(max_scl[0], sx), max(max_scl[1], sy), max(max_scl[2], sz)]

        def get_or_create_constraint(ctype, name):
            con = tgt.constraints.get(name)
            if not con: con = tgt.constraints.new(ctype); con.name = name
            return con

        c_loc = get_or_create_constraint('LIMIT_LOCATION', "LS_Limit_Loc")
        c_loc.owner_space = 'LOCAL'
        c_loc.use_min_x = c_loc.use_max_x = c_loc.use_min_y = c_loc.use_max_y = c_loc.use_min_z = c_loc.use_max_z = True
        c_loc.min_x, c_loc.max_x = min_loc[0], max_loc[0]; c_loc.min_y, c_loc.max_y = min_loc[1], max_loc[1]; c_loc.min_z, c_loc.max_z = min_loc[2], max_loc[2]

        c_rot = get_or_create_constraint('LIMIT_ROTATION', "LS_Limit_Rot")
        c_rot.owner_space = 'LOCAL'
        c_rot.use_limit_x = c_rot.use_limit_y = c_rot.use_limit_z = True
        c_rot.min_x, c_rot.max_x = min_rot[0], max_rot[0]; c_rot.min_y, c_rot.max_y = min_rot[1], max_rot[1]; c_rot.min_z, c_rot.max_z = min_rot[2], max_rot[2]

        c_scl = get_or_create_constraint('LIMIT_SCALE', "LS_Limit_Scl")
        c_scl.owner_space = 'LOCAL'
        c_scl.use_min_x = c_scl.use_max_x = c_scl.use_min_y = c_scl.use_max_y = c_scl.use_min_z = c_scl.use_max_z = True
        c_scl.min_x, c_scl.max_x = min_scl[0], max_scl[0]; c_scl.min_y, c_scl.max_y = min_scl[1], max_scl[1]; c_scl.min_z, c_scl.max_z = min_scl[2], max_scl[2]

        c_loc.use_transform_limit = c_rot.use_transform_limit = c_scl.use_transform_limit = False
        return {'FINISHED'}

class LOGICSUB_OT_bridge_segs(bpy.types.Operator):
    bl_idname = "logicsub.bridge_segs"
    bl_label = "Bridge Selected Segs"
    def execute(self, context):
        m = get_active_mapping(context.scene, create=True)
        segs = [t for t in m.tags if t.type == 'SEG' and t.is_selected_for_bridge]
        if len(segs) != 2: return {'CANCELLED'}
        s1, s2 = segs[0].target_step, segs[1].target_step
        new_tag = m.tags.add()
        new_tag.type = 'GROUPIE'; new_tag.name = f"{segs[0].name} > {segs[1].name}"
        for _ in range(m.substeps + 1): new_tag.group_steps.add()
        start, end = min(s1, s2), max(s1, s2)
        for i in range(start, end + 1):
            if i < len(new_tag.group_steps): new_tag.group_steps[i].is_active = True
        segs[0].is_selected_for_bridge = False; segs[1].is_selected_for_bridge = False
        return {'FINISHED'}

class LOGICSUB_OT_bake_action(bpy.types.Operator):
    bl_idname = "logicsub.bake_action"
    bl_label = "Bake Track to Action"
    idx: IntProperty()
    def execute(self, context):
        s = context.scene
        m = get_active_mapping(s, create=True)
        tag = m.tags[self.idx]
        d_obj, d_bone, d_is_bone = get_driven_target(s)
        if not d_obj: return {'CANCELLED'}
        tgt = d_bone if d_is_bone else d_obj
        action = bpy.data.actions.new(name=f"{d_obj.name}_{tag.name}_Action")
        if not d_obj.animation_data: d_obj.animation_data_create()
        d_obj.animation_data.action = action
        
        base_steps = [i for i, gs in enumerate(tag.group_steps) if gs.is_active]
        if not base_steps: return {'CANCELLED'}
        
        sequence = []
        if tag.bake_mode == 'ONCE': sequence = base_steps
        elif tag.bake_mode == 'LOOP': sequence = base_steps * tag.loop_count
        elif tag.bake_mode == 'PING_PONG': ping = base_steps + base_steps[-2::-1]; sequence = ping * tag.loop_count
        
        current_frame = float(s.frame_current)
        total_steps = len(sequence); gr = m.gear_ratio
        
        for i, step_idx in enumerate(sequence):
            if step_idx >= len(m.steps): continue
            step = m.steps[step_idx]
            jx, jy, jz, jrx, jry, jrz = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            if tag.use_jitter:
                ji = tag.jitter_intensity
                noise_val = fbm_noise(current_frame * 0.1) * ji
                jx = noise_val; jy = noise_val * 0.5; jz = noise_val
                jrx = noise_val * 0.2; jry = noise_val * 0.2; jrz = noise_val * 0.2
            
            tgt.location = ((step.loc_x + jx) * gr, (step.loc_y + jy) * gr, (step.loc_z + jz) * gr)
            if tgt.rotation_mode not in {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'}: tgt.rotation_mode = 'XYZ'
            tgt.rotation_euler = ((step.rot_x + jrx) * gr, (step.rot_y + jry) * gr, (step.rot_z + jrz) * gr)
            tgt.scale = (1.0 + (step.scl_x - 1.0) * gr, 1.0 + (step.scl_y - 1.0) * gr, 1.0 + (step.scl_z - 1.0) * gr)
            
            frame_int = int(round(current_frame))
            for data_path in ["location", "rotation_euler", "scale"]:
                tgt.keyframe_insert(data_path=data_path, frame=frame_int)
                
            if step.step_label != "":
                marker_name = f"{tag.name}: {step.step_label}"
                s.timeline_markers.new(name=marker_name, frame=frame_int)
                
            if d_obj.animation_data and d_obj.animation_data.action:
                for fc in d_obj.animation_data.action.fcurves:
                    for kp in fc.keyframe_points:
                        if abs(kp.co[0] - frame_int) < 0.1:
                            if step.smoov_preset == 'STEP': 
                                kp.interpolation = 'CONSTANT'
                            elif step.smoov_preset == 'LINEAR': 
                                kp.interpolation = 'LINEAR'
                            elif step.smoov_preset == 'VISCOUS':
                                kp.interpolation = 'BEZIER'
                                kp.easing = 'EASE_IN'
                            elif step.smoov_preset == 'CLAMPED':
                                kp.interpolation = 'BEZIER'
                                kp.easing = 'EASE_OUT'
                            else: 
                                kp.interpolation = 'BEZIER'
            
            for mc in step.mod_con_states:
                try:
                    live_mc = None
                    if mc.type == 'MOD' and not d_is_bone: live_mc = d_obj.modifiers.get(mc.name)
                    elif mc.type == 'CON' and not d_is_bone: live_mc = d_obj.constraints.get(mc.name)
                    elif mc.type == 'BCON' and d_is_bone: live_mc = d_bone.constraints.get(mc.name)
                    if live_mc:
                        if mc.type == 'MOD': 
                            live_mc.show_viewport = mc.show_viewport; live_mc.keyframe_insert(data_path="show_viewport", frame=frame_int)
                        else: 
                            live_mc.influence = mc.influence; live_mc.keyframe_insert(data_path="influence", frame=frame_int)
                except: pass
                
            if i < total_steps - 1:
                t = i / (total_steps - 1) if total_steps > 1 else 0
                gap = float(tag.frame_gap)
                if tag.time_warp == 'ACCEL': gap = max(1.0, gap * (2.0 - t))
                elif tag.time_warp == 'DECEL': gap = max(1.0, gap * (0.5 + t))
                current_frame += gap

        if tag.push_to_nla:
            anim_data = d_obj.animation_data
            if not anim_data.nla_tracks: track = anim_data.nla_tracks.new()
            else: track = anim_data.nla_tracks.get(tag.name) or anim_data.nla_tracks.new()
            track.name = tag.name
            strip = track.strips.new(action.name, int(s.frame_current), action)
            strip.blend_type = 'REPLACE'
        return {'FINISHED'}

class LOGICSUB_OT_add_tag(bpy.types.Operator):
    bl_idname = "logicsub.add_tag"
    bl_label = "Add Tag"
    tag_type: StringProperty()
    def execute(self, context):
        mapping = get_active_mapping(context.scene, create=True)
        if mapping:
            tag = mapping.tags.add()
            tag.type = self.tag_type; tag.name = "New Seg" if self.tag_type == 'SEG' else "New Track"
            if self.tag_type == 'GROUPIE':
                target_len = max(1, mapping.substeps + 1)
                for _ in range(target_len): tag.group_steps.add()
                tag.is_expanded = True
        return {'FINISHED'}

class LOGICSUB_OT_remove_tag(bpy.types.Operator):
    bl_idname = "logicsub.remove_tag"
    bl_label = "Remove Tag"
    idx: IntProperty()
    def execute(self, context):
        mapping = get_active_mapping(context.scene, create=True)
        if mapping: mapping.tags.remove(self.idx)
        return {'FINISHED'}

class LOGICSUB_OT_smooth_groupie(bpy.types.Operator):
    bl_idname = "logicsub.smooth_groupie"
    bl_label = "Smooth Slope"
    idx: IntProperty()
    def execute(self, context):
        mapping = get_active_mapping(context.scene, create=True)
        if not mapping: return {'CANCELLED'}
        tag = mapping.tags[self.idx]
        if tag.type != 'GROUPIE': return {'CANCELLED'}
        
        active_idx = [i for i, gs in enumerate(tag.group_steps) if gs.is_active]
        if len(active_idx) < 3: return {'CANCELLED'}
            
        start_i, end_i = active_idx[0], active_idx[-1]
        if start_i >= len(mapping.steps) or end_i >= len(mapping.steps): return {'CANCELLED'}
            
        s1, s2 = mapping.steps[start_i], mapping.steps[end_i]
        context.scene.logic_sub_is_syncing = True
        try:
            for i in range(start_i + 1, end_i):
                if i in active_idx:
                    t = (i - start_i) / (end_i - start_i)
                    if tag.ease_type == 'EASE_IN': fac = t * t
                    elif tag.ease_type == 'EASE_OUT': fac = 1 - (1 - t) * (1 - t)
                    elif tag.ease_type == 'EASE_IN_OUT': fac = 2 * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 2) / 2
                    elif tag.ease_type == 'OVERSHOOT': c1 = 1.70158; c3 = c1 + 1; fac = 1 + c3 * math.pow(t - 1, 3) + c1 * math.pow(t - 1, 2)
                    elif tag.ease_type == 'BOUNCE':
                        n1 = 7.5625; d1 = 2.75
                        if t < 1 / d1: fac = n1 * t * t
                        elif t < 2 / d1: t -= 1.5 / d1; fac = n1 * t * t + 0.75
                        elif t < 2.5 / d1: t -= 2.25 / d1; fac = n1 * t * t + 0.9375
                        else: t -= 2.625 / d1; fac = n1 * t * t + 0.984375
                    elif tag.ease_type == 'ELASTIC':
                        c4 = (2 * math.pi) / 3
                        if t == 0: fac = 0
                        elif t == 1: fac = 1
                        else: fac = -math.pow(2, 10 * t - 10) * math.sin((t * 10 - 10.75) * c4)
                    else: fac = t 
                    
                    step = mapping.steps[i]
                    step.loc_x = s1.loc_x + (s2.loc_x - s1.loc_x) * fac; step.loc_y = s1.loc_y + (s2.loc_y - s1.loc_y) * fac; step.loc_z = s1.loc_z + (s2.loc_z - s1.loc_z) * fac
                    step.rot_x = s1.rot_x + (s2.rot_x - s1.rot_x) * fac; step.rot_y = s1.rot_y + (s2.rot_y - s1.rot_y) * fac; step.rot_z = s1.rot_z + (s2.rot_z - s1.rot_z) * fac
                    step.scl_x = s1.scl_x + (s2.scl_x - s1.scl_x) * fac; step.scl_y = s1.scl_y + (s2.scl_y - s1.scl_y) * fac; step.scl_z = s1.scl_z + (s2.scl_z - s1.scl_z) * fac
                    step.status = 'EDITED'
        finally: context.scene.logic_sub_is_syncing = False
        update_data_text(context.scene); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_activate_tag(bpy.types.Operator):
    bl_idname = "logicsub.activate_tag"
    bl_label = "Play/Load Track"
    idx: IntProperty()
    def execute(self, context):
        s = context.scene
        mapping = get_active_mapping(s, create=True)
        if not mapping: return {'CANCELLED'}
        tag = mapping.tags[self.idx]
        
        if tag.type == 'SEG':
            s.logic_sub_current_step = tag.target_step; apply_logic_transform(context)
        elif tag.type == 'GROUPIE':
            s.logic_sub_show_batcher = True
            for i, step in enumerate(mapping.steps): step.is_selected_for_batch = tag.group_steps[i].is_active if i < len(tag.group_steps) else False
        return {'FINISHED'}

class LOGICSUB_OT_clear_all_steps(bpy.types.Operator):
    bl_idname = "logicsub.clear_all_steps"
    bl_label = "Clear All Steps"
    def execute(self, context):
        s = context.scene
        m = get_active_mapping(s, create=True)
        if not m: return {'CANCELLED'}
        s.logic_sub_is_syncing = True
        try:
            for step in m.steps:
                step.loc_x = step.loc_y = step.loc_z = 0.0
                step.rot_x = step.rot_y = step.rot_z = 0.0
                step.scl_x = step.scl_y = step.scl_z = 1.0
                step.mod_con_states.clear()
                step.status = 'UNSET'
        finally: s.logic_sub_is_syncing = False
        update_data_text(s) 
        # REMOVED apply_logic_transform(context) -> Now it won't snap the physical viewport objects to zero!
        return {'FINISHED'}

class LOGICSUB_OT_capture_all_steps(bpy.types.Operator):
    bl_idname = "logicsub.capture_all_steps"
    bl_label = "Capture All Steps"
    def execute(self, context):
        m = get_active_mapping(context.scene, create=True)
        if not m: return {'CANCELLED'}
        for i in range(len(m.steps)): bpy.ops.logicsub.set_driven_step(step=i)
        return {'FINISHED'}

class LOGICSUB_OT_import_data(bpy.types.Operator, ImportHelper):
    bl_idname = "logicsub.import_data"
    bl_label = "Import Data (.txt)"
    filename_ext = ".txt"
    axis_override: EnumProperty(items=[('AUTO', "Current Tab", ""), ('POS', "Force (+)", ""), ('NEG', "Force (-)", "")], default='AUTO')
    def execute(self, context):
        with open(self.filepath, 'r', encoding='utf-8') as f: content = f.read()
        if "=== LOGIC SUBSTEPP'N MASTER DATA ===" not in content and "COMBINATION:" not in content:
            return {'CANCELLED'}
        processed_lines = []
        for line in content.splitlines():
            if line.startswith("COMBINATION:"):
                parts = line.split("|")
                combo_str = parts[0]
                if "__POS" not in combo_str and "__NEG" not in combo_str:
                    suffix = "__POS" if self.axis_override == 'POS' else "__NEG"
                    if self.axis_override == 'AUTO': suffix = f"__{context.scene.logic_sub_direction}"
                    combo_str = combo_str.rstrip() + suffix + " "
                elif self.axis_override == 'POS': combo_str = combo_str.replace("__NEG", "__POS")
                elif self.axis_override == 'NEG': combo_str = combo_str.replace("__POS", "__NEG")
                line = combo_str + " | " + " | ".join(parts[1:]) if len(parts) > 1 else combo_str
            processed_lines.append(line)
        sync_from_data_text(context, raw_text="\n".join(processed_lines))
        return {'FINISHED'}

class LOGICSUB_OT_export_data(bpy.types.Operator):
    bl_idname = "logicsub.export_data"
    bl_label = "Export Backup Data"
    def execute(self, context):
        update_data_text(context.scene)
        txt = bpy.data.texts.get("LogicSub_Data.txt")
        if not txt: return {'CANCELLED'}
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = get_substeppn_path(f"data/LogicSub_Data_{timestamp}.txt")
        if not path: return {'CANCELLED'}
        with open(path, "w", encoding="utf-8") as f: f.write(txt.as_string())
        return {'FINISHED'}

class LOGICSUB_OT_sync_text(bpy.types.Operator):
    bl_idname = "logicsub.sync_text"
    bl_label = "Sync from Text"
    def execute(self, context):
        sync_from_data_text(context)
        return {'FINISHED'}

class LOGICSUB_OT_open_data(bpy.types.Operator):
    bl_idname = "logicsub.open_data"
    bl_label = "Open Live Data Table"
    def execute(self, context):
        update_data_text(context.scene)
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.spaces.active.text = bpy.data.texts.get("LogicSub_Data.txt")
                return {'FINISHED'}
        bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
        new_area = context.screen.areas[-1]
        new_area.type = 'TEXT_EDITOR'
        new_area.spaces.active.text = bpy.data.texts.get("LogicSub_Data.txt")
        return {'FINISHED'}

class LOGICSUB_OT_reset_table(bpy.types.Operator):
    bl_idname = "logicsub.reset_table"
    bl_label = "Reset Master Table"
    def execute(self, context):
        s = context.scene
        mapping = get_active_mapping(s, create=True)
        if not mapping: return {'CANCELLED'}
        s.logic_sub_is_syncing = True
        try:
            for step in mapping.steps:
                step.loc_x = step.loc_y = step.loc_z = 0.0
                step.rot_x = step.rot_y = step.rot_z = 0.0
                step.scl_x = step.scl_y = step.scl_z = 1.0
                step.mod_con_states.clear()
                step.status = 'UNSET'
        finally:
            s.logic_sub_is_syncing = False
        update_data_text(s); apply_logic_transform(context)
        return {'FINISHED'}

class LOGICSUB_OT_open_log(bpy.types.Operator):
    bl_idname = "logicsub.open_log"
    bl_label = "Open Activity Log"
    def execute(self, context):
        txt = bpy.data.texts.get("LogicSub_Activity_Log.txt")
        if not txt: txt = bpy.data.texts.new("LogicSub_Activity_Log.txt")
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.spaces.active.text = txt
                return {'FINISHED'}
        bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
        context.screen.areas[-1].type = 'TEXT_EDITOR'
        context.screen.areas[-1].spaces.active.text = txt
        return {'FINISHED'}

class LOGICSUB_OT_generate_drivers(bpy.types.Operator):
    bl_idname = "logicsub.generate_drivers"
    bl_label = "Generate / Update Drivers"
    def execute(self, context):
        scene = context.scene
        t_obj, t_bone, t_is_bone = get_logic_target(scene)
        if not t_obj: return {'CANCELLED'}
        t_n = t_bone.name if t_is_bone else t_obj.name
        generate_driver_script(scene)
        
        for d_idx, deck in enumerate(scene.logic_sub_decks):
            d_obj, d_bone, d_is_bone = get_driven_target(scene, d_idx)
            if not d_obj: continue
            
            d_n = d_bone.name if d_is_bone else d_obj.name
            base_combo_name = f"{t_n}__TO__{d_n}"
            drv_target = d_bone if d_is_bone else d_obj
            channel = scene.logic_sub_channel
            
            all_mcs = {}
            for dir_suffix in ('__POS', '__NEG'):
                m_name = base_combo_name + dir_suffix
                for m in scene.logic_sub_mappings:
                    if m.name == m_name and len(m.steps) > 0:
                        for mc in m.steps[0].mod_con_states:
                            all_mcs[f"{mc.type}_{mc.name}"] = mc
            
            create_single_driver(t_obj, t_bone, drv_target, "location", 0, base_combo_name, "loc_x", channel)
            create_single_driver(t_obj, t_bone, drv_target, "location", 1, base_combo_name, "loc_y", channel)
            create_single_driver(t_obj, t_bone, drv_target, "location", 2, base_combo_name, "loc_z", channel)
            
            if drv_target.rotation_mode not in {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'}: drv_target.rotation_mode = 'XYZ'
            create_single_driver(t_obj, t_bone, drv_target, "rotation_euler", 0, base_combo_name, "rot_x", channel)
            create_single_driver(t_obj, t_bone, drv_target, "rotation_euler", 1, base_combo_name, "rot_y", channel)
            create_single_driver(t_obj, t_bone, drv_target, "rotation_euler", 2, base_combo_name, "rot_z", channel)
            
            create_single_driver(t_obj, t_bone, drv_target, "scale", 0, base_combo_name, "scl_x", channel)
            create_single_driver(t_obj, t_bone, drv_target, "scale", 1, base_combo_name, "scl_y", channel)
            create_single_driver(t_obj, t_bone, drv_target, "scale", 2, base_combo_name, "scl_z", channel)
            
            for mc in all_mcs.values():
                mc_id = f"{mc.type}_{mc.name}"
                live_mc = d_obj.modifiers.get(mc.name) if mc.type == 'MOD' and not d_is_bone else (d_obj.constraints.get(mc.name) if mc.type == 'CON' and not d_is_bone else (d_bone.constraints.get(mc.name) if mc.type == 'BCON' and d_is_bone else None))
                if live_mc:
                    if mc.type == 'MOD': create_single_driver(t_obj, t_bone, live_mc, "show_viewport", None, base_combo_name, mc_id + "_view", channel)
                    else: create_single_driver(t_obj, t_bone, live_mc, "influence", None, base_combo_name, mc_id + "_inf", channel)
                    for tp in mc.tracked_props:
                        create_single_driver(t_obj, t_bone, live_mc, tp.prop_name, None, base_combo_name, mc_id + "_" + tp.prop_name, channel)
        return {'FINISHED'}
        
# -------------------------------------------------------
# DECKFLOW™ NESTED UI ENGINE
# -------------------------------------------------------

class LOGICSUB_UL_deck_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        deck_name = item.driven_bone if item.driven_bone else (item.driven_object.name if item.driven_object else f"Deck {index+1}")
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=deck_name, icon='OBJECT_DATA')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OBJECT_DATA')

def _draw_single_deck_step(layout, context, s, mapping, deck_idx, step_idx, subs, is_nested=False):
    step_data = mapping.steps[step_idx]
    
    if step_idx % 2 == 0: wrapper = layout.box(); box = wrapper.column(align=True)
    else: box = layout.column(align=True)
        
    if step_data.is_bookmarked: box.alert = True 
    row_header = box.row(align=True)
    
    d_obj = s.logic_sub_decks[deck_idx].driven_object
    d_name = s.logic_sub_decks[deck_idx].driven_bone if s.logic_sub_decks[deck_idx].driven_bone else (d_obj.name if d_obj else f"Deck {deck_idx+1}")
    lbl_tag = f" '{step_data.step_label}'" if step_data.step_label else ""
    header_text = f"STEP {step_idx}{lbl_tag} ➔ [{d_name.upper()}]"
    
    row_header.prop(step_data, "show_mod_cons", text=header_text, icon='OUTLINER' if step_data.show_mod_cons else 'OPTIONS', emboss=True)
    
    pct = int(round(100 * step_idx / max(1, subs))) if subs > 0 else 0
    op_jump = row_header.operator("logicsub.exec", text=f"[{pct}%]")
    op_jump.mode = 'JUMP'; op_jump.step = step_idx
    
    row_header.prop(step_data, "is_bookmarked", text="", icon='SOLO_ON' if step_data.is_bookmarked else 'SOLO_OFF')
    iso_op = row_header.operator("logicsub.isolate_target", text="", icon='HIDE_OFF'); iso_op.deck_idx = deck_idx
    
    wand_op = row_header.operator("logicsub.wand_snap", text="", icon='AUTO'); wand_op.step_idx = step_idx; wand_op.deck_idx = deck_idx

    if not is_nested:
        op_exp = row_header.operator("logicsub.toggle_nested_decks", text="", icon='OUTLINER_OB_GROUP_INSTANCE'); op_exp.step_idx = step_idx
        
    op_play = row_header.operator("logicsub.play_to_step", text="", icon='PLAY'); op_play.target_step = step_idx
    op_copy = row_header.operator("logicsub.copy_clipboard", text="", icon='COPYDOWN'); op_copy.idx = step_idx; op_copy.deck_idx = deck_idx
    op_paste = row_header.operator("logicsub.paste_clipboard", text="", icon='PASTEDOWN'); op_paste.idx = step_idx; op_paste.deck_idx = deck_idx

    if step_data.status == 'UNSET': row_header.alert = True 
    set_op = row_header.operator("logicsub.set_driven_step", text="Capture", icon='RECORD_ON' if step_data.status == 'UNSET' else 'FILE_REFRESH', depress=(step_data.status == 'EDITED'))
    set_op.step = step_idx; set_op.deck_override = deck_idx

    if step_data.show_mod_cons:
        d_box = box.box()
        
        # SMOOV'MNT ENGINE: Curve Preset, Panel Toggle & Labeling Row
        smoov_box = d_box.box()
        smoov_header = smoov_box.row(align=True)
        smoov_header.prop(step_data, "show_smoov_panel", icon='IPO_BEZIER', text="", toggle=True)
        smoov_header.prop(step_data, "step_label", text="", icon='BOOKMARKS', placeholder="Substep Tag (e.g., Contact)")
        smoov_header.prop(step_data, "smoov_preset", text="")
        
        op_recoil = smoov_header.operator("logicsub.generate_recoil", text="", icon='GRAPH')
        op_recoil.step_idx = step_idx
        op_recoil.deck_idx = deck_idx

        # Expanded Smoov'mnt Panel
        if step_data.show_smoov_panel:
            s_panel = smoov_box.column(align=True)
            if step_data.smoov_preset not in {'LINEAR', 'STEP'}:
                r = s_panel.row(align=True)
                r.prop(step_data, "smoov_blend", text="Curve Power", slider=True)
                r.prop(step_data, "smoov_tension", text="Tension", slider=True)
            else:
                s_panel.label(text="Advanced curve sliders disabled for Linear/Step modes.", icon='INFO')
        
        row_loc = d_box.row(align=True)
        row_loc.prop(step_data, "loc_x", text="X"); row_loc.prop(step_data, "loc_y", text="Y"); row_loc.prop(step_data, "loc_z", text="Z")
        row_rot = d_box.row(align=True)
        row_rot.prop(step_data, "rot_x", text="Rot X"); row_rot.prop(step_data, "rot_y", text="Rot Y"); row_rot.prop(step_data, "rot_z", text="Rot Z")
        row_scl = d_box.row(align=True)
        row_scl.prop(step_data, "scl_x", text="Scale X"); row_scl.prop(step_data, "scl_y", text="Scale Y"); row_scl.prop(step_data, "scl_z", text="Scale Z")

        row_tools = d_box.row(align=True)
        row_tools.prop(step_data, "show_cursor_tools", text="", icon='PIVOT_CURSOR', toggle=True)
        row_tools.prop(step_data, "show_quick_math", text="Quick Math", icon='MOD_ARRAY', toggle=True)
        row_tools.prop(step_data, "show_shuffle", text="Shuffle Cycle", icon='UV_SYNC_SELECT', toggle=True)
        
        op_flip = row_tools.operator("logicsub.flip_step", text="Flip", icon='ARROW_LEFTRIGHT'); op_flip.step_idx = step_idx; op_flip.deck_idx = deck_idx

        if step_data.show_cursor_tools:
            c_box = d_box.box(); c_box.label(text="Transform & Origin Tools", icon='PIVOT_CURSOR')
            r1 = c_box.row(align=True)
            op1 = r1.operator("logicsub.step_tool", text="Cursor to Sel", icon='RESTRICT_SELECT_OFF'); op1.action = 'CURSOR_TO_SEL'; op1.step_idx = step_idx; op1.deck_idx = deck_idx
            op2 = r1.operator("logicsub.step_tool", text="Sel to Cursor (+ Capture)", icon='PIVOT_CURSOR'); op2.action = 'SEL_TO_CURSOR'; op2.step_idx = step_idx; op2.deck_idx = deck_idx
            r2 = c_box.row(align=True)
            op3 = r2.operator("logicsub.step_tool", text="Cursor to World", icon='SNAP_GRID'); op3.action = 'CURSOR_TO_WORLD'; op3.step_idx = step_idx; op3.deck_idx = deck_idx
            r3 = c_box.row(align=True)
            op4 = r3.operator("logicsub.step_tool", text="Origin to Cursor", icon='OBJECT_ORIGIN'); op4.action = 'ORIGIN_TO_CURSOR'; op4.step_idx = step_idx; op4.deck_idx = deck_idx
            op5 = r3.operator("logicsub.step_tool", text="Origin to Geom", icon='SNAP_VOLUME'); op5.action = 'ORIGIN_TO_GEOM'; op5.step_idx = step_idx; op5.deck_idx = deck_idx

        if step_data.show_shuffle:
            shuf_box = d_box.box()
            shuf_row = shuf_box.row(align=True); shuf_row.label(text="Cycle Axes:")
            op1 = shuf_row.operator("logicsub.shuffle_channels", text="X➔Y➔Z", icon='TRIA_RIGHT'); op1.step_idx = step_idx; op1.deck_idx = deck_idx; op1.mode = 'AXIS_FWD'
            op2 = shuf_row.operator("logicsub.shuffle_channels", text="Z➔Y➔X", icon='TRIA_LEFT'); op2.step_idx = step_idx; op2.deck_idx = deck_idx; op2.mode = 'AXIS_BWD'
            shuf_row2 = shuf_box.row(align=True); shuf_row2.label(text="Cycle Type:")
            op3 = shuf_row2.operator("logicsub.shuffle_channels", text="Loc➔Rot➔Scl", icon='TRIA_RIGHT'); op3.step_idx = step_idx; op3.deck_idx = deck_idx; op3.mode = 'TYPE_FWD'
            op4 = shuf_row2.operator("logicsub.shuffle_channels", text="Scl➔Rot➔Loc", icon='TRIA_LEFT'); op4.step_idx = step_idx; op4.deck_idx = deck_idx; op4.mode = 'TYPE_BWD'
            op5 = shuf_row2.operator("logicsub.shuffle_channels", text="Smart Cycle", icon='FILE_REFRESH'); op5.step_idx = step_idx; op5.deck_idx = deck_idx; op5.mode = 'TYPE_SMART'

        if step_data.show_quick_math:
            qm_box = d_box.box()
            r_chan = qm_box.row(align=True)
            r_chan.prop(step_data, "qm_loc_x", text="Loc X", toggle=True); r_chan.prop(step_data, "qm_loc_y", text="Loc Y", toggle=True); r_chan.prop(step_data, "qm_loc_z", text="Loc Z", toggle=True)
            r_chan2 = qm_box.row(align=True)
            r_chan2.prop(step_data, "qm_rot_x", text="Rot X", toggle=True); r_chan2.prop(step_data, "qm_rot_y", text="Rot Y", toggle=True); r_chan2.prop(step_data, "qm_rot_z", text="Rot Z", toggle=True)
            r_chan3 = qm_box.row(align=True)
            r_chan3.prop(step_data, "qm_scl_x", text="Scl X", toggle=True); r_chan3.prop(step_data, "qm_scl_y", text="Scl Y", toggle=True); r_chan3.prop(step_data, "qm_scl_z", text="Scl Z", toggle=True)
            op_row = qm_box.row(align=True); op_row.prop(step_data, "qm_op", text=""); op_row.prop(step_data, "qm_val", text="")
            prop_row = qm_box.row(align=True)
            op_up = prop_row.operator("logicsub.quick_math_propagate", text="To Start", icon='TRIA_UP_BAR'); op_up.step_idx = step_idx; op_up.direction = 'TO_START'; op_up.deck_idx = deck_idx
            op_dn = prop_row.operator("logicsub.quick_math_propagate", text="To End", icon='TRIA_DOWN_BAR'); op_dn.step_idx = step_idx; op_dn.direction = 'TO_END'; op_dn.deck_idx = deck_idx

        # Modifiers and Constraints
        if step_data.show_mod_cons:
            mc_box = d_box.box()
            if not step_data.mod_con_states: mc_box.label(text="Hit Capture to fetch Mods/Constraints.", icon='INFO')
            else:
                for mc in step_data.mod_con_states:
                    m_box = mc_box.box()
                    mc_row = m_box.row()
                    if mc.type == 'MOD': mc_row.label(text=mc.name, icon='MODIFIER')
                    elif mc.type == 'CON': mc_row.label(text=mc.name, icon='CONSTRAINT')
                    elif mc.type == 'BCON': mc_row.label(text=mc.name, icon='CONSTRAINT_BONE')
                        
                    if mc.type == 'MOD': mc_row.prop(mc, "show_viewport", text="View")
                    else: mc_row.prop(mc, "influence", text="Inf")
                    
                    lock_row = m_box.row(align=True)
                    lock_row.prop_search(mc, "locked_groupie", mapping, "tags", text="", icon='LINKED')
                    
                    for tp in mc.tracked_props:
                        tp_row = m_box.row(align=True)
                        tp_row.label(text=tp.prop_name.replace("_", " ").title())
                        if tp.prop_type == 'FLOAT': tp_row.prop(tp, "val_float", text="")
                        elif tp.prop_type == 'INT': tp_row.prop(tp, "val_int", text="")
                        elif tp.prop_type == 'BOOL': tp_row.prop(tp, "val_bool", text="")
                        rem_op = tp_row.operator("logicsub.remove_tracked_prop", text="", icon='X')
                        rem_op.step_idx = step_idx; rem_op.mc_name = mc.name; rem_op.mc_type = mc.type; rem_op.prop_name = tp.prop_name; rem_op.deck_idx = deck_idx
                    
                    add_row = m_box.row(align=True)
                    add_row.prop(mc, "prop_selector", text="")
                    add_op = add_row.operator("logicsub.add_tracked_prop", text="", icon='ADD')
                    add_op.step_idx = step_idx; add_op.mc_name = mc.name; add_op.mc_type = mc.type; add_op.deck_idx = deck_idx

    if not is_nested:
        f_box = box.box() 
        f_row = f_box.row(align=True)
        btn_reset = f_row.operator("logicsub.reset_step_transforms", text="", icon='LOOP_BACK'); btn_reset.step_idx = step_idx; btn_reset.deck_idx = deck_idx
        
        if step_data.has_snapshot:
            btn_snap = f_row.operator("logicsub.snapshot_step", text="Restore Snap", icon='FILE_TICK'); btn_snap.action = 'RESTORE'; btn_snap.step_idx = step_idx; btn_snap.deck_idx = deck_idx
        else:
            btn_snap = f_row.operator("logicsub.snapshot_step", text="Save Snap", icon='CAMERA_DATA'); btn_snap.action = 'SAVE'; btn_snap.step_idx = step_idx; btn_snap.deck_idx = deck_idx
            
        btn_bridge = f_row.operator("logicsub.bridge_to_next", text="Bridge to Next", icon='FORWARD'); btn_bridge.step_idx = step_idx; btn_bridge.deck_idx = deck_idx
        if len(step_data.mod_con_states) > 0: f_row.label(text="", icon='CONSTRAINT')

def draw_step_ui_with_deckflow(layout, context, s, active_mapping, active_deck_idx, step_idx, subs):
    _draw_single_deck_step(layout, context, s, active_mapping, active_deck_idx, step_idx, subs, is_nested=False)
    
    for d_idx, deck in enumerate(s.logic_sub_decks):
        if d_idx == active_deck_idx: continue
        m_nested = get_active_mapping(s, d_idx, create=False)
        if not m_nested or step_idx >= len(m_nested.steps): continue
        
        step_data = m_nested.steps[step_idx]
        deck_name = deck.driven_bone if deck.driven_bone else (deck.driven_object.name if deck.driven_object else f"Deck {d_idx+1}")
        
        row = layout.row()
        row.prop(step_data, "show_nested_deck", text=f"➔ Deck {d_idx+1}: {deck_name}", icon='LIBRARY_DATA_OVERRIDE', toggle=True)
        
        if step_data.show_nested_deck:
            _draw_single_deck_step(layout, context, s, m_nested, d_idx, step_idx, subs, is_nested=True)
            
    layout.separator(factor=0.25)
    
# -------------------------------------------------------
# MAIN UI PANEL
# -------------------------------------------------------

class VIEW3D_PT_logic_sub(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Substepp'n"
    bl_label = "Logic Substepp'n: DeckFlow"

    def draw(self, context):
        layout = self.layout
        s = context.scene

        # --- TOP HEADER: FILE OPS & SYSTEM ---
        row_sys = layout.row(align=True)
        row_sys.operator("logicsub.import_data", text="Import", icon='IMPORT')
        row_sys.operator("logicsub.export_data", text="Export", icon='EXPORT')
        row_sys.operator("logicsub.sync_text", text="Sync", icon='FILE_REFRESH')
        
        row_db = layout.row(align=True)
        row_db.operator("logicsub.open_data", text="Data", icon='SPREADSHEET')
        row_db.operator("logicsub.open_log", text="Log", icon='TEXT')
        row_db.operator("logicsub.reset_table", text="Reset Master", icon='TRASH')
        row_db.operator("logicsub.copy_error", text="", icon='ERROR')
        
        layout.separator()

        # --- 1. TARGET SELECTION (LOGIC DRIVER) ---
        box_target = layout.box()
        box_target.label(text="Logic Trigger (The Driver)", icon='CON_KINEMATIC')
        box_target.prop(s, "logic_sub_object", text="")
        t_obj = s.logic_sub_object
        if t_obj and t_obj.type == 'ARMATURE':
            box_target.prop_search(s, "logic_sub_bone_name", t_obj.pose, "bones", text="", icon='BONE_DATA')
        
        row_chan = box_target.row(align=True)
        row_chan.prop(s, "logic_sub_channel", text="")
        row_chan.prop(s, "logic_sub_direction", text="", icon='ARROW_LEFTRIGHT')

        # --- 2. DECK MANAGER (DRIVEN TARGETS) ---
        layout.separator()
        box_deck = layout.box()
        row_deck_header = box_deck.row()
        row_deck_header.label(text="Driven Decks", icon='LIBRARY_DATA_OVERRIDE')
        
        # New UI Viewer List Implementation
        row_list = box_deck.row()
        row_list.template_list("LOGICSUB_UL_deck_list", "", s, "logic_sub_decks", s, "logic_sub_active_deck_idx", rows=3)
        
        col_list_ops = row_list.column(align=True)
        col_list_ops.operator("logicsub.add_deck", text="", icon='ADD')
        col_list_ops.operator("logicsub.remove_deck", text="", icon='REMOVE')
        col_list_ops.separator()
        op_up = col_list_ops.operator("logicsub.move_deck", text="", icon='TRIA_UP')
        op_up.direction = 'UP'
        op_dn = col_list_ops.operator("logicsub.move_deck", text="", icon='TRIA_DOWN')
        op_dn.direction = 'DOWN'
        
        if len(s.logic_sub_decks) == 0:
            box_deck.label(text="No decks. Add one to start.", icon='INFO')
            return

        d_idx = s.logic_sub_active_deck_idx
        deck = s.logic_sub_decks[d_idx]
        
        row_deck_tools = box_deck.row(align=True)
        op_copy = row_deck_tools.operator("logicsub.copy_deck", text="Copy Deck To...", icon='DUPLICATE')
        op_copy.source_deck_idx = d_idx
        op_tween = row_deck_tools.operator("logicsub.tween_all_steps", text="Magic Tween", icon='IPO_BEZIER')
        op_tween.deck_idx = d_idx

        box_deck.prop(deck, "driven_object", text="Target")
        if deck.driven_object and deck.driven_object.type == 'ARMATURE':
            box_deck.prop_search(deck, "driven_bone", deck.driven_object.pose, "bones", text="", icon='BONE_DATA')

        active_mapping = get_active_mapping(s, d_idx, create=False)
        if not active_mapping:
            box_deck.operator("logicsub.init_mapping", text="Initialize Deck Mapping", icon='PLUS')
            return

        # --- PHYSICS ENGINE SETTINGS ---
        box_deck.prop(s, "logic_sub_show_physics", icon='PHYSICS', text="Elastomeric Physics", toggle=True)
        if s.logic_sub_show_physics:
            phys_box = box_deck.box()
            phys_box.prop(deck, "physics_domain", text="Domain")
            if deck.physics_domain == 'MECHANICAL': phys_box.prop(deck, "physics_matter", text="Material")
            
            p_row = phys_box.row(align=True)
            p_row.prop(deck, "mass")
            p_row.prop(deck, "drag")
            p_row.prop(deck, "spring_tension")
            
            col_box = phys_box.box()
            col_box.label(text="Kinematic Boundaries (No Touchy)", icon='CON_DISTLIMIT')
            col_box.prop(deck, "collider_target", text="Collider")
            if deck.collider_target and deck.collider_target.type == 'ARMATURE':
                col_box.prop_search(deck, "collider_bone", deck.collider_target.pose, "bones", text="", icon='BONE_DATA')
            col_box.prop(deck, "collider_margin", text="Base Margin")
            
            col_op = col_box.operator("logicsub.apply_no_touchy_math", text="Enforce Boundary", icon='SHIELD_OVERLAY')
            col_op.deck_idx = d_idx

        # --- 3. SCRUBBER & SYNC ---
        layout.separator()
        box_scrub = layout.box()
        box_scrub.label(text="Scrubber & Sync", icon='TIME')
        
        row_target = box_scrub.row(align=True)
        row_target.prop(active_mapping, "target_max", text="Trigger Max")
        row_target.prop(active_mapping, "substeps", text="Steps")
        
        row_scrubber = box_scrub.row(align=True)
        row_scrubber.prop(s, "logic_sub_full_scrubber", text="Scrub", slider=True)
        
        row_phase = box_scrub.row(align=True)
        row_phase.prop(active_mapping, "phase_offset", text="Phase Offset")
        row_phase.prop(active_mapping, "gear_ratio", text="Gear Ratio")
        
        row_global = box_scrub.row(align=True)
        row_global.operator("logicsub.capture_all_steps", text="Capture All", icon='RECORD_ON')
        row_global.operator("logicsub.clear_all_steps", text="Clear All", icon='TRASH')
        row_global.operator("logicsub.execute_backslide", text="Backslide Groove", icon='UV_SYNC_SELECT')

        row_drv = box_scrub.row(align=True)
        row_drv.operator("logicsub.generate_drivers", text="Compile Drivers", icon='SCRIPT')
        row_drv.operator("logicsub.auto_limit_bounds", text="Auto Bounds", icon='CON_LIMITROT').deck_idx = d_idx

        preview_icon = 'PAUSE' if getattr(s, "logic_sub_is_previewing", False) else 'PLAY'
        row_prev = box_scrub.row(align=True)
        row_prev.operator("logicsub.preview_play", text="Play Smoov'mnt", icon=preview_icon)
        row_prev.prop(s, "logic_sub_preview_mode", text="")
        row_prev.prop(s, "logic_sub_preview_scope", text="")
        row_prev.prop(s, "logic_sub_preview_fps", text="FPS")

        # --- 4. BATCH & MACROS ---
        layout.separator()
        b_box = layout.box()
        b_box.prop(s, "logic_sub_show_batcher", text="Batch Processing", icon='MOD_ARRAY', toggle=True)
        if s.logic_sub_show_batcher:
            b = s.logic_sub_batch
            b_box.operator("logicsub.batch_select_all", text="Select All", icon='CHECKBOX_HLT').state = True
            b_box.operator("logicsub.batch_select_all", text="Deselect All", icon='CHECKBOX_DEHLT').state = False
            
            b_box.prop(b, "operation", text="Op")
            if b.operation in ['SET', 'ADD']: b_box.prop(b, "is_progressive")
            
            col = b_box.column(align=True)
            r = col.row(align=True); r.prop(b, "use_loc_x", text="", icon='CHECKBOX_HLT' if b.use_loc_x else 'CHECKBOX_DEHLT'); r.prop(b, "val_loc_x", text="X"); r.prop(b, "use_loc_y", text="", icon='CHECKBOX_HLT' if b.use_loc_y else 'CHECKBOX_DEHLT'); r.prop(b, "val_loc_y", text="Y"); r.prop(b, "use_loc_z", text="", icon='CHECKBOX_HLT' if b.use_loc_z else 'CHECKBOX_DEHLT'); r.prop(b, "val_loc_z", text="Z")
            r2 = col.row(align=True); r2.prop(b, "use_rot_x", text="", icon='CHECKBOX_HLT' if b.use_rot_x else 'CHECKBOX_DEHLT'); r2.prop(b, "val_rot_x", text="rX"); r2.prop(b, "use_rot_y", text="", icon='CHECKBOX_HLT' if b.use_rot_y else 'CHECKBOX_DEHLT'); r2.prop(b, "val_rot_y", text="rY"); r2.prop(b, "use_rot_z", text="", icon='CHECKBOX_HLT' if b.use_rot_z else 'CHECKBOX_DEHLT'); r2.prop(b, "val_rot_z", text="rZ")
            r3 = col.row(align=True); r3.prop(b, "use_scl_x", text="", icon='CHECKBOX_HLT' if b.use_scl_x else 'CHECKBOX_DEHLT'); r3.prop(b, "val_scl_x", text="sX"); r3.prop(b, "use_scl_y", text="", icon='CHECKBOX_HLT' if b.use_scl_y else 'CHECKBOX_DEHLT'); r3.prop(b, "val_scl_y", text="sY"); r3.prop(b, "use_scl_z", text="", icon='CHECKBOX_HLT' if b.use_scl_z else 'CHECKBOX_DEHLT'); r3.prop(b, "val_scl_z", text="sZ")
            
            b_box.operator("logicsub.batch_apply", text="Apply Batch", icon='FILE_TICK')
            
            snap_box = b_box.box()
            snap_box.prop(b, "snap_target_obj", text="Batch Target Origin")
            snap_box.operator("logicsub.advanced_batch_snap", text="Execute Macro Snap", icon='PIVOT_CURSOR')

        # --- 5. DATA STEPS (DECKFLOW) ---
        layout.separator()
        box_steps = layout.box()
        box_steps.label(text="Substeps", icon='ALIGN_JUSTIFY')
        subs = max(1, active_mapping.substeps)
        for i in range(len(active_mapping.steps)):
            step_col = box_steps.column(align=True)
            if s.logic_sub_show_batcher:
                row_sel = step_col.row(align=True)
                row_sel.prop(active_mapping.steps[i], "is_selected_for_batch", text="", icon='CHECKBOX_HLT' if active_mapping.steps[i].is_selected_for_batch else 'CHECKBOX_DEHLT')
                step_box = row_sel.column(align=True)
            else:
                step_box = step_col
                
            draw_step_ui_with_deckflow(step_box, context, s, active_mapping, d_idx, i, subs)

        # --- 6. ACTION BAKER & TAGS ---
        layout.separator()
        box_tags = layout.box()
        row_tags_header = box_tags.row()
        row_tags_header.label(text="Tracks & Baker", icon='ACTION')
        row_tags_ops = row_tags_header.row(align=True)
        op_add_seg = row_tags_ops.operator("logicsub.add_tag", text="", icon='MARKER_HLT'); op_add_seg.tag_type = 'SEG'
        op_add_grp = row_tags_ops.operator("logicsub.add_tag", text="", icon='GROUP'); op_add_grp.tag_type = 'GROUPIE'

        for i, tag in enumerate(active_mapping.tags):
            tag_box = box_tags.box()
            header_row = tag_box.row(align=True)
            
            if tag.type == 'SEG': icon = 'MARKER'
            else: icon = 'TRIA_DOWN' if tag.is_expanded else 'TRIA_RIGHT'
            
            if tag.type == 'GROUPIE': header_row.prop(tag, "is_expanded", text="", icon=icon, emboss=False)
            header_row.prop(tag, "name", text="")
            
            if tag.type == 'SEG':
                header_row.prop(tag, "target_step", text="Step")
                header_row.prop(tag, "is_selected_for_bridge", text="", icon='LINKED')
            
            play_op = header_row.operator("logicsub.activate_tag", text="", icon='PLAY'); play_op.idx = i
            rem_op = header_row.operator("logicsub.remove_tag", text="", icon='X'); rem_op.idx = i
            
            if tag.type == 'GROUPIE' and tag.is_expanded:
                col = tag_box.column(align=True)
                col.prop(tag, "show_ghosting")
                col.prop(tag, "ease_type", text="Slope")
                op_smooth = col.operator("logicsub.smooth_groupie", text="Smooth Interp", icon='SMOOTH'); op_smooth.idx = i
                
                grid = col.grid_flow(row_major=True, columns=5, even_columns=True, even_rows=True, align=True)
                for j, gs in enumerate(tag.group_steps):
                    if j >= len(active_mapping.steps): continue
                    grid.prop(gs, "is_active", text=f"{j}", toggle=True)
                    
                bake_box = tag_box.box()
                bake_box.label(text="Action Baker", icon='ANIM_DATA')
                bake_box.prop(tag, "bake_mode", text="Mode")
                if tag.bake_mode in {'LOOP', 'PING_PONG'}: bake_box.prop(tag, "loop_count")
                bake_box.prop(tag, "frame_gap")
                bake_box.prop(tag, "time_warp", text="Warp")
                bake_box.prop(tag, "use_jitter")
                if tag.use_jitter: bake_box.prop(tag, "jitter_intensity")
                bake_box.prop(tag, "push_to_nla")
                
                bake_op = bake_box.operator("logicsub.bake_action", text="Bake to Action", icon='REC'); bake_op.idx = i

        bridge_row = box_tags.row()
        bridge_row.operator("logicsub.bridge_segs", text="Bridge Selected Segs", icon='NLA')


# -------------------------------------------------------
# REGISTRATION
# -------------------------------------------------------

classes = (
    LogicSubClipboard,
    LogicSubTrackedProp,
    LogicSubModConState,
    LogicSubDrivenStep,
    LogicSubTagStep,
    LogicSubTag,
    LogicSubMapping,
    LogicSubDeckItem,
    LogicSubBatchSettings,
    
    LOGICSUB_UL_deck_list,
    LOGICSUB_OT_move_deck,
    LOGICSUB_OT_apply_no_touchy_math,
    LOGICSUB_OT_execute_backslide,
    LOGICSUB_OT_copy_deck,
    LOGICSUB_OT_tween_all_steps,
    LOGICSUB_OT_generate_recoil,
    LOGICSUB_OT_copy_error,
    LOGICSUB_OT_add_deck,
    LOGICSUB_OT_remove_deck,
    LOGICSUB_OT_init_mapping,
    LOGICSUB_OT_toggle_nested_decks,
    LOGICSUB_OT_step_tool,
    LOGICSUB_OT_wand_snap,
    LOGICSUB_OT_isolate_target,
    LOGICSUB_OT_reset_step_transforms,
    LOGICSUB_OT_snapshot_step,
    LOGICSUB_OT_bridge_to_next,
    LOGICSUB_OT_exec,
    LOGICSUB_OT_exec_full,
    LOGICSUB_OT_play_to_step,
    LOGICSUB_OT_set_driven_step,
    LOGICSUB_OT_flip_step,
    LOGICSUB_OT_shuffle_channels,
    LOGICSUB_OT_copy_clipboard,
    LOGICSUB_OT_paste_clipboard,
    LOGICSUB_OT_copy_step,
    LOGICSUB_OT_quick_math_propagate,
    LOGICSUB_OT_add_tracked_prop,
    LOGICSUB_OT_remove_tracked_prop,
    LOGICSUB_OT_batch_select_all,
    LOGICSUB_OT_batch_apply,
    LOGICSUB_OT_advanced_batch_snap,
    LOGICSUB_OT_auto_limit_bounds,
    LOGICSUB_OT_bridge_segs,
    LOGICSUB_OT_bake_action,
    LOGICSUB_OT_add_tag,
    LOGICSUB_OT_remove_tag,
    LOGICSUB_OT_smooth_groupie,
    LOGICSUB_OT_activate_tag,
    LOGICSUB_OT_clear_all_steps,
    LOGICSUB_OT_capture_all_steps,
    LOGICSUB_OT_import_data,
    LOGICSUB_OT_export_data,
    LOGICSUB_OT_sync_text,
    LOGICSUB_OT_open_data,
    LOGICSUB_OT_reset_table,
    LOGICSUB_OT_open_log,
    LOGICSUB_OT_generate_drivers,
    LOGICSUB_OT_preview_play,
    
    VIEW3D_PT_logic_sub,
)

from bpy.app.handlers import persistent

@persistent
def depsgraph_update_handler(scene, depsgraph):
    if getattr(scene, "logic_sub_is_syncing", False):
        return
    pass

def register():
    for cls in classes: bpy.utils.register_class(cls)

    bpy.types.Scene.logic_sub_object = PointerProperty(type=bpy.types.Object, name="Trigger Object")
    bpy.types.Scene.logic_sub_bone_name = StringProperty(name="Trigger Bone")
    bpy.types.Scene.logic_sub_channel = EnumProperty(items=[
        ('LOC_X', "Loc X", ""), ('LOC_Y', "Loc Y", ""), ('LOC_Z', "Loc Z", ""),
        ('ROT_X', "Rot X", ""), ('ROT_Y', "Rot Y", ""), ('ROT_Z', "Rot Z", ""),
        ('SCL_X', "Scl X", ""), ('SCL_Y', "Scl Y", ""), ('SCL_Z', "Scl Z", "")], default='LOC_Z')
    bpy.types.Scene.logic_sub_direction = EnumProperty(items=[('POS', "Positive (+)", ""), ('NEG', "Negative (-)", "")], default='POS')
    
    bpy.types.Scene.logic_sub_inv_loc_x = BoolProperty(default=True); bpy.types.Scene.logic_sub_inv_loc_y = BoolProperty(default=True); bpy.types.Scene.logic_sub_inv_loc_z = BoolProperty(default=True)
    bpy.types.Scene.logic_sub_inv_rot_x = BoolProperty(default=True); bpy.types.Scene.logic_sub_inv_rot_y = BoolProperty(default=True); bpy.types.Scene.logic_sub_inv_rot_z = BoolProperty(default=True)
    bpy.types.Scene.logic_sub_inv_scl_x = BoolProperty(default=True); bpy.types.Scene.logic_sub_inv_scl_y = BoolProperty(default=True); bpy.types.Scene.logic_sub_inv_scl_z = BoolProperty(default=True)

    bpy.types.Scene.logic_sub_decks = CollectionProperty(type=LogicSubDeckItem)
    bpy.types.Scene.logic_sub_active_deck_idx = IntProperty(default=0, min=0)
    bpy.types.Scene.logic_sub_mappings = CollectionProperty(type=LogicSubMapping)
    
    bpy.types.Scene.logic_sub_clipboard = PointerProperty(type=LogicSubClipboard)
    bpy.types.Scene.logic_sub_batch = PointerProperty(type=LogicSubBatchSettings)
    bpy.types.Scene.logic_sub_show_batcher = BoolProperty(default=False)
    bpy.types.Scene.logic_sub_show_physics = BoolProperty(default=False)

    bpy.types.Scene.logic_sub_current_step = IntProperty(name="Substep", default=0, min=0, update=update_scrubber)
    bpy.types.Scene.logic_sub_full_scrubber = IntProperty(name="Full Scrubber", default=0, update=update_full_scrubber)

    bpy.types.Scene.logic_sub_is_syncing = BoolProperty(default=False)
    bpy.types.Scene.logic_sub_is_capturing = BoolProperty(default=False)

    bpy.types.Scene.logic_sub_is_previewing = BoolProperty(default=False)
    bpy.types.Scene.logic_sub_preview_mode = EnumProperty(items=[('PLAY', 'Play Once', ''), ('LOOP', 'Loop', ''), ('BOUNCE', 'Ping-Pong', '')], default='PLAY')
    bpy.types.Scene.logic_sub_preview_scope = EnumProperty(items=[('SINGLE', 'Active Direction Only', ''), ('FULL', 'Full Range (+/-)', '')], default='SINGLE')
    bpy.types.Scene.logic_sub_preview_fps = IntProperty(default=24, min=1)
    
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_handler)
    global _ls_draw_handler
    _ls_draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_ghost_arcs, (), 'WINDOW', 'POST_VIEW')

def unregister():
    for cls in reversed(classes): bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.logic_sub_object
    del bpy.types.Scene.logic_sub_bone_name
    del bpy.types.Scene.logic_sub_channel
    del bpy.types.Scene.logic_sub_direction
    
    del bpy.types.Scene.logic_sub_inv_loc_x; del bpy.types.Scene.logic_sub_inv_loc_y; del bpy.types.Scene.logic_sub_inv_loc_z
    del bpy.types.Scene.logic_sub_inv_rot_x; del bpy.types.Scene.logic_sub_inv_rot_y; del bpy.types.Scene.logic_sub_inv_rot_z
    del bpy.types.Scene.logic_sub_inv_scl_x; del bpy.types.Scene.logic_sub_inv_scl_y; del bpy.types.Scene.logic_sub_inv_scl_z
    
    del bpy.types.Scene.logic_sub_decks
    del bpy.types.Scene.logic_sub_active_deck_idx
    del bpy.types.Scene.logic_sub_mappings
    
    del bpy.types.Scene.logic_sub_clipboard
    del bpy.types.Scene.logic_sub_batch
    del bpy.types.Scene.logic_sub_show_batcher
    del bpy.types.Scene.logic_sub_show_physics
    
    del bpy.types.Scene.logic_sub_current_step
    del bpy.types.Scene.logic_sub_full_scrubber
    del bpy.types.Scene.logic_sub_is_syncing
    del bpy.types.Scene.logic_sub_is_capturing
    del bpy.types.Scene.logic_sub_is_previewing
    del bpy.types.Scene.logic_sub_preview_mode
    del bpy.types.Scene.logic_sub_preview_scope
    del bpy.types.Scene.logic_sub_preview_fps
    
    if depsgraph_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_handler)
    
    global _ls_draw_handler
    if _ls_draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_ls_draw_handler, 'WINDOW')
        _ls_draw_handler = None

if __name__ == "__main__":
    register()