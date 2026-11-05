#!/usr/bin/env python3
"""
Generate a 2x2 1950s service station house (8bpp, normal zoom) and its NML.

    north tile  garage: office with a plate-glass front, two service bays,
                flat roof with a red-and-white fascia
    south tile  pump canopy on four posts over two pump islands (front, most visible)
    west tile   tall GAS sign on a pole, with a price board, and an air/water post
    east tile   customer parking with a parked two-tone 1950s car, an ice
                cooler and a tyre stack

Run from anywhere:

    python3 mods/gas_station/tools/make_sprites.py

Outputs:
    mods/gas_station/gfx/gas_station.png   sprite sheet (TTD palette)
    mods/gas_station/gfx/preview.png       3x preview of the assembled house
    mods/gas_station/gas_station.nml       NML source (generated, do not edit)

Scale (normal zoom): a tile is 64 x 32 px and one height unit is 1 px. The
garage is a single storey, 13 px to the roof, which is in line with the
base-set small houses. The canopy clears 12 px, about one storey. The GAS sign
stands 29 px tall so it reads from a distance, like a highway sign.
"""

import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Palette indices (TTD palette). Company colours (80-87, 198-205) and
# animated colours (>= 217) are avoided.
WHITE = (15, 13, 12)           # top, lit, shade: enamel panels
RED = (164, 163, 162)          # brand red
GREY = (12, 11, 33)            # concrete islands and roof
GLASS = (158, 156)             # lit, shade
DARK = 136
YELLOW = 52
CAR = (161, 159, 158)          # turquoise body: top, lit, shade
CREAM = (39, 38, 37)           # car roof


def proj(x, y, z):
    """OpenTTD RemapCoords at normal zoom."""
    return 2 * (y - x), (x + y) - z


class Canvas:
    """Sparse pixel canvas in screen coordinates relative to the tile's north corner."""

    def __init__(self):
        self.px = {}

    def put(self, u, v, c):
        if c is not None:                       # None leaves the pixel transparent
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


def solid(trio):
    top, left, right = trio
    def shade(face, col, row, ncols, nrows):
        return {'top': top, 'left': left, 'right': right}[face]
    return shade


def lr(face, lit, dark):
    return lit if face == 'left' else dark


GLYPHS = {
    'G': ('011', '100', '101', '101', '011'),
    'A': ('010', '101', '111', '101', '101'),
    'S': ('011', '100', '010', '001', '110'),
}


# ---------------------------------------------------------------------------
# North tile: the garage
# ---------------------------------------------------------------------------
GARAGE_H = 13


def garage_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return GREY[0]
    wall = lr(face, WHITE[1], WHITE[2])
    if row == 0:
        return lr(face, 33, 32)                          # base course
    if face == 'left':
        # Two roll-up service bay doors.
        for start in (2, 13):
            if start <= col < start + 9:
                if row >= 10:
                    return wall
                if col in (start, start + 8):
                    return 12                            # door frame
                return 11 if row % 2 else 40             # door slats
        return wall
    # Right face: office with a big plate-glass window and a glass door.
    if 2 <= col < 15 and 2 <= row <= 9:
        if col in (2, 14) or row in (2, 9):
            return RED[2]                                # red window frame
        return GLASS[1] if (col + row) % 6 else GLASS[0]
    if 17 <= col < 20 and row <= 9:
        return DARK if col == 17 or row == 9 else GLASS[1]
    return wall


def fascia_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return GREY[0] if 0 < col < ncols - 1 and 0 < row < nrows - 1 else WHITE[0]
    return lr(face, RED[1], RED[2]) if row == 0 else lr(face, WHITE[1], WHITE[2])


def make_garage():
    c = Canvas()
    c.box(1, 1, 0, 13, 13, GARAGE_H, garage_shader)
    c.box(0, 0, GARAGE_H, 15, 15, 3, fascia_shader)      # overhanging roof slab
    c.box(4, 4, GARAGE_H + 3, 2, 2, 3, solid(GREY))      # roof vent
    return c, (0, 0, 0, 15, 15, GARAGE_H + 6)


# ---------------------------------------------------------------------------
# South tile: pump canopy over two islands
# ---------------------------------------------------------------------------
CANOPY_Z = 12


def pump_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return WHITE[0]
    if row == nrows - 1:
        return lr(face, WHITE[1], WHITE[2])              # white globe-top
    if face == 'left' and row == nrows - 3 and col == 1:
        return YELLOW                                    # price window
    return lr(face, RED[1], RED[2])


def canopy_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return WHITE[0] if (col + row) % 8 else WHITE[1]
    # Fascia: red band with a white pin-stripe.
    return lr(face, WHITE[1], WHITE[2]) if row == 1 else lr(face, RED[1], RED[2])


def make_canopy():
    c = Canvas()
    # Pump islands, back to front, each with two pumps.
    for x in (4, 10):
        c.box(x, 3, 0, 2, 10, 1, solid(GREY))
        c.box(x, 4, 1, 2, 2, 6, pump_shader)
        c.box(x, 10, 1, 2, 2, 6, pump_shader)
    # Posts at the canopy corners.
    for (x, y) in ((2, 2), (2, 13), (13, 2), (13, 13)):
        c.box(x, y, 0, 1, 1, CANOPY_Z, solid(WHITE))
    c.box(1, 1, CANOPY_Z, 14, 14, 3, canopy_shader)
    return c, (1, 1, 0, 14, 14, CANOPY_Z + 3)


# ---------------------------------------------------------------------------
# West tile: the GAS sign and the air/water post
# ---------------------------------------------------------------------------
POLE_H = 28
SIGN_W = 12                    # sign panel width in world units (along y)


def sign_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return RED[0]
    if face == 'right':
        return RED[2]
    if col in (0, ncols - 1) or row in (0, nrows - 1):
        return RED[2]                                    # darker rim
    # Each letter pixel is 2 screen columns wide, so the strokes follow the
    # 2:1 iso stair-steps and stay readable on the slanted face.
    text = 'GAS'
    r = nrows - 2 - row
    if 0 <= r < 5:
        c0 = (ncols - 22) // 2
        k = (col - c0) // 2
        if 0 <= col - c0 < 22 and k % 4 != 3:
            ch = text[k // 4]
            return WHITE[0] if GLYPHS[ch][r][k % 4] == '1' else RED[1]
    return RED[1]


def price_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return WHITE[0]
    if face == 'right':
        return WHITE[2]
    if col in (0, ncols - 1) or row in (0, nrows - 1):
        return 33
    return DARK if (col % 3 == 1 and row in (1, 3)) else WHITE[1]   # price digits


def make_sign():
    c = Canvas()
    y0 = 8 - SIGN_W // 2
    # Air and water post, behind the sign.
    c.box(4, 4, 0, 1, 1, 6, solid((WHITE[0], RED[1], RED[2])))
    # Planter base and pole.
    c.box(7, 7, 0, 3, 3, 2, solid((93, 33, 32)))
    c.box(8, 8, 2, 1, 1, POLE_H - 2, solid((12, 11, 33)))
    # Price board under the sign, then the sign itself.
    c.box(8, y0 + 3, POLE_H - 14, 1, SIGN_W - 6, 5, price_shader)
    c.box(8, y0, POLE_H - 7, 1, SIGN_W, 8, sign_shader)
    return c, (4, y0, 0, 6, SIGN_W, POLE_H + 1)


# ---------------------------------------------------------------------------
# East tile: parking with a car, an ice cooler and a tyre stack
# ---------------------------------------------------------------------------
def car_body_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return CAR[0]
    if row == 0:
        return DARK                                      # tyres and shadow
    if row == nrows - 1:
        return lr(face, WHITE[1], WHITE[2])              # chrome trim line
    return lr(face, CAR[1], CAR[2])


def car_cabin_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return CREAM[0]
    if row == nrows - 1:
        return lr(face, CREAM[1], CREAM[2])
    return lr(face, 130, 129)                            # windows


def cooler_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return WHITE[0]
    if row == nrows - 2:
        return lr(face, 148, 146)                        # blue "ICE" band
    return lr(face, WHITE[1], WHITE[2])


def make_parking():
    c = Canvas()
    # Tyre stack and cooler along the back.
    c.box(3, 3, 0, 1, 1, 4, solid((32, DARK, DARK)))
    c.box(3, 9, 0, 2, 3, 5, cooler_shader)
    # Parked car facing south-west: body, then the cabin set back.
    c.box(6, 5, 0, 7, 3, 3, car_body_shader)
    c.box(8, 5, 3, 4, 3, 2, car_cabin_shader)
    return c, (3, 3, 0, 10, 9, 5)


# ---------------------------------------------------------------------------
# Sheet + NML output
# ---------------------------------------------------------------------------
TILES = [  # name, house tile constant, (tx, ty), maker
    ('garage', 'HOUSE_TILE_NORTH', (0, 0), make_garage),
    ('sign', 'HOUSE_TILE_WEST', (1, 0), make_sign),
    ('parking', 'HOUSE_TILE_EAST', (0, 1), make_parking),
    ('canopy', 'HOUSE_TILE_SOUTH', (1, 1), make_canopy),
]


def main():
    palette = Image.open(os.path.join(HERE, 'ttd_palette.png')).getpalette()[:768]
    images = []
    for name, _const, _txy, maker in TILES:
        canvas, bb = maker()
        im, u0, v0 = canvas.crop()
        bu, bv = proj(bb[0], bb[1], bb[2])
        images.append((name, im, u0 - bu, v0 - bv, bb))

    pad = 4
    sheet = Image.new('P', (sum(im.width + pad for _, im, *_ in images) + pad,
                            max(im.height for _, im, *_ in images) + 2 * pad), 0)
    sheet.putpalette(palette)
    entries = {}
    x = pad
    for name, im, xrel, yrel, bb in images:
        sheet.paste(im, (x, pad))
        entries[name] = (x, pad, im.width, im.height, xrel, yrel, bb)
        x += im.width + pad
    sheet.save(os.path.join(ROOT, 'gfx', 'gas_station.png'), optimize=True)

    write_preview(sheet, entries)
    write_nml(entries)
    for name, e in entries.items():
        print(f'{name:8s} sheet=({e[0]},{e[1]}) size={e[2]}x{e[3]} rel=({e[4]},{e[5]}) bbox={e[6]}')


def write_preview(sheet, entries):
    W, H = 150, 100
    org = (W // 2, 40)
    prev = Image.new('RGB', (W, H), (0, 0, 255))
    d = ImageDraw.Draw(prev)
    for _name, _c, (tx, ty), _m in TILES:
        pts = [proj(tx * 16 + a, ty * 16 + b, 0) for a, b in ((0, 0), (16, 0), (16, 16), (0, 16))]
        d.polygon([(org[0] + p[0], org[1] + p[1]) for p in pts], fill=(168, 168, 168), outline=(132, 132, 132))
    for name, _c, (tx, ty), _m in TILES:              # already back to front
        x, y, w, h, xrel, yrel, bb = entries[name]
        spr = sheet.crop((x, y, x + w, y + h))
        bu, bv = proj(tx * 16 + bb[0], ty * 16 + bb[1], bb[2])
        mask = spr.point(lambda p: 255 if p else 0, 'L')
        prev.paste(spr.convert('RGB'), (org[0] + bu + xrel, org[1] + bv + yrel), mask)
    prev.resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(ROOT, 'gfx', 'preview.png'))


NML = """\
/*
 * Service station (1950s) - a 2x2 town building for OpenTTD.
 *
 * GENERATED by tools/make_sprites.py - edit that script, not this file.
 */

grf {{
    grfid:       "TT\\01\\05";
    name:        string(STR_GRF_NAME);
    desc:        string(STR_GRF_DESC);
    version:     1;
    min_compatible_version: 1;
}}

cargotable {{ PASS, MAIL, GOOD }}

/* ---- Sprites and layouts, one per tile of the 2x2 house -------------- */
{tiles}

switch (FEAT_HOUSES, SELF, sw_gas_station_tile, house_tile) {{
{cases}
}}

item (FEAT_HOUSES, gas_station, -1, HOUSE_SIZE_2X2) {{
    property {{
        substitute:              0x14; /* stadium (a 2x2 base house) */
        building_flags:          bitmask(HOUSE_FLAG_NOT_SLOPED, HOUSE_FLAG_PROTECTED);
        name:                    string(STR_GAS_STATION);
        years_available:         [1950, 65535];
        minimum_lifetime:        255;
        population:              10;
        mail_multiplier:         20;
        accepted_cargos:         [[PASS, 4], [MAIL, 2], [GOOD, 8]];
        local_authority_impact:  100;
        removal_cost_multiplier: 80;
        /* Never grown by towns: placed by hand with the house picker only. */
        probability:             0;
        building_class:          0;
        /* Listed under "town centre" in the house picker; temperate, sub-arctic and sub-tropical. */
        availability_mask:       [bitmask(4), bitmask(CLIMATE_TEMPERATE, CLIMATE_ARCTIC, CLIMATE_TROPIC)];
    }}
    graphics {{
        sw_gas_station_tile;
    }}
}}
"""


def write_nml(entries):
    tiles, cases = [], []
    for name, const, _txy, _m in TILES:
        x, y, w, h, xrel, yrel, (ox, oy, oz, sx, sy, sz) = entries[name]
        tiles.append(f"""spriteset (spr_{name}, "gfx/gas_station.png") {{ [{x}, {y}, {w}, {h}, {xrel}, {yrel}] }}

spritelayout layout_{name} {{
    ground {{ sprite: GROUNDSPRITE_CONCRETE; }}
    building {{
        sprite: spr_{name};
        xoffset: {ox}; yoffset: {oy}; zoffset: {oz};
        xextent: {sx}; yextent: {sy}; zextent: {sz};
    }}
}}
""")
        cases.append(f'    {const}: layout_{name};')
    with open(os.path.join(ROOT, 'gas_station.nml'), 'w') as f:
        f.write(NML.format(tiles='\n'.join(tiles), cases='\n'.join(cases)))


if __name__ == '__main__':
    main()
