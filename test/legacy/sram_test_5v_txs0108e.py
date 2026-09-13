#!/usr/bin/env python3
"""
========================================================
  8x8 64-bit SRAM Test Script for Raspberry Pi
  PDK: NSPL 0.5um Analog CMOS 2P3M 5V
  Hardware: Level-shifted via TXS0108E (3.3V <-> 5V)

  Timing: Cadence Virtuoso testbench simulation 기반
  (sram_test_guide_v3.docx 참조)
========================================================

Circuit topology:
  - 6T SRAM cell (8x8 array)
  - Precharge: PMOS-based, BL/BLB equalization
  - Row Decoder: MUX-based with E (Enable) signal
                 A[1:3] -> WL[0:7],  E=HIGH -> 디코더 활성화
  - Column Decoder: Transmission gate, A[0] -> column select
  - Sense Amp: Current mirror type voltage sense amplifier
  - Write Driver: Inverted write (WDATA 1 -> BL=0, BLB=1)

Pin interface:
  Inputs  : PRE, E, A[0:3], SE, WE, WDATA[0:3]
  Outputs : RDATA[0:3]
  Power   : VDD=5V (via level shifter VCCB), VSS=GND

Address space:
  A[1:3] -> Row (3-bit, WL[0]~WL[7], 8 rows)
  A[0]   -> Column (1-bit, selects one of two 4-bit word columns)
  Total  : 4-bit x 16 locations = 64-bit
========================================================
"""

import RPi.GPIO as GPIO
import time
import sys

# ─────────────────────────────────────────────
#  GPIO Pin Assignment (BCM numbering)
#  TXS0108E 2개 사용 (IC#1: ch1~ch8, IC#2: ch1~ch8)
#
#  IC#1: PRE, A[0], A[1], A[2], A[3], WE, SE, WDATA[0]
#  IC#2: WDATA[1], WDATA[2], WDATA[3], RDATA[0],
#        RDATA[1], RDATA[2], RDATA[3], E
# ─────────────────────────────────────────────

PIN_PRE    = 17           # Precharge enable  (Active LOW)
PIN_E      = 27           # Row Decoder Enable (Active HIGH)
                          # → TXS0108E IC#2 ch8 (이전 미사용 채널)

PIN_A      = [18,         # A[0] : Column select
              23,         # A[1] : Row address bit 0
              24,         # A[2] : Row address bit 1
              25]         # A[3] : Row address bit 2

PIN_WE     = 8            # Write enable  (Active HIGH)
PIN_SE     = 7            # Sense amp enable (Active HIGH)

PIN_WDATA  = [12,         # WDATA[0]
              16,         # WDATA[1]
              20,         # WDATA[2]
              21]         # WDATA[3]

PIN_RDATA  = [26,         # RDATA[0]
              19,         # RDATA[1]
              13,         # RDATA[2]
              6]          # RDATA[3]

# ─────────────────────────────────────────────
#  Timing Parameters (seconds)
#  Cadence Virtuoso testbench simulation 기반
#  (sram_test_guide_v3.docx Section 3 참조)
#
#  [Write 타이밍 근거]
#  T_PRECHARGE  : PMOS 3개가 BL/BLB → VDD(5V) 충전
#                 기생 커패시턴스 ~50 fF, PMOS Ron ~수 kΩ
#                 RC 시정수 ~수십 ns, 10× 마진 → 50 μs
#  T_ADDR_SETUP : Row decoder MUX 전파 지연(0.5μm 공정 ~수 ns)
#                 + RPi 소프트웨어 오버헤드 보정 → 10 μs
#  T_WRITE_HOLD : Write driver가 BL/BLB에 데이터 주입
#                 + 6T cell 내부 latch 완전 반전 시간 → 50 μs
#  T_CYCLE      : 연속 사이클 간 BL/BLB 잔류 전하 소산 → 100 μs
#
#  [Read 타이밍 근거]
#  T_PRECHARGE  : Write와 동일. 이전 R/W 잔류 ΔV 완전 소거 → 50 μs
#  T_ADDR_SETUP : WL 어서트 후 BL/BLB 미세 방전 ΔV 형성 대기
#                 SE 인가 전 충분한 차분 확보 → 10 μs
#  T_SE_HOLD    : Current mirror type sense amp가
#                 BL-BLB 차이(~수십 mV) → 풀스윙(0~5V) 증폭
#                 + 출력 인버터 체인 정착 시간 포함 → 50 μs
#  T_CYCLE      : 연속 사이클 간 간섭 방지 → 100 μs
#
#  ⚠️  PRE와 SE는 절대 동시에 HIGH가 되면 안 됨!
#      PRE HIGH 전환 후 T_ADDR_SETUP 대기 → SE HIGH 순서 필수.
# ─────────────────────────────────────────────

T_PRECHARGE  = 50e-6    # Precharge pulse width         (50 us)
T_ADDR_SETUP = 10e-6    # Address/WL setup time         (10 us)
T_WRITE_HOLD = 50e-6    # WE assert hold (latch time)   (50 us)
T_SE_HOLD    = 50e-6    # SE hold (sense amp settling)  (50 us)
T_CYCLE      = 100e-6   # Inter-cycle BL/BLB drain time (100 us)

# ─────────────────────────────────────────────
#  ANSI Color Codes for terminal output
# ─────────────────────────────────────────────

class Color:
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    CYAN    = '\033[96m'
    BOLD    = '\033[1m'
    RESET   = '\033[0m'
    GRAY    = '\033[90m'

# ═══════════════════════════════════════════════
#  GPIO Initialization
# ═══════════════════════════════════════════════

def gpio_init():
    """Initialize all GPIO pins."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    outputs = [PIN_PRE, PIN_E, PIN_WE, PIN_SE] + PIN_A + PIN_WDATA
    inputs  = PIN_RDATA

    for pin in outputs:
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

    for pin in inputs:
        GPIO.setup(pin, GPIO.IN)

    # Safe idle state:
    #   PRE=HIGH (precharge disabled, active LOW)
    #   E=LOW    (row decoder disabled)
    #   WE=LOW   (write disabled)
    #   SE=LOW   (sense amp disabled)
    GPIO.output(PIN_PRE, GPIO.HIGH)
    GPIO.output(PIN_E,   GPIO.LOW)
    GPIO.output(PIN_WE,  GPIO.LOW)
    GPIO.output(PIN_SE,  GPIO.LOW)

    print(f"{Color.CYAN}[INIT] GPIO initialized (BCM mode){Color.RESET}")
    print(f"{Color.CYAN}[INIT] E(Row Decoder EN) -> GPIO {PIN_E} | "
          f"WE -> GPIO {PIN_WE} | SE -> GPIO {PIN_SE}{Color.RESET}")


def gpio_cleanup():
    """Release all GPIO resources."""
    GPIO.output(PIN_PRE, GPIO.HIGH)
    GPIO.output(PIN_E,   GPIO.LOW)
    GPIO.output(PIN_WE,  GPIO.LOW)
    GPIO.output(PIN_SE,  GPIO.LOW)
    for pin in PIN_WDATA:
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()
    print(f"{Color.CYAN}[INIT] GPIO cleaned up{Color.RESET}")

# ═══════════════════════════════════════════════
#  Low-level Signal Helpers
# ═══════════════════════════════════════════════

def set_address(addr4bit: int):
    """
    Drive A[0:3] pins.
    A[0]   = column select (bit 0 of addr)
    A[1:3] = row address   (bits 1-3 of addr -> WL[0]~WL[7])
    """
    for i, pin in enumerate(PIN_A):
        GPIO.output(pin, (addr4bit >> i) & 1)


def set_wdata(data4bit: int):
    """Drive WDATA[0:3] pins."""
    for i, pin in enumerate(PIN_WDATA):
        GPIO.output(pin, (data4bit >> i) & 1)


def read_rdata() -> int:
    """Sample RDATA[0:3] and return as integer."""
    val = 0
    for i, pin in enumerate(PIN_RDATA):
        if GPIO.input(pin):
            val |= (1 << i)
    return val

# ═══════════════════════════════════════════════
#  SRAM Write Operation
# ═══════════════════════════════════════════════

def sram_write(addr: int, data: int):
    """
    Write 4-bit data to 4-bit address.

    Testbench 기반 Write 타이밍 시퀀스
    (sram_test_guide_v3.docx Section 3.1):

      1. PRE = LOW
         → PMOS 3개 도통: BL→VDD, BLB→VDD, BL=BLB 등화
         → memory effect 초기화
      2. PRE = HIGH  (T_PRECHARGE 후)
         → Precharge 종료, BL/BLB floating at VDD
      3. T_ADDR_SETUP 대기
         → WL이 완전히 어서트된 후 Write driver가 동작해야 함
      4. A[0:3] 확정 + E = HIGH
         → Row decoder 활성화, WL[x] 어서트
         → Column decoder 방향 결정
      5. WDATA[0:3] 인가
         → Write driver 입력 준비 (WE 인가 전에 데이터 확정)
      6. WE = HIGH
         → Write driver 활성화
         → WDATA=1이면 BL=LOW, BLB=HIGH (반전 기록)
         → 6T cell latch 반전 (T_WRITE_HOLD 동안 유지)
      7. WE = LOW  (T_WRITE_HOLD 후)
         → 쓰기 종료, 셀 데이터 확정
      8. E = LOW
         → Row decoder 비활성화, WL 디어서트
      9. T_CYCLE 대기
         → BL/BLB 잔류 전하 소산
    """
    # Step 1-2: Precharge (PRE LOW → HIGH)
    GPIO.output(PIN_PRE, GPIO.LOW)
    time.sleep(T_PRECHARGE)
    GPIO.output(PIN_PRE, GPIO.HIGH)

    # Step 3: PRE HIGH 후 WL 어서트 대기
    time.sleep(T_ADDR_SETUP)

    # Step 4: Address 확정 + Row Decoder 활성화
    set_address(addr)
    GPIO.output(PIN_E, GPIO.HIGH)

    # Step 5: WDATA 확정 (WE 인가 전에 데이터 준비)
    set_wdata(data)

    # Step 6: WE 어서트 → Write driver 활성화, latch 반전
    GPIO.output(PIN_WE, GPIO.HIGH)
    time.sleep(T_WRITE_HOLD)

    # Step 7: WE 디어서트 → 쓰기 종료
    GPIO.output(PIN_WE, GPIO.LOW)

    # WDATA 클리어 (안전)
    set_wdata(0)

    # Step 8: Row Decoder 비활성화
    GPIO.output(PIN_E, GPIO.LOW)

    # Step 9: 잔류 전하 소산 대기
    time.sleep(T_CYCLE)


# ═══════════════════════════════════════════════
#  SRAM Read Operation
# ═══════════════════════════════════════════════

def sram_read(addr: int) -> int:
    """
    Read 4-bit data from 4-bit address.

    Testbench 기반 Read 타이밍 시퀀스
    (sram_test_guide_v3.docx Section 3.2):

      1. PRE = LOW
         → BL, BLB 동시에 VDD로 precharge 및 equalize (BL = BLB = VDD)
         → 이전 Read/Write 잔류 ΔV 완전 소거
      2. PRE = HIGH  (T_PRECHARGE 후)
         → Precharge 종료
      3. A[0:3] 설정 + E = HIGH + WE = LOW 확인
         → Row decoder 활성화, WL 어서트
         → 셀 저장값에 따라 BL 또는 BLB가 약간 방전
      4. T_ADDR_SETUP 대기
         → BL-BLB 차분(ΔV ~수십 mV)이 충분히 형성될 때까지 대기
         ⚠️  PRE HIGH 후 SE HIGH 사이에 반드시 이 대기 필요
             (PRE와 SE 동시 HIGH 시 Sense Amp 출력 undefined)
      5. SE = HIGH
         → Sense Amp 활성화
         → Current mirror가 BL-BLB ΔV 증폭 → RDATA 확정
      6. T_SE_HOLD 대기
         → Sense Amp 풀스윙 정착 + 출력 인버터 체인 안정화
      7. RDATA[0:3] 샘플링
      8. SE = LOW
         → Sense Amp 비활성화
      9. E = LOW
         → Row decoder 비활성화
     10. T_CYCLE 대기
         → BL/BLB 잔류 전하 소산 및 간섭 방지
    """
    # Step 1-2: Precharge (PRE LOW → HIGH)
    GPIO.output(PIN_PRE, GPIO.LOW)
    time.sleep(T_PRECHARGE)
    GPIO.output(PIN_PRE, GPIO.HIGH)

    # Step 3: Address 설정 + Row Decoder 활성화, WE LOW 확인
    set_address(addr)
    GPIO.output(PIN_E,  GPIO.HIGH)
    GPIO.output(PIN_WE, GPIO.LOW)

    # Step 4: BL-BLB ΔV 형성 대기 (PRE→SE 사이 필수 딜레이)
    time.sleep(T_ADDR_SETUP)

    # Step 5: SE 어서트 → Sense Amp 활성화
    GPIO.output(PIN_SE, GPIO.HIGH)

    # Step 6: Sense Amp 정착 대기
    time.sleep(T_SE_HOLD)

    # Step 7: RDATA 샘플링
    data = read_rdata()

    # Step 8: SE 디어서트 → Sense Amp 비활성화
    GPIO.output(PIN_SE, GPIO.LOW)

    # Step 9: Row Decoder 비활성화
    GPIO.output(PIN_E, GPIO.LOW)

    # Step 10: 잔류 전하 소산 대기
    time.sleep(T_CYCLE)
    return data

# ═══════════════════════════════════════════════
#  Test Patterns
# ═══════════════════════════════════════════════

def fmt_bits(val: int, width: int = 4) -> str:
    """Format integer as binary string with width."""
    return format(val, f'0{width}b')


def fmt_addr(addr: int) -> str:
    """Format 4-bit address as 'row:col' notation."""
    row = (addr >> 1) & 0x7   # A[1:3]
    col = addr & 0x1          # A[0]
    return f"WL[{row}]/Col{col} (A={fmt_bits(addr)})"


def print_header(title: str):
    width = 60
    print()
    print(Color.BOLD + "═" * width + Color.RESET)
    print(Color.BOLD + f"  {title}" + Color.RESET)
    print(Color.BOLD + "═" * width + Color.RESET)


def print_result(addr: int, written: int, read_back: int):
    addr_str    = fmt_addr(addr)
    written_str = fmt_bits(written)
    read_str    = fmt_bits(read_back)

    if written == read_back:
        status = f"{Color.GREEN}✓ PASS{Color.RESET}"
    else:
        status = f"{Color.RED}✗ FAIL{Color.RESET}"

    print(f"  Addr {addr:2d} [{addr_str}] "
          f"W={written_str}({written:#04x})  "
          f"R={read_str}({read_back:#04x})  {status}")

# ═══════════════════════════════════════════════
#  Test Cases
# ═══════════════════════════════════════════════

def test_walking_ones() -> tuple[int, int]:
    """
    Walking-ones pattern: write 0x1, 0x2, 0x4, 0x8 sequentially
    across all 16 addresses. Tests each bit independently.
    """
    print_header("TEST 1: Walking-Ones Pattern")
    patterns = [0x1, 0x2, 0x4, 0x8,
                0x1, 0x2, 0x4, 0x8,
                0x1, 0x2, 0x4, 0x8,
                0x1, 0x2, 0x4, 0x8]
    passed = 0
    failed = 0

    for addr in range(16):
        sram_write(addr, patterns[addr])
    for addr in range(16):
        expected = patterns[addr]
        got = sram_read(addr)
        print_result(addr, expected, got)
        if expected == got:
            passed += 1
        else:
            failed += 1
    return passed, failed


def test_walking_zeros() -> tuple[int, int]:
    """
    Walking-zeros pattern: complement of walking-ones.
    Tests stuck-at-one faults.
    """
    print_header("TEST 2: Walking-Zeros Pattern")
    patterns = [0xE, 0xD, 0xB, 0x7,
                0xE, 0xD, 0xB, 0x7,
                0xE, 0xD, 0xB, 0x7,
                0xE, 0xD, 0xB, 0x7]
    passed = 0
    failed = 0

    for addr in range(16):
        sram_write(addr, patterns[addr])
    for addr in range(16):
        expected = patterns[addr]
        got = sram_read(addr)
        print_result(addr, expected, got)
        if expected == got:
            passed += 1
        else:
            failed += 1
    return passed, failed


def test_checkerboard() -> tuple[int, int]:
    """
    Checkerboard pattern: alternating 0x5 and 0xA.
    Tests neighboring bit interference (coupling faults).
    """
    print_header("TEST 3: Checkerboard Pattern (0x5 / 0xA)")
    passed = 0
    failed = 0

    print(f"  {Color.GRAY}Phase 1 (even=0101, odd=1010){Color.RESET}")
    for addr in range(16):
        data = 0x5 if addr % 2 == 0 else 0xA
        sram_write(addr, data)
    for addr in range(16):
        expected = 0x5 if addr % 2 == 0 else 0xA
        got = sram_read(addr)
        print_result(addr, expected, got)
        if expected == got:
            passed += 1
        else:
            failed += 1

    print(f"  {Color.GRAY}Phase 2 (even=1010, odd=0101){Color.RESET}")
    for addr in range(16):
        data = 0xA if addr % 2 == 0 else 0x5
        sram_write(addr, data)
    for addr in range(16):
        expected = 0xA if addr % 2 == 0 else 0x5
        got = sram_read(addr)
        print_result(addr, expected, got)
        if expected == got:
            passed += 1
        else:
            failed += 1
    return passed, failed


def test_all_zeros_ones() -> tuple[int, int]:
    """All-zeros then all-ones: tests global stuck-at faults."""
    print_header("TEST 4: All-Zeros then All-Ones")
    passed = 0
    failed = 0

    print(f"  {Color.GRAY}Writing 0x0 to all addresses...{Color.RESET}")
    for addr in range(16):
        sram_write(addr, 0x0)
    for addr in range(16):
        got = sram_read(addr)
        print_result(addr, 0x0, got)
        if got == 0x0:
            passed += 1
        else:
            failed += 1

    print(f"  {Color.GRAY}Writing 0xF to all addresses...{Color.RESET}")
    for addr in range(16):
        sram_write(addr, 0xF)
    for addr in range(16):
        got = sram_read(addr)
        print_result(addr, 0xF, got)
        if got == 0xF:
            passed += 1
        else:
            failed += 1
    return passed, failed


def test_address_as_data() -> tuple[int, int]:
    """
    Write address value as data: addr 0->0x0, addr 5->0x5, etc.
    Tests address decoder correctness (address uniqueness).
    """
    print_header("TEST 5: Address-as-Data (Decoder Integrity)")
    passed = 0
    failed = 0

    print(f"  {Color.GRAY}Writing addr value to each address...{Color.RESET}")
    for addr in range(16):
        sram_write(addr, addr & 0xF)

    print(f"  {Color.GRAY}Reading back...{Color.RESET}")
    for addr in range(16):
        expected = addr & 0xF
        got = sram_read(addr)
        print_result(addr, expected, got)
        if expected == got:
            passed += 1
        else:
            failed += 1
    return passed, failed


def test_march_c() -> tuple[int, int]:
    """
    Simplified March-C algorithm:
      M0: (up)  Write 0 to all
      M1: (up)  Read 0, Write 1
      M2: (up)  Read 1, Write 0
      M3: (dn)  Read 0, Write 1
      M4: (dn)  Read 1, Write 0
      M5: (up)  Read 0
    """
    print_header("TEST 6: March-C Algorithm (Fault Coverage)")
    passed = 0
    failed = 0

    def check(addr, expected, got, phase):
        nonlocal passed, failed
        ok = (expected == got)
        status = f"{Color.GREEN}✓{Color.RESET}" if ok else f"{Color.RED}✗{Color.RESET}"
        print(f"  {phase} addr={addr:2d} exp={fmt_bits(expected)} got={fmt_bits(got)} {status}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"  {Color.YELLOW}M0↑ Write 0x0{Color.RESET}")
    for addr in range(16):
        sram_write(addr, 0x0)

    print(f"  {Color.YELLOW}M1↑ Read 0x0, Write 0xF{Color.RESET}")
    for addr in range(16):
        got = sram_read(addr)
        check(addr, 0x0, got, "M1↑")
        sram_write(addr, 0xF)

    print(f"  {Color.YELLOW}M2↑ Read 0xF, Write 0x0{Color.RESET}")
    for addr in range(16):
        got = sram_read(addr)
        check(addr, 0xF, got, "M2↑")
        sram_write(addr, 0x0)

    print(f"  {Color.YELLOW}M3↓ Read 0x0, Write 0xF{Color.RESET}")
    for addr in range(15, -1, -1):
        got = sram_read(addr)
        check(addr, 0x0, got, "M3↓")
        sram_write(addr, 0xF)

    print(f"  {Color.YELLOW}M4↓ Read 0xF, Write 0x0{Color.RESET}")
    for addr in range(15, -1, -1):
        got = sram_read(addr)
        check(addr, 0xF, got, "M4↓")
        sram_write(addr, 0x0)

    print(f"  {Color.YELLOW}M5↑ Read 0x0{Color.RESET}")
    for addr in range(16):
        got = sram_read(addr)
        check(addr, 0x0, got, "M5↑")

    return passed, failed


def test_retention(hold_time_sec: float = 2.0) -> tuple[int, int]:
    """
    Data retention test: write all addresses, wait, then read back.
    """
    print_header(f"TEST 7: Data Retention (hold {hold_time_sec}s)")
    passed = 0
    failed = 0
    pattern = [addr & 0xF for addr in range(16)]

    print(f"  {Color.GRAY}Writing address-as-data pattern...{Color.RESET}")
    for addr in range(16):
        sram_write(addr, pattern[addr])

    print(f"  {Color.YELLOW}Holding for {hold_time_sec}s...{Color.RESET}")
    time.sleep(hold_time_sec)

    print(f"  {Color.GRAY}Reading back after hold...{Color.RESET}")
    for addr in range(16):
        expected = pattern[addr]
        got = sram_read(addr)
        print_result(addr, expected, got)
        if expected == got:
            passed += 1
        else:
            failed += 1
    return passed, failed

# ═══════════════════════════════════════════════
#  Summary Report
# ═══════════════════════════════════════════════

def print_summary(results: dict):
    print()
    print(Color.BOLD + "═" * 60 + Color.RESET)
    print(Color.BOLD + "  TEST SUMMARY" + Color.RESET)
    print(Color.BOLD + "═" * 60 + Color.RESET)

    total_pass = 0
    total_fail = 0

    for test_name, (p, f) in results.items():
        total = p + f
        bar_p = int((p / total) * 20) if total > 0 else 0
        bar_f = 20 - bar_p
        bar = (Color.GREEN + "█" * bar_p + Color.RED + "█" * bar_f + Color.RESET)
        status = f"{Color.GREEN}ALL PASS{Color.RESET}" if f == 0 else f"{Color.RED}{f} FAIL{Color.RESET}"
        print(f"  {test_name:<28} {bar}  {p:3d}/{total:3d}  {status}")
        total_pass += p
        total_fail += f

    grand_total = total_pass + total_fail
    print(Color.BOLD + "─" * 60 + Color.RESET)
    if total_fail == 0:
        verdict = f"{Color.GREEN}{Color.BOLD}ALL TESTS PASSED ({total_pass}/{grand_total}){Color.RESET}"
    else:
        verdict = (f"{Color.RED}{Color.BOLD}FAILED: {total_fail}/{grand_total} checks failed"
                   f"{Color.RESET}")
    print(f"  {verdict}")
    print(Color.BOLD + "═" * 60 + Color.RESET)
    print()

# ═══════════════════════════════════════════════
#  Interactive Single R/W Mode
# ═══════════════════════════════════════════════

def interactive_mode():
    """
    Manual single-address read/write for debugging.
    Usage: python3 sram_test.py interactive
    """
    print_header("Interactive Mode (type 'q' to quit)")
    print("  Commands:")
    print("    w <addr> <data>   -- write hex data to hex address")
    print("    r <addr>          -- read from hex address")
    print("    dump              -- read all 16 addresses")
    print("    q                 -- quit")
    print()

    while True:
        try:
            cmd = input(f"  {Color.CYAN}sram> {Color.RESET}").strip().split()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue

        if cmd[0] == 'q':
            break

        elif cmd[0] == 'w' and len(cmd) == 3:
            try:
                addr = int(cmd[1], 16)
                data = int(cmd[2], 16)
                if not (0 <= addr <= 15):
                    print(f"  {Color.RED}Address must be 0x0~0xF{Color.RESET}")
                    continue
                if not (0 <= data <= 15):
                    print(f"  {Color.RED}Data must be 0x0~0xF{Color.RESET}")
                    continue
                sram_write(addr, data)
                print(f"  {Color.GREEN}Written: addr={addr:#04x} data={fmt_bits(data)} ({data:#04x}){Color.RESET}")
            except ValueError:
                print(f"  {Color.RED}Invalid format. Use hex: w 0a 05{Color.RESET}")

        elif cmd[0] == 'r' and len(cmd) == 2:
            try:
                addr = int(cmd[1], 16)
                if not (0 <= addr <= 15):
                    print(f"  {Color.RED}Address must be 0x0~0xF{Color.RESET}")
                    continue
                got = sram_read(addr)
                print(f"  {Color.GREEN}Read:    addr={addr:#04x} data={fmt_bits(got)} ({got:#04x}){Color.RESET}")
            except ValueError:
                print(f"  {Color.RED}Invalid format. Use hex: r 0a{Color.RESET}")

        elif cmd[0] == 'dump':
            print(f"  {Color.YELLOW}  Addr  Row/Col      Data{Color.RESET}")
            for addr in range(16):
                got = sram_read(addr)
                row = (addr >> 1) & 0x7
                col = addr & 0x1
                print(f"  [{addr:2d}] WL[{row}]/C{col}   {fmt_bits(got)} ({got:#04x})")

        else:
            print(f"  {Color.RED}Unknown command{Color.RESET}")

# ═══════════════════════════════════════════════
#  Main Entry Point
# ═══════════════════════════════════════════════

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    print()
    print(Color.BOLD + Color.CYAN)
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   8x8 64-bit SRAM Tester                ║")
    print("  ║   NSPL 0.5um CMOS 2P3M 5V PDK           ║")
    print("  ║   Raspberry Pi + TXS0108E Level Shifter ║")
    print("  ║   Timing: Cadence Virtuoso TB 기반      ║")
    print("  ╚══════════════════════════════════════════╝")
    print(Color.RESET)

    try:
        gpio_init()

        if mode == "interactive":
            interactive_mode()
            return

        results = {}

        if mode in ("full", "walking1"):
            p, f = test_walking_ones()
            results["1. Walking-Ones"] = (p, f)

        if mode in ("full", "walking0"):
            p, f = test_walking_zeros()
            results["2. Walking-Zeros"] = (p, f)

        if mode in ("full", "checker"):
            p, f = test_checkerboard()
            results["3. Checkerboard"] = (p, f)

        if mode in ("full", "allzeroone"):
            p, f = test_all_zeros_ones()
            results["4. All-Zeros/Ones"] = (p, f)

        if mode in ("full", "addr"):
            p, f = test_address_as_data()
            results["5. Addr-as-Data"] = (p, f)

        if mode in ("full", "marchc"):
            p, f = test_march_c()
            results["6. March-C"] = (p, f)

        if mode in ("full", "retention"):
            p, f = test_retention(hold_time_sec=2.0)
            results["7. Retention (2s)"] = (p, f)

        if results:
            print_summary(results)

    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}[!] Interrupted by user{Color.RESET}")

    finally:
        gpio_cleanup()


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════
#  Usage Examples
# ═══════════════════════════════════════════════
#
#  Run all tests:
#    sudo python3 sram_test.py full
#
#  Run specific test:
#    sudo python3 sram_test.py walking1
#    sudo python3 sram_test.py walking0
#    sudo python3 sram_test.py checker
#    sudo python3 sram_test.py allzeroone
#    sudo python3 sram_test.py addr
#    sudo python3 sram_test.py marchc
#    sudo python3 sram_test.py retention
#
#  Interactive single R/W:
#    sudo python3 sram_test.py interactive
#
#  Install dependency:
#    pip install RPi.GPIO
