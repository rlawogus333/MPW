#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PKNU_2026_M12  8x8 (64-bit) 6T SRAM — Raspberry Pi 실측 R/W 테스트
  칩 VDD = 3.3 V, VSS = 0 V, 라즈베리파이 3.3 V GPIO 직결 (레벨시프터 없음)

────────────────────────────────────────────────────────────────────
[모아팹 제출버전 schematic에서 확인한 동작]
  PRE   Active-LOW.  Precharger PMOS(BL·BLB → VDD, equalizer). PRE=0이면 프리차지.
  E     Active-HIGH. RowDecoder NAND4의 4번째 입력 → WL = E · decode(A3A2A1)
        → E가 곧 워드라인 펄스다.
  A3A2A1  행 선택 (000=WL0 … 111=WL7)
  A0    ColDecoder TG. 0 → Col0~3, 1 → Col4~7.  (Colk 와 Col(k+4)가 CBLk 공유)
  WE    WriteDriver NMOS pass. BL = WDATA, BLB = ~WDATA  (비반전)
  SE    Current-mirror SenseAmp tail. RDATA = (BL > BLB)  (비반전, 래치 없음)
        SE=0 이면 RDATA = 0 → 반드시 SE=1 구간 안에서 샘플링해야 한다.
  ⇒ RDATA == WDATA   (Spectre tb: WDATA=5 → RDATA=5 확인)

  비트 위치: 주소 a, 데이터 bit k  →  행 = a>>1,  열 = k + 4*(a&1)

[코드가 강제하는 안전 규칙 (interlock)]
  1) PRE=0 인 동안 E=0, WE=0     precharger ↔ 셀/write driver 충돌 방지
  2) E=1 인 동안 주소 변경 금지    다른 WL 글리치 → 오기록 방지
  3) WE=1 과 SE=1 동시 금지
  4) Read/Write 모두 WL 열기 전 매번 precharge
     (같은 행의 비선택 4개 열은 bitline이 떠 있으므로 half-select 교란 방지)

[시퀀스]
  WRITE : A 설정 → PRE 펄스 → WDATA 설정 → WE=1 → E=1 → E=0 → WE=0
          (WL을 먼저 닫고 나서 write driver를 놓는다)
  READ  : A 설정 → PRE 펄스 → E=1 → SE=1 → RDATA N회 샘플 → SE=0 → E=0
────────────────────────────────────────────────────────────────────

설치 (Raspberry Pi OS Bookworm):  sudo apt install python3-lgpio
  - lgpio 가 없으면 RPi.GPIO 로 자동 fallback (단, Pi 5는 RPi.GPIO 불가)
  - GPIO 7, 8 은 SPI0 CS 핀. raspi-config 에서 SPI 를 꺼두어야 claim 가능

사용 예:
  python3 sram_rw_test.py --sim                 # PC에서 로직 검증 (하드웨어 불필요)
  python3 sram_rw_test.py --sim --fault s0:3,5 --fault pin:A2=0
  python3 sram_rw_test.py conn smoke            # 칩 받으면 제일 먼저
  python3 sram_rw_test.py all                   # conn→smoke→addr→march→disturb→retention
  python3 sram_rw_test.py shmoo                 # 타이밍 스케일 스윕
  python3 sram_rw_test.py shell                 # 수동 R/W, 스코프 디버깅
"""

import argparse
import csv
import random
import sys
import time
from dataclasses import dataclass, asdict

# ═══════════════════════════════════════════════════════════════════
#  핀 맵 (BCM 번호) — sram_test_guide_v3 배정 유지
# ═══════════════════════════════════════════════════════════════════
PINS = {
    "PRE": 17,
    "E": 27,
    "WE": 8,
    "SE": 7,
    "A": [18, 23, 24, 25],      # A0, A1, A2, A3
    "WDATA": [12, 16, 20, 21],  # bit0 … bit3
    "RDATA": [26, 19, 13, 6],   # bit0 … bit3
}


# ═══════════════════════════════════════════════════════════════════
#  타이밍 (단위 µs)
#  칩 내부 지연은 ns 단위(Spectre: PRE/WE/SE 500 ns 펄스로 동작).
#  Python GPIO 한 번 토글이 수~수십 µs 이므로 여유 있게 ms 단위로 시작하고,
#  shmoo 로 줄여가며 마진을 본다. 정적 SRAM이라 느린 건 문제 없음.
# ═══════════════════════════════════════════════════════════════════
@dataclass
class Timing:
    t_addr: int = 200      # 주소 변경 후 안정화 (E=0 상태)
    t_pre: int = 1000      # PRE=0 폭
    t_pre_off: int = 200   # PRE=1 → E/WE 올리기 전
    t_wd: int = 500        # WE=1 → E=1 (write driver가 BL/BLB 구동)
    t_wl_w: int = 1000     # write 시 E=1 유지 (셀 반전)
    t_hold: int = 200      # E=0 → WE=0
    t_dev: int = 1000      # read: E=1 → SE=1 (BL/BLB 차동 형성)
    t_sa: int = 500        # SE=1 → 첫 샘플
    t_smp: int = 100       # 샘플 간격

    def scaled(self, k: float) -> "Timing":
        return Timing(**{n: max(0, int(v * k)) for n, v in asdict(self).items()})


def wait_us(us: float) -> None:
    """2 ms 이상은 sleep, 그 미만은 busy-wait (time.sleep 은 짧은 대기가 부정확)."""
    if us <= 0:
        return
    if us >= 2000:
        time.sleep(us / 1e6)
        return
    end = time.perf_counter_ns() + int(us * 1000)
    while time.perf_counter_ns() < end:
        pass


class C:  # 터미널 색
    R, G, Y, B, D, BOLD, X = "\033[91m", "\033[92m", "\033[93m", "\033[96m", "\033[90m", "\033[1m", "\033[0m"


# ═══════════════════════════════════════════════════════════════════
#  GPIO 백엔드
# ═══════════════════════════════════════════════════════════════════
class LgpioBackend:
    """Pi 3/4/5 공통. Pi 5는 RP1(pinctrl-rp1) gpiochip 자동 탐색."""
    name = "lgpio"

    def __init__(self, chip=None):
        import lgpio
        self.lg = lgpio
        self.h = self._open(chip)
        self.claimed = set()

    def _open(self, chip):
        lg = self.lg
        if chip is not None:
            return lg.gpiochip_open(chip)
        for n in range(8):
            try:
                h = lg.gpiochip_open(n)
            except Exception:
                continue
            try:
                info = " ".join(str(x) for x in lg.gpio_get_chip_info(h))
            except Exception:
                info = ""
            if any(k in info for k in ("rp1", "bcm2711", "bcm2835")):
                return h
            lg.gpiochip_close(h)
        raise RuntimeError("40핀 헤더 gpiochip 을 못 찾음 → `gpiodetect` 확인 후 --chip N 지정")

    def out(self, g, level):
        self.lg.gpio_claim_output(self.h, g, level)
        self.claimed.add(g)

    def inp(self, g, pull="none"):
        flag = {"none": self.lg.SET_PULL_NONE, "up": self.lg.SET_PULL_UP,
                "down": self.lg.SET_PULL_DOWN}[pull]
        if g in self.claimed:
            self.lg.gpio_free(self.h, g)
        self.lg.gpio_claim_input(self.h, g, flag)
        self.claimed.add(g)

    def write(self, g, v):
        self.lg.gpio_write(self.h, g, v)

    def read(self, g):
        return self.lg.gpio_read(self.h, g)

    def close(self):
        for g in self.claimed:
            try:
                self.lg.gpio_free(self.h, g)
            except Exception:
                pass
        self.lg.gpiochip_close(self.h)


class RPiGPIOBackend:
    """Pi 4 이하 전용 fallback."""
    name = "RPi.GPIO"

    def __init__(self):
        import RPi.GPIO as G
        self.G = G
        G.setwarnings(False)
        G.setmode(G.BCM)

    def out(self, g, level):
        self.G.setup(g, self.G.OUT, initial=level)

    def inp(self, g, pull="none"):
        pud = {"none": self.G.PUD_OFF, "up": self.G.PUD_UP, "down": self.G.PUD_DOWN}[pull]
        self.G.setup(g, self.G.IN, pull_up_down=pud)

    def write(self, g, v):
        self.G.output(g, v)

    def read(self, g):
        return self.G.input(g)

    def close(self):
        self.G.cleanup()


class SimBackend:
    """
    PC 검증용 칩 모델 (위 회로 해석을 그대로 반영) + 결함 주입.
      --fault s0:r,c     셀 (행 r, 열 c) stuck-at-0
      --fault s1:r,c     셀 stuck-at-1
      --fault row:r      WL r 이 안 올라옴 (읽으면 랜덤)
      --fault pin:A2=0   칩 핀 고정 (A0~3, WDATA0~3, RDATA0~3, PRE/E/WE/SE)
    """
    name = "sim"

    def __init__(self, pins, faults=(), seed=1):
        self.p = pins
        self.lv = {}
        self.rng = random.Random(seed)
        self.mem = [[self.rng.randint(0, 1) for _ in range(8)] for _ in range(8)]  # 전원 인가 직후 랜덤
        self.stuck, self.dead_rows, self.force = {}, set(), {}
        self.violations, self.no_pre = [], 0
        self._prev_e, self._fresh_pre = 0, False
        for f in faults:
            self._parse(f)

    def _parse(self, f):
        kind, _, arg = f.partition(":")
        if kind in ("s0", "s1"):
            r, c = map(int, arg.split(","))
            self.stuck[(r, c)] = int(kind[1])
        elif kind == "row":
            self.dead_rows.add(int(arg))
        elif kind == "pin":
            name, v = arg.split("=")
            self.force[self._gpio(name)] = int(v)
        else:
            raise ValueError(f"알 수 없는 fault: {f}")

    def _gpio(self, name):
        name = name.upper()
        for bus in ("WDATA", "RDATA", "A"):
            if name.startswith(bus) and name[len(bus):].isdigit():
                return self.p[bus][int(name[len(bus):])]
        return self.p[name]

    def _v(self, name, i=None):
        g = self.p[name] if i is None else self.p[name][i]
        return self.force.get(g, self.lv.get(g, 0))

    def _rowcol(self):
        return self._v("A", 1) | self._v("A", 2) << 1 | self._v("A", 3) << 2, self._v("A", 0)

    def _eval(self):
        pre, e, we = self._v("PRE"), self._v("E"), self._v("WE")
        if pre == 0:
            self._fresh_pre = True
            if e or we:
                self.violations.append("PRE=0 & (E|WE)=1")
        if e and not self._prev_e:
            if not self._fresh_pre:
                self.no_pre += 1
            self._fresh_pre = False
        self._prev_e = e
        if e and we and pre:
            row, a0 = self._rowcol()
            if row not in self.dead_rows:
                for k in range(4):
                    c = k + 4 * a0
                    self.mem[row][c] = self.stuck.get((row, c), self._v("WDATA", k))

    def out(self, g, level):
        self.lv[g] = level
        self._eval()

    def inp(self, g, pull="none"):
        pass

    def write(self, g, v):
        self.lv[g] = v
        self._eval()

    def read(self, g):
        if g in self.force:
            return self.force[g]
        if not (self._v("SE") and self._v("E") and self._v("PRE")):
            return 0  # SA 비활성 → RDATA=0
        row, a0 = self._rowcol()
        if row in self.dead_rows:
            return self.rng.randint(0, 1)
        c = self.p["RDATA"].index(g) + 4 * a0
        return self.stuck.get((row, c), self.mem[row][c])

    def close(self):
        pass


def make_backend(args):
    if args.sim:
        return SimBackend(PINS, args.fault)
    if args.backend in ("auto", "lgpio"):
        try:
            return LgpioBackend(args.chip)
        except ImportError:
            if args.backend == "lgpio":
                raise
    return RPiGPIOBackend()


# ═══════════════════════════════════════════════════════════════════
#  SRAM 드라이버
# ═══════════════════════════════════════════════════════════════════
class InterlockError(RuntimeError):
    pass


class SRAM:
    def __init__(self, be, pins=PINS, timing=None, samples=3, waiter=wait_us):
        self.be, self.p = be, pins
        self.t = timing or Timing()
        self.samples, self.wait = samples, waiter
        self.st = {"PRE": 1, "E": 0, "WE": 0, "SE": 0}
        self.n_w = self.n_r = 0
        self.s_w = self.s_r = 0.0
        # 제어선부터 안전 상태로 claim → 주소/데이터 → 입력
        for n in ("E", "WE", "SE"):
            be.out(pins[n], 0)
        be.out(pins["PRE"], 1)
        for g in pins["A"] + pins["WDATA"]:
            be.out(g, 0)
        for g in pins["RDATA"]:
            be.inp(g, "none")

    # ── 저수준 ──
    def ctrl(self, name, v):
        nxt = dict(self.st, **{name: v})
        if nxt["PRE"] == 0 and (nxt["E"] or nxt["WE"]):
            raise InterlockError(f"{name}={v} 거부: PRE=0 동안 E·WE 는 0 이어야 함  {nxt}")
        if nxt["WE"] and nxt["SE"]:
            raise InterlockError(f"{name}={v} 거부: WE·SE 동시 HIGH 금지  {nxt}")
        self.be.write(self.p[name], v)
        self.st = nxt

    def set_addr(self, a):
        if self.st["E"]:
            raise InterlockError("E=1 상태에서 주소 변경 금지")
        for i, g in enumerate(self.p["A"]):
            self.be.write(g, (a >> i) & 1)
        self.wait(self.t.t_addr)

    def set_wdata(self, d):
        for i, g in enumerate(self.p["WDATA"]):
            self.be.write(g, (d >> i) & 1)

    def read_bus(self):
        return sum(self.be.read(g) << i for i, g in enumerate(self.p["RDATA"]))

    def precharge(self):
        self.ctrl("PRE", 0)
        self.wait(self.t.t_pre)
        self.ctrl("PRE", 1)
        self.wait(self.t.t_pre_off)

    # ── Write / Read ──
    def write(self, addr, data):
        t0 = time.perf_counter()
        self.set_addr(addr & 0xF)
        self.precharge()
        self.set_wdata(data & 0xF)
        self.ctrl("WE", 1); self.wait(self.t.t_wd)
        self.ctrl("E", 1);  self.wait(self.t.t_wl_w)
        self.ctrl("E", 0);  self.wait(self.t.t_hold)
        self.ctrl("WE", 0)
        self.n_w += 1
        self.s_w += time.perf_counter() - t0

    def read(self, addr):
        """반환: (다수결 값, 샘플 간 흔들린 비트 마스크)"""
        t0 = time.perf_counter()
        self.set_addr(addr & 0xF)
        self.precharge()
        self.ctrl("E", 1);  self.wait(self.t.t_dev)
        self.ctrl("SE", 1); self.wait(self.t.t_sa)
        smp = []
        for i in range(self.samples):
            if i:
                self.wait(self.t.t_smp)
            smp.append(self.read_bus())
        self.ctrl("SE", 0)
        self.ctrl("E", 0)
        val = unst = 0
        for b in range(4):
            ones = sum((s >> b) & 1 for s in smp)
            if ones * 2 > len(smp):
                val |= 1 << b
            if 0 < ones < len(smp):
                unst |= 1 << b
        self.n_r += 1
        self.s_r += time.perf_counter() - t0
        return val, unst

    def power_down_state(self):
        """종료 시 모든 출력 LOW → 칩 VDD 를 먼저 내려도 GPIO→ESD 다이오드 역전류 없음."""
        for n in ("SE", "WE", "E"):
            self.be.write(self.p[n], 0)
            self.st[n] = 0
        for g in self.p["A"] + self.p["WDATA"]:
            self.be.write(g, 0)
        self.be.write(self.p["PRE"], 0)
        self.st["PRE"] = 0


# ═══════════════════════════════════════════════════════════════════
#  결과 추적 · 8x8 불량 맵 · 원인 추정
# ═══════════════════════════════════════════════════════════════════
def rc(addr, bit):
    return addr >> 1, bit + 4 * (addr & 1)


class Tracker:
    def __init__(self, csv_path=None):
        z = lambda: [[0] * 8 for _ in range(8)]
        self.f1, self.f0, self.fu = z(), z(), z()  # 1기대→0 / 0기대→1 / 불안정
        self.hints = []
        self.summary = []
        self.fh = self.cw = None
        if csv_path:
            self.fh = open(csv_path, "w", newline="", encoding="utf-8")
            self.cw = csv.writer(self.fh)
            self.cw.writerow(["time", "test", "step", "addr", "row", "A0",
                              "expected", "read", "unstable_mask", "result"])

    def check(self, test, step, addr, exp, got, unst):
        bad = ((exp ^ got) | unst) & 0xF
        for b in range(4):
            if (bad >> b) & 1:
                r, c = rc(addr, b)
                if (unst >> b) & 1:
                    self.fu[r][c] += 1
                elif (exp >> b) & 1:
                    self.f1[r][c] += 1
                else:
                    self.f0[r][c] += 1
        if self.cw:
            self.cw.writerow([f"{time.time():.3f}", test, step, addr, addr >> 1, addr & 1,
                              f"{exp:04b}", f"{got:04b}", f"{unst:04b}", "PASS" if bad == 0 else "FAIL"])
        return bad == 0

    def hint(self, msg):
        if msg not in self.hints:
            self.hints.append(msg)

    def failed(self, r, c):
        return bool(self.f1[r][c] or self.f0[r][c] or self.fu[r][c])

    def close(self):
        if self.fh:
            self.fh.close()


def print_bitmap(trk):
    print(f"\n{C.BOLD}  불량 셀 맵{C.X}  {C.D}( . PASS | 0: 1을 써도 0 | 1: 0을 써도 1 | X: 둘 다 | ~: 샘플 불안정 ){C.X}")
    print("                      Col 0 1 2 3   4 5 6 7")
    print("                         (A0=0)    (A0=1)")
    for r in range(8):
        cells = []
        for c in range(8):
            e1, e0, u = trk.f1[r][c], trk.f0[r][c], trk.fu[r][c]
            if not (e1 or e0 or u):
                cells.append(f"{C.G}.{C.X}")
            else:
                ch = "X" if (e1 and e0) else "0" if e1 else "1" if e0 else "~"
                cells.append(f"{C.R}{ch}{C.X}")
        print(f"  WL{r} (A3A2A1={r:03b})      " + " ".join(cells[:4]) + "   " + " ".join(cells[4:]))


def diagnose(trk):
    F = [[trk.failed(r, c) for c in range(8)] for r in range(8)]
    n = sum(map(sum, F))
    if n == 0:
        return
    if n == 64:
        if any("aliasing" in h for h in trk.hints):
            return
        trk.hint("64비트 전부 실패 → VDD/VSS·공통 GND·PRE/E/WE/SE 배선·핀맵부터 (conn 테스트, 스코프로 E/PRE 파형)")
        return
    col_full = lambda c: all(F[r][c] for r in range(8))
    col_none = lambda c: not any(F[r][c] for r in range(8))
    used = set()
    for lo, hi, a0 in ((0, 4, 0), (4, 8, 1)):
        other = range(4, 8) if a0 == 0 else range(0, 4)
        if all(col_full(c) for c in range(lo, hi)) and all(col_none(c) for c in other):
            trk.hint(f"A0={a0} 쪽 4열 전체 실패, 반대쪽 정상 → A0 핀 / ColDecoder 인버터(A_b)·TG 의심")
            used |= set(range(lo, hi))
    for k in range(4):
        if k not in used and col_full(k) and col_full(k + 4):
            cells = [(r, c) for r in range(8) for c in (k, k + 4)]
            if all(trk.f0[r][c] == 0 and trk.fu[r][c] == 0 for r, c in cells):
                s = " (항상 0)"
            elif all(trk.f1[r][c] == 0 and trk.fu[r][c] == 0 for r, c in cells):
                s = " (항상 1)"
            else:
                s = ""
            trk.hint(f"Col{k}·Col{k+4} 동시 실패{s} → 공통 경로 RDATA{k}/WDATA{k} 핀·SenseAmp{k}·WriteDriver{k} 의심")
            used |= {k, k + 4}
    for c in range(8):
        if c not in used and col_full(c):
            trk.hint(f"Col{c} 만 전체 실패 → BL{c}/BLB{c} 배선·Precharger{c}·TG{c} 의심")
            used.add(c)
    rows = [r for r in range(8) if all(F[r][c] for c in range(8) if c not in used)] if len(used) < 8 else []
    if rows:
        matched = False
        for bit in range(3):
            for val in (0, 1):
                if rows == [r for r in range(8) if ((r >> bit) & 1) == val]:
                    trk.hint(f"실패 행 {rows} = A{bit+1}={val} 인 행 전부 → A{bit+1} 핀/패드 의심")
                    matched = True
        if not matched:
            for r in rows:
                trk.hint(f"WL{r} 전체 실패 → RowDecoder 출력 {r} (NAND4/INV)·WL{r} 배선 의심")
    lone = sum(F[r][c] for r in range(8) for c in range(8) if c not in used and r not in rows)
    if lone:
        trk.hint(f"개별 셀 실패 {lone}개 → 셀 결함 또는 마진 부족. retention·disturb·shmoo 로 조건 좁히기")
    if any(trk.fu[r][c] for r in range(8) for c in range(8)):
        trk.hint("샘플 불안정(~) 비트 있음 → t_dev·t_sa 늘려보기, RDATA 배선 길이/GND 리턴·디커플링 확인")


# ═══════════════════════════════════════════════════════════════════
#  테스트
# ═══════════════════════════════════════════════════════════════════
class Ctx:
    def __init__(self, sram, trk, args):
        self.s, self.trk, self.args = sram, trk, args
        self.ok = self.tot = self.shown = 0

    def reset(self):
        self.ok = self.tot = 0

    def chk(self, test, step, addr, exp):
        got, unst = self.s.read(addr)
        good = self.trk.check(test, step, addr, exp, got, unst)
        self.ok += good
        self.tot += 1
        if not good and self.shown < 40:
            self.shown += 1
            r = addr >> 1
            u = f"  unstable={unst:04b}" if unst else ""
            print(f"    {C.R}FAIL{C.X} {test}/{step:<6} addr=0x{addr:X} (WL{r}, A0={addr & 1})  "
                  f"exp={exp:04b} got={got:04b}{u}")
        return got


def checker(addr, inv=False):
    """물리적 체커보드: 셀(r,c) = (r+c)%2 → 워드값은 행 짝/홀로 결정 (A0 무관)."""
    v = 0xA if (addr >> 1) % 2 == 0 else 0x5
    return (~v & 0xF) if inv else v


def t_conn(ctx):
    """RDATA 배선/칩 구동 확인: Pi 내부 pull-up 을 켜도 SE=0 이면 칩이 RDATA 를 0 으로 잡아야 함."""
    s = ctx.s
    for g in s.p["RDATA"]:
        s.be.inp(g, "up")
    s.wait(5000)
    v = s.read_bus()
    for g in s.p["RDATA"]:
        s.be.inp(g, "none")
    for k in range(4):
        ctx.tot += 1
        if (v >> k) & 1:
            print(f"    {C.R}RDATA{k} (GPIO{s.p['RDATA'][k]}) = 1{C.X} → 칩이 구동 안 함: 배선 단선/핀 번호/칩 VDD·VSS 확인")
            ctx.trk.hint(f"RDATA{k} 가 pull-up 에 끌려 1 → 해당 핀 연결 또는 칩 전원 문제")
        else:
            ctx.ok += 1


def t_smoke(ctx):
    for addr in (0x0, 0xF):
        for d in (0x0, 0xF, 0x5, 0xA):
            ctx.s.write(addr, d)
            ctx.chk("smoke", f"w{d:X}", addr, d)


def t_addr(ctx):
    """주소=데이터 / 주소 보수 = 데이터. 디코더 aliasing 검출."""
    reads = {}
    for inv in (False, True):
        pat = (lambda a: ~a & 0xF) if inv else (lambda a: a)
        for a in range(16):
            ctx.s.write(a, pat(a))
        for a in range(16):
            reads[(inv, a)] = ctx.chk("addr", "~a" if inv else "a", a, pat(a))
    # A_b 가 칩에 반영 안 되면 a 와 a^(1<<b) 가 같은 셀 → 0→15 순서로 썼으므로
    # 두 주소 모두 bit b=1 쪽 주소의 데이터가 읽힌다. 16개 × 2 배경이 전부 이 예측과 맞을 때만 판정.
    for b in range(4):
        if all(reads[(inv, a)] == ((~(a | 1 << b) & 0xF) if inv else (a | 1 << b))
               for inv in (False, True) for a in range(16)):
            where = "ColDecoder(A0)" if b == 0 else "RowDecoder"
            ctx.trk.hint(f"주소 aliasing: A{b} 가 칩에 반영 안 됨 → A{b} 핀 배선/패드·{where} 입력 의심")


def t_march(ctx):
    """March C- (10N) × 데이터 배경 3종 (0000, 0101, 0011) → 워드 내부 커플링까지."""
    up, dn = list(range(16)), list(range(15, -1, -1))
    s = ctx.s
    for bg in (0x0, 0x5, 0x3):
        d0, d1 = bg, ~bg & 0xF
        tag = f"{bg:X}"
        for a in up: s.write(a, d0)
        for a in up: ctx.chk("march", f"M1.{tag}", a, d0); s.write(a, d1)
        for a in up: ctx.chk("march", f"M2.{tag}", a, d1); s.write(a, d0)
        for a in dn: ctx.chk("march", f"M3.{tag}", a, d0); s.write(a, d1)
        for a in dn: ctx.chk("march", f"M4.{tag}", a, d1); s.write(a, d0)
        for a in up: ctx.chk("march", f"M5.{tag}", a, d0)


def t_disturb(ctx):
    """(1) read disturb: 같은 주소 반복 읽기  (2) half-select: 한 주소를 반복 기록 후 같은 행 반대편 A0 확인."""
    s, n = ctx.s, ctx.args.reads
    for inv in (False, True):
        for a in range(16):
            s.write(a, checker(a, inv))
        for a in range(16):
            for i in range(n):
                ctx.chk("disturb", "rd" + ("~" if inv else ""), a, checker(a, inv))
    for a in range(16):
        s.write(a, checker(a))
    for a in range(16):
        for _ in range(10):
            s.write(a, checker(a, True))
        ctx.chk("disturb", "halfsel", a ^ 1, checker(a ^ 1))
        s.write(a, checker(a))


def t_retention(ctx):
    s = ctx.s
    for h in ctx.args.hold:
        for inv in (False, True):
            for a in range(16):
                s.write(a, checker(a, inv))
            print(f"    {C.D}hold {h:g} s (E=0, PRE=1){C.X}")
            time.sleep(0 if ctx.args.sim else h)
            for a in range(16):
                ctx.chk("retention", f"{h:g}s" + ("~" if inv else ""), a, checker(a, inv))


def t_shmoo(ctx):
    """타이밍 전체를 k 배로 줄여가며 addr 테스트. 결과는 불량 맵에 합산하지 않음."""
    base, s = ctx.s.t, ctx.s
    print(f"    {'scale':>6} {'write':>9} {'read':>9}   result")
    for k in (4, 2, 1, 0.5, 0.2, 0.1, 0.05, 0):
        s.t = base.scaled(k)
        s.n_w = s.n_r = 0
        s.s_w = s.s_r = 0.0
        sub = Ctx(s, Tracker(), ctx.args)
        sub.shown = 999  # 개별 FAIL 출력 생략
        t_addr(sub)
        wm = 1e3 * s.s_w / max(s.n_w, 1)
        rm = 1e3 * s.s_r / max(s.n_r, 1)
        col = C.G if sub.ok == sub.tot else C.R
        print(f"    {k:>6g} {wm:>7.2f}ms {rm:>7.2f}ms   {col}{sub.ok}/{sub.tot}{C.X}")
        ctx.ok += sub.ok
        ctx.tot += sub.tot
    s.t = base


TESTS = {
    "conn": ("RDATA 연결 확인", t_conn),
    "smoke": ("기본 R/W (0x0, 0xF)", t_smoke),
    "addr": ("주소 디코더 (addr, ~addr)", t_addr),
    "march": ("March C- ×3 배경", t_march),
    "disturb": ("Read disturb · Half-select", t_disturb),
    "retention": ("Retention", t_retention),
    "shmoo": ("타이밍 스케일 스윕", t_shmoo),
}
ALL = ["conn", "smoke", "addr", "march", "disturb", "retention"]


# ═══════════════════════════════════════════════════════════════════
#  수동 모드
# ═══════════════════════════════════════════════════════════════════
SHELL_HELP = """  w <addr> <data>   쓰기 (hex)          r <addr>      읽기
  fill <data>       전체 주소에 쓰기     dump          8x8 비트맵으로 전체 읽기
  pin <PRE|E|WE|SE> <0|1>  제어선 직접 (interlock 적용, 스코프 확인용)
  addr <a>          주소만 설정          wd <data>     WDATA 만 설정
  t                 타이밍 보기          set <필드> <µs> 타이밍 변경
  q                 종료"""


def shell(s):
    print(SHELL_HELP)
    while True:
        try:
            cmd = input(f"{C.B}sram> {C.X}").split()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not cmd:
            continue
        try:
            op = cmd[0].lower()
            if op == "q":
                return
            elif op == "w":
                a, d = int(cmd[1], 16), int(cmd[2], 16)
                s.write(a, d)
                print(f"  write 0x{a:X} ← {d:04b}")
            elif op == "r":
                a = int(cmd[1], 16)
                v, u = s.read(a)
                print(f"  read  0x{a:X} → {v:04b} (0x{v:X})" + (f"  {C.Y}unstable {u:04b}{C.X}" if u else ""))
            elif op == "fill":
                d = int(cmd[1], 16)
                for a in range(16):
                    s.write(a, d)
            elif op == "dump":
                print("                 Col 0 1 2 3   4 5 6 7")
                for r in range(8):
                    bits = []
                    for a0 in (0, 1):
                        v, u = s.read(r << 1 | a0)
                        bits += [("~" if (u >> k) & 1 else str((v >> k) & 1)) for k in range(4)]
                    print(f"  WL{r} ({r:03b})        " + " ".join(bits[:4]) + "   " + " ".join(bits[4:]))
            elif op == "pin":
                s.ctrl(cmd[1].upper(), int(cmd[2]))
                print(f"  {s.st}")
            elif op == "addr":
                s.set_addr(int(cmd[1], 16) & 0xF)
            elif op == "wd":
                s.set_wdata(int(cmd[1], 16) & 0xF)
            elif op == "t":
                print(f"  {asdict(s.t)}")
            elif op == "set":
                setattr(s.t, cmd[1], int(cmd[2]))
                print(f"  {asdict(s.t)}")
            else:
                print(SHELL_HELP)
        except InterlockError as e:
            print(f"  {C.R}{e}{C.X}")
        except (IndexError, ValueError, AttributeError, KeyError):
            print(f"  {C.Y}형식 오류{C.X}")


# ═══════════════════════════════════════════════════════════════════
#  main
# ═══════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description="PKNU_2026_M12 8x8 SRAM R/W tester",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="tests: " + ", ".join(TESTS) + ", all, shell")
    ap.add_argument("tests", nargs="*", default=["all"])
    ap.add_argument("--sim", action="store_true", help="하드웨어 없이 칩 모델로 실행")
    ap.add_argument("--fault", action="append", default=[], help="sim 결함 주입 (s0:r,c / s1:r,c / row:r / pin:A2=0)")
    ap.add_argument("--backend", choices=["auto", "lgpio", "rpigpio"], default="auto")
    ap.add_argument("--chip", type=int, help="gpiochip 번호 강제 (lgpio)")
    ap.add_argument("--scale", type=float, default=1.0, help="모든 타이밍 배율")
    ap.add_argument("--samples", type=int, default=3, help="read 1회당 RDATA 샘플 수")
    ap.add_argument("--reads", type=int, default=20, help="disturb: 주소당 반복 읽기 수")
    ap.add_argument("--hold", type=float, nargs="+", default=[1, 10], help="retention 대기(s)")
    ap.add_argument("--csv", help="결과 CSV 경로 (실측 시 기본 자동 생성)")
    ap.add_argument("-y", "--yes", action="store_true", help="전원 확인 프롬프트 생략")
    args = ap.parse_args()

    names = []
    for t in args.tests:
        names += ALL if t == "all" else [t]
    bad = [t for t in names if t not in TESTS and t != "shell"]
    if bad:
        ap.error(f"알 수 없는 테스트: {bad}")

    if not args.sim and not args.yes:
        input(f"{C.Y}칩 VDD=3.3V·VSS 연결 및 전원 ON, Pi GND 공통 확인 후 Enter "
              f"(칩 전원 없이 GPIO가 HIGH 를 내면 ESD 다이오드로 역전류){C.X}")

    csv_path = args.csv or (None if args.sim else time.strftime("sram_log_%Y%m%d_%H%M%S.csv"))
    be = make_backend(args)
    waiter = (lambda us: None) if args.sim else wait_us
    try:
        s = SRAM(be, timing=Timing().scaled(args.scale), samples=args.samples, waiter=waiter)
    except Exception as e:
        be.close()
        sys.exit(f"GPIO 초기화 실패: {e}\n  → GPIO 7/8 사용 중이면 SPI 비활성화, 다른 프로그램이 핀을 잡고 있는지 확인")

    trk = Tracker(csv_path)
    ctx = Ctx(s, trk, args)
    print(f"{C.BOLD}PKNU_2026_M12 SRAM tester{C.X}  backend={be.name}  scale={args.scale:g}  samples={args.samples}"
          + (f"  csv={csv_path}" if csv_path else ""))

    try:
        for name in names:
            if name == "shell":
                shell(s)
                continue
            title, fn = TESTS[name]
            print(f"\n{C.BOLD}▶ {name}{C.X}  {C.D}{title}{C.X}")
            ctx.reset()
            fn(ctx)
            col = C.G if ctx.ok == ctx.tot else C.R
            print(f"  {col}{ctx.ok}/{ctx.tot}{C.X}")
            trk.summary.append((name, ctx.ok, ctx.tot))
            if name == "smoke" and ctx.ok < ctx.tot // 2 and len(names) > 1:
                print(f"  {C.R}기본 R/W 가 전혀 안 됨 → 이후 테스트 생략. conn/배선/전원/핀맵 먼저 확인{C.X}")
                break
    except KeyboardInterrupt:
        print(f"\n{C.Y}중단됨{C.X}")
    except InterlockError as e:
        print(f"\n{C.R}Interlock: {e}{C.X}")
    finally:
        s.power_down_state()
        be.close()
        trk.close()

    if trk.summary:
        print(f"\n{C.BOLD}══ 요약 ══{C.X}")
        for name, ok, tot in trk.summary:
            col = C.G if ok == tot else C.R
            print(f"  {name:<10} {col}{ok:>5}/{tot:<5}{C.X}")
        if s.n_w or s.n_r:
            print(f"  {C.D}평균 write {1e3 * s.s_w / max(s.n_w, 1):.2f} ms, "
                  f"read {1e3 * s.s_r / max(s.n_r, 1):.2f} ms (Python 오버헤드 포함){C.X}")
        if any(n in ("smoke", "addr", "march", "disturb", "retention") for n, _, _ in trk.summary):
            print_bitmap(trk)
        diagnose(trk)
        for h in trk.hints:
            print(f"  {C.Y}→ {h}{C.X}")
    if args.sim and isinstance(be, SimBackend):
        print(f"  {C.D}[sim] interlock 위반 {len(be.violations)}건, precharge 없이 WL 오픈 {be.no_pre}건{C.X}")

    all_ok = all(ok == tot for _, ok, tot in trk.summary)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()