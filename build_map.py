#!/usr/bin/env python3
"""Regenerate the page 5 street map (the #map-page section of index.html) from OSM.

    python3 build_map.py             # write map_body.svg only
    python3 build_map.py --inject    # write it and splice it into index.html

Geometry is fetched from OpenStreetMap via Overpass and cached beside this file as
geo.json / bld.json — delete those to refetch.

Pin positions: China Construction Bank and Agricultural Bank of China are OSM nodes.
The Jufengyuan Rd shops are not in OSM at all, so they are linear-referenced along the
real Jufengyuan Rd centreline from OSM's surveyed house numbers (#88; #165 KFC;
#205 Sam's Club) together with #329, whose GCJ-02 coordinate came from the China
Telecom Amap share link in Chapter I and was converted to WGS-84.
"""
import json, math, html, os, re, sys, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__)) or '.'
BBOX = '31.3125,121.3705,31.3255,121.3925'
QUERIES = {
 'geo.json': f'''[out:json][timeout:180];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|pedestrian|footway)$"]({BBOX});
  way["waterway"]({BBOX});
  way["natural"="water"]({BBOX});
  way["landuse"~"^(grass|forest|recreation_ground|village_green)$"]({BBOX});
  way["leisure"~"^(park|garden|pitch|sports_centre|stadium)$"]({BBOX});
  relation["amenity"="university"]({BBOX});
  way["railway"="subway"]({BBOX});
  node["railway"="station"]({BBOX});
);
out geom;''',
 'bld.json': f'[out:json][timeout:180];way["building"]({BBOX});out geom;',
}

def osm(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        print(f'fetching {name} from Overpass ...')
        req = urllib.request.Request(
            'https://overpass-api.de/api/interpreter',
            data=urllib.parse.urlencode({'data': QUERIES[name]}).encode(),
            headers={'User-Agent': 'guide-baoshan/1.0'})
        with urllib.request.urlopen(req, timeout=300) as r, open(p, 'wb') as f:
            f.write(r.read())
    return json.load(open(p, encoding='utf-8'))

# ---------------------------------------------------------------- projection
LON0, LON1 = 121.37150, 121.38820
LAT0, LAT1 = 31.31380, 31.32350
W = 1000.0

merc = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
MY0, MY1 = merc(LAT0), merc(LAT1)
H = W * (MY1 - MY0) / math.radians(LON1 - LON0)

def xy(lat, lon):
    return ((lon - LON0) / (LON1 - LON0) * W,
            H - (merc(lat) - MY0) / (MY1 - MY0) * H)

def d_of(geom, close=False):
    pts = [xy(p['lat'], p['lon']) for p in geom]
    if not pts:
        return ''
    return 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts) + (' Z' if close else '')

def vis(geom, pad=0.0015):
    return any(LAT0 - pad < p['lat'] < LAT1 + pad and LON0 - pad < p['lon'] < LON1 + pad
               for p in geom)

E = lambda s: html.escape(s, quote=True)

# ---------------------------------------------------------------- read OSM
els = osm('geo.json')['elements']
blds = [e for e in osm('bld.json')['elements'] if vis(e.get('geometry', []))]

water, greens, subway7, subway15, campus = [], [], [], [], []
roads = {k: [] for k in ('service', 'footway', 'minor', 'residential', 'tertiary', 'primary')}
named = {}
CLASS = {'primary': 'primary', 'trunk': 'primary', 'secondary': 'tertiary', 'tertiary': 'tertiary',
         'residential': 'residential', 'unclassified': 'residential', 'living_street': 'minor',
         'pedestrian': 'minor', 'service': 'service', 'footway': 'footway'}

for e in els:
    t, g = e.get('tags', {}), e.get('geometry')
    if t.get('amenity') == 'university' and e['type'] == 'relation':
        for m in e.get('members', []):
            if m.get('role') == 'outer' and m.get('geometry'):
                campus.append(m['geometry'])
        continue
    if not g or not vis(g):
        continue
    if t.get('railway') == 'subway':
        (subway15 if '15' in (t.get('name') or '') else subway7).append(g)
    elif t.get('natural') == 'water':
        water.append((g, False))
    elif 'waterway' in t:
        water.append((g, True))
    elif t.get('leisure') in ('park', 'garden', 'pitch', 'sports_centre', 'stadium') \
            or t.get('landuse') in ('grass', 'forest', 'recreation_ground', 'village_green'):
        greens.append(g)
    elif 'highway' in t:
        c = CLASS.get(t['highway'])
        if c:
            roads[c].append(g)
            if t.get('name'):
                named.setdefault(t['name'], []).append(g)

# ------------------------------------- stitch Jufengyuan Rd into one polyline, W->E
_segs = [[(p['lat'], p['lon']) for p in g] for g in named.get('聚丰园路', [])]
line = _segs.pop(0)
_moved = True
while _segs and _moved:
    _moved = False
    for i, s in enumerate(list(_segs)):
        for cand in (s, s[::-1]):
            if abs(cand[0][0] - line[-1][0]) < 3e-5 and abs(cand[0][1] - line[-1][1]) < 3e-5:
                line += cand[1:]; _segs.pop(i); _moved = True; break
            if abs(cand[-1][0] - line[0][0]) < 3e-5 and abs(cand[-1][1] - line[0][1]) < 3e-5:
                line = cand[:-1] + line; _segs.pop(i); _moved = True; break
        if _moved:
            break
if line[0][1] > line[-1][1]:
    line = line[::-1]

_R = 6371000.0
def _m(a, b):
    return math.hypot(math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2)) * _R,
                      math.radians(b[0] - a[0]) * _R)
cum = [0.0]
for i in range(1, len(line)):
    cum.append(cum[-1] + _m(line[i - 1], line[i]))

def at(s):
    for i in range(len(cum) - 1):
        if cum[i] <= s <= cum[i + 1]:
            f = (s - cum[i]) / max(1e-9, cum[i + 1] - cum[i])
            (a1, o1), (a2, o2) = line[i], line[i + 1]
            return a1 + f * (a2 - a1), o1 + f * (o2 - o1)
    return line[-1] if s > cum[-1] else line[0]

def side(s, m):
    a1, o1 = at(max(0, s - 15)); a2, o2 = at(min(cum[-1], s + 15))
    k = math.cos(math.radians(a1))
    dx, dy = (o2 - o1) * k, a2 - a1
    n = math.hypot(dx, dy) or 1
    la, lo = at(s)
    return la + (dx / n) * m / 111320.0, lo + (-dy / n) * m / (111320.0 * k)

# Metres east along the Jufengyuan Rd centreline; the west gate is at GATE_ALONG, so
# (GATE_ALONG - value) is the walking distance from it. Set from local knowledge, not
# derived from the walk times printed in index.html — those are rounded figures and
# back-solving positions from them invents precision the timings don't carry.
# Mobile and ICBC share a value: they face each other across the road.
GATE_ALONG = 1022.6
ALONG = {'ICBC': 77.6, 'Mobile': 77.6, 'Telecom': 392.6, 'Unicom': 622.0, 'BOC': 658.0}

# Perpendicular offset in metres: positive = north pavement, negative = south.
# The odd numbers (155, 165, 189, 329) share the north side; ICBC at 458 is the only
# even number here, and stands on the south side directly across from China Mobile.
SIDE  = {'ICBC': -22, 'Mobile': 22, 'Telecom': 20, 'BOC': 22, 'Unicom': 22}
P = {k: side(ALONG[k], SIDE[k]) for k in ALONG}
P.update({
    'CCB':  (31.322930, 121.384448),   # OSM node, China Construction Bank, at Jinqiu Xintiandi
    'ABC':  (31.320619, 121.376051),   # OSM node, Agricultural Bank of China
    'gate': (31.317444, 121.383114),   # OSM barrier=gate  西门
    'ngate': (31.322028, 121.384540),
    'mall': (31.322772, 121.383832),
    'sta_shu': (31.322363, 121.383935),
    'sta_jq': (31.322188, 121.377316),
})

G = 'https://uri.amap.com/search?keyword=%s&city=%%E4%%B8%%8A%%E6%%B5%%B7'
LINKS = {
 'Unicom': 'https://m.amap.com/detail/index/poiid=B0FFG42F4M&src=uriapi',
 'Mobile': 'https://m.amap.com/detail/index/poiid=B0IGCXJ9TP&src=uriapi',
 'ICBC':   'https://m.amap.com/detail/index/poiid=B0G0V1N0NX&src=uriapi',
 'CCB':    'https://m.amap.com/detail/index/poiid=B001571A5P&src=uriapi',
 'ABC':    'https://m.amap.com/detail/index/poiid=B0015118D0&src=uriapi',
 'Telecom': 'https://uri.amap.com/search?keyword=%E4%B8%AD%E5%9B%BD%E7%94%B5%E4%BF%A1%20%E8%81%9A%E4%B8%B0%E5%9B%AD%E8%B7%AF&city=%E4%B8%8A%E6%B5%B7',
 'BOC':    'https://uri.amap.com/search?keyword=%E4%B8%AD%E5%9B%BD%E9%93%B6%E8%A1%8C%E7%A5%81%E8%BF%9E%E5%B1%B1%E8%B7%AF%E6%94%AF%E8%A1%8C&city=%E4%B8%8A%E6%B5%B7',
}

#            n   key        english            chinese          kind   label offset  align
STOPS = [
    ('1', 'Unicom',  'CHINA UNICOM',    '中国联通 · 155',    'sim',  (86, 150), 'middle'),
    ('2', 'Telecom', 'CHINA TELECOM',   '中国电信 · 329',    'sim',  (0, 132), 'middle'),
    ('3', 'Mobile',  'CHINA MOBILE',    '中国移动 · 189',    'sim',  (-4, -92), 'middle'),
    ('4', 'BOC',     'BANK OF CHINA',   '中国银行 · 165',    'bank', (36, -58), 'middle'),
    ('5', 'CCB',     'CONSTRUCTION BANK', '中国建设银行',    'bank', (26, -4), 'start'),
    ('6', 'ICBC',    'ICBC',            '中国工商银行 · 458', 'bank', (-4, 104), 'middle'),
    ('7', 'ABC',     'AGRICULTURAL BANK', '中国农业银行',    'bank', (-44, -42), 'middle'),
]

# ---------------------------------------------------------------- emit
o = []; a = o.append
a(f'<svg viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-label="Street map of the area west and '
  'north of the Shanghai University Baoshan campus. China Unicom, China Telecom and China Mobile '
  'and the Bank of China and ICBC branches lie along Jufengyuan Road, running west from the west '
  'gate. The China Construction Bank and Agricultural Bank of China branches lie on Jinqiu Road '
  'to the north.">')
a('''<defs><style>
 .wa{fill:#CEE0EB}
 .wl{fill:none;stroke:#CEE0EB;stroke-width:5.5;stroke-linecap:round}
 .gr{fill:#E2EEDC}
 .bl{fill:#EAE4DD}
 .cam{fill:#EAF3E8;stroke:#84B48D;stroke-width:1.7;stroke-dasharray:8 5}
 .cas{fill:none;stroke:#E1DAD2;stroke-linecap:round;stroke-linejoin:round}
 .rd{fill:none;stroke:#fff;stroke-linecap:round;stroke-linejoin:round}
 .sv{fill:none;stroke:#fff;stroke-width:2.3;stroke-linecap:round}
 .fw{fill:none;stroke:#DCD5CE;stroke-width:1;stroke-dasharray:3 3}
 .m7{fill:none;stroke:#E8A33D;stroke-width:2.6;opacity:.7}
 .m15{fill:none;stroke:#9E7B54;stroke-width:2.6;opacity:.6}
 .rdn{font-family:var(--etroit),"Arial Narrow",Arial,sans-serif;font-size:14px;font-weight:700;
      letter-spacing:.16em;fill:#958C84}
 .lbl{font-family:var(--etroit),"Arial Narrow",Arial,sans-serif;font-size:15px;font-weight:700;
      letter-spacing:.05em;fill:#2B2622}
 .lcn{font-family:var(--hanzi),sans-serif;font-size:12.5px;fill:#5C544E}
 .num{font-family:var(--etroit),"Arial Narrow",Arial,sans-serif;font-size:14px;font-weight:700}
 .lead{stroke:#9A918A;stroke-width:1.1;fill:none}
 .halo{paint-order:stroke;stroke:#F6F3EF;stroke-width:3.4;stroke-linejoin:round}
 .cap{font-family:var(--etroit),"Arial Narrow",Arial,sans-serif;font-size:12px;
      letter-spacing:.08em;fill:#9A918A}
</style></defs>''')
a(f'<rect width="{W:.0f}" height="{H:.0f}" fill="#F6F3EF"/>')

for g in greens: a(f'<path class="gr" d="{d_of(g, True)}"/>')
for g in campus: a(f'<path class="cam" d="{d_of(g, True)}"/>')
for g, ln in water: a(f'<path class="{"wl" if ln else "wa"}" d="{d_of(g, not ln)}"/>')
for b in blds: a(f'<path class="bl" d="{d_of(b["geometry"], True)}"/>')

WID = {'primary': (14, 10), 'tertiary': (10.5, 7), 'residential': (7.5, 5), 'minor': (6, 4)}
ORDER = ('minor', 'residential', 'tertiary', 'primary')
for c in ORDER:
    for g in roads[c]: a(f'<path class="cas" style="stroke-width:{WID[c][0]}" d="{d_of(g)}"/>')
for g in roads['footway']: a(f'<path class="fw" d="{d_of(g)}"/>')
for g in roads['service']: a(f'<path class="sv" d="{d_of(g)}"/>')
for c in ORDER:
    for g in roads[c]: a(f'<path class="rd" style="stroke-width:{WID[c][1]}" d="{d_of(g)}"/>')
for g in subway15: a(f'<path class="m15" d="{d_of(g)}"/>')
for g in subway7: a(f'<path class="m7" d="{d_of(g)}"/>')

# ---- street names, rotated along the real centreline
def street(name, target, en, cn, flip=False):
    tx, ty = target
    best = None
    for g in named.get(name, []):
        for i in range(len(g) - 1):
            p, q = xy(g[i]['lat'], g[i]['lon']), xy(g[i + 1]['lat'], g[i + 1]['lon'])
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            if math.hypot(q[0] - p[0], q[1] - p[1]) < 30:
                continue
            if not (20 < mx < W - 20 and 20 < my < H - 20):
                continue
            dd = math.hypot(mx - tx, my - ty)
            if best is None or dd < best[0]:
                best = (dd, mx, my, math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])))
    if not best:
        print('  ! no label placed for', name)
        return
    _, mx, my, ang = best
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    a(f'<g transform="translate({mx:.1f},{my:.1f}) rotate({ang:.1f})">'
      f'<text class="rdn halo" y="{16 if flip else -6}" text-anchor="middle">{E(en)} '
      f'<tspan class="lcn" style="fill:#958C84">{E(cn)}</tspan></text></g>')

street('聚丰园路', (600, 520), 'JUFENGYUAN RD', '聚丰园路')
street('锦秋路', (560, 190), 'JINQIU RD', '锦秋路')
street('祁连山路', (345, 430), 'QILIANSHAN RD', '祁连山路')

# ---- campus label
cx, cy = xy(31.31950, 121.38530)
a(f'<text class="lbl halo" x="{cx:.0f}" y="{cy:.0f}" text-anchor="middle" '
  f'style="font-size:19px;letter-spacing:.14em;fill:#3E7A4B">SHANGHAI UNIVERSITY</text>')
a(f'<text class="lcn halo" x="{cx:.0f}" y="{cy+19:.0f}" text-anchor="middle" '
  f'style="font-size:14px;fill:#3E7A4B">上海大学 · 宝山校区</text>')

# ---- metro stations
for key, col in (('sta_shu', '#E8A33D'), ('sta_jq', '#9E7B54')):
    sx, sy = xy(*P[key])
    a(f'<rect x="{sx-7:.1f}" y="{sy-7:.1f}" width="14" height="14" rx="3" fill="{col}" '
      f'stroke="#fff" stroke-width="2"/>')
    a(f'<text class="num" x="{sx:.1f}" y="{sy+4.6:.1f}" text-anchor="middle" fill="#fff" '
      f'style="font-size:11px">M</text>')
sx, sy = xy(*P['sta_jq'])
a(f'<text class="cap halo" x="{sx:.0f}" y="{sy-13:.0f}" text-anchor="middle">L15 JINQIU RD 锦秋路站</text>')
sx, sy = xy(*P['sta_shu'])
a(f'<text class="cap halo" x="{sx-12:.0f}" y="{sy+21:.0f}" text-anchor="end">L7 上海大学站</text>')

# ---- Jinqiu Xintiandi
mx, my = xy(*P['mall'])
a(f'<text class="cap halo" x="{mx-10:.0f}" y="{my-8:.0f}" text-anchor="end">锦秋新天地</text>')

# ---- west gate
gx, gy = xy(*P['gate'])
a(f'<g transform="translate({gx:.1f},{gy:.1f}) rotate(45)">'
  f'<rect x="-8.5" y="-8.5" width="17" height="17" fill="#2B2622" stroke="#fff" stroke-width="2.4"/></g>')
a(f'<text class="lbl halo" x="{gx:.0f}" y="{gy-20:.0f}" text-anchor="middle">WEST GATE</text>')
a(f'<text class="lcn halo" x="{gx:.0f}" y="{gy-6:.0f}" text-anchor="middle">西门</text>')
nx, ny = xy(*P['ngate'])
a(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="5" fill="#2B2622" stroke="#fff" stroke-width="2"/>')
a(f'<text class="cap halo" x="{nx+10:.0f}" y="{ny+5:.0f}">NORTH GATE 北门</text>')

# ---- POI pins + labels
COL = {'sim': '#F0A500', 'bank': '#A6192E'}
for n, key, en, cn, kind, (ox, oy), align in STOPS:
    px, py = xy(*P[key])
    lx, ly = px + ox, py + oy
    a(f'<a href="{E(LINKS[key])}" target="_blank" rel="noopener">')
    a(f'<path class="lead" d="M{px:.1f} {py:.1f} L{lx:.1f} {ly - 22 if oy > 0 else ly + 9:.1f}"/>')
    a(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="11.5" fill="{COL[kind]}" stroke="#fff" stroke-width="2.6"/>')
    a(f'<text class="num" x="{px:.1f}" y="{py+4.9:.1f}" text-anchor="middle" '
      f'fill="{"#2B2622" if kind == "sim" else "#fff"}">{n}</text>')
    a(f'<text class="lbl halo" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{align}">{E(en)}</text>')
    a(f'<text class="lcn halo" x="{lx:.1f}" y="{ly + 15:.1f}" text-anchor="{align}">{E(cn)}</text>')
    a('</a>')

# ---- scale bar (200 m)
m_per_unit = (LON1 - LON0) * 111320 * math.cos(math.radians(31.32)) / W
bar = 200 / m_per_unit
bx, by = 30, 40          # top-left: the bottom-left corner carries the ICBC label
a(f'<g><rect x="{bx}" y="{by}" width="{bar/2:.1f}" height="6" fill="#5C544E"/>'
  f'<rect x="{bx+bar/2:.1f}" y="{by}" width="{bar/2:.1f}" height="6" fill="#fff" '
  f'stroke="#5C544E" stroke-width="1"/>'
  f'<text class="cap" x="{bx}" y="{by-6:.0f}">0</text>'
  f'<text class="cap" x="{bx+bar:.0f}" y="{by-6:.0f}" text-anchor="middle">200 m</text></g>')

# ---- north arrow
a(f'<g transform="translate({W-34:.0f},26)">'
  f'<path d="M0 40 L0 8" stroke="#5C544E" stroke-width="1.8"/>'
  f'<path d="M-5.5 15 L0 3 L5.5 15 Z" fill="#5C544E"/>'
  f'<text class="cap" x="0" y="55" text-anchor="middle" style="fill:#5C544E">N</text></g>')

# ---- attribution
a(f'<text class="cap" x="{W-8:.0f}" y="{H-8:.0f}" text-anchor="end" '
  f'style="font-size:10px">Map data © OpenStreetMap contributors</text>')

a('</svg>')
svg = '\n'.join(o)
out = os.path.join(HERE, 'map_body.svg')
open(out, 'w', encoding='utf-8').write(svg)

print(f'viewBox 0 0 {W:.0f} {H:.0f}  ({W/H:.3f})   '
      f'{(LON1-LON0)*111320*math.cos(math.radians(31.32)):.0f} x {(LAT1-LAT0)*110574:.0f} m')
print('scale printed at 176 mm wide  ->  1 :',
      round((LON1 - LON0) * 111320 * math.cos(math.radians(31.32)) / 0.176))
print(f'{len(blds)} buildings, {len(greens)} green areas, {len(campus)} campus rings '
      f'-> {out} ({len(svg)//1024} KB)')

if '--inject' in sys.argv:
    p = os.path.join(HERE, 'index.html')
    h = open(p, encoding='utf-8').read()
    h, n = re.subn(r'<svg viewBox="0 0 1000 \d+".*?</svg>', lambda m: svg, h, flags=re.S)
    if n != 1:
        sys.exit(f'expected exactly one map <svg> in index.html, found {n}')
    open(p, 'w', encoding='utf-8').write(h)
    print('injected into index.html')
