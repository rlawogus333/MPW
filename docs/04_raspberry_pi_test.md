# 04. 라즈베리파이 실측 환경 — 배선 · 핀맵 · 타이밍

## 1. 왜 3.3 V 직결인가

칩의 `VDD`를 **3.3 V**로 잡아 라즈베리파이 GPIO 레벨과 맞췄습니다.
그 결과 **레벨 시프터 없이 GPIO를 칩 핀에 그대로 연결**합니다.

| | 3.3 V 직결 (현행) | 5 V + TXS0108E (초기안) |
|---|---|---|
| 부품 | 없음 | TXS0108E × 2, 바이패스 커패시터, 풀다운 저항 |
| 배선 | RPi ↔ 칩 16가닥 | RPi ↔ IC ↔ 칩, 중간 경유 32가닥 |
| 리스크 | — | 자동 방향 감지 오동작, High-Z 구간 불확실, 기생 용량으로 엣지 둔화 |
| 디버깅 | 신호 이상 = 칩 또는 배선 | 신호 이상 = 칩 / 배선 / 레벨 시프터 중 하나 |

실측에서 가장 비싼 비용은 "어디가 문제인지 모르는 상태"입니다.
중간 소자를 없애 의심 대상을 줄인 것이 3.3 V를 택한 실질적인 이유입니다.

초기 5 V 버전 코드는 [`test/legacy/sram_test_5v_txs0108e.py`](../test/legacy/sram_test_5v_txs0108e.py)에
보존해 두었습니다. TXS0108E 상세 배선표가 필요하면 그쪽을 참고하세요.

---

## 2. GPIO 핀맵 (BCM 번호)

`sram_rw_test.py`의 `PINS` 딕셔너리와 동일합니다.

| 신호 | GPIO (BCM) | 방향 | 비고 |
|------|-----------|------|------|
| `PRE` | 17 | OUT | Active-LOW |
| `E` | 27 | OUT | Active-HIGH (워드라인 펄스) |
| `WE` | 8 | OUT | Active-HIGH · **SPI0 CE0** |
| `SE` | 7 | OUT | Active-HIGH · **SPI0 CE1** |
| `A[0]` | 18 | OUT | Column 그룹 선택 |
| `A[1]` | 23 | OUT | Row addr LSB |
| `A[2]` | 24 | OUT | Row addr |
| `A[3]` | 25 | OUT | Row addr MSB |
| `WDATA[0]` | 12 | OUT | |
| `WDATA[1]` | 16 | OUT | |
| `WDATA[2]` | 20 | OUT | |
| `WDATA[3]` | 21 | OUT | |
| `RDATA[0]` | 26 | IN | Sense Amp 출력 |
| `RDATA[1]` | 19 | IN | |
| `RDATA[2]` | 13 | IN | |
| `RDATA[3]` | 6 | IN | |

> ⚠️ **GPIO 7, 8은 SPI0의 CS 핀입니다.** SPI가 켜져 있으면 커널이 이 핀을 점유해
> `gpio_claim_output`이 실패합니다. `sudo raspi-config` → Interface Options → SPI → **Disable**.

### 전원 배선

| 칩 핀 | 연결 |
|-------|------|
| `VDD` | 3.3 V (라즈베리파이 3.3 V 레일 또는 별도 3.3 V LDO) |
| `VSS` | GND — **라즈베리파이 GND와 반드시 공통** |

- `VDD`–`VSS` 사이에 칩 가까이 **100 nF 바이패스 커패시터**를 둡니다.
- 별도 전원을 쓰더라도 GND는 반드시 묶어야 합니다. GND가 분리되면 레벨 기준이 달라져
  모든 신호가 무의미해집니다. 실측에서 "64비트 전부 실패"의 가장 흔한 원인이 이것입니다.

---

## 3. 전원 인가 순서 — 칩 보호

```
전원 ON :  칩 VDD 인가  →  GPIO 초기화 (모두 LOW)  →  테스트 시작
전원 OFF:  모든 GPIO LOW  →  GPIO 해제  →  칩 VDD 차단
```

**칩 전원이 없는 상태에서 GPIO가 HIGH를 내면 안 됩니다.**
입력 패드의 ESD 보호 다이오드를 통해 전류가 칩 내부 VDD 레일로 역류하여
칩을 부분적으로 기동시키거나 손상시킬 수 있습니다.

`sram_rw_test.py`는 이를 코드로 보장합니다.

- 시작 시 전원 확인 프롬프트를 띄웁니다 (`-y` 옵션으로 생략 가능)
- 정상 종료·예외·`Ctrl+C` 어느 경로로든 `power_down_state()`를 거쳐
  **모든 출력을 LOW로 내린 뒤** GPIO를 해제합니다

---

## 4. 타이밍 파라미터

`Timing` 데이터클래스의 기본값입니다. 단위는 **μs**.

| 파라미터 | 기본값 | 의미 |
|----------|--------|------|
| `t_addr` | 200 | 주소 변경 후 안정화 (`E = 0` 상태에서) |
| `t_pre` | 1000 | `PRE = 0` 폭 (프리차지 구간) |
| `t_pre_off` | 200 | `PRE = 1` 이후 `E`/`WE`를 올리기 전 대기 |
| `t_wd` | 500 | Write: `WE = 1` → `E = 1` (드라이버가 BL/BLB를 구동할 시간) |
| `t_wl_w` | 1000 | Write: `E = 1` 유지 (셀 latch 반전) |
| `t_hold` | 200 | Write: `E = 0` → `WE = 0` |
| `t_dev` | 1000 | Read: `E = 1` → `SE = 1` (BL/BLB 차분 형성) |
| `t_sa` | 500 | Read: `SE = 1` → 첫 샘플 |
| `t_smp` | 100 | 샘플 간격 |

**왜 시뮬레이션보다 1000배 이상 느린가**

Spectre에서는 500 ns 펄스로 동작합니다. 반면 Python에서 GPIO를 한 번 토글하는 데만
수~수십 μs가 걸리고, OS 스케줄링으로 그 시간이 흔들립니다.
SRAM은 정적 메모리라 **느린 것 자체는 문제가 되지 않으므로**, 넉넉한 값에서 출발해
`shmoo` 테스트로 배율을 낮춰가며 실제 마진이 어디서 무너지는지 측정합니다.

```bash
python3 test/sram_rw_test.py shmoo          # 타이밍 배율 스윕
python3 test/sram_rw_test.py all --scale 0.2  # 전체를 1/5 타이밍으로
```

2 ms 이상은 `time.sleep()`, 그 미만은 `perf_counter_ns()` 기반 busy-wait을 씁니다
(`time.sleep`은 짧은 대기에서 정확도가 크게 떨어지기 때문).

---

## 5. 안전 규칙 (interlock)

테스터는 다음 네 가지를 코드 레벨에서 차단합니다. 위반 시 `InterlockError`를 던지고 중단합니다.

| # | 규칙 | 막는 사고 |
|---|------|-----------|
| 1 | `PRE = 0` 동안 `E = 0`, `WE = 0` | Precharger PMOS와 셀/Write Driver가 동시에 비트라인을 반대로 구동 → 관통 전류 |
| 2 | `E = 1` 동안 주소 변경 금지 | 전이 구간에 다른 WL이 열려 해당 행 오기록 |
| 3 | `WE = 1`과 `SE = 1` 동시 금지 | Write Driver가 구동 중인 비트라인을 Sense Amp가 읽어 무의미한 값 + 전류 경합 |
| 4 | Read/Write 모두 WL 열기 전 매번 precharge | 같은 행의 비선택 4개 열이 뜬 비트라인으로 half-select 교란 |

4번은 이 칩 구조에서 특히 중요합니다. WL이 열리면 **그 행의 8개 셀이 전부** access NMOS를 통해
비트라인에 연결되는데, TG 디코더가 고르지 않은 4개 열의 비트라인은 CBL에서 끊겨 떠 있습니다.
그 상태로 반복 접근하면 half-select된 셀이 서서히 교란될 수 있어, 매 사이클 프리차지로
모든 비트라인을 VDD에 붙여 둡니다.

---

## 6. 수동 디버깅 모드

배선 확인이나 오실로스코프 관찰 시 사용합니다.

```bash
python3 test/sram_rw_test.py shell
```

```
w <addr> <data>          쓰기 (hex)
r <addr>                 읽기
fill <data>              전체 주소에 쓰기
dump                     8×8 비트맵으로 전체 읽기
pin <PRE|E|WE|SE> <0|1>  제어선 직접 토글 (interlock 적용)
addr <a>                 주소만 설정
wd <data>                WDATA만 설정
t                        현재 타이밍 보기
set <필드> <µs>          타이밍 변경
q                        종료
```

`pin` 명령으로 제어선을 고정해 두고 스코프로 칩 핀의 실제 파형을 확인하면,
"GPIO는 토글되는데 칩 핀은 안 움직인다"(배선/납땜) 와
"칩 핀은 움직이는데 결과가 이상하다"(칩/로직) 를 구분할 수 있습니다.
