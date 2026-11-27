import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import sd_model as m

st.set_page_config(page_title="SD Gula Nasional", page_icon="🍬", layout="wide")

@st.cache_data
def siapkan():
    df = m.load_data("data_gula.csv")
    return df, m.kalibrasi(df)

df, P0 = siapkan()

st.title("🍬 Simulasi Sistem Dinamik Ketersediaan Gula Nasional")
st.caption("Produksi, konsumsi, dan ketergantungan impor dengan skenario peningkatan produktivitas, rendemen, dan perluasan areal tebu")

# ------------------------------------------------------------ sidebar
st.sidebar.header("Skenario kustom")
y_t = st.sidebar.slider("Target produktivitas tebu (ton/ha)", 70.0, 100.0, 85.0, 1.0)
r_t = st.sidebar.slider("Target rendemen (%)", 7.0, 12.0, 10.0, 0.1) / 100
ha = st.sidebar.slider("Tambahan areal baru (ribu ha)", 0, 700, 350, 25) * 1000
real = st.sidebar.slider("Realisasi program (%)", 0, 100, 100, 5) / 100
mulai, selesai = st.sidebar.slider("Periode intervensi", 2026, 2035, (2026, 2030))
g_net = st.sidebar.slider("Pertumbuhan neto areal baseline (%/th)", -2.0, 5.0, 2.07, 0.1) / 100
horizon = st.sidebar.slider("Tahun akhir simulasi", 2030, 2040, 2035)

p = dict(P0, g_exp_proy=g_net + P0["g_conv"])
kustom = dict(y_target=y_t, r_target=r_t, ha_program=ha, realisasi=real)
base = m.simulate(p, t1=horizon, mulai=mulai, selesai=selesai)
sim = m.simulate(p, kustom, t1=horizon, mulai=mulai, selesai=selesai)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Skenario kustom", "Perbandingan skenario", "Validasi model",
                                         "Sensitivitas", "Metode & data"])

# ------------------------------------------------------------ tab 1
with tab1:
    th = st.selectbox("Tahun yang ditinjau", list(range(2026, horizon + 1)), index=min(4, horizon - 2026))
    a, b = base.set_index("tahun").loc[th], sim.set_index("tahun").loc[th]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"SSR {th}", f"{b.SSR*100:.1f}%", f"{(b.SSR-a.SSR)*100:+.1f} poin vs baseline")
    c2.metric(f"Produksi {th}", f"{b.produksi_ton/1e6:.2f} jt ton", f"{(b.produksi_ton-a.produksi_ton)/1e6:+.2f}")
    c3.metric(f"Impor {th}", f"{b.impor_ton/1e6:.2f} jt ton", f"{(b.impor_ton-a.impor_ton)/1e6:+.2f}", delta_color="inverse")
    c4.metric(f"Luas areal {th}", f"{b.luas_ha/1e3:.0f} rb ha", f"{(b.luas_ha-a.luas_ha)/1e3:+.0f}")

    fig, ax = plt.subplots(2, 2, figsize=(11, 6.5))
    ax[0, 0].plot(df.tahun, df.produksi_ton / 1e6, "ko", ms=4, label="Produksi aktual")
    ax[0, 0].plot(base.tahun, base.produksi_ton / 1e6, "--", label="Produksi baseline")
    ax[0, 0].plot(sim.tahun, sim.produksi_ton / 1e6, label="Produksi skenario")
    ax[0, 0].plot(sim.tahun, sim.konsumsi_ton / 1e6, color="tab:red", label="Konsumsi")
    ax[0, 0].set_title("Produksi vs konsumsi (juta ton)"); ax[0, 0].legend(fontsize=7)
    ax[0, 1].plot(df.tahun, df.SSR_aktual * 100, "ko", ms=4, label="SSR aktual")
    ax[0, 1].plot(base.tahun, base.SSR * 100, "--", label="Baseline")
    ax[0, 1].plot(sim.tahun, sim.SSR * 100, label="Skenario")
    ax[0, 1].axhline(100, color="g", lw=0.8); ax[0, 1].set_title("Self-Sufficiency Ratio (%)"); ax[0, 1].legend(fontsize=7)
    ax[1, 0].plot(df.tahun, df.luas_panen_ha / 1e3, "ko", ms=4)
    ax[1, 0].plot(base.tahun, base.luas_ha / 1e3, "--"); ax[1, 0].plot(sim.tahun, sim.luas_ha / 1e3)
    ax[1, 0].set_title("Luas areal tebu (ribu ha)")
    ax[1, 1].plot(df.tahun, df.impor_ton / 1e6, "ko", ms=4)
    ax[1, 1].plot(base.tahun, base.impor_ton / 1e6, "--"); ax[1, 1].plot(sim.tahun, sim.impor_ton / 1e6)
    ax[1, 1].set_title("Impor gula (juta ton)")
    for x in ax.flat: x.grid(alpha=0.3)
    plt.tight_layout(); st.pyplot(fig)
    st.dataframe(sim[["tahun", "luas_ha", "y_tebu", "rendemen", "produksi_ton", "konsumsi_ton", "impor_ton", "SSR", "IDR"]]
                 .round(3), width="stretch", hide_index=True)

# ------------------------------------------------------------ tab 2
with tab2:
    rows = []
    for nama, sc in m.SKENARIO.items():
        s = m.simulate(p, sc, t1=2035).set_index("tahun")
        rows.append({"Skenario": nama, "SSR 2030 (%)": s.loc[2030, "SSR"] * 100,
                     "SSR 2035 (%)": s.loc[2035, "SSR"] * 100,
                     "Produksi 2030 (jt ton)": s.loc[2030, "produksi_ton"] / 1e6,
                     "Impor 2030 (jt ton)": s.loc[2030, "impor_ton"] / 1e6})
    tb = pd.DataFrame(rows).round(2)
    st.dataframe(tb, width="stretch", hide_index=True)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for nama, sc in m.SKENARIO.items():
        s = m.simulate(p, sc, t1=2035)
        ax.plot(s.tahun, s.SSR * 100, label=nama)
    ax.axhline(100, color="g", lw=0.8); ax.set_ylabel("SSR (%)"); ax.grid(alpha=0.3); ax.legend(fontsize=7)
    st.pyplot(fig)

# ------------------------------------------------------------ tab 3
with tab3:
    val = m.validasi(df, P0)
    st.subheader("MAPE model terhadap data 2014–2024")
    st.dataframe(pd.DataFrame({"Variabel": val.keys(), "MAPE (%)": [round(v, 2) for v in val.values()]}),
                 hide_index=True)
    sv = m.simulate(P0, t1=2024)
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.5))
    for x, (jd, ak, sm) in zip(ax, [("Luas areal (ha)", df.luas_panen_ha, sv.luas_ha),
                                    ("Produksi (ton)", df.produksi_ton, sv.produksi_ton),
                                    ("Impor (ton)", df.impor_ton, sv.impor_ton)]):
        x.plot(df.tahun, ak, "ko-", ms=3, label="Aktual"); x.plot(sv.tahun, sm, "r--", label="Simulasi")
        x.set_title(jd); x.grid(alpha=0.3); x.legend(fontsize=7)
    plt.tight_layout(); st.pyplot(fig)
    st.write("**Uji kondisi ekstrem (tahun 2030)**")
    st.json({k: {kk: float(vv) for kk, vv in v.items()} for k, v in m.uji_ekstrem(P0).items()})
    st.write("**Parameter hasil kalibrasi**")
    st.json({k: (round(v, 5) if isinstance(v, float) else v) for k, v in P0.items()})

# ------------------------------------------------------------ tab 4
with tab4:
    th = st.selectbox("Tahun SSR", [2030, 2035], index=0)
    delta = st.slider("Perubahan parameter ±(%)", 5, 30, 10, 5) / 100
    base_ssr, out = m.sensitivitas(p, tahun=th, delta=delta)
    st.write(f"SSR baseline {th}: **{base_ssr*100:.1f}%**")
    nama = list(out.keys()); lo = [out[k][0] * 100 for k in nama]; hi = [out[k][1] * 100 for k in nama]
    urut = np.argsort([max(abs(l), abs(h)) for l, h in zip(lo, hi)])
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh([nama[i] for i in urut], [lo[i] for i in urut], color="tab:blue", label=f"-{int(delta*100)}%")
    ax.barh([nama[i] for i in urut], [hi[i] for i in urut], color="tab:orange", label=f"+{int(delta*100)}%")
    ax.axvline(0, color="k", lw=0.8); ax.set_xlabel("Perubahan SSR (poin persen)"); ax.legend(); ax.grid(alpha=0.3)
    st.pyplot(fig)

# ------------------------------------------------------------ tab 5
with tab5:
    st.markdown("""
**Struktur model (stock-flow)**
- Stok: luas areal tebu *A*, lahan dalam pengembangan *D* (delay 1 tahun), stok gula nasional *S*, penduduk *P*.
- Produksi = *A* × produktivitas tebu × rendemen efektif.
- Konsumsi = *P* × konsumsi per kapita (menuju titik jenuh).
- Impor = max(0, konsumsi − produksi + (stok target − *S*)/τ) → loop penyeimbang.
- SSR = produksi / konsumsi. Konsumsi = produksi + impor (apparent consumption, definisi Outlook Tebu).

**Sumber data:** Outlook Tebu 2025 (Pusdatin Kementan; data Ditjen Perkebunan), BPS, dan berita yang mengutip BPS.
Impor 2017 dan jumlah penduduk perlu diverifikasi dengan tabel BPS (lihat kolom *catatan* pada data).
""")
    st.dataframe(df, width="stretch", hide_index=True)
