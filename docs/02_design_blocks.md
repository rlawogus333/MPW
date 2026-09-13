# 02. 블록별 설계

공정: **NSPL 0.5 μm Analog CMOS 2P3M** · 동작 전압 **VDD = 3.3 V**
모든 소자는 최소 채널 길이 `L = 0.5 μm`를 사용했습니다.

각 블록은 `*_schematic.png`(회로), `*_layout_box.png`(추상 뷰 / 블록 경계),
`*_layout_instance.png`(인스턴스 전개 뷰) 세 가지로 정리했습니다.

---

## 1. 6T SRAM Cell

| Schematic | Layout (box) | Layout (instance) |
|---|---|---|
| <img src="../images/01_sram_cell/SRAM_CELL_schematic.png" width="260"> | <img src="../images/01_sram_cell/SRAM_CELL_layout_box.png" width="260"> | <img src="../images/01_sram_cell/SRAM_CELL_layout_instance.png" width="260"> |

표준 6T 구조 — 교차 결합 인버터 2개(래치) + access NMOS 2개.

| 소자 | 역할 | W / L |
|------|------|-------|
| M2, M3 (pmos4) | Pull-up | 0.8 μm / 0.5 μm |
| M0, M1 (nmos4) | Pull-down (driver) | 1.6 μm / 0.5 μm |
| M4, M5 (nmos4) | Access (게이트 = WL) | 1.2 μm / 0.5 μm |

**사이징 근거**

- **Cell ratio β = W(pull-down) / W(access) = 1.6 / 1.2 ≈ 1.33**
  Read 시 access 트랜지스터를 통해 BL이 방전되는 동안, 저장 노드 '0'이 들뜨는 전압
  (read disturb)을 억제하려면 pull-down이 access보다 강해야 합니다.
- **PR ratio = W(pull-up) / W(access) = 0.8 / 1.2 ≈ 0.67**
  Write 시 Write Driver가 BLB를 LOW로 끌어 저장 노드 '1'을 뒤집어야 하므로,
  pull-up PMOS는 access NMOS보다 약해야 합니다.
- 두 조건은 서로 반대 방향으로 작용합니다 — read stability를 키우면 writability가 나빠집니다.
  β ≈ 1.33 / PR ≈ 0.67은 그 사이에서 양쪽 마진을 모두 확보한 값입니다.

**Butterfly curve (SNM)**

<img src="../images/01_sram_cell/SRAM_CELL_ButterflyCurve.png" width="460">

두 인버터의 VTC를 겹쳐 그려 최대 내접 정사각형의 변 길이로 Static Noise Margin을 확인했습니다.

---

## 2. Transmission Gate (TG)

| Schematic | Layout (box) | Layout (instance) |
|---|---|---|
| <img src="../images/02_tg/tg_schematic.png" width="260"> | <img src="../images/02_tg/tg_layout_box.png" width="260"> | <img src="../images/02_tg/tg_layout_instance.png" width="260"> |

NMOS + PMOS 병렬 구조. Column Decoder의 기본 단위 셀로 쓰입니다.
단일 NMOS pass gate와 달리 **VDD까지 문턱전압 손실 없이 전달**되므로,
프리차지된 VDD 레벨의 비트라인을 그대로 CBL로 넘길 수 있습니다.

---

## 3. Row Decoder (3-to-8)

| Schematic (top) | NAND4 | INV |
|---|---|---|
| <img src="../images/03_row_decoder/RowDecoder_schematic.png" width="260"> | <img src="../images/03_row_decoder/RowDecoder_schematic_nand4.png" width="260"> | <img src="../images/03_row_decoder/RowDecoder_schematic_inv.png" width="260"> |

| Layout (box) | Layout (instance) |
|---|---|
| <img src="../images/03_row_decoder/RowDecoder_layout_box.png" width="320"> | <img src="../images/03_row_decoder/RowDecoder_layout_instance.png" width="320"> |

**NAND4 + INV × 8** 구조입니다. 각 NAND4는 `A3, A2, A1`의 참/보수 조합 3개와
**`E`를 네 번째 입력**으로 받습니다.

```
WL[n] = E · decode(A3 A2 A1)
```

즉 `E`는 단순한 enable이 아니라 **워드라인 펄스 그 자체**입니다.
디코드 조합은 주소가 바뀌는 순간 즉시 따라 움직이므로, `E = 1` 상태에서 주소를 변경하면
의도하지 않은 WL이 순간적으로 열려 그 행의 데이터가 손상됩니다.
실측 코드가 "`E = 1` 동안 주소 변경 금지"를 interlock으로 막는 이유입니다.

**검증 testbench**

| tb schematic | tb simulation |
|---|---|
| <img src="../images/03_row_decoder/tb_RowDecoder_schematic.png" width="320"> | <img src="../images/03_row_decoder/tb_RowDecoder_simulation.png" width="320"> |

A[3:1]을 000 → 111로 스윕하며 WL[0]~WL[7]이 하나씩만 어서트되는지, 그리고
`E = 0`일 때 모든 WL이 LOW인지 확인했습니다.

---

## 4. Column Decoder (Transmission Gate 기반)

| Schematic (full) | Schematic 1 | Schematic 2 |
|---|---|---|
| <img src="../images/04_col_decoder/ColDecoder_schematic_full.png" width="260"> | <img src="../images/04_col_decoder/Coldecoder_schematic_1.png" width="260"> | <img src="../images/04_col_decoder/ColDecoder_schematic_2.png" width="260"> |

| Layout (box) | Layout (instance) |
|---|---|
| <img src="../images/04_col_decoder/ColDecoder_layout_box.png" width="320"> | <img src="../images/04_col_decoder/ColDecoder_layout_instance.png" width="320"> |

**Transmission Gate 16개 + 인버터 1개**로 구성했습니다.
BL0/BLB0 ~ BL7/BLB7 각각에 TG가 하나씩 붙습니다 (8열 × 2라인 = 16개).

| Column | TG 게이트 연결 | A0 = 0 | A0 = 1 |
|--------|----------------|--------|--------|
| Col 0 – 3 | 인버터 출력 `A_b`를 TG의 N게이트에 연결 | **ON** | OFF |
| Col 4 – 7 | `A0`를 TG의 N게이트(보수는 `A_b`)에 연결 | OFF | **ON** |

두 그룹이 서로 반대 극성으로 묶여 있어, 인버터 하나로 상호배타적 선택이 됩니다.
**Col k와 Col (k+4)가 공통 비트라인 CBL[k]를 공유**하므로 Sense Amp와 Write Driver는
8쌍이 아니라 **4쌍만** 필요합니다.

> 이 구조 때문에 실측에서 나타나는 고장 패턴이 특징적입니다.
> "A0 = 0 쪽 4열만 전부 실패" → A0 핀/인버터/TG 문제,
> "Col k와 Col k+4가 동시에 실패" → 공유 경로(CBL k, SenseAmp k, WriteDriver k, RDATA/WDATA k) 문제.
> 테스터의 `diagnose()`가 이 규칙을 그대로 코드화하고 있습니다.

---

## 5. Precharger

| Schematic | Layout (box) | Layout (instance) |
|---|---|---|
| <img src="../images/05_precharger/Precharger_schematic.png" width="260"> | <img src="../images/05_precharger/Precharger_layout_box.png" width="260"> | <img src="../images/05_precharger/Precharger_layout_instance.png" width="260"> |

**PMOS 3개** 구조, 게이트는 모두 `PRE` (Active-LOW).

| 소자 | 역할 | W / L |
|------|------|-------|
| M0 | BL → VDD 충전 | 4.8 μm / 0.5 μm |
| M1 | BLB → VDD 충전 | 4.8 μm / 0.5 μm |
| M2 | BL ↔ BLB **equalizer** | 2.4 μm / 0.5 μm |

충전용 PMOS를 크게(4.8 μm) 잡아 비트라인 기생 커패시턴스를 빠르게 채우고,
equalizer는 두 라인의 잔류 전압 차이만 없애면 되므로 절반 크기(2.4 μm)로 두었습니다.

equalizer가 중요한 이유는 Sense Amp가 **절대 전압이 아니라 BL−BLB 차분**을 읽기 때문입니다.
직전 사이클의 잔류 ΔV가 남으면 다음 읽기에서 그 값이 그대로 오프셋으로 더해져,
멀쩡한 셀도 잘못 읽힐 수 있습니다.

---

## 6. Sense Amplifier (Current Mirror 타입)

| Schematic | Layout (box) | Layout (instance) |
|---|---|---|
| <img src="../images/06_sense_amp/SenseAmp_schematic.png" width="260"> | <img src="../images/06_sense_amp/SenseAmp_layout_box.png" width="260"> | <img src="../images/06_sense_amp/SenseAmp_layout_instance.png" width="260"> |

| 소자 | 역할 | W / L |
|------|------|-------|
| M0, M1 (pmos4) | Current mirror 부하 | 3.2 μm / 0.5 μm |
| M2 (nmos4) | 입력 — 게이트 = **BLB** | 1.6 μm / 0.5 μm |
| M3 (nmos4) | 입력 — 게이트 = **BL** | 1.6 μm / 0.5 μm |
| M4 (nmos4) | Tail — 게이트 = **SE** | 1.6 μm / 0.5 μm |
| I1 (inv) | 출력 버퍼 → `RDATA` | P 3.2 μm / N 1.6 μm, L = 0.5 μm |

동작:

```
SE = 1  →  tail 전류 흐름  →  BL > BLB 이면 M3 쪽이 더 많이 도통
        →  출력 노드 LOW  →  인버터 통과  →  RDATA = 1
RDATA = (BL > BLB)   (비반전)
```

**주의 — 래치가 없습니다.** `SE = 0`이면 tail이 끊기고 출력 노드가 VDD로 떠서
인버터를 통과한 `RDATA`는 **0**이 됩니다. 이 0은 "저장값 0"이 아니라 "무효"입니다.
따라서 실측 샘플링은 반드시 `SE = 1` 구간 안에서 이루어져야 하며,
테스터는 기본적으로 한 번의 read마다 3회 샘플해 값이 흔들리면 `~`(불안정)로 따로 표시합니다.

---

## 7. Write Driver

| Schematic | Layout (box) | Layout (instance) |
|---|---|---|
| <img src="../images/07_write_driver/WriteDriver_schematic.png" width="260"> | <img src="../images/07_write_driver/WriteDriver_layout_box.png" width="260"> | <img src="../images/07_write_driver/WriteDriver_layout_instance.png" width="260"> |

인버터 체인 + `WE` 게이트 NMOS 2개(각 3.2 μm / 0.5 μm) 구조입니다.

```
WDATA ──┬── inv(I6) ── inv(I5) ──[NMOS, gate=WE]── BL    →  BL  =  WDATA
        └────────────── inv(I4) ──[NMOS, gate=WE]── BLB   →  BLB = ~WDATA
```

인버터를 하나 더 통과시켜 **BL 쪽은 비반전, BLB 쪽은 반전**을 만듭니다.
즉 `WDATA = 1` → `BL = HIGH, BLB = LOW`이고, Spectre testbench에서
`WDATA = 5` → `RDATA = 5`로 입출력이 그대로 일치함을 확인했습니다.

구동 인버터는 P 6.4 μm / N 2.2 μm로 크게 잡아, 프리차지로 VDD까지 올라간 비트라인을
셀 latch가 뒤집힐 만큼 빠르게 끌어내릴 수 있도록 했습니다.

---

## 8. Top — SRAM_64bit 매크로

| Symbol | Schematic (full) | Layout (full) |
|---|---|---|
| <img src="../images/08_top_sram64/SRAM_64bit_symbol.png" width="260"> | <img src="../images/08_top_sram64/SRAM_64bit_schematic_full.png" width="260"> | <img src="../images/08_top_sram64/SRAM_64bit_layout_full.png" width="260"> |

블록별 상세 뷰:

| 영역 | Schematic | Layout |
|------|-----------|--------|
| Row Decoder | <img src="../images/08_top_sram64/SRAM_64bit_schematic_row_decoder.png" width="220"> | <img src="../images/08_top_sram64/SRAM_64bit_layout_block_top.png" width="220"> |
| Column Decoder | <img src="../images/08_top_sram64/SRAM_64bit_schematic_col_decoder.png" width="220"> | <img src="../images/08_top_sram64/SRAM_64bit_layout_block_full.png" width="220"> |
| Precharger | <img src="../images/08_top_sram64/SRAM_64bit_schematic_precharger.png" width="220"> | — |
| Sense Amp + Write Driver | <img src="../images/08_top_sram64/SRAM_64bit_schematic_SA_WriteDriver.png" width="220"> | <img src="../images/08_top_sram64/SRAM_64bit_layout_block_bottom.png" width="220"> |
| 하단 I/O | <img src="../images/08_top_sram64/SRAM_64bit_schematic_bottom.png" width="220"> | — |

플로어플랜은 셀 어레이를 중앙에 두고, 위쪽에 Row Decoder,
아래쪽에 Precharger → Column Decoder → Sense Amp / Write Driver를 배치하는 구조입니다.
비트라인이 세로로 곧게 내려가고 워드라인이 가로로 지나가도록 해 배선 기생 성분을 최소화했습니다.

---

## 9. Chip Top — 패드 프레임 포함

<p align="center">
  <img src="../images/10_chip_top/M12_layout_full.png" width="460">
</p>

MPW 패드 프레임에 SRAM 매크로를 배치하고, 각 신호를 I/O 패드까지 라우팅한 최종 top입니다.

| 영역 | 이미지 |
|------|--------|
| 매크로 중심부 | [M12_layout_main.png](../images/10_chip_top/M12_layout_main.png) |
| 좌측 / 좌상단 | [M12_layout_left.png](../images/10_chip_top/M12_layout_left.png) · [M12_layout_left_top.png](../images/10_chip_top/M12_layout_left_top.png) |
| RDATA 배선 (상단) | [M12_layout_top_RDATA.png](../images/10_chip_top/M12_layout_top_RDATA.png) |
| WDATA 배선 (하단 / 우측) | [M12_layout_bottom_WDATA.png](../images/10_chip_top/M12_layout_bottom_WDATA.png) · [M12_layout_right_WDATA.png](../images/10_chip_top/M12_layout_right_WDATA.png) |
| Read / Write 경로 | [M12_layout_Read_Write.png](../images/10_chip_top/M12_layout_Read_Write.png) |
| Row Decoder | [M12_layout_rowdecoder.png](../images/10_chip_top/M12_layout_rowdecoder.png) |
| 프로젝트 로고 (`PKNU 2026 M12`) | [M12_Logo.png](../images/10_chip_top/M12_Logo.png) |
