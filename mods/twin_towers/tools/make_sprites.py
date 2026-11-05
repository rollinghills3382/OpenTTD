#!/usr/bin/env python3
"""
Generate the Twin Towers house sprites (8bpp, normal zoom) and the NML source.

The towers are drawn procedurally in OpenTTD's isometric projection so that
every pixel lines up exactly with the bounding boxes used in the sprite
layouts. Run from anywhere:

    python3 mods/twin_towers/tools/make_sprites.py

Outputs:
    mods/twin_towers/gfx/twin_towers.png   sprite sheet (TTD palette)
    mods/twin_towers/gfx/preview.png       4x preview of the assembled 2x2 house
    mods/twin_towers/twin_towers.nml       NML source (generated, do not edit)

Scale reference (OpenGFX / original base set, normal zoom):
    * a tile is 64 x 32 px; one world unit of height = 1 px
    * the tallest base-set houses (tall office blocks) have a bounding box
      height of 100-110 px and sprites up to 149 px tall
    * OpenTTD only redraws up to MAX_BUILDING_PIXELS (200 px) above a tile's
      north corner, so nothing may poke out higher than that
The towers are TOWER_H px tall (about 1.6x the tallest base-set office), with
the North Tower's antenna topping out just under the 200 px redraw limit.
"""

import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
TOWER_H = 172          # roof height in px (= world z units)
TOWER_OFS = 2          # tower footprint offset inside the 16x16 tile
TOWER_SIZE = 12        # tower footprint (12x12 of 16x16 units)
ANTENNA_H = 40         # antenna height above the roof

# Palette indices (TTD palette). Steel blue-grey ramp 16..23, greys 10..15.
# Avoids company colours (80-87, 198-205) and animated colours (>= 217).
LEFT = dict(light=22, dark=19, band=18, glass=17, parapet=21, edge=23, lobby=20)
RIGHT = dict(light=20, dark=17, band=16, glass=16, parapet=19, edge=21, lobby=18)
ROOF, ROOF_EDGE = 13, 11
MECH_TOP, MECH_L, MECH_R = 12, 11, 33
MAST_L, MAST_R, MAST_TIP = 14, 40, 164
CONC_TOP, CONC_L, CONC_R = 12, 11, 33
WATER = (147, 148, 149)
BRONZE = (60, 61, 62, 63, 64, 65, 66)
BUSH = (90, 91, 92, 93, 94)


def proj(x, y, z):
    """OpenTTD RemapCoords at normal zoom."""
    return 2 * (y - x), (x + y) - z


class Canvas:
    """Sparse pixel canvas in screen coordinates relative to the tile's north corner."""

    def __init__(self):
        self.px = {}

    def put(self, u, v, c):
        self.px[(u, v)] = c

    def box(self, ox, oy, oz, sx, sy, sz, shade):
        """
        Paint a solid box. shade(face, col, row, ncols, nrows) -> palette index,
        face in 'top'/'left'/'right'. col counts pixels from the face's left
        edge on screen, row counts pixels up from the box's bottom (z).
        """
        x1, y1 = ox + sx, oy + sy
        u_min, _ = proj(x1, oy, 0)
        u_max, _ = proj(ox, y1, 0)
        u_front, _ = proj(x1, y1, 0)
        v_top = (ox + oy) - (oz + sz)
        v_bot = (x1 + y1) - oz
        for u in range(u_min, u_max):
            for v in range(v_top - 1, v_bot + 1):
                uc, vc = u + 0.5, v + 0.5
                # Top face: z = oz+sz, solve for x, y.
                s = vc + oz + sz          # x + y
                d = uc / 2.0              # y - x
                tx, ty = (s - d) / 2.0, (s + d) / 2.0
                if ox <= tx < x1 and oy <= ty < y1:
                    rows = sx + sy
                    self.put(u, v, shade('top', int(tx - ox), int(ty - oy), sx, sy))
                    continue
                if uc < u_front:
                    # Left (south-west) face: x = x1.
                    y = x1 + uc / 2.0
                    z = x1 + y - vc
                    if oy <= y < y1 and oz <= z < oz + sz:
                        self.put(u, v, shade('left', u - u_min, int(z - oz), u_front - u_min, sz))
                else:
                    # Right (south-east) face: y = y1.
                    x = y1 - uc / 2.0
                    z = x + y1 - vc
                    if ox <= x < x1 and oz <= z < oz + sz:
                        self.put(u, v, shade('right', u - u_front, int(z - oz), u_max - u_front, sz))

    def crop(self):
        us = [p[0] for p in self.px]
        vs = [p[1] for p in self.px]
        u0, v0 = min(us), min(vs)
        w, h = max(us) - u0 + 1, max(vs) - v0 + 1
        im = Image.new('P', (w, h), 0)
        for (u, v), c in self.px.items():
            im.putpixel((u - u0, v - v0), c)
        return im, u0, v0


# ---------------------------------------------------------------------------
# Shaders
# ---------------------------------------------------------------------------
def tower_shader(face, col, row, ncols, nrows):
    if face == 'top':
        # Parapet ring around a pale roof.
        if col in (0, ncols - 1) or row in (0, nrows - 1):
            return ROOF_EDGE
        return ROOF
    pal = LEFT if face == 'left' else RIGHT
    # Front corner gets a highlight column, like base-set buildings.
    if (face == 'left' and col == ncols - 1) or (face == 'right' and col == 0):
        return pal['edge'] if row < nrows - 3 else pal['parapet']
    if row >= nrows - 4:
        return pal['parapet']                       # roof parapet band
    if row < 14:
        # Plaza-level lobby: wide "gothic arch" columns with tall glass between.
        if row >= 11:
            return pal['lobby'] if col % 3 != 2 else pal['light']
        return pal['light'] if col % 3 == 0 else pal['glass']
    # Mechanical / sky-lobby floors show as darker bands.
    for frac in (0.36, 0.67):
        b = int(nrows * frac)
        if b <= row < b + 2:
            return pal['band']
    # Characteristic pin-stripe facade: narrow aluminium columns, slit windows.
    return pal['light'] if col % 2 == 0 else pal['dark']


def solid_shader(top, left, right):
    def shade(face, col, row, ncols, nrows):
        return {'top': top, 'left': left, 'right': right}[face]
    return shade


def mech_shader(face, col, row, ncols, nrows):
    return {'top': MECH_TOP, 'left': MECH_L, 'right': MECH_R}[face]


# ---------------------------------------------------------------------------
# Sprites
# ---------------------------------------------------------------------------
def make_tower(antenna):
    c = Canvas()
    o, s, h = TOWER_OFS, TOWER_SIZE, TOWER_H
    c.box(o, o, 0, s, s, h, tower_shader)
    # Roof plant, drawn back-to-front.
    if antenna:
        c.box(o + 2, o + 2, h, 3, 3, 3, mech_shader)
        c.box(o + 7, o + 7, h, 3, 3, 2, mech_shader)
        # Antenna: a stubby base then a thin mast centred on the roof.
        cx = cy = o + s // 2
        c.box(cx - 1, cy - 1, h, 2, 2, 6, solid_shader(MAST_L, MAST_L, MAST_R))
        u, v = proj(cx, cy, h + 6)
        for i in range(ANTENNA_H - 6):
            vv = v - i
            if i < 20:
                c.put(u - 1, vv, MAST_L)
                c.put(u, vv, MAST_R)
            else:
                c.put(u, vv, MAST_L if i % 6 else MAST_R)
        c.put(u, v - (ANTENNA_H - 6), MAST_TIP)
    else:
        # South Tower: observation deck roof with low plant.
        c.box(o + 3, o + 3, h, 6, 6, 2, mech_shader)
    return c


def make_sphere_plaza():
    """South plaza: Koenig's 'The Sphere' on its fountain."""
    c = Canvas()
    # Fountain basin: concrete rim with water inside.
    def basin(face, col, row, ncols, nrows):
        if face == 'top':
            if col in (0, ncols - 1) or row in (0, nrows - 1):
                return CONC_TOP
            return WATER[(col + row) % 3]
        return CONC_L if face == 'left' else CONC_R
    c.box(4, 4, 0, 8, 8, 2, basin)
    # Pedestal.
    c.box(7, 7, 2, 2, 2, 3, solid_shader(CONC_TOP, CONC_L, CONC_R))
    # The sphere itself, lit from the upper left.
    cu, cv = proj(8, 8, 10)
    r = 5.5
    for du in range(-6, 6):
        for dv in range(-6, 6):
            x, y = du + 0.5, dv + 0.5
            if x * x + y * y <= r * r:
                light = (-x * 0.6 - y * 0.8) / r      # -1..1
                idx = int(round((light + 1) / 2 * (len(BRONZE) - 1)))
                c.put(cu + du, cv + dv, BRONZE[max(0, min(len(BRONZE) - 1, idx))])
    return c


def make_north_plaza():
    """North plaza: concrete planters with shrubs."""
    c = Canvas()
    def planter(seed):
        def shade(face, col, row, ncols, nrows):
            if face == 'top':
                if col in (0, ncols - 1) or row in (0, nrows - 1):
                    return CONC_TOP
                return BUSH[(col * 3 + row * 5 + seed) % len(BUSH)]
            if row == nrows - 1:
                return BUSH[2] if face == 'left' else BUSH[0]
            return CONC_L if face == 'left' else CONC_R
        return shade
    for i, (x, y) in enumerate([(2, 2), (2, 10), (10, 2), (10, 10)]):
        c.box(x, y, 0, 4, 4, 3, planter(i))
    return c


# ---------------------------------------------------------------------------
# Sheet + NML output
# ---------------------------------------------------------------------------
def main():
    palette = Image.open(os.path.join(HERE, 'ttd_palette.png')).getpalette()[:768]

    # name -> (canvas, bounding box (ox, oy, oz, sx, sy, sz))
    o, s = TOWER_OFS, TOWER_SIZE
    sprites = [
        ('north_tower', make_tower(True), (o, o, 0, s, s, TOWER_H)),
        ('south_tower', make_tower(False), (o, o, 0, s, s, TOWER_H)),
        ('sphere_plaza', make_sphere_plaza(), (4, 4, 0, 8, 8, 16)),
        ('north_plaza', make_north_plaza(), (2, 2, 0, 12, 12, 4)),
    ]

    images = []
    for name, canvas, bb in sprites:
        im, u0, v0 = canvas.crop()
        bu, bv = proj(bb[0], bb[1], bb[2])
        images.append((name, im, u0 - bu, v0 - bv, bb))

    pad = 4
    sheet_w = sum(im.width + pad for _, im, *_ in images) + pad
    sheet_h = max(im.height for _, im, *_ in images) + 2 * pad
    sheet = Image.new('P', (sheet_w, sheet_h), 0)
    sheet.putpalette(palette)
    x = pad
    entries = {}
    for name, im, xrel, yrel, bb in images:
        sheet.paste(im, (x, pad))
        entries[name] = (x, pad, im.width, im.height, xrel, yrel, bb)
        x += im.width + pad
    sheet.save(os.path.join(ROOT, 'gfx', 'twin_towers.png'), optimize=True)

    write_preview(sheet, entries, palette)
    write_nml(entries)
    for name, e in entries.items():
        print(f'{name:13s} sheet=({e[0]},{e[1]}) size={e[2]}x{e[3]} rel=({e[4]},{e[5]}) bbox={e[6]}')


def write_preview(sheet, entries, palette):
    """Assemble the 2x2 house on concrete, back to front, as a sanity check."""
    W, H = 200, 260
    org = (W // 2, H - 70)                     # screen pos of the house's north corner
    prev = Image.new('RGB', (W, H), (0, 0, 255))
    def paste(name, tx, ty):
        x, y, w, h, xrel, yrel, bb = entries[name]
        spr = sheet.crop((x, y, x + w, y + h))
        bu, bv = proj(tx * 16 + bb[0], ty * 16 + bb[1], bb[2])
        mask = spr.point(lambda p: 255 if p else 0, 'L')
        prev.paste(spr.convert('RGB'), (org[0] + bu + xrel, org[1] + bv + yrel), mask)
    # Ground: concrete diamonds.
    gnd = Image.new('RGB', (W, H))
    from PIL import ImageDraw
    d = ImageDraw.Draw(prev)
    for tx in range(2):
        for ty in range(2):
            pts = [proj(tx * 16 + a, ty * 16 + b, 0) for a, b in ((0, 0), (16, 0), (16, 16), (0, 16))]
            d.polygon([(org[0] + p[0], org[1] + p[1]) for p in pts], fill=(168, 168, 168), outline=(132, 132, 132))
    # Draw order: north (0,0), then west (1,0) and east (0,1), then south (1,1).
    paste('north_plaza', 0, 0)
    paste('north_tower', 1, 0)
    paste('south_tower', 0, 1)
    paste('sphere_plaza', 1, 1)
    # Reference line: OpenTTD's 200 px redraw limit above the north corner.
    prev = prev.resize((W * 3, H * 3), Image.NEAREST)
    prev.save(os.path.join(ROOT, 'gfx', 'preview.png'))


NML = """\
/*
 * Twin Towers (World Trade Center) - a 2x2 town building for OpenTTD.
 *
 * GENERATED by tools/make_sprites.py - edit that script, not this file.
 */

grf {{
    grfid:       "TT\\01\\01";
    name:        string(STR_GRF_NAME);
    desc:        string(STR_GRF_DESC);
    version:     1;
    min_compatible_version: 1;
}}

cargotable {{ PASS, MAIL, GOOD }}

/* ---- Sprites --------------------------------------------------------- */
{spritesets}

/* ---- Layouts: one per tile of the 2x2 house -------------------------- */
{layouts}

switch (FEAT_HOUSES, SELF, sw_twin_towers_tile, house_tile) {{
    HOUSE_TILE_NORTH: layout_north_plaza;
    HOUSE_TILE_WEST:  layout_north_tower;
    HOUSE_TILE_EAST:  layout_south_tower;
    HOUSE_TILE_SOUTH: layout_sphere_plaza;
}}

item (FEAT_HOUSES, twin_towers, -1, HOUSE_SIZE_2X2) {{
    property {{
        substitute:              0x28; /* shopping centre (a 2x2 base house) */
        building_flags:          bitmask(HOUSE_FLAG_NOT_SLOPED, HOUSE_FLAG_PROTECTED);
        name:                    string(STR_TWIN_TOWERS);
        years_available:         [1973, 65535];
        minimum_lifetime:        255;
        population:              255;
        mail_multiplier:         255;
        accepted_cargos:         [[PASS, 8], [MAIL, 8], [GOOD, 4]];
        local_authority_impact:  500;
        removal_cost_multiplier: 255;
        /* Never grown by towns: placed by hand with the house picker only. */
        probability:             0;
        building_class:          0;
        /* Listed under "town centre" in the house picker; temperate, sub-arctic and sub-tropical. */
        availability_mask:       [bitmask(4), bitmask(CLIMATE_TEMPERATE, CLIMATE_ARCTIC, CLIMATE_TROPIC)];
    }}
    graphics {{
        sw_twin_towers_tile;
    }}
}}
"""


def write_nml(entries):
    sets, lays = [], []
    for name, (x, y, w, h, xrel, yrel, bb) in entries.items():
        sets.append(
            f'spriteset (spr_{name}, "gfx/twin_towers.png") {{ [{x}, {y}, {w}, {h}, {xrel}, {yrel}] }}')
        ox, oy, oz, sx, sy, sz = bb
        lays.append(f"""spritelayout layout_{name} {{
    ground {{ sprite: GROUNDSPRITE_CONCRETE; }}
    building {{
        sprite: spr_{name};
        xoffset: {ox}; yoffset: {oy}; zoffset: {oz};
        xextent: {sx}; yextent: {sy}; zextent: {sz};
    }}
}}""")
    with open(os.path.join(ROOT, 'twin_towers.nml'), 'w') as f:
        f.write(NML.format(spritesets='\n'.join(sets), layouts='\n\n'.join(lays)))


if __name__ == '__main__':
    main()
