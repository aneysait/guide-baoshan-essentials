# SIM Card & Bank Account — Baoshan (UTSEUS)

**Read it here: [aneysait.github.io/sim-and-bank](https://aneysait.github.io/sim-and-bank/)**

The two things to sort out in your first days at Shanghai University (Baoshan campus), on
five pages you can print or open on your phone:
- **Chinese SIM card**: recommended operators, student plans with no contract, addresses near the campus with Gaode Maps links.
- **Opening a bank account**: SHU partner branches, list of mandatory documents, tips and alternatives (WeChat / Alipay).
- **Area map**: every address on one street map of the streets around the west gate.

## Rebuilding the map

Page 5 carries a vector street map drawn from OpenStreetMap data and embedded inline in
`index.html` — there is no image file to keep in sync. To redraw it after moving a pin or
changing the framing, edit the constants at the top of `build_map.py` and run:

```sh
python3 build_map.py --inject
```

It fetches what it needs from Overpass (cached locally as `geo.json` / `bld.json`, both
gitignored) and rewrites the `<svg>` inside `index.html` in place.

---
Written by Anicet Barrios, Head Student Coordinator UTSEUS.
The full Baoshan guide, still in progress, lives at [aneysait.github.io/guide-baoshan](https://aneysait.github.io/guide-baoshan/).
