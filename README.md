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
# 1. Introduction
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


### ▶️ How It Works

1. Extract files named `HY202103` from the customer-provided dataset
2. Process raw XML data through a series of analysis modules
3. Export the final results as `.csv` and `.xlsx` reports
---
# 3. ⚙️ Key Features


### 1) Data Extraction & Visualization Preparation

- **`ref_poly.py`** — Removes noise from REF signals and establishes a stable baseline for analysis
- **`data_parser.py`** — Parses target band (LMZC / LMZO) spectrum data from raw XML files
- **`plot.py`** — Generates baseline wavelength-transmission spectrum plots from parsed raw data


### 2) Signal Correction & Target Region Extraction

- **`flatting.py`** — Flattens the signal baseline by correcting offset errors between Reference and MZM devices
- **`zoom.py`** — Zooms into key analysis wavelength ranges per band (LMZC: 1550 nm / LMZO: 1310 nm)
- **`Fitting.py`** — Removes high-frequency noise (ripple) and applies polynomial fitting for smooth data refinement


### 3) Device Performance Metric Calculation

- **`Phase shift - V.py`** — Tracks wavelength shifts according to applied bias voltage based on dip positions in fitted graphs
- **`VpiL.py`** — Calculates VπL (electro-optic modulation efficiency) by converting phase shifts into half-wave voltage (Vπ) and multiplying by device length (L)


### 4) Wafer Map & Box Plot Auto-Generation

- **`ER_Analysis.py`** — Generates Wafer Map and Box Graph for Extinction Ratio (ER)
- **`IL_Analysis.py`** — Generates Wafer Map and Box Graph for Insertion Loss (IL)
- **`VpiL_Analysis.py`** — Generates Wafer Map and Box Graph for VpiL


### 5) Visualization Merging & Report Auto-Generation

- **`combine_plot.py`** — Merges individual analysis graphs into a single summary dashboard image per wafer and measurement date
- **`export_summary.py`** — Exports final IL / ER / VπL data as `.csv` and `.xlsx` files, with hyperlinks in Excel mapped to merged summary images for intuitive one-click data verification
------
# 4. 📁 Directory Structure

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
# 5. Install and Run

### Installation

```bash
pip install -r requirements.txt
```

### How to Run

1. Place the raw XML data folder you want to analyze into the `dat/` directory
2. Execute the pipeline

```bash
python run.py
```

3. Select analysis options
   - Target **Wafer** and **Die** (row & column)
   - Figure options : `Show Figure` / `Save Figure` / `Save CSV`
4. Results are automatically saved in the `res/` directory
---
# 6. Input & Output Examples

---

# 7. ⚙️ Data Analysis Pipeline

When `run.py` is executed, a total of 9 core modules operate 
sequentially to process the data.

### 1. Data Extraction & Visualization Preparation

- **`data_parser.py`** (Data Parsing)
  - Loads target band (LMZC, LMZO) spectrum data required 
    for analysis from the raw XML data files.
- **`plot.py`** (Raw Data Plot)
  - Generates basic wavelength-transmission spectrum plots 
    based on the parsed raw data.

### 2. Signal Correction & Target Region Extraction

- **`flatting.py`** (Signal Flattening)
  - Corrects offset errors between the Reference device and 
    MZM device to flatten the signal baseline.
- **`zoom.py`** (Target Wavelength Zoom-in)
  - Zooms into key analysis wavelength ranges according to 
    each band's characteristics. 
    (LMZC: 1550 nm / LMZO: 1310 nm)
- **`Fitting.py`** (Noise Filtering & Fitting)
  - Removes high-frequency noise such as ripple from the 
    measured signal and applies polynomial fitting to 
    smooth and refine the data.

### 3. Device Performance Metric Calculation

- **`Phase shift - V.py`** (Phase Shift Calculation)
  - Tracks how much the wavelength shifts according to the 
    applied bias voltage based on the dip positions in the 
    fitted graph, and calculates the phase shift.
- **`VpiL.py`** (VπL Extraction)
  - Converts the bias-dependent phase shift into half-wave 
    voltage (Vπ) and multiplies by the device length (L) to 
    calculate the final electro-optic modulation efficiency 
    index, VπL.

### 4. Wafer Map & Box Graph Auto-Generation

- **`ER_Analysis.py`** (Wafer Map & Box Graph)
  - Generates `Wafer Map` and `Box Graph` files from the 
    extracted ER data.
- **`IL_Analysis.py`** (Wafer Map & Box Graph)
  - Generates `Wafer Map` and `Box Graph` files from the 
    extracted IL data.
- **`VpiL_Analysis.py`** (Wafer Map & Box Graph)
  - Generates `Wafer Map` and `Box Graph` files from the 
    extracted VpiL data.

### 5. Visualization Merging & Report Auto-Generation

- **`combine_plot.py`** (Dashboard Image Merging)
  - Merges multiple graphs generated throughout the analysis 
    into a single summary dashboard image, grouped by 
    wafer and measurement date.
- **`export_summary.py`** (Consolidated Report Export)
  - Saves the extracted key metric data (IL, ER, VπL) as 
    `.csv` and `.xlsx` files. The Excel file includes 
    hyperlinks mapped to merged summary images (PNG), 
    enabling intuitive one-click data verification.