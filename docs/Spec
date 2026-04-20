# 🚀 8x8 Full-Custom SRAM Design & Verification Project

![SRAM Architecture](https://img.shields.io/badge/Tools-Cadence%20Virtuoso-orange) ![Process](https://img.shields.io/badge/Process-PDK%200.5um-blue) ![Category](https://img.shields.io/badge/Category-Memory%20IP%20Design-green)

본 프로젝트는 **Cadence Virtuoso**를 활용하여 Schematic 설계부터 Layout, Post-Layout Simulation까지 진행하는 **Full-Custom 8x8 SRAM(Static Random Access Memory)** 설계 및 검증 프로세스를 담고 있습니다. MPW(Multi-Project Wafer) 제작을 목표로 하며, Raspberry Pi를 이용한 실물 테스트 전략을 포함합니다.

---

## 📐 1. 프로젝트 개요 및 설계 사양

### 프로젝트 목표
* **Full-Custom IC 설계:** Cadence Virtuoso를 이용한 8×8 SRAM 설계 및 Spectre 시뮬레이션 검증.
* **MPW Tape-out:** 설계 완료 후 GDSII 추출 및 칩 제작 프로세스 수행.
* **Hardware Verification:** 제작 완료된 칩을 Raspberry Pi GPIO와 연결하여 Row/Column Mux 제어를 통한 개별 셀 Read/Write 동작 테스트.

### 핵심 사양 (Specifications)
| 항목 | 내용 |
| :--- | :--- |
| **SRAM 구조** | 8 × 8 = 64 Cell (6T SRAM) |
| **공정 (Process)** | 0.5μm CMOS Process |
| **동작 전압 (VDD)** | 3.3V |
| **설계 & 시뮬레이션** | Cadence Virtuoso / Spectre |
| **테스트 환경** | Raspberry Pi 4/5 GPIO Interface |
| **어드레스 구성** | Row 3-bit + Column 3-bit |

---

## 🔬 2. 6T SRAM Cell 설계 상세

### 트랜지스터 사이징 (Transistor Sizing)
안정적인 Static Noise Margin(SNM) 확보와 Write 동작을 위해 최적화된 Ratio를 적용했습니다.

| 소자 (Transistor) | W / L | 용도 (Role) |
| :--- | :--- | :--- |
| **PMOS Load** | 4.8μm / 0.5μm | Pull-up (Data Latching) |
| **NMOS Access** | 1.6μm / 0.5μm | Cell Access (Wordline Control) |
| **NMOS Driver** | 1.6μm / 0.5μm | Pull-down (Data Storage) |

### 회로 구성 (Cell Structure)
6T SRAM 셀은 두 개의 Cross-coupled Inverter와 두 개의 Access Transistor로 구성됩니다.
* **M1, M3 (PMOS Load):** 안정적인 데이터 유지를 위한 부하 소자.
* **M2, M4 (NMOS Driver):** 저장 노드의 전위를 결정하는 드라이버 소자.
* **M5, M6 (NMOS Access):** $WL$ 신호에 의해 활성화되어 $BL/BLB$와 데이터를 주고받음.

---

## 🏗 3. Project Architecture
SRAM의 핵심 블록들을 계층 구조(Hierarchical Structure)로 설계했습니다.

* **Row Decoder (3-to-8):** 8개의 Wordline($WL$) 중 하나를 선택.
* **Column Decoder (3-to-8):** 8개의 Column Select 신호($YSW/YSR$) 생성.
* **Per-Column Circuitry:** Precharge 회로(PMOS Pull-up) 및 Column Mux 포함.
* **Common Shared Circuitry:**
    * **Sense Amplifier:** Voltage Latch-type으로 비트라인의 미세 전압 증폭.
    * **Write Driver:** 강력한 인버터 체인으로 셀에 데이터 기록.
    * **Control Logic:** ATD(Address Transition Detection) 회로 구현.

---

## 🛠 4. 수행 절차 (Step-by-Step)

1.  **Schematic & Unit Verification:** 6T Cell 및 개별 Peripheral 블록(Decoder, SA 등) 설계 및 검증.
2.  **System Integration:** 전체 시스템 통합 후 Transient Analysis 및 전력 소모(Power) 분석.
3.  **Physical Design (Layout):** DRC/LVS를 준수하는 레이아웃 설계 및 Pitch Matching 최적화.
4.  **Post-Layout Simulation:** PEX를 통한 기생 성분 추출 및 최종 성능 확인.

---

## 📡 5. 테스트 전략 (Raspberry Pi Interface)
라즈베리파이 GPIO의 속도 한계를 보완하기 위한 설계 전략입니다.

* **Timing:** 내부 **ATD 회로**를 통해 셀프 타이밍을 구현하여 외부 신호 동기화.
* **Data Verification:** 0x00(0행 0열)부터 0x3F(7행 7열)까지 순차적으로 데이터를 쓰고 읽어 정합성 확인.

---

## 💻 Tech Stacks
* **Design:** Cadence Virtuoso
* **Simulation:** Spectre, ADE L/XL
* **Verification:** Mentor Graphics Calibre (DRC, LVS, PEX)
* **Testing:** Python (Raspberry Pi GPIO Control)

---

### 📝 Note
이 저장소에는 공정 PDK 관련 보안 파일은 포함되어 있지 않으며, 설계 방법론과 검증 결과 보고서(PDF)를 중심으로 구성되어 있습니다.
