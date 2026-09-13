# 64-bit (8×8) 6T SRAM — Full-Custom IC 설계 · 검증 · 실측

> **PKNU_2026_M12 / PKNU_MPW2_M12** · 국립부경대학교 전기공학과
> 모아팹(MoaFab) **내 칩(My Chip) 제작 서비스** 2026년 2차 MPW 제출작

Cadence Virtuoso로 64-bit 6T SRAM 매크로를 **풀커스텀(schematic → layout → DRC/LVS → GDS)** 으로 설계하고,
MPW로 제작된 실물 칩을 **라즈베리파이 GPIO 직결**로 Read/Write 검증하는 전체 플로우 프로젝트입니다.

<p align="center">
  <img src="images/10_chip_top/M12_layout_full.png" width="420" alt="PKNU_2026_M12 칩 전체 레이아웃">
</p>

---

## 1. 한눈에 보기

| 항목 | 내용 |
|------|------|
| 용량 | 64-bit = 8 word-line × 8 column (4-bit word × 16 주소) |
| 셀 구조 | 6T CMOS SRAM cell |
| 공정 | **NSPL 0.5 μm Analog CMOS 2-Poly 3-Metal** (ETRI / 모아팹 PDK) |
| 동작 전압 | **VDD = 3.3 V**, VSS = 0 V |
| 설계 툴 | Cadence Virtuoso (schematic · layout), Spectre (시뮬레이션), Assura (DRC/LVS) |
| 주변 회로 | 3-to-8 Row Decoder, Transmission-Gate Column Decoder, Precharger, Current-Mirror Sense Amp, Write Driver |
| 인터페이스 | A[3:0], WDATA[3:0], RDATA[3:0], PRE / E / WE / SE |
| 실측 플랫폼 | Raspberry Pi (BCM GPIO **3.3 V 직결**, 레벨 시프터 불필요) |
| 검증 | Spectre transient/DC · Butterfly(SNM) · Assura DRC/LVS clean · 실리콘 R/W 테스트 |

**동작 전압을 3.3 V로 잡은 이유** — 공정 자체는 5 V 소자용 PDK이지만, 동작 전압을 라즈베리파이 GPIO 레벨인
3.3 V에 맞추면 **TXS0108E 같은 레벨 시프터 없이 GPIO를 칩에 직결**할 수 있습니다.
중간 소자가 빠지면서 배선 기생 성분·방향 감지 지연·High-Z 구간 불확실성이 모두 사라져
실측 환경이 단순해지고 디버깅 시 신뢰할 변수가 줄어듭니다.

---

## 2. 저장소 구조

```
.
├── README.md
├── docs/
│   ├── 01_architecture.md      # 아키텍처 · 주소 맵 · 신호 정의
│   ├── 02_design_blocks.md     # 블록별 schematic / layout 설명
│   ├── 03_verification.md      # Spectre 시뮬레이션 · DRC/LVS
│   ├── 04_raspberry_pi_test.md # 실측 배선 · 핀맵 · 타이밍 · 안전 규칙
│   ├── 05_test_procedure.md    # 테스트 실행 절차 · FAIL 진단
│   └── timing_diagram.html     # 인터랙티브 Write/Read 타이밍 다이어그램
├── images/                     # 설계 캡처 (블록별 분류)
│   ├── 01_sram_cell/ … 07_write_driver/
│   ├── 08_top_sram64/          # SRAM 매크로 top
│   ├── 09_testbench/           # Spectre testbench · 파형
│   ├── 10_chip_top/            # 패드 프레임 포함 칩 top
│   └── 11_verification/        # DRC / LVS 결과
└── test/
    ├── sram_rw_test.py         # ★ 실측 R/W 테스터 (3.3 V 직결, 현행)
    └── legacy/
        └── sram_test_5v_txs0108e.py   # 초기 5 V + 레벨 시프터 버전 (보존용)
```

---

## 3. 빠른 시작 — 실측 테스트

```bash
# 1) PC에서 로직 먼저 검증 (하드웨어 불필요)
python3 test/sram_rw_test.py --sim
python3 test/sram_rw_test.py --sim --fault s0:3,5 --fault pin:A2=0   # 결함 주입

# 2) 라즈베리파이에서 — 칩 받고 제일 먼저
sudo apt install python3-lgpio
python3 test/sram_rw_test.py conn smoke

# 3) 전체 스위트
python3 test/sram_rw_test.py all        # conn→smoke→addr→march→disturb→retention

# 4) 수동 디버깅 (스코프 보며 핀 직접 토글)
python3 test/sram_rw_test.py shell
```

> ⚠️ **칩 VDD를 먼저 올린 뒤 GPIO를 구동**해야 합니다. 칩 전원이 없는 상태에서 GPIO가 HIGH를 내면
> 입력 ESD 다이오드를 통해 역전류가 흘러 칩이 손상될 수 있습니다. 스크립트는 시작 시 이를 확인하는
> 프롬프트를 띄우고, 종료 시 모든 출력을 LOW로 내린 뒤 GPIO를 해제합니다.

자세한 배선·핀맵은 [docs/04_raspberry_pi_test.md](docs/04_raspberry_pi_test.md),
실행 절차와 FAIL 진단은 [docs/05_test_procedure.md](docs/05_test_procedure.md)를 참고하세요.

---

## 4. 설계 하이라이트

### 4.1 주소 구조 — 4-bit 주소로 4-bit word 16개

`A[3:1]`이 Row Decoder로 들어가 WL[0]~WL[7] 중 하나를 선택하고, `A[0]`은 Transmission Gate
Column Decoder에서 Col 0~3 / Col 4~7 중 어느 쪽을 공통 비트라인(CBL)에 연결할지 결정합니다.

```
비트 위치:  주소 a, 데이터 bit k  →  행 = a >> 1,  열 = k + 4·(a & 1)
```

| 주소 | A3 A2 A1 | A0 | 선택 WL | Column 그룹 | 저장 비트 |
|------|----------|----|---------|-------------|-----------|
| 0x0 | 0 0 0 | 0 | WL[0] | Col 0–3 | bit 0–3 |
| 0x1 | 0 0 0 | 1 | WL[0] | Col 4–7 | bit 4–7 |
| … | | | | | |
| 0xF | 1 1 1 | 1 | WL[7] | Col 4–7 | bit 60–63 |

### 4.2 제어 신호

| 신호 | 극성 | 역할 |
|------|------|------|
| `PRE` | **Active-LOW** | Precharger PMOS 3개 도통 → BL·BLB를 VDD로 충전 + equalize |
| `E` | Active-HIGH | Row Decoder NAND4의 4번째 입력. **E가 곧 워드라인 펄스**: `WL = E · decode(A3A2A1)` |
| `WE` | Active-HIGH | Write Driver NMOS pass 게이트. `BL = WDATA`, `BLB = ~WDATA` (비반전) |
| `SE` | Active-HIGH | Sense Amp의 current-mirror tail. `RDATA = (BL > BLB)`, 래치 없음 |

> `SE = 0`이면 `RDATA = 0`입니다. **반드시 `SE = 1` 구간 안에서 샘플링**해야 합니다.

### 4.3 실측 코드가 강제하는 안전 규칙 (interlock)

`sram_rw_test.py`는 아래 규칙을 코드 레벨에서 막아, 배선 실수나 오타로 칩을 망가뜨리거나
엉뚱한 셀을 덮어쓰는 상황을 예방합니다.

1. `PRE = 0` 동안 `E = 0`, `WE = 0` — precharger ↔ 셀/write driver 전류 충돌 방지
2. `E = 1` 동안 주소 변경 금지 — 다른 WL 글리치로 인한 오기록 방지
3. `WE = 1`과 `SE = 1` 동시 금지
4. Read/Write 모두 WL을 열기 전 매번 precharge — 같은 행의 비선택 4개 열이 half-select로 교란되는 것 방지

---

## 5. 검증 요약

| 단계 | 방법 | 결과 |
|------|------|------|
| 셀 안정성 | DC sweep → Butterfly curve (SNM) | [이미지](images/01_sram_cell/SRAM_CELL_ButterflyCurve.png) |
| Row Decoder | tb_RowDecoder transient | WL[0]~WL[7] 단일 선택 확인 |
| Top R/W | tb_SRAM_64bit transient (3.3 V) | **WDATA = 5 → RDATA = 5** 일치 확인 |
| 물리 검증 | Assura DRC | clean ([결과](images/11_verification/DRC_result.jpg)) |
| 물리 검증 | Assura LVS | schematic ↔ layout 일치 ([결과](images/11_verification/LVS_result.jpg)) |
| 실리콘 | Raspberry Pi R/W 테스트 | 칩 수령 후 진행 |

자세한 내용은 [docs/03_verification.md](docs/03_verification.md)에 있습니다.

---

## 6. 프로젝트 참여

| 이름 | 역할 |
|------|------|
| 김창민 | 설계 (Backend — layout, DRC/LVS, GDS stream-out) |
| 김재현 | 설계 (Frontend — schematic 작성 및 Spectre 검증, 실측 테스트 환경) |
| 배종대 교수 | 지도교수 |

---

## 7. 라이선스

설계 문서와 테스트 코드는 MIT 라이선스로 공개합니다.
단, **NSPL/ETRI PDK 및 공정 관련 자료는 배포 제한 대상이므로 이 저장소에 포함하지 않습니다.**
