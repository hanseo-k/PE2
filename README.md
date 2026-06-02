# 📂 Wafer Data Analysis & Integrated Reporting System

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-150458?logo=pandas&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-Visualization-black?logo=python)
---
# 📝Contents
1. Introduction
2. Project information
3. Directory Structure
4. Install and Run
---
> **This is an automated system that parses XML-based wafer measurement data and performs precise analysis of IL, ER, VpiL, and Phase Shift to generate visualizations and integrated Excel reports.**

This project is an end-to-end pipeline that automatically analyzes wafer-level test data from optical devices such as Mach-Zehnder Modulators and outputs the results as a dashboard-style report for at-a-glance visualization.

---
## 1. Introduction
-PE2: WOP project

Our goal is to build a system that automatically analyzes optical characteristics using Python and XML data.
## 👥 Contributors

|     Name      |       E-mail       | 
|:-------------:|:------------------:|
|  Lee Hangyol  | 0000@hanyang.ac.kr |
| Jeong Jae-min | 0000@hanyang.ac.kr |
| Lee HyoSeong  | 0000@hanyang.ac.kr |
|  Kim HanSeo   | 0000@hanyang.ac.kr |
---
# 2. Project information
### 📖 About This Project

Our goal is to build a system that automatically analyzes
optical characteristics using Python and XML data.

The system receives raw wafer data from the customer along
with specific analysis requests, including:

- Target Wafer
- Die Row & Column
- Analysis Options

Based on these inputs, the pipeline acts as a **black box** —
automatically processing the requested data and delivering
the final results without manual intervention.

---

### ▶️ How It Works

1. Extract files named `HY202103` from the customer-provided dataset
2. Process raw XML data through a series of analysis modules
3. Export the final results as `.csv` and `.xlsx` reports
---
## 📁 Directory Structure

The project is structured to separate raw inputs, 
processed outputs, and source logic clearly

```text
📁 pycharm-project-root/
│
├── 📄 run.py                       # Integrated automation entry point (One-click Execution)
│
├── 📁 dat/
│   └── 📄 data                     # Raw wafer XML compressed data (ex: HY202103.zip)
│
├── 📁 src/                         # Core analysis module directory
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
└── 📁 res/                         # Output directory automatically generated at runtime
    ├── 📁 csv/                     # Collection of summary and consolidated data CSVs
    │   ├── 📄 Analysis.csv             
    │   ├── 📄 Total_Process_result.csv 
    │   └── 📄 {Wafer_ID}_Process_result.csv 
    │
    ├── 📁 xlsx/                    # Collection of consolidated Excel reports with hyperlinks
    │   ├── 📄 Analysis.xlsm            
    │   ├── 📄 Total_Process_result.xlsx 
    │   └── 📄 {Wafer_ID}_Process_result.xlsx 
    │
    └── 📁 png/                     # Visualization image storage
        ├── 📁 WaferMap/                # Per-wafer ER, IL, and VpiL heatmaps
        ├── 📁 BoxPlot/                 # Per-wafer Center vs Edge box plots
        └── 📁 {Wafer_ID}/              # Individual die data
            └── 📁 {Date_YYYYMMDD}/     # Per-measurement-date folders 
                └── 📄 HY202103_{Wafer}_({C},{R})_LION1_DCM_{Band}.png  # Merged summary images
```

---

## ⚙️ 데이터 분석 파이프라인 (Data Pipeline)

`run.py` 실행 시 내부적으로 총 9개의 핵심 모듈이 순차적으로 동작하며 데이터를 가공합니다. 

### 1. 데이터 추출 및 시각화 준비
* **`data_parser.py` (데이터 파싱)**
  * 원본 XML 데이터 파일에서 분석에 필요한 타겟 밴드(LMZC, LMZO) 스펙트럼 데이터를 불러옵니다.
* **`plot.py` (원시 데이터 플롯)**
  * 파싱된 Raw 데이터를 바탕으로 기본 파장-투과도(Transmission) 스펙트럼 플롯을 생성합니다.

<img width="989" height="590" alt="D07_C0_R0_LMZC_Raw" src="https://github.com/user-attachments/assets/96f24f7d-ff9e-44ef-946a-5471b433d626" />

### 2. 신호 보정 및 타겟 영역 추출
* **`flatting.py` (신호 평탄화)**
  * Reference 소자와 MZM 소자 간에 발생하는 오차를 보정하여 신호의 베이스라인을 평탄화(Flattening)합니다.

<img width="989" height="590" alt="D07_C0_R0_LMZC_Flat" src="https://github.com/user-attachments/assets/27be193e-6cf5-4301-8ad5-cbfc1fffd25f" />

* **`zoom.py` (타겟 파장 줌인)**
  * 밴드별 특성에 맞춰 주요 분석 타겟 파장 영역을 집중적으로 확대합니다. (LMZC: 1550 nm / LMZO: 1310 nm)

<img width="990" height="590" alt="D07_C0_R0_LMZC_Zoom" src="https://github.com/user-attachments/assets/e3782f8c-73f1-4885-9f2d-93f716d63e9d" />

* **`Fitting.py` (노이즈 필터링 및 피팅)**
  * 측정 신호 내부에 존재하는 리플(Ripple) 등의 고주파 노이즈를 제거하고, 다항식 피팅을 적용하여 데이터를 매끄럽게 정제합니다.

<img width="987" height="590" alt="D07_C0_R0_LMZC_Fitting" src="https://github.com/user-attachments/assets/344548af-9787-42b6-9549-4a50cc5da6ec" />

### 3. 소자 성능 지표 연산
* **`Phase shift - V.py` (위상 변화 연산)**
  * 피팅된 그래프의 최소점(Dip)을 기준으로, 인가된 바이어스 전압(Bias Voltage)에 따라 파장이 얼마나 이동(Shift)하는지 추적하여 위상 변화량을 계산합니다.

<img width="989" height="590" alt="D07_C0_R0_LMZC_Phase" src="https://github.com/user-attachments/assets/74cbb1c8-9cdb-4ef1-98b4-fc615ac42cac" />

* **`VpiL.py` ($V_\pi L$ 추출)**
  * 바이어스에 따른 위상 변화를 반파장 전압($V_\pi$)으로 환산하고, 소자의 길이($L$)를 곱하여 최종적인 전광 변조 효율 지표인 $V_\pi L$ 수치를 계산합니다.

<img width="989" height="590" alt="D07_C0_R0_LMZC_VpiL" src="https://github.com/user-attachments/assets/5f2617c1-50b5-404b-869d-b2d1ef6dbbb6" />

### 4. Wafer Map 과 Box Graph 자동 생성
* **`ER_Analysis,py` (Wafer Map, Box graph 데이터)**
  * 추출된 주요 수치 데이터(ER)를 `Wafer Map` 및 `Box Graph` 파일

<img width="698" height="654" alt="Map_D07_LMZC_20190715_ER" src="https://github.com/user-attachments/assets/bcfdc059-7823-4d33-adef-03bc0929266e" />

<img width="790" height="790" alt="Box_D07_LMZC_20190715_ER_Flattened" src="https://github.com/user-attachments/assets/9b1665b5-2bec-47fb-9969-4c5249594398" />

* **`IL_Analysis,py` (Wafer Map, Box graph 데이터)**
  * 추출된 주요 수치 데이터(IL)를 `Wafer Map` 및 `Box Graph` 파일

<img width="729" height="654" alt="Map_D07_LMZC_20190715_IL" src="https://github.com/user-attachments/assets/e326e389-0a04-4acd-8ef7-09a30112c107" />

<img width="790" height="790" alt="Box_D07_LMZC_20190715_IL" src="https://github.com/user-attachments/assets/9a246003-ef34-4431-a691-c1fecb7f8c77" />

* **`VpiL_Analysis,py` (Wafer Map, Box graph 데이터)**
  * 추출된 주요 수치 데이터(VpiL)를 `Wafer Map` 및 `Box Graph` 파일

<img width="704" height="645" alt="Map_D07_LMZC_20190715_VpiL_0V" src="https://github.com/user-attachments/assets/d3f860ed-76dd-44fb-bd93-2afafd4bcfdf" />

<img width="790" height="790" alt="Box_D07_LMZC_20190715_VpiL_0V" src="https://github.com/user-attachments/assets/1481388c-0f16-419b-8881-049a174d9c78" />

### 5. 시각화 병합 및 리포트 자동 생성
* **`combine_plot.py` (대시보드 이미지 병합)**
  * 개별 분석 과정을 거치며 생성된 여러 장의 그래프를 웨이퍼(Wafer) 및 날짜별로 묶어 **단 한 장의 요약 대시보드 이미지**로 병합합니다.

 <img width="2187" height="654" alt="Summary_WaferMap_D07_LMZC_20190715" src="https://github.com/user-attachments/assets/4051eff6-9de0-4185-b99d-5940eab6fc8e" />
 
<img width="2370" height="790" alt="Summary_BoxPlot_D07_LMZC_20190715" src="https://github.com/user-attachments/assets/9de893ca-1882-49ac-aaf7-7b962bc48d3f" />

* **`export_summary.py` (통합 리포트 출력)**
  * 추출된 주요 수치 데이터(IL, ER, $V_\pi L$)를 `csv` 및 `xlsx` 파일로 저장합니다. 엑셀 파일 내에는 **병합된 요약 이미지(PNG)를 클릭 한 번에 열 수 있는 하이퍼링크**가 매핑되어 직관적인 데이터 검증이 가능합니다.
