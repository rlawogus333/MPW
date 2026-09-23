# 실측 테스트 코드

| 파일 | 용도 | 상태 |
|------|------|------|
| [`sram_ctrl_timing.py`](sram_ctrl_timing.py) | PRE · WE · SE 타이밍만 발생 (E·주소·WDATA는 외부 고정) | **2026-09 실측에 사용** |
| [`sram_rw_test.py`](sram_rw_test.py) | 주소·데이터까지 GPIO로 구동하는 전체 R/W 테스트 스위트 | 4-bit 주소 원안 기준 — 칩에 맞게 수정 필요 |
| [`legacy/sram_test_5v_txs0108e.py`](legacy/sram_test_5v_txs0108e.py) | 5 V + TXS0108E 레벨 시프터 초기안 | 보존용 |

## `sram_ctrl_timing.py` — 실측에 사용한 제어 타이밍 발생기

라즈베리파이가 **PRE · WE · SE만** 발생하고, 나머지는 보드에서 고정합니다.
(라즈베리파이에서는 `sram_rw_test.py`라는 이름으로 실행했던 파일입니다.)

| 신호 | 연결 |
|------|------|
| PRE / WE / SE | GPIO 17 / 8 / 7 — 3.3 V 직결 |
| E | 보드에서 5 V 고정 (`--e-ext`) |
| A[2:0] | 보드에서 DC 고정 (`--no-addr`) |
| WDATA | 파형 발생기 · DC |
| RDATA | 오실로스코프로 관찰 (Pi는 읽지 않음) |

```bash
python3 sram_ctrl_timing.py --sim -n 2 --log        # PC에서 에지 순서 확인
python3 sram_ctrl_timing.py rw --e-ext --no-addr    # write → read 무한 반복
python3 sram_ctrl_timing.py shell                   # 핀을 한 번씩 수동 조작
```

기본 타이밍: PRE 1 ms · WE 2 ms · SE 2 ms, 한 사이클 9 ms (실측 약 9.2 ms).
결과는 [`../docs/06_silicon_measurement.md`](../docs/06_silicon_measurement.md)를 보세요.

> 스크립트 머리말의 "칩 VDD = 3.3 V"는 작성 당시 계획입니다. 실측은 VDD = 5 V(USB)로 했고,
> 3.3 V 제어 신호가 그대로 인식됐습니다.

## `sram_rw_test.py` — 전체 테스트 스위트

```bash
python3 sram_rw_test.py --sim      # 하드웨어 없이 로직 검증
python3 sram_rw_test.py conn smoke
python3 sram_rw_test.py all        # conn → smoke → addr → march → disturb → retention
python3 sram_rw_test.py shmoo      # 타이밍 마진 스윕
python3 sram_rw_test.py shell      # 수동 R/W · 스코프 디버깅
```

- GPIO 백엔드 3종 — `lgpio`(Pi 3/4/5) / `RPi.GPIO`(Pi 4 이하) / `sim`(PC 모델)
- interlock — 잘못된 제어선 조합을 코드 레벨에서 차단
- 7종 테스트 — `conn` `smoke` `addr` `march` `disturb` `retention` `shmoo`
- 8×8 불량 맵 + 패턴 기반 자동 원인 진단 · CSV 로깅

> ⚠️ 이 스위트는 주소를 `A[3:0]` 4비트(16 워드)로 가정합니다. 제작된 칩은 `A[2:0]` 3핀에
> A0가 행·열 디코더에 공유되어 **선택 가능한 워드가 8개**입니다 ([01 §2.1](../docs/01_architecture.md#21-제작된-칩-a20-a0-공유)).
> 칩에 그대로 쓰면 주소 0x8 이상과 절반의 셀이 FAIL로 보이므로, 주소 매핑을 먼저 고쳐야 합니다.

자세한 배선과 절차는 [`../docs/04_raspberry_pi_test.md`](../docs/04_raspberry_pi_test.md),
[`../docs/05_test_procedure.md`](../docs/05_test_procedure.md)를 보세요.

## `legacy/sram_test_5v_txs0108e.py` — 초기안 (보존용)

칩을 5 V로 구동하고 TXS0108E 레벨 시프터 2개로 3.3 V ↔ 5 V를 변환하던 초기 버전입니다.
실측에서는 레벨 시프터 없이 3.3 V 제어 신호로 5 V 칩이 동작함을 확인해 사용하지 않았습니다.
TXS0108E 배선표가 필요할 때를 위해 남겨둡니다.
