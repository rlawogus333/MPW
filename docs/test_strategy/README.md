## 🧪 5. 테스트 및 검증 전략 (Test Strategy)

본 프로젝트는 설계의 신뢰성을 확보하기 위해 시뮬레이션 단계부터 실물 칩 테스트까지 단계별 검증을 수행합니다.

### 🔴 단계 1: 시뮬레이션 검증 (Spectre Pre-Sim)

#### Level 1: Cell Level Verification
* **Butterfly Plot (DC Sweep):** SNM(Static Noise Margin) > 200mV 확보 여부 확인.
* **Hold SNM:** $WL=0$ 상태에서 데이터 유지 능력 검증.
* **Read SNM:** $WL=1, BL=VDD$ 상태에서 읽기 동작 시 데이터 파괴 여부 확인.
* **Write Margin:** $BL=0, BLB=VDD$ 상태에서 성공적인 데이터 반전(Flip) 확인.

#### Level 2: Individual Block Verification
| 테스트 항목 | 검증 내용 | 기대 결과 |
| :--- | :--- | :--- |
| **Precharger** | BL/BLB Precharge 속도 및 레벨 | $PCLK$ 하강 후 10ns 내 VDD 도달 |
| **Decoder** | 3-to-8 주소 디코딩 정확성 | 모든 입조합에 대한 정확한 WL 출력 |
| **Col Mux** | YSR/YSW 경로 분리 및 선택 | 읽기/쓰기 신호 간의 간섭(Contention) 없음 |
| **Sense Amp** | 최소 전압 차 증폭 능력 | 10mV 내외의 전압 차이를 고속으로 증폭 |
| **Write Driver** | Full-Swing 드라이빙 성능 | 설정된 타이밍 내에 BL/BLB 전위 반전 |
| **Output FF** | 데이터 래칭 안정성 | Setup/Hold Time 준수 및 출력 유지 |

#### Level 3: 통합 테스트 (Full Array Integration)
모든 셀에 대해 아래 패턴을 적용하여 전체 동작을 검증합니다.
* **All-0 / All-1:** 전체 셀에 동일 데이터 기록 후 읽기.
* **Checkerboard (0101):** 인접 셀 간의 간섭 여부 확인.
* **March C-:** 메모리 테스트 표준 알고리즘을 통한 커플링 결함 검증.

---

### 🟢 단계 2: 실물 칩 테스트 (with Raspberry Pi)

제작된 칩의 동작을 확인하기 위해 **March C- 알고리즘**을 자동화하여 테스트를 수행합니다.

#### March C- 알고리즘 단계
1. **Step 1:** 전체 셀에 `0` 쓰기 (Initialize)
2. **Step 2:** 정순(↑)으로 `Read 0`, `Write 1` 수행
3. **Step 3:** 정순(↑)으로 `Read 1`, `Write 0` 수행
4. **Step 4:** 역순(↓)으로 `Read 0`, `Write 1` 수행
5. **Step 5:** 역순(↓)으로 `Read 1`, `Write 0` 수행
6. **Step 6:** 전체 셀 `Read 0` 확인 (Final Check)

#### 자동화 테스트 코드 (Python Example)
```python
def march_c_minus(sram):
    N = 8  # Array Size (8x8)
    errors = []
    
    # Step 1: 전체 0 초기화
    for r in range(N):
        for c in range(N):
            sram.write(r, c, 0)
    
    # Step 2: 순차 Read 0 후 Write 1
    for r in range(N):
        for c in range(N):
            if sram.read(r, c) != 0:
                errors.append((r, c, 'read0_fail'))
            sram.write(r, c, 1)
    
    # (이후 Step 3~6 과정을 반복하여 테스트 수행)
    
    return errors

if __name__ == '__main__':
    test_results = march_c_minus(sram)
    if not test_results:
        print("✅ PASS: March C- Algorithm Success")
    else:
        print(f"❌ FAIL: {len(test_results)} Errors Detected")
