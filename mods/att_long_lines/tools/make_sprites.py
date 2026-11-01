#!/usr/bin/env python3
"""
Generate the AT&T Long Lines Building house sprite (8bpp, normal zoom) and the NML source.

33 Thomas Street, Manhattan (1974): a windowless telephone exchange clad in
pinkish granite, with vertical stone piers and big louvred air intakes
instead of windows. Drawn procedurally in OpenTTD's isometric projection so
every pixel lines up with its bounding box. Run from anywhere:

    python3 mods/att_long_lines/tools/make_sprites.py

Outputs:
    mods/att_long_lines/gfx/att_long_lines.png   sprite sheet (TTD palette)
    mods/att_long_lines/gfx/preview.png          4x preview on a concrete tile
    mods/att_long_lines/att_long_lines.nml       NML source (generated, do not edit)

Scale (normal zoom): a tile is 64 x 32 px and one height unit is 1 px. The
tallest base-set offices are 100-110 px, and the Twin Towers in this repo are
172 px. The real building is 167 m against the towers' 417 m, but true ratio
would make it shorter than a base-set office, which reads wrong for a building
that towers over its neighbourhood. So it is set at BUILDING_H px: clearly
above the base offices and clearly below the Twin Towers, and on a bulkier
footprint than either.
"""

import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
BUILDING_H = 132       # roof height in px (= world z units)
OFS = 1                # footprint offset inside the 16x16 tile
SIZE = 14              # footprint (14x14 of 16x16 units): a bulky slab

# Palette indices (TTD palette). Pinkish granite from the 122..127 ramp,
# greys for the louvres. Avoids company colours (80-87, 198-205) and
# animated colours (>= 217).
LEFT = dict(stone=127, seam=126, pier=127, recess=125, base=126)
RIGHT = dict(stone=126, seam=125, pier=126, recess=124, base=125)
LOUVRE = (88, 106)     # alternating dark slats
LOUVRE_FRAME = {'left': 126, 'right': 125}
ROOF, ROOF_EDGE = 40, 126
MECH_TOP, MECH_L, MECH_R = 12, 11, 33


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
def louvre_bands(nrows):
    """Rows (bottom-up) holding the big louvred air intakes."""
    low = int(nrows * 0.30)
    return [(low, low + 10), (nrows - 22, nrows - 10)]


def building_shader(face, col, row, ncols, nrows):
    if face == 'top':
        if col in (0, ncols - 1) or row in (0, nrows - 1):
            return ROOF_EDGE
        return ROOF
    pal = LEFT if face == 'left' else RIGHT
    corner = col < 3 or col >= ncols - 3
    if row >= nrows - 3:
        return pal['pier']                          # solid parapet
    if row < 10:
        # Recessed street-level entrance between heavy piers.
        if corner:
            return pal['pier']
        return pal['recess'] if col % 4 in (1, 2) and row < 8 else pal['base']
    if corner:
        return pal['pier']                          # massive corner piers
    for lo, hi in louvre_bands(nrows):
        if lo <= row < hi and 4 <= col < ncols - 4:
            if row in (lo, hi - 1) or col in (4, ncols - 5):
                return LOUVRE_FRAME[face]
            return LOUVRE[row % 2]
    # Windowless granite skin: vertical panel ribs.
    return pal['seam'] if col % 4 == 3 else pal['stone']


def mech_shader(face, col, row, ncols, nrows):
    return {'top': MECH_TOP, 'left': MECH_L, 'right': MECH_R}[face]


# ---------------------------------------------------------------------------
# Sprites
# ---------------------------------------------------------------------------
def make_building():
    c = Canvas()
    c.box(OFS, OFS, 0, SIZE, SIZE, BUILDING_H, building_shader)
    # Low rooftop plant, back to front.
    c.box(OFS + 3, OFS + 3, BUILDING_H, 4, 4, 4, mech_shader)
    c.box(OFS + 8, OFS + 6, BUILDING_H, 3, 5, 2, mech_shader)
    return c


# ---------------------------------------------------------------------------
# Sheet + NML output
# ---------------------------------------------------------------------------
def main():
    palette = Image.open(os.path.join(HERE, 'ttd_palette.png')).getpalette()[:768]
    bb = (OFS, OFS, 0, SIZE, SIZE, BUILDING_H)
    im, u0, v0 = make_building().crop()
    bu, bv = proj(bb[0], bb[1], bb[2])
    xrel, yrel = u0 - bu, v0 - bv

    pad = 4
    sheet = Image.new('P', (im.width + 2 * pad, im.height + 2 * pad), 0)
    sheet.putpalette(palette)
    sheet.paste(im, (pad, pad))
    sheet.save(os.path.join(ROOT, 'gfx', 'att_long_lines.png'), optimize=True)
    entry = (pad, pad, im.width, im.height, xrel, yrel, bb)

    write_preview(sheet, entry)
    write_nml(entry)
    print(f'building sheet=({pad},{pad}) size={im.width}x{im.height} rel=({xrel},{yrel}) bbox={bb}')


def write_preview(sheet, entry):
    from PIL import ImageDraw
    W, H = 120, 190
    org = (W // 2, H - 40)
    prev = Image.new('RGB', (W, H), (0, 0, 255))
    d = ImageDraw.Draw(prev)
    pts = [proj(a, b, 0) for a, b in ((0, 0), (16, 0), (16, 16), (0, 16))]
    d.polygon([(org[0] + p[0], org[1] + p[1]) for p in pts], fill=(168, 168, 168), outline=(132, 132, 132))
    x, y, w, h, xrel, yrel, bb = entry
    spr = sheet.crop((x, y, x + w, y + h))
    bu, bv = proj(bb[0], bb[1], bb[2])
    mask = spr.point(lambda p: 255 if p else 0, 'L')
    prev.paste(spr.convert('RGB'), (org[0] + bu + xrel, org[1] + bv + yrel), mask)
    prev.resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(ROOT, 'gfx', 'preview.png'))


NML = """\
/*
 * AT&T Long Lines Building (33 Thomas Street) - a 1x1 town building for OpenTTD.
 *
 * GENERATED by tools/make_sprites.py - edit that script, not this file.
 */

grf {{
    grfid:       "TT\\01\\02";
    name:        string(STR_GRF_NAME);
    desc:        string(STR_GRF_DESC);
    version:     1;
    min_compatible_version: 1;
}}

cargotable {{ PASS, MAIL, GOOD }}

spriteset (spr_building, "gfx/att_long_lines.png") {{ [{x}, {y}, {w}, {h}, {xrel}, {yrel}] }}

spritelayout layout_building {{
    ground {{ sprite: GROUNDSPRITE_CONCRETE; }}
    building {{
        sprite: spr_building;
        xoffset: {ox}; yoffset: {oy}; zoffset: {oz};
        xextent: {sx}; yextent: {sy}; zextent: {sz};
    }}
}}

item (FEAT_HOUSES, att_long_lines, -1, HOUSE_SIZE_1X1) {{
    property {{
        substitute:              0x00; /* tall office block */
        building_flags:          bitmask(HOUSE_FLAG_NOT_SLOPED, HOUSE_FLAG_PROTECTED);
        name:                    string(STR_ATT_LONG_LINES);
        years_available:         [1974, 65535];
        minimum_lifetime:        255;
        /* A telephone exchange: few people, lots of mail. */
        population:              40;
        mail_multiplier:         255;
        accepted_cargos:         [[PASS, 4], [MAIL, 8], [GOOD, 4]];
        local_authority_impact:  300;
        removal_cost_multiplier: 255;
        /* Never grown by towns: placed by hand with the house picker only. */
        probability:             0;
        building_class:          0;
        /* Listed under "town centre" in the house picker; temperate, sub-arctic and sub-tropical. */
        availability_mask:       [bitmask(4), bitmask(CLIMATE_TEMPERATE, CLIMATE_ARCTIC, CLIMATE_TROPIC)];
    }}
    graphics {{
        layout_building;
    }}
}}
"""


def write_nml(entry):
    x, y, w, h, xrel, yrel, (ox, oy, oz, sx, sy, sz) = entry
    with open(os.path.join(ROOT, 'att_long_lines.nml'), 'w') as f:
        f.write(NML.format(x=x, y=y, w=w, h=h, xrel=xrel, yrel=yrel,
                           ox=ox, oy=oy, oz=oz, sx=sx, sy=sy, sz=sz))


if __name__ == '__main__':
    main()
