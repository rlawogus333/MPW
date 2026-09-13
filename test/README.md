# 실측 테스트 코드

## `sram_rw_test.py` — 현행 (3.3 V 직결)

PKNU_2026_M12 8×8 SRAM의 Raspberry Pi R/W 테스터입니다.
칩 `VDD = 3.3 V`, 라즈베리파이 GPIO 직결 (레벨 시프터 없음).

```bash
python3 sram_rw_test.py --sim      # 하드웨어 없이 로직 검증
python3 sram_rw_test.py conn smoke # 칩 받으면 제일 먼저
python3 sram_rw_test.py all        # 전체 스위트
python3 sram_rw_test.py shmoo      # 타이밍 마진 스윕
python3 sram_rw_test.py shell      # 수동 R/W · 스코프 디버깅
```

구성:

- GPIO 백엔드 3종 — `lgpio`(Pi 3/4/5) / `RPi.GPIO`(Pi 4 이하) / `sim`(PC 모델)
- interlock — 잘못된 제어선 조합을 코드 레벨에서 차단
- 7종 테스트 — `conn` `smoke` `addr` `march` `disturb` `retention` `shmoo`
- 8×8 불량 맵 + 패턴 기반 자동 원인 진단
- CSV 로깅 (실측 시 자동 생성)

자세한 배선과 절차는 [`../docs/04_raspberry_pi_test.md`](../docs/04_raspberry_pi_test.md),
[`../docs/05_test_procedure.md`](../docs/05_test_procedure.md)를 보세요.

## `legacy/sram_test_5v_txs0108e.py` — 초기안 (보존용)

칩을 5 V로 구동하고 TXS0108E 레벨 시프터 2개로 3.3 V ↔ 5 V를 변환하던 초기 버전입니다.
동작 전압을 3.3 V로 확정하면서 사용하지 않게 되었지만,
TXS0108E 배선표와 5 V 기준 타이밍 파라미터가 필요할 때를 위해 남겨둡니다.
