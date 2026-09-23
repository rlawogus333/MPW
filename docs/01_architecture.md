# 01. 아키텍처 · 주소 맵 · 신호 정의

## 1. 전체 구조

64-bit SRAM을 8행(word line) × 8열(bit line) 배열로 구성하고, 4-bit 단위로 입출력합니다.
어레이 자체는 4-bit word 16개 분량이지만, **제작된 칩은 주소 핀이 A[2:0] 3개**이고
A0가 행 디코더와 열 디코더에 함께 연결되어 있어 외부에서 선택 가능한 워드는 **8개(32 bit)** 입니다 (§2).

```
                     ColDecoder (Transmission Gate × 16)  ← A0 (행 디코더와 공유)
                  ┌───┬───┬───┬───┰───┬───┬───┬───┐
                  BL0 BL1 BL2 BL3 ┃BL4 BL5 BL6 BL7
                   │   │   │   │  ┃ │   │   │   │
   Row      ┌──────┼───┼───┼───┼──╂─┼───┼───┼───┼──┐
 Decoder    │                     ┃                │
  (3-to-8)  │  WL0  C   C   C   C ┃ C   C   C   C  │
     ▲      │  WL1  C   C   C   C ┃ C   C   C   C  │
     │      │  WL2  C   C   C   C ┃ C   C   C   C  │   C = 6T SRAM Cell
  A2 A1 A0  │  WL3  C   C   C   C ┃ C   C   C   C  │   (8 × 8 = 64 bit)
     +      │  WL4  C   C   C   C ┃ C   C   C   C  │
     E      │  WL5  C   C   C   C ┃ C   C   C   C  │
            │  WL6  C   C   C   C ┃ C   C   C   C  │
            │  WL7  C   C   C   C ┃ C   C   C   C  │
            └─────────────────────╂────────────────┘
                  ┌───────────────┸────────────────┐
        PRE  →    │          Precharger ×8         │
                  └────────────────────────────────┘
                  ┌────────────────────────────────┐
        WE   →    │        Write Driver ×4         │  ← WDATA[3:0]
        SE   →    │    Sense Amp (current mirror) ×4│ → RDATA[3:0]
                  └────────────────────────────────┘
```

핵심은 **Col k와 Col (k+4)가 공통 비트라인 CBL[k]를 공유**한다는 점입니다.
TG 디코더가 A0에 따라 둘 중 하나만 CBL에 붙이므로, Sense Amp와 Write Driver는
각각 4개만 있으면 됩니다. (면적 절감 — 8쌍이 아니라 4쌍)

---

## 2. 주소 맵

### 2.1 제작된 칩 (A[2:0], A0 공유)

측정 환경상 열 선택 신호를 별도 핀으로 인출하지 못해 주소 핀은 `A2 A1 A0` 3개이며, `A0`는 Row Decoder의 LSB 입력과
Column Decoder의 선택 입력에 **같은 넷으로** 연결되어 있습니다 (최종 GDS 연결 추적으로 확인 — [03 §6.4](03_verification.md#64-연결-추적)).

```
WL  = A2 A1 A0   (0 … 7, A2 = MSB 가정)
Col = A0          (0 → Col 0–3, 1 → Col 4–7)
→ 짝수 WL은 항상 Col 0–3, 홀수 WL은 항상 Col 4–7 과 짝지어짐
```

| A2 A1 A0 | 선택 WL | Column 그룹 | 실측 (2026-09) |
|----------|---------|-------------|----------------|
| 000 | WL[0] | Col 0–3 | ✅ bit 0–3 |
| 001 | WL[1] | Col 4–7 | ✅ bit 3 |
| 010 | WL[2] | Col 0–3 | ✅ bit 3 |
| 011 | WL[3] | Col 4–7 | — |
| 100 | WL[4] | Col 0–3 | ✅ bit 3 |
| 101 | WL[5] | Col 4–7 | — |
| 110 | WL[6] | Col 0–3 | — |
| 111 | WL[7] | Col 4–7 | — |

나머지 32개 셀(짝수 WL의 Col 4–7, 홀수 WL의 Col 0–3)은 외부에서 선택할 수 없습니다.
실측 결과는 [06_silicon_measurement.md](06_silicon_measurement.md)에 있습니다.

### 2.2 설계 원안 (4-bit 주소, 참고)

초기 설계 문서와 `test/sram_rw_test.py`(전체 테스트 스위트)는 `A[3:1]` → 행, `A[0]` → 열로
16개 워드를 모두 쓰는 4-bit 주소 구조를 가정했습니다. 제작된 칩에 쓰려면 주소 매핑을 §2.1에 맞게 고쳐야 합니다.

```
비트 위치:  주소 a, 데이터 bit k  →  행(row) = a >> 1,  열(col) = k + 4 × (a & 1)
```

| 주소 | A[3] A[2] A[1] | A[0] | 선택 WL | Column 그룹 | 저장 비트 위치 |
|------|----------------|------|---------|-------------|----------------|
| 0x0 | 0 0 0 | 0 | WL[0] | Col 0–3 | bit 0 – 3 |
| 0x1 | 0 0 0 | 1 | WL[0] | Col 4–7 | bit 4 – 7 |
| … | | | | | |
| 0xF | 1 1 1 | 1 | WL[7] | Col 4–7 | bit 60 – 63 |

---

## 3. 신호 정의

### 3.1 입력

| 신호 | 비트 | 극성 | 설명 |
|------|------|------|------|
| `A[2:0]` | 3 | — | Row 주소. 3-to-8 Row Decoder 입력 (000 = WL0 … 111 = WL7) |
| `A[0]` | (공유) | — | Column 선택도 겸함. 0 → Col 0–3, 1 → Col 4–7 |
| `E` | 1 | Active-HIGH | Row Decoder Enable. NAND4의 4번째 입력 → **WL = E · decode(A2A1A0)** |
| `PRE` | 1 | **Active-LOW** | Precharge. LOW일 때 BL·BLB를 VDD로 충전하고 equalize |
| `WE` | 1 | Active-HIGH | Write Enable. Write Driver를 활성화 |
| `SE` | 1 | Active-HIGH | Sense Enable. Sense Amp의 current-mirror tail을 열어 증폭 시작 |
| `WDATA[3:0]` | 4 | — | 쓰기 데이터 |
| `VDD / VSS` | — | — | 시뮬레이션 3.3 V · 실측 5 V (USB) / 0 V |

### 3.2 출력

| 신호 | 비트 | 설명 |
|------|------|------|
| `RDATA[3:0]` | 4 | 읽기 데이터. `RDATA = (BL > BLB)` — **비반전, 래치 없음** |

### 3.3 극성에서 자주 헷갈리는 지점

- **`PRE`는 Active-LOW입니다.** `PRE = 0`이 프리차지 구간입니다. 다른 제어선은 모두 Active-HIGH라
  여기만 반대이므로, 코드/배선 점검 시 첫 번째로 확인할 부분입니다.
- **`E`는 chip enable이 아니라 사실상 워드라인 펄스입니다.** `E`를 올리는 순간 WL이 어서트되므로,
  `E = 1` 상태에서 주소를 바꾸면 다른 WL이 순간적으로 열려 데이터가 깨집니다.
- **`SE` 구간 밖의 `RDATA`는 무효입니다.** Sense Amp에 래치가 없습니다. 시뮬레이션에서는 `SE = 0`이면 곧바로
  `RDATA = 0`이 되었고, 실리콘에서는 SE 하강 후 다음 PRE까지 약 1 ms 값이 남아 있었습니다.
  어느 쪽이든 샘플링은 반드시 `SE = 1` 구간 안에서 해야 합니다.
- **Write Driver는 비반전입니다.** `WDATA = 1` → `BL = HIGH`, `BLB = LOW`. Spectre testbench에서
  `WDATA = 5` → `RDATA = 5`로 일치함을 확인했습니다.

---

## 4. Read / Write 시퀀스

### 4.1 Write

```
A 설정 → PRE 펄스(LOW→HIGH) → WDATA 설정 → WE = 1 → E = 1 → E = 0 → WE = 0
```

`E`를 먼저 내리고 그다음 `WE`를 내리는 순서가 중요합니다. Write Driver가 비트라인을 잡고 있는
동안 워드라인을 닫아야, WL이 닫히는 과도 구간에 셀이 중간 상태로 남지 않습니다.

1. `PRE = 0` → PMOS 3개 도통, BL·BLB → VDD 및 equalize (직전 사이클의 잔류 ΔV 제거)
2. `PRE = 1` → 프리차지 종료, BL/BLB는 VDD에서 floating
3. `A[2:0]` 확정 후 안정화 대기
4. `WDATA[3:0]` 인가 → Write Driver 입력 확정
5. `WE = 1` → Write Driver가 BL/BLB를 각각 데이터/반전 데이터로 구동
6. `E = 1` → WL 어서트, access NMOS를 통해 6T latch가 강제 반전
7. `E = 0` → WL 디어서트 (셀 데이터 확정)
8. `WE = 0` → Write Driver 해제

### 4.2 Read

```
A 설정 → PRE 펄스 → E = 1 → SE = 1 → RDATA N회 샘플 → SE = 0 → E = 0
```

1. `PRE = 0 → 1` → BL = BLB = VDD로 초기화
2. `A[2:0]` 확정
3. `E = 1` → WL 어서트. 셀 저장값에 따라 BL 또는 BLB가 미세 방전 (ΔV ~ 수십 mV)
4. 차분 형성 대기 (`t_dev`)
5. `SE = 1` → current-mirror Sense Amp가 ΔV를 풀스윙으로 증폭
6. `RDATA[3:0]` 샘플링 (테스터는 기본 3회 샘플하여 불안정 비트를 따로 표시)
7. `SE = 0` → `E = 0`

인터랙티브 타이밍 다이어그램: [timing_diagram.html](timing_diagram.html)

---

## 5. 관련 문서

- 블록별 회로 설명 → [02_design_blocks.md](02_design_blocks.md)
- 시뮬레이션 · 물리 검증 → [03_verification.md](03_verification.md)
- 라즈베리파이 배선 · 핀맵 → [04_raspberry_pi_test.md](04_raspberry_pi_test.md)
