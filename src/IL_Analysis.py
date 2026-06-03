import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from data_parser import load_parsed

zip_path = "../dat/HY202103"
base_res_dir = "../res/png"
target_wafers = ['D07', 'D08', 'D23', 'D24']
IL_TARGETS = {'LMZO': -8.75, 'LMZC': -8.75}

# 1. WaferMap과 BoxPlot 최상위 경로 설정
wafer_map_dir = os.path.join(base_res_dir, "WaferMap")
box_plot_dir = os.path.join(base_res_dir, "BoxPlot")
os.makedirs(wafer_map_dir, exist_ok=True)
os.makedirs(box_plot_dir, exist_ok=True)

print("🚀 IL 추출 및 날짜별/Center vs Edge 통합 분석을 시작합니다...")

il_data_list = []
for d in load_parsed(zip_path, target_wafers):
    date_str = d.get('date', 'Unknown_Date')

    max_peak = -999.0
    for b in d['bias_data_list']:
        if b['bias'] is None: continue
        m = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        if np.any(m): max_peak = max(max_peak, np.max(b['il'][m]))

    if max_peak != -999.0:
        il_data_list.append(
            {'Wafer': d['wafer_id'], 'Band': d['band'], 'Date': date_str, 'Column': d['die_c'], 'Row': d['die_r'],
             'IL': max_peak})

df = pd.DataFrame(il_data_list).groupby(['Wafer', 'Band', 'Date', 'Column', 'Row'], as_index=False)['IL'].mean()
df['Radius'] = np.sqrt(df['Column'] ** 2 + df['Row'] ** 2)


# ==========================================================
# 2. 자정을 넘긴 측정 데이터(0603, 0604) 병합 처리
# ==========================================================
def merge_midnight_dates(date_val):
    date_str = str(date_val)
    if '0603' in date_str or '0604' in date_str:
        return '20190603'
    return date_str


df['Date'] = df['Date'].apply(merge_midnight_dates)
print("🕒 0603 및 0604 날짜 데이터를 '0603_0604_Combined'로 통합했습니다.")
# ==========================================================

filtered_df = pd.DataFrame()
for _, group in df.groupby(['Wafer', 'Band', 'Date']):
    m, s = group['IL'].mean(), group['IL'].std()
    filtered_df = pd.concat([filtered_df, group[(group['IL'] >= m - 3 * s) & (group['IL'] <= m + 3 * s)]])

max_rad = filtered_df['Radius'].max()
filtered_df['Region'] = np.where(filtered_df['Radius'] > max_rad * 0.75, 'Edge', 'Center')

# ==========================================================
# [통일된 디자인] Wafer Map 그리기
# ==========================================================
print("▶ 웨이퍼 및 날짜별 Wafer Map 생성 중...")
for b in filtered_df['Band'].unique():
    limits = {'min': np.floor(filtered_df[filtered_df['Band'] == b]['IL'].min()),
              'max': np.ceil(filtered_df[filtered_df['Band'] == b]['IL'].max())}

    for (w, date), grp in filtered_df[filtered_df['Band'] == b].groupby(['Wafer', 'Date']):
        if grp.empty: continue

        plt.figure(figsize=(9, 9))
        th = np.linspace(0, 2 * np.pi, 100)
        plt.plot((max_rad + 0.5) * np.cos(th), (max_rad + 0.5) * np.sin(th), color='gray', lw=2)
        plt.plot(max_rad * 0.75 * np.cos(th), max_rad * 0.75 * np.sin(th), color='red', ls='--', lw=2, alpha=0.6)

        sc = plt.scatter(grp['Column'], grp['Row'], c=grp['IL'], cmap='coolwarm_r', vmin=limits['min'],
                         vmax=limits['max'], s=500, edgecolor='black', alpha=0.9, zorder=5)

        for _, r in grp.iterrows():
            plt.text(r['Column'], r['Row'], f"{r['IL']:.1f}", ha='center', va='center',
                     fontsize=10, fontweight='bold', color='black', zorder=10)

        cb = plt.colorbar(sc, shrink=0.8)
        cb.set_label('IL [dB]', fontsize=14, fontweight='bold')
        cb.ax.tick_params(labelsize=12)
        for l in cb.ax.yaxis.get_ticklabels(): l.set_weight("bold")

        plt.title(f"Wafer Map: {w} / {b} (IL)\nDate: {date}", fontsize=18, fontweight='bold', pad=15)
        plt.axis('off')
        plt.gca().set_aspect('equal')

        # 저장 경로: WaferMap / 웨이퍼 / 날짜
        w_dir = os.path.join(wafer_map_dir, w, date)
        os.makedirs(w_dir, exist_ok=True)
        plt.savefig(os.path.join(w_dir, f"Map_{w}_{b}_{date}_IL.png"), bbox_inches='tight')
        plt.close()

# ==========================================================
# 3. [통일된 디자인] Box Plot 그리기 (개별 웨이퍼 단위)
# ==========================================================
print("▶ 웨이퍼 및 날짜별 Box Plot 생성 중...")
for (w, b, date), wbd_df in filtered_df.groupby(['Wafer', 'Band', 'Date']):
    if wbd_df.empty: continue

    plt.figure(figsize=(8, 8))  # 개별 웨이퍼 플롯 사이즈
    pos, data, lbl, clr = [], [], [], []

    c = wbd_df[wbd_df['Region'] == 'Center']['IL'].values
    e = wbd_df[wbd_df['Region'] == 'Edge']['IL'].values

    if len(c) > 0:
        pos.append(1)
        data.append(c)
        lbl.append(f"Center\nn={len(c)}")
        clr.append('#3498db')
    if len(e) > 0:
        pos.append(2)
        data.append(e)
        lbl.append(f"Edge\nn={len(e)}")
        clr.append('#e74c3c')

    if not data: continue

    tgt_il = IL_TARGETS.get(b, -8.75)

    # Y축 범위를 미리 계산하여 배경색 영역 지정에 사용
    all_data = np.concatenate(data)
    y_min = min(all_data.min(), tgt_il) - 2  # 데이터 최소값 또는 타겟 중 작은 값 기준 안전마진
    y_max = max(all_data.max(), tgt_il) + 2  # 데이터 최대값 또는 타겟 중 큰 값 기준 안전마진
    plt.ylim(y_min, y_max)

    # ------------------------------------------------------
    # 🌟 성능별 배경색(수평 영역) 지정
    # ------------------------------------------------------
    # 타겟(Target) 이상: 연한 초록색 (Good Region)
    plt.axhspan(tgt_il, y_max, facecolor='#e8f8f5', alpha=0.6, zorder=0, label='Good Region')

    # 타겟(Target) 미만: 연한 붉은/코랄 계열 (Poor Region) - 눈에 띄면서 부정적인 의미 전달
    plt.axhspan(y_min, tgt_il, facecolor='#fadbd8', alpha=0.6, zorder=0, label='Poor Region')
    # ------------------------------------------------------

    box = plt.boxplot(data, positions=pos, patch_artist=True, widths=0.5,
                      flierprops=dict(marker='d', markerfacecolor='black', markersize=6, alpha=0.6),
                      zorder=2)
    for p, c_hex in zip(box['boxes'], clr): p.set_facecolor(c_hex); p.set_alpha(0.7)

    # Jitter(산점도) 추가
    for p, d_arr in zip(pos, data):
        plt.scatter(np.random.normal(p, 0.05, len(d_arr)), d_arr, color='black', alpha=0.5, s=20, zorder=3)

    avg_il = wbd_df['IL'].mean()

    # 평균 및 타겟 라인
    plt.axhline(avg_il, color='blue', ls='--', lw=2.5, label=f'Avg: {avg_il:.2f} dB', zorder=4)
    plt.axhline(tgt_il, color='red', ls='-', lw=2.5, label=f'Target: {tgt_il:.2f} dB', zorder=4)

    plt.title(f"IL Analysis : {w} ({b})\nDate: {date}", fontsize=18, fontweight='bold', pad=15)
    plt.xticks(pos, lbl, fontsize=14, fontweight='bold')
    plt.yticks(fontsize=14, fontweight='bold')
    plt.ylabel('IL [dB]', fontsize=16, fontweight='bold')

    # 범례 설정
    plt.legend(loc='upper right', prop={'size': 11, 'weight': 'bold'})
    plt.grid(True, axis='y', ls=':', alpha=0.4, zorder=1)
    plt.xlim(0.5, max(pos) + 0.5)
    plt.tight_layout()

    # 저장 경로: BoxPlot / 웨이퍼 / 날짜
    box_dir = os.path.join(box_plot_dir, w, date)
    os.makedirs(box_dir, exist_ok=True)
    plt.savefig(os.path.join(box_dir, f"Box_{w}_{b}_{date}_IL.png"), bbox_inches='tight')
    plt.close()