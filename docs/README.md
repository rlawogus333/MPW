# 🚀 8x8 Full-Custom SRAM Design & Verification Project

![SRAM Architecture](https://img.shields.io/badge/Tools-Cadence%20Virtuoso-orange) ![Process](https://img.shields.io/badge/Process-PDK%200.18um%2F28nm-blue) ![Category](https://img.shields.io/badge/Category-Memory%20IP%20Design-green)

본 프로젝트는 **Cadence Virtuoso**를 활용하여 Schematic 설계부터 Layout, Post-Layout Simulation까지 진행하는 **Full-Custom 8x8 SRAM(Static Random Access Memory)** 설계 및 검증 프로세스를 담고 있습니다. MPW(Multi-Project Wafer) 제출을 목표로 설계된 고집적 메모리 IP 프로젝트입니다.

---

## 🏗 Project Architecture
SRAM의 핵심 블록들을 계층 구조(Hierarchical Structure)로 설계하여 재사용성과 가독성을 극대화했습니다.

### 1. Top-Level Structure
* **Row & Column Decoder (3-to-8):** 8행 8열의 셀을 선택하기 위한 주소 디코딩 로직.
* **8x8 Core Cell Array:** 64개의 **6T SRAM Cell**로 구성된 메인 스토리지 영역.
* **Per-Column Circuitry:**
    * Precharge 회로 (PMOS Pull-up)
    * Column Mux (Pass Transistor/TG Switch)
* **Common Shared Circuitry:**
    * **Sense Amplifier:** Voltage Latch-type을 적용하여 미세 전압(Bit-line) 증폭.
    * **Write Driver:** 데이터 기록을 위한 강력한 인버터 체인 기반 드라이버.
    * **Control Logic:** ATD(Address Transition Detection) 및 타이밍 제어 유닛.

---

## 🛠 Step-by-Step Procedure

### Step 1. Schematic Design & Unit Verification
* **6T SRAM Cell:** PDK 가이드를 준수하여 Read/Write Margin을 고려한 트랜지스터 사이징.
* **Peripheral Blocks:** NAND/Inverter 기반 디코더 및 Latch-type SA 설계.
* **Unit Test:** Spectre를 활용하여 각 블록의 단독 동작 특성 검증.

### Step 2. System Integration & Transient Analysis
* **Integration:** 모든 블록을 결합하여 Full-Chip Schematic 완성.
* **Timing Optimization:** ATD 신호와 $WL$ 활성화, $SA\_EN$ 시점의 최적화로 타이밍 마진 확보.
* **Power Analysis:** 동작별(Read/Write) 평균 및 Peak 전력 소모 측정.

### Step 3. Physical Design (Layout)
* **Floorplan:** 면적 최소화를 위한 Decoder 및 Array 배치 전략 수립.
* **Pitch Matching:** Column 회로와 Cell Array의 폭을 일치시켜 배선 효율성 극대화 ($M1, M2$).
* **Verification:**
    * **DRC (Design Rule Check):** 공정 규칙 준수 확인.
    * **LVS (Layout vs Schematic):** 회로도와 레이아웃 일치성 검증.

### Step 4. Post-Layout Simulation
* **PEX (Parasitic Extraction):** 배선에 따른 기생 R/C 성분 추출.
* **Final Verification:** 기생 성분이 포함된 실제 하드웨어 환경에서의 성능(Speed, Power) 최종 확인.

---

## 📡 Test Strategy (External Interface)
저속 제어 장치(Raspberry Pi)와의 인터페이스를 고려한 설계 전략입니다.

* **Address Control:** GPIO를 통한 Row/Column 주소 제어.
* **Self-Timing:** 내부 **ATD(Address Transition Detection)** 회로를 구현하여 외부 GPIO의 느린 속도를 보완하고 내부 고속 동작 동기화.
* **Full-Range Test:** 0x00부터 0x3F까지 전 영역 순차적 쓰기/읽기를 통한 데이터 정합성 확인.

---

## 💻 Tech Stacks
* **Design Tools:** Cadence Virtuoso (Schematic, Layout)
* **Simulation:** Spectre, ADE L/XL
* **Verification:** Mentor Graphics Calibre (DRC, LVS, PEX)
* **Languages:** Verilog (Functional Modeling), Skill Script (Option)

---

### 📝 Note
이 저장소에는 실제 공정 PDK(Process Design Kit) 파일은 포함되어 있지 않습니다. 설계 방법론과 검증 결과 보고서를 중심으로 구성되었습니다.
