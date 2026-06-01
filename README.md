# 📂 Wafer Data Analysis & Integrated Reporting System

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-150458?logo=pandas&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-Visualization-black?logo=python)

> **This is an automated system that parses XML-based wafer measurement data and performs precise analysis of IL, ER, VpiL, and Phase Shift to generate visualizations and integrated Excel reports.**

This project is an end-to-end pipeline that automatically analyzes wafer-level test data from optical devices such as Mach-Zehnder Modulators and outputs the results as a dashboard-style report for at-a-glance visualization.

---
# 📝Contents
1. Introduction
2. Project information
3. Directory Structure
4. Install and Run
---
## 📁 디렉토리 구조 (Directory Structure)

정상적인 분석 실행을 위해 데이터와 스크립트가 아래의 구조를 유지해야 합니다. 

```text
📁 pycharm-project-root/
│
├── 📄 run.py                       # 🚀 통합 자동화 실행 파일 (One-click Execution)
│
├── 📁 dat/
│   └── 📄 data                     # 원본 웨이퍼 XML 압축 데이터 (예: HY202103.zip)
│
├── 📁 src/                         # 핵심 분석 모듈 폴더
│   ├── 📄 data_parser.py           
│   ├── 📄 plot.py                  
│   ├── 📄 flatting.py              
│   ├── 📄 zoom.py                  
│   ├── 📄 Fitting.py               
│   ├── 📄 Phase shift - V.py       
│   ├── 📄 VpiL.py                  
│   ├── 📄 ER_Analysis.py           
│   ├── 📄 IL_Analysis.py           
│   ├── 📄 VpiL_Analysis.py         
│   ├── 📄 combine_plot.py          
│   └── 📄 export_summary.py        
│
└── 📁 res/                         # 프로그램 실행 시 자동 생성되는 결과물 디렉토리
    ├── 📁 csv/                     # 요약 및 통합 데이터 CSV 모음
    │   ├── 📄 Analysis.csv             
    │   ├── 📄 Total_Process_result.csv 
    │   └── 📄 {Wafer_ID}_Process_result.csv 
    │
    ├── 📁 xlsx/                    # 하이퍼링크가 포함된 통합 엑셀 리포트 모음
    │   ├── 📄 Analysis.xlsm            
    │   ├── 📄 Total_Process_result.xlsx 
    │   └── 📄 {Wafer_ID}_Process_result.xlsx 
    │
    └── 📁 png/                     # 시각화 이미지 저장소
        ├── 📁 WaferMap/                # 웨이퍼별 ER, IL, VpiL 히트맵
        ├── 📁 BoxPlot/                 # 웨이퍼별 Center vs Edge Box Plot
        └── 📁 {Wafer_ID}/              # [개별 다이 데이터]
            └── 📁 {Date_YYYYMMDD}/     # 측정 날짜별 폴더 
                └── 📄 HY202103_{Wafer}_({C},{R})_LION1_DCM_{Band}.png  # ✨ 병합된 요약 이미지
```

---

## ⚙️ 데이터 분석 파이프라인 (Data Pipeline)

`run.py` 실행 시 내부적으로 총 9개의 핵심 모듈이 순차적으로 동작하며 데이터를 가공합니다. 

### 1. 데이터 추출 및 시각화 준비
* **`data_parser.py` (데이터 파싱)**
  * 원본 XML 데이터 파일에서 분석에 필요한 타겟 밴드(LMZC, LMZO) 스펙트럼 데이터를 불러옵니다.
* **`plot.py` (원시 데이터 플롯)**
  * 파싱된 Raw 데이터를 바탕으로 기본 파장-투과도(Transmission) 스펙트럼 플롯을 생성합니다.

### 2. 신호 보정 및 타겟 영역 추출
* **`flatting.py` (신호 평탄화)**
  * Reference 소자와 MZM 소자 간에 발생하는 오차를 보정하여 신호의 베이스라인을 평탄화(Flattening)합니다.

* **`zoom.py` (타겟 파장 줌인)**
  * 밴드별 특성에 맞춰 주요 분석 타겟 파장 영역을 집중적으로 확대합니다. (LMZC: 1550 nm / LMZO: 1310 nm)

* **`Fitting.py` (노이즈 필터링 및 피팅)**
  * 측정 신호 내부에 존재하는 리플(Ripple) 등의 고주파 노이즈를 제거하고, 다항식 피팅을 적용하여 데이터를 매끄럽게 정제합니다.


### 3. 소자 성능 지표 연산
* **`Phase shift - V.py` (위상 변화 연산)**
  * 피팅된 그래프의 최소점(Dip)을 기준으로, 인가된 바이어스 전압(Bias Voltage)에 따라 파장이 얼마나 이동(Shift)하는지 추적하여 위상 변화량을 계산합니다.
* **`VpiL.py` ($V_\pi L$ 추출)**
  * 바이어스에 따른 위상 변화를 반파장 전압($V_\pi$)으로 환산하고, 소자의 길이($L$)를 곱하여 최종적인 전광 변조 효율 지표인 $V_\pi L$ 수치를 계산합니다.

### 4. Wafer Map 과 Box Graph 자동 생성
* **`ER_Analysis,py` (Wafer Map, Box graph 데이터)**
  * 추출된 주요 수치 데이터(ER)를 `Wafer Map` 및 `Box Graph` 파일
* **`IL_Analysis,py` (Wafer Map, Box graph 데이터)**
  * 추출된 주요 수치 데이터(IL)를 `Wafer Map` 및 `Box Graph` 파일
* **`VpiL_Analysis,py` (Wafer Map, Box graph 데이터)**
  * 추출된 주요 수치 데이터(VpiL)를 `Wafer Map` 및 `Box Graph` 파일


### 5. 시각화 병합 및 리포트 자동 생성
* **`combine_plot.py` (대시보드 이미지 병합)**
  * 개별 분석 과정을 거치며 생성된 여러 장의 그래프를 웨이퍼(Wafer) 및 날짜별로 묶어 **단 한 장의 요약 대시보드 이미지**로 병합합니다.
* **`export_summary.py` (통합 리포트 출력)**
  * 추출된 주요 수치 데이터(IL, ER, $V_\pi L$)를 `csv` 및 `xlsx` 파일로 저장합니다. 엑셀 파일 내에는 **병합된 요약 이미지(PNG)를 클릭 한 번에 열 수 있는 하이퍼링크**가 매핑되어 직관적인 데이터 검증이 가능합니다.