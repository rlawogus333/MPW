# 03. 검증 — Spectre 시뮬레이션 · DRC / LVS · GDS 대조

## 1. 검증 단계 요약

| 단계 | 대상 | 방법 | 결과 |
|------|------|------|------|
| 1 | 6T Cell | DC sweep → Butterfly curve | SNM 확보 확인 |
| 2 | Row Decoder | Transient (tb_RowDecoder) | WL 단일 선택 · `E = 0`일 때 전체 LOW 확인 |
| 3 | SRAM_64bit Top | Transient (tb_SRAM_64bit, VDD = 3.3 V) | **WDATA = 5 → RDATA = 5** 일치 |
| 4 | Layout | Assura DRC | clean |
| 5 | Layout ↔ Schematic | Assura LVS | 일치 |
| 6 | 최종 GDS | `tools/gds_verify.py` — 치수 · W/L · 인스턴스 · 패드 · 연결 추적 | 논문 표 2와 일치, 주소 핀 A[2:0] · A0 공유 확인 ([§6](#6-최종-gds-대조-검증)) |
| 7 | 실리콘 | 라즈베리파이 + 오실로스코프 R/W | **71 사이클 불일치 0** ([06_silicon_measurement.md](06_silicon_measurement.md)) |

---

## 2. 셀 안정성 — Butterfly Curve

<img src="../images/01_sram_cell/SRAM_CELL_ButterflyCurve.png" width="520">

교차 결합된 두 인버터의 VTC를 서로 축을 바꿔 겹쳐 그린 뒤, 두 곡선 사이에 들어가는
최대 정사각형의 한 변으로 **SNM(Static Noise Margin)** 을 읽습니다.
정사각형이 찌그러지거나 사라지면 셀이 노이즈에 의해 상태를 잃는다는 뜻입니다.

이 곡선이 셀 사이징(β = 2.0, PR = 1.0 — [§6.2](#62-트랜지스터-wl) GDS 추출값)의 근거이기도 합니다.
pull-down을 키우면 곡선 눈이 커지지만(read 안정), pull-up까지 커지면 write가 어려워지므로
두 조건을 함께 만족하는 지점에서 사이징을 확정했습니다.

---

## 3. Row Decoder 검증

| Testbench | 결과 파형 |
|---|---|
| <img src="../images/03_row_decoder/tb_RowDecoder_schematic.png" width="340"> | <img src="../images/03_row_decoder/tb_RowDecoder_simulation.png" width="340"> |

확인 항목:

- Row 주소 3비트를 000 → 111로 스윕할 때 WL[0] ~ WL[7]이 **정확히 하나씩만** 어서트되는가
- `E = 0`일 때 8개 WL이 **모두 LOW**인가
- WL 전이 구간에 두 라인이 동시에 뜨는 글리치가 없는가

세 번째 항목이 특히 중요합니다. 글리치가 있으면 write 시 엉뚱한 행에 데이터가 새어 들어가고,
그 증상은 실측에서 "특정 행 전체 오염"으로 나타나 원인 추적이 까다로워집니다.

---

## 4. Top-level R/W 검증 (tb_SRAM_64bit)

### 4.1 Testbench 구성

| 전체 | 셀 영역 | WDATA 소스 | 랜덤 패턴 |
|---|---|---|---|
| <img src="../images/09_testbench/tb_SRAM_64bit_schematic_full.png" width="230"> | <img src="../images/09_testbench/tb_SRAM_64bit_schematic_cell.png" width="230"> | <img src="../images/09_testbench/tb_SRAM_64bit_schematic_WDATA.png" width="230"> | <img src="../images/09_testbench/tb_SRAM_64bit_schematic_random.png" width="230"> |

### 4.2 제어 신호 펄스

`PRE`, `E`, `WE`, `SE` 각각의 `vpulse` 설정입니다. Spectre에서는 **500 ns 펄스폭**으로 정상 동작을 확인했습니다.

| PRE | E | WE | SE |
|---|---|---|---|
| <img src="../images/09_testbench/tb_PRE_pulse.png" width="230"> | <img src="../images/09_testbench/tb_E_pulse.png" width="230"> | <img src="../images/09_testbench/tb_WE_pulse.png" width="230"> | <img src="../images/09_testbench/tb_SE_pulse.png" width="230"> |

### 4.3 Transient 결과

<img src="../images/09_testbench/tb_SRAM_64bit_schematic_simulation.png" width="760">

| 전체 구간 | 파라미터 |
|---|---|
| <img src="../images/09_testbench/tb_SRAM_64bit_schematic_simulation_full.png" width="380"> | <img src="../images/09_testbench/tb_SRAM_64bit_schematic_simulation_param.png" width="380"> |

<img src="../images/09_testbench/SRAM_64bit_simulation.png" width="760">

파형에서 확인한 내용:

- 모든 제어선이 **0 V ↔ 3.3 V 풀스윙**으로 동작 — 3.3 V 전원에서 정상 동작 확인
- `PRE`는 LOW 구간이 프리차지임을 파형으로 재확인 (Active-LOW)
- `WE` 펄스 이후 `SE` 펄스가 뒤따르는 write → read 반복 시퀀스
- 커서 측정: `WDATA_IN = 5` 시점 대비 `RDATA_OUT = 5` — **입력과 출력이 그대로 일치**
- `SE` 펄스 밖 구간에서 `RDATA_OUT`이 0으로 떨어짐 → Sense Amp에 래치가 없다는 점이
  파형으로 드러남. 실측 코드가 `SE = 1` 구간 안에서만 샘플링하도록 만든 근거입니다.
  (실리콘에서는 SE 하강 후 다음 PRE까지 약 1 ms 출력이 유지됐습니다 — [06 §4.2](06_silicon_measurement.md#42-se-하강-후에도-rdata가-유지됨))

> **시뮬레이션(ns)과 실측(μs~ms)의 타이밍 차이**
> Spectre에서는 500 ns 펄스로 충분하지만, 라즈베리파이에서 Python으로 GPIO를 한 번 토글하면
> 수~수십 μs가 걸립니다. SRAM은 정적(static) 메모리라 느리게 동작시켜도 데이터가 유지되므로,
> 실측은 여유 있는 타이밍으로 시작해 `shmoo` 테스트로 줄여가며 마진을 측정합니다.

---

## 5. 물리 검증 — Assura DRC / LVS

| DRC | LVS |
|---|---|
| <img src="../images/11_verification/DRC_result.jpg" width="380"> | <img src="../images/11_verification/LVS_result.jpg" width="380"> |

- **DRC** — NSPL 0.5 μm 2P3M 디자인 룰 기준 clean
- **LVS** — schematic ↔ layout 넷리스트 일치 확인

두 검증을 통과한 뒤 GDS를 stream out 하여 모아팹에 제출했습니다.

---

## 6. 최종 GDS 대조 검증

제출한 최종 GDS(`PKNU_2026_M12.gds`, top = `PKNU_2026_M12`)를 [`tools/gds_verify.py`](../tools/gds_verify.py)로 직접 읽어
문서·논문에 적힌 수치를 대조했습니다. (GDS 파일 자체는 PDK 패드 셀이 포함되어 저장소에 넣지 않습니다.)

```bash
pip install gdstk shapely
python3 tools/gds_verify.py PKNU_2026_M12.gds
```

### 6.1 블록 크기 (bounding box)

| 블록 | GDS 셀 | GDS 실측 (μm) | 논문 표 2 (μm) | 판정 |
|------|--------|---------------|----------------|------|
| 6T SRAM 셀 | `SRAM_CELL` | 35.80 × 25.70 | 35.8 × 25.7 | 일치 |
| 행 디코더 | `RowDecoder` | 163.00 × 212.40 | 163.0 × 212.4 | 일치 |
| 열 디코더 | `ColDecoder` | 345.00 × 19.75 | 345.0 × 19.8 | 일치 (반올림) |
| 프리차지 회로 | `Precharger` | 26.00 × 17.25 | 26.0 × 17.3 | 일치 (반올림) |
| 감지 증폭기 | `SenseAmp` | 28.70 × 30.10 | 28.7 × 30.1 | 일치 |
| 쓰기 드라이버 | `WriteDriver` | 36.30 × 36.60 | 36.3 × 36.6 | 일치 |
| SRAM 코어 | `SRAM_64bit` | 643.80 × 612.70 | 643.8 × 612.7 | 일치 |
| 전체 칩 | `PKNU_MPW2_STD004` | 1900 × 1900 | 1.9 mm × 1.9 mm | 일치 |

### 6.2 트랜지스터 W/L

POLY ∩ ACTIVE 영역으로 게이트를 뽑고, NWELL 포함 여부로 N/P를 구분했습니다. 모든 L = 0.5 μm.
역할은 poly 공유 관계와 배치(셀 가장자리 = access, 같은 x축의 P/N 쌍 = 인버터)로 판별했습니다.

| 블록 | GDS 추출 | 역할별 |
|------|----------|--------|
| 6T 셀 | N 3.2 ×2, N 1.6 ×2, P 1.6 ×2 | **Pull-down 3.2 · Access 1.6 · Pull-up 1.6 → β = 2.0, PR = 1.0** |
| Precharger | P 4.8 ×2, P 2.4 ×1 | 충전 4.8 ×2 · equalizer 2.4 |
| Sense Amp | P 3.2 ×3, N 1.6 ×4 | mirror 3.2 ×2 · 입력쌍 1.6 ×2 · tail 1.6 · 출력 INV P 3.2 / N 1.6 |
| Write Driver | P 6.4 ×2, N 2.2 ×2, P 3.0 ×1, N 1.6 ×3 | 구동 INV P 6.4 / N 2.2 ×2 · INV P 3.0 / N 1.6 · **WE pass NMOS 1.6 ×2** |
| TG | N 1.6, P 1.6 | — |

> 이전 문서에 적혀 있던 6T 셀 사이징(PU 0.8 / PD 1.6 / ACC 1.2, β ≈ 1.33)과 Write Driver pass NMOS 3.2 μm는
> 최종 GDS와 달라 이번에 GDS 값으로 정정했습니다. LVS가 clean이므로 schematic도 같은 값입니다.

### 6.3 인스턴스 · 패드

| 항목 | GDS |
|------|-----|
| `SRAM_64bit` 내부 | SRAM_CELL ×64, Precharger ×8, SenseAmp ×4, WriteDriver ×4, RowDecoder ×1, ColDecoder ×1 |
| ColDecoder / RowDecoder | TG ×16 / NAND4 ×8 |
| 패드 사이트 | 28 (`MPW_PAD_28pin`) |
| 사용 패드 17 | 입력 `PBCT4` ×11 (A0 A1 A2 E PRE WE SE WDATA0–3) · 출력 `POB24` ×4 (RDATA0–3) · `PVDD` · `PVSS` |
| 매크로 주소 핀 | **A0, A1, A2** (A3 없음) |

### 6.4 연결 추적

METAL1/2/3 · POLY 도형을 CONT/VIA1/VIA2로 묶어 넷을 만든 뒤, `SRAM_64bit`의 핀 라벨에서 패드까지 따라갔습니다.

- A0 · A1 · A2 · E · PRE · WE · SE · WDATA0–3 핀이 **각각 같은 이름의 입력 패드 하나에만** 연결됨
- 이 11개 넷 사이에 단락 없음
- `A0` 라벨이 두 곳(RowDecoder 입력, ColDecoder 입력)에 있고, **두 라벨이 같은 METAL1 넷 → A0 패드 하나**로 연결됨
  → 행 디코더 3비트 = A2 A1 A0, 열 선택 = A0 (공유). 주소 구조는 [01_architecture.md](01_architecture.md#2-주소-맵) 참고.

---

## 7. 실리콘 검증

[06_silicon_measurement.md](06_silicon_measurement.md)에 정리했습니다.

- [x] Write → Read 기능 검증 — 주소 4개(000/001/010/100), 71 사이클 불일치 0
- [ ] Read access time 실측 (현재 제어가 ms 단위라 측정 불가)
- [ ] 동작 전압 범위 (VDD 스윕, 3.3 V 동작 포함)
- [ ] 접근 가능한 8 워드 전체 March-C · 불량 셀 맵
- [ ] Simulation vs Silicon 속도 비교
