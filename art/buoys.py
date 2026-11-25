"""Builds navigational buoys and fixed channel markers for Tideways.

Generates procedural weathered PBR textures (faded maritime paint, rust streaks,
salt/brine concrete, oxidized bronze, solar cell grid), builds six game-ready
models in Blender, saves the editable source .blend, and exports one .glb per
asset with embedded materials and marker empties (BeaconLight, MooringEye).

Run headless:
    Blender --background --python art/buoys.py
    Blender --background --python art/buoys.py -- --render /tmp/buoys_preview
    Blender --background --python art/buoys.py -- --high

Outputs:
    art/buoys.blend
    art/buoys_textures/*.png
    assets/models/buoys/buoy_port_can.glb
    assets/models/buoys/buoy_starboard_nun.glb
    assets/models/buoys/buoy_bell_tower.glb
    assets/models/buoys/buoy_hazard_spar.glb
    assets/models/buoys/marker_channel_port.glb
    assets/models/buoys/marker_channel_starboard.glb
    assets/models/buoys/buoy_traffic_separation.glb

Frame:
    Blender Z-up, metres (glTF export maps to Godot Y-up, Blender -Y -> Godot +Z).
    - Buoys: origin (0, 0, 0) at the waterline; submerged ballast skirt, keel,
      and anchor chain stub extend below Z = 0.
    - Channel markers: origin (0, 0, 0) at waterline/mudline; driven pilings
      extend to Z = -1.1 m for clean embedding on sloped shorelines/shoals.
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Matrix, Vector

ROOT = (
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if "__file__" in globals()
    else "/Users/jon/Documents/GitHub/tideways"
)
OUT_DIR = os.path.join(ROOT, "assets", "models", "buoys")
TEX_DIR = os.path.join(ROOT, "art", "buoys_textures")
BLEND_PATH = os.path.join(ROOT, "art", "buoys.blend")
SCENE_NAME = "NavBuoys"
TEX_PX = 512
UV_TILE_M = 2.0  # 1.0 UV unit = 2.0 metres
HIGH_DETAIL = False  # Default game-ready ~34% tri budget; pass --high for showcase subdivisions


# ------------------------------------------------------------------ noise & textures

def _np():
    import numpy as np
    return np


def smoothstep(x, a, b):
    np = _np()
    t = np.clip((x - a) / max(b - a, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def tile_noise2(px, cx, cy, seed):
    """Seamless tiling 2D value noise with independent X/Y frequencies."""
    np = _np()
    rng = np.random.default_rng(seed)
    lat = rng.random((cy, cx), dtype=np.float32)
    tx = np.arange(px, dtype=np.float32) * cx / px
    ty = np.arange(px, dtype=np.float32) * cy / px
    x0 = np.floor(tx).astype(np.int32)
    y0 = np.floor(ty).astype(np.int32)
    fx = tx - x0
    fy = ty - y0
    fx = fx * fx * (3.0 - 2.0 * fx)
    fy = fy * fy * (3.0 - 2.0 * fy)
    x1 = (x0 + 1) % cx
    y1 = (y0 + 1) % cy
    x0 %= cx
    y0 %= cy
    a = lat[np.ix_(y0, x0)]
    b = lat[np.ix_(y0, x1)]
    c = lat[np.ix_(y1, x0)]
    d = lat[np.ix_(y1, x1)]
    fx = fx[None, :]
    fy = fy[:, None]
    return (a * (1.0 - fx) + b * fx) * (1.0 - fy) + (c * (1.0 - fx) + d * fx) * fy


def fbm(px, cells, octaves, seed):
    np = _np()
    out = np.zeros((px, px), dtype=np.float32)
    amp = 0.5
    norm = 0.0
    for k in range(octaves):
        out += tile_noise2(px, cells << k, cells << k, seed + k * 17) * amp
        norm += amp
        amp *= 0.5
    return out / norm


def normal_from_height(h, strength=4.0):
    np = _np()
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5 * strength
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5 * strength
    nx = -dx
    ny = dy
    nz = np.ones_like(h)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([(nx * inv) * 0.5 + 0.5, (ny * inv) * 0.5 + 0.5, (nz * inv) * 0.5 + 0.5], axis=-1)


def save_tex(name, rgb, non_color=False):
    np = _np()
    h, w = rgb.shape[:2]
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    buf = np.ones((h, w, 4), dtype=np.float32)
    buf[..., : rgb.shape[2]] = np.clip(rgb, 0.0, 1.0)
    img.pixels.foreach_set(buf[::-1].ravel())
    os.makedirs(TEX_DIR, exist_ok=True)
    path = os.path.join(TEX_DIR, name + ".png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return path


def generate_textures():
    """Generates shared weathered marine PBR textures into assets/world/buoys/textures/."""
    np = _np()
    P = TEX_PX
    paths = {}

    # Shared marine paint wear mask: vertical rust streaks, chipped edges, dust/salt haze.
    streak = tile_noise2(P, 48, 3, 201) * 0.6 + tile_noise2(P, 96, 6, 203) * 0.4
    streak_len = smoothstep(tile_noise2(P, 10, 4, 205), 0.35, 0.75)
    runs = smoothstep(streak, 0.58, 0.76) * streak_len
    big = fbm(P, 4, 4, 211)
    mid = fbm(P, 12, 4, 213)
    fine = fbm(P, 40, 3, 215)
    grime = fbm(P, 6, 3, 217)

    raw = big * 0.55 + mid * 0.30 + fine * 0.15
    patch = smoothstep(raw, 0.63, 0.68)
    chips = smoothstep(mid * 0.45 + fine * 0.55, 0.71, 0.74)
    bare = np.maximum(patch, chips)
    halo = smoothstep(raw, 0.54, 0.63) * (1.0 - patch)

    rust_dark = np.array((0.24, 0.11, 0.06))
    rust_bright = np.array((0.52, 0.25, 0.11))
    rt = smoothstep(fine * 0.6 + mid * 0.4, 0.38, 0.64)[..., None]
    rust_col = rust_dark * (1.0 - rt) + rust_bright * rt
    stain_col = np.array((0.44, 0.22, 0.10))
    salt_dust = np.array((0.76, 0.66, 0.54))

    paint_tints = {
        "buoy_green": (0.12, 0.46, 0.32),
        "buoy_red": (0.64, 0.15, 0.11),
        "buoy_yellow": (0.86, 0.65, 0.13),
        "buoy_cream": (0.85, 0.81, 0.71),
        "buoy_charcoal": (0.17, 0.18, 0.20),
    }
    for name, tint in paint_tints.items():
        base = np.array(tint) * (0.90 + 0.14 * fine[..., None]) * (1.0 - 0.14 * grime[..., None])
        s_mix = np.clip(runs * 0.70 + halo * 0.42, 0.0, 0.85)[..., None]
        col = base * (1.0 - s_mix) + stain_col * s_mix
        d_mix = smoothstep(grime * 0.6 + big * 0.4, 0.52, 0.80)[..., None] * 0.20
        col = col * (1.0 - d_mix) + salt_dust * d_mix
        b_mix = bare[..., None] * 0.88
        col = col * (1.0 - b_mix) + rust_col * b_mix
        paths[name + "_albedo"] = save_tex(name + "_albedo", col, False)

    paint_h = (1.0 - bare) * 0.65 + fine * 0.20 + mid * 0.15 - runs * 0.06
    paths["paint_normal"] = save_tex("buoy_paint_normal", normal_from_height(paint_h, 4.5), True)
    paint_orm = np.stack(
        [
            0.84 + 0.16 * (1.0 - bare),
            np.clip(0.52 + 0.34 * bare + 0.14 * runs + 0.08 * grime, 0.0, 1.0),
            np.clip(0.08 + 0.22 * bare, 0.0, 1.0),
        ],
        axis=-1,
    )
    paths["paint_orm"] = save_tex("buoy_paint_orm", paint_orm, True)

    # Heavy corroded iron / steel rust (submerged skirts, chains, collars, bolts).
    r_big = fbm(P, 5, 4, 301)
    r_mid = fbm(P, 16, 4, 307)
    r_fine = fbm(P, 48, 3, 313)
    steel_show = smoothstep(r_mid * 0.5 + r_fine * 0.5, 0.66, 0.74)
    salt_crust = smoothstep(r_big * 0.6 + r_fine * 0.4, 0.68, 0.78) * 0.45
    r_t = smoothstep(r_big * 0.5 + r_fine * 0.5, 0.32, 0.68)[..., None]
    r_col = np.array((0.20, 0.09, 0.05)) * (1.0 - r_t) + np.array((0.48, 0.22, 0.10)) * r_t
    r_col = r_col * (1.0 - steel_show[..., None]) + np.array((0.36, 0.35, 0.34)) * steel_show[..., None]
    r_col = r_col * (1.0 - salt_crust[..., None]) + np.array((0.76, 0.71, 0.62)) * salt_crust[..., None]
    paths["buoy_rust_albedo"] = save_tex("buoy_rust_albedo", r_col, False)
    paths["buoy_rust_normal"] = save_tex(
        "buoy_rust_normal", normal_from_height(r_mid * 0.5 + r_fine * 0.5, 5.5), True
    )
    r_orm = np.stack(
        [
            0.78 + 0.22 * r_mid,
            np.clip(0.84 - 0.35 * steel_show + 0.1 * salt_crust, 0.25, 0.96),
            np.clip(0.22 + 0.55 * steel_show - 0.2 * salt_crust, 0.0, 0.9),
        ],
        axis=-1,
    )
    paths["buoy_rust_orm"] = save_tex("buoy_rust_orm", r_orm, True)

    # Brine-crusted weathered concrete piling.
    c_big = fbm(P, 5, 4, 401)
    c_mid = fbm(P, 18, 4, 407)
    c_fine = fbm(P, 54, 3, 413)
    pits = smoothstep(c_fine * 0.6 + c_mid * 0.4, 0.68, 0.76)
    c_salt = smoothstep(c_big * 0.65 + c_mid * 0.35, 0.58, 0.74)
    c_col = np.array((0.56, 0.52, 0.46)) * (0.86 + 0.24 * c_mid[..., None])
    c_col = c_col * (1.0 - c_salt[..., None] * 0.48) + np.array((0.83, 0.80, 0.73)) * (c_salt[..., None] * 0.48)
    c_col *= 1.0 - 0.25 * pits[..., None]
    paths["buoy_concrete_albedo"] = save_tex("buoy_concrete_albedo", c_col, False)
    paths["buoy_concrete_normal"] = save_tex(
        "buoy_concrete_normal", normal_from_height(c_mid * 0.45 + c_fine * 0.35 - pits * 0.35, 5.0), True
    )
    c_orm = np.stack([0.82 + 0.18 * (1.0 - pits), np.full((P, P), 0.92), np.zeros((P, P))], axis=-1)
    paths["buoy_concrete_orm"] = save_tex("buoy_concrete_orm", c_orm, True)

    # Oxidized bronze with subtle verdigris patina (bell).
    b_mid = fbm(P, 10, 4, 501)
    b_fine = fbm(P, 36, 3, 509)
    patina = smoothstep(b_mid * 0.65 + b_fine * 0.35, 0.56, 0.72)
    b_col = np.array((0.58, 0.44, 0.22)) * (0.88 + 0.20 * b_fine[..., None])
    b_col = b_col * (1.0 - patina[..., None] * 0.72) + np.array((0.24, 0.46, 0.38)) * (patina[..., None] * 0.72)
    paths["buoy_bronze_albedo"] = save_tex("buoy_bronze_albedo", b_col, False)
    b_orm = np.stack(
        [
            0.88 + 0.12 * b_fine,
            np.clip(0.32 + 0.44 * patina, 0.2, 0.85),
            np.clip(0.86 - 0.65 * patina, 0.1, 0.95),
        ],
        axis=-1,
    )
    paths["buoy_bronze_normal"] = save_tex(
        "buoy_bronze_normal", normal_from_height(b_fine * 0.6 + b_mid * 0.4, 1.8), True
    )
    paths["buoy_bronze_orm"] = save_tex("buoy_bronze_orm", b_orm, True)

    # Gridded photovoltaic solar panel texture (mapped 0..1 on panel face).
    u = np.linspace(0.0, 1.0, P, dtype=np.float32)
    v = np.linspace(0.0, 1.0, P, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)
    cols_n, rows_n = 4, 6
    gx = np.abs(((uu * cols_n) % 1.0) - 0.5)
    gy = np.abs(((vv * rows_n) % 1.0) - 0.5)
    cell_gap = (gx > 0.465) | (gy > 0.465)
    busbar = (np.abs(((uu * cols_n * 2.0) % 1.0) - 0.5) < 0.025) & (~cell_gap)
    dust_s = smoothstep(fbm(P, 8, 3, 601), 0.58, 0.84) * 0.25
    cell_var = tile_noise2(P, cols_n, rows_n, 607) * 0.04
    s_col = np.zeros((P, P, 3), dtype=np.float32)
    s_col[..., 0] = 0.05 + cell_var
    s_col[..., 1] = 0.10 + cell_var * 1.4
    s_col[..., 2] = 0.24 + cell_var * 2.2
    s_col[busbar] = (0.48, 0.52, 0.58)
    s_col[cell_gap] = (0.76, 0.78, 0.78)
    s_col = s_col * (1.0 - dust_s[..., None]) + np.array((0.68, 0.52, 0.38)) * dust_s[..., None]
    paths["buoy_solar_albedo"] = save_tex("buoy_solar_albedo", s_col, False)
    s_orm = np.stack(
        [
            np.ones((P, P)),
            np.where(cell_gap, 0.45, 0.16 + dust_s * 0.6),
            np.where(busbar, 0.85, np.where(cell_gap, 0.2, 0.35)),
        ],
        axis=-1,
    )
    paths["buoy_solar_orm"] = save_tex("buoy_solar_orm", s_orm, True)

    # Dark oxide/maroon antifouling boot-top & waterline hull paint.
    af_big = fbm(P, 5, 4, 701)
    af_mid = fbm(P, 16, 4, 709)
    af_fine = fbm(P, 44, 3, 719)
    af_algae = smoothstep(af_big * 0.6 + af_mid * 0.4, 0.56, 0.74) * 0.42
    af_salt = smoothstep(af_mid * 0.55 + af_fine * 0.45, 0.68, 0.80) * 0.30
    af_base = np.array((0.23, 0.085, 0.065)) * (0.82 + 0.28 * af_fine[..., None])
    af_col = af_base * (1.0 - af_algae[..., None]) + np.array((0.12, 0.14, 0.08)) * af_algae[..., None]
    af_col = af_col * (1.0 - af_salt[..., None]) + np.array((0.52, 0.46, 0.38)) * af_salt[..., None]
    paths["buoy_antifouling_albedo"] = save_tex("buoy_antifouling_albedo", af_col, False)
    af_orm = np.stack(
        [
            0.80 + 0.20 * af_mid,
            np.clip(0.76 + 0.16 * af_salt - 0.10 * af_algae, 0.45, 0.96),
            np.full((P, P), 0.08),
        ],
        axis=-1,
    )
    paths["buoy_antifouling_orm"] = save_tex("buoy_antifouling_orm", af_orm, True)

    # Weathered yellow upper daymark panel with crisp dark-charcoal "SC" lettering.
    # Coordinate frame matches 0..1 UVs: x=0 left..1 right, y=0 bottom..1 top (row 0 = top).
    gx_u = np.linspace(0.0, 1.0, P, dtype=np.float32)
    gy_v = np.linspace(1.0, 0.0, P, dtype=np.float32)
    uu_sc, vv_sc = np.meshgrid(gx_u, gy_v)

    def _sd_arc(px, py, cx, cy, rx, ry, a0_deg, a1_deg):
        # Distance to an elliptical arc approximated in normalized ellipse space.
        dx = (px - cx) / rx
        dy = (py - cy) / ry
        a0 = math.radians(a0_deg)
        a1 = math.radians(a1_deg)
        amid = 0.5 * (a0 + a1)
        ahalf = 0.5 * abs(a1 - a0)
        ang = np.arctan2(dy, dx)
        rel = (ang - amid + math.pi) % math.tau - math.pi
        clamped = np.clip(rel, -ahalf, ahalf) + amid
        qx = cx + rx * np.cos(clamped)
        qy = cy + ry * np.sin(clamped)
        return np.hypot(px - qx, py - qy)

    def _sd_seg(px, py, x0, y0, x1, y1):
        vx, vy = x1 - x0, y1 - y0
        l2 = max(vx * vx + vy * vy, 1e-8)
        t = np.clip(((px - x0) * vx + (py - y0) * vy) / l2, 0.0, 1.0)
        return np.hypot(px - (x0 + t * vx), py - (y0 + t * vy))

    # Bold USCG-style sans-serif "S" (left) and "C" (right) centered on panel.
    stroke_r = 0.039
    # "S" centered around x = 0.355, y = 0.52 (upright USCG Gothic proportions)
    sx, sy = 0.355, 0.52
    srx, sry = 0.108, 0.118
    d_s_top = _sd_arc(uu_sc, vv_sc, sx, sy + sry, srx, sry, 24.0, 270.0)
    d_s_bot = _sd_arc(uu_sc, vv_sc, sx, sy - sry, srx, sry, -156.0, 90.0)
    d_s = np.minimum(d_s_top, d_s_bot)

    # "C" centered around x = 0.665, y = 0.52 (matching height & stroke)
    cx_c, cy_c = 0.665, 0.52
    crx, cry = 0.112, 0.125
    c_stem_half = 0.111
    d_c_top = _sd_arc(uu_sc, vv_sc, cx_c, cy_c + c_stem_half, crx, cry, 26.0, 180.0)
    d_c_bot = _sd_arc(uu_sc, vv_sc, cx_c, cy_c - c_stem_half, crx, cry, 180.0, 334.0)
    d_c_left = _sd_seg(uu_sc, vv_sc, cx_c - crx, cy_c - c_stem_half, cx_c - crx, cy_c + c_stem_half)
    d_c = np.minimum(np.minimum(d_c_top, d_c_bot), d_c_left)

    d_letters = np.minimum(d_s, d_c)
    letter_mask = 1.0 - smoothstep(d_letters, stroke_r - 0.005, stroke_r + 0.005)

    # Build weathered yellow base matching buoy_yellow, plus subtle top grime/guano & paint fade on letters.
    sc_base = np.array(paint_tints["buoy_yellow"]) * (0.90 + 0.14 * fine[..., None]) * (1.0 - 0.14 * grime[..., None])
    letter_col = np.array((0.14, 0.15, 0.16)) * (0.92 + 0.12 * fine[..., None])
    letter_wear = np.clip(letter_mask * (0.92 - 0.18 * smoothstep(mid, 0.55, 0.80)), 0.0, 1.0)[..., None]
    sc_col = sc_base * (1.0 - letter_wear) + letter_col * letter_wear
    # Apply the same rust streaks, salt haze, and chipped bare metal spots over both paint & lettering
    s_mix = np.clip(runs * 0.55 + halo * 0.34, 0.0, 0.78)[..., None]
    sc_col = sc_col * (1.0 - s_mix) + stain_col * s_mix
    # Subtle coastal salt/guano streak along the very top edge of the panel
    top_streak = smoothstep(vv_sc, 0.76, 0.98) * smoothstep(tile_noise2(P, 18, 4, 733), 0.42, 0.78) * 0.28
    sc_col = sc_col * (1.0 - top_streak[..., None]) + np.array((0.82, 0.80, 0.74)) * top_streak[..., None]
    d_mix = smoothstep(grime * 0.6 + big * 0.4, 0.54, 0.82)[..., None] * 0.18
    sc_col = sc_col * (1.0 - d_mix) + salt_dust * d_mix
    b_mix = bare[..., None] * 0.78
    sc_col = sc_col * (1.0 - b_mix) + rust_col * b_mix
    paths["buoy_yellow_sc_albedo"] = save_tex("buoy_yellow_sc_albedo", sc_col, False)

    return paths


def srgb_to_linear(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def _load_image(path, non_color=False):
    name = os.path.basename(path)
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.load(path)
    else:
        img.filepath = path
        img.reload()
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return img


def _ensure_nodes(datablock):
    if bpy.app.version < (5, 0, 0):
        try:
            if not datablock.use_nodes:
                datablock.use_nodes = True
        except AttributeError:
            pass


def _make_pbr_mat(name, albedo_path, normal_path=None, orm_path=None, normal_strength=0.75):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    _ensure_nodes(m)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex_a = nt.nodes.new("ShaderNodeTexImage")
    tex_a.image = _load_image(albedo_path, False)
    nt.links.new(tex_a.outputs["Color"], bsdf.inputs["Base Color"])

    if normal_path:
        tex_n = nt.nodes.new("ShaderNodeTexImage")
        tex_n.image = _load_image(normal_path, True)
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = normal_strength
        nt.links.new(tex_n.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    if orm_path:
        tex_o = nt.nodes.new("ShaderNodeTexImage")
        tex_o.image = _load_image(orm_path, True)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(tex_o.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])

    return m


def _make_solid_mat(name, srgb, metallic=0.0, roughness=0.5, emission=None, emission_strength=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    _ensure_nodes(m)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    lin = (*srgb_to_linear(srgb), 1.0)
    bsdf.inputs["Base Color"].default_value = lin
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None and emission_strength > 0.0:
        elin = (*srgb_to_linear(emission), 1.0)
        bsdf.inputs["Emission Color"].default_value = elin
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    m.diffuse_color = lin
    return m


def build_materials(tex_paths):
    mats = {}
    for pname in ("buoy_green", "buoy_red", "buoy_yellow", "buoy_cream", "buoy_charcoal"):
        mats[pname] = _make_pbr_mat(
            pname, tex_paths[pname + "_albedo"], tex_paths["paint_normal"], tex_paths["paint_orm"]
        )
    mats["buoy_rust"] = _make_pbr_mat(
        "buoy_rust", tex_paths["buoy_rust_albedo"], tex_paths["buoy_rust_normal"], tex_paths["buoy_rust_orm"]
    )
    mats["buoy_concrete"] = _make_pbr_mat(
        "buoy_concrete",
        tex_paths["buoy_concrete_albedo"],
        tex_paths["buoy_concrete_normal"],
        tex_paths["buoy_concrete_orm"],
    )
    mats["buoy_bronze"] = _make_pbr_mat(
        "buoy_bronze",
        tex_paths["buoy_bronze_albedo"],
        tex_paths["buoy_bronze_normal"],
        tex_paths["buoy_bronze_orm"],
        normal_strength=0.45,
    )
    mats["buoy_solar"] = _make_pbr_mat(
        "buoy_solar", tex_paths["buoy_solar_albedo"], None, tex_paths["buoy_solar_orm"]
    )
    mats["buoy_antifouling"] = _make_pbr_mat(
        "buoy_antifouling",
        tex_paths["buoy_antifouling_albedo"],
        tex_paths["buoy_rust_normal"],
        tex_paths["buoy_antifouling_orm"],
    )
    mats["buoy_yellow_sc"] = _make_pbr_mat(
        "buoy_yellow_sc",
        tex_paths["buoy_yellow_sc_albedo"],
        tex_paths["paint_normal"],
        tex_paths["paint_orm"],
    )
    mats["buoy_rubber"] = _make_solid_mat("buoy_rubber", (0.07, 0.07, 0.08), metallic=0.0, roughness=0.88)
    mats["buoy_steel_bright"] = _make_solid_mat("buoy_steel_bright", (0.58, 0.60, 0.60), metallic=0.85, roughness=0.34)
    mats["beacon_green"] = _make_solid_mat(
        "beacon_green", (0.14, 0.85, 0.42), metallic=0.0, roughness=0.14, emission=(0.15, 0.95, 0.45), emission_strength=3.8
    )
    mats["beacon_red"] = _make_solid_mat(
        "beacon_red", (0.92, 0.16, 0.12), metallic=0.0, roughness=0.14, emission=(1.0, 0.18, 0.12), emission_strength=3.8
    )
    mats["beacon_amber"] = _make_solid_mat(
        "beacon_amber", (0.98, 0.66, 0.10), metallic=0.0, roughness=0.14, emission=(1.0, 0.70, 0.12), emission_strength=3.8
    )
    mats["beacon_white"] = _make_solid_mat(
        "beacon_white", (0.98, 0.93, 0.80), metallic=0.0, roughness=0.14, emission=(1.0, 0.94, 0.78), emission_strength=4.2
    )
    return mats


# ------------------------------------------------------------------ mesh builder

class BuoyMesh:
    """Bmesh builder with automatic material tracking and metre-scaled box UVs."""

    def __init__(self, name, all_mats):
        self.name = name
        self.all_mats = all_mats
        self.used_mats = []
        self.bm = bmesh.new()
        self.uv_layer = self.bm.loops.layers.uv.new("UVMap")

    def _slot(self, mat_name):
        if mat_name not in self.used_mats:
            self.used_mats.append(mat_name)
        return self.used_mats.index(mat_name)

    def _box_uv(self, bm_part, tile_m=UV_TILE_M):
        uv = bm_part.loops.layers.uv.verify()
        inv = 1.0 / tile_m
        for f in bm_part.faces:
            n = f.normal
            ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
            if az >= ax and az >= ay:
                for loop in f.loops:
                    co = loop.vert.co
                    loop[uv].uv = (co.x * inv, co.y * inv)
            elif ax >= ay:
                for loop in f.loops:
                    co = loop.vert.co
                    loop[uv].uv = (co.y * inv, co.z * inv)
            else:
                for loop in f.loops:
                    co = loop.vert.co
                    loop[uv].uv = (co.x * inv, co.z * inv)

    def _merge(self, part, mat_name, xform=None, smooth_angle_deg=None, custom_uv=False):
        if xform is not None:
            part.transform(xform)
        bmesh.ops.recalc_face_normals(part, faces=part.faces[:])
        if not custom_uv:
            self._box_uv(part)
        slot = self._slot(mat_name)
        for f in part.faces:
            f.material_index = slot
            if smooth_angle_deg is not None:
                f.smooth = smooth_angle_deg > 0
        me = bpy.data.meshes.new("_tmp_buoy")
        part.to_mesh(me)
        part.free()
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)

    def box(self, size, center, mat, rot=None, bevel=0.0):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        if HIGH_DETAIL and bevel > 0.0:
            bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=2, affect="EDGES", profile=0.5)
        xf = Matrix.Translation(Vector(center)) @ (rot.to_4x4() if rot else Matrix.Identity(4))
        self._merge(bm, mat, xf, smooth_angle_deg=0)

    def cylinder(self, r1, r2, depth, center, mat, segs=24, rot=None, cap_ends=True, smooth=True):
        if not HIGH_DETAIL:
            if segs >= 24:
                segs = 14
            elif segs >= 18:
                segs = 11
            elif segs >= 14:
                segs = 9
            elif segs >= 10:
                segs = 6
            else:
                segs = 4
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm, cap_ends=cap_ends, cap_tris=False, segments=segs, radius1=r1, radius2=r2, depth=depth
        )
        for f in bm.faces:
            f.smooth = smooth and len(f.verts) == 4
        xf = Matrix.Translation(Vector(center)) @ (rot.to_4x4() if rot else Matrix.Identity(4))
        self._merge(bm, mat, xf)

    def lathe(self, profile_rz, center, mat, segs=24, smooth=True, cap_bottom=True, cap_top=True):
        """Revolves a list of (radius, z) pairs around Z at `center`."""
        if not HIGH_DETAIL:
            if len(profile_rz) >= 8 and max(r for r, _ in profile_rz) < 0.25:
                profile_rz = [profile_rz[0], profile_rz[2], profile_rz[4], profile_rz[6], profile_rz[-1]]
            if segs >= 24:
                segs = 14
            elif segs >= 18:
                segs = 10
            else:
                segs = 8
        bm = bmesh.new()
        rings = []
        for r, z in profile_rz:
            ring = []
            for k in range(segs):
                a = math.tau * k / segs
                ring.append(bm.verts.new((math.cos(a) * r, math.sin(a) * r, z)))
            rings.append((ring, r, z))
        bm.verts.ensure_lookup_table()
        uv = bm.loops.layers.uv.verify()
        # Cumulative arc distance along profile for crisp V coordinates
        v_coords = [0.0]
        for i in range(1, len(profile_rz)):
            dr = profile_rz[i][0] - profile_rz[i - 1][0]
            dz = profile_rz[i][1] - profile_rz[i - 1][1]
            v_coords.append(v_coords[-1] + math.hypot(dr, dz))
        max_r = max((r for r, _ in profile_rz), default=0.5)
        circ = math.tau * max(max_r, 0.1)
        inv = 1.0 / UV_TILE_M
        for i in range(len(rings) - 1):
            r0, _, _ = rings[i]
            r1, _, _ = rings[i + 1]
            v0, v1 = v_coords[i] * inv, v_coords[i + 1] * inv
            for k in range(segs):
                k1 = (k + 1) % segs
                try:
                    f = bm.faces.new((r0[k], r0[k1], r1[k1], r1[k]))
                    f.smooth = smooth
                    u0 = circ * (k / segs) * inv
                    u1 = circ * ((k + 1) / segs) * inv
                    uvs = ((u0, v0), (u1, v0), (u1, v1), (u0, v1))
                    for loop, t in zip(f.loops, uvs):
                        loop[uv].uv = t
                except ValueError:
                    pass
        if cap_bottom and profile_rz[0][0] > 1e-4:
            try:
                f = bm.faces.new(rings[0][0][::-1])
                f.smooth = False
                for loop in f.loops:
                    loop[uv].uv = (loop.vert.co.x * inv, loop.vert.co.y * inv)
            except ValueError:
                pass
        if cap_top and profile_rz[-1][0] > 1e-4:
            try:
                f = bm.faces.new(rings[-1][0])
                f.smooth = False
                for loop in f.loops:
                    loop[uv].uv = (loop.vert.co.x * inv, loop.vert.co.y * inv)
            except ValueError:
                pass
        self._merge(bm, mat, Matrix.Translation(Vector(center)), custom_uv=True)

    def strut(self, p0, p1, radius, mat, segs=8, r2=None, cap=True):
        a, b = Vector(p0), Vector(p1)
        d = b - a
        if d.length < 1e-5:
            return
        rot = d.to_track_quat("Z", "Y").to_matrix()
        self.cylinder(radius, r2 if r2 is not None else radius, d.length, (a + b) * 0.5, mat, segs=segs, rot=rot, cap_ends=cap)

    def torus(self, major_r, minor_r, center, mat, major_segs=24, minor_segs=10, rot=None):
        if not HIGH_DETAIL:
            if major_segs >= 24:
                major_segs = 14
            elif major_segs >= 16:
                major_segs = 10
            else:
                major_segs = 8
            minor_segs = 4
        bm = bmesh.new()
        rings = []
        for i in range(major_segs):
            a = math.tau * i / major_segs
            ca, sa = math.cos(a), math.sin(a)
            ring = []
            for j in range(minor_segs):
                b = math.tau * j / minor_segs
                r = major_r + minor_r * math.cos(b)
                z = minor_r * math.sin(b)
                ring.append(bm.verts.new((ca * r, sa * r, z)))
            rings.append(ring)
        for i in range(major_segs):
            i1 = (i + 1) % major_segs
            for j in range(minor_segs):
                j1 = (j + 1) % minor_segs
                f = bm.faces.new((rings[i][j], rings[i1][j], rings[i1][j1], rings[i][j1]))
                f.smooth = True
        xf = Matrix.Translation(Vector(center)) @ (rot.to_4x4() if rot else Matrix.Identity(4))
        self._merge(bm, mat, xf)

    def sphere(self, radius, center, mat, u_segs=16, v_segs=10):
        if not HIGH_DETAIL:
            u_segs, v_segs = 6, 4
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=u_segs, v_segments=v_segs, radius=radius)
        for f in bm.faces:
            f.smooth = True
        self._merge(bm, mat, Matrix.Translation(Vector(center)))

    def chain_link(self, center, length, width, wire_r, mat, rot=None):
        """Stadium-shaped marine anchor chain link in the XZ plane."""
        bm = bmesh.new()
        half_straight = max(0.005, (length - width) * 0.5)
        arc_r = width * 0.5 - wire_r
        path = []
        arc_steps = 5 if HIGH_DETAIL else 2
        # Top semicircle
        for i in range(arc_steps + 1):
            a = math.pi * i / arc_steps
            path.append(Vector((math.cos(a) * arc_r, 0.0, half_straight + math.sin(a) * arc_r)))
        # Bottom semicircle
        for i in range(arc_steps + 1):
            a = math.pi + math.pi * i / arc_steps
            path.append(Vector((math.cos(a) * arc_r, 0.0, -half_straight + math.sin(a) * arc_r)))

        minor_segs = 7 if HIGH_DETAIL else 4
        rings = []
        n = len(path)
        for i, p in enumerate(path):
            t = (path[(i + 1) % n] - path[(i - 1) % n]).normalized()
            nrm = Vector((0.0, 1.0, 0.0))
            binrm = t.cross(nrm).normalized()
            ring = []
            for j in range(minor_segs):
                b = math.tau * j / minor_segs
                ring.append(bm.verts.new(p + (nrm * math.cos(b) + binrm * math.sin(b)) * wire_r))
            rings.append(ring)
        for i in range(n):
            i1 = (i + 1) % n
            for j in range(minor_segs):
                j1 = (j + 1) % minor_segs
                f = bm.faces.new((rings[i][j], rings[i1][j], rings[i1][j1], rings[i][j1]))
                f.smooth = True
        xf = Matrix.Translation(Vector(center)) @ (rot.to_4x4() if rot else Matrix.Identity(4))
        self._merge(bm, mat, xf)

    def extrude_poly_y(self, pts_xz, thickness, center, mat, rot=None):
        """Extrudes a 2D polygon in XZ along Y by `thickness` centered at Y=0."""
        bm = bmesh.new()
        hy = thickness * 0.5
        front = [bm.verts.new((x, -hy, z)) for x, z in pts_xz]
        back = [bm.verts.new((x, hy, z)) for x, z in pts_xz]
        bm.faces.new(front[::-1])
        bm.faces.new(back)
        n = len(pts_xz)
        for i in range(n):
            i1 = (i + 1) % n
            bm.faces.new((front[i], front[i1], back[i1], back[i]))
        xf = Matrix.Translation(Vector(center)) @ (rot.to_4x4() if rot else Matrix.Identity(4))
        self._merge(bm, mat, xf, smooth_angle_deg=0)

    def solar_face(self, width, height, xform, mat="buoy_solar"):
        """Single quad with exact 0..1 UVs (facing local -Y)."""
        bm = bmesh.new()
        hw, hh = width * 0.5, height * 0.5
        v0 = bm.verts.new((-hw, 0.0, -hh))
        v1 = bm.verts.new((hw, 0.0, -hh))
        v2 = bm.verts.new((hw, 0.0, hh))
        v3 = bm.verts.new((-hw, 0.0, hh))
        f = bm.faces.new((v0, v1, v2, v3))
        uv = bm.loops.layers.uv.verify()
        for loop, t in zip(f.loops, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
            loop[uv].uv = t
        self._merge(bm, mat, xform, custom_uv=True)

    def arched_lug(self, center, yaw, base_w, arch_r, z_center, thick, hole_r, mat):
        """Heavy arched welded deck lifting lug in local XZ with a true through-hole along Y."""
        segs = 12 if HIGH_DETAIL else 8
        bm = bmesh.new()
        hy = thick * 0.5
        hw = base_w * 0.5
        f_in, f_out, b_in, b_out = [], [], [], []
        for k in range(segs):
            a = math.tau * k / segs
            ca, sa = math.cos(a), math.sin(a)
            ix, iz = hole_r * ca, z_center + hole_r * sa
            if sa >= 0.0:
                ox, oz = arch_r * ca, z_center + arch_r * sa
            else:
                tx = hw / max(abs(ca), 1e-6)
                tz = z_center / max(-sa, 1e-6)
                t = min(tx, tz)
                ox, oz = t * ca, z_center + t * sa
            f_in.append(bm.verts.new((ix, -hy, iz)))
            f_out.append(bm.verts.new((ox, -hy, oz)))
            b_in.append(bm.verts.new((ix, hy, iz)))
            b_out.append(bm.verts.new((ox, hy, oz)))
        for k in range(segs):
            k1 = (k + 1) % segs
            # Front (-Y) and back (+Y) annular faces
            bm.faces.new((f_in[k], f_out[k], f_out[k1], f_in[k1]))
            bm.faces.new((b_in[k], b_in[k1], b_out[k1], b_out[k]))
            # Outer arch rim and inner hole bore
            bm.faces.new((f_out[k], b_out[k], b_out[k1], f_out[k1]))
            bm.faces.new((f_in[k], f_in[k1], b_in[k1], b_in[k]))
        rot = Matrix.Rotation(yaw, 3, "Z")
        xf = Matrix.Translation(Vector(center)) @ rot.to_4x4()
        self._merge(bm, mat, xf, smooth_angle_deg=0)

    def finish(self, collection):
        me = bpy.data.meshes.get(self.name)
        if me:
            bpy.data.meshes.remove(me)
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for mname in self.used_mats:
            me.materials.append(self.all_mats[mname])
        ob = bpy.data.objects.new(self.name, me)
        collection.objects.link(ob)
        return ob


# ------------------------------------------------------------------ shared marine assemblies

def add_bolt_ring(m, center, ring_r, count, bolt_r=0.018, bolt_h=0.022, mat="buoy_rust"):
    cx, cy, cz = center
    for i in range(count):
        a = math.tau * i / count
        m.cylinder(bolt_r, bolt_r, bolt_h, (cx + math.cos(a) * ring_r, cy + math.sin(a) * ring_r, cz), mat, segs=6, smooth=False)


def add_padeye(m, pos, yaw, mat="buoy_rust", scale=1.0):
    """Welded deck lifting padeye with base plate and shackle ring."""
    rot = Matrix.Rotation(yaw, 3, "Z")
    p = Vector(pos)
    m.box((0.06 * scale, 0.14 * scale, 0.025 * scale), p + rot @ Vector((0, 0, 0.012 * scale)), mat, rot=rot, bevel=0.004)
    m.box((0.022 * scale, 0.10 * scale, 0.10 * scale), p + rot @ Vector((0, 0, 0.065 * scale)), mat, rot=rot, bevel=0.005)
    ring_rot = rot @ Matrix.Rotation(math.pi * 0.5, 3, "Y")
    m.torus(0.055 * scale, 0.014 * scale, p + rot @ Vector((0, 0, 0.125 * scale)), "buoy_steel_bright", major_segs=14, minor_segs=6, rot=ring_rot)


def add_deck_hatch(m, pos, radius=0.18, mat="buoy_charcoal"):
    """Bolted circular inspection hatch on a buoy deck."""
    p = Vector(pos)
    m.cylinder(radius * 1.12, radius * 1.12, 0.035, p + Vector((0, 0, 0.018)), "buoy_rust", segs=16)
    m.cylinder(radius, radius * 0.96, 0.03, p + Vector((0, 0, 0.045)), mat, segs=16)
    add_bolt_ring(m, p + Vector((0, 0, 0.058)), radius * 0.85, 8, bolt_r=0.012, bolt_h=0.016, mat="buoy_steel_bright")
    m.box((radius * 0.6, 0.028, 0.035), p + Vector((0, 0, 0.072)), "buoy_rust", bevel=0.005)


def add_mooring_chain(m, top_z, links=4, link_len=0.19, link_w=0.11, wire_r=0.018):
    """Mooring bail ring + hanging anchor chain links below the buoy keel."""
    m.torus(0.085, 0.022, (0.0, 0.0, top_z - 0.06), "buoy_rust", major_segs=16, minor_segs=7, rot=Matrix.Rotation(math.pi * 0.5, 3, "X"))
    step = link_len - 2.3 * wire_r
    z = top_z - 0.16
    for i in range(links):
        rot = Matrix.Rotation(math.pi * 0.5 if i % 2 else 0.0, 3, "Z")
        m.chain_link((0.0, 0.0, z), link_len, link_w, wire_r, "buoy_rust", rot=rot)
        z -= step
    return Vector((0.0, 0.0, top_z - 0.06))


def add_fresnel_lantern(m, base_pos, lens_mat, scale=1.0, cage=True):
    """Detailed marine beacon lantern: flange, cast heatsink, tiered Fresnel lens, cap, guard cage."""
    p = Vector(base_pos)
    s = scale
    # Mounting flange + bolts
    m.cylinder(0.15 * s, 0.15 * s, 0.03 * s, p + Vector((0, 0, 0.015 * s)), "buoy_charcoal", segs=16)
    add_bolt_ring(m, p + Vector((0, 0, 0.032 * s)), 0.125 * s, 6, bolt_r=0.011 * s, bolt_h=0.014 * s, mat="buoy_steel_bright")
    # Ribbed cast housing base
    base_prof = [
        (0.12 * s, 0.03 * s),
        (0.12 * s, 0.07 * s),
        (0.135 * s, 0.08 * s),
        (0.135 * s, 0.10 * s),
        (0.12 * s, 0.11 * s),
        (0.12 * s, 0.15 * s),
        (0.132 * s, 0.16 * s),
        (0.115 * s, 0.18 * s),
    ]
    m.lathe(base_prof, p, "buoy_charcoal", segs=18)
    # Tiered Fresnel glowing lens
    lens_prof = [
        (0.095 * s, 0.18 * s),
        (0.112 * s, 0.21 * s),
        (0.098 * s, 0.235 * s),
        (0.116 * s, 0.265 * s),
        (0.100 * s, 0.295 * s),
        (0.115 * s, 0.325 * s),
        (0.098 * s, 0.355 * s),
        (0.110 * s, 0.385 * s),
        (0.092 * s, 0.41 * s),
    ]
    m.lathe(lens_prof, p, lens_mat, segs=20, smooth=True)
    # Domed weather hood + daylight sensor + bird spike
    hood_prof = [
        (0.125 * s, 0.41 * s),
        (0.135 * s, 0.43 * s),
        (0.115 * s, 0.465 * s),
        (0.065 * s, 0.495 * s),
        (0.022 * s, 0.51 * s),
    ]
    m.lathe(hood_prof, p, "buoy_charcoal", segs=18)
    m.strut(p + Vector((0, 0, 0.505 * s)), p + Vector((0, 0, 0.64 * s)), 0.008 * s, "buoy_steel_bright", segs=6)

    if cage:
        cage_r = 0.175 * s
        m.torus(cage_r, 0.011 * s, p + Vector((0, 0, 0.17 * s)), "buoy_charcoal", major_segs=18, minor_segs=6)
        m.torus(cage_r, 0.011 * s, p + Vector((0, 0, 0.43 * s)), "buoy_charcoal", major_segs=18, minor_segs=6)
        for i in range(4):
            a = math.tau * i / 4.0 + math.pi * 0.25
            ca, sa = math.cos(a), math.sin(a)
            p_bot = p + Vector((ca * 0.145 * s, sa * 0.145 * s, 0.02 * s))
            p_mid1 = p + Vector((ca * cage_r, sa * cage_r, 0.17 * s))
            p_mid2 = p + Vector((ca * cage_r, sa * cage_r, 0.43 * s))
            p_top = p + Vector((ca * 0.08 * s, sa * 0.08 * s, 0.50 * s))
            m.strut(p_bot, p_mid1, 0.011 * s, "buoy_charcoal", segs=6)
            m.strut(p_mid1, p_mid2, 0.011 * s, "buoy_charcoal", segs=6)
            m.strut(p_mid2, p_top, 0.011 * s, "buoy_charcoal", segs=6)
    return p + Vector((0, 0, 0.295 * s))


def add_radar_reflector(m, center, size=0.36, yaw=0.0):
    """Classic 3-plane orthogonal octahedral marine radar reflector mounted diagonally."""
    rot = (
        Matrix.Rotation(yaw, 3, "Z")
        @ Matrix.Rotation(math.radians(35.26), 3, "X")
        @ Matrix.Rotation(math.radians(45.0), 3, "Y")
    )
    t = 0.012
    c = Vector(center)
    m.box((size, size, t), c, "buoy_steel_bright", rot=rot)
    m.box((size, t, size), c, "buoy_steel_bright", rot=rot)
    m.box((t, size, size), c, "buoy_steel_bright", rot=rot)


def add_solar_panel(m, pos, width=0.46, height=0.34, tilt_deg=38.0, yaw_deg=0.0):
    """Framed photovoltaic solar panel with angled rear mounting yoke."""
    rot = Matrix.Rotation(math.radians(yaw_deg), 3, "Z") @ Matrix.Rotation(math.radians(-tilt_deg), 3, "X")
    xf = Matrix.Translation(Vector(pos)) @ rot.to_4x4()
    frame_t = 0.026
    border = 0.022
    # Backing plate & frame rails
    m.box((width, 0.014, height), Vector(pos) + rot @ Vector((0, 0.008, 0)), "buoy_charcoal", rot=rot)
    m.box((width + border * 2, frame_t, border), Vector(pos) + rot @ Vector((0, 0, height * 0.5 + border * 0.5)), "buoy_steel_bright", rot=rot, bevel=0.003)
    m.box((width + border * 2, frame_t, border), Vector(pos) + rot @ Vector((0, 0, -height * 0.5 - border * 0.5)), "buoy_steel_bright", rot=rot, bevel=0.003)
    m.box((border, frame_t, height), Vector(pos) + rot @ Vector((width * 0.5 + border * 0.5, 0, 0)), "buoy_steel_bright", rot=rot, bevel=0.003)
    m.box((border, frame_t, height), Vector(pos) + rot @ Vector((-width * 0.5 - border * 0.5, 0, 0)), "buoy_steel_bright", rot=rot, bevel=0.003)
    # Gridded cell face facing local -Y (front/skyward)
    m.solar_face(width, height, xf @ Matrix.Translation((0.0, -0.004, 0.0)))
    # Rear junction nub
    m.box((0.09, 0.035, 0.07), Vector(pos) + rot @ Vector((0, 0.03, 0)), "buoy_charcoal", rot=rot, bevel=0.004)


def add_battery_box(m, pos, yaw_deg=0.0, size=(0.30, 0.22, 0.36)):
    """Weathered steel marine battery/controller cabinet with flanged lid and clasp."""
    rot = Matrix.Rotation(math.radians(yaw_deg), 3, "Z")
    p = Vector(pos)
    sx, sy, sz = size
    m.box(size, p, "buoy_charcoal", rot=rot, bevel=0.01)
    # Overhanging rain-lip lid
    m.box((sx + 0.03, sy + 0.03, 0.045), p + rot @ Vector((0, 0, sz * 0.5 + 0.01)), "buoy_rust", rot=rot, bevel=0.006)
    # Front latch hasp + status LED
    m.box((0.035, 0.025, 0.08), p + rot @ Vector((0, -sy * 0.5 - 0.01, 0.04)), "buoy_steel_bright", rot=rot)
    m.box((0.03, 0.016, 0.03), p + rot @ Vector((sx * 0.28, -sy * 0.5 - 0.006, sz * 0.28)), "beacon_amber", rot=rot)


def add_rub_rail(m, radius, z, height=0.14, thick=0.065, clamps=8):
    """Heavy dark marine rubber fender ring with steel clamping straps."""
    prof = [
        (radius - 0.01, z - height * 0.5),
        (radius + thick, z - height * 0.36),
        (radius + thick, z + height * 0.36),
        (radius - 0.01, z + height * 0.5),
    ]
    m.lathe(prof, (0, 0, 0), "buoy_rubber", segs=28, smooth=True, cap_bottom=False, cap_top=False)
    for i in range(clamps):
        a = math.tau * i / clamps
        rot = Matrix.Rotation(a, 3, "Z")
        m.box((thick + 0.03, 0.055, height + 0.035), (math.cos(a) * (radius + thick * 0.55), math.sin(a) * (radius + thick * 0.55), z), "buoy_rust", rot=rot, bevel=0.006)


def add_stenciled_digit(m, digit, center, face_sign_y, scale=1.0, mat="buoy_cream"):
    """Crisp geometric raised/stenciled channel numeral ('3' or '4') with zero coplanar overlap."""
    cx, cy, cz = center
    t = 0.016
    s = scale
    # Mirror X on back face (+Y) so the numeral reads left-to-right from both sides.
    sx_dir = 1.0 if face_sign_y < 0 else -1.0

    def bar(x, z, w, h):
        m.box((w * s, t, h * s), (cx + x * s * sx_dir, cy + face_sign_y * t * 0.45, cz + z * s), mat, bevel=0.002)

    if digit == "3":
        # Continuous right spine; 3 horizontal bars cleanly butt against its left edge (x = 0.085)
        bar(0.125, 0.0, 0.080, 0.595)
        bar(-0.040, 0.260, 0.250, 0.075)
        bar(-0.025, 0.000, 0.220, 0.075)
        bar(-0.040, -0.260, 0.250, 0.075)
    elif digit == "4":
        # Continuous right vertical leg; crossbar splits cleanly left & right of it, upper left leg butts above crossbar
        bar(0.100, 0.000, 0.084, 0.580)
        bar(-0.055, -0.020, 0.226, 0.080)
        bar(0.172, -0.020, 0.060, 0.080)
        bar(-0.126, 0.155, 0.084, 0.270)


# ------------------------------------------------------------------ 6 asset builders

def build_buoy_port_can(coll, mats):
    """Port-Hand Can Buoy: green flat-top cylindrical buoy with solar beacon & radar reflector."""
    m = BuoyMesh("buoy_port_can", mats)

    # Submerged counterweight skirt & lower hull
    sub_prof = [
        (0.32, -0.82),
        (0.46, -0.78),
        (0.50, -0.60),
        (0.70, -0.25),
        (0.84, 0.02),
    ]
    m.lathe(sub_prof, (0, 0, 0), "buoy_rust", segs=24)
    # Anti-roll counterweight ring at bottom
    m.torus(0.46, 0.045, (0, 0, -0.72), "buoy_rust", major_segs=20, minor_segs=8)
    mooring_pt = add_mooring_chain(m, -0.82, links=4)

    # Main cylindrical pontoon float (green)
    float_prof = [
        (0.85, 0.0),
        (0.86, 0.64),
        (0.79, 0.72),
        (0.54, 0.74),
    ]
    m.lathe(float_prof, (0, 0, 0), "buoy_green", segs=28)
    # Waterline rusted splash ring & vertical weld seams
    m.cylinder(0.87, 0.87, 0.14, (0, 0, 0.06), "buoy_rust", segs=28)
    add_rub_rail(m, 0.86, 0.36, height=0.14, thick=0.065, clamps=8)
    for i in range(6):
        a = math.tau * i / 6.0
        rot = Matrix.Rotation(a, 3, "Z")
        m.box((0.022, 0.018, 0.56), (math.cos(a) * 0.855, math.sin(a) * 0.855, 0.36), "buoy_rust", rot=rot)

    # Deck hardware: 3 lifting padeyes + inspection hatch
    for i in range(3):
        a = math.tau * i / 3.0 + math.radians(30)
        add_padeye(m, (math.cos(a) * 0.68, math.sin(a) * 0.68, 0.725), a, scale=0.9)
    add_deck_hatch(m, (0.0, -0.64, 0.72), radius=0.13)

    # Bolted deck collar flange
    m.cylinder(0.60, 0.60, 0.05, (0, 0, 0.75), "buoy_rust", segs=24)
    add_bolt_ring(m, (0, 0, 0.78), 0.56, 12, bolt_r=0.016, bolt_h=0.02)

    # Cylindrical "Can" superstructure (green lower/upper, crisp cream middle band)
    m.lathe([(0.52, 0.77), (0.52, 1.44)], (0, 0, 0), "buoy_green", segs=24, cap_bottom=False, cap_top=False)
    m.lathe([(0.524, 1.44), (0.524, 1.88)], (0, 0, 0), "buoy_cream", segs=24, cap_bottom=False, cap_top=False)
    m.lathe([(0.52, 1.88), (0.52, 2.40), (0.48, 2.45)], (0, 0, 0), "buoy_green", segs=24, cap_bottom=False, cap_top=True)
    # Raised weld seam rings bordering the cream band
    for rz in (1.44, 1.88):
        m.torus(0.524, 0.014, (0, 0, rz), "buoy_rust", major_segs=24, minor_segs=6)

    # 4 vertical triangular gussets tying the can body into the float deck
    for i in range(4):
        a = math.tau * i / 4.0 + math.pi * 0.25
        rot = Matrix.Rotation(a, 3, "Z")
        m.extrude_poly_y([(0.50, 0.74), (0.76, 0.74), (0.50, 1.24)], 0.028, (0, 0, 0), "buoy_green", rot=rot)

    # Climbing grab rungs on +X side
    for rz in (1.12, 1.48, 1.84, 2.20):
        m.strut((0.50, -0.14, rz), (0.60, -0.14, rz), 0.013, "buoy_charcoal", segs=6)
        m.strut((0.50, 0.14, rz), (0.60, 0.14, rz), 0.013, "buoy_charcoal", segs=6)
        m.strut((0.60, -0.14, rz), (0.60, 0.14, rz), 0.013, "buoy_charcoal", segs=6)

    # Top flange rim & deck ring
    m.torus(0.49, 0.018, (0, 0, 2.45), "buoy_charcoal", major_segs=24, minor_segs=6)

    # Side solar panel + battery box + armored conduit on -X side
    add_battery_box(m, (-0.54, 0.0, 2.02), yaw_deg=90, size=(0.24, 0.16, 0.28))
    m.strut((-0.54, 0.0, 2.16), (-0.56, -0.04, 2.66), 0.013, "buoy_rust", segs=6)
    m.strut((-0.44, 0.0, 2.30), (-0.56, -0.06, 2.66), 0.022, "buoy_charcoal", segs=8)
    add_solar_panel(m, (-0.58, -0.09, 2.72), width=0.42, height=0.30, tilt_deg=35, yaw_deg=25)

    # Radar reflector on +X mast arm
    m.strut((0.36, 0.0, 2.42), (0.46, 0.0, 2.86), 0.02, "buoy_charcoal", segs=8)
    add_radar_reflector(m, (0.46, 0.0, 2.98), size=0.34, yaw=0.4)

    # Center green Fresnel beacon lantern
    m.cylinder(0.17, 0.14, 0.22, (0, 0, 2.55), "buoy_charcoal", segs=16)
    beacon_pt = add_fresnel_lantern(m, (0, 0, 2.66), "beacon_green", scale=1.05, cage=True)

    ob = m.finish(coll)
    return ob, {"BeaconLight": beacon_pt, "MooringEye": mooring_pt}


def build_buoy_starboard_nun(coll, mats):
    """Starboard-Hand Nun Buoy: red conical-top buoy with radar reflector & red beacon."""
    m = BuoyMesh("buoy_starboard_nun", mats)

    # Submerged counterweight cone & skirt
    sub_prof = [
        (0.28, -0.84),
        (0.44, -0.78),
        (0.52, -0.58),
        (0.72, -0.22),
        (0.85, 0.02),
    ]
    m.lathe(sub_prof, (0, 0, 0), "buoy_rust", segs=24)
    m.torus(0.44, 0.045, (0, 0, -0.72), "buoy_rust", major_segs=20, minor_segs=8)
    mooring_pt = add_mooring_chain(m, -0.84, links=4)

    # Main cylindrical pontoon float (red)
    float_prof = [
        (0.86, 0.0),
        (0.87, 0.62),
        (0.80, 0.70),
        (0.62, 0.72),
    ]
    m.lathe(float_prof, (0, 0, 0), "buoy_red", segs=28)
    m.cylinder(0.88, 0.88, 0.14, (0, 0, 0.06), "buoy_rust", segs=28)
    add_rub_rail(m, 0.87, 0.34, height=0.14, thick=0.065, clamps=8)

    # Deck padeyes + hatch
    for i in range(3):
        a = math.tau * i / 3.0 + math.radians(-30)
        add_padeye(m, (math.cos(a) * 0.70, math.sin(a) * 0.70, 0.705), a, scale=0.9)
    add_deck_hatch(m, (0.0, -0.68, 0.70), radius=0.12)

    # Bolted collar flange
    m.cylinder(0.66, 0.66, 0.05, (0, 0, 0.73), "buoy_rust", segs=24)
    add_bolt_ring(m, (0, 0, 0.76), 0.62, 12, bolt_r=0.016, bolt_h=0.02)

    # Conical "Nun" superstructure in 3 courses (red / cream stripe / red cone)
    m.lathe([(0.60, 0.75), (0.45, 1.46)], (0, 0, 0), "buoy_red", segs=24, cap_bottom=False, cap_top=False)
    m.lathe([(0.454, 1.46), (0.364, 1.88)], (0, 0, 0), "buoy_cream", segs=24, cap_bottom=False, cap_top=False)
    m.lathe([(0.36, 1.88), (0.17, 2.74)], (0, 0, 0), "buoy_red", segs=24, cap_bottom=False, cap_top=True)
    m.torus(0.454, 0.014, (0, 0, 1.46), "buoy_rust", major_segs=24, minor_segs=6)
    m.torus(0.364, 0.014, (0, 0, 1.88), "buoy_rust", major_segs=24, minor_segs=6)

    # 4 vertical gusset fins at cone base
    for i in range(4):
        a = math.tau * i / 4.0 + math.pi * 0.25
        rot = Matrix.Rotation(a, 3, "Z")
        m.extrude_poly_y([(0.56, 0.72), (0.78, 0.72), (0.49, 1.24)], 0.028, (0, 0, 0), "buoy_red", rot=rot)

    # Side solar panel + battery pack + armored conduit on -X flank
    m.strut((-0.34, 0.0, 1.98), (-0.54, -0.05, 2.24), 0.022, "buoy_charcoal", segs=8)
    add_solar_panel(m, (-0.56, -0.08, 2.32), width=0.40, height=0.28, tilt_deg=35, yaw_deg=20)
    add_battery_box(m, (-0.49, 0.0, 1.50), yaw_deg=90, size=(0.22, 0.15, 0.26))
    m.strut((-0.49, 0.0, 1.63), (-0.54, -0.04, 2.26), 0.013, "buoy_rust", segs=6)

    # Radar reflector on +X side arm near upper cone
    m.strut((0.24, 0.0, 2.38), (0.50, 0.0, 2.52), 0.02, "buoy_charcoal", segs=8)
    m.strut((0.50, 0.0, 2.52), (0.50, 0.0, 2.74), 0.02, "buoy_charcoal", segs=8)
    add_radar_reflector(m, (0.50, 0.0, 2.86), size=0.34, yaw=-0.3)

    # Crowned red Fresnel lantern
    m.cylinder(0.18, 0.15, 0.16, (0, 0, 2.80), "buoy_charcoal", segs=16)
    beacon_pt = add_fresnel_lantern(m, (0, 0, 2.88), "beacon_red", scale=1.05, cage=True)

    ob = m.finish(coll)
    return ob, {"BeaconLight": beacon_pt, "MooringEye": mooring_pt}


def build_buoy_bell_tower(coll, mats):
    """Hero Fairway Lattice Bell Buoy: wide float, 4-leg tower, bronze bell, twin solar wings, Fresnel beacon."""
    m = BuoyMesh("buoy_bell_tower", mats)

    # Deep submerged counterweight tube + cruciform anti-roll fins + hull skirt
    sub_prof = [
        (0.36, -1.30),
        (0.42, -1.26),
        (0.42, -0.58),
        (0.76, -0.34),
        (1.18, 0.02),
    ]
    m.lathe(sub_prof, (0, 0, 0), "buoy_rust", segs=24)
    for i in range(4):
        a = math.tau * i / 4.0
        rot = Matrix.Rotation(a, 3, "Z")
        m.extrude_poly_y([(0.40, -1.20), (0.64, -1.06), (0.64, -0.56), (0.40, -0.48)], 0.032, (0, 0, 0), "buoy_rust", rot=rot)
    mooring_pt = add_mooring_chain(m, -1.30, links=5, link_len=0.22, link_w=0.13, wire_r=0.022)

    # Wide pontoon float hull: rusted splash band, bold red body, cream deck shoulder
    m.lathe([(1.24, 0.0), (1.26, 0.22)], (0, 0, 0), "buoy_rust", segs=28, cap_bottom=False, cap_top=False)
    m.lathe([(1.26, 0.22), (1.26, 0.76)], (0, 0, 0), "buoy_red", segs=28, cap_bottom=False, cap_top=False)
    m.lathe([(1.26, 0.76), (1.16, 0.92), (0.01, 0.94)], (0, 0, 0), "buoy_cream", segs=28, cap_bottom=False, cap_top=True)
    add_rub_rail(m, 1.26, 0.48, height=0.18, thick=0.085, clamps=12)

    # Deck hardware: 4 heavy padeyes, battery-well hatch, perimeter toe ring
    for i in range(4):
        a = math.tau * i / 4.0
        add_padeye(m, (math.cos(a) * 1.04, math.sin(a) * 1.04, 0.92), a, scale=1.15)
    add_deck_hatch(m, (0.0, 0.0, 0.93), radius=0.28, mat="buoy_charcoal")
    m.torus(1.14, 0.025, (0, 0, 0.93), "buoy_rust", major_segs=28, minor_segs=6)

    # 4-legged tapered open steel lattice tower (z = 0.92 .. 4.30)
    z_levels = [0.92, 1.82, 2.74, 3.58, 4.30]
    half_spans = [0.76, 0.64, 0.53, 0.44, 0.36]

    def leg_pt(lv, corner_idx):
        sx = -1.0 if corner_idx in (0, 3) else 1.0
        sy = -1.0 if corner_idx in (0, 1) else 1.0
        return Vector((sx * half_spans[lv], sy * half_spans[lv], z_levels[lv]))

    # Corner foot gussets + 4 main legs (Eden cream painted steel with red upper bay)
    for c in range(4):
        base = leg_pt(0, c)
        m.box((0.20, 0.20, 0.045), base + Vector((0, 0, 0.02)), "buoy_rust", bevel=0.006)
        add_bolt_ring(m, base + Vector((0, 0, 0.048)), 0.075, 4, bolt_r=0.014, bolt_h=0.018)
        for lv in range(len(z_levels) - 1):
            leg_mat = "buoy_red" if lv == 2 else "buoy_cream"
            m.strut(leg_pt(lv, c), leg_pt(lv + 1, c), 0.046, leg_mat, segs=8)

    # Horizontal perimeter beams & X-bracing struts
    for lv in range(1, len(z_levels)):
        ring_mat = "buoy_red" if lv == 3 else "buoy_cream"
        for c in range(4):
            c1 = (c + 1) % 4
            m.strut(leg_pt(lv, c), leg_pt(lv, c1), 0.030, ring_mat, segs=6)
    # X-bracing on bays 1, 2, 3 (leave bay 0 open around the bell, with upper corner knee braces!)
    for lv in (1, 2, 3):
        brace_mat = "buoy_charcoal" if lv == 2 else "buoy_cream"
        for c in range(4):
            c1 = (c + 1) % 4
            a0, a1 = leg_pt(lv, c), leg_pt(lv, c1)
            b0, b1 = leg_pt(lv + 1, c), leg_pt(lv + 1, c1)
            m.strut(a0, b1, 0.020, brace_mat, segs=6)
            m.strut(a1, b0, 0.020, brace_mat, segs=6)
    # Lower bay corner knee braces flanking the bell opening
    for c in range(4):
        c1 = (c + 1) % 4
        top_a = leg_pt(1, c)
        top_b = leg_pt(1, c1)
        mid_a = leg_pt(0, c).lerp(top_a, 0.52)
        mid_b = leg_pt(0, c1).lerp(top_b, 0.52)
        m.strut(mid_a, top_a.lerp(top_b, 0.34), 0.022, "buoy_cream", segs=6)
        m.strut(mid_b, top_b.lerp(top_a, 0.34), 0.022, "buoy_cream", segs=6)

    # Suspended cast-bronze navigation bell inside lower bay (z = 1.56 .. 2.38)
    # Anchor bell crossbar solidly between two side perimeter rails spanning legs at z = 2.46
    def leg_at_z(z_target, corner_idx):
        for lv in range(len(z_levels) - 1):
            if z_levels[lv] <= z_target <= z_levels[lv + 1]:
                t = (z_target - z_levels[lv]) / (z_levels[lv + 1] - z_levels[lv])
                return leg_pt(lv, corner_idx).lerp(leg_pt(lv + 1, corner_idx), t)
        return leg_pt(0, corner_idx)

    bell_bar_z = 2.46
    # Side horizontal support rails on -X (corners 0-3) and +X (corners 1-2)
    m.strut(leg_at_z(bell_bar_z, 0), leg_at_z(bell_bar_z, 3), 0.028, "buoy_charcoal", segs=8)
    m.strut(leg_at_z(bell_bar_z, 1), leg_at_z(bell_bar_z, 2), 0.028, "buoy_charcoal", segs=8)
    p_l = leg_at_z(bell_bar_z, 0).lerp(leg_at_z(bell_bar_z, 3), 0.5)
    p_r = leg_at_z(bell_bar_z, 1).lerp(leg_at_z(bell_bar_z, 2), 0.5)
    m.strut(p_l, p_r, 0.032, "buoy_charcoal", segs=8)
    m.box((0.18, 0.16, 0.12), (0, 0, 2.40), "buoy_rust", bevel=0.01)
    # Authentic spun bell profile (crown -> waist -> sound bow -> flared lip)
    bell_prof = [
        (0.37, 1.56),
        (0.38, 1.60),
        (0.32, 1.66),
        (0.24, 1.78),
        (0.21, 1.98),
        (0.20, 2.16),
        (0.16, 2.28),
        (0.08, 2.35),
    ]
    m.lathe(bell_prof, (0, 0, 0), "buoy_bronze", segs=28, smooth=True, cap_bottom=False, cap_top=True)
    # Inner hollow rim lip for depth
    m.lathe([(0.37, 1.56), (0.33, 1.57), (0.28, 1.68)], (0, 0, 0), "buoy_bronze", segs=24, smooth=True, cap_bottom=False, cap_top=False)
    # 4 external pivoted steel striker/clapper hammers anchored directly to the 4 corner tower legs
    for c in range(4):
        leg_attach = leg_at_z(2.12, c)
        radial_dir = Vector((leg_attach.x, leg_attach.y, 0.0)).normalized()
        pivot = Vector((radial_dir.x * 0.50, radial_dir.y * 0.50, 2.12))
        strike = Vector((radial_dir.x * 0.41, radial_dir.y * 0.41, 1.64))
        m.strut(leg_attach, pivot, 0.022, "buoy_charcoal", segs=6)
        m.sphere(0.028, pivot, "buoy_charcoal", u_segs=10, v_segs=6)
        m.strut(pivot, strike, 0.016, "buoy_rust", segs=6)
        m.sphere(0.052, strike, "buoy_rust", u_segs=12, v_segs=8)

    # Access ladder climbing the -Y (front) face from deck to gallery
    lx = 0.14
    for sgn in (-1, 1):
        p0 = Vector((sgn * lx, -0.78, 0.94))
        p1 = Vector((sgn * lx, -0.44, 4.30))
        m.strut(p0, p1, 0.016, "buoy_yellow", segs=6)
    for k in range(11):
        t = (k + 0.5) / 11.0
        z = 0.94 + t * (4.30 - 0.94)
        y = -0.78 + t * (-0.44 + 0.78)
        m.strut((-lx, y, z), (lx, y, z), 0.012, "buoy_yellow", segs=6)

    # Upper service gallery deck + safety-yellow handrails (z = 4.30 .. 4.96)
    m.cylinder(0.68, 0.70, 0.06, (0, 0, 4.32), "buoy_charcoal", segs=16)
    m.cylinder(0.71, 0.71, 0.11, (0, 0, 4.37), "buoy_yellow", segs=16, cap_ends=False)
    m.torus(0.69, 0.018, (0, 0, 4.66), "buoy_yellow", major_segs=16, minor_segs=6)
    m.torus(0.69, 0.020, (0, 0, 4.96), "buoy_yellow", major_segs=16, minor_segs=6)
    for i in range(8):
        a = math.tau * i / 8.0 + math.pi / 8.0
        m.strut((math.cos(a) * 0.69, math.sin(a) * 0.69, 4.32), (math.cos(a) * 0.69, math.sin(a) * 0.69, 4.96), 0.017, "buoy_yellow", segs=6)

    # Battery/controller cabinet hung under the gallery deck on steel straps
    add_battery_box(m, (0.0, 0.12, 3.88), yaw_deg=0, size=(0.36, 0.26, 0.42))
    for sx in (-0.14, 0.14):
        m.strut((sx, 0.12, 4.08), (sx, 0.12, 4.32), 0.018, "buoy_rust", segs=6)

    # Twin angled solar collector wings on +X and -X sides of the gallery
    for sgn in (-1, 1):
        m.strut((sgn * 0.54, 0.0, 4.36), (sgn * 0.94, 0.0, 4.54), 0.024, "buoy_charcoal", segs=8)
        m.strut((sgn * 0.66, 0.0, 4.80), (sgn * 0.94, 0.0, 4.54), 0.018, "buoy_charcoal", segs=6)
        add_solar_panel(m, (sgn * 1.00, -0.04, 4.60), width=0.58, height=0.40, tilt_deg=34, yaw_deg=sgn * -12)

    # Offset octahedral radar reflector on +Y mast arm
    m.strut((0.0, 0.52, 4.34), (0.0, 0.72, 4.98), 0.022, "buoy_charcoal", segs=8)
    add_radar_reflector(m, (0.0, 0.72, 5.16), size=0.44, yaw=0.25)

    # Hero central lantern pedestal + warm-white Fresnel beacon + lightning rod
    m.cylinder(0.24, 0.19, 0.54, (0, 0, 4.60), "buoy_red", segs=18)
    m.cylinder(0.21, 0.21, 0.04, (0, 0, 4.88), "buoy_rust", segs=18)
    beacon_pt = add_fresnel_lantern(m, (0, 0, 4.90), "beacon_white", scale=1.28, cage=True)
    # Extra lightning spire above the hero lantern
    m.strut((0, 0, 5.58), (0, 0, 5.92), 0.008, "buoy_steel_bright", segs=6)

    ob = m.finish(coll)
    return ob, {"BeaconLight": beacon_pt, "MooringEye": mooring_pt}


def build_buoy_hazard_spar(coll, mats):
    """Hazard / Shoal Spar Buoy: slender yellow-and-black banded mast, bulbous float, X-cross topmark, amber strobe."""
    m = BuoyMesh("buoy_hazard_spar", mats)

    # Submerged slender ballast spar + heavy cast ballast disk + 4 stabilizing fins
    m.lathe([(0.20, -1.24), (0.24, -0.15)], (0, 0, 0), "buoy_rust", segs=20)
    m.cylinder(0.40, 0.40, 0.16, (0, 0, -1.12), "buoy_rust", segs=20)
    for i in range(4):
        a = math.tau * i / 4.0
        rot = Matrix.Rotation(a, 3, "Z")
        m.extrude_poly_y([(0.21, -1.04), (0.38, -0.94), (0.38, -0.42), (0.23, -0.30)], 0.026, (0, 0, 0), "buoy_rust", rot=rot)
    mooring_pt = add_mooring_chain(m, -1.24, links=4, link_len=0.17, link_w=0.10, wire_r=0.016)

    # Bulbous mid-float belly (safety yellow with rubber rub-rail)
    bulb_prof = [
        (0.26, -0.16),
        (0.54, 0.08),
        (0.58, 0.36),
        (0.54, 0.62),
        (0.32, 0.86),
        (0.24, 0.94),
    ]
    m.lathe(bulb_prof, (0, 0, 0), "buoy_yellow", segs=24)
    add_rub_rail(m, 0.58, 0.36, height=0.13, thick=0.055, clamps=6)
    # 3 lifting padeyes on float shoulder
    for i in range(3):
        a = math.tau * i / 3.0
        add_padeye(m, (math.cos(a) * 0.43, math.sin(a) * 0.43, 0.72), a, scale=0.78)

    # Bolted collar at spar base
    m.cylinder(0.29, 0.29, 0.045, (0, 0, 0.94), "buoy_rust", segs=20)
    add_bolt_ring(m, (0, 0, 0.965), 0.26, 8, bolt_r=0.013, bolt_h=0.016)

    # Tall tapered spar mast with alternating yellow / charcoal-black hazard bands
    band_z = [0.96, 1.48, 2.00, 2.52, 3.04, 3.58]
    band_r = [0.23, 0.21, 0.19, 0.17, 0.155, 0.14]
    band_m = ["buoy_charcoal", "buoy_yellow", "buoy_charcoal", "buoy_yellow", "buoy_charcoal"]
    for i in range(5):
        m.lathe([(band_r[i], band_z[i]), (band_r[i + 1], band_z[i + 1])], (0, 0, 0), band_m[i], segs=20, cap_bottom=False, cap_top=(i == 4))
        if i > 0:
            m.torus(band_r[i] + 0.004, 0.010, (0, 0, band_z[i]), "buoy_rust", major_segs=20, minor_segs=6)

    # 4 vertical transition fins between bulb and spar
    for i in range(4):
        a = math.tau * i / 4.0 + math.pi * 0.25
        rot = Matrix.Rotation(a, 3, "Z")
        m.extrude_poly_y([(0.22, 0.86), (0.38, 0.80), (0.21, 1.32)], 0.022, (0, 0, 0), "buoy_yellow", rot=rot)

    # 4-vane radar reflector fins wrapped around upper spar (z = 2.96..3.46)
    for i in range(4):
        a = math.tau * i / 4.0
        rot = Matrix.Rotation(a, 3, "Z")
        m.box((0.26, 0.014, 0.48), (math.cos(a) * 0.25, math.sin(a) * 0.25, 3.22), "buoy_steel_bright", rot=rot)
    # Horizontal divider disc for crisp corner-reflector cavities
    m.cylinder(0.37, 0.37, 0.014, (0, 0, 3.22), "buoy_steel_bright", segs=16)

    # Side-mounted compact battery box & vertical-tilted solar panel + armored conduit
    add_battery_box(m, (-0.24, 0.0, 2.22), yaw_deg=90, size=(0.20, 0.14, 0.26))
    m.strut((-0.24, 0.0, 2.35), (-0.34, -0.04, 2.86), 0.012, "buoy_rust", segs=6)
    m.strut((-0.17, 0.0, 2.66), (-0.34, -0.04, 2.86), 0.018, "buoy_charcoal", segs=6)
    add_solar_panel(m, (-0.36, -0.06, 2.92), width=0.34, height=0.26, tilt_deg=42, yaw_deg=18)

    # Upper collar platform + IALA St. Andrew's X-Cross hazard topmark (3D crossed blades)
    m.cylinder(0.22, 0.22, 0.04, (0, 0, 3.58), "buoy_charcoal", segs=18)
    m.strut((0, 0, 3.60), (0, 0, 4.34), 0.028, "buoy_charcoal", segs=10)
    # Crossed X blades facing both X and Y so the X reads clearly from 360 degrees
    for yaw in (0.0, math.pi * 0.5):
        for tilt in (math.radians(45), math.radians(-45)):
            rot = Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(tilt, 3, "Y")
            m.box((0.68, 0.022, 0.11), (0, 0, 3.98), "buoy_yellow", rot=rot, bevel=0.005)
    # Center hub cap where X blades intersect
    m.cylinder(0.08, 0.08, 0.09, (0, 0, 3.98), "buoy_charcoal", segs=12)

    # Compact amber strobe beacon crowning the spar
    beacon_pt = add_fresnel_lantern(m, (0, 0, 4.34), "beacon_amber", scale=0.92, cage=True)

    ob = m.finish(coll)
    return ob, {"BeaconLight": beacon_pt, "MooringEye": mooring_pt}


def build_marker_channel_port(coll, mats):
    """Fixed Port-Hand Channel Marker: concrete-sleeved steel piling, square green '3' dayboard, solar & green beacon."""
    m = BuoyMesh("marker_channel_port", mats)

    # Driven concrete/brine-crusted base sleeve (z = -1.10 .. 0.92)
    base_prof = [
        (0.32, -1.10),
        (0.32, 0.80),
        (0.24, 0.94),
    ]
    m.lathe(base_prof, (0, 0, 0), "buoy_concrete", segs=20)
    # Rusted splash-zone collar directly above concrete
    m.cylinder(0.235, 0.235, 0.42, (0, 0, 1.12), "buoy_rust", segs=20)
    # Main vertical weathered steel piling (z = 1.32 .. 4.56)
    m.cylinder(0.21, 0.20, 3.26, (0, 0, 2.94), "buoy_charcoal", segs=20)
    # Heavy bolted steel piling clamp bands
    for cz in (1.55, 2.95, 3.85):
        m.cylinder(0.23, 0.23, 0.08, (0, 0, cz), "buoy_rust", segs=20)
        m.box((0.12, 0.09, 0.07), (0.26, 0.0, cz), "buoy_rust")
        m.box((0.12, 0.09, 0.07), (-0.26, 0.0, cz), "buoy_rust")

    # Steel climbing rungs up +X side + small service footrest
    for rz in (1.10, 1.48, 1.86, 2.24, 2.62):
        m.strut((0.19, -0.13, rz), (0.33, -0.13, rz), 0.014, "buoy_rust", segs=6)
        m.strut((0.19, 0.13, rz), (0.33, 0.13, rz), 0.014, "buoy_rust", segs=6)
        m.strut((0.33, -0.13, rz), (0.33, 0.13, rz), 0.014, "buoy_rust", segs=6)

    # Horizontal steel mounting channels carrying the double-sided square dayboards
    for bz in (2.95, 3.85):
        m.box((1.34, 0.08, 0.08), (0.0, -0.24, bz), "buoy_rust", bevel=0.006)
        m.box((1.34, 0.08, 0.08), (0.0, 0.24, bz), "buoy_rust", bevel=0.006)
        # Through-bolts tying front & back channels across the pile
        m.strut((-0.26, -0.29, bz), (-0.26, 0.29, bz), 0.016, "buoy_steel_bright", segs=6)
        m.strut((0.26, -0.29, bz), (0.26, 0.29, bz), 0.016, "buoy_steel_bright", segs=6)

    # Double-sided SQUARE Port-Hand Dayboards (front -Y and back +Y)
    board_w, board_h = 1.40, 1.40
    board_z = 3.40
    for sgn_y in (-1.0, 1.0):
        by = sgn_y * 0.30
        # Steel backing plate
        m.box((board_w, 0.042, board_h), (0, by, board_z), "buoy_green", bevel=0.008)
        # Cream reflective border frame (4 cleanly butt-jointed border strips, zero corner overlap)
        bt = 0.014
        bw = 0.105
        margin = 0.03
        fy = by + sgn_y * (0.021 + bt * 0.45)
        h_span = board_w - 2.0 * margin
        v_span = board_h - 2.0 * margin - 2.0 * bw
        edge_z = board_h * 0.5 - margin - bw * 0.5
        edge_x = board_w * 0.5 - margin - bw * 0.5
        m.box((h_span, bt, bw), (0, fy, board_z + edge_z), "buoy_cream")
        m.box((h_span, bt, bw), (0, fy, board_z - edge_z), "buoy_cream")
        m.box((bw, bt, v_span), (edge_x, fy, board_z), "buoy_cream")
        m.box((bw, bt, v_span), (-edge_x, fy, board_z), "buoy_cream")
        # Channel numeral '3'
        add_stenciled_digit(m, "3", (0.0, by + sgn_y * 0.022, board_z), sgn_y, scale=1.18, mat="buoy_cream")
        # 4 corner mounting hex bolts
        for sx in (-0.54, 0.54):
            for sz in (-0.45, 0.45):
                m.cylinder(0.02, 0.02, 0.028, (sx, fy + sgn_y * 0.005, board_z + sz), "buoy_steel_bright", segs=6, rot=Matrix.Rotation(math.pi * 0.5, 3, "X"), smooth=False)

    # Battery box + conduit + angled solar panel
    add_battery_box(m, (-0.32, 0.0, 2.28), yaw_deg=90, size=(0.28, 0.22, 0.38))
    m.strut((-0.24, 0.0, 2.48), (-0.24, 0.0, 4.32), 0.015, "buoy_rust", segs=6)
    m.strut((0.0, 0.0, 4.24), (-0.44, -0.05, 4.44), 0.024, "buoy_charcoal", segs=8)
    add_solar_panel(m, (-0.48, -0.08, 4.50), width=0.52, height=0.36, tilt_deg=36, yaw_deg=15)

    # Top pile cap + caged green beacon lantern
    m.cylinder(0.25, 0.25, 0.05, (0, 0, 4.58), "buoy_rust", segs=20)
    add_bolt_ring(m, (0, 0, 4.61), 0.21, 8, bolt_r=0.013, bolt_h=0.016)
    beacon_pt = add_fresnel_lantern(m, (0, 0, 4.61), "beacon_green", scale=1.08, cage=True)

    ob = m.finish(coll)
    return ob, {"BeaconLight": beacon_pt}


def build_marker_channel_starboard(coll, mats):
    """Fixed Starboard-Hand Tripod Channel Marker: 3-leg steel tripod, triangular red '4' dayboard, solar & red beacon."""
    m = BuoyMesh("marker_channel_starboard", mats)

    # Central vertical steel piling + concrete/brine base sleeve
    m.lathe([(0.28, -1.10), (0.28, 0.62), (0.21, 0.74)], (0, 0, 0), "buoy_concrete", segs=18)
    m.cylinder(0.20, 0.20, 0.38, (0, 0, 0.92), "buoy_rust", segs=18)
    m.cylinder(0.18, 0.17, 3.60, (0, 0, 2.88), "buoy_charcoal", segs=18)

    # Two angled batter tripod legs + concrete footing sleeves + horizontal tie struts
    apex = Vector((0.0, 0.0, 2.52))
    leg_feet = [Vector((-0.98, 0.36, -1.10)), Vector((0.98, 0.36, -1.10))]
    # Third shorter rear/front brace leg for a true 3-legged tripod stance
    leg_feet.append(Vector((0.0, -0.92, -1.10)))

    for foot in leg_feet:
        # Interpolate point along batter leg at z = 0.56 for concrete sleeve
        t_conc = (0.56 - foot.z) / (apex.z - foot.z)
        conc_top = foot.lerp(apex, t_conc)
        m.strut(foot, conc_top, 0.20, "buoy_concrete", segs=14, r2=0.17)
        m.strut(conc_top, apex, 0.115, "buoy_charcoal", segs=12, r2=0.105)
        # Splash rust ring above concrete
        t_r0 = (0.54 - foot.z) / (apex.z - foot.z)
        t_r1 = (0.94 - foot.z) / (apex.z - foot.z)
        m.strut(foot.lerp(apex, t_r0), foot.lerp(apex, t_r1), 0.125, "buoy_rust", segs=12)

    # Horizontal perimeter tie-beams connecting the 3 tripod legs at z = 0.85 and z = 1.72
    for hz in (0.85, 1.72):
        pts = [foot.lerp(apex, (hz - foot.z) / (apex.z - foot.z)) for foot in leg_feet]
        for i in range(3):
            m.strut(pts[i], pts[(i + 1) % 3], 0.036, "buoy_rust", segs=8)
            m.strut(pts[i], Vector((0.0, 0.0, hz)), 0.032, "buoy_charcoal", segs=8)

    # Heavy bolted collar gusset where tripod legs meet the central mast
    m.cylinder(0.28, 0.26, 0.26, (0, 0, 2.50), "buoy_rust", segs=18)
    add_bolt_ring(m, (0, 0, 2.64), 0.23, 8, bolt_r=0.014, bolt_h=0.018)

    # Horizontal mounting channels for the triangular dayboards
    for bz, span in ((3.02, 1.24), (3.72, 0.68)):
        m.box((span, 0.075, 0.075), (0.0, -0.21, bz), "buoy_rust", bevel=0.005)
        m.box((span, 0.075, 0.075), (0.0, 0.21, bz), "buoy_rust", bevel=0.005)

    # Double-sided EQUILATERAL TRIANGLE Starboard-Hand Dayboards (front -Y and back +Y)
    tri_w = 1.62
    tri_h = 1.42
    tri_base_z = 2.82
    outer_pts = [(-tri_w * 0.5, 0.0), (tri_w * 0.5, 0.0), (0.0, tri_h)]
    # Inset border band vertices
    def inset_tri(d):
        # Equilateral-ish triangle inset
        return [
            (-tri_w * 0.5 + d * 1.72, d),
            (tri_w * 0.5 - d * 1.72, d),
            (0.0, tri_h - d * 1.98),
        ]

    b_out = inset_tri(0.055)
    b_in = inset_tri(0.155)
    for sgn_y in (-1.0, 1.0):
        by = sgn_y * 0.27
        # Red triangular steel backing plate
        m.extrude_poly_y(outer_pts, 0.042, (0, by, tri_base_z), "buoy_red")
        # Cream triangular border (3 crisp border bars around the perimeter)
        fy = by + sgn_y * 0.025
        for i in range(3):
            i1 = (i + 1) % 3
            quad = [b_out[i], b_out[i1], b_in[i1], b_in[i]]
            m.extrude_poly_y(quad, 0.014, (0, fy, tri_base_z), "buoy_cream")
        # Channel numeral '4' centered visually inside the triangle
        add_stenciled_digit(m, "4", (0.0, by + sgn_y * 0.023, tri_base_z + 0.50), sgn_y, scale=1.02, mat="buoy_cream")

    # Battery cabinet + conduit + angled solar panel
    add_battery_box(m, (0.34, 0.0, 2.24), yaw_deg=-90, size=(0.28, 0.22, 0.38))
    m.strut((0.22, 0.0, 2.44), (0.22, 0.0, 4.44), 0.015, "buoy_rust", segs=6)
    m.strut((0.0, 0.0, 4.38), (0.44, -0.05, 4.56), 0.024, "buoy_charcoal", segs=8)
    add_solar_panel(m, (0.48, -0.08, 4.62), width=0.52, height=0.36, tilt_deg=36, yaw_deg=-15)

    # Top pile cap + caged red beacon lantern
    m.cylinder(0.23, 0.23, 0.05, (0, 0, 4.68), "buoy_rust", segs=18)
    add_bolt_ring(m, (0, 0, 4.71), 0.19, 8, bolt_r=0.013, bolt_h=0.016)
    beacon_pt = add_fresnel_lantern(m, (0, 0, 4.71), "beacon_red", scale=1.08, cage=True)

    ob = m.finish(coll)
    return ob, {"BeaconLight": beacon_pt}


def build_buoy_traffic_separation(coll, mats):
    """USCG Traffic Separation Scheme Lighted Buoy ('SC'): all-yellow pontoon with dark antifouling waterline,
    heavy arched deck lifting lugs, 4-leg yellow lattice around central battery riser, tall square 'SC' daymark box,
    low domed roof cap, and amber Fresnel beacon."""
    m = BuoyMesh("buoy_traffic_separation", mats)

    # Submerged counterweight skirt, central ballast tube, 4 anti-roll fins, and anchor chain stub
    sub_prof = [
        (0.36, -1.35),
        (0.42, -1.30),
        (0.42, -0.60),
        (0.80, -0.34),
        (1.26, 0.02),
    ]
    m.lathe(sub_prof, (0, 0, 0), "buoy_antifouling", segs=24)
    for i in range(4):
        a = math.tau * i / 4.0 + math.pi * 0.25
        rot = Matrix.Rotation(a, 3, "Z")
        m.extrude_poly_y(
            [(0.40, -1.24), (0.66, -1.10), (0.66, -0.58), (0.40, -0.50)],
            0.032,
            (0, 0, 0),
            "buoy_rust",
            rot=rot,
        )
    mooring_pt = add_mooring_chain(m, -1.35, links=5, link_len=0.22, link_w=0.13, wire_r=0.022)

    # Wide cylindrical pontoon float: dark oxide/antifouling waterline boot-top + chunky safety-yellow drum
    m.lathe([(1.28, 0.00), (1.29, 0.25)], (0, 0, 0), "buoy_antifouling", segs=28, cap_bottom=False, cap_top=False)
    m.lathe(
        [(1.29, 0.25), (1.29, 0.79), (1.23, 0.85), (0.01, 0.87)],
        (0, 0, 0),
        "buoy_yellow",
        segs=28,
        cap_bottom=False,
        cap_top=True,
    )
    # Subtle welded chime rim around the pontoon deck perimeter
    m.torus(1.23, 0.022, (0, 0, 0.855), "buoy_yellow", major_segs=28, minor_segs=6)

    # 4 prominent heavy arched yellow steel lifting lugs around the pontoon deck rim (matching photo silhouette)
    for i in range(4):
        a = math.tau * i / 4.0
        px, py = math.cos(a) * 1.07, math.sin(a) * 1.07
        rot = Matrix.Rotation(a, 3, "Z")
        # Welded doubling pad under each lug
        m.box((0.28, 0.14, 0.028), (px, py, 0.865), "buoy_yellow", rot=rot, bevel=0.004)
        # Tall arched lifting eye with circular shackle bore facing tangentially
        m.arched_lug((px, py, 0.87), a, base_w=0.25, arch_r=0.115, z_center=0.165, thick=0.056, hole_r=0.054, mat="buoy_yellow")

    # Small recessed deck inspection hatch beside the central riser
    add_deck_hatch(m, (0.0, -0.94, 0.855), radius=0.14, mat="buoy_yellow")

    # Open 4-legged yellow steel lattice tower (z = 0.86 .. 2.84)
    z_levels = [0.86, 1.54, 2.20, 2.84]
    half_spans = [0.74, 0.725, 0.71, 0.695]

    def leg_pt(lv, corner_idx):
        sx = -1.0 if corner_idx in (0, 3) else 1.0
        sy = -1.0 if corner_idx in (0, 1) else 1.0
        return Vector((sx * half_spans[lv], sy * half_spans[lv], z_levels[lv]))

    # Corner foot plates + 4 stout vertical-ish yellow legs
    for c in range(4):
        base = leg_pt(0, c)
        m.box((0.22, 0.22, 0.045), base + Vector((0, 0, 0.015)), "buoy_yellow", bevel=0.006)
        add_bolt_ring(m, base + Vector((0, 0, 0.042)), 0.08, 4, bolt_r=0.014, bolt_h=0.018, mat="buoy_rust")
        for lv in range(len(z_levels) - 1):
            m.strut(leg_pt(lv, c), leg_pt(lv + 1, c), 0.048, "buoy_yellow", segs=8)

    # Horizontal perimeter beams at each tower level
    for lv in (1, 2, 3):
        for c in range(4):
            c1 = (c + 1) % 4
            m.strut(leg_pt(lv, c), leg_pt(lv, c1), 0.032, "buoy_yellow", segs=6)

    # Central yellow cylindrical battery pocket / counterweight column inside lower lattice (z = 0.86 .. 1.94)
    m.cylinder(0.32, 0.32, 0.05, (0, 0, 0.885), "buoy_yellow", segs=20)
    add_bolt_ring(m, (0, 0, 0.915), 0.28, 8, bolt_r=0.013, bolt_h=0.016, mat="buoy_rust")
    m.lathe(
        [(0.25, 0.90), (0.25, 1.84), (0.28, 1.86), (0.28, 1.90), (0.23, 1.94), (0.01, 1.95)],
        (0, 0, 0),
        "buoy_yellow",
        segs=20,
    )
    add_bolt_ring(m, (0, 0, 1.91), 0.25, 8, bolt_r=0.011, bolt_h=0.015, mat="buoy_rust")

    # Radial bracing & gusset arms tying the central battery column solidly to all 4 tower legs
    for c in range(4):
        p_leg_low = leg_pt(0, c).lerp(leg_pt(1, c), 0.60)
        p_leg_mid = leg_pt(1, c)
        p_leg_hi = leg_pt(2, c)
        rad = Vector((p_leg_mid.x, p_leg_mid.y, 0.0)).normalized()
        col_low = Vector((rad.x * 0.23, rad.y * 0.23, 1.24))
        col_hi = Vector((rad.x * 0.23, rad.y * 0.23, 1.72))
        m.strut(col_low, p_leg_mid, 0.026, "buoy_yellow", segs=6)
        m.strut(col_hi, p_leg_low, 0.024, "buoy_yellow", segs=6)
        m.strut(col_hi, p_leg_hi, 0.024, "buoy_yellow", segs=6)
        # Side horizontal tie collar ring around central column
        c1 = (c + 1) % 4
        # Lower bay corner knee braces on outer perimeter
        m.strut(leg_pt(0, c), leg_pt(1, c).lerp(leg_pt(1, c1), 0.45), 0.024, "buoy_yellow", segs=6)
        m.strut(leg_pt(0, c1), leg_pt(1, c1).lerp(leg_pt(1, c), 0.45), 0.024, "buoy_yellow", segs=6)

    # Crisp yellow X-bracing on middle bay (lv 1..2) and upper open bay (lv 2..3)
    for lv in (1, 2):
        for c in range(4):
            c1 = (c + 1) % 4
            a0, a1 = leg_pt(lv, c), leg_pt(lv, c1)
            b0, b1 = leg_pt(lv + 1, c), leg_pt(lv + 1, c1)
            m.strut(a0, b1, 0.022, "buoy_yellow", segs=6)
            m.strut(a1, b0, 0.022, "buoy_yellow", segs=6)

    # Vertical maintenance ladder on +X face of lattice tower
    lx = 0.745
    for sy in (-0.15, 0.15):
        m.strut((lx, sy, 0.90), (0.715, sy, 2.84), 0.015, "buoy_yellow", segs=6)
    for k in range(6):
        t = (k + 0.5) / 6.0
        z = 0.90 + t * (2.84 - 0.90)
        x = lx + t * (0.715 - lx)
        m.strut((x, -0.15, z), (x, 0.15, z), 0.012, "buoy_yellow", segs=6)

    # Tall square yellow upper superstructure / daymark box (z = 2.84 .. 4.78, width 1.44 m)
    box_z0, box_z1 = 2.84, 4.78
    box_zmid = 0.5 * (box_z0 + box_z1)  # 3.81
    box_h = box_z1 - box_z0  # 1.94
    core_w = 1.34
    frame_half = 0.695

    # Recessed solid inner yellow box core
    m.box((core_w, core_w, box_h - 0.02), (0, 0, box_zmid), "buoy_yellow")

    # 4 vertical corner frame angle-posts standing proud of the recessed panels
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            m.box((0.088, 0.088, box_h + 0.02), (sx * frame_half, sy * frame_half, box_zmid), "buoy_yellow", bevel=0.006)

    # 3 horizontal perimeter trim bands: bottom sill, prominent mid-height divider, top cornice rail
    for rz, rh in ((box_z0 + 0.03, 0.072), (box_zmid, 0.074), (box_z1 - 0.025, 0.072)):
        for sgn in (-1.0, 1.0):
            m.box((1.46, 0.068, rh), (0, sgn * frame_half, rz), "buoy_yellow", bevel=0.005)
            m.box((0.068, 1.46, rh), (sgn * frame_half, 0, rz), "buoy_yellow", bevel=0.005)

    # All 4 outward faces: upper "SC" daymark panel (z = 3.85..4.73) & lower stiffener trim
    panel_w = 1.28
    panel_h = 0.86
    upper_panel_z = 0.5 * (box_zmid + 0.037 + box_z1 - 0.061)  # ~4.28
    lower_panel_z = 0.5 * (box_z0 + 0.066 + box_zmid - 0.037)  # ~3.34
    panel_offset = core_w * 0.5 + 0.006  # 0.676 m, cleanly recessed inside 0.729 m frame face
    for i in range(4):
        yaw = math.tau * i / 4.0
        rot = Matrix.Rotation(yaw, 3, "Z")
        xf = Matrix.Translation(rot @ Vector((0.0, -panel_offset, upper_panel_z))) @ rot.to_4x4()
        m.solar_face(panel_w, panel_h, xf, mat="buoy_yellow")  # blank: the game letters each one
        # Subtle vertical center stiffening seam & corner bolts on lower panel
        m.box((0.024, 0.016, panel_h - 0.04), rot @ Vector((0.0, -panel_offset, lower_panel_z)), "buoy_yellow", rot=rot)
        for bx in (-0.54, 0.54):
            for bz in (-0.34, 0.34):
                m.cylinder(
                    0.013,
                    0.013,
                    0.016,
                    rot @ Vector((bx, -panel_offset - 0.006, lower_panel_z + bz)),
                    "buoy_rust",
                    segs=6,
                    rot=rot @ Matrix.Rotation(math.pi * 0.5, 3, "X"),
                    smooth=False,
                )

    # Gently domed yellow roof cap & cornice drip-lip (z = 4.78 .. 4.98)
    m.box((1.50, 1.50, 0.042), (0, 0, 4.795), "buoy_yellow", bevel=0.008)
    roof_prof = [
        (0.73, 4.81),
        (0.64, 4.89),
        (0.44, 4.95),
        (0.22, 4.98),
    ]
    m.lathe(roof_prof, (0, 0, 0), "buoy_yellow", segs=16, cap_bottom=True, cap_top=True)

    # Compact low-profile solar panels mounted cleanly on short brackets above the sloped roof crown (+Y and -Y)
    for sgn, yaw_d in ((-1.0, 0.0), (1.0, 180.0)):
        for bx in (-0.16, 0.16):
            m.strut((bx, sgn * 0.46, 4.88), (bx, sgn * 0.46, 5.01), 0.015, "buoy_charcoal", segs=6)
        add_solar_panel(m, (0.0, sgn * 0.48, 5.03), width=0.46, height=0.22, tilt_deg=18.0, yaw_deg=yaw_d)

    # Small corner radar/GPS sensor turret + stainless whip on -X/-Y roof edge
    m.cylinder(0.055, 0.048, 0.16, (-0.56, -0.56, 4.88), "buoy_charcoal", segs=10)
    m.sphere(0.052, (-0.56, -0.56, 4.97), "buoy_charcoal", u_segs=10, v_segs=6)
    m.strut((-0.56, -0.56, 4.98), (-0.56, -0.56, 5.34), 0.007, "buoy_steel_bright", segs=6)

    # Central compact marine amber beacon lantern (USCG Special Purpose Traffic Separation flashes yellow/amber)
    m.cylinder(0.18, 0.16, 0.08, (0, 0, 5.01), "buoy_charcoal", segs=16)
    beacon_pt = add_fresnel_lantern(m, (0, 0, 5.05), "beacon_amber", scale=0.84, cage=True)

    ob = m.finish(coll)
    return ob, {"BeaconLight": beacon_pt, "MooringEye": mooring_pt}


ASSETS = [
    ("buoy_port_can", build_buoy_port_can, -7.2),
    ("buoy_starboard_nun", build_buoy_starboard_nun, -4.4),
    ("buoy_hazard_spar", build_buoy_hazard_spar, -1.8),
    ("buoy_bell_tower", build_buoy_bell_tower, 1.4),
    ("marker_channel_port", build_marker_channel_port, 5.0),
    ("marker_channel_starboard", build_marker_channel_starboard, 8.2),
    ("buoy_traffic_separation", build_buoy_traffic_separation, 11.8),
]


# ------------------------------------------------------------------ export & preview

def _reset_scene():
    sc = bpy.data.scenes.get(SCENE_NAME)
    if sc is None:
        sc = bpy.data.scenes.new(SCENE_NAME)
    for ob in list(sc.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for c in list(sc.collection.children_recursive):
        bpy.data.collections.remove(c)
    if bpy.context.window is not None:
        bpy.context.window.scene = sc
    sc.unit_settings.system = "METRIC"
    return sc


def export_asset(sc, name, root_ob, empties):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, name + ".glb")
    saved_loc = root_ob.location.copy()
    root_ob.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    sel = {root_ob, *empties}
    for o in sc.objects:
        o.select_set(o in sel)
    bpy.context.view_layer.objects.active = root_ob
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        use_active_scene=True,
        export_apply=True,
        export_yup=True,
        export_cameras=False,
        export_lights=False,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )

    root_ob.location = saved_loc
    bpy.context.view_layer.update()
    return out_path


def render_previews(sc, render_dir, only_asset=None):
    os.makedirs(render_dir, exist_ok=True)

    # Create translucent brine waterline plane at Z=0 & seabed below Z=-1.45
    bpy.ops.mesh.primitive_plane_add(size=80.0, location=(2.5, 0.0, -1.45))
    bed = bpy.context.active_object
    bed.name = "_pv_bed"
    bed.data.materials.append(_make_solid_mat("_pv_bed_mat", (0.68, 0.48, 0.34), metallic=0.0, roughness=0.92))

    # Subtle translucent water surface at Z = 0.0
    bpy.ops.mesh.primitive_plane_add(size=80.0, location=(2.5, 0.0, 0.0))
    water = bpy.context.active_object
    water.name = "_pv_water"
    wm = bpy.data.materials.new("_pv_water_mat")
    _ensure_nodes(wm)
    bsdf = next(n for n in wm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*srgb_to_linear((0.18, 0.28, 0.34)), 1.0)
    bsdf.inputs["Roughness"].default_value = 0.22
    bsdf.inputs["Alpha"].default_value = 0.72
    water.data.materials.append(wm)

    # Lighting: warm Pacific afternoon sun + cool sky fill
    sun = bpy.data.objects.new("_pv_sun", bpy.data.lights.new("_pv_sun", "SUN"))
    sun.data.energy = 4.2
    sun.data.color = (1.0, 0.94, 0.84)
    sun.data.angle = math.radians(1.5)
    sun.rotation_euler = (math.radians(52), math.radians(10), math.radians(-38))
    sc.collection.objects.link(sun)

    fill = bpy.data.objects.new("_pv_fill", bpy.data.lights.new("_pv_fill", "SUN"))
    fill.data.energy = 1.2
    fill.data.color = (0.74, 0.86, 1.0)
    fill.rotation_euler = (math.radians(65), 0.0, math.radians(135))
    sc.collection.objects.link(fill)

    world = bpy.data.worlds.new("_pv_world")
    _ensure_nodes(world)
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*srgb_to_linear((0.68, 0.74, 0.80)), 1.0)
    bg.inputs[1].default_value = 0.75
    sc.world = world

    cam_data = bpy.data.cameras.new("_pv_cam")
    cam_data.lens = 42.0
    cam_data.clip_end = 250.0
    cam = bpy.data.objects.new("_pv_cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam

    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 36
    sc.cycles.use_denoising = True
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 720

    if only_asset == "buoy_traffic_separation":
        cx = 11.8
        shots = [
            ("ts_01_ref_angle.png", (cx + 5.8, -11.5, 2.5), (cx, 0.0, 2.75), 42.0, True),
            ("ts_02_front_34.png", (cx - 6.8, -10.8, 3.6), (cx, 0.0, 2.75), 42.0, True),
            ("ts_03_back_34.png", (cx + 6.8, 10.8, 3.8), (cx, 0.0, 2.75), 42.0, True),
            ("ts_04_upper_detail.png", (cx + 3.2, -5.2, 4.65), (cx, 0.0, 4.55), 44.0, True),
            ("ts_05_submerged.png", (cx + 7.2, -11.2, 1.8), (cx, 0.0, 1.9), 38.0, False),
        ]
    else:
        shots = [
            ("01_lineup.png", (2.2, -25.0, 5.0), (2.2, 0.0, 2.3), 36.0, True),
            ("02_buoys_close.png", (-5.0, -8.2, 2.7), (-4.5, 0.0, 1.75), 44.0, True),
            ("03_bell_tower_close.png", (4.8, -6.2, 3.6), (1.4, 0.0, 2.85), 44.0, True),
            ("04_markers_close.png", (6.3, -8.2, 3.4), (6.6, 0.0, 2.85), 44.0, True),
            ("05_submerged_keels.png", (-1.8, -11.5, 1.6), (-1.8, 0.0, 0.6), 44.0, False),
            ("06_gameplay_50deg.png", (2.2, -16.0, 18.0), (2.2, 0.0, 1.5), 36.0, True),
            ("07_traffic_separation_close.png", (11.8 + 5.8, -11.5, 2.5), (11.8, 0.0, 2.75), 42.0, True),
        ]
    rendered = []
    for fname, eye, aim, lens, show_water in shots:
        water.hide_render = not show_water
        cam_data.lens = lens
        cam.location = eye
        cam.rotation_euler = (Vector(aim) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        out = os.path.join(render_dir, fname)
        sc.render.filepath = out
        bpy.ops.render.render(write_still=True, scene=sc.name)
        rendered.append(out)

    # Clean up temporary preview helpers before saving the clean .blend
    for ob in (bed, water, sun, fill, cam):
        bpy.data.objects.remove(ob, do_unlink=True)
    return rendered


def build(render_dir=None, only_asset=None):
    sc = _reset_scene()
    tex_paths = generate_textures()
    mats = build_materials(tex_paths)

    results = {}
    for name, fn, x_pos in ASSETS:
        coll = bpy.data.collections.new(name)
        sc.collection.children.link(coll)
        root_ob, empty_map = fn(coll, mats)
        root_ob.location = (x_pos, 0.0, 0.0)
        empties = []
        for ename, epos in empty_map.items():
            e = bpy.data.objects.new(ename, None)
            e.empty_display_type = "PLAIN_AXES"
            e.empty_display_size = 0.25
            e.location = epos
            e.parent = root_ob
            coll.objects.link(e)
            empties.append(e)

        if only_asset is None or name == only_asset:
            glb_path = export_asset(sc, name, root_ob, empties)
            tris = sum(len(p.vertices) - 2 for p in root_ob.data.polygons)
            results[name] = {
                "tris": tris,
                "mats": len(root_ob.data.materials),
                "glb": glb_path,
                "size_kb": round(os.path.getsize(glb_path) / 1024.0, 1),
            }

    rendered = []
    if render_dir:
        rendered = render_previews(sc, render_dir, only_asset=only_asset)

    # Pack textures into the .blend so opening it anywhere displays materials intact
    try:
        bpy.ops.file.pack_all()
    except Exception:
        pass
    os.makedirs(os.path.dirname(BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH, copy=True)
    return results, rendered


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if "--high" in argv:
        HIGH_DETAIL = True
    rdir = argv[argv.index("--render") + 1] if "--render" in argv else None
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    res, rendered = build(rdir, only_asset=only)
    for k, v in res.items():
        print(f"ASSET {k}: {v['tris']} tris, {v['mats']} mats, {v['size_kb']} KB -> {v['glb']}")
    if rendered:
        print("RENDERED", rendered)
