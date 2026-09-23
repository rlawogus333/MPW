# 05. 테스트 실행 절차 · FAIL 진단

> ⚠️ **이 문서는 `test/sram_rw_test.py` 전체 스위트(4-bit 주소 원안) 기준입니다.**
> 제작된 칩은 주소 핀이 `A[2:0]`이고 A0가 행·열 디코더에 공유되어 선택 가능한 워드가 8개입니다
> ([01 §2.1](01_architecture.md#21-제작된-칩-a20-a0-공유)). 불량 맵에서 짝수 WL의 Col 4–7, 홀수 WL의 Col 0–3은
> 원래 접근할 수 없는 셀이므로 FAIL로 판정하지 않도록 스크립트를 먼저 고쳐야 합니다.
> 2026-09 실측은 [`test/sram_ctrl_timing.py`](../test/sram_ctrl_timing.py) + 오실로스코프로 진행했고,
> 결과는 [06_silicon_measurement.md](06_silicon_measurement.md)에 있습니다.

## 1. 설치

라즈베리파이 OS Bookworm 기준:

```bash
sudo apt install python3-lgpio
```

`lgpio`가 없으면 `RPi.GPIO`로 자동 폴백하지만, **라즈베리파이 5에서는 `RPi.GPIO`가 동작하지 않습니다**
(RP1 칩으로 GPIO 컨트롤러가 바뀌었기 때문). Pi 5라면 `lgpio`가 필수입니다.

SPI0를 끕니다 (GPIO 7, 8을 쓰기 위해):

```bash
sudo raspi-config   # Interface Options → SPI → Disable → 재부팅
```

---

## 2. 하드웨어 없이 먼저 검증

칩이 오기 전에, 그리고 실측에서 이상한 결과가 나왔을 때 "코드가 맞나"를 확인하는 용도입니다.
`--sim`은 회로 해석을 그대로 반영한 칩 모델을 메모리상에서 돌립니다.

```bash
python3 test/sram_rw_test.py --sim              # 전체 스위트, 전부 PASS 나와야 정상
```

**결함 주입** — 특정 고장이 어떤 패턴으로 보이는지 미리 익혀 두면 실측에서 판독이 빨라집니다.

```bash
python3 test/sram_rw_test.py --sim --fault s0:3,5      # 셀 (행3, 열5) stuck-at-0
python3 test/sram_rw_test.py --sim --fault s1:0,0      # 셀 stuck-at-1
python3 test/sram_rw_test.py --sim --fault row:2       # WL2가 안 올라감
python3 test/sram_rw_test.py --sim --fault pin:A2=0    # A2 핀 고정
python3 test/sram_rw_test.py --sim --fault s0:3,5 --fault pin:A2=0   # 복합
```

sim 모드는 interlock 위반 횟수와 "precharge 없이 WL을 연 횟수"도 함께 집계하므로,
테스트 코드를 수정했을 때 안전 규칙이 깨지지 않았는지 확인할 수 있습니다.

---

## 3. 실측 순서

### 3-1. 칩을 받으면 제일 먼저

```bash
python3 test/sram_rw_test.py conn smoke
```

| 테스트 | 내용 |
|--------|------|
| `conn` | RDATA 4가닥에 라즈베리파이 내부 풀업을 걸고, `SE = 0` 상태에서 칩이 그 라인을 0으로 잡는지 확인. **배선/전원이 살아 있는지를 보는 가장 싼 테스트**입니다. 풀업에 끌려 1이 읽히면 그 핀은 단선이거나 칩 전원이 안 들어간 것입니다. |
| `smoke` | 전 주소에 `0x0`과 `0xF`를 쓰고 되읽는 기본 R/W |

`smoke`에서 절반도 통과하지 못하면 스크립트가 이후 테스트를 건너뜁니다.
기본 R/W가 안 되는 상태에서 March-C를 돌려봐야 정보가 늘지 않기 때문입니다.

### 3-2. 전체 스위트

```bash
python3 test/sram_rw_test.py all
# = conn → smoke → addr → march → disturb → retention
```

| 테스트 | 내용 | 검출 대상 |
|--------|------|-----------|
| `conn` | RDATA 연결 확인 | 단선, 전원 미인가, 핀맵 오류 |
| `smoke` | 기본 R/W (`0x0`, `0xF`) | 전역 stuck-at |
| `addr` | 주소값 = 데이터값, 그리고 그 보수 | Row/Column 디코더 오동작, 주소 aliasing |
| `march` | March C− ×3 배경 패턴 | 전이 결함(TF), 커플링 결함(CF) — 메모리 테스트 업계 표준 |
| `disturb` | 반복 읽기 · half-select 교란 | Read disturb, 인접 셀 간섭 |
| `retention` | 기록 → 대기 → 비교 | 누설에 의한 데이터 손실 |
| `shmoo` | 타이밍 배율 스윕 (`all`에는 미포함) | 타이밍 마진 |

주요 옵션:

```bash
--scale 0.2      # 모든 타이밍 ×0.2 (빠르게)
--samples 5      # read 1회당 RDATA 샘플 수 (기본 3)
--reads 50       # disturb: 주소당 반복 읽기 횟수
--hold 1 10 60   # retention 대기 시간(초) 목록
--csv out.csv    # 결과 CSV 경로 (실측 시 기본 자동 생성)
-y               # 전원 확인 프롬프트 생략
```

실측 모드에서는 `sram_log_YYYYMMDD_HHMMSS.csv`가 자동 생성되어
매 접근의 주소·기대값·실제값·불안정 마스크가 기록됩니다.

---

## 4. 결과 읽기 — 8×8 불량 맵

테스트가 끝나면 FAIL 비트를 **물리 좌표**로 되돌려 그립니다.

```
  불량 셀 맵   ( . PASS | 0: 1을 써도 0 | 1: 0을 써도 1 | X: 둘 다 | ~: 샘플 불안정 )
                      Col 0 1 2 3   4 5 6 7
                         (A0=0)    (A0=1)
  WL0 (A3A2A1=000)      . . . .   . . . .
  WL1 (A3A2A1=001)      . . . .   . . . .
  WL2 (A3A2A1=010)      . . . .   . . . .
  ...
```

주소·비트 번호가 아니라 행/열로 그리는 이유는, **고장 원인이 물리 구조를 따라 모이기 때문**입니다.
"주소 0x6, bit 1 실패"는 정보가 거의 없지만 "Col 3이 세로로 전부 실패"는 곧바로
BL3 배선 / Precharger3 / TG3를 가리킵니다.

---

## 5. 자동 진단 규칙

`diagnose()`가 불량 맵의 모양을 보고 원인 블록을 좁혀 힌트를 출력합니다.
아래는 그 규칙이자, 수동으로 판독할 때의 체크리스트이기도 합니다.

| 불량 패턴 | 추정 원인 |
|-----------|-----------|
| **64비트 전부 실패** | VDD/VSS, 공통 GND, PRE/E/WE/SE 배선, 핀맵. `conn` 먼저 돌리고 스코프로 `E`·`PRE` 파형 확인 |
| **A0 = 0 쪽 4열 전체 실패, 반대쪽 정상** (또는 그 반대) | `A0` 핀, ColDecoder 인버터(`A_b`), TG |
| **Col k와 Col k+4가 동시에 실패** | 공유 경로 — `RDATA[k]` / `WDATA[k]` 핀, SenseAmp k, WriteDriver k |
| ↳ 그 중 **항상 0** | `RDATA[k]` 단선 또는 SenseAmp k 출력 고착 |
| ↳ 그 중 **항상 1** | `WDATA[k]` 고정 또는 WriteDriver k 고착 |
| **Col c 하나만 세로로 전체 실패** | `BL[c]` / `BLB[c]` 배선, Precharger c, TG c |
| **실패 행들이 "A[n] = 0인 행 전부"와 일치** | `A[n]` 핀 또는 패드 |
| **WL r 하나만 가로로 전체 실패** | RowDecoder 출력 r (NAND4 / INV), WL r 배선 |
| **개별 셀 산발적 실패** | 셀 결함 또는 마진 부족 → `retention`, `disturb`, `shmoo`로 조건 좁히기 |
| **`~` (샘플 불안정) 비트 존재** | `t_dev`·`t_sa` 증가, RDATA 배선 길이 / GND 리턴 / 디커플링 확인 |

불안정(`~`)은 stuck-at과 성격이 다릅니다. 같은 read 안에서 3회 샘플이 서로 다르게 나온 경우로,
대개 **고장이 아니라 타이밍이나 신호 무결성 문제**입니다.
`--scale`을 키워 여유를 주었을 때 사라진다면 마진 문제로 확정할 수 있습니다.

---

## 6. 실측 후 정리할 항목

- [x] 파형 캡처 — 주소 4개 write → read ([06](06_silicon_measurement.md))
- [ ] 동작 전압 범위 — VDD를 스윕하며 전체 스위트 통과 하한/상한
- [ ] 최소 동작 타이밍 — `shmoo`로 찾은 배율 한계
- [ ] Read access time — 오실로스코프로 `SE` 상승 → `RDATA` 확정까지
- [ ] 불량 셀 맵과 수율
- [ ] Simulation vs Silicon 비교표
- [ ] 칩 현미경 사진
