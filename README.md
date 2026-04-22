# SRAM_MPW_Project
# 8x8 SRAM 설계 및 검증 프로젝트 프레임워크

> **PDK**: ETRI My Chip Service  
> **설계 툴**: Cadence Virtuoso + Spectre  
> **테스트 플랫폼**: Raspberry Pi (GPIO 기반)  
> **작성일**: 2026-04-13  

---

## 1. 프로젝트 개요

8x8 (64-bit) SRAM을 ETRI My Chip Service를 통해 설계·제작하고, 라즈베리파이로 실측 검증하는 풀 플로우 프로젝트이다. Row MUX로 Word Line(WL)을 선택하고, Column MUX로 Bit Line(BL) 열을 선택하여 셀 단위 Read/Write 동작을 수행한다.

### 1.1 SRAM 아키텍처 요약

```
        Column MUX (3-to-8 Decoder)
         ┌──┬──┬──┬──┬──┬──┬──┬──┐
         BL0 BL1 BL2 BL3 BL4 BL5 BL6 BL7
    ┌────┼──┼──┼──┼──┼──┼──┼──┼──┤
WL0 │    C  C  C  C  C  C  C  C  │
WL1 │    C  C  C  C  C  C  C  C  │
WL2 │    C  C  C  C  C  C  C  C  │
WL3 │    C  C  C  C  C  C  C  C  │  ← 6T SRAM Cell
WL4 │    C  C  C  C  C  C  C  C  │     Array (8×8)
WL5 │    C  C  C  C  C  C  C  C  │
WL6 │    C  C  C  C  C  C  C  C  │
WL7 │    C  C  C  C  C  C  C  C  │
    └────┴──┴──┴──┴──┴──┴──┴──┴──┘
         │                    │
    Row MUX                Sense Amp
   (3-to-8 Decoder)       + Write Driver
```

### 1.2 주요 신호 정의

| 신호 | 비트 수 | 방향 | 설명 |
|------|---------|------|------|
| CLK | 1 | Input | 마스터 클럭 |
| WE (Write Enable) | 1 | Input | High = Write, Low = Read |
| ROW_ADDR[2:0] | 3 | Input | Row 선택 (3-to-8 디코더 입력) |
| COL_ADDR[2:0] | 3 | Input | Column 선택 (3-to-8 디코더 입력) |
| DIN | 1 | Input | Write 데이터 입력 |
| DOUT | 1 | Output | Read 데이터 출력 |
| CS (Chip Select) | 1 | Input | 칩 활성화 |
| PRE (Precharge) | 1 | Input | BL Precharge 제어 |

---

## 2. 프로젝트 단계별 상세 계획

### Phase 1: 설계 사양 확정 (1주)

- [ ] SRAM 동작 사양 정의 (동작 전압, 목표 주파수, 타이밍 마진)
- [ ] ETRI My Chip Service PDK 확인 및 설계 규칙(DRC/LVS) 파악
- [ ] 6T SRAM 셀 사이징 결정 (NMOS/PMOS W/L ratio)
- [ ] Top-level 블록 다이어그램 확정
- [ ] 핀 배치 및 패드 할당 계획 (ETRI MPW 패드 프레임 규격 확인)

### Phase 2: 회로 설계 — Cadence Virtuoso (3~4주)

#### 2-1. 단위 셀 설계
- [ ] 6T SRAM Cell Schematic 작성
- [ ] Cell 동작 확인 (Read/Write stability)
- [ ] SNM(Static Noise Margin) 시뮬레이션 — Butterfly curve
- [ ] Cell Symbol 생성

#### 2-2. 주변 회로 설계
- [ ] 3-to-8 Row Decoder (Row MUX) Schematic
- [ ] 3-to-8 Column Decoder (Column MUX) Schematic
- [ ] Sense Amplifier Schematic
- [ ] Write Driver Schematic
- [ ] Precharge 회로 Schematic
- [ ] 클럭 버퍼/분배 회로
- [ ] I/O 패드 및 레벨 시프터 (외부 인터페이스용)

#### 2-3. Top-level 통합
- [ ] 8×8 Array 인스턴스화 (Cell × 64)
- [ ] Row Decoder + Column MUX + Sense Amp + Write Driver 연결
- [ ] Top-level Schematic 완성
- [ ] Top-level Symbol 생성

### Phase 3: Spectre 시뮬레이션 검증 (2~3주)

#### 3-1. 단위 셀 검증
- [ ] DC: SNM 측정 (Read SNM, Write SNM)
- [ ] Transient: Single Cell Read/Write 파형 확인
- [ ] Monte Carlo: 공정 변동에 따른 셀 안정성 분석
- [ ] Corner 시뮬레이션 (TT, FF, SS, SF, FS)

#### 3-2. Array 레벨 검증
- [ ] Write 동작: 특정 주소에 '0'/'1' 쓰기 → BL/BLB 파형 확인
- [ ] Read 동작: 저장된 데이터 읽기 → DOUT 파형 확인
- [ ] Read-after-Write: 연속 Write → Read 정합성 확인
- [ ] 전체 셀 순차 접근: Row 0~7, Col 0~7 스캔
- [ ] 타이밍 분석: Setup/Hold time, Access time, Cycle time 측정
- [ ] 소비 전력 분석 (Standby / Active)

#### 3-3. Post-layout 시뮬레이션 (레이아웃 완료 후)
- [ ] RC 추출 후 Spectre 재시뮬레이션
- [ ] 타이밍 열화 확인 및 마진 재검토

### Phase 4: 레이아웃 및 물리 검증 (3~4주)

- [ ] 6T SRAM Cell Layout (최소 면적, 규칙적 배치)
- [ ] Cell을 8×8 Array로 타일링
- [ ] 주변 회로 Layout (Decoder, SA, Write Driver, Precharge)
- [ ] Top-level Floorplan 및 배치/배선
- [ ] DRC (Design Rule Check) — ETRI PDK 규칙 기준
- [ ] LVS (Layout vs Schematic) — Schematic과 Layout 일치 확인
- [ ] RC Extraction (기생 저항/커패시턴스 추출)
- [ ] ETRI MPW 제출 규격에 맞춘 패드 프레임 적용
- [ ] GDS 파일 생성 및 최종 점검

### Phase 5: MPW 제출 및 칩 제작 (8~12주, ETRI 일정에 따라 변동)

- [ ] ETRI My Chip Service 제출 서류 준비
- [ ] GDS + 문서 제출
- [ ] DRC/LVS 최종 리뷰 (ETRI 측 피드백 반영)
- [ ] 제작 대기 및 진행 상황 추적
- [ ] 칩 수령 및 외관 검사

### Phase 6: 라즈베리파이 테스트 환경 구축 (Phase 5 대기 중 병행)

#### 6-1. 하드웨어 셋업
- [ ] 테스트 보드 설계/제작 (칩 소켓 + 라즈베리파이 연결)
- [ ] 칩 핀 ↔ 라즈베리파이 GPIO 핀맵 정의
- [ ] 레벨 시프터 검토 (칩 I/O 전압 ↔ RPi 3.3V)
- [ ] 전원 공급 회로 구성 (VDD/GND, 바이패스 캐패시터)
- [ ] 오실로스코프/로직 분석기 프로브 포인트 확보

#### 6-2. 핀맵 구조 (예시)

| SRAM 핀 | 방향 | RPi GPIO (BCM) | 비고 |
|---------|------|-----------------|------|
| CLK | ← | GPIO 18 (PWM) | 하드웨어 PWM 활용 |
| WE | ← | GPIO 17 | Write Enable |
| CS | ← | GPIO 27 | Chip Select |
| PRE | ← | GPIO 22 | Precharge |
| ROW_ADDR[0] | ← | GPIO 5 | Row 주소 LSB |
| ROW_ADDR[1] | ← | GPIO 6 | |
| ROW_ADDR[2] | ← | GPIO 13 | Row 주소 MSB |
| COL_ADDR[0] | ← | GPIO 19 | Col 주소 LSB |
| COL_ADDR[1] | ← | GPIO 26 | |
| COL_ADDR[2] | ← | GPIO 12 | Col 주소 MSB |
| DIN | ← | GPIO 16 | 데이터 입력 |
| DOUT | → | GPIO 20 | 데이터 출력 |

> ※ 실제 핀맵은 칩 패드 배치 확정 후 갱신 필요

#### 6-3. 테스트 소프트웨어 구조

```
raspberry_pi_test/
├── config/
│   ├── pin_map.json          # GPIO ↔ SRAM 핀 매핑
│   └── timing_params.json    # 클럭 주기, Setup/Hold 등
├── drivers/
│   ├── gpio_controller.py    # GPIO 초기화 및 제어
│   ├── clock_gen.py          # CLK 생성 (PWM 또는 비트뱅)
│   └── sram_interface.py     # 주소/데이터/제어 신호 래핑
├── tests/
│   ├── test_single_cell.py   # 단일 셀 R/W 테스트
│   ├── test_full_scan.py     # 전체 64셀 순차 R/W
│   ├── test_checkerboard.py  # 체커보드 패턴 테스트
│   ├── test_march_c.py       # March-C 알고리즘 테스트
│   └── test_timing.py        # 타이밍 마진 측정
├── utils/
│   ├── logger.py             # 결과 로깅
│   └── report_gen.py         # 테스트 리포트 생성
├── main.py                   # 테스트 실행 엔트리포인트
└── README.md
```

### Phase 7: 실측 검증 (2~3주)

#### 7-1. 기본 동작 테스트
- [ ] 전원 인가 및 전류 소모 확인 (정상 범위 내인지)
- [ ] Single Cell Write → Read 검증 (주소 (0,0)부터)
- [ ] 전체 64셀 순차 Write '1' → Read → 전체 '0' → Read
- [ ] Random Address Read/Write 검증

#### 7-2. 패턴 기반 테스트
- [ ] Checkerboard 패턴 (인접 셀 간섭 검증)
- [ ] March-C 알고리즘 (Stuck-at fault 검출)
- [ ] All-0 / All-1 패턴

#### 7-3. 타이밍 테스트
- [ ] 클럭 주파수 점진적 상승 → 최대 동작 주파수 탐색
- [ ] Setup/Hold 위반 시 동작 실패 지점 확인
- [ ] Read Access Time 측정 (오실로스코프)

#### 7-4. 결과 분석 및 보고
- [ ] Simulation vs Silicon 결과 비교
- [ ] Fail 셀 맵핑 (있을 경우)
- [ ] 최종 테스트 리포트 작성

---

## 3. 타임라인 (예상)

```
Week  1       : ██ Phase 1 — 사양 확정
Week  2 ~  5  : ████████ Phase 2 — 회로 설계 (Virtuoso)
Week  4 ~  7  : ██████ Phase 3 — Spectre 시뮬레이션
Week  6 ~ 10  : ████████ Phase 4 — 레이아웃 & 물리검증
Week 10       : █ Phase 5-1 — MPW 제출
Week 10 ~ 22  : ████████████████████████ Phase 5-2 — 칩 제작 대기
Week 12 ~ 18  : ████████████ Phase 6 — RPi 테스트 환경 구축 (병행)
Week 22 ~ 25  : ██████ Phase 7 — 실측 검증
```

> 총 예상 기간: 약 **25주 (6개월)**  
> ※ ETRI MPW 제작 일정(8~12주)이 가장 큰 변수

---

## 4. Read/Write 동작 시퀀스

### 4.1 Write 동작

```
         ┌───┐   ┌───┐   ┌───┐
CLK  ────┘   └───┘   └───┘   └───
     ┌─────────────────────────────
CS   ┘  (Active High)
     ┌─────────────────────────────
WE   ┘  (Write Enable)
         ┌─────────┐
PRE  ────┘ precharge└─────────────  (precharge → release)
     ════╤═════════════════════════
ADDR     │  ROW[2:0] + COL[2:0]    (주소 안정화)
     ════╧═════════════════════════
     ════╤═════════════════════════
DIN      │  Data Valid              (쓸 데이터)
     ════╧═════════════════════════
```

1. CS 활성화 → PRE로 BL/BLB precharge
2. ROW_ADDR → Row Decoder → 해당 WL 활성화
3. COL_ADDR → Column MUX → 해당 BL 쌍 선택
4. WE=High → Write Driver가 DIN 값을 BL/BLB에 구동
5. CLK 상승 엣지에서 셀에 데이터 저장

### 4.2 Read 동작

1. CS 활성화 → PRE로 BL/BLB를 VDD/2 근처로 precharge
2. ROW_ADDR → Row Decoder → 해당 WL 활성화
3. COL_ADDR → Column MUX → 해당 BL 쌍 선택
4. WE=Low → Sense Amplifier 활성화
5. BL/BLB 전압 차 감지 → DOUT 출력

---

## 5. 핵심 리스크 및 대응

| 리스크 | 영향 | 대응 방안 |
|--------|------|-----------|
| SNM 부족으로 Read 불안정 | 셀 데이터 손상 | Cell ratio 조정, 공정 코너 시뮬 강화 |
| ETRI MPW 일정 지연 | 전체 일정 밀림 | Phase 6 병행으로 유휴시간 최소화 |
| 칩 I/O 전압 ↔ RPi 불일치 | 테스트 불가 | 레벨 시프터 회로 사전 설계 |
| 기생 RC로 타이밍 열화 | 동작 주파수 하락 | Post-layout Sim으로 사전 확인 |
| 제작 후 불량 셀 발생 | 수율 저하 | March-C 등 체계적 고장 탐지 적용 |

---

## 6. 산출물 체크리스트

| 단계 | 산출물 |
|------|--------|
| Phase 1 | 설계 사양서, 블록 다이어그램 |
| Phase 2 | Virtuoso Schematic (Cell, Decoder, SA, Top) |
| Phase 3 | 시뮬레이션 결과 보고서 (파형, SNM, 타이밍) |
| Phase 4 | Layout GDS, DRC/LVS 리포트, RC 추출 넷리스트 |
| Phase 5 | MPW 제출 서류, 제작 완료 칩 |
| Phase 6 | 테스트 보드, RPi 테스트 코드, 핀맵 문서 |
| Phase 7 | 실측 보고서 (Sim vs Silicon 비교 포함) |
