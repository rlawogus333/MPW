## 🧩 보유 회로 블록 현황 (Circuit Block Status)

현재 모든 핵심 블록의 **Schematic 설계 및 Symbol 라이브러리 제작**이 완료된 상태입니다.

### 📋 회로 블록 리스트
| 번호 | 블록 이름 | 주요 기능 | 상태 |
| :--- | :--- | :--- | :--- |
| 1 | **SRAM_CELL** | 6T SRAM 단위 셀 (Core Storage) | ✅ 완성 |
| 2 | **3to8Decoder** | Row/Col 3-bit 주소 디코더 (WL0~WL7 선택) | ✅ 완성 |
| 3 | **Precharger** | BL/BLB 라인 정전압(VDD) 프리차지 | ✅ 완성 |
| 4 | **col_mux_slice** | YSR/YSW 분리형 컬럼 멀티플렉서 | ✅ 완성 |
| 5 | **SenseAmp** | 래치형 미세 전압 감지 증폭기 | ✅ 완성 |
| 6 | **Write_driver** | 입력 데이터(Din)를 BL/BLB로 드라이브 | ✅ 완성 |
| 7 | **Output_FF** | NAND2 기반 SR Latch (Dout 유지) | ✅ 완성 |
| 8 | **inv / nand2 / nand4** | 표준 로직 게이트 라이브러리 | ✅ 완성 |

---

## 🔍 주요 블록 상세 설명

### 1️⃣ SRAM_CELL (6T Core)
* **구성:** Cross-coupled Inverter ×2 + Access NMOS ×2
* **Sizing:** PMOS 4.8μm/0.5μm (Load), NMOS 1.6μm/0.5μm (Driver/Access)
* **안정성:** 읽기 동작 시 데이터 파괴 방지를 위해 $\beta$ Ratio ($W_{driver} / W_{access}$)를 고려한 설계 적용.

### 2️⃣ 3to8Decoder
* **입력:** A[2:0] (3-bit Address) / **출력:** Y[7:0] (8개 Wordline 또는 Column Select)
* **구현:** High-speed 동작을 위해 `nand4` + `inv` 조합의 Static 로직으로 설계.

### 3️⃣ Precharger
* **동작:** $PCLK$ 가 Low일 때 비트라인을 VDD로 충전.
* **구조:** 3개의 PMOS를 사용하여 두 라인의 Pull-up 및 **Equalization(평형화)** 수행.

### 4️⃣ col_mux_slice (Path Separation)
* **Read Path (YSR):** Sense Amp로 비트라인 연결.
* **Write Path (YSW):** Write Driver의 신호를 비트라인에 인가.
* **특징:** 읽기/쓰기 경로를 분리하여 신호 간섭 방지 및 동작 신뢰성 향상.

### 5️⃣ SenseAmp (Latch-type)
* **동작:** $SAEN$ 신호 활성화 시 동작.
* **기능:** 비트라인 쌍($BL, BLB$) 사이의 미세한 전압 차이를 양전원 피드백을 통해 Rail-to-Rail로 고속 증폭.

### 6️⃣ Write_driver
* **기능:** $WEN$ 신호에 따라 입력 `Din` 값을 비트라인에 강제로 주입.
* **출력:** `Din=1`일 때 $BL=VDD, BLB=0$ / `Din=0`일 때 $BL=0, BLB=VDD$.

### 7️⃣ Output_FF (SR Latch)
* **구성:** 2개의 `nand2` 게이트를 활용한 교차 피드백 구조.
* **역할:** Sense Amp에서 출력된 일시적인 데이터를 다음 읽기 동작 전까지 안정적으로 유지(Latch).
