# Shared analysis module for MZM measurement data.
# Heavy computation (parsing / fitting / metric extraction) lives here.
# The Jupyter notebook only imports these functions and displays the results inline.
# Folder path and wafer list are passed as arguments, so no code change is needed when data changes.

import os
import re
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from data_parser import parse_wafer_data
from ref_poly import q_sub, ref_poly

VPIL_MIN, VPIL_MAX = 0.1, 10.0   # valid VpiL range (V*cm)
DEFAULT_L_UM = 500               # fallback arm length when not found (um)


def _show_fig(fig):
    # Display the figure inline and close it. Does not depend on the matplotlib
    # backend, so it renders reliably in both VS Code and Jupyter.
    try:
        from IPython.display import display
        display(fig)
    except Exception:
        pass
    plt.close(fig)


# ============================================================
# 1. Data loading / listing (for dropdowns)
# ============================================================
def load(folder, wafers):
    # folder path + wafer list -> list of per-die data
    return list(parse_wafer_data(folder, wafers))


def build_length_map(folder, wafers):
    # Read each die's arm length (um) from the modulator name in the XML.
    # Name example: 'MZMCTE_LULAB_450_500' -> trailing 500 = length (um)
    out = {}
    for root_dir, _, files in os.walk(folder):
        for fname in files:
            if not fname.lower().endswith('.xml'):
                continue
            fp = os.path.join(root_dir, fname)
            if not any(w in fp for w in wafers):
                continue
            try:
                root = ET.parse(fp).getroot()
            except Exception:
                continue
            info = root.find('.//TestSiteInfo')
            if info is None:
                continue
            ts = info.get('TestSite', '').upper()
            band = 'LMZO' if 'LMZO' in ts else ('LMZC' if 'LMZC' in ts else None)
            if band is None:
                continue
            die_c = int(info.get('DieRow', 0)) if info.get('DieRow') else 0
            die_r = int(info.get('DieColumn', 0)) if info.get('DieColumn') else 0
            wafer = next((w for w in wafers if w in fp), None)
            if wafer is None:
                continue
            for mod in root.iter('Modulator'):
                nm = mod.attrib.get('Name', '')
                if 'ALIGN' in nm.upper():
                    continue
                m = re.search(r'_LULAB_\d+_(\d+)', nm)
                if m:
                    out[(wafer, die_c, die_r, band)] = int(m.group(1))
                break
    return out


def list_wafers(data):
    return sorted({d['wafer_id'] for d in data})


def list_dates(data, wafer):
    return sorted({d['date'] for d in data if d['wafer_id'] == wafer})


def list_dies(data, wafer, date):
    # (band, column, row) list for that wafer/date
    items = {(d['band'], d['die_c'], d['die_r'])
             for d in data if d['wafer_id'] == wafer and d['date'] == date}
    return sorted(items)


def get_die(data, wafer, date, band, c, r):
    # Find the data for a single selected die
    for d in data:
        if (d['wafer_id'], d['date'], d['band'], d['die_c'], d['die_r']) == (wafer, date, band, c, r):
            return d
    return None


# ============================================================
# 2. Metric extraction (computation)
# ============================================================
def extract_vpil(d, L_cm):
    # V_pi*L at 0V for a single die. Returns (vpil_0V, volts, vpil_curve) or None
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    ref_wl, ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(ref_wl) < 31:
        return None
    poly = ref_poly(ref_wl, ref_il, smooth=True)            # flattening baseline

    z = next((b for b in d['bias_data_list']
              if b['bias'] is not None and abs(b['bias']) < 1e-3), None)  # 0V measurement
    if not z:
        return None
    m0 = (z['wl'] >= d['wl_min']) & (z['wl'] <= d['wl_max'])
    w0, i0 = z['wl'][m0], z['il'][m0]
    flat0 = savgol_filter(i0, 31, 3) - poly(w0)             # flattened 0V
    v0, _ = find_peaks(-flat0, prominence=0.3, distance=20) # deep valleys (nulls)
    if len(v0) < 2:
        return None
    fsr = np.mean(np.diff(w0[v0]))                          # mean null spacing = FSR
    cwl = w0[v0[np.argmin(np.abs(w0[v0] - d['target_wl']))]]  # reference null

    volts, p_pi = [], []
    sh = fsr / 2.5
    for b in d['bias_data_list']:
        if b['bias'] is None:
            continue
        mb = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        wb, ib = b['wl'][mb], b['il'][mb]
        mloc = (wb >= cwl - sh) & (wb <= cwl + sh)          # around the null only
        if np.sum(mloc) < 5:
            continue
        flat = savgol_filter(ib[mloc], 11, 3) - poly(wb[mloc])
        volts.append(b['bias'])
        p_pi.append(2.0 * (q_sub(wb[mloc], flat) - cwl) / fsr)  # phase (pi units)

    if len(volts) < 5:
        return None
    volts, p_pi = np.array(volts), np.array(p_pi)
    deriv = np.polyder(np.poly1d(np.polyfit(volts, p_pi, 2)))   # phase-voltage slope
    vpil_0V = L_cm / max(abs(deriv(0.0)), 1e-5)             # V_pi*L = length / slope
    if not (VPIL_MIN <= vpil_0V <= VPIL_MAX):
        return None
    vpil_curve = L_cm / np.maximum(np.abs(deriv(volts)), 1e-5)
    return vpil_0V, volts, vpil_curve


def extract_phase(d):
    # Null shift vs voltage as phase in radians. Returns (volts, phase_rad, fsr) or None
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    ref_wl, ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(ref_wl) < 31:
        return None
    poly = ref_poly(ref_wl, ref_il, smooth=True)
    z = next((b for b in d['bias_data_list']
              if b['bias'] is not None and abs(b['bias']) < 1e-3), None)
    if not z:
        return None
    m0 = (z['wl'] >= d['wl_min']) & (z['wl'] <= d['wl_max'])
    w0, i0 = z['wl'][m0], z['il'][m0]
    flat0 = savgol_filter(i0, 31, 3) - poly(w0)
    v0, _ = find_peaks(-flat0, prominence=0.3, distance=20)
    if len(v0) < 2:
        return None
    fsr = np.mean(np.diff(w0[v0]))
    cwl = w0[v0[np.argmin(np.abs(w0[v0] - d['target_wl']))]]
    sh = fsr / 2.5
    pts = []
    for b in d['bias_data_list']:
        if b['bias'] is None:
            continue
        mb = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        wb, ib = b['wl'][mb], b['il'][mb]
        mloc = (wb >= cwl - sh) & (wb <= cwl + sh)
        if np.sum(mloc) < 5:
            continue
        flat = savgol_filter(ib[mloc], 11, 3) - poly(wb[mloc])
        vwl = q_sub(wb[mloc], flat)
        # phase (radians): one full FSR shift = 2*pi
        pts.append((b['bias'], 2.0 * np.pi * (vwl - cwl) / fsr))
    if len(pts) < 3:
        return None
    pts.sort()
    V = np.array([p[0] for p in pts])
    PH = np.array([p[1] for p in pts])
    return V, PH, fsr


def extract_il(d):
    # Insertion loss (IL) = max passband transmission over all biases (lowest-loss point)
    mx = -np.inf
    for b in d['bias_data_list']:
        if b['bias'] is None:
            continue
        m = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        if np.any(m):
            mx = max(mx, float(np.max(b['il'][m])))
    return mx if mx > -np.inf else None


def extract_er(d):
    # Extinction ratio (ER) = max over biases of (99th - 1st percentile) after flattening
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    ref_wl, ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(ref_wl) < 4:
        return None
    poly = ref_poly(ref_wl, ref_il, smooth=False)
    best = 0.0
    for b in d['bias_data_list']:
        mb = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        wl, il = b['wl'][mb], b['il'][mb]
        if len(wl) == 0:
            continue
        flat = il - poly(wl)
        pk, _ = find_peaks(flat, prominence=3.0, distance=30)
        if len(pk) >= 2:                                    # correct peak-envelope tilt
            flat = flat - np.poly1d(np.polyfit(wl[pk], flat[pk], 1))(wl)
        best = max(best, float(np.percentile(flat, 99) - np.percentile(flat, 1)))
    return best if best > 0 else None


def metric_value(d, metric, length_map=None):
    # Return a single scalar value by metric name (for wafer maps / box plots)
    if metric == 'vpil':
        L_cm = (length_map or {}).get(
            (d['wafer_id'], d['die_c'], d['die_r'], d['band']), DEFAULT_L_UM) * 1e-4
        res = extract_vpil(d, L_cm)
        return res[0] if res else None
    if metric == 'il':
        return extract_il(d)
    if metric == 'er':
        return extract_er(d)
    return None


METRIC_LABEL = {'vpil': 'Vpi*L (V*cm)', 'il': 'IL (dB)', 'er': 'ER (dB)'}


# ============================================================
# 3. Visualization (draw and show inline in the notebook)
# ============================================================
def plot_die_vpil(data, length_map, wafer, date, band, c, r):
    # VpiL curve for a single selected die
    d = get_die(data, wafer, date, band, c, r)
    fig, ax = plt.subplots(figsize=(8, 5))
    res = extract_vpil(d, (length_map or {}).get((wafer, c, r, band), DEFAULT_L_UM) * 1e-4) if d else None
    if not res:
        ax.text(0.5, 0.5, 'No valid VpiL data', ha='center', va='center')
        _show_fig(fig)
        return
    vpil, volts, curve = res
    ax.plot(volts, curve, 's-', color='gray', label='VpiL curve')
    ax.plot(0.0, vpil, 'r*', markersize=16, label=f'@0V = {vpil:.3f} V*cm')
    ax.axhline(vpil, color='red', ls=':', alpha=0.5)
    ax.set_xlabel('Voltage (V)'); ax.set_ylabel('Vpi*L (V*cm)')
    ax.set_title(f'{wafer} {band} ({c},{r})  |  VpiL@0V = {vpil:.3f} V*cm')
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    _show_fig(fig)


def plot_die_phase(data, wafer, date, band, c, r):
    # Phase shift (radians) of the selected die, with a pi reference line
    d = get_die(data, wafer, date, band, c, r)
    fig, ax = plt.subplots(figsize=(8, 5))
    res = extract_phase(d) if d else None
    if not res:
        ax.text(0.5, 0.5, 'No valid phase data', ha='center', va='center')
        _show_fig(fig)
        return
    V, PH, fsr = res
    ax.plot(V, PH, 'o-', color='steelblue', label='delta phi (rad)')
    ax.axhline(np.pi, color='red', ls=':', alpha=0.6)      # pi = V_pi reached
    ax.text(V.max(), np.pi, '  pi', color='red', va='center')
    ax.axhline(0, color='gray', lw=0.5)
    ax.set_xlabel('Voltage (V)'); ax.set_ylabel('Phase shift (rad)')
    ax.set_title(f'{wafer} {band} ({c},{r})  |  FSR = {fsr:.2f} nm')
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    _show_fig(fig)


def plot_die_plot(data, length_map, wafer, date, band, c, r):
    # Raw transmission spectra of a single selected die
    d = get_die(data, wafer, date, band, c, r)
    fig, ax = plt.subplots(figsize=(8, 5))
    if d is None:
        ax.text(0.5, 0.5, 'No valid data', ha='center', va='center')
        _show_fig(fig)
        return

    for b in d['bias_data_list']:
        ax.plot(b['wl'], b['il'], label=b['label'], linewidth=2)

    ax.plot(d['ref_data']['wl'], d['ref_data']['il'], label=d['ref_data']['label'],
            linewidth=2, color='black', alpha=0.8, linestyle='--')

    ax.set_title(f"Wafer: {wafer} / Coord: ({c}, {r}) / Band: {band}", fontsize=12, fontweight='bold', pad=10)
    ax.set_xlabel("Wavelength (nm)", fontsize=11, fontweight='bold')
    ax.set_ylabel("Transmission (dB)", fontsize=11, fontweight='bold')
    ax.set_ylim(-65, 5)
    ax.legend(loc='best', prop={'size': 9, 'weight': 'bold'})
    ax.grid(True, linestyle='--', alpha=0.6, linewidth=1)

    for spine in ax.spines.values():
        spine.set_linewidth(1.5)

    fig.tight_layout()
    _show_fig(fig)


def plot_die_fitting(data, length_map, wafer, date, band, c, r):
    # Ripple-removed and fitted spectra of a single die (zoomed)
    d = get_die(data, wafer, date, band, c, r)
    fig, ax = plt.subplots(figsize=(8, 5))
    if d is None:
        ax.text(0.5, 0.5, 'No valid data', ha='center', va='center')
        _show_fig(fig)
        return

    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]

    if len(v_ref_wl) < 31:
        ax.text(0.5, 0.5, 'Not enough data (N < 31)', ha='center', va='center')
        _show_fig(fig)
        return

    # Polynomial fit for flattening, plus R^2
    sm_ref = savgol_filter(v_ref_il, 31, 3)
    poly = np.poly1d(np.polyfit(v_ref_wl, sm_ref, 3))
    y_fitted = poly(v_ref_wl)

    ss_res = np.sum((sm_ref - y_fitted) ** 2)
    ss_tot = np.sum((sm_ref - np.mean(sm_ref)) ** 2)
    r_squared = 1.0 if ss_tot == 0 else 1 - (ss_res / ss_tot)

    # Peak search for the zoom range (use -2V, or the first bias)
    z_min, z_max = d['wl_min'], d['wl_max']
    tgt_bias = next((b for b in d['bias_data_list'] if b['bias'] == -2.0),
                    d['bias_data_list'][0] if d['bias_data_list'] else None)

    if tgt_bias:
        m_t = (tgt_bias['wl'] >= d['wl_min']) & (tgt_bias['wl'] <= d['wl_max'])
        w_t, i_t = tgt_bias['wl'][m_t], tgt_bias['il'][m_t]

        if len(w_t) >= 31:
            flat_t = savgol_filter(i_t, 31, 3) - poly(w_t)
            peaks, _ = find_peaks(flat_t, prominence=3.0, distance=30)

            if len(peaks) >= 2:
                centers = (w_t[peaks[:-1]] + w_t[peaks[1:]]) / 2.0
                band_str = str(d.get('band', '')).upper()
                target_wl = d.get('target_wl', 1310.0) if 'O' in band_str else d.get('target_wl', 1550.0)
                idx = np.argmin(np.abs(centers - target_wl))

                if idx + 1 < len(peaks):
                    z_min, z_max = w_t[peaks[idx]] - 0.5, w_t[peaks[idx + 1]] + 0.5

    # Flatten each bias, correct the peak-envelope tilt, then plot
    for b in d['bias_data_list']:
        m_b = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        v_wl, v_il = b['wl'][m_b], b['il'][m_b]
        if len(v_wl) < 31:
            continue

        flat_il = savgol_filter(v_il, 31, 3) - poly(v_wl)
        peaks, _ = find_peaks(flat_il, prominence=3.0, distance=30)

        if len(peaks) >= 2:
            flat_il -= np.poly1d(np.polyfit(v_wl[peaks], flat_il[peaks], 1))(v_wl)

        ax.plot(v_wl, flat_il, label=b['label'], alpha=0.8, linewidth=2)

    # Reference line
    ax.plot(v_ref_wl, sm_ref - y_fitted, label=f'REF (R^2={r_squared:.4f})',
            color='black', lw=2, linestyle='--', zorder=10)

    ax.set_title(f"Wafer: {wafer} / Coord: ({c}, {r}) / Band: {band}\nSmoothed, Flattened & Zoomed", fontsize=12,
                 fontweight='bold', pad=10)
    ax.set_xlabel('Wavelength (nm)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Transmission (dB)', fontsize=11, fontweight='bold')
    ax.axhline(0, color='gray', ls='--', alpha=0.6, linewidth=1.5)
    ax.set_xlim(z_min, z_max)
    ax.legend(loc='best', prop={'size': 9, 'weight': 'bold'})
    ax.grid(True, linestyle='--', alpha=0.6, linewidth=1)

    for spine in ax.spines.values():
        spine.set_linewidth(1.5)

    fig.tight_layout()
    _show_fig(fig)


# Per-metric style (same as the original analysis scripts)
_MAP_CFG = {
    'vpil': dict(cmap='coolwarm',   cbar='Vpi*L @ 0V [V*cm]', maptag='VpiL',
                 boxtag='VpiL', unit='V*cm', target={'LMZO': 1.4, 'LMZC': 2.0}, good_above=False),
    'il':   dict(cmap='coolwarm_r', cbar='IL [dB]', maptag='IL',
                 boxtag='IL', unit='dB', target=-8.75, good_above=True),
    'er':   dict(cmap='coolwarm_r', cbar='Extinction Ratio [dB]', maptag='Flattened ER',
                 boxtag='ER', unit='dB', target=20.0, good_above=True),
}


def _merge_date(date):
    # Treat measurements that ran past midnight (0603 -> 0604) as the same day (0603)
    s = str(date)
    return '20190603' if ('0603' in s or '0604' in s) else s


def _metric_df(data, length_map, metric):
    # Same preprocessing as the original scripts:
    # duplicate-coord average -> date merge -> 3-sigma (if group > 5) -> Center/Edge
    rows = []
    for d in data:
        v = metric_value(d, metric, length_map)
        if v is None:
            continue
        rows.append({'Wafer': d['wafer_id'], 'Band': d['band'], 'Date': _merge_date(d['date']),
                     'Column': d['die_c'], 'Row': d['die_r'],
                     'Radius': np.hypot(d['die_c'], d['die_r']), 'val': v})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.groupby(['Wafer', 'Band', 'Date', 'Column', 'Row', 'Radius'], as_index=False)['val'].mean()
    keep = []
    for _, g in df.groupby(['Wafer', 'Band', 'Date']):
        if len(g) > 5:
            mu, sd = g['val'].mean(), g['val'].std()
            g = g[(g['val'] >= mu - 3 * sd) & (g['val'] <= mu + 3 * sd)]
        keep.append(g)
    df = pd.concat(keep, ignore_index=True)
    df['Region'] = np.where(df['Radius'] > df['Radius'].max() * 0.75, 'Edge', 'Center')
    return df


def plot_wafer_map(data, length_map, wafer, date, band, metric='vpil', selected_c=None, selected_r=None):
    # Same style as the wafer maps in the res folder
    cfg = _MAP_CFG[metric]
    df = _metric_df(data, length_map, metric)
    qdate = _merge_date(date)
    fig, ax = plt.subplots(figsize=(10, 10))
    grp = df[(df['Wafer'] == wafer) & (df['Band'] == band) & (df['Date'] == qdate)] if not df.empty else df
    if df.empty or grp.empty:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center')
        _show_fig(fig)
        return

    # Color range (per band) + map size (per overall radius)
    bvals = df[df['Band'] == band]['val']
    if metric == 'vpil':
        v_min, v_max = bvals.min() - 0.05, bvals.max() + 0.05
    else:
        v_min, v_max = np.floor(bvals.min()), np.ceil(bvals.max())
    max_r = df['Radius'].max()
    edge_limit = max_r * 0.75
    map_limit = np.ceil(max_r) + 0.5

    th = np.linspace(0, 2 * np.pi, 100)
    ax.plot((max_r + 0.5) * np.cos(th), (max_r + 0.5) * np.sin(th), color='#555555', lw=2, zorder=1)
    ax.plot(edge_limit * np.cos(th), edge_limit * np.sin(th), color='#FF8888', ls='--', lw=2, alpha=0.7, zorder=1)
    ax.set_aspect('equal')
    ax.set_xlim(-map_limit, map_limit)
    ax.set_ylim(-map_limit, map_limit)
    ticks = np.arange(-np.floor(map_limit), np.ceil(map_limit) + 1, 1)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.grid(True, which='major', color='#DDDDDD', linestyle='--', linewidth=1, zorder=2)

    for lb in ax.get_xticklabels() + ax.get_yticklabels():
        lb.set_fontweight('bold')
    ax.set_xlabel('Column (X Coordinate)', fontsize=14, fontweight='bold', labelpad=10)
    ax.set_ylabel('Row (Y Coordinate)', fontsize=14, fontweight='bold', labelpad=10)

    # Draw all die markers
    sc = ax.scatter(grp['Column'], grp['Row'], c=grp['val'], cmap=cfg['cmap'],
                    vmin=v_min, vmax=v_max, s=500, edgecolor='black', alpha=0.9, zorder=5)

    for _, row in grp.iterrows():
        ax.text(row['Column'], row['Row'], f"{row['val']:.2f}", ha='center', va='center',
                fontsize=9, weight='bold', color='black', zorder=6)

    # Highlight the selected die with a thick hot-pink ring
    if selected_c is not None and selected_r is not None:
        ax.scatter(selected_c, selected_r, s=750, facecolors='none',
                   edgecolors='#FF007F', linewidths=4, zorder=10, label='Selected Die')

    cb = plt.colorbar(sc, ax=ax, shrink=0.8, pad=0.03)
    cb.set_label(cfg['cbar'], fontsize=13, fontweight='bold')
    ax.set_title(f"Wafer Map: {wafer} / {band} ({cfg['maptag']})\nDate: {qdate}",
                 fontsize=17, fontweight='bold', pad=20)
    _show_fig(fig)


def plot_box(data, length_map, wafer, date, band, metric='vpil', selected_c=None, selected_r=None):
    # Same style as the Center vs Edge box plots in the res folder
    cfg = _MAP_CFG[metric]
    df = _metric_df(data, length_map, metric)
    qdate = _merge_date(date)

    # Legend sits outside on the right, so a slightly wider ratio (9, 8) stays balanced
    fig, ax = plt.subplots(figsize=(9, 8))

    grp = df[(df['Wafer'] == wafer) & (df['Band'] == band) & (df['Date'] == qdate)] if not df.empty else df
    if df.empty or grp.empty:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center')
        _show_fig(fig)
        return
    tgt = cfg['target'][band] if isinstance(cfg['target'], dict) else cfg['target']
    c_data = grp[grp['Region'] == 'Center']['val'].values
    e_data = grp[grp['Region'] == 'Edge']['val'].values
    pos, box_data, labels, colors = [], [], [], []
    if len(c_data) > 0:
        pos.append(1)
        box_data.append(c_data)
        labels.append(f'Center\nn={len(c_data)}')
        colors.append('#3498db')
    if len(e_data) > 0:
        pos.append(2)
        box_data.append(e_data)
        labels.append(f'Edge\nn={len(e_data)}')
        colors.append('#e74c3c')
    if not box_data:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center')
        _show_fig(fig)
        return

    allv = np.concatenate(box_data)
    y_min = min(allv.min(), tgt) - 0.2
    y_max = max(allv.max(), tgt) + 0.2
    ax.set_ylim(y_min, y_max)

    # Good/Poor regions (VpiL: lower is better, IL/ER: higher is better)
    if cfg['good_above']:
        ax.axhspan(tgt, y_max, facecolor='#e8f8f5', alpha=0.6, zorder=0, label='Good Region')
        ax.axhspan(y_min, tgt, facecolor='#fadbd8', alpha=0.6, zorder=0, label='Poor Region')
    else:
        ax.axhspan(y_min, tgt, facecolor='#e8f8f5', alpha=0.6, zorder=0, label='Good Region')
        ax.axhspan(tgt, y_max, facecolor='#fadbd8', alpha=0.6, zorder=0, label='Poor Region')

    box = ax.boxplot(box_data, positions=pos, patch_artist=True, widths=0.5,
                     flierprops=dict(marker='d', markerfacecolor='black', markersize=6, alpha=0.6), zorder=2)
    for p, cl in zip(box['boxes'], colors):
        p.set_facecolor(cl)
        p.set_alpha(0.7)
    for p, arr in zip(pos, box_data):
        ax.scatter(np.random.normal(p, 0.05, len(arr)), arr, color='black', alpha=0.5, s=20, zorder=3)

    avg = grp['val'].mean()
    ax.axhline(avg, color='blue', ls='--', lw=2.5, label=f'Avg: {avg:.2f} {cfg["unit"]}', zorder=4)
    ax.axhline(tgt, color='red', ls='-', lw=2.5, label=f'Target: {tgt:.2f} {cfg["unit"]}', zorder=4)

    # Mark the selected die with a short region line and a star (no full-width line)
    if selected_c is not None and selected_r is not None:
        target_die = grp[(grp['Column'] == selected_c) & (grp['Row'] == selected_r)]
        if not target_die.empty:
            die_val = target_die['val'].values[0]
            die_region = target_die['Region'].values[0]
            x_pos = 1 if die_region == 'Center' else 2

            ax.hlines(die_val, xmin=x_pos - 0.28, xmax=x_pos + 0.28, color='#FF007F', ls='--', lw=2, zorder=5)
            ax.scatter(x_pos, die_val, color='#FF007F', marker='*', s=350, edgecolor='black',
                       linewidths=1.5, zorder=10, label=f'Die ({selected_c}, {selected_r})')
            ax.text(x_pos + 0.15, die_val, f"{die_val:.2f}", color='#FF007F', fontweight='bold', va='center', zorder=11)

    ax.set_title(f"{cfg['boxtag']} Analysis : {wafer} ({band})\nDate: {qdate}", fontsize=18, fontweight='bold', pad=15)
    ax.set_xticks(pos)
    ax.set_xticklabels(labels, fontsize=14, fontweight='bold')
    ax.set_ylabel(cfg['cbar'], fontsize=16, fontweight='bold')

    # Push the legend fully outside on the right to avoid overlap
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), prop={'size': 11, 'weight': 'bold'})

    ax.grid(True, axis='y', ls=':', alpha=0.4, zorder=1)
    ax.set_xlim(0.5, max(pos) + 0.5)

    # Adjust layout so the outside legend is not clipped
    fig.tight_layout()
    _show_fig(fig)


def display_die_table(data, length_map, wafer, date, band, c, r, show_raw=False):
    # Show one die's metrics (and optionally raw data) as a DataFrame
    from IPython.display import display
    d = get_die(data, wafer, date, band, c, r)
    if d is None:
        print(f"No valid data: {wafer} / {band} / ({c}, {r})")
        return

    # 1. Summary metrics
    vpil_val = metric_value(d, 'vpil', length_map)
    il_val = metric_value(d, 'il', length_map)
    er_val = metric_value(d, 'er', length_map)

    df_summary = pd.DataFrame([{
        'Wafer': wafer, 'Date': date, 'Band': band,
        'Column': c, 'Row': r,
        'ER (dB)': er_val, 'IL (dB)': il_val, 'VpiL (V*cm)': vpil_val
    }])

    print(f"[Summary] {wafer} / {band} / Coord: ({c}, {r})")
    display(df_summary)

    # 2. Raw spectra (only when show_raw is True)
    if show_raw:
        raw_rows = []
        for b in d['bias_data_list']:
            if b['bias'] is None:
                continue
            m = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
            for w, i in zip(b['wl'][m], b['il'][m]):
                raw_rows.append({'Bias (V)': b['bias'], 'Wavelength (nm)': w, 'IL (dB)': i})

        if raw_rows:
            df_raw = pd.DataFrame(raw_rows)
            print(f"\n[Raw spectra] {len(df_raw)} rows total (showing first 10)")
            display(df_raw.head(10))


def interactive(data, length_map=None, metric='vpil'):
    # Pick a die from a dropdown and show its plot (notebook only).
    # metric: 'vpil' -> VpiL curve, 'phase' -> phase (radians) curve.
    import ipywidgets as widgets
    from ipywidgets import interact

    opts = sorted({(d['wafer_id'], d['date'], d['band'], d['die_c'], d['die_r']) for d in data})
    labels = [(f"{w} / {dt} / {b} ({c},{r})", (w, dt, b, c, r)) for (w, dt, b, c, r) in opts]

    def _show(sel):
        w, dt, b, c, r = sel
        if metric == 'phase':
            plot_die_phase(data, w, dt, b, c, r)
        else:
            plot_die_vpil(data, length_map, w, dt, b, c, r)

    interact(_show, sel=widgets.Dropdown(options=labels, description='Die:'))


def plot_die_summary(data, length_map, wafer, date, band, c, r):
    # Combine one die's main plots into a 2x2 figure: raw / flattened / VpiL / phase
    d = get_die(data, wafer, date, band, c, r)
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle(f'{wafer} {band} {date} ({c},{r})', fontsize=14, fontweight='bold')
    if d is None:
        axes[0, 0].text(0.5, 0.5, 'No data', ha='center', va='center')
        _show_fig(fig)
        return

    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    rwl, ril = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    poly = ref_poly(rwl, ril, smooth=True) if len(rwl) >= 31 else None

    # (1) Raw spectra (per bias)
    ax = axes[0, 0]
    for b in d['bias_data_list']:
        mb = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        ax.plot(b['wl'][mb], b['il'][mb], lw=0.8, label=b.get('label', ''))
    ax.set_title('Raw spectra'); ax.set_xlabel('Wavelength (nm)'); ax.set_ylabel('IL (dB)')
    ax.grid(alpha=0.3); ax.legend(fontsize=7, ncol=2)

    # (2) Flattened spectra
    ax = axes[0, 1]
    if poly is not None:
        for b in d['bias_data_list']:
            mb = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
            ax.plot(b['wl'][mb], b['il'][mb] - poly(b['wl'][mb]), lw=0.8)
    ax.set_title('Flattened spectra'); ax.set_xlabel('Wavelength (nm)'); ax.grid(alpha=0.3)

    # (3) VpiL curve
    ax = axes[1, 0]
    res = extract_vpil(d, (length_map or {}).get((wafer, c, r, band), DEFAULT_L_UM) * 1e-4)
    if res:
        vpil, volts, curve = res
        ax.plot(volts, curve, 's-', color='gray'); ax.plot(0.0, vpil, 'r*', markersize=14)
        ax.set_title(f'VpiL @0V = {vpil:.3f} V*cm')
    else:
        ax.set_title('VpiL: no valid value')
    ax.set_xlabel('Voltage (V)'); ax.set_ylabel('Vpi*L (V*cm)'); ax.grid(alpha=0.3)

    # (4) Phase (radians) curve
    ax = axes[1, 1]
    pr = extract_phase(d)
    if pr:
        V, PH, fsr = pr
        ax.plot(V, PH, 'o-', color='steelblue'); ax.axhline(np.pi, color='red', ls=':')
        ax.text(V.max(), np.pi, '  pi', color='red', va='center')
        ax.set_title(f'Phase (rad)  FSR={fsr:.2f} nm')
    else:
        ax.set_title('Phase: no valid value')
    ax.set_xlabel('Voltage (V)'); ax.set_ylabel('Phase shift (rad)'); ax.grid(alpha=0.3)

    fig.tight_layout()
    _show_fig(fig)


def dashboard(data, length_map=None):
    # Buttons to pick wafer/band/metric and a die, then view the plots (notebook only).
    import ipywidgets as widgets
    from IPython.display import display, clear_output

    wafer_b = widgets.ToggleButtons(options=list_wafers(data), description='Wafer')
    band_b = widgets.ToggleButtons(options=['LMZC', 'LMZO'], description='Band')
    metric_b = widgets.ToggleButtons(options=[('VpiL', 'vpil'), ('IL', 'il'), ('ER', 'er')], description='Metric')
    die_d = widgets.Dropdown(description='Die')
    out = widgets.Output()

    def _fill_dies():
        try:
            die_d.unobserve(_refresh, 'value')
        except ValueError:
            pass
        dies = sorted({(d['date'], d['die_c'], d['die_r']) for d in data
                       if d['wafer_id'] == wafer_b.value and d['band'] == band_b.value})
        die_d.options = [(f"{dt} ({c},{r})", (dt, c, r)) for (dt, c, r) in dies]
        die_d.observe(_refresh, 'value')

    def _refresh(*_):
        with out:
            clear_output(wait=True)
            if not die_d.value:
                print('No dies for this wafer/band combination.')
                return
            dt, c, r = die_d.value
            w, b, met = wafer_b.value, band_b.value, metric_b.value
            plot_die_summary(data, length_map, w, dt, b, c, r)
            plot_wafer_map(data, length_map, w, dt, b, met)
            plot_box(data, length_map, w, dt, b, met)

    def _on_top(*_):
        _fill_dies()
        _refresh()

    wafer_b.observe(_on_top, 'value')
    band_b.observe(_on_top, 'value')
    metric_b.observe(_refresh, 'value')

    _fill_dies()
    display(widgets.VBox([wafer_b, band_b, metric_b, die_d, out]))
    _refresh()


def summary_table(data, length_map=None):
    # Per wafer/band summary: median VpiL/IL/ER + VpiL Center/Edge + VpiL target pass rate
    dfs = {m: _metric_df(data, length_map, m) for m in ('vpil', 'il', 'er')}
    label = {'vpil': 'VpiL (V.cm)', 'il': 'IL (dB)', 'er': 'ER (dB)'}
    keys = set()
    for df in dfs.values():
        if not df.empty:
            keys |= {tuple(x) for x in df[['Wafer', 'Band']].drop_duplicates().values}

    rows = []
    for wafer, band in sorted(keys):
        r = {'Wafer': wafer, 'Band': band}
        for m in ('vpil', 'il', 'er'):
            df = dfs[m]
            g = df[(df['Wafer'] == wafer) & (df['Band'] == band)] if not df.empty else df
            r[label[m]] = round(g['val'].median(), 3) if len(g) else None
        gv = dfs['vpil']
        gv = gv[(gv['Wafer'] == wafer) & (gv['Band'] == band)] if not gv.empty else gv
        r['n'] = len(gv)
        if len(gv):
            cen = gv[gv['Region'] == 'Center']['val']
            edg = gv[gv['Region'] == 'Edge']['val']
            r['VpiL_Center (V.cm)'] = round(cen.median(), 3) if len(cen) else None
            r['VpiL_Edge (V.cm)'] = round(edg.median(), 3) if len(edg) else None
        rows.append(r)
    cols = ['Wafer', 'Band', 'n', 'VpiL (V.cm)', 'IL (dB)', 'ER (dB)',
            'VpiL_Center (V.cm)', 'VpiL_Edge (V.cm)']
    df = pd.DataFrame(rows)
    return df[[c for c in cols if c in df.columns]]
