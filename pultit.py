#!/usr/bin/env python3
"""Pultit - ISO-metristen pulttien, mutterien ja aluslevyjen STL-generaattori.

Käyttö:  python pultit.py            (avaa graafisen käyttöliittymän)
         python pultit.py bolt M8 --length 40
         python pultit.py nut M8
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
# DIN 1587 hattumutteri: (s, kokonaiskorkeus h, kuusiön korkeus m, kierresyvyys t)
# HUOM: likimääräiset arvot DIN 1587 -taulukon mukaan
CAPNUT = {
    "M3": (5.5, 7.0, 4.0, 4.5), "M4": (7.0, 8.0, 5.0, 5.5), "M5": (8.0, 10.0, 6.0, 7.0),
    "M6": (10.0, 12.0, 7.0, 8.0), "M8": (13.0, 15.0, 9.0, 11.0),
    "M10": (16.0, 18.0, 11.0, 13.0), "M12": (18.0, 22.0, 13.0, 16.0),
}
N_THETA = 96  # jaollinen 6:lla -> kuusiokulmat osuvat tarkasti verteksiin


def _size(name):
    name = name.upper()
    if name not in SIZES:
        raise ValueError(f"Tuntematon koko {name}. Vaihtoehdot: {', '.join(SIZES)}")
    return int(name[1:]), SIZES[name]


def _theta(n=N_THETA):
    return np.linspace(0, 2 * np.pi, n, endpoint=False)


def hex_radius(theta, s):
    """Kuusiön säde kulman funktiona (s = avainväli, kulmat 0°,60°,...)."""
    a = np.mod(theta + np.pi / 6, np.pi / 3) - np.pi / 6
    return (s / 2) / np.cos(a)


def thread_radius(theta, z, d, P, external, clearance):
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


def make_bolt(size, length, thread_length=None, clearance=0.2, head_chamfer=True):
    d, (P, s, k, *_rest) = _size(size)
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
    r_root = d / 2 - 17 * (math.sqrt(3) / 2 * P) / 24 - clearance / 2
    zs = []
    if zthr0 > k:
        zs += list(_zsamples(k, zthr0, P / 2))
    zs += list(_zsamples(max(zthr0, k), ztip, zstep))
    zs = np.unique(np.round(zs, 9))
    for z in zs:
        if z < zthr0 - 1e-9:
            r = np.full_like(th, r_shank)
        else:
            r = thread_radius(th, z, d, P, True, clearance)
            r = np.minimum(r, np.maximum(r_shank, d / 2) )
            r = np.minimum(r, r_root + (ztip - z))          # 45° kärkiviiste
            r = np.minimum(r, r_shank + (z - zthr0) * 2) if zthr0 > k else r  # kierteen loppu
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


def make_nut(size, clearance=0.2):
    d, (P, s, _k, m, *_r) = _size(size)
    th = _theta()
    outer = []
    for z in _zsamples(0, m, m / 12):
        r = hex_radius(th, s)
        dist = min(z, m - z)
        r = np.minimum(r, s / 2 * 0.98 + dist * math.sqrt(3))  # 30° viisteet
        outer.append((z, r))
    inner = []
    for z in _zsamples(0, m, P / 16):
        r = thread_radius(th, z, d, P, False, clearance)
        dist = min(z, m - z)
        r = np.maximum(r, d / 2 + clearance / 2 + 0.1 * P - dist)  # sisäviisteet
        inner.append((z, r))
    return _ring_part(th, outer, inner)


def make_capnut(size, clearance=0.2):
    d, (P, *_r) = _size(size)
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
    inner = []
    for z in _zsamples(0, t, P / 16):
        r = thread_radius(th, z, d, P, False, clearance)
        r = np.maximum(r, d / 2 + clearance / 2 + 0.1 * P - z)
        inner.append((z, r))
    rd = d / 2 - 5 * math.sqrt(3) / 2 * P / 8 + clearance / 2 - 0.05  # poran säde
    inner.append((t, np.full_like(th, rd)))
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


def make_washer(size, clearance=0.2):
    _d, (*_x, d1, d2, h) = _size(size)
    th = _theta()
    outer = [(0, np.full_like(th, d2 / 2)), (h, np.full_like(th, d2 / 2))]
    inner = [(0, np.full_like(th, d1 / 2 + clearance / 2)), (h, np.full_like(th, d1 / 2 + clearance / 2))]
    return _ring_part(th, outer, inner)


def generate(kind, size, length=None, thread_length=None, clearance=0.2, out=None):
    size = size.upper()
    if kind == "bolt":
        if not length:
            raise ValueError("Pultille pitää antaa pituus")
        mesh = make_bolt(size, length, thread_length, clearance)
        default = f"pultti_{size}x{length:g}.stl"
    elif kind == "nut":
        mesh = make_nut(size, clearance)
        default = f"mutteri_{size}.stl"
    elif kind == "capnut":
        mesh = make_capnut(size, clearance)
        default = f"hattumutteri_{size}.stl"
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
    v_clr = tk.StringVar(value="0.2")

    rows = [("Tyyppi:", ttk.Combobox(frm, textvariable=v_kind, values=list(kinds), state="readonly")),
            ("Koko:", ttk.Combobox(frm, textvariable=v_size, values=list(SIZES), state="readonly")),
            ("Pultin pituus (mm):", ttk.Entry(frm, textvariable=v_len)),
            ("Kierteen pituus (mm, tyhjä = koko pituus):", ttk.Entry(frm, textvariable=v_thr)),
            ("Tulostusvara / toleranssi (mm):", ttk.Entry(frm, textvariable=v_clr))]
    for i, (lbl, w) in enumerate(rows):
        ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky="w", pady=3)
        w.grid(row=i, column=1, sticky="ew", pady=3)

    def toggle(*_):
        st = "normal" if v_kind.get() == "Pultti" else "disabled"
        rows[2][1].config(state=st); rows[3][1].config(state=st)
    v_kind.trace_add("write", toggle)

    def create():
        try:
            kind = kinds[v_kind.get()]
            length = float(v_len.get().replace(",", ".")) if kind == "bolt" else None
            thr = float(v_thr.get().replace(",", ".")) if (kind == "bolt" and v_thr.get().strip()) else None
            clr = float(v_clr.get().replace(",", "."))
            name = {"bolt": f"pultti_{v_size.get()}x{length:g}" if length else "",
                    "nut": f"mutteri_{v_size.get()}", "capnut": f"hattumutteri_{v_size.get()}", "washer": f"aluslevy_{v_size.get()}"}[kind]
            path = filedialog.asksaveasfilename(defaultextension=".stl", initialfile=name + ".stl",
                                                filetypes=[("STL-tiedosto", "*.stl")])
            if not path:
                return
            root.config(cursor="watch"); root.update()
            out, mesh = generate(kind, v_size.get(), length, thr, clr, path)
            ext = mesh.extents
            messagebox.showinfo("Valmis", f"Tallennettu:\n{out}\n\nMitat: {ext[0]:.1f} × {ext[1]:.1f} × {ext[2]:.1f} mm\n"
                                          f"Umpinainen (watertight): {'kyllä' if mesh.is_watertight else 'EI'}")
        except Exception as e:
            messagebox.showerror("Virhe", str(e))
        finally:
            root.config(cursor="")

    ttk.Button(frm, text="Luo STL…", command=create).grid(row=len(rows), column=0, columnspan=2, pady=10)
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
    p.add_argument("--clearance", "-c", type=float, default=0.2, help="Tulostusvara mm (oletus 0.2)")
    p.add_argument("--output", "-o", help="Tiedostonimi")
    a = p.parse_args(argv)
    out, mesh = generate(a.kind, a.size, a.length, a.thread_length, a.clearance, a.output)
    e = mesh.extents
    print(f"Tallennettu {out}  ({e[0]:.2f} x {e[1]:.2f} x {e[2]:.2f} mm, "
          f"{len(mesh.faces)} kolmiota, watertight={mesh.is_watertight})")


if __name__ == "__main__":
    main()
