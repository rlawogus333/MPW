#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PKNU_2026_M12  8x8 (64-bit) 6T SRAM — Raspberry Pi 제어 타이밍 발생기   [E 고정 HIGH]
  칩 VDD = 3.3 V, VSS = 0 V, 라즈베리파이 3.3 V GPIO 직결

[역할 분담]
  라즈베리파이  PRE · WE · SE 타이밍만 발생  (+ E=HIGH 유지, 주소 고정, 스코프 SYNC)
  외부 장비     WDATA 펄스 인가 (펑션 제너레이터 등)
  스코프        WDATA ↔ RDATA 비교   ※ Pi 는 WDATA/RDATA 를 건드리지 않음

[제어 신호]
  PRE  Active-LOW  프리차지 (BL·BLB → VDD)
  WE   Active-HIGH write driver ON → BL = WDATA.  E=1 이라 WL 이 이미 열려 있어 WE=1 동안 셀에 기록
       → 셀에 최종 저장되는 값 = WE 하강 에지 순간의 WDATA
  SE   Active-HIGH sense amp ON.  래치 없음 → SE=0 이면 RDATA=0, 스코프는 SE=1 구간에서 볼 것

[1 사이클 (rw 모드)]
        ┌ WRITE ─────────────────────────┐┌ READ ──────────────────────────────┐
  PRE ‾‾\____/‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\____/‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
  WE  ____________/‾‾‾‾‾‾‾‾\______________________________________________
  SE  ____________________________________________/‾‾‾‾‾‾‾‾‾\_____________
  SYNC /‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\________________________________
       t_pre  t_pre_off  t_we   t_hold    t_pre    t_dev     t_se    t_gap

[interlock]
  PRE=0 동안 WE=0  /  WE·SE 동시 HIGH 금지  /  E 토글 금지

설치 (Raspberry Pi OS Bookworm):  sudo apt install python3-lgpio
  - lgpio 가 없으면 RPi.GPIO 로 자동 fallback (단, Pi 5는 RPi.GPIO 불가)
  - GPIO 7, 8 은 SPI0 CS 핀. raspi-config 에서 SPI 를 꺼두어야 claim 가능

사용 예:
  python3 sram_rw_test.py --sim -n 2 --log          # PC에서 시퀀스/에지 확인
  python3 sram_rw_test.py rw                         # write→read 무한 반복 (Ctrl+C 종료)
  python3 sram_rw_test.py rw -n 1000 --addr 5
  python3 sram_rw_test.py w                          # write 펄스만 반복
  python3 sram_rw_test.py r                          # read 펄스만 반복
  python3 sram_rw_test.py rw --set t_we=5000 --set t_se=20000
  python3 sram_rw_test.py rw --scale 10              # 전체 타이밍 10배 (스코프로 보기 쉽게)
  python3 sram_rw_test.py shell                      # 수동으로 핀/시퀀스 한 번씩
"""
import argparse
import sys
import time
from dataclasses import dataclass, asdict, fields

# ═══════════════════════════════════════════════════════════════════
#  핀 맵 (BCM 번호) — sram_test_guide_v3 배정 유지
#  WDATA/RDATA 핀(12,16,20,21 / 26,19,13,6)은 이 스크립트에서 claim 하지 않음
# ═══════════════════════════════════════════════════════════════════
PINS = {
    "PRE": 17,
    "E": 27,
    "WE": 8,
    "SE": 7,
    "A": [18, 23, 24, 25],      # A0, A1, A2, A3
}
SYNC_DEFAULT = 22               # 스코프 트리거용 (빈 GPIO). 연결 안 해도 무방


# ═══════════════════════════════════════════════════════════════════
#  타이밍 (단위 µs)
#  Python GPIO 토글 지터가 수십 µs 이므로 ms 단위로 시작.
#  외부 WDATA 펄스 주기와 맞출 때는 --set / --scale 로 조정.
# ═══════════════════════════════════════════════════════════════════
@dataclass
class Timing:
    t_pre: int = 1000       # PRE=0 폭
    t_pre_off: int = 500    # PRE=1 → WE=1
    t_we: int = 2000        # WE=1 폭 (이 구간 WDATA 가 셀에 기록, 하강 에지 값이 최종)
    t_hold: int = 500       # WE=0 → 다음 PRE=0
    t_dev: int = 1000       # read: PRE=1 → SE=1 (BL/BLB 차동 형성)
    t_se: int = 2000        # SE=1 폭 (이 구간에 RDATA 유효)
    t_gap: int = 1000       # SE=0 → 다음 사이클

    def scaled(self, k: float) -> "Timing":
        return Timing(**{n: max(0, int(v * k)) for n, v in asdict(self).items()})

    def period(self, mode):
        w = self.t_pre + self.t_pre_off + self.t_we + self.t_hold
        r = self.t_pre + self.t_dev + self.t_se + self.t_gap
        return {"rw": w + r, "w": w, "r": r}[mode]


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
#  GPIO 백엔드 (출력만 사용)
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

    def write(self, g, v):
        self.lg.gpio_write(self.h, g, v)

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

    def write(self, g, v):
        self.G.output(g, v)

    def close(self):
        self.G.cleanup()


class SimBackend:
    """하드웨어 없이 에지 순서·interlock 확인. --log 면 모든 에지를 시간과 함께 출력."""
    name = "sim"

    def __init__(self, log=False):
        self.lv, self.log = {}, log
        self.names = {g: n for n, g in PINS.items() if isinstance(g, int)}
        self.names.update({g: f"A{i}" for i, g in enumerate(PINS["A"])})
        self.t0 = time.perf_counter()
        self.violations = 0
        self.edges = 0

    def _chk(self):
        pre = self.lv.get(PINS["PRE"], 1)
        we, se = self.lv.get(PINS["WE"], 0), self.lv.get(PINS["SE"], 0)
        if (pre == 0 and we) or (we and se):
            self.violations += 1

    def out(self, g, level):
        self.lv[g] = level
        self._chk()

    def write(self, g, v):
        if self.lv.get(g) != v:
            self.edges += 1
            if self.log:
                ms = 1e3 * (time.perf_counter() - self.t0)
                print(f"    {C.D}{ms:9.3f} ms  {self.names.get(g, f'GPIO{g}'):<5}{'↑' if v else '↓'}{C.X}")
        self.lv[g] = v
        self._chk()

    def close(self):
        pass


def make_backend(args):
    if args.sim:
        return SimBackend(args.log)
    if args.backend in ("auto", "lgpio"):
        try:
            return LgpioBackend(args.chip)
        except ImportError:
            if args.backend == "lgpio":
                raise
    return RPiGPIOBackend()


# ═══════════════════════════════════════════════════════════════════
#  제어 신호 발생기
# ═══════════════════════════════════════════════════════════════════
class InterlockError(RuntimeError):
    pass


class CtrlGen:
    def __init__(self, be, timing, addr=0, drive_addr=True, e_ext=False, sync=SYNC_DEFAULT, waiter=wait_us):
        self.be, self.t, self.wait = be, timing, waiter
        self.e_ext, self.drive_addr, self.sync = e_ext, drive_addr, sync
        self.st = {"PRE": 1, "WE": 0, "SE": 0}
        # 안전 상태: WE=SE=0, PRE=0(BL=VDD 로 잡은 채) → 주소 → E=1 → PRE=1
        be.out(PINS["WE"], 0)
        be.out(PINS["SE"], 0)
        be.out(PINS["PRE"], 0)
        self.st["PRE"] = 0
        if drive_addr:
            for i, g in enumerate(PINS["A"]):
                be.out(g, (addr >> i) & 1)
        if sync >= 0:
            be.out(sync, 0)
        if not e_ext:
            be.out(PINS["E"], 1)
        self.wait(self.t.t_pre)
        self.ctrl("PRE", 1)
        self.n_w = self.n_r = 0

    def ctrl(self, name, v):
        if name not in self.st:
            raise InterlockError(f"{name} 는 제어 대상 아님 (PRE/WE/SE 만, E 는 HIGH 고정)")
        nxt = dict(self.st, **{name: v})
        if nxt["PRE"] == 0 and nxt["WE"]:
            raise InterlockError(f"{name}={v} 거부: PRE=0 동안 WE 는 0 이어야 함")
        if nxt["WE"] and nxt["SE"]:
            raise InterlockError(f"{name}={v} 거부: WE·SE 동시 HIGH 금지")
        self.be.write(PINS[name], v)
        self.st = nxt

    def _sync(self, v):
        if self.sync >= 0:
            self.be.write(self.sync, v)

    def idle(self):
        """WE=SE=0 으로 복귀 (수동 조작·중단 후에도 다음 사이클이 안전하게 시작되도록)."""
        for n in ("SE", "WE"):
            if self.st[n]:
                self.ctrl(n, 0)

    def precharge(self):
        self.idle()
        self.ctrl("PRE", 0)
        self.wait(self.t.t_pre)
        self.ctrl("PRE", 1)

    def write_cycle(self):
        self._sync(1)
        self.precharge()
        self.wait(self.t.t_pre_off)
        self.ctrl("WE", 1); self.wait(self.t.t_we)
        self.ctrl("WE", 0); self.wait(self.t.t_hold)
        self._sync(0)
        self.n_w += 1

    def read_cycle(self):
        self.precharge()
        self.wait(self.t.t_dev)
        self.ctrl("SE", 1); self.wait(self.t.t_se)
        self.ctrl("SE", 0); self.wait(self.t.t_gap)
        self.n_r += 1

    def power_down(self):
        """모든 출력 LOW → 칩 VDD 를 먼저 내려도 GPIO→ESD 다이오드 역전류 없음."""
        for n in ("SE", "WE"):
            self.be.write(PINS[n], 0)
        self.be.write(PINS["PRE"], 0)
        if not self.e_ext:
            self.be.write(PINS["E"], 0)
        if self.drive_addr:
            for g in PINS["A"]:
                self.be.write(g, 0)
        self._sync(0)


def run(gen, mode, n):
    """n=0 이면 Ctrl+C 까지 무한 반복."""
    per = gen.t.period(mode) / 1e3
    print(f"  mode={mode}  주기≈{per:.2f} ms ({1e3 / per:.1f} Hz, Python 오버헤드 제외)  "
          f"{'무한 반복 — Ctrl+C 종료' if n == 0 else f'{n} 사이클'}")
    i, t_start, t_print = 0, time.perf_counter(), time.perf_counter()
    while n == 0 or i < n:
        if mode in ("rw", "w"):
            gen.write_cycle()
        if mode in ("rw", "r"):
            gen.read_cycle()
        i += 1
        now = time.perf_counter()
        if now - t_print >= 1.0:
            t_print = now
            real = 1e3 * (now - t_start) / i
            print(f"\r  cycle {i}  실측 주기 {real:.2f} ms   ", end="", flush=True)
    real = 1e3 * (time.perf_counter() - t_start) / max(i, 1)
    print(f"\r  {i} 사이클 완료  실측 주기 {real:.2f} ms        ")


# ═══════════════════════════════════════════════════════════════════
#  수동 모드
# ═══════════════════════════════════════════════════════════════════
SHELL_HELP = """  pin <PRE|WE|SE> <0|1>   제어선 직접 (interlock 적용)
  w [n]     write 사이클 n회 (PRE 펄스 → WE 펄스)
  r [n]     read 사이클 n회  (PRE 펄스 → SE 펄스)
  rw [n]    write→read n회
  se <ms>   SE=1 을 ms 동안 유지 (스코프로 RDATA 천천히 보기)
  t         타이밍 보기          set <필드> <µs>   타이밍 변경
  q         종료"""


def shell(gen):
    print(SHELL_HELP)
    while True:
        try:
            cmd = input(f"{C.B}ctrl> {C.X}").split()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not cmd:
            continue
        try:
            op = cmd[0].lower()
            if op == "q":
                return
            elif op == "pin":
                gen.ctrl(cmd[1].upper(), int(cmd[2]))
                print(f"  {gen.st}")
            elif op in ("w", "r", "rw"):
                run(gen, op, int(cmd[1]) if len(cmd) > 1 else 1)
            elif op == "se":
                gen.precharge()
                gen.wait(gen.t.t_dev)
                gen.ctrl("SE", 1)
                time.sleep(float(cmd[1]) / 1e3)
                gen.ctrl("SE", 0)
            elif op == "t":
                print(f"  {asdict(gen.t)}")
            elif op == "set":
                setattr(gen.t, cmd[1], int(cmd[2]))
                print(f"  {asdict(gen.t)}")
            else:
                print(SHELL_HELP)
        except InterlockError as e:
            print(f"  {C.R}{e}{C.X}")
        except KeyboardInterrupt:
            print(f"\n  {C.Y}중단{C.X}")
        except (IndexError, ValueError, AttributeError, KeyError):
            print(f"  {C.Y}형식 오류{C.X}")


# ═══════════════════════════════════════════════════════════════════
#  main
# ═══════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description="PKNU_2026_M12 SRAM 제어 타이밍 발생기 (PRE/WE/SE, E=HIGH 고정)",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="timing fields: " + ", ".join(f.name for f in fields(Timing)))
    ap.add_argument("mode", nargs="?", default="rw", choices=["rw", "w", "r", "shell"])
    ap.add_argument("-n", type=int, default=0, help="사이클 수 (0 = Ctrl+C 까지 무한)")
    ap.add_argument("--addr", type=lambda s: int(s, 0), default=0,
                    help="고정 주소 0~15 (bit0=A0, bit3=A3). 기본 0")
    ap.add_argument("--no-addr", action="store_true", help="주소를 외부에서 고정 → A 핀 claim 안 함")
    ap.add_argument("--e-ext", action="store_true", help="E 를 보드에서 VDD 에 직결 → GPIO27 사용 안 함")
    ap.add_argument("--sync", type=int, default=SYNC_DEFAULT,
                    help=f"스코프 트리거 GPIO (write 구간 HIGH). -1 = 끔. 기본 {SYNC_DEFAULT}")
    ap.add_argument("--set", action="append", default=[], metavar="FIELD=US", help="개별 타이밍 변경 (µs)")
    ap.add_argument("--scale", type=float, default=1.0, help="모든 타이밍 배율")
    ap.add_argument("--sim", action="store_true", help="하드웨어 없이 실행")
    ap.add_argument("--log", action="store_true", help="sim: 모든 에지 출력")
    ap.add_argument("--backend", choices=["auto", "lgpio", "rpigpio"], default="auto")
    ap.add_argument("--chip", type=int, help="gpiochip 번호 강제 (lgpio)")
    ap.add_argument("-y", "--yes", action="store_true", help="전원 확인 프롬프트 생략")
    args = ap.parse_args()

    if not 0 <= args.addr <= 15:
        ap.error("--addr 는 0~15")
    t = Timing()
    for kv in args.set:
        k, _, v = kv.partition("=")
        if k not in asdict(t):
            ap.error(f"알 수 없는 타이밍 필드: {k}  (가능: {', '.join(asdict(t))})")
        setattr(t, k, int(float(v)))
    t = t.scaled(args.scale)

    if not args.sim and not args.yes:
        input(f"{C.Y}칩 VDD=3.3V·VSS 연결 및 전원 ON, Pi GND·펄스 발생기 GND 공통 확인 후 Enter "
              f"(칩 전원 없이 GPIO 가 HIGH 를 내면 ESD 다이오드로 역전류){C.X}")

    be = make_backend(args)
    a = args.addr
    print(f"{C.BOLD}PKNU_2026_M12 SRAM ctrl{C.X}  backend={be.name}  scale={args.scale:g}")
    print(f"  E=HIGH{' (외부)' if args.e_ext else ' (GPIO27)'}  |  "
          + ("주소 외부 고정" if args.no_addr else
             f"addr=0x{a:X} → WL{a >> 1} (A3A2A1={a >> 1:03b}), A0={a & 1} → Col{'4~7' if a & 1 else '0~3'}")
          + f"  |  SYNC={'GPIO' + str(args.sync) if args.sync >= 0 else '끔'}")
    print(f"  {C.D}{asdict(t)}{C.X}")
    try:
        gen = CtrlGen(be, t, addr=args.addr, drive_addr=not args.no_addr, e_ext=args.e_ext,
                      sync=args.sync, waiter=wait_us)
    except Exception as e:
        be.close()
        sys.exit(f"GPIO 초기화 실패: {e}\n  → GPIO 7/8 사용 중이면 SPI 비활성화, 다른 프로그램이 핀을 잡고 있는지 확인")


    try:
        if args.mode == "shell":
            shell(gen)
        else:
            run(gen, args.mode, args.n)
    except KeyboardInterrupt:
        print(f"\n  {C.Y}중단됨{C.X}  write {gen.n_w}회, read {gen.n_r}회")
    except InterlockError as e:
        print(f"\n{C.R}Interlock: {e}{C.X}")
    finally:
        gen.power_down()
        be.close()

    if isinstance(be, SimBackend):
        print(f"  {C.D}[sim] 에지 {be.edges}개, interlock 위반 {be.violations}건{C.X}")


if __name__ == "__main__":
    main()
