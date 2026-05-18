import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from data_parser import parse_wafer_data

# ==========================================================
# 1. 설정 (USER SETTING & CONFIGURATION)
# ==========================================================
zip_path = "../dat/HY202103.zip"
base_res_dir = "../res"
target_wafers = ['D07', 'D08', 'D23', 'D24']
L_length = 0.05  # phase shifter length [cm]
TARGET_VPIL = {'LMZO': 1.4, 'LMZC': 2.0}

# --- [통합 설정] 모든 분석 결과(맵, 박스플롯)가 모일 res/Analysis 폴더 생성 ---
global_analysis_dir = os.path.join(base_res_dir, "Analysis")
os.makedirs(global_analysis_dir, exist_ok=True)

summary_rows = []
count = 0

print("🚀 0V 기준 VpiL 통합 분석(Advanced)을 시작합니다...")


# ==========================================================
# 2. 보조 함수 (HELPER FUNCTION)
# ==========================================================
def q_sub(x, y):
    """valley 주변 3점으로 subpixel 위치 정밀 보정"""
    if len(x) < 3: return x[np.argmin(y)]
    idx = np.argmin(y)
    if idx == 0 or idx == len(x) - 1: return x[idx]
    c = np.polyfit(x[idx - 1:idx + 2], y[idx - 1:idx + 2], 2)
    return -c[1] / (2 * c[0]) if abs(c[0]) > 1e-12 else x[idx]


# ==========================================================
# 3. 데이터 파싱 및 VpiL 계산 (0V 기준)
# ==========================================================
for d in parse_wafer_data(zip_path, target_wafers):
    wafer, band, c, r = d['wafer_id'], d['band'], d['die_c'], d['die_r']
    radius = np.sqrt(c ** 2 + r ** 2)

    # [추가] 날짜 정보 가져오기
    date_str = d.get('date', 'Unknown_Date')

    # Baseline (Ref) Fitting
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(v_ref_wl) < 31: continue
    poly_func = np.poly1d(np.polyfit(v_ref_wl, savgol_filter(v_ref_il, 31, 3), 3))

    # 0V 데이터 확인
    z_data = next((b for b in d['bias_data_list'] if b['bias'] == 0.0), None)
    if not z_data: continue

    m0 = (z_data['wl'] >= d['wl_min']) & (z_data['wl'] <= d['wl_max'])
    w0, i0 = z_data['wl'][m0], z_data['il'][m0]
    flat0 = savgol_filter(i0, 31, 3) - poly_func(w0)
    v0, _ = find_peaks(-flat0, prominence=0.3, distance=20)
    if len(v0) < 2: continue

    fsr = np.mean(np.diff(w0[v0]))
    cwl = w0[v0[np.argmin(np.abs(w0[v0] - d['target_wl']))]]

    volts, p_pi = [], []
    sh = fsr / 2.5
    for b in d['bias_data_list']:
        if b['bias'] is None: continue
        w, i = b['wl'], b['il']
        mb = (w >= d['wl_min']) & (w <= d['wl_max'])
        wb, ib = w[mb], i[mb]

        mloc = (wb >= cwl - sh) & (wb <= cwl + sh)
        if np.sum(mloc) < 5: continue

        flat = savgol_filter(ib[mloc], 11, 3) - poly_func(wb[mloc])
        vwl = q_sub(wb[mloc], flat)
        volts.append(b['bias'])
        p_pi.append(2.0 * (vwl - cwl) / fsr)

    if len(volts) < 5: continue
    volts, p_pi = np.array(volts), np.array(p_pi)

    # 0V 기준 VpiL 추출
    fit = np.poly1d(np.polyfit(volts, p_pi, 2))
    derivative = np.polyder(fit)

    slope_at_0 = np.abs(derivative(0.0))
    slope_at_0 = max(slope_at_0, 1e-5)
    vpil_0V = L_length / slope_at_0

    if not (0.1 <= vpil_0V <= 10.0): continue

    # DataFrame에 날짜(Date)도 함께 저장
    summary_rows.append({
        'Wafer': wafer, 'Band': band, 'Date': date_str, 'Column': c, 'Row': r,
        'Radius': radius, 'VpiL_0V': vpil_0V
    })

    # 트렌드 그래프 그리기
    plt.figure(figsize=(8, 6))
    vpil_curve = L_length / np.maximum(np.abs(derivative(volts)), 1e-5)
    plt.plot(volts, vpil_curve, 's-', lw=2, color='gray', label="VpiL Curve")
    plt.plot(0.0, vpil_0V, 'r*', markersize=15, label=f'Value @ 0V = {vpil_0V:.3f}')
    plt.axhline(vpil_0V, color='red', ls=':', alpha=0.5)
    plt.axvline(0.0, color='red', ls=':', alpha=0.5)
    plt.title(f"{wafer} {band} / Coord: ({c}, {r}) / VπL at 0V", fontweight='bold')
    plt.xlabel("Voltage (V)")
    plt.ylabel("Vpi*L (V*cm)")
    plt.grid(True)
    plt.legend()

    # --- 개별 좌표 그래프는 res/Wafer/날짜/좌표/ 구조로 유지하여 저장 ---
    coord_folder = f"C{c}_R{r}"
    w_dir = os.path.join(base_res_dir, wafer, date_str, coord_folder)
    os.makedirs(w_dir, exist_ok=True)

    save_filename = f"{wafer}_C{c}_R{r}_{band}_VpiL.png"
    plt.savefig(os.path.join(w_dir, save_filename))
    plt.close()

    count += 1
    if count % 100 == 0:
        print(f"현재 {count}개 Die 파싱 및 0V VpiL 분석 완료...")

# ==========================================================
# 4. 데이터 정리 및 필터링
# ==========================================================
if not summary_rows:
    print("❌ 유효한 데이터를 찾지 못했습니다.")
    exit()

df = pd.DataFrame(summary_rows)
filtered_df = pd.DataFrame()

# Groupby 데이터 가집계
df_grouped = df.groupby(['Wafer', 'Band', 'Column', 'Row', 'Radius'], as_index=False)['VpiL_0V'].mean()

for (wafer, band), group in df_grouped.groupby(['Wafer', 'Band']):
    if len(group) > 5:
        m, s = group['VpiL_0V'].mean(), group['VpiL_0V'].std()
        valid_group = group[(group['VpiL_0V'] >= m - 3 * s) & (group['VpiL_0V'] <= m + 3 * s)]
        filtered_df = pd.concat([filtered_df, valid_group])
    else:
        filtered_df = pd.concat([filtered_df, group])

max_r = filtered_df['Radius'].max()
edge_limit = max_r * 0.75
filtered_df['Region'] = np.where(filtered_df['Radius'] > edge_limit, 'Edge', 'Center')

print(f"\n✅ 데이터 정리 완료! (총 {len(filtered_df)}개 유효 다이)")

# ==========================================================
# 5. 통합 Wafer Map 시각화 (통합 Analysis 폴더에 저장)
# ==========================================================
band_limits = {}
for b in filtered_df['Band'].unique():
    b_data = filtered_df[filtered_df['Band'] == b]['VpiL_0V']
    band_limits[b] = {'min': b_data.min() - 0.05, 'max': b_data.max() + 0.05}

for (wafer, band), group in filtered_df.groupby(['Wafer', 'Band']):
    plt.figure(figsize=(9, 9))
    theta = np.linspace(0, 2 * np.pi, 100)
    plt.plot((max_r + 0.5) * np.cos(theta), (max_r + 0.5) * np.sin(theta), color='gray', lw=2)
    plt.plot(edge_limit * np.cos(theta), edge_limit * np.sin(theta), 'r--', lw=2, alpha=0.6,
             label='Center/Edge Boundary')

    v_min, v_max = band_limits[band]['min'], band_limits[band]['max']

    scatter = plt.scatter(group['Column'], group['Row'], c=group['VpiL_0V'], cmap='coolwarm',
                          vmin=v_min, vmax=v_max, s=600, edgecolor='black', alpha=0.9, zorder=5)

    for _, row in group.iterrows():
        plt.text(row['Column'], row['Row'], f"{row['VpiL_0V']:.2f}",
                 ha='center', va='center', fontsize=10, weight='bold', color='black', zorder=10)

    cbar = plt.colorbar(scatter, shrink=0.8)
    cbar.set_label('Vpi*L @ 0V [V*cm]', fontsize=14, fontweight='bold')

    plt.title(f"Wafer Map: {wafer} / {band}\nVpiL at 0V ({v_min:.2f} ~ {v_max:.2f} V*cm)", fontsize=18,
              fontweight='bold', pad=15)
    plt.xlabel("Die Column (X)", fontsize=16, fontweight='bold')
    plt.ylabel("Die Row (Y)", fontsize=16, fontweight='bold')
    plt.gca().set_aspect('equal')
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3, linestyle=':')

    # --- 웨이퍼 맵 저장 경로를 global_analysis_dir (../res/Analysis) 로 통일 ---
    plt.savefig(os.path.join(global_analysis_dir, f"Map_{wafer}_{band}_VpiL_0V.png"), bbox_inches='tight')
    plt.close()

# ==========================================================
# 6. Advanced Box Plot (통합: Center vs Edge) (통합 Analysis 폴더에 저장)
# ==========================================================
# 에러 해결: 누락되었던 flierprops 변수 정의 추가
flierprops = dict(marker='d', markerfacecolor='black', markersize=6, alpha=0.6)

for band in filtered_df['Band'].unique():
    band_df = filtered_df[filtered_df['Band'] == band]
    wafer_list = sorted(band_df['Wafer'].unique())
    current_target = TARGET_VPIL.get(band, 1.5)

    plt.figure(figsize=(14, 8))
    positions, plot_data, labels, colors = [], [], [], []

    for i, wafer in enumerate(wafer_list):
        w_df = band_df[band_df['Wafer'] == wafer]
        c_data = w_df[w_df['Region'] == 'Center']['VpiL_0V'].values
        e_data = w_df[w_df['Region'] == 'Edge']['VpiL_0V'].values

        if len(c_data) > 0:
            plot_data.append(c_data)
            positions.append(i * 3 + 1)
            labels.append(f"{wafer}\n(Center)\nn={len(c_data)}")
            colors.append('#3498db')
        if len(e_data) > 0:
            plot_data.append(e_data)
            positions.append(i * 3 + 2)
            labels.append(f"{wafer}\n(Edge)\nn={len(e_data)}")
            colors.append('#e74c3c')

    if not plot_data: continue

    box_reg = plt.boxplot(plot_data, positions=positions, tick_labels=labels, patch_artist=True, flierprops=flierprops)
    for patch, color in zip(box_reg['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    for pos, data in zip(positions, plot_data):
        x_jitter = np.random.normal(pos, 0.05, size=len(data))
        plt.scatter(x_jitter, data, color='black', alpha=0.5, s=20, zorder=3)

    plt.axhline(current_target, color='red', ls='-', linewidth=2.5, label=f'Target ({current_target} V*cm)')

    plt.title(f"Advanced Box Plot (Center vs Edge): {band} @ 0V", fontsize=18, fontweight='bold', pad=15)
    plt.ylabel("Vpi*L @ 0V [V*cm]", fontsize=16, fontweight='bold', labelpad=10)
    plt.legend(loc='upper right', prop={'size': 13, 'weight': 'bold'})
    plt.grid(True, axis='y', alpha=0.5, linestyle=':')
    plt.xlim(0, max(positions) + 1)
    plt.tight_layout()

    # --- 박스 플롯 저장 경로를 global_analysis_dir (../res/Analysis) 로 통일 ---
    plt.savefig(os.path.join(global_analysis_dir, f"Box_{band}_VpiL_0V.png"), bbox_inches='tight')
    plt.close()

print("✅ 모든 통합 분석(Advanced 0V) 및 이미지 저장이 완료되었습니다!")