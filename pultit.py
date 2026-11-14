#!/usr/bin/env python3
"""Pultit - ISO-metristen pulttien, mutterien ja aluslevyjen STL-generaattori.

Käyttö:  python pultit.py            (avaa graafisen käyttöliittymän)
         python pultit.py bolt M8 --length 40
         python pultit.py bolt M8 -l 40 --thread print
         python pultit.py nut M8 --thread print
         python pultit.py capnut M8
         python pultit.py washer M8
"""
import argparse
import math
import sys

import numpy as np
import trimesh

# koko: (nousu P, avainväli s, kannan korkeus k [ISO 4014/4017],
#        mutterin korkeus m [ISO 4032], aluslevy d1, d2, h [ISO 7089])
SIZES = {
    "M3":  (0.5,  5.5, 2.0, 2.4,  3.2,  7.0, 0.5),
    "M4":  (0.7,  7.0, 2.8, 3.2,  4.3,  9.0, 0.8),
    "M5":  (0.8,  8.0, 3.5, 4.7,  5.3, 10.0, 1.0),
    "M6":  (1.0, 10.0, 4.0, 5.2,  6.4, 12.0, 1.6),
    "M8":  (1.25, 13.0, 5.3, 6.8, 8.4, 16.0, 1.6),
    "M10": (1.5, 16.0, 6.4, 8.4, 10.5, 20.0, 2.0),
    "M12": (1.75, 18.0, 7.5, 10.8, 13.0, 24.0, 2.5),
}
# Tulostusystävällinen kierre: (nousu, oletustulostusvara).
# Nousu noin 1.5–2× ISO-karkea. Vara on koon mukaan, jotta kierteeseen jää pitoa
# (45° kyljillä korkeus on enintään ≈ 0.42 P).
PRINT_SPEC = {
    "M3":  (1.00, 0.20),
    "M4":  (1.25, 0.25),
    "M5":  (1.50, 0.30),
    "M6":  (1.75, 0.35),
    "M8":  (2.00, 0.40),
    "M10": (2.50, 0.40),
    "M12": (3.00, 0.40),
}
# DIN 1587 hattumutteri: (s, kokonaiskorkeus h, kuusiön korkeus m, kierresyvyys t)
# HUOM: likimääräiset arvot DIN 1587 -taulukon mukaan
CAPNUT = {
    "M3": (5.5, 7.0, 4.0, 4.5), "M4": (7.0, 8.0, 5.0, 5.5), "M5": (8.0, 10.0, 6.0, 7.0),
    "M6": (10.0, 12.0, 7.0, 8.0), "M8": (13.0, 15.0, 9.0, 11.0),
    "M10": (16.0, 18.0, 11.0, 13.0), "M12": (18.0, 22.0, 13.0, 16.0),
}
N_THETA = 96  # jaollinen 6:lla -> kuusiokulmat osuvat tarkasti verteksiin
THREAD_MODES = ("iso", "print")
THREAD_LABELS = {"iso": "ISO (tarkka)", "print": "Tulostusystävällinen"}


def _size(name):
    name = name.upper()
    if name not in SIZES:
        raise ValueError(f"Tuntematon koko {name}. Vaihtoehdot: {', '.join(SIZES)}")
    return int(name[1:]), SIZES[name]


def _mode(name):
    name = (name or "iso").lower()
    if name not in THREAD_MODES:
        raise ValueError(f"Tuntematon kierretyyppi {name}. Vaihtoehdot: iso, print")
    return name


def default_clearance(size, mode="iso"):
    mode = _mode(mode)
    if mode == "print":
        return PRINT_SPEC[size.upper()][1]
    return 0.2


def pitch_of(size, mode="iso"):
    d, (P_iso, *_rest) = _size(size)
    if _mode(mode) == "print":
        return PRINT_SPEC[size.upper()][0]
    return P_iso


def _theta(n=N_THETA):
    return np.linspace(0, 2 * np.pi, n, endpoint=False)


def hex_radius(theta, s):
    """Kuusiön säde kulman funktiona (s = avainväli, kulmat 0°,60°,...)."""
    a = np.mod(theta + np.pi / 6, np.pi / 3) - np.pi / 6
    return (s / 2) / np.cos(a)


def print_thread_dims(P):
    """Puolisuunnikaskierre: 45° kyljet, typistetyt + pyöristetyt harjat/pohjat."""
    crest_flat = 0.16 * P
    root_flat = 0.16 * P
    flank_z = (P - crest_flat - root_flat) / 2
    height = flank_z  # 45° => dr = dz
    rf = 0.10 * P
    return crest_flat, root_flat, flank_z, height, rf


def print_thread_radius(theta, z, d, P, external, clearance):
    """Tulostusystävällinen kierre: 45° kyljet (ylitys ≤ 45° pystyssä tulostettaessa)."""
    u = np.mod(z - P * theta / (2 * np.pi), P)
    dist = np.abs(u - P / 2)  # 0 = harjan keski, P/2 = pohjan keski
    crest_flat, root_flat, flank_z, height, rf = print_thread_dims(P)
    k = rf * (math.sqrt(2) - 1.0)
    r_maj = d / 2.0
    r_min = d / 2.0 - height
    u_crest = crest_flat / 2.0
    u_root = u_crest + flank_z

    r = np.where(
        dist <= u_crest,
        r_maj,
        np.where(dist >= u_root, r_min, r_maj - (dist - u_crest)),
    )

    # Harjan kupera pyöristys (keskipiste kappaleen sisällä)
    uc = u_crest - k
    rc = r_maj - rf
    in_crest = (dist >= uc) & (dist <= uc + rf / math.sqrt(2))
    r = np.where(in_crest, rc + np.sqrt(np.maximum(rf ** 2 - (dist - uc) ** 2, 0.0)), r)

    # Pohjan kovera pyöristys (keskipiste uran puolella)
    ur = u_root + k
    rr = r_min + rf
    in_root = (dist >= ur - rf / math.sqrt(2)) & (dist <= ur)
    r = np.where(in_root, rr - np.sqrt(np.maximum(rf ** 2 - (dist - ur) ** 2, 0.0)), r)

    if external:
        return r - clearance / 2.0
    return r + clearance / 2.0


def iso_thread_radius(theta, z, d, P, external, clearance):
    """ISO-metrisen 60° kierreprofiilin säde (z, theta) pisteessä. Oikeakätinen."""
    H = math.sqrt(3) / 2 * P
    u = np.mod(z - P * theta / (2 * np.pi), P)
    dist = np.abs(u - P / 2)
    sharp_crest = d / 2 + H / 8
    r = sharp_crest - math.sqrt(3) * dist
    if external:
        r = np.clip(r, d / 2 - 17 * H / 24, d / 2) - clearance / 2
    else:
        r = np.clip(r, d / 2 - 5 * H / 8, d / 2) + clearance / 2
    return r


def thread_radius(theta, z, d, P, external, clearance, mode="iso"):
    if _mode(mode) == "print":
        return print_thread_radius(theta, z, d, P, external, clearance)
    return iso_thread_radius(theta, z, d, P, external, clearance)


def thread_root_radius(d, P, clearance, mode, external=True):
    """Kierteen pohjan säde (ulko- tai sisäpuolinen)."""
    if _mode(mode) == "print":
        height = print_thread_dims(P)[3]
        r = d / 2.0 - height
    else:
        H = math.sqrt(3) / 2 * P
        r = d / 2 - (17 * H / 24 if external else 5 * H / 8)
    return r - clearance / 2 if external else r + clearance / 2


def _rings_to_xyz(theta, rings):
    """rings: lista (z, r_array) -> (n_rings, n_theta, 3)."""
    out = []
    for z, r in rings:
        out.append(np.stack([r * np.cos(theta), r * np.sin(theta), np.full_like(theta, z)], -1))
    return np.array(out)


def _grid_faces(nr, nt, offset, inward=False):
    i, j = np.meshgrid(np.arange(nr - 1), np.arange(nt), indexing="ij")
    i, j = i.ravel(), j.ravel()
    jn = (j + 1) % nt
    a, b = offset + i * nt + j, offset + i * nt + jn
    c, d = offset + (i + 1) * nt + jn, offset + (i + 1) * nt + j
    f = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    return f[:, ::-1] if inward else f


def _annulus(outer_off, inner_off, nt, up):
    j = np.arange(nt)
    jn = (j + 1) % nt
    O, On, I, In = outer_off + j, outer_off + jn, inner_off + j, inner_off + jn
    f = np.concatenate([np.stack([O, I, In], 1), np.stack([O, In, On], 1)])
    return f[:, ::-1] if up else f


def _zsamples(z0, z1, step):
    n = max(1, int(math.ceil((z1 - z0) / step)))
    return np.linspace(z0, z1, n + 1)


def make_bolt(size, length, thread_length=None, clearance=None, head_chamfer=True, mode="iso"):
    mode = _mode(mode)
    d, (P_iso, s, k, *_rest) = _size(size)
    P = pitch_of(size, mode)
    if clearance is None:
        clearance = default_clearance(size, mode)
    if length <= 0:
        raise ValueError("Pituuden täytyy olla > 0")
    if thread_length is None or thread_length > length:
        thread_length = length
    th = _theta()
    zstep = P / 16
    rings = []
    # kanta z = 0..k, yläreunassa 30° viiste
    for z in _zsamples(0, k, k / 8):
        r = hex_radius(th, s)
        if head_chamfer:
            # viiste kannan alapinnassa (kannan "laakeripinta" alas, z=0)
            r = np.minimum(r, s / 2 * 0.98 + z * math.sqrt(3))
        rings.append((z, r))
    ztip = k + length
    zthr0 = ztip - thread_length
    r_shank = d / 2 - clearance / 2
    r_root = thread_root_radius(d, P, clearance, mode, external=True)
    zs = []
    if zthr0 > k:
        zs += list(_zsamples(k, zthr0, P / 2))
    zs += list(_zsamples(max(zthr0, k), ztip, zstep))
    zs = np.unique(np.round(zs, 9))
    # Tulostustilassa pidempi 45° sisäänmeno kärjessä ja kierteen alussa
    tip_len = max(r_shank - r_root, 0.75 * P if mode == "print" else 0.0)
    runout = 1.0 if mode == "print" else 2.0  # dr/dz; 1 => 45°
    for z in zs:
        if z < zthr0 - 1e-9:
            r = np.full_like(th, r_shank)
        else:
            r = thread_radius(th, z, d, P, True, clearance, mode)
            r = np.minimum(r, np.maximum(r_shank, d / 2))
            r = np.minimum(r, r_root + (ztip - z) * (r_shank - r_root) / max(tip_len, 1e-9))
            if tip_len > r_shank - r_root:
                # 45° viiste kärjessä koko tip_len-matkalta
                r = np.minimum(r, r_shank + (ztip - z) - tip_len + (r_shank - r_root))
                r = np.minimum(r, r_shank + (ztip - z))
            if zthr0 > k:
                r = np.minimum(r, r_shank + (z - zthr0) * runout)
        rings.append((z, r))
    V = _rings_to_xyz(th, rings).reshape(-1, 3)
    nr, nt = len(rings), len(th)
    F = [_grid_faces(nr, nt, 0)]
    cb, ct = len(V), len(V) + 1
    V = np.vstack([V, [0, 0, 0], [0, 0, ztip]])
    j = np.arange(nt); jn = (j + 1) % nt
    F.append(np.stack([np.full(nt, cb), jn, j], 1))
    top = (nr - 1) * nt
    F.append(np.stack([np.full(nt, ct), top + j, top + jn], 1))
    return trimesh.Trimesh(V, np.concatenate(F), process=True)


def _ring_part(th, outer_rings, inner_rings):
    """Rengasmainen kappale: ulko- ja sisäpinta (samat z-päät) + ylä/alarenkaat."""
    Vo = _rings_to_xyz(th, outer_rings).reshape(-1, 3)
    Vi = _rings_to_xyz(th, inner_rings).reshape(-1, 3)
    nt = len(th)
    no, ni = len(outer_rings), len(inner_rings)
    off_i = len(Vo)
    F = [_grid_faces(no, nt, 0), _grid_faces(ni, nt, off_i, inward=True),
         _annulus(0, off_i, nt, up=False),
         _annulus((no - 1) * nt, off_i + (ni - 1) * nt, nt, up=True)]
    return trimesh.Trimesh(np.vstack([Vo, Vi]), np.concatenate(F), process=True)


def make_nut(size, clearance=None, mode="iso"):
    mode = _mode(mode)
    d, (P_iso, s, _k, m, *_r) = _size(size)
    P = pitch_of(size, mode)
    if clearance is None:
        clearance = default_clearance(size, mode)
    th = _theta()
    outer = []
    for z in _zsamples(0, m, m / 12):
        r = hex_radius(th, s)
        dist = min(z, m - z)
        r = np.minimum(r, s / 2 * 0.98 + dist * math.sqrt(3))  # 30° viisteet
        outer.append((z, r))
    chamfer = min(0.5 * P, 0.22 * m) if mode == "print" else 0.1 * P
    r_bore = d / 2 + clearance / 2  # sisäkierteen pohja (suurin reikä ilman viistettä)
    inner = []
    for z in _zsamples(0, m, P / 16):
        r = thread_radius(th, z, d, P, False, clearance, mode)
        dist = min(z, m - z)
        r = np.maximum(r, r_bore + chamfer - dist)  # sisäänmeno, 45° tulostustilassa
        inner.append((z, r))
    return _ring_part(th, outer, inner)


def make_capnut(size, clearance=None, mode="iso"):
    mode = _mode(mode)
    d, (P_iso, *_r) = _size(size)
    P = pitch_of(size, mode)
    if clearance is None:
        clearance = default_clearance(size, mode)
    s, h, m, t = CAPNUT[size.upper()]
    th = _theta()
    nt = len(th)
    R = s / 2 * 0.98
    zc = h - R  # kuvun keskipiste
    outer = []
    for z in _zsamples(0, m, m / 12):
        outer.append((z, np.minimum(hex_radius(th, s), s / 2 * 0.98 + z * math.sqrt(3))))
    if zc > m:
        outer.append((m, np.full_like(th, R)))
        outer.append((zc, np.full_like(th, R)))
    for a in np.linspace(0, np.pi / 2, 25)[1:-1]:
        z = zc + R * math.sin(a)
        if z > m:
            outer.append((z, np.full_like(th, R * math.cos(a))))
    chamfer = 0.5 * P if mode == "print" else 0.1 * P
    r_bore = d / 2 + clearance / 2
    inner = []
    zs_th = _zsamples(0, t, P / 16)
    for z in zs_th:
        r = thread_radius(th, z, d, P, False, clearance, mode)
        r = np.maximum(r, r_bore + chamfer - z)
        inner.append((z, r))
    # Poran säde hieman sisäkierteen pohjaa (pienin r) pienempi, umpinainen pohja
    rd = thread_root_radius(d, P, clearance, mode, external=False) - 0.08
    if abs(inner[-1][0] - t) < 1e-12:
        # sama z kuin viimeinen kierresilmukka: vain jos rd on selvästi pienempi
        inner.append((t, np.full_like(th, min(rd, np.min(inner[-1][1]) - 0.04))))
    else:
        inner.append((t, np.full_like(th, rd)))
    rd = inner[-1][1][0]
    for f in (0.66, 0.33):
        inner.append((t + (1 - f) * rd * math.tan(math.radians(31)), np.full_like(th, rd * f)))
    apex_in = t + rd * math.tan(math.radians(31))
    Vo = _rings_to_xyz(th, outer).reshape(-1, 3)
    Vi = _rings_to_xyz(th, inner).reshape(-1, 3)
    no, ni, oi = len(outer), len(inner), len(Vo)
    V = np.vstack([Vo, Vi, [0, 0, h], [0, 0, apex_in]])
    ao, ai = len(V) - 2, len(V) - 1
    j = np.arange(nt); jn = (j + 1) % nt
    to, ti = (no - 1) * nt, oi + (ni - 1) * nt
    F = [_grid_faces(no, nt, 0), _grid_faces(ni, nt, oi, inward=True),
         _annulus(0, oi, nt, up=False),
         np.stack([np.full(nt, ao), to + j, to + jn], 1),
         np.stack([np.full(nt, ai), ti + jn, ti + j], 1)]
    return trimesh.Trimesh(V, np.concatenate(F), process=True)


def make_washer(size, clearance=None, mode="iso"):
    _d, (*_x, d1, d2, h) = _size(size)
    if clearance is None:
        clearance = 0.2
    th = _theta()
    outer = [(0, np.full_like(th, d2 / 2)), (h, np.full_like(th, d2 / 2))]
    inner = [(0, np.full_like(th, d1 / 2 + clearance / 2)), (h, np.full_like(th, d1 / 2 + clearance / 2))]
    return _ring_part(th, outer, inner)


def _name_suffix(mode, kind):
    if kind != "washer" and _mode(mode) == "print":
        return "_tulostus"
    return ""


def generate(kind, size, length=None, thread_length=None, clearance=None, out=None, mode="iso"):
    size = size.upper()
    mode = _mode(mode)
    if clearance is None and kind != "washer":
        clearance = default_clearance(size, mode)
    elif clearance is None:
        clearance = 0.2
    suf = _name_suffix(mode, kind)
    if kind == "bolt":
        if not length:
            raise ValueError("Pultille pitää antaa pituus")
        mesh = make_bolt(size, length, thread_length, clearance, mode=mode)
        default = f"pultti_{size}x{length:g}{suf}.stl"
    elif kind == "nut":
        mesh = make_nut(size, clearance, mode=mode)
        default = f"mutteri_{size}{suf}.stl"
    elif kind == "capnut":
        mesh = make_capnut(size, clearance, mode=mode)
        default = f"hattumutteri_{size}{suf}.stl"
    elif kind == "washer":
        mesh = make_washer(size, clearance)
        default = f"aluslevy_{size}.stl"
    else:
        raise ValueError(kind)
    out = out or default
    mesh.export(out)
    return out, mesh


def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    root = tk.Tk()
    root.title("Pultit – STL-generaattori")
    frm = ttk.Frame(root, padding=12)
    frm.grid()
    kinds = {"Pultti": "bolt", "Mutteri": "nut", "Hattumutteri": "capnut", "Aluslevy": "washer"}
    v_kind = tk.StringVar(value="Pultti")
    v_size = tk.StringVar(value="M8")
    v_len = tk.StringVar(value="30")
    v_thr = tk.StringVar(value="")
    v_mode = tk.StringVar(value=THREAD_LABELS["iso"])
    v_clr = tk.StringVar(value="0.2")
    last_auto = [0.2]

    mode_box = ttk.Combobox(frm, textvariable=v_mode, values=list(THREAD_LABELS.values()), state="readonly")
    rows = [("Tyyppi:", ttk.Combobox(frm, textvariable=v_kind, values=list(kinds), state="readonly")),
            ("Koko:", ttk.Combobox(frm, textvariable=v_size, values=list(SIZES), state="readonly")),
            ("Kierretyyppi:", mode_box),
            ("Pultin pituus (mm):", ttk.Entry(frm, textvariable=v_len)),
            ("Kierteen pituus (mm, tyhjä = koko pituus):", ttk.Entry(frm, textvariable=v_thr)),
            ("Tulostusvara / toleranssi (mm):", ttk.Entry(frm, textvariable=v_clr))]
    for i, (lbl, w) in enumerate(rows):
        ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky="w", pady=3, padx=(0, 10))
        w.grid(row=i, column=1, sticky="ew", pady=3)
    frm.columnconfigure(1, weight=1)
    root.minsize(540, 400)
    root.geometry("580x440")
    note = ttk.Label(
        frm,
        text="Tulostusystävällinen kierre ei sovi tavallisiin ISO-pultteihin tai -muttereihin.\n"
             "Käytä samaa kierretyyppiä pultissa ja mutterissa.",
        wraplength=520,
        foreground="#333",
    )
    note.grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=(4, 2))

    def current_mode():
        return "print" if v_mode.get() == THREAD_LABELS["print"] else "iso"

    def current_default():
        if v_kind.get() == "Aluslevy":
            return 0.2
        return default_clearance(v_size.get(), current_mode())

    def toggle(*_):
        is_bolt = v_kind.get() == "Pultti"
        is_washer = v_kind.get() == "Aluslevy"
        rows[3][1].config(state="normal" if is_bolt else "disabled")
        rows[4][1].config(state="normal" if is_bolt else "disabled")
        mode_box.config(state="disabled" if is_washer else "readonly")
        try:
            cur = float(v_clr.get().replace(",", "."))
        except ValueError:
            cur = last_auto[0]
        new_def = current_default()
        if abs(cur - last_auto[0]) < 1e-9:
            v_clr.set(str(new_def) if new_def != int(new_def) else str(int(new_def)))
            # pidä yksi desimaali
            v_clr.set(f"{new_def:g}")
        last_auto[0] = new_def

    v_kind.trace_add("write", toggle)
    v_size.trace_add("write", toggle)
    v_mode.trace_add("write", toggle)

    def create():
        try:
            kind = kinds[v_kind.get()]
            mode = current_mode()
            length = float(v_len.get().replace(",", ".")) if kind == "bolt" else None
            thr = float(v_thr.get().replace(",", ".")) if (kind == "bolt" and v_thr.get().strip()) else None
            clr = float(v_clr.get().replace(",", "."))
            suf = _name_suffix(mode, kind)
            name = {"bolt": f"pultti_{v_size.get()}x{length:g}{suf}" if length else "",
                    "nut": f"mutteri_{v_size.get()}{suf}",
                    "capnut": f"hattumutteri_{v_size.get()}{suf}",
                    "washer": f"aluslevy_{v_size.get()}"}[kind]
            path = filedialog.asksaveasfilename(defaultextension=".stl", initialfile=name + ".stl",
                                                filetypes=[("STL-tiedosto", "*.stl")])
            if not path:
                return
            root.config(cursor="watch"); root.update()
            out, mesh = generate(kind, v_size.get(), length, thr, clr, path, mode=mode)
            ext = mesh.extents
            messagebox.showinfo("Valmis", f"Tallennettu:\n{out}\n\nMitat: {ext[0]:.1f} × {ext[1]:.1f} × {ext[2]:.1f} mm\n"
                                          f"Umpinainen (watertight): {'kyllä' if mesh.is_watertight else 'EI'}")
        except Exception as e:
            messagebox.showerror("Virhe", str(e))
        finally:
            root.config(cursor="")

    ttk.Button(frm, text="Luo STL…", command=create).grid(row=len(rows) + 1, column=0, columnspan=2, pady=10)
    root.mainloop()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return run_gui()
    p = argparse.ArgumentParser(description="ISO-metristen pulttien, mutterien ja aluslevyjen STL-generaattori")
    p.add_argument("kind", choices=["bolt", "nut", "capnut", "washer"], help="bolt=pultti, nut=mutteri, capnut=hattumutteri, washer=aluslevy")
    p.add_argument("size", help="Koko: " + ", ".join(SIZES))
    p.add_argument("--length", "-l", type=float, help="Pultin varren pituus mm (kannan alta)")
    p.add_argument("--thread-length", "-t", type=float, help="Kierteen pituus mm (oletus: koko pituus)")
    p.add_argument("--thread", choices=["iso", "print"], default="iso",
                   help="Kierreprofiili: iso (oletus, tarkka 60°) tai print (tulostusystävällinen)")
    p.add_argument("--clearance", "-c", type=float, default=None,
                   help="Tulostusvara mm (oletus 0.2 iso, 0.2–0.4 print koon mukaan)")
    p.add_argument("--output", "-o", help="Tiedostonimi")
    a = p.parse_args(argv)
    out, mesh = generate(a.kind, a.size, a.length, a.thread_length, a.clearance, a.output, mode=a.thread)
    e = mesh.extents
    print(f"Tallennettu {out}  ({e[0]:.2f} x {e[1]:.2f} x {e[2]:.2f} mm, "
          f"{len(mesh.faces)} kolmiota, watertight={mesh.is_watertight}, kierre={a.thread})")


if __name__ == "__main__":
    main()
