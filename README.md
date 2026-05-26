# 📂 Wafer Data Analysis & Integrated Reporting System

> **XML 기반의 Wafer 측정 데이터를 파싱하고 정밀 분석(IL, ER, VpiL, Phase Shift)하여 시각화 및 통합 엑셀 리포트를 생성하는 자동화 시스템입니다.**

---

## 📁 디렉토리 구조 (Directory Structure)
정상적인 분석 실행을 위해 데이터와 스크립트가 아래의 구조를 유지해야 합니다.

```text
📁 pycharm-project-root/
│
├── 📁 dat/
│   └── 📄 HY202103.zip             # 원본 웨이퍼 XML 압축 데이터
│
├── 📁 src/
│   ├── 📄 data_parser.py           # XML 파싱 코어 모듈
│   ├── 📄 plot.py                  # 데이터 기반 기본 plot이미지 생성 스크립트
│   ├── 📄 flatting.py              # 평탄화 실시 생성 스크립트
│   ├── 📄 zoom.py                  # 줌 플롯 생성 스크립트
│   ├── 📄 Fitting.py               # 줌 플롯을 피팅하는 생성 스크립트
│   ├── 📄 Phase shift - V.py       # Phase shift 분석 생성 스크립트
│   ├── 📄 VpiL.py                  # VpiL 분석 및 통합 맵 생성 스크립트
│   ├── 📄 ER_Analysis.py           # ER 분석 및 통합 맵 생성 스크립트
│   ├── 📄 IL_Analysis.py           # IL 분석 및 통합 맵 생성 스크립트
│   ├── 📄 VpiL_Analysis.py         # VpiL 분석 및 통합 맵 생성 스크립트
│   ├── 📄 comnibe_plot.py          # Combing image
│   └── 📄 export_summary.py        # 하이퍼링크 리포트 생성 스크립트
│
└── 📁 res/                         # 프로그램 실행 시 자동 생성되는 결과물 폴더
    ├── 📁 csv/                     # 프로그램 실행 시 자동으로 csv 폴더가 생성되는 결과물 폴더
    └── 📁 png/                     # 프로그램 실행 시 자동으로 png 폴더가 생성되는 결과물 폴더     
        ├── 📄 Process_result.xlsx      # [통합 엑셀 리포트] (폴더 하이퍼링크 포함)
        ├── 📁 Analysis/                # [통합 분석 맵] (Wafer Map, Box Plot 모음)
        └── 📁 {Wafer_ID}/              # [개별 다이] 데이터 (예: D07)
            └── 📁 {Date_YYYYMMDD}/     # 측정 날짜별 폴더 (예: 20190531)
                └── 📁 HY202103_wafer_id_(C,R)_LION1_DCM_band/   # 개별 좌표별 플롯 이미지 모음 (Raw, Flat, Phase 등)