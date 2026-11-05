#!/usr/bin/env python3
"""
Generate six small-town downtown buildings (1900-1960) as 1x1 houses
(8bpp, normal zoom) plus the NML source.

    * Brick commercial block, c.1905: two storeys of red brick, a shopfront
      with display windows and a painted sign band, a pressed-tin cornice.
    * Town bank, c.1920: a limestone Neoclassical bank with pilasters, tall
      windows, a frieze and a heavy cornice.
    * Roxy Theatre, c.1948: an Art Deco cinema in cream stucco, with maroon
      streamline bands, a bulb-lit marquee and a vertical ROXY blade sign.
    * Post office c.1915, town hall c.1910 (clock cupola) and Carnegie
      library c.1905 (columned portico), in the same limestone as the bank.

Run from anywhere:

    python3 mods/small_town_downtown/tools/make_sprites.py

Outputs:
    mods/small_town_downtown/gfx/small_town_downtown.png   sprite sheet
    mods/small_town_downtown/gfx/preview.png               3x preview of all three
    mods/small_town_downtown/small_town_downtown.nml       NML (generated, do not edit)

Scale (normal zoom): a tile is 64 x 32 px and one height unit is 1 px. Base-set
small offices are about 30 px tall at roughly 10 px per storey, and the old
offices about 55 px. These are two-storey Main Street buildings, so they stand
27-31 px to the roof, which is the same as the base-set shops. The theatre's
blade sign rises to 40 px.
"""

import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Palette indices used below (TTD palette). Company colours (80-87, 198-205)
# and animated colours (>= 217) are avoided.
#   brick 73-77, limestone 35-39, cream stucco 29-31, maroon 42-44,
#   glass 128-130 / 156-158, greys 10-15 / 32 / 33 / 40 / 106 / 136,
#   sign red 162-163, bulb yellow 51-52, shopfront green 96-98.


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




def solid(top, left, right):
    def shade(face, col, row, ncols, nrows):
        return {'top': top, 'left': left, 'right': right}[face]
    return shade


def lr(face, lit, dark):
    """Pick the lit (south-west, left) or shaded (south-east, right) colour."""
    return lit if face == 'left' else dark


# ---------------------------------------------------------------------------
# 1. Brick commercial block, c.1905
# ---------------------------------------------------------------------------
BLOCK_H = 27


def brick_block_shader(face, col, row, ncols, nrows):
    if face == 'top':
        if col in (0, ncols - 1) or row in (0, nrows - 1):
            return 74                                   # brick parapet cap
        return 106                                      # tar roof
    brick = lr(face, 76, 74)
    stone = lr(face, 38, 36)
    edge = col in (0, ncols - 1)
    # Pressed-tin cornice with dentils.
    if row >= nrows - 2:
        return lr(face, 33, 32) if row == nrows - 2 else lr(face, 40, 33)
    if row == nrows - 3:
        return stone if col % 2 == 0 else lr(face, 35, 34)
    if edge:
        return brick
    # Upper storey: arched sash windows with stone sills and lintels.
    if 12 <= row < nrows - 3:
        if row in (13, 21) and col % 4 in (0, 1, 2, 3) and col % 4 != 3:
            return stone
        if 14 <= row <= 20 and col % 4 in (1, 2):
            if row == 17:
                return lr(face, 38, 36)                 # meeting rail
            return lr(face, 130, 129)
        return brick
    # Stone belt course over the shopfront.
    if row == 11:
        return stone
    # Painted sign band with faint lettering.
    if row in (9, 10):
        if row == 10 and 3 <= col < ncols - 3 and col % 2 == 0:
            return 51
        return lr(face, 98, 96)
    # Shopfront: brick piers, plate-glass display windows, a recessed door.
    if row == 0:
        return lr(face, 35, 34)
    seg = col % 7
    if seg in (0, 6):
        return brick
    door = (col // 7) == 1
    if door and seg in (2, 3, 4):
        return 136 if row <= 7 else lr(face, 157, 156)
    if row == 8:
        return lr(face, 158, 157)                       # transom
    if row == 1:
        return lr(face, 98, 96)                         # bulkhead under the glass
    return lr(face, 158, 156) if (col + 2 * row) % 7 == 0 else lr(face, 156, 155)


def make_brick_block():
    c = Canvas()
    c.box(1, 1, 0, 14, 14, BLOCK_H, brick_block_shader)
    # Little rooftop chimney and skylight.
    c.box(3, 3, BLOCK_H, 2, 2, 4, solid(75, 75, 73))
    c.box(8, 6, BLOCK_H, 3, 3, 1, solid(158, 33, 32))
    return c, (1, 1, 0, 14, 14, BLOCK_H + 4)


# ---------------------------------------------------------------------------
# 2. Town bank, c.1920
# ---------------------------------------------------------------------------
BANK_H = 31


def bank_shader(face, col, row, ncols, nrows):
    if face == 'top':
        if col in (0, ncols - 1) or row in (0, nrows - 1):
            return 38
        return 40
    stone = lr(face, 38, 37)
    light = lr(face, 39, 38)
    dark = lr(face, 36, 35)
    if row >= nrows - 2:
        return light                                    # cornice
    if row == nrows - 3:
        return stone if col % 2 == 0 else dark          # dentils
    if nrows - 7 <= row < nrows - 3:
        return dark if row == nrows - 5 else stone      # frieze
    if row < 3:
        return lr(face, 36, 34) if row < 2 else dark    # granite plinth
    seg = col % 6
    if seg in (0, 1) or col >= ncols - 1:
        return light                                    # pilasters
    # Entrance in the middle bay of the lit face.
    mid = ncols // 2
    if face == 'left' and mid - 2 <= col <= mid + 1:
        if row <= 13 and mid - 1 <= col <= mid:
            return 136
        if row <= 14:
            return light
    # Tall windows with a transom bar and round-arch keystone.
    if seg in (3, 4) and 5 <= row <= 21:
        if row == 15:
            return stone
        if row == 21:
            return light
        return lr(face, 130, 129)
    return stone


def make_bank():
    c = Canvas()
    c.box(2, 2, 0, 12, 12, BANK_H, bank_shader)
    # Low attic block on the roof.
    c.box(5, 5, BANK_H, 6, 6, 2, solid(40, 38, 36))
    return c, (2, 2, 0, 12, 12, BANK_H + 2)


# ---------------------------------------------------------------------------
# 3. Roxy Theatre, c.1948
# ---------------------------------------------------------------------------
THEATRE_H = 30
SIGN_Z, SIGN_H = 14, 26

GLYPHS = {
    'R': ('110', '101', '110', '101', '101'),
    'O': ('010', '101', '101', '101', '010'),
    'X': ('101', '101', '010', '101', '101'),
    'Y': ('101', '101', '010', '010', '010'),
}


def theatre_shader(face, col, row, ncols, nrows):
    if face == 'top':
        if col in (0, ncols - 1) or row in (0, nrows - 1):
            return 30
        return 40
    cream = lr(face, 31, 30)
    flute = lr(face, 30, 29)
    maroon = lr(face, 43, 42)
    if row >= nrows - 2:
        return maroon if row == nrows - 2 else cream    # capped parapet
    if row in (nrows - 5, nrows - 7):
        return maroon                                   # streamline speed lines
    if row in (10, 11, 12):
        return maroon                                   # band behind the marquee
    if row >= 13:
        return flute if col % 4 == 0 else cream         # Deco fluting
    # Ground floor: glass lobby doors between poster cases.
    if row == 0:
        return maroon
    mid = ncols // 2
    if mid - 4 <= col < mid + 4:
        if row <= 7:
            return 136 if col % 2 else lr(face, 157, 156)
        return lr(face, 13, 12)
    if col % 8 in (2, 3, 4) and 2 <= row <= 7:
        return 163 if row != 2 else 162                 # framed posters
    return cream


def marquee_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return 52
    if face == 'left':
        return 43
    # Front of the marquee: bulb rows round a white letter board.
    if row in (0, nrows - 1):
        return 51 if col % 2 == 0 else 15
    if 2 <= col < ncols - 2 and col % 3 != 2 and row == 1:
        return 136                                      # "NOW SHOWING" letters
    return 15


def blade_sign_shader(face, col, row, ncols, nrows):
    if face != 'left':
        return 162
    if col in (0, ncols - 1) or row in (0, nrows - 1):
        return 52                                       # bulb border
    for i, ch in enumerate('ROXY'):
        top = nrows - 3 - i * 6
        r = top - row
        if 0 <= r < 5 and 1 <= col <= 3:
            return 52 if GLYPHS[ch][r][col - 1] == '1' else 163
    return 163


def make_theatre():
    c = Canvas()
    c.box(1, 1, 0, 12, 12, THEATRE_H, theatre_shader)
    # Marquee projecting over the sidewalk on the right-hand face.
    c.box(2, 13, 10, 10, 2, 4, marquee_shader)
    # Vertical blade sign standing out from the facade above the marquee.
    c.box(9, 13, SIGN_Z, 1, 3, SIGN_H, blade_sign_shader)
    return c, (1, 1, 0, 12, 15, SIGN_Z + SIGN_H)


# ---------------------------------------------------------------------------
# Civic buildings in the same limestone Neoclassical style as the bank
# ---------------------------------------------------------------------------
GLASS = (130, 129)
COPPER = (101, 100, 99)        # verdigris: lit, mid, shade
FLAG_RED, FLAG_WHITE, FLAG_BLUE = 163, 15, 146


def limestone(face):
    return lr(face, 38, 37), lr(face, 39, 38), lr(face, 36, 35)


def classical_top(face, col, row, nrows):
    """Shared cornice, dentils and frieze. Returns None below the frieze."""
    stone, light, dark = limestone(face)
    if row >= nrows - 2:
        return light
    if row == nrows - 3:
        return stone if col % 2 == 0 else dark
    if nrows - 6 <= row < nrows - 3:
        return dark if row == nrows - 5 else stone
    return None


def roof_shader(face, col, row, ncols, nrows):
    if col in (0, ncols - 1) or row in (0, nrows - 1):
        return 38
    return 40


# 4. Post office, c.1915 ------------------------------------------------------
POST_H = 25


def post_office_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return roof_shader(face, col, row, ncols, nrows)
    stone, light, dark = limestone(face)
    top = classical_top(face, col, row, nrows)
    if top is not None:
        # Lettering in the frieze ("UNITED STATES POST OFFICE").
        if row == nrows - 4 and 2 <= col < ncols - 2 and col % 3 != 2:
            return lr(face, 33, 32)
        return top
    if row < 2:
        return lr(face, 36, 34)                          # granite plinth
    if col in (0, ncols - 1):
        return light                                     # quoins
    # One tall storey of round-arched windows; the door is the middle arch.
    seg = col % 5
    if seg in (2, 3) and 3 <= row <= 16:
        if row >= 15:
            return light if row == 16 and seg == 2 else (GLASS[0] if face == 'left' else GLASS[1])
        if face == 'left' and col // 5 == (ncols // 5) // 2 and row <= 11:
            return 136                                   # doors
        return lr(face, *GLASS) if row != 11 else stone  # transom bar
    if seg in (2, 3) and row == 17:
        return light                                     # keystone line
    return stone


def make_post_office():
    c = Canvas()
    c.box(2, 2, 0, 12, 12, POST_H, post_office_shader)
    # Steps in front of the door.
    c.box(14, 6, 0, 1, 4, 1, solid(39, 38, 36))
    # Flagpole on the front corner of the roof, with the flag flying.
    pu, pv = proj(13, 13, POST_H)
    for i in range(18):
        c.put(pu, pv - i, 15 if i < 17 else 52)
    for r in range(5):
        for k in range(7):
            v = pv - 16 + r + k // 2                     # flag drapes along the iso diagonal
            u = pu + 1 + k
            if r < 3 and k < 3:
                c.put(u, v, FLAG_BLUE)
            else:
                c.put(u, v, FLAG_RED if r % 2 == 0 else FLAG_WHITE)
    return c, (2, 2, 0, 12, 12, POST_H + 18)


# 5. Town hall, c.1910 ---------------------------------------------------------
HALL_H = 30
CUPOLA = (5, 5)                # roof position of the clock tower


def town_hall_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return roof_shader(face, col, row, ncols, nrows)
    stone, light, dark = limestone(face)
    top = classical_top(face, col, row, nrows)
    if top is not None:
        return top
    if row < 2:
        return lr(face, 36, 34)
    if row == 12:
        return light                                     # belt course between storeys
    if col in (0, 1, ncols - 2, ncols - 1):
        return light if row % 3 else dark                # rusticated corner quoins
    seg = col % 4
    if seg in (1, 2):
        if 3 <= row <= 10:
            if face == 'left' and col // 4 == (ncols // 4) // 2:
                return 136 if seg == 1 or row < 9 else 136   # main doors
            return lr(face, *GLASS)
        if 14 <= row <= nrows - 8:
            return lr(face, *GLASS) if row != nrows - 8 else light
    return stone


def clock_drum_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return 38
    stone, light, dark = limestone(face)
    if row in (0, nrows - 1):
        return light
    # A white clock dial with dark hands, ringed in pale stone.
    cc, rc = (ncols - 1) / 2, (nrows - 1) / 2
    d2 = (col - cc) ** 2 + ((row - rc) * 1.4) ** 2
    if d2 <= 9:
        ci, ri = int(round(cc)), int(round(rc))
        if (col, row) in ((ci, ri), (ci, ri + 1), (ci, ri + 2), (ci + 1, ri)):
            return 136
        return 15
    if d2 <= 13:
        return light
    return stone


def copper_shader(face, col, row, ncols, nrows):
    return {'top': COPPER[0], 'left': COPPER[1], 'right': COPPER[2]}[face]


def make_town_hall():
    c = Canvas()
    c.box(1, 1, 0, 14, 14, HALL_H, town_hall_shader)
    x, y = CUPOLA
    z = HALL_H
    c.box(x, y, z, 5, 5, 2, solid(39, 38, 36))           # base
    c.box(x, y, z + 2, 5, 5, 10, clock_drum_shader)       # clock drum
    c.box(x, y, z + 12, 5, 5, 2, copper_shader)           # copper roof, stepped
    c.box(x + 1, y + 1, z + 14, 3, 3, 2, copper_shader)
    c.box(x + 2, y + 2, z + 16, 1, 1, 2, copper_shader)
    pu, pv = proj(x + 2, y + 3, z + 18)
    for i in range(4):
        c.put(pu, pv - i, 52 if i == 3 else 32)          # finial
    return c, (1, 1, 0, 14, 14, HALL_H + 22)


# 6. Carnegie library, c.1905 --------------------------------------------------
LIB_H = 24


def library_shader(face, col, row, ncols, nrows):
    if face == 'top':
        return roof_shader(face, col, row, ncols, nrows)
    stone, light, dark = limestone(face)
    top = classical_top(face, col, row, nrows)
    if top is not None:
        return top
    if row < 4:
        return lr(face, 36, 34)                          # raised basement
    if col in (0, ncols - 1):
        return light
    seg = col % 6
    if seg in (2, 3) and 6 <= row <= nrows - 9:
        return lr(face, *GLASS) if row != 13 else stone
    return stone


def portico_shader(face, col, row, ncols, nrows):
    stone, light, dark = limestone(face)
    if face == 'top':
        return None                                      # hidden behind the pediment
    if face == 'right':
        if row >= nrows - 7:
            return light if row == nrows - 7 else None
        return dark
    # Front: a triangular pediment over an entablature and four columns.
    ped = nrows - 7
    if row >= ped:
        h = row - ped
        half = (ncols - 1) / 2
        if h * 1.3 > half - abs(col - half) + 0.5:
            return None                                  # sky around the pediment
        if h * 1.3 > half - abs(col - half) - 1.5 or h == 0:
            return lr(face, 39, 38)                      # raking cornice
        return lr(face, 35, 34)                          # shadowed tympanum
    if row >= ped - 3:
        return dark if row == ped - 2 else stone         # entablature
    if col % 3 == 0 or col == ncols - 1:
        return light                                     # columns
    return 136 if row < ped - 6 and ncols // 3 <= col < ncols - ncols // 3 else dark


def make_library():
    c = Canvas()
    c.box(2, 2, 0, 12, 12, LIB_H, library_shader)
    # Wide steps up to the portico, then the portico itself on the lit face.
    c.box(14, 4, 0, 2, 8, 2, solid(39, 38, 36))
    c.box(14, 5, 2, 1, 6, LIB_H - 2 + 4, portico_shader)
    return c, (2, 2, 0, 14, 12, LIB_H + 4)


# ---------------------------------------------------------------------------
# Sheet + NML output
# ---------------------------------------------------------------------------
BUILDINGS = [
    # id, name string, maker, year, population, mail, accepted cargo
    ('brick_block', 'STR_BRICK_BLOCK', make_brick_block, 1905, 30, 30, '[[PASS, 4], [MAIL, 4], [GOOD, 8]]'),
    ('town_bank', 'STR_TOWN_BANK', make_bank, 1920, 20, 60, '[[PASS, 4], [MAIL, 8]]'),
    ('roxy_theatre', 'STR_ROXY_THEATRE', make_theatre, 1948, 40, 20, '[[PASS, 8], [MAIL, 2], [GOOD, 4]]'),
    ('post_office', 'STR_POST_OFFICE', make_post_office, 1915, 15, 255, '[[PASS, 4], [MAIL, 8]]'),
    ('town_hall', 'STR_TOWN_HALL', make_town_hall, 1910, 35, 80, '[[PASS, 8], [MAIL, 8]]'),
    ('carnegie_library', 'STR_CARNEGIE_LIBRARY', make_library, 1905, 15, 40, '[[PASS, 4], [MAIL, 4]]'),
]


def main():
    palette = Image.open(os.path.join(HERE, 'ttd_palette.png')).getpalette()[:768]
    images = []
    for bid, *_rest in BUILDINGS:
        maker = _rest[1]
        canvas, bb = maker()
        im, u0, v0 = canvas.crop()
        bu, bv = proj(bb[0], bb[1], bb[2])
        images.append((bid, im, u0 - bu, v0 - bv, bb))

    pad = 4
    sheet = Image.new('P', (sum(im.width + pad for _, im, *_ in images) + pad,
                            max(im.height for _, im, *_ in images) + 2 * pad), 0)
    sheet.putpalette(palette)
    entries = {}
    x = pad
    for bid, im, xrel, yrel, bb in images:
        sheet.paste(im, (x, pad))
        entries[bid] = (x, pad, im.width, im.height, xrel, yrel, bb)
        x += im.width + pad
    sheet.save(os.path.join(ROOT, 'gfx', 'small_town_downtown.png'), optimize=True)

    write_preview(sheet, entries)
    write_nml(entries)
    for bid, e in entries.items():
        print(f'{bid:13s} sheet=({e[0]},{e[1]}) size={e[2]}x{e[3]} rel=({e[4]},{e[5]}) bbox={e[6]}')


def write_preview(sheet, entries):
    """All the buildings side by side along a street, on concrete tiles."""
    W, H = 36 + 32 * len(BUILDINGS) + 40, 50 + 16 * len(BUILDINGS) + 20
    prev = Image.new('RGB', (W, H), (0, 0, 255))
    d = ImageDraw.Draw(prev)
    # Lay the tiles out along the y axis (a row running down to the right).
    origins = []
    for i in range(len(BUILDINGS)):
        ou, ov = proj(0, i * 16, 0)
        origins.append((36 + ou, 50 + ov))
    for org in origins:
        pts = [proj(a, b, 0) for a, b in ((0, 0), (16, 0), (16, 16), (0, 16))]
        d.polygon([(org[0] + p[0], org[1] + p[1]) for p in pts], fill=(168, 168, 168), outline=(132, 132, 132))
    for org, (bid, *_rest) in zip(origins, BUILDINGS):
        x, y, w, h, xrel, yrel, bb = entries[bid]
        spr = sheet.crop((x, y, x + w, y + h))
        bu, bv = proj(bb[0], bb[1], bb[2])
        mask = spr.point(lambda p: 255 if p else 0, 'L')
        prev.paste(spr.convert('RGB'), (org[0] + bu + xrel, org[1] + bv + yrel), mask)
    prev.resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(ROOT, 'gfx', 'preview.png'))


NML_HEAD = """\
/*
 * Small-town downtown buildings (1900-1960) - six 1x1 town buildings for OpenTTD.
 *
 * GENERATED by tools/make_sprites.py - edit that script, not this file.
 */

grf {
    grfid:       "TT\\01\\04";
    name:        string(STR_GRF_NAME);
    desc:        string(STR_GRF_DESC);
    version:     1;
    min_compatible_version: 1;
}

cargotable { PASS, MAIL, GOOD }
"""

NML_HOUSE = """
spriteset (spr_{bid}, "gfx/small_town_downtown.png") {{ [{x}, {y}, {w}, {h}, {xrel}, {yrel}] }}

spritelayout layout_{bid} {{
    ground {{ sprite: GROUNDSPRITE_CONCRETE; }}
    building {{
        sprite: spr_{bid};
        xoffset: {ox}; yoffset: {oy}; zoffset: {oz};
        xextent: {sx}; yextent: {sy}; zextent: {sz};
    }}
}}

item (FEAT_HOUSES, {bid}, -1, HOUSE_SIZE_1X1) {{
    property {{
        substitute:              0x02; /* small offices */
        building_flags:          bitmask(HOUSE_FLAG_NOT_SLOPED, HOUSE_FLAG_PROTECTED);
        name:                    string({name});
        years_available:         [{year}, 65535];
        minimum_lifetime:        255;
        population:              {pop};
        mail_multiplier:         {mail};
        accepted_cargos:         {cargo};
        local_authority_impact:  150;
        removal_cost_multiplier: 120;
        /* Never grown by towns: placed by hand with the house picker only. */
        probability:             0;
        building_class:          0;
        /* Listed under "town centre" in the house picker; temperate, sub-arctic and sub-tropical. */
        availability_mask:       [bitmask(4), bitmask(CLIMATE_TEMPERATE, CLIMATE_ARCTIC, CLIMATE_TROPIC)];
    }}
    graphics {{
        layout_{bid};
    }}
}}
"""


def write_nml(entries):
    out = [NML_HEAD]
    for bid, name, _maker, year, pop, mail, cargo in BUILDINGS:
        x, y, w, h, xrel, yrel, (ox, oy, oz, sx, sy, sz) = entries[bid]
        out.append(NML_HOUSE.format(bid=bid, name=name, x=x, y=y, w=w, h=h, xrel=xrel, yrel=yrel,
                                    ox=ox, oy=oy, oz=oz, sx=sx, sy=sy, sz=sz,
                                    year=year, pop=pop, mail=mail, cargo=cargo))
    with open(os.path.join(ROOT, 'small_town_downtown.nml'), 'w') as f:
        f.write(''.join(out))


if __name__ == '__main__':
    main()
