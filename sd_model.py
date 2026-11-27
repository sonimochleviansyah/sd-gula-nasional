"""
Model System Dynamics: Ketersediaan Gula Nasional Indonesia
Stok  : Luas areal tebu (A), Lahan dalam pengembangan (D), Stok gula nasional (S), Penduduk (P)
Aliran: ekspansi organik, alih fungsi, pematangan lahan baru, produksi, impor, konsumsi
Sumber data: Outlook Tebu 2025 (Pusdatin Kementan), BPS, berita yang mengutip BPS.
"""
import numpy as np
import pandas as pd
from scipy.optimize import least_squares, curve_fit

# ---------------------------------------------------------------- DATA
def load_data(path="data_gula.csv"):
    df = pd.read_csv(path)
    df["konsumsi_ton"] = df["produksi_ton"] + df["impor_ton"]          # apparent consumption
    df["kons_per_kapita_kg"] = df["konsumsi_ton"] / (df["penduduk_juta"] * 1000)
    df["SSR_aktual"] = df["produksi_ton"] / df["konsumsi_ton"]
    return df

# ---------------------------------------------------------------- SKENARIO
SKENARIO = {
    "Baseline (tren saat ini)":      dict(),
    "Peningkatan produktivitas":     dict(y_target=85.0),
    "Peningkatan rendemen":          dict(r_target=0.10),
    "Perluasan areal (+350 rb ha)":  dict(ha_program=350_000),
    "Kombinasi tiga intervensi":     dict(y_target=85.0, r_target=0.10, ha_program=350_000),
    "Roadmap Perpres 40/2023 penuh": dict(y_target=93.0, r_target=0.112, ha_program=700_000),
}

# ---------------------------------------------------------------- MODEL
def simulate(p, skenario=None, t0=2014, t1=2035, dt=0.25, mulai=2026, selesai=2030):
    """Simulasi Euler. Mengembalikan DataFrame tahunan."""
    s = skenario or {}
    y0, r0 = p["y_tebu0"], p["r_eff"]
    y_t = s.get("y_target", y0)
    r_t = s.get("r_target", r0)
    ha_total = s.get("ha_program", 0.0) * s.get("realisasi", 1.0)

    A, D, P = p["A0"], 0.0, p["pop0"]
    S = p["cover"] * (P * p["c0"] * 1000)           # stok awal = stok target
    rows, n_steps = [], int(round((t1 - t0) / dt))
    for k in range(n_steps + 1):
        t = t0 + k * dt
        frac = float(np.clip((t - mulai) / (selesai - mulai), 0, 1))
        y_tebu = y0 + (y_t - y0) * frac
        rendemen = r0 + (r_t - r0) * frac
        in_program = (ha_total / (selesai - mulai)) if mulai <= t < selesai else 0.0

        produksi = A * y_tebu * rendemen
        c_kapita = p["c_inf"] - (p["c_inf"] - p["c0"]) * np.exp(-p["k_c"] * (t - t0))   # menuju titik jenuh
        konsumsi = P * c_kapita * 1000
        s_target = p["cover"] * konsumsi
        impor = max(0.0, konsumsi - produksi + (s_target - S) / p["tau_s"])

        if abs(t - round(t)) < 1e-9:
            rows.append(dict(tahun=int(round(t)), luas_ha=A, lahan_pengembangan_ha=D,
                             y_tebu=y_tebu, rendemen=rendemen, produksi_ton=produksi,
                             penduduk_juta=P, konsumsi_ton=konsumsi, impor_ton=impor,
                             stok_ton=S, SSR=produksi / konsumsi,
                             IDR=impor / (produksi + impor) if (produksi + impor) > 0 else 0))
        # laju perubahan
        matang = D / p["tau_dev"]
        if t < p["tahun_rezim"]:
            g_exp = p["g_exp"]
        elif t < p["tahun_proyeksi"]:
            g_exp = p["g_exp2"]
        else:
            g_exp = p["g_exp_proy"]
        dA = g_exp * A + matang - p["g_conv"] * A
        dD = in_program - matang
        dS = produksi + impor - konsumsi
        dP = p["g_pop"] * P
        A += dA * dt; D += dD * dt; S += dS * dt; P += dP * dt
    return pd.DataFrame(rows)

# ---------------------------------------------------------------- KALIBRASI
def kalibrasi(df, g_conv=0.02, y_tebu0=70.0, cover=0.15, tau_s=1.0, tau_dev=1.0,
              tahun_rezim=2021, tahun_proyeksi=2024, net_growth_proyeksi=0.0207):
    """Kalibrasi parameter. net_growth_proyeksi = rata-rata pertumbuhan luas panen 2016-2025
    (Outlook Tebu 2025: 2,07%/tahun) dipakai untuk tahun >= tahun_proyeksi."""
    t = df.tahun.values - df.tahun.values[0]
    g_pop = np.polyfit(t, np.log(df.penduduk_juta.values), 1)[0]
    f = lambda tt, c0, cinf, k: cinf - (cinf - c0) * np.exp(-k * tt)
    (c0, c_inf, k_c), _ = curve_fit(f, t, df.kons_per_kapita_kg.values, p0=[22, 30, 0.3],
                                    bounds=([10, 20, 0.01], [40, 60, 2.0]))
    p = dict(A0=float(df.luas_panen_ha.iloc[0]), pop0=float(df.penduduk_juta.iloc[0]),
             c0=float(c0), c_inf=float(c_inf), k_c=float(k_c), g_pop=float(g_pop),
             g_conv=g_conv, y_tebu0=y_tebu0, cover=cover, tau_s=tau_s, tau_dev=tau_dev,
             tahun_rezim=tahun_rezim, tahun_proyeksi=tahun_proyeksi,
             g_exp=0.03, g_exp2=0.05, r_eff=0.07, g_exp_proy=net_growth_proyeksi + g_conv)
    t0, t1 = int(df.tahun.min()), int(df.tahun.max())

    def resid(x):
        q = dict(p, g_exp=x[0], g_exp2=x[1], r_eff=x[2])
        sim = simulate(q, t0=t0, t1=t1).set_index("tahun")
        a = (sim.luas_ha.values - df.luas_panen_ha.values) / df.luas_panen_ha.values
        b = (sim.produksi_ton.values - df.produksi_ton.values) / df.produksi_ton.values
        return np.r_[a, b]

    sol = least_squares(resid, x0=[0.0, 0.05, 0.07], bounds=([-0.1, -0.1, 0.03], [0.2, 0.3, 0.12]))
    p["g_exp"], p["g_exp2"], p["r_eff"] = map(float, sol.x)
    return p

# ---------------------------------------------------------------- VALIDASI
def mape(aktual, sim):
    aktual, sim = np.asarray(aktual, float), np.asarray(sim, float)
    return float(np.mean(np.abs((aktual - sim) / aktual)) * 100)

def validasi(df, p, tahun=None):
    t0, t1 = int(df.tahun.min()), int(df.tahun.max())
    sim = simulate(p, t0=t0, t1=t1).set_index("tahun")
    d = df.set_index("tahun")
    if tahun is not None:
        sim, d = sim.loc[tahun], d.loc[tahun]
    return {
        "Luas areal":   mape(d.luas_panen_ha, sim.luas_ha),
        "Produksi":     mape(d.produksi_ton, sim.produksi_ton),
        "Konsumsi":     mape(d.konsumsi_ton, sim.konsumsi_ton),
        "Impor":        mape(d.impor_ton, sim.impor_ton),
        "SSR":          mape(d.SSR_aktual, sim.SSR),
    }

# ---------------------------------------------------------------- SENSITIVITAS
def sensitivitas(p, tahun=2030, delta=0.10):
    base = simulate(p).set_index("tahun").loc[tahun, "SSR"]
    out = {}
    for nama, key in [("Rendemen efektif", "r_eff"), ("Produktivitas tebu", "y_tebu0"),
                      ("Laju ekspansi lahan (proyeksi)", "g_exp_proy"), ("Laju alih fungsi", "g_conv"),
                      ("Konsumsi/kapita jenuh", "c_inf"), ("Pertumbuhan penduduk", "g_pop")]:
        hasil = []
        for sgn in (-1, +1):
            q = dict(p); q[key] = p[key] * (1 + sgn * delta)
            hasil.append(simulate(q).set_index("tahun").loc[tahun, "SSR"] - base)
        out[nama] = hasil
    return base, out


# ---------------------------------------------------------------- UJI KONDISI EKSTREM
def uji_ekstrem(p):
    """Uji kondisi ekstrem: hasil harus masuk akal secara logika."""
    hasil = {}
    q = dict(p, r_eff=0.0)                                  # rendemen nol -> produksi nol, semua impor
    r = simulate(q).set_index("tahun").loc[2030]
    hasil["Rendemen = 0"] = dict(produksi=r.produksi_ton, SSR=r.SSR, impor_vs_konsumsi=r.impor_ton / r.konsumsi_ton)
    q = dict(p, c0=1e-6, c_inf=1e-6)                        # konsumsi ~ 0 -> impor 0
    r = simulate(q).set_index("tahun").loc[2030]
    hasil["Konsumsi ~ 0"] = dict(impor=r.impor_ton)
    q = dict(p, r_eff=0.5)                                  # rendemen sangat tinggi -> SSR >> 1, impor 0
    r = simulate(q).set_index("tahun").loc[2030]
    hasil["Rendemen sangat tinggi"] = dict(SSR=r.SSR, impor=r.impor_ton)
    return hasil
