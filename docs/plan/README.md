# Phase 1~6 실행 계획

## Phase 1: 셀 레벨 검증 (SRAM Cell DC/Transient)

**목표**: 6T SRAM 셀 동작 검증 (SNM, Read/Write 마진 확보)

**작업 항목**:

- DC 시뮤레이션으로 Butterfly Curve (SNM) 측정
- Transient: WL Pulse 역할 BL 방류 파형 확인
- WL 쓰기 시 셀 내부 노드 전압 반전 확인
- 비트라인 스윈징 시간 측정

**완료 기준**: SNM > 200mV @ VDD=3.3V

---

## Phase 2: 주변 회로 개별 검증

**목표**: 각 Peri 보 Block 도능 동작 검증

**작업 항목**:

- **Precharger**: PCLK에 따라 BL/BLB = VDD 정상 충전 확인
- **3-to-8 Decoder**: A[2:0] 입력별 Y[7:0] 선택 동작 검증 (8가지 코드)
- **Col Mux**: YSR과 YSW 분리 동작 (동시 선택 안됨)
- **Sense Amp**: SAEN Enable 시 10mV 차이 증폭 검증
- **Write Driver**: Din 변화에 따라 BL/BLB 정확 드라이브 검증
- **Output FF**: S/R 에지 후 Latch 유지 확인

**완료 기준**: 모든 블록이 설계 틀 검증 통과

---

## Phase 3: 통합 시뮤레이션 (8x8 Full Array)

**목표**: 64셀 전체를 통합한 통합 시뮤레이션

**작업 항목**:

- SRAM Cell ×64 + 모든 Peri 회로 연결
- Write → Read 루프 사이클
- All-0 쓰기 시작 후 All-0 읽기 검증
- All-1 쓰기 후 All-1 읽기 검증
- 체커보드 패턴 (0101... / 1010...) 검증
- 타이밍 수렴 및 열화 처리

**완료 기준**: 64셀 전체 동작 이상 없음

---

## Phase 4: Layout & DRC/LVS

**목표**: GDS 생성과 부하 검증 통과

**작업 항목**:

- SRAM Cell Layout (Symmetric, Mirrored) 제작
- Array 8x8 Tile 제작 (Metal 1/2 연결)
- 주변 회로 Layout 포함
- DRC (Design Rule Check) 통과
- LVS (Layout vs. Schematic) 일치 확인
- PEX (Parasitic Extraction) 후 Post-Layout Sim

**완료 기준**: DRC/LVS Clean, 타이밍 수렴

---

## Phase 5: MPW Tape-out

**목표**: GDSII 제출 및 칱 제조

**작업 항목**:

- Final GDS Export
- 디지탈 제조사에 MPW 제출 (쫐작전 주의: 다이 크기, 패드 민요 구조)
- Bond Wire 구성 (선택적 디코방)
- PCB 설계 및 쯔 제작
- 칱 수령 후 안전 보관

**완료 기준**: 제조사 구코 통과 + 칱 수령

---

## Phase 6: Raspberry Pi 테스트

**목표**: 실칱 Read/Write 기능 검증

**작업 항목**:

- PCB 여던 후 칩 연결
- RPi GPIO 핀 할당 확인
- Python 제어 스크립트 작성 (RPi.GPIO 라이브러리)
- All-0/1 Write → Read 자동 테스트
- 체커보드 패턴 검증
- March C- 알고리즘 적용
- 실패 시 파형 분석 (로직 애널라이저 활용)

**완료 기준**: 64셀 전체 Write/Read Pass
