"""Animate the construction site progression and render an MP4 video.

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/render_construction_anim.py

Reads art/construction_site.blend, adds a 9-second (216-frame @ 24fps) keyframed
animation from cleared lot + materials to completed wood-framed building, saves
the animated .blend, and encodes art/construction_site_anim.mp4.
"""

import math
import subprocess
import tempfile
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "art" / "construction_site.blend"
VIDEO_PATH = ROOT / "art" / "construction_site_anim.mp4"


def key_vis(obj, frame, visible):
    """Keyframe viewport and render visibility with constant interpolation."""
    hide = not visible
    obj.hide_viewport = hide
    obj.hide_render = hide
    obj.keyframe_insert(data_path="hide_viewport", frame=frame)
    obj.keyframe_insert(data_path="hide_render", frame=frame)


def key_crane(jib, trolley, cable, hook, frame, jib_deg, trolley_x, drop):
    """Keyframe crane jib slew, trolley radius, cable length, and hook height."""
    jib.rotation_euler.z = math.radians(jib_deg)
    jib.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)

    trolley.location.x = trolley_x
    trolley.keyframe_insert(data_path="location", index=0, frame=frame)

    cable.scale.z = drop
    cable.keyframe_insert(data_path="scale", index=2, frame=frame)

    hook.location.z = -0.16 - drop
    hook.keyframe_insert(data_path="location", index=2, frame=frame)


def set_vis_constant(obj):
    if not obj.animation_data or not obj.animation_data.action:
        return
    action = obj.animation_data.action
    # Blender 5.x layered actions or legacy fcurves
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

    # Look up articulated crane parts
    jib = bpy.data.objects["Crane_Jib"]
    trolley = bpy.data.objects["Crane_Trolley"]
    cable = bpy.data.objects["Crane_Cable"]
    hook = bpy.data.objects["Crane_Hook"]
    payload = bpy.data.objects["Crane_Payload_Frame"]

    # Look up building stages
    s1 = bpy.data.objects["Stage1_Foundation"]
    s2 = bpy.data.objects["Stage2_FloorDeck"]
    s3 = bpy.data.objects["Stage3_FirstFloorWalls"]
    s4 = bpy.data.objects["Stage4_UpperFrameAndGables"]
    s5 = bpy.data.objects["Stage5_RoofTrusses"]

    # Look up depletable material piles
    p_blocks = bpy.data.objects["Pile_ConcreteBlocks"]
    p_lumber1 = bpy.data.objects["Pile_LumberStack_1"]
    p_lumber2 = bpy.data.objects["Pile_LumberStack_2"]
    p_frames = bpy.data.objects["Pile_PrefabFrames"]

    all_animated = [jib, trolley, cable, hook, payload, s1, s2, s3, s4, s5,
                    p_blocks, p_lumber1, p_lumber2, p_frames]
    for obj in all_animated:
        obj.animation_data_clear()

    scene.frame_start = 1
    scene.frame_end = 216
    scene.render.fps = 24

    # Initial visibility at frame 1: empty building pad, all materials present, no payload on hook
    for st in (s1, s2, s3, s4, s5):
        key_vis(st, 1, False)
    for pile in (p_blocks, p_lumber1, p_lumber2, p_frames):
        key_vis(pile, 1, True)
    key_vis(payload, 1, False)

    # --- Choreography ---
    # 1. Establishing pause (f1..f10)
    key_crane(jib, trolley, cable, hook, 1,   -135.0, 4.2, 3.0)
    key_crane(jib, trolley, cable, hook, 10,  -135.0, 4.2, 3.0)

    # 2. Pick concrete blocks & pour foundation (f10..f42)
    key_crane(jib, trolley, cable, hook, 20,  -104.0, 7.5, 3.5)
    key_crane(jib, trolley, cable, hook, 25,  -104.0, 7.5, 7.6)
    key_vis(p_blocks, 26, False)
    key_crane(jib, trolley, cable, hook, 30,  -104.0, 7.5, 3.8)
    key_crane(jib, trolley, cable, hook, 39,   -14.0, 6.0, 4.2)
    key_crane(jib, trolley, cable, hook, 43,   -14.0, 6.0, 6.8)
    key_vis(s1, 43, True)

    # 3. Pick plywood/joists & build floor deck (f43..f74)
    key_crane(jib, trolley, cable, hook, 48,   -14.0, 6.0, 3.4)
    key_crane(jib, trolley, cable, hook, 58,   136.0, 4.7, 3.4)
    key_crane(jib, trolley, cable, hook, 62,   136.0, 4.7, 7.4)
    key_crane(jib, trolley, cable, hook, 66,   136.0, 4.7, 3.4)
    key_crane(jib, trolley, cable, hook, 72,   -12.0, 6.0, 3.8)
    key_crane(jib, trolley, cable, hook, 76,   -12.0, 6.0, 6.4)
    key_vis(s2, 76, True)

    # 4. Hero frame lift #1: Pick wall frame from rack -> erect 1st floor walls (f76..f122)
    key_crane(jib, trolley, cable, hook, 80,   -12.0, 6.0, 3.2)
    key_crane(jib, trolley, cable, hook, 90,  -113.0, 4.1, 3.2)
    key_crane(jib, trolley, cable, hook, 95,  -113.0, 4.1, 6.0)
    key_vis(payload, 95, True)
    key_crane(jib, trolley, cable, hook, 102, -113.0, 4.1, 2.0)
    key_crane(jib, trolley, cable, hook, 115,  -18.0, 6.2, 2.0)
    key_crane(jib, trolley, cable, hook, 121,  -18.0, 6.2, 4.5)
    key_vis(s3, 121, True)
    key_vis(payload, 121, False)
    key_vis(p_lumber1, 121, False)

    # 5. Hero frame lift #2: Pick upper frame -> erect ceiling joists & gables (f121..f162)
    key_crane(jib, trolley, cable, hook, 126,  -18.0, 6.2, 2.2)
    key_crane(jib, trolley, cable, hook, 136, -113.0, 4.1, 2.6)
    key_crane(jib, trolley, cable, hook, 141, -113.0, 4.1, 5.8)
    key_vis(payload, 141, True)
    key_crane(jib, trolley, cable, hook, 147, -113.0, 4.1, 1.5)
    key_crane(jib, trolley, cable, hook, 157,  -12.0, 6.4, 1.5)
    key_crane(jib, trolley, cable, hook, 162,  -12.0, 6.4, 2.9)
    key_vis(s4, 162, True)
    key_vis(payload, 162, False)
    key_vis(p_lumber2, 162, False)

    # 6. Roof truss lift: Pick final prefab frames -> install roof trusses (f162..f198)
    key_crane(jib, trolley, cable, hook, 166,  -12.0, 6.4, 1.6)
    key_crane(jib, trolley, cable, hook, 175, -113.0, 4.1, 2.4)
    key_crane(jib, trolley, cable, hook, 180, -113.0, 4.1, 5.8)
    key_vis(payload, 180, True)
    key_vis(p_frames, 180, False)
    key_crane(jib, trolley, cable, hook, 185, -113.0, 4.1, 1.2)
    key_crane(jib, trolley, cable, hook, 194,  -14.0, 6.0, 1.2)
    key_crane(jib, trolley, cable, hook, 198,  -14.0, 6.0, 2.1)
    key_vis(s5, 198, True)
    key_vis(payload, 198, False)

    # 7. Final park & hold to admire completed wood-framed building (f198..f216)
    key_crane(jib, trolley, cable, hook, 208,   20.0, 7.4, 2.4)
    key_crane(jib, trolley, cable, hook, 216,   20.0, 7.4, 2.4)

    for obj in (payload, s1, s2, s3, s4, s5, p_blocks, p_lumber1, p_lumber2, p_frames):
        set_vis_constant(obj)

    # Save animated .blend
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), compress=True)

    # Render frames fast with EEVEE (fall back to Cycles low samples if needed)
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

        # Encode to H.264 MP4 compatible with QuickTime & web players
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
