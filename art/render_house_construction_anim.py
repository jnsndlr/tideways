"""Animate the compact residential house construction site and render an MP4 video.

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/render_house_construction_anim.py

Reads art/house_construction_site.blend, adds a 10-second (240-frame @ 24fps)
keyframed animation featuring:
  - Spinning & tilting portable cement mixer + wheelbarrow foundation pour
  - Floor joists & plywood subfloor build
  - Signature tilt-up wood stud walls raised one-by-one by two animated builders
  - Rolling scaffold & stepladder moving into place for gables and roof trusses
  - Sequential roof trusses & cottage front porch gable framing

Saves the animated .blend and encodes art/house_construction_site_anim.mp4.
"""

import math
import subprocess
import tempfile
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "art" / "house_construction_site.blend"
VIDEO_PATH = ROOT / "art" / "house_construction_site_anim.mp4"

PAD_TOP = 0.16
Z_DECK_TOP = 0.76
Z_SCAF_DECK = PAD_TOP + 2.08


def key_vis(obj, frame, visible):
    hide = not visible
    obj.hide_viewport = hide
    obj.hide_render = hide
    obj.keyframe_insert(data_path="hide_viewport", frame=frame)
    obj.keyframe_insert(data_path="hide_render", frame=frame)


def key_loc(obj, frame, loc):
    obj.location = loc
    obj.keyframe_insert(data_path="location", frame=frame)


def key_rot(obj, frame, rot_deg):
    obj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def key_scale_z(obj, frame, sz):
    obj.scale.z = sz
    obj.keyframe_insert(data_path="scale", index=2, frame=frame)


def key_pop_rise(obj, start_frame, end_frame):
    """Show object at start_frame and smoothly rise in Z from 0.05 to 1.0."""
    key_vis(obj, start_frame, True)
    key_scale_z(obj, start_frame, 0.05)
    key_scale_z(obj, end_frame, 1.0)


def key_hammering(arm_r, f_start, f_end, step=4, low_deg=25.0, high_deg=115.0):
    """Oscillate worker's right arm to hammer."""
    toggle = False
    for f in range(f_start, f_end + 1, step):
        arm_r.rotation_euler.x = math.radians(high_deg if toggle else low_deg)
        arm_r.keyframe_insert(data_path="rotation_euler", index=0, frame=f)
        toggle = not toggle
    arm_r.rotation_euler.x = 0.0
    arm_r.keyframe_insert(data_path="rotation_euler", index=0, frame=f_end + 3)


def key_arms_push(arm_l, arm_r, f_start, f_end, angle_deg=110.0):
    """Raise both arms forward to push a tilt-up wall."""
    for arm in (arm_l, arm_r):
        arm.rotation_euler.x = math.radians(0.0)
        arm.keyframe_insert(data_path="rotation_euler", index=0, frame=f_start - 2)
        arm.rotation_euler.x = math.radians(angle_deg)
        arm.keyframe_insert(data_path="rotation_euler", index=0, frame=f_start + 2)
        arm.rotation_euler.x = math.radians(angle_deg + 25.0)
        arm.keyframe_insert(data_path="rotation_euler", index=0, frame=f_end - 2)
        arm.rotation_euler.x = math.radians(0.0)
        arm.keyframe_insert(data_path="rotation_euler", index=0, frame=f_end + 2)


def set_vis_constant(obj):
    if not obj.animation_data or not obj.animation_data.action:
        return
    action = obj.animation_data.action
    fcurves = []
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    fcurves.extend(bag.fcurves)
    elif hasattr(action, "fcurves"):
        fcurves.extend(action.fcurves)
    for fc in fcurves:
        if fc.data_path in ("hide_viewport", "hide_render"):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def build_animation():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_PATH))
    scene = bpy.context.scene

    # Building stages
    s1 = bpy.data.objects["Stage1_Foundation"]
    s2 = bpy.data.objects["Stage2_FloorDeck"]
    w_back = bpy.data.objects["Wall_Back"]
    w_left = bpy.data.objects["Wall_Left"]
    w_right = bpy.data.objects["Wall_Right"]
    w_front = bpy.data.objects["Wall_Front"]
    w_int = bpy.data.objects["Wall_InteriorAndPorch"]
    s4 = bpy.data.objects["Stage4_UpperFrameAndGables"]
    s5a = bpy.data.objects["Stage5a_TrussesLeft"]
    s5b = bpy.data.objects["Stage5b_TrussesRight"]
    s5c = bpy.data.objects["Stage5c_PorchRoof"]

    # Material piles & truck load
    p_bags = bpy.data.objects["Pile_ConcreteBags"]
    p_ply = bpy.data.objects["Pile_PlywoodSheets"]
    p_lumber = bpy.data.objects["Pile_LumberStack"]
    p_roof = bpy.data.objects["Pile_RoofLumber"]
    truck_load = bpy.data.objects["Truck_LumberLoad"]

    # Equipment
    mixer_tilt = bpy.data.objects["Mixer_Tilt"]
    mixer_drum = bpy.data.objects["Mixer_Drum"]
    wb = bpy.data.objects["Wheelbarrow"]
    wb_conc = bpy.data.objects["Wheelbarrow_Concrete"]
    ladder = bpy.data.objects["Stepladder"]
    scaf = bpy.data.objects["Scaffold"]

    # Workers
    w1 = bpy.data.objects["Worker_1"]
    w1_al = bpy.data.objects["Worker_1_ArmL"]
    w1_ar = bpy.data.objects["Worker_1_ArmR"]
    w2 = bpy.data.objects["Worker_2"]
    w2_al = bpy.data.objects["Worker_2_ArmL"]
    w2_ar = bpy.data.objects["Worker_2_ArmR"]

    all_stages = [s1, s2, w_back, w_left, w_right, w_front, w_int, s4, s5a, s5b, s5c]
    all_piles = [p_bags, p_ply, p_lumber, p_roof, truck_load]
    all_animated = all_stages + all_piles + [
        mixer_tilt, mixer_drum, wb, wb_conc, ladder, scaf,
        w1, w1_al, w1_ar, w2, w2_al, w2_ar,
    ]
    for obj in all_animated:
        obj.animation_data_clear()

    scene.frame_start = 1
    scene.frame_end = 240
    scene.render.fps = 24

    # ------------------------------------------------------------------
    # Frame 1: Initial cleared lot state
    # ------------------------------------------------------------------
    for st in all_stages:
        key_vis(st, 1, False)
        key_scale_z(st, 1, 1.0)
    for pile in all_piles:
        key_vis(pile, 1, True)
    key_vis(wb_conc, 1, False)

    # Initial wall flat poses (hidden until each wall tilts up)
    key_rot(w_back, 1, (90.0, 0.0, 0.0))
    key_rot(w_left, 1, (0.0, 90.0, 0.0))
    key_rot(w_right, 1, (0.0, -90.0, 0.0))
    key_rot(w_front, 1, (-90.0, 0.0, 0.0))

    # Equipment initial transforms
    key_rot(mixer_tilt, 1, (-28.0, 0.0, 0.0))
    key_rot(mixer_drum, 1, (0.0, 0.0, 0.0))
    key_loc(wb, 1, (1.40, -2.90, PAD_TOP))
    key_rot(wb, 1, (0.0, 0.0, 0.0))
    key_loc(ladder, 1, (-2.85, -1.65, PAD_TOP))
    key_loc(scaf, 1, (4.55, 1.65, PAD_TOP))

    # Workers initial poses
    key_loc(w1, 1, (0.90, -3.20, PAD_TOP))
    key_rot(w1, 1, (0.0, 0.0, -30.0))
    key_loc(w2, 1, (3.15, -2.50, PAD_TOP))
    key_rot(w2, 1, (0.0, 0.0, 75.0))
    for arm in (w1_al, w1_ar, w2_al, w2_ar):
        key_rot(arm, 1, (0.0, 0.0, 0.0))

    # ------------------------------------------------------------------
    # Phase 1 (f10..f48): Concrete Mixing & Foundation Pour
    # ------------------------------------------------------------------
    # Spin cement mixer drum rapidly during mixing & pouring
    key_rot(mixer_drum, 10, (0.0, 0.0, 0.0))
    key_rot(mixer_drum, 46, (0.0, 0.0, 1440.0))  # 4 full rotations

    # Tilt mixer to dump concrete into wheelbarrow
    key_rot(mixer_tilt, 16, (-28.0, 0.0, 0.0))
    key_rot(mixer_tilt, 22, (-78.0, 0.0, 0.0))
    key_vis(wb_conc, 22, True)
    key_vis(p_bags, 22, False)
    key_rot(mixer_tilt, 28, (-28.0, 0.0, 0.0))

    # Worker 1 pushes loaded wheelbarrow up to the foundation pad
    key_loc(w1, 22, (1.40, -3.65, PAD_TOP))
    key_rot(w1, 22, (0.0, 0.0, 0.0))
    key_loc(wb, 23, (1.40, -2.90, PAD_TOP))
    key_loc(wb, 32, (1.40, -1.90, PAD_TOP))
    key_loc(w1, 32, (1.40, -2.65, PAD_TOP))
    # Tip wheelbarrow to pour
    key_rot(wb, 32, (0.0, 0.0, 0.0))
    key_rot(wb, 35, (-22.0, 0.0, 0.0))
    key_vis(wb_conc, 36, False)
    key_rot(wb, 39, (0.0, 0.0, 0.0))

    # Foundation rises smoothly into place
    key_pop_rise(s1, 34, 44)

    # Pull wheelbarrow back to park
    key_loc(wb, 47, (1.40, -2.90, PAD_TOP))
    key_loc(w1, 47, (0.65, -3.10, PAD_TOP))

    # ------------------------------------------------------------------
    # Phase 2 (f48..f74): Floor Joists & Plywood Subfloor Deck
    # ------------------------------------------------------------------
    key_loc(w1, 54, (-1.20, -1.85, PAD_TOP))
    key_rot(w1, 54, (0.0, 0.0, -10.0))
    key_loc(w2, 54, (2.20, -1.85, PAD_TOP))
    key_rot(w2, 54, (0.0, 0.0, 15.0))
    key_hammering(w1_ar, 54, 70, step=4)
    key_hammering(w2_ar, 55, 71, step=4)

    key_vis(p_ply, 58, False)
    key_pop_rise(s2, 58, 68)

    # ------------------------------------------------------------------
    # Phase 3 (f74..f144): Signature Tilt-Up Wall Framing!
    # ------------------------------------------------------------------
    key_vis(truck_load, 75, False)

    # 3a. Back Wall tilt-up (f76..f92): workers step onto subfloor deck
    key_loc(w1, 75, (-0.80, 1.55, Z_DECK_TOP))
    key_rot(w1, 75, (0.0, 0.0, 0.0))
    key_loc(w2, 75, (1.40, 1.55, Z_DECK_TOP))
    key_rot(w2, 75, (0.0, 0.0, 0.0))

    key_vis(w_back, 76, True)
    key_rot(w_back, 78, (90.0, 0.0, 0.0))
    key_rot(w_back, 91, (0.0, 0.0, 0.0))
    key_arms_push(w1_al, w1_ar, 78, 91)
    key_arms_push(w2_al, w2_ar, 78, 91)
    key_loc(w1, 91, (-0.80, 2.20, Z_DECK_TOP))
    key_loc(w2, 91, (1.40, 2.20, Z_DECK_TOP))

    # 3b. Left Wall tilt-up (f94..f108)
    key_loc(w1, 95, (-1.20, 0.15, Z_DECK_TOP))
    key_rot(w1, 95, (0.0, 0.0, 90.0))
    key_loc(w2, 95, (-1.20, 1.50, Z_DECK_TOP))
    key_rot(w2, 95, (0.0, 0.0, 90.0))

    key_vis(w_left, 94, True)
    key_rot(w_left, 96, (0.0, 90.0, 0.0))
    key_rot(w_left, 107, (0.0, 0.0, 0.0))
    key_arms_push(w1_al, w1_ar, 96, 107)
    key_arms_push(w2_al, w2_ar, 96, 107)
    key_loc(w1, 107, (-1.90, 0.15, Z_DECK_TOP))
    key_loc(w2, 107, (-1.90, 1.50, Z_DECK_TOP))

    # 3c. Right Wall tilt-up (f108..f122)
    key_loc(w1, 110, (1.80, 0.15, Z_DECK_TOP))
    key_rot(w1, 110, (0.0, 0.0, -90.0))
    key_loc(w2, 110, (1.80, 1.50, Z_DECK_TOP))
    key_rot(w2, 110, (0.0, 0.0, -90.0))

    key_vis(w_right, 108, True)
    key_rot(w_right, 110, (0.0, -90.0, 0.0))
    key_rot(w_right, 121, (0.0, 0.0, 0.0))
    key_arms_push(w1_al, w1_ar, 110, 121)
    key_arms_push(w2_al, w2_ar, 110, 121)
    key_loc(w1, 121, (2.45, 0.15, Z_DECK_TOP))
    key_loc(w2, 121, (2.45, 1.50, Z_DECK_TOP))
    key_vis(p_lumber, 118, False)

    # 3d. Front Wall tilt-up (f122..f138)
    key_loc(w1, 124, (-0.75, 0.25, Z_DECK_TOP))
    key_rot(w1, 124, (0.0, 0.0, 180.0))
    key_loc(w2, 124, (1.35, 0.25, Z_DECK_TOP))
    key_rot(w2, 124, (0.0, 0.0, 180.0))

    key_vis(w_front, 122, True)
    key_rot(w_front, 124, (-90.0, 0.0, 0.0))
    key_rot(w_front, 137, (0.0, 0.0, 0.0))
    key_arms_push(w1_al, w1_ar, 124, 137)
    key_arms_push(w2_al, w2_ar, 124, 137)
    key_loc(w1, 137, (-0.75, -0.55, Z_DECK_TOP))
    key_loc(w2, 137, (1.35, -0.55, Z_DECK_TOP))

    # 3e. Interior partition & front porch posts pop in
    key_pop_rise(w_int, 139, 145)

    # ------------------------------------------------------------------
    # Phase 4 (f145..f178): Rolling Scaffold, Ceiling Joists & Gable Ends
    # ------------------------------------------------------------------
    # Roll scaffold up against the right wall & move stepladder near front-left
    key_loc(scaf, 144, (4.55, 1.65, PAD_TOP))
    key_loc(scaf, 156, (3.95, 0.85, PAD_TOP))
    key_loc(ladder, 144, (-2.85, -1.65, PAD_TOP))
    key_loc(ladder, 154, (-2.35, -1.75, PAD_TOP))

    # Worker 1 steps out to front porch; Worker 2 climbs onto scaffold deck
    key_loc(w1, 152, (-1.65, -2.15, PAD_TOP))
    key_rot(w1, 152, (0.0, 0.0, -25.0))
    key_loc(w2, 157, (3.95, 0.85, Z_SCAF_DECK))
    key_rot(w2, 157, (0.0, 0.0, 90.0))

    key_hammering(w1_ar, 156, 174, step=4)
    key_hammering(w2_ar, 158, 176, step=4)

    key_pop_rise(s4, 160, 170)

    # ------------------------------------------------------------------
    # Phase 5 (f178..f214): Sequential Roof Trusses & Cottage Porch Gable
    # ------------------------------------------------------------------
    key_vis(p_roof, 180, False)

    # Left half of roof trusses
    key_pop_rise(s5a, 180, 190)
    key_hammering(w1_ar, 180, 196, step=4)

    # Right half of roof trusses + fascia & purlins
    key_pop_rise(s5b, 192, 202)
    key_hammering(w2_ar, 182, 206, step=4)

    # Front porch gable roof
    key_loc(w1, 200, (-0.55, -2.55, PAD_TOP))
    key_rot(w1, 200, (0.0, 0.0, 10.0))
    key_pop_rise(s5c, 204, 212)
    key_hammering(w1_ar, 200, 212, step=4)

    # ------------------------------------------------------------------
    # Phase 6 (f214..f240): Roll Scaffold Back & Celebrate Completed Frame
    # ------------------------------------------------------------------
    key_loc(w2, 216, (3.45, -1.45, PAD_TOP))
    key_rot(w2, 216, (0.0, 0.0, 145.0))
    key_loc(scaf, 214, (3.95, 0.85, PAD_TOP))
    key_loc(scaf, 224, (4.55, 1.65, PAD_TOP))
    key_loc(w1, 220, (-0.85, -2.85, PAD_TOP))
    key_rot(w1, 220, (0.0, 0.0, 155.0))

    # Small celebratory wave at the end!
    for arm in (w1_al, w2_al):
        key_rot(arm, 222, (0.0, 0.0, 0.0))
        key_rot(arm, 226, (150.0, 0.0, 0.0))
        key_rot(arm, 232, (130.0, 0.0, 0.0))
        key_rot(arm, 238, (150.0, 0.0, 0.0))

    # Ensure crisp constant interpolation on all visibility tracks
    for obj in all_stages + all_piles + [wb_conc]:
        set_vis_constant(obj)

    # Save animated .blend
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), compress=True)

    # Render fast with EEVEE (fall back to Cycles if unavailable)
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = engine
            print(f"Using render engine: {engine}")
            break
        except TypeError:
            continue

    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 12
        scene.cycles.use_denoising = True
    else:
        if hasattr(scene, "eevee"):
            scene.eevee.taa_render_samples = 16

    scene.render.resolution_x = 960
    scene.render.resolution_y = 680
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    with tempfile.TemporaryDirectory() as tmpdir:
        scene.render.filepath = str(Path(tmpdir) / "frame_")
        bpy.ops.render.render(animation=True)

        cmd = [
            "ffmpeg", "-y",
            "-framerate", "24",
            "-i", str(Path(tmpdir) / "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            "-movflags", "+faststart",
            str(VIDEO_PATH),
        ]
        subprocess.run(cmd, check=True)

    print(f"Saved animation video: {VIDEO_PATH}")


if __name__ == "__main__":
    build_animation()
