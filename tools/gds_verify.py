#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PKNU_2026_M12 GDS 검증 스크립트
  - 블록별 bounding box (논문 표 2 대조)
  - 트랜지스터 W/L 추출 (POLY ∩ ACTIVE)
  - 인스턴스 개수 (셀 어레이 · 주변회로)
  - 패드 / 핀 라벨
  - 금속·비아 연결 추적: 매크로 핀 → 패드, A0 공유 여부

사용:  pip install gdstk shapely
       python3 tools/gds_verify.py PKNU_2026_M12.gds

레이어 (NSPL 0.5 μm 2P3M, GDS 번호):
  2 NWELL · 11 ACTIVE · 12 POLY1 · 31 CONT · 32 METAL1 · 33 VIA1 · 34 METAL2 · 35 VIA2 · 36 METAL3
  라벨: 42 (매크로 핀) · 46 (칩 패드)
"""
import sys
import collections
import gdstk
from shapely.geometry import Polygon, Point, box
from shapely.strtree import STRtree
from shapely.ops import unary_union

NWELL, ACTIVE, POLY = 2, 11, 12
CONDUCTORS = {12: "POLY", 32: "M1", 34: "M2", 36: "M3"}
VIAS = {31: (12, 32), 33: (32, 34), 35: (34, 36)}      # CONT 는 POLY–M1 연결만 추적
MACRO, CHIP = "SRAM_64bit", "PKNU_MPW2_STD004"

PAPER_TABLE2 = {            # 셀 이름: (논문 표기, W, H)  단위 μm
    "SRAM_CELL":   ("6T SRAM 셀",     35.8, 25.7),
    "RowDecoder":  ("행 디코더",      163.0, 212.4),
    "ColDecoder":  ("열 디코더",      345.0, 19.8),
    "Precharger":  ("프리차지 회로",   26.0, 17.3),
    "SenseAmp":    ("감지 증폭기",     28.7, 30.1),
    "WriteDriver": ("쓰기 드라이버",   36.3, 36.6),
    "SRAM_64bit":  ("SRAM 코어 전체", 643.8, 612.7),
}


def size(bb):
    (x0, y0), (x1, y1) = bb
    return x1 - x0, y1 - y0


def flat(cells, name):
    c = cells[name].copy(f"_flat_{name}")
    c.flatten()
    return c


def gates(cells, name):
    """POLY ∩ ACTIVE → (type, W, L) 카운트. NWELL 안이면 PMOS."""
    f = flat(cells, name)
    act = [p for p in f.polygons if p.layer == ACTIVE]
    poly = [p for p in f.polygons if p.layer == POLY]
    nw = [p for p in f.polygons if p.layer == NWELL]
    out = collections.Counter()
    for g in gdstk.boolean(act, poly, "and"):
        (x0, y0), (x1, y1) = g.bounding_box()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        is_p = any(gdstk.inside([(cx, cy)], [n])[0] for n in nw)
        w, h = x1 - x0, y1 - y0
        L, W = sorted((w, h)) if min(w, h) >= 0.49 else (w, h)
        out[("P" if is_p else "N", round(W, 2), round(L, 2))] += 1
    return out


class Nets:
    """금속/폴리 도형을 비아로 묶어 넷을 만든다 (다이오드·트랜지스터 경로는 제외)."""

    def __init__(self, cells, name):
        f = flat(cells, name)
        self.shapes, self.layer = [], []
        for L in CONDUCTORS:
            u = unary_union([Polygon(p.points).buffer(0) for p in f.polygons if p.layer == L])
            for g in getattr(u, "geoms", [u]):
                self.shapes.append(g)
                self.layer.append(L)
        self.tree = STRtree(self.shapes)
        self.parent = list(range(len(self.shapes)))
        for V, (la, lb) in VIAS.items():
            for p in f.polygons:
                if p.layer != V:
                    continue
                (x0, y0), (x1, y1) = p.bounding_box()
                hits = self._at((x0 + x1) / 2, (y0 + y1) / 2)
                A = [i for i in hits if self.layer[i] == la]
                B = [i for i in hits if self.layer[i] == lb]
                for a in A:
                    for b in B:
                        self._union(a, b)

    def _find(self, a):
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def _union(self, a, b):
        ra, rb = self._find(a), self._find(b)
        if ra != rb:
            self.parent[ra] = rb

    def _at(self, x, y):
        P = Point(x, y)
        return [i for i in self.tree.query(P) if self.shapes[i].covers(P)]

    def net(self, x, y, layer=32):
        """라벨 위치의 METAL1 넷 (위를 지나는 다른 층 배선에 속지 않도록 층을 지정)."""
        n = {self._find(i) for i in self._at(x, y) if self.layer[i] == layer}
        return n.pop() if len(n) == 1 else None

    def touches(self, root, bb):
        B = box(bb[0][0], bb[0][1], bb[1][0], bb[1][1])
        return any(self._find(i) == root and self.shapes[i].intersects(B) for i in range(len(self.shapes)))


def main(path):
    lib = gdstk.read_gds(path)
    cells = {c.name: c for c in lib.cells}
    print(f"GDS: {path}  unit={lib.unit}  top={[c.name for c in lib.top_level()]}\n")

    # 1. 블록 크기
    print("[1] 블록 크기 (μm)  — 논문 표 2 대조")
    for name, (label, pw, ph) in PAPER_TABLE2.items():
        w, h = size(cells[name].bounding_box())
        ok = "OK" if abs(w - pw) <= 0.05 + 1e-6 and abs(h - ph) <= 0.05 + 1e-6 else "DIFF"
        print(f"  {label:12s} {name:12s} {w:7.2f} × {h:7.2f}   논문 {pw:6.1f} × {ph:6.1f}   {ok}")
    w, h = size(cells[CHIP].bounding_box())
    print(f"  {'전체 칩':12s} {CHIP:12s} {w:7.1f} × {h:7.1f}   논문 1900 × 1900\n")

    # 2. 트랜지스터 사이징
    print("[2] 트랜지스터 W/L (μm)  — POLY ∩ ACTIVE")
    for name in ["SRAM_CELL", "Precharger", "SenseAmp", "WriteDriver", "tg", "RowDecoder", "ColDecoder"]:
        g = gates(cells, name)
        s = ", ".join(f"{t} {W}/{L} ×{n}" for (t, W, L), n in sorted(g.items()))
        print(f"  {name:12s} {s}")
    print()

    # 3. 인스턴스 개수
    print(f"[3] {MACRO} 내부 인스턴스")
    cnt = collections.Counter(r.cell.name for r in cells[MACRO].references)
    for k in ["SRAM_CELL", "Precharger", "SenseAmp", "WriteDriver", "RowDecoder", "ColDecoder"]:
        print(f"  {k:12s} ×{cnt[k]}")
    tg = collections.Counter(r.cell.name for r in cells["ColDecoder"].references)
    rd = collections.Counter(r.cell.name for r in cells["RowDecoder"].references)
    print(f"  ColDecoder 내 TG ×{tg['tg'] + tg['tg2']},  RowDecoder 내 NAND4 ×{sum(v for k, v in rd.items() if 'nand4' in k)}\n")

    # 4. 패드 / 핀
    chip = cells[CHIP]
    pad_sites = collections.Counter(r.cell.name for r in cells["MPW_PAD_28pin"].references)
    padlabels = [(l.text, tuple(l.origin)) for l in chip.labels if l.layer == 46]
    pads = [(r.cell.name, r.bounding_box()) for r in chip.references
            if r.cell.name in ("PBCT4_modified4_MPW4", "POB24", "PVDD", "PVSS")]

    def padname(bb):
        (x0, y0), (x1, y1) = bb
        return next((t for t, (x, y) in padlabels if x0 - 5 <= x <= x1 + 5 and y0 - 5 <= y <= y1 + 5), "?")

    print(f"[4] 패드: 사이트 {sum(pad_sites.values())}개, 사용 {len(pads)}개")
    for kind in ("PBCT4_modified4_MPW4", "POB24", "PVDD", "PVSS"):
        names = sorted(padname(bb) for n, bb in pads if n == kind)
        print(f"  {kind:22s} ×{len(names):2d}  {names}")
    addr = sorted({l.text for l in cells[MACRO].labels if l.text.startswith("A")})
    print(f"  매크로 주소 핀 라벨: {addr}\n")

    # 5. 연결 추적
    print("[5] 연결 추적: 매크로 핀(METAL1 라벨) → 패드")
    ref = next(r for r in chip.references if r.cell.name == MACRO)
    ox, oy = ref.origin
    sy = -1 if ref.x_reflection else 1
    nets = Nets(cells, CHIP)
    roots = collections.defaultdict(list)
    for l in cells[MACRO].labels:
        if l.layer != 42 or l.text.startswith("RDATA") or l.text in ("VDD", "VSS"):
            continue
        x, y = ox + l.origin[0], oy + sy * l.origin[1]
        r = nets.net(x, y)
        roots[l.text].append(r)
        hit = sorted({padname(bb) for n, bb in pads if n == "PBCT4_modified4_MPW4" and r is not None and nets.touches(r, bb)})
        print(f"  {l.text:7s} @({l.origin[0]:6.1f},{l.origin[1]:7.1f})  net#{r}  → pad {hit}")
    a0 = roots.get("A0", [])
    print(f"\n  A0 라벨 {len(a0)}개 (RowDecoder 입력 · ColDecoder 입력) 동일 넷: {len(set(a0)) == 1}")
    others = {k: v[0] for k, v in roots.items() if k != "A0"}
    print(f"  제어/주소/데이터 넷 간 단락 없음: {len(set(others.values()) | set(a0)) == len(others) + 1}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
