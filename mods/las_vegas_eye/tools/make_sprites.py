#!/usr/bin/env python3
"""
Generate the Las Vegas Eye (the Sphere showing its eyeball display) house
sprites (8bpp, normal zoom) and the NML source.

The dome is ray-cast in OpenTTD's isometric projection. Each screen pixel is
traced to the point it hits on the sphere, and the pixel goes into the sprite
of the tile that point stands on. So the dome is split cleanly across the four
tiles of a 2x2 house, and every tile's pixels sit inside its own bounding box.

    python3 mods/las_vegas_eye/tools/make_sprites.py

Outputs:
    mods/las_vegas_eye/gfx/las_vegas_eye.png   sprite sheet (TTD palette)
    mods/las_vegas_eye/gfx/preview.png         3x preview of the assembled house
    mods/las_vegas_eye/las_vegas_eye.nml       NML source (generated, do not edit)

Scale: OpenTTD's projection draws one horizontal world unit as 2 px across and
one height unit as 1 px. To look round on screen, the sphere is an ellipsoid
whose vertical radius is sqrt(6) times its horizontal one. Houses can be at
most 2x2 tiles, so the dome is inscribed in that 32x32 footprint (radius 16).
That makes it about 90 px across. The real Sphere is 157 m wide and 112 m
tall, so its centre sits below half height, and the visible dome is a little
wider than it is tall.
"""

import math
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------------------
# Geometry (house coordinates: the 2x2 house spans 0..32 in x and y)
# ---------------------------------------------------------------------------
RH = 15.75                     # horizontal radius, world units
RZ = RH * math.sqrt(6)         # vertical radius, px (makes the outline a circle)
CX = CY = 16.0                 # centre of the 2x2 footprint
CZ = RZ * 0.43                 # 112 m tall out of 157 m diameter
TOP = int(math.ceil(CZ + RZ))

# Palette indices (TTD palette). Avoids company colours (80-87, 198-205)
# and animated colours (>= 217).
SCLERA = (40, 10, 11, 12, 13, 14, 15)       # dark limb -> bright highlight
IRIS = (145, 146, 147, 148, 149, 150, 151)  # outer ring -> inner glow
PUPIL = 136
GLINT = 15
VEIN = 162


def norm(v):
    m = math.sqrt(sum(c * c for c in v))
    return tuple(c / m for c in v)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


# Directions in the sphere's normalised space (x/RH, y/RH, z/RZ).
VIEW = norm((1 / RH, 1 / RH, 2 / RZ))              # towards the viewer
SCREEN_UP = norm((-0.5 / RH, -0.5 / RH, 1 / RZ))   # roughly "up" on screen
SCREEN_LEFT = norm((1, -1, 0))                     # "left" on screen
LIGHT = norm(tuple(VIEW[i] + 0.7 * SCREEN_UP[i] + 0.6 * SCREEN_LEFT[i] for i in range(3)))
GAZE = norm(tuple(VIEW[i] + 0.12 * SCREEN_UP[i] + 0.10 * SCREEN_LEFT[i] for i in range(3)))
GLINT_DIR = norm(tuple(GAZE[i] + 0.16 * SCREEN_UP[i] + 0.16 * SCREEN_LEFT[i] for i in range(3)))


def proj(x, y, z):
    """OpenTTD RemapCoords at normal zoom."""
    return 2 * (y - x), (x + y) - z


def hit(uc, vc):
    """Front-most point of the dome under screen point (uc, vc), or None."""
    # Points on the ray: (x0 + t, y0 + t, 2t), starting on the ground plane.
    x0, y0 = (vc - uc / 2) / 2, (vc + uc / 2) / 2
    ax, ay, az = (x0 - CX) / RH, (y0 - CY) / RH, (0 - CZ) / RZ
    dx, dy, dz = 1 / RH, 1 / RH, 2 / RZ
    a = dx * dx + dy * dy + dz * dz
    b = 2 * (ax * dx + ay * dy + az * dz)
    c = ax * ax + ay * ay + az * az - 1
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    t = (-b + math.sqrt(disc)) / (2 * a)            # the viewer is at +t
    x, y, z = x0 + t, y0 + t, 2 * t
    if z < 0:
        return None                                  # below ground
    return x, y, z


def shade(x, y, z):
    s = ((x - CX) / RH, (y - CY) / RH, (z - CZ) / RZ)
    g = dot(s, GAZE)
    if g > math.cos(math.radians(11)):
        return GLINT if dot(s, GLINT_DIR) > math.cos(math.radians(3.2)) else PUPIL
    if g > math.cos(math.radians(27)):
        # Iris: brighter towards the pupil, dark rim at the edge.
        ang = math.degrees(math.acos(min(1, g)))
        if ang > 25:
            return IRIS[0]
        k = (ang - 11) / 14                        # 0 at the pupil, 1 at the rim
        idx = int(round((1 - k) * (len(IRIS) - 2))) + 1
        if dot(s, GLINT_DIR) > math.cos(math.radians(3.2)):
            return GLINT
        return IRIS[max(1, min(len(IRIS) - 1, idx))]
    # Sclera, lit from the upper left, darker towards the limb.
    facing = dot(s, VIEW)
    b = dot(s, LIGHT)
    if facing < 0.18:
        return SCLERA[0]
    # A few faint veins radiating from the iris.
    ang = math.atan2(dot(s, SCREEN_UP), dot(s, SCREEN_LEFT))
    if 0.45 < g < 0.72 and abs(math.sin(ang * 5 + 0.4)) < 0.035:
        return VEIN
    idx = int(round((b + 1) / 2 * (len(SCLERA) - 2))) + 1
    return SCLERA[max(1, min(len(SCLERA) - 1, idx))]


# ---------------------------------------------------------------------------
# Rasterise and split per tile
# ---------------------------------------------------------------------------
TILES = {  # house tile name -> (tx, ty)
    'north': (0, 0),
    'east': (0, 1),
    'west': (1, 0),
    'south': (1, 1),
}


def render():
    per_tile = {name: {} for name in TILES}
    by_xy = {v: k for k, v in TILES.items()}
    u_r = int(2 * math.sqrt(2) * RH) + 2
    _, v_c = proj(CX, CY, CZ)
    v_r = int(math.sqrt(2 * RH * RH + RZ * RZ)) + 2
    for u in range(-u_r, u_r + 1):
        for v in range(int(v_c) - v_r, int(v_c) + v_r + 1):
            p = hit(u + 0.5, v + 0.5)
            if p is None:
                continue
            x, y, z = p
            tx, ty = min(1, max(0, int(x // 16))), min(1, max(0, int(y // 16)))
            name = by_xy[(tx, ty)]
            bu, bv = proj(tx * 16, ty * 16, 0)
            per_tile[name][(u - bu, v - bv)] = shade(x, y, z)
    return per_tile


def crop(px):
    if not px:
        im = Image.new('P', (1, 1), 0)
        return im, 0, 0
    us = [p[0] for p in px]
    vs = [p[1] for p in px]
    u0, v0 = min(us), min(vs)
    im = Image.new('P', (max(us) - u0 + 1, max(vs) - v0 + 1), 0)
    for (u, v), c in px.items():
        im.putpixel((u - u0, v - v0), c)
    return im, u0, v0


def main():
    palette = Image.open(os.path.join(HERE, 'ttd_palette.png')).getpalette()[:768]
    per_tile = render()

    pad = 4
    images = []
    for name in ('north', 'west', 'east', 'south'):
        im, xrel, yrel = crop(per_tile[name])
        images.append((name, im, xrel, yrel))
    sheet = Image.new('P', (sum(im.width + pad for _, im, _, _ in images) + pad,
                            max(im.height for _, im, _, _ in images) + 2 * pad), 0)
    sheet.putpalette(palette)
    entries = {}
    x = pad
    for name, im, xrel, yrel in images:
        sheet.paste(im, (x, pad))
        entries[name] = (x, pad, im.width, im.height, xrel, yrel)
        x += im.width + pad
    sheet.save(os.path.join(ROOT, 'gfx', 'las_vegas_eye.png'), optimize=True)

    write_preview(sheet, entries)
    write_nml(entries)
    for name, e in entries.items():
        print(f'{name:6s} sheet=({e[0]},{e[1]}) size={e[2]}x{e[3]} rel=({e[4]},{e[5]})')
    print(f'radius {RH} units, vertical radius {RZ:.1f} px, centre z {CZ:.1f}, top {TOP} px')


def write_preview(sheet, entries):
    W, H = 200, 150
    org = (W // 2, H - 75)
    prev = Image.new('RGB', (W, H), (0, 0, 255))
    d = ImageDraw.Draw(prev)
    for (tx, ty) in TILES.values():
        pts = [proj(tx * 16 + a, ty * 16 + b, 0) for a, b in ((0, 0), (16, 0), (16, 16), (0, 16))]
        d.polygon([(org[0] + p[0], org[1] + p[1]) for p in pts], fill=(168, 168, 168), outline=(132, 132, 132))
    for name in ('north', 'west', 'east', 'south'):
        x, y, w, h, xrel, yrel = entries[name]
        tx, ty = TILES[name]
        spr = sheet.crop((x, y, x + w, y + h))
        bu, bv = proj(tx * 16, ty * 16, 0)
        mask = spr.point(lambda p: 255 if p else 0, 'L')
        prev.paste(spr.convert('RGB'), (org[0] + bu + xrel, org[1] + bv + yrel), mask)
    prev.resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(ROOT, 'gfx', 'preview.png'))


NML = """\
/*
 * Las Vegas Eye (the Sphere with its eyeball display) - a 2x2 town building for OpenTTD.
 *
 * GENERATED by tools/make_sprites.py - edit that script, not this file.
 */

grf {{
    grfid:       "TT\\01\\03";
    name:        string(STR_GRF_NAME);
    desc:        string(STR_GRF_DESC);
    version:     1;
    min_compatible_version: 1;
}}

cargotable {{ PASS, MAIL, GOOD }}

/* ---- Sprites: the dome, split by the tile each pixel stands on ------- */
{spritesets}

/* ---- Layouts: one per tile of the 2x2 house -------------------------- */
{layouts}

switch (FEAT_HOUSES, SELF, sw_las_vegas_eye_tile, house_tile) {{
    HOUSE_TILE_NORTH: layout_north;
    HOUSE_TILE_WEST:  layout_west;
    HOUSE_TILE_EAST:  layout_east;
    HOUSE_TILE_SOUTH: layout_south;
}}

item (FEAT_HOUSES, las_vegas_eye, -1, HOUSE_SIZE_2X2) {{
    property {{
        substitute:              0x14; /* stadium (a 2x2 base house) */
        building_flags:          bitmask(HOUSE_FLAG_NOT_SLOPED, HOUSE_FLAG_PROTECTED);
        name:                    string(STR_LAS_VEGAS_EYE);
        years_available:         [2023, 65535];
        minimum_lifetime:        255;
        /* An arena: lots of visitors, little mail. */
        population:              200;
        mail_multiplier:         40;
        accepted_cargos:         [[PASS, 8], [MAIL, 4], [GOOD, 8]];
        local_authority_impact:  500;
        removal_cost_multiplier: 255;
        /* Never grown by towns: placed by hand with the house picker only. */
        probability:             0;
        building_class:          0;
        /* Listed under "town centre" in the house picker; temperate, sub-arctic and sub-tropical. */
        availability_mask:       [bitmask(4), bitmask(CLIMATE_TEMPERATE, CLIMATE_ARCTIC, CLIMATE_TROPIC)];
    }}
    graphics {{
        sw_las_vegas_eye_tile;
    }}
}}
"""


def write_nml(entries):
    sets, lays = [], []
    for name, (x, y, w, h, xrel, yrel) in entries.items():
        sets.append(
            f'spriteset (spr_{name}, "gfx/las_vegas_eye.png") {{ [{x}, {y}, {w}, {h}, {xrel}, {yrel}] }}')
        lays.append(f"""spritelayout layout_{name} {{
    ground {{ sprite: GROUNDSPRITE_CONCRETE; }}
    building {{
        sprite: spr_{name};
        xoffset: 0; yoffset: 0; zoffset: 0;
        xextent: 16; yextent: 16; zextent: {TOP};
    }}
}}""")
    with open(os.path.join(ROOT, 'las_vegas_eye.nml'), 'w') as f:
        f.write(NML.format(spritesets='\n'.join(sets), layouts='\n\n'.join(lays)))


if __name__ == '__main__':
    main()
