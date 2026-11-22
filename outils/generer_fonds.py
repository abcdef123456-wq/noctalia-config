#!/usr/bin/env python3
"""generer_fonds : les fonds d'écran des thèmes, dessinés par nous (art procédural), 3840x2400 (16:10).

Outil du dépôt, pas un script installé : il demande numpy et Pillow. Les images livrées sont dans
home/Pictures/Wallpapers/<thème>/ (crédits : CREDITS.tsv, « généré par noctalia-config »).

Usage : python3 outils/generer_fonds.py DOSSIER [nom...]   (sans nom : tout)
Sortie : DOSSIER/png/<nom>.png (contrôle) et DOSSIER/jpg/<nom>.jpg (final, qualité 92, 4:4:4). DOSSIER est
obligatoire et ne doit pas être dans le dépôt : rien n'est jamais généré ici. Graine fixe par image : résultat
reproductible.
"""
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

W, H = 3840, 2400
ICI = ""       # le dossier de sortie, donné en premier argument
F32 = np.float32


# --------------------------------------------------------------------------
# Outils de base
# --------------------------------------------------------------------------
def hexc(s):
    """'#rrggbb' -> tableau float 0..1."""
    return np.array([int(s[i:i + 2], 16) for i in (1, 3, 5)], F32) / 255


def interp_stops(t, stops):
    """Dégradé multi-arrêts [(pos, '#hex'), ...] appliqué à un tableau t."""
    pos = [p for p, _ in stops]
    cols = np.stack([hexc(c) for _, c in stops])
    return np.stack([np.interp(t, pos, cols[:, k]) for k in range(3)], -1).astype(F32)


def vgrad(stops, h=H, w=W):
    """Dégradé vertical plein cadre."""
    col = interp_stops(np.linspace(0, 1, h), stops)
    return np.repeat(col[:, None, :], w, 1)


def mix(base, col, a):
    """Mélange base -> col avec un alpha 2D (modifie et renvoie base)."""
    a = np.asarray(a, F32)[..., None]
    base += (np.asarray(col, F32) - base) * a
    return base


def add(base, col, a):
    """Mélange additif (lumière)."""
    base += np.asarray(col, F32) * np.asarray(a, F32)[..., None]
    return base


def resize(a, w, h):
    """Redimensionne un tableau 2D float (bicubique)."""
    return np.array(Image.fromarray(a.astype(F32), "F").resize((w, h), Image.Resampling.BICUBIC), F32)


def resize3(a, w, h):
    return np.stack([resize(a[..., k], w, h) for k in range(3)], -1)


def blur(a, sigma):
    """Flou gaussien 2D par FFT, calculé sur une version réduite."""
    h, w = a.shape
    f = max(1, int(sigma // 3))
    while h % f or w % f:
        f -= 1
    small = a.reshape(h // f, f, w // f, f).mean((1, 3)) if f > 1 else a
    s = sigma / f
    pad = int(3 * s) + 2
    p = np.pad(small, pad, mode="reflect")
    fy = np.fft.fftfreq(p.shape[0])[:, None]
    fx = np.fft.rfftfreq(p.shape[1])[None, :]
    g = np.exp(-2 * np.pi ** 2 * s * s * (fx * fx + fy * fy))
    r = np.fft.irfft2(np.fft.rfft2(p) * g, p.shape)[pad:-pad, pad:-pad]
    return resize(r, w, h) if f > 1 else r.astype(F32)


def fbm(w, h, rng, base=4, octaves=5, gain=0.5):
    """Bruit fractal lisse normalisé dans [0,1], de taille (h, w)."""
    out = np.zeros((h, w), F32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        r = rng.random((max(2, int(n * h / w)) + 1, n + 1)).astype(F32)
        out += amp * resize(r, w, h)
        tot += amp
        amp *= gain
    out /= tot
    return np.clip((out - out.min()) / (out.max() - out.min()), 0, 1)


def fbm1d(n, rng, base=4, octaves=6, gain=0.5):
    """Bruit fractal 1D dans [-1,1] (profils de montagnes, dunes)."""
    out = np.zeros(n, F32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        r = rng.random((1, base * 2 ** o + 3)).astype(F32)
        out += amp * resize(r, n, 1)[0]
        tot += amp
        amp *= gain
    out /= tot
    return (out - out.min()) / (out.max() - out.min()) * 2 - 1


def vignette(img, force=0.35, puissance=2.2):
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    r = np.hypot((x - W / 2) / (W / 2), (y - H / 2) / (H / 2)) / 1.414
    img *= (1 - force * np.clip(r, 0, 1) ** puissance)[..., None]
    return img


def etoiles(img, rng, n, ymax, couleur, force=1.0):
    """Étoiles : points aléatoires légèrement floutés, quelques grosses."""
    m = np.zeros((H, W), F32)
    ys = (rng.random(n) ** 0.8 * ymax).astype(int)
    xs = rng.integers(0, W, n)
    m[ys, xs] = rng.random(n) ** 2.5 * 0.9 + 0.1
    petites = blur(m, 1.0) * 5
    gros = np.zeros((H, W), F32)
    k = max(3, n // 40)
    gros[(rng.random(k) * ymax * 0.8).astype(int), rng.integers(0, W, k)] = 1
    gros = blur(gros, 2.2) * 40
    return add(img, couleur, np.clip(petites + gros, 0, 1) * force)


def ligne_aa(f, df, lw):
    """Ligne antialiasée : f = champ (lignes aux entiers), df = pente par pixel."""
    d = np.abs(f - np.round(f)) / np.maximum(df, 1e-6)
    a = np.clip(lw / 2 + 0.5 - d, 0, 1)
    return a * np.clip(1 - (df - 0.25) / 0.35, 0, 1)  # fondu quand les lignes se tassent


def sol_perspective(y0, cx=W / 2, k_h=10600.0, c_v=7.2):
    """Grille de sol en perspective sous l'horizon y0.
    Renvoie (alpha lignes horizontales, alpha lignes verticales, profondeur 0..1)."""
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    t = np.maximum(y - y0, 0.5)
    lw = 1.6 + 3.0 * np.clip(t / (H - y0), 0, 1)
    fh = k_h / t
    ah = ligne_aa(fh, k_h / t ** 2, lw)
    fv = (x - cx) * c_v / t
    dv = np.hypot(c_v / t, (x - cx) * c_v / t ** 2)
    av = ligne_aa(fv, dv, lw)
    sol = (y > y0).astype(F32)
    return ah * sol, av * sol, np.clip(t / (H - y0), 0, 1)


def sauver(img, nom, bruit=0.55, seed=0):
    """Tramage (bruit gaussien < 1 niveau) puis PNG + JPEG 4:4:4 q92."""
    rng = np.random.default_rng(seed + 999)
    out = np.clip(img, 0, 1) * 255 + rng.normal(0, bruit, img.shape).astype(F32)
    im = Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGB")
    os.makedirs(os.path.join(ICI, "png"), exist_ok=True)
    os.makedirs(os.path.join(ICI, "jpg"), exist_ok=True)
    im.save(os.path.join(ICI, "png", nom + ".png"), compress_level=3)
    im.save(os.path.join(ICI, "jpg", nom + ".jpg"), quality=92, subsampling=0, optimize=True)


# --------------------------------------------------------------------------
# 1. Rétro terminal
# --------------------------------------------------------------------------
def retro_grille():
    rng = np.random.default_rng(11)
    vert, fond = hexc("#33ff66"), hexc("#0a0f0a")
    y0 = H * 0.54
    img = vgrad([(0, "#070b07"), (0.54, "#0d150d"), (1, "#0a0f0a")])
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    # halo discret à l'horizon
    glow = np.exp(-((y - y0) / 260) ** 2) * np.exp(-((x - W / 2) / 1900) ** 2)
    add(img, vert, glow * 0.2)
    add(img, vert, np.exp(-((y - y0) / 700) ** 2) * np.exp(-((x - W / 2) / 2400) ** 2) * 0.05)
    ah, av, prof = sol_perspective(y0, k_h=11500, c_v=8.5)
    # les lignes s'éteignent vers l'horizon (profondeur) et sur les bords
    fondu = np.clip(prof * 1.6, 0, 1) ** 1.4 * (0.35 + 0.65 * np.exp(-((x - W / 2) / 2200) ** 2))
    lignes = np.maximum(ah, av) * fondu
    lueur = blur(lignes, 9)
    mix(img, vert, np.clip(lignes * 0.55, 0, 1))
    add(img, vert, lueur * 0.9)
    # ligne d'horizon fine
    mix(img, vert, np.clip(1.2 - np.abs(y - y0) / 1.0, 0, 1) * 0.35 * np.exp(-((x - W / 2) / 1500) ** 2))
    # lignes de balayage très légères
    img *= (1 - 0.045 * (np.sin(y * np.pi / 3.0) * 0.5 + 0.5))[..., None]
    # léger scintillement lent (bandes larges)
    img *= (1 + 0.012 * np.sin(y / 70.0))[..., None]
    vignette(img, 0.55, 2.0)
    sauver(img, "retro-grille", seed=11)


def retro_ambre():
    rng = np.random.default_rng(12)
    amb, fond = hexc("#ffb000"), hexc("#0f0a00")
    img = np.broadcast_to(fond, (H, W, 3)).copy()
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    # relief : bruit fractal + un massif décentré
    relief = fbm(W // 2, H // 2, rng, base=3, octaves=5, gain=0.5)
    relief = resize(relief, W, H)
    relief += 0.5 * np.exp(-(((x - W * 0.78) / 900) ** 2 + ((y - H * 0.7) / 700) ** 2))
    relief += 0.35 * np.exp(-(((x - W * 0.15) / 800) ** 2 + ((y - H * 0.25) / 600) ** 2))
    n_niv = 26
    f = relief * n_niv
    gy, gx = np.gradient(f)
    df = np.hypot(gx, gy)
    fin = ligne_aa(f, df, 1.6)
    maitre = ligne_aa(f / 5, df / 5, 3.0)  # une courbe maîtresse sur cinq, plus épaisse
    lignes = np.maximum(fin * 0.55, maitre)
    # centre calme : les courbes s'estompent vers le milieu
    r = np.hypot((x - W / 2) / (W / 2), (y - H / 2) / (H / 2))
    masque = 0.12 + 0.88 * np.clip((r - 0.25) / 0.7, 0, 1) ** 1.3
    # anneaux de radar, très discrets, centrés en bas à droite
    rr = np.hypot(x - W * 0.78, (y - H * 0.7)) / 220
    anneaux = ligne_aa(rr, np.full_like(rr, 1 / 220), 1.5) * (rr < 7)
    anneaux *= np.clip(1 - rr / 7, 0, 1)
    ang = np.arctan2(y - H * 0.7, x - W * 0.78)
    rayons = ligne_aa(ang * 12 / np.pi, 12 / np.pi / np.maximum(rr * 220, 20), 1.4) * (rr < 7) * (rr > 0.6)
    mix(img, amb, np.clip(lignes * masque * 0.8, 0, 1))
    mix(img, amb, np.clip((anneaux + rayons * 0.6) * 0.5, 0, 1))
    add(img, amb, blur(lignes * masque, 8) * 0.35)
    img *= (1 - 0.04 * (np.sin(y * np.pi / 3.0) * 0.5 + 0.5))[..., None]
    vignette(img, 0.6, 2.0)
    sauver(img, "retro-ambre", seed=12)


# --------------------------------------------------------------------------
# 2. Synthwave
# --------------------------------------------------------------------------
def synthwave_soleil():
    rng = np.random.default_rng(21)
    rose, cyan, jaune = hexc("#ff7edb"), hexc("#36f9f6"), hexc("#fede5d")
    y0 = H * 0.58
    ciel = [(0, "#1a1326"), (0.25, "#241b2f"), (0.45, "#3d2262"), (0.58, "#a23a96")]
    img = vgrad(ciel[:3] + [(0.58, "#a23a96"), (1.0, "#1b1226")])
    # sol : on redessine sous l'horizon
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    sol = vgrad([(0, "#a23a96"), (0.58, "#7a2f88"), (0.66, "#3f1d5e"), (0.8, "#2a1645"), (1, "#190f2a")])
    img = np.where((y > y0)[..., None], sol, img)
    etoiles(img, rng, 900, y0 * 0.75, hexc("#e8dcff"), 0.9 * 1)
    # le ciel s'éclaircit en haut à l'horizon : on re-masque les étoiles trop bas
    cx, cy, R = W / 2, 1000.0, 560.0
    d = np.hypot(x - cx, y - cy)
    # halo large derrière le soleil
    add(img, rose, np.exp(-(d / 900) ** 2) * 0.28 * (y < y0))
    add(img, jaune, np.exp(-(d / 520) ** 2) * 0.10 * (y < y0))
    # soleil : dégradé jaune -> rose, bandes de plus en plus épaisses vers le bas
    disque = np.clip(R - d + 0.5, 0, 1)
    t = np.clip((y - (cy - R)) / (2 * R), 0, 1)
    sun = interp_stops(t, [(0, "#fff0a0"), (0.35, "#fede5d"), (0.7, "#ff9e8a"), (1, "#ff5fc0")])
    s = (y - cy) / R
    periode = 78.0
    ph = np.mod(y - cy, periode)
    coupe = np.clip(s, 0, 1) * periode * 0.62
    bande = np.where(s > 0.08, np.clip(coupe - ph + 0.5, 0, 1), 0)
    mix(img, sun, disque * (1 - bande))
    # horizon : ligne lumineuse + brume
    add(img, rose, np.exp(-((y - y0) / 55) ** 2) * 0.32 * np.exp(-((x - cx) / 1700) ** 2))
    # sol : grille cyan (verticales) et rose (horizontales)
    ah, av, prof = sol_perspective(y0)
    f = np.clip(prof * 2.2, 0, 1) ** 1.2
    lueur = blur(av + ah, 10)
    mix(img, cyan, np.clip(av * f * 0.85, 0, 1))
    mix(img, rose, np.clip(ah * f * 0.85, 0, 1))
    add(img, cyan * 0.5 + rose * 0.5, lueur * f * 0.55)
    # reflet du soleil au sol
    add(img, rose, np.exp(-((x - cx) / 420) ** 2) * np.exp(-((y - y0) / 380) ** 2) * (y > y0) * 0.22)
    vignette(img, 0.5, 2.0)
    sauver(img, "synthwave-soleil", seed=21)


def _crete(rng, base, amp, octaves=6, nets=0.0, base_n=3):
    """Profil de crête (hauteur y par colonne) : bruit fractal, un peu anguleux."""
    n = fbm1d(W, rng, base_n, octaves, 0.52)
    r = 1 - np.abs(n)  # arêtes
    return base - amp * (0.55 * (n * 0.5 + 0.5) + 0.45 * r ** 1.5)


def synthwave_montagnes():
    rng = np.random.default_rng(22)
    rose, cyan, jaune = hexc("#ff7edb"), hexc("#36f9f6"), hexc("#fede5d")
    y0 = H * 0.70
    img = vgrad([(0, "#171020"), (0.3, "#241b2f"), (0.5, "#4a2468"), (0.64, "#b8449f"),
                 (0.70, "#ff7edb"), (1, "#ff7edb")])
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    etoiles(img, rng, 700, H * 0.42, hexc("#e8dcff"), 0.85)
    # lueur d'horizon chaude, centrée
    add(img, jaune, np.exp(-((y - y0) / 230) ** 2) * np.exp(-((x - W / 2) / 1100) ** 2) * 0.16)
    add(img, rose, np.exp(-((y - y0) / 480) ** 2) * 0.22)
    couches = [
        # base, amplitude, couleur, couleur de crête
        (0.74, 330, "#7a3a94", cyan),
        (0.79, 380, "#4a2468", rose),
        (0.86, 330, "#2c1646", cyan),
        (0.95, 240, "#1b0f2c", rose),
    ]
    for i, (b, a, col, rim) in enumerate(couches):
        yc = _crete(rng, H * b, a, 6 + i // 2)
        # on creuse le centre : les montagnes s'abaissent pour laisser respirer le ciel
        u = np.abs(x[0] / W - 0.5) * 2
        yc = yc + (1 - u ** 1.5) * (70 + 25 * i)
        d = y - yc[None, :]
        masque = np.clip(d + 0.5, 0, 1)
        # dégradé relatif à la crête : clair au sommet, sombre en profondeur
        fond = hexc(col) + (hexc("#0d0716") - hexc(col)) * np.clip(d / 650, 0, 1)[..., None]
        mix(img, fond, masque)
        # arête lumineuse fine (fil de fer) + halo
        arete = np.clip(1.6 - np.abs(d) / 1.0, 0, 1) * 0.9
        add(img, rim, arete * (0.85 - 0.1 * i))
        add(img, rim, blur(arete, 14) * 1.6 * (0.55 - 0.1 * i))
        # voile de brume entre les plans
        mix(img, hexc("#b8449f"), np.clip(1 - d / 420, 0, 1) * masque * (0.22 - 0.05 * i))
    vignette(img, 0.5, 2.0)
    sauver(img, "synthwave-montagnes", seed=22)


# --------------------------------------------------------------------------
# 3. Tokyo Night
# --------------------------------------------------------------------------
def _plan_immeubles(rng, d, y_h, lm, hmin, hmax, p_tour):
    """Dessine un plan d'immeubles (silhouette + antennes + fenêtres) avec PIL.
    Renvoie (masque L, fenêtres RGBA) à pleine taille. d = dessin du plan."""
    sil = Image.new("L", (W, H), 0)
    fen = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds, df = ImageDraw.Draw(sil), ImageDraw.Draw(fen)
    cw, ch = d["fen"]
    x = -int(rng.integers(0, lm))
    while x < W:
        w = int(lm * rng.uniform(0.55, 1.7))
        u = abs((x + w / 2) / W - 0.5) * 2          # 0 au centre, 1 au bord
        env = d["centre"] + (1 - d["centre"]) * u ** 1.3
        hh = (hmin + (hmax - hmin) * rng.random() ** 1.8) * env
        if rng.random() < p_tour:                     # quelques tours très hautes
            hh *= rng.uniform(1.5, 2.1)
        hh = min(hh, y_h - H * 0.13)
        haut = y_h - hh
        # corps + toit(s) en gradins
        tiers = [(x, x + w, haut)]
        for _ in range(int(rng.integers(0, 3))):
            if rng.random() < 0.55 and tiers[-1][1] - tiers[-1][0] > 5 * cw:
                a, b, t = tiers[-1]
                m = int((b - a) * rng.uniform(0.12, 0.28))
                tiers.append((a + m, b - m, t - rng.uniform(0.06, 0.16) * hh))
        for (a, b, t) in tiers:
            ds.rectangle([a, t, b, y_h + 50], fill=255)
        # antenne ou flèche
        if rng.random() < d["antenne"]:
            a, b, t = tiers[-1]
            cx = int((a + b) / 2 + rng.uniform(-0.2, 0.2) * (b - a))
            hl = rng.uniform(70, 260) * d["echelle"]
            ds.rectangle([cx - 2 * d["echelle"], t - hl, cx + 2 * d["echelle"], t + 2], fill=255)
            if rng.random() < 0.5:  # traverse de l'antenne
                ds.rectangle([cx - 9 * d["echelle"], t - hl * 0.6, cx + 9 * d["echelle"], t - hl * 0.6 + 3], fill=255)
        # fenêtres : par étage (certains éteints), cellules irrégulières
        biais = rng.uniform(0.08, 0.55) * d["allume"]
        for (a, b, t) in tiers:
            nc = int((b - a - 2 * cw) // (cw * 1.8))
            for fl in range(int((y_h - t - 30) // (ch * 1.9))):
                if rng.random() < 0.4:      # étage éteint
                    continue
                yy = t + 24 + fl * ch * 1.9
                for c in range(nc):
                    if rng.random() > biais * 1.5:
                        continue
                    r = rng.random()
                    col = (255, 214, 140) if r < 0.82 else ((140, 220, 255) if r < 0.93 else (255, 150, 170))
                    k = rng.uniform(0.55, 1.0)
                    xx = a + cw + c * cw * 1.8
                    df.rectangle([xx, yy, xx + cw, yy + ch], fill=tuple(int(v * k) for v in col) + (255,))
        x += w + int(rng.integers(0, 6))
    return sil, fen


def tokyo_ville():
    rng = np.random.default_rng(31)
    magenta, cyan = hexc("#f7768e"), hexc("#7dcfff")
    y_h = int(H * 0.76)                    # ligne d'horizon / bord du sol mouillé
    img = vgrad([(0, "#0b0d1c"), (0.28, "#141a38"), (0.46, "#232d62"), (0.60, "#4a4a92"), (0.70, "#8a62a6"), (0.76, "#b57fae"), (1, "#b57fae")])
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    etoiles(img, rng, 450, H * 0.35, hexc("#c0caf5"), 0.55)
    add(img, hexc("#7aa2f7"), np.exp(-(np.hypot(x - W * 0.66, y - H * 0.24) / 480) ** 2) * 0.10)
    # cinq plans, du plus lointain (clair, bleu, brumeux) au plus proche (sombre, net)
    plans = [
        dict(lm=170, hmin=520, hmax=980, p=0.10, col="#6a78b8", fen=(5, 7), allume=0.5, echelle=0.5, antenne=0.15, centre=0.8, brume=0.30, win=0.30),
        dict(lm=200, hmin=420, hmax=1000, p=0.12, col="#4d5a9c", fen=(6, 9), allume=0.6, echelle=0.7, antenne=0.20, centre=0.7, brume=0.26, win=0.45),
        dict(lm=240, hmin=280, hmax=900, p=0.14, col="#363f78", fen=(8, 11), allume=0.8, echelle=0.9, antenne=0.25, centre=0.6, brume=0.22, win=0.62),
        dict(lm=300, hmin=200, hmax=900, p=0.14, col="#222850", fen=(10, 14), allume=0.9, echelle=1.1, antenne=0.25, centre=0.5, brume=0.16, win=0.8),
        dict(lm=380, hmin=140, hmax=700, p=0.10, col="#10122a", fen=(13, 18), allume=1.0, echelle=1.3, antenne=0.20, centre=0.4, brume=0.0, win=1.0),
    ]
    brume_col = hexc("#8a62a6")
    for i, d in enumerate(plans):
        sil, fen = _plan_immeubles(rng, d, y_h, d["lm"], d["hmin"], d["hmax"], d["p"])
        m = np.asarray(sil, F32) / 255
        if i < 3:
            m = blur(m, 1.4)  # lointain : contours adoucis
        mix(img, hexc(d["col"]), m)
        fa = np.asarray(fen, F32) / 255
        wm = fa[..., 3]
        if i < 3:
            wm = blur(wm, 1.2)
        wcol = fa[..., :3]
        mix(img, wcol, np.clip(wm * d["win"], 0, 1))
        if i >= 3:  # petite lueur chaude autour des fenêtres proches
            lueur = np.stack([blur(fa[..., k] * wm, 5) for k in range(3)], -1)
            img += lueur * 0.35
        # enseignes néon floues sur les plans proches
        if i >= 2:
            ne = Image.new("RGB", (W, H), (0, 0, 0))
            dn = ImageDraw.Draw(ne)
            for _ in range(6 if i == 4 else 4):
                nx = int(rng.choice([rng.uniform(0.04, 0.34), rng.uniform(0.66, 0.96)]) * W)
                ny = int(y_h - rng.uniform(0.25, 0.75) * d["hmax"] * d["centre"])
                col = (247, 118, 142) if rng.random() < 0.5 else (125, 207, 255)
                sc = d["echelle"]
                if rng.random() < 0.6:   # enseigne verticale
                    dn.rectangle([nx, ny, nx + 16 * sc, ny + rng.uniform(110, 230) * sc], fill=col)
                else:                    # enseigne horizontale
                    dn.rectangle([nx, ny, nx + rng.uniform(90, 200) * sc, ny + 14 * sc], fill=col)
            na = np.asarray(ne, F32) / 255
            core = np.stack([blur(na[..., k], 3) for k in range(3)], -1)
            halo = np.stack([blur(na[..., k], 28) for k in range(3)], -1)
            large = np.stack([blur(na[..., k], 90) for k in range(3)], -1)
            img += core * 0.8 + halo * 1.9 + large * 1.7
        # brume entre ce plan et le suivant : plus dense près de l'horizon
        mix(img, brume_col, np.exp(-(y_h - y).clip(0) / 520) * d["brume"] * (y < y_h))
    # sol mouillé : reflet flou et assombri de la ville, avec rides
    n = H - y_h
    src = img[y_h - n:y_h][::-1].copy()
    src = resize3(src, W // 10, n)            # flou horizontal fort (bicubique)
    src = resize3(src, W, n)
    src = np.stack([blur(src[..., k], 6) for k in range(3)], -1)
    prof = np.linspace(0, 1, n)[:, None, None]
    rides = 0.7 + 0.3 * resize(rng.random((n, 1)).astype(F32), 1, n)[:, :1]
    decal = (6 * np.sin(np.arange(n) * 0.09 + rng.random() * 6)).astype(int)
    src = np.stack([np.roll(src[k], int(decal[k]), axis=0) for k in range(n)])
    sol = vgrad([(0, "#2a2448"), (0.3, "#14122a"), (1, "#07070f")], n, W)
    refl = src * rides[..., None] * (1 - prof) ** 1.3 * 0.55
    img[y_h:] = sol + refl
    vignette(img, 0.42, 2.0)
    sauver(img, "tokyo-ville", seed=31)


def _bokeh(img, cx, cy, r, col, a):
    """Disque flou (bokeh) : cœur doux et anneau plus lumineux, sur une boîte locale."""
    m = int(r * 1.5)
    x0, x1, y0, y1 = max(0, int(cx - m)), min(W, int(cx + m)), max(0, int(cy - m)), min(H, int(cy + m))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(F32)
    d = np.hypot(xx - cx, yy - cy) / r
    bord = 0.05 + 0.5 * np.clip(1 - np.abs(d - 0.9) / 0.35, 0, 1) ** 2
    corps = np.clip(1 - d, 0, 1) ** 0.4 * np.clip((1.12 - d) / 0.12, 0, 1)
    prof = (0.35 + bord) * corps * (1 + 0.0) + 0
    img[y0:y1, x0:x1] += np.asarray(col, F32) * (a * prof)[..., None]


def tokyo_pluie():
    rng = np.random.default_rng(32)
    cols = [hexc(c) for c in ("#7aa2f7", "#bb9af7", "#f7768e", "#7dcfff", "#7aa2f7", "#bb9af7")]
    img = vgrad([(0, "#0e0f17"), (0.5, "#171824"), (1, "#1a1b26")])
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    # brume colorée de fond, très lisse
    brume = np.zeros((H // 4, W // 4, 3), F32)
    yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(F32) * 4
    for (px, py, c, s, a) in [(0.18, 0.75, 0, 1100, 0.20), (0.85, 0.3, 1, 1000, 0.20),
                              (0.7, 0.9, 2, 800, 0.14), (0.1, 0.15, 1, 800, 0.12)]:
        brume += cols[c] * (np.exp(-(((xx - px * W) ** 2 + (yy - py * H) ** 2) / s ** 2)) * a)[..., None]
    img += resize3(brume, W, H)
    # bokeh : surtout sur les bords, le centre reste calme
    nets = np.zeros_like(img)
    for _ in range(55):
        for _ in range(20):
            cx, cy = rng.random() * W, rng.random() * H
            u = np.hypot((cx - W / 2) / (W / 2), (cy - H / 2) / (H / 2))
            if rng.random() < np.clip((u - 0.25) / 0.6, 0.04, 1):
                break
        r = rng.choice([70, 110, 160, 230, 300], p=[0.3, 0.3, 0.2, 0.14, 0.06])
        _bokeh(nets, cx, cy, r, cols[rng.integers(len(cols))], rng.uniform(0.07, 0.24))
    # on floute très légèrement les plus grands : un second passage doux
    img += nets
    img += np.stack([blur(nets[..., k], 14) for k in range(3)], -1) * 0.6
    # traînées de pluie : fines lignes inclinées
    from PIL import ImageFilter
    pluie = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(pluie)
    for _ in range(900):
        px, py = rng.random() * (W + 600), rng.random() * (H + 400) - 200
        ln = rng.uniform(80, 340)
        dr.line([(px, py), (px - ln * 0.18, py + ln)], fill=int(rng.uniform(25, 90)), width=int(rng.choice([1, 2, 2, 3])))
    pluie = pluie.filter(ImageFilter.GaussianBlur(0.9))
    p = np.asarray(pluie, F32) / 255
    add(img, hexc("#a9b8ee"), p * (0.4 + 0.6 * np.clip(np.hypot((x - W / 2) / W, (y - H / 2) / H) * 1.8, 0, 1)))
    vignette(img, 0.5, 2.0)
    sauver(img, "tokyo-pluie", seed=32)


# --------------------------------------------------------------------------
# 4. Apple
# --------------------------------------------------------------------------
def _dune(rng, base, amp, freqs):
    """Crête lisse : somme de sinusoïdes à phases aléatoires + un peu de bruit."""
    x = np.linspace(0, 1, W, dtype=F32)
    y = np.zeros(W, F32)
    for k, f in enumerate(freqs):
        y += np.sin(2 * np.pi * (f * x + rng.random())) * (amp / (k + 1))
    y += fbm1d(W, rng, 2, 3, 0.4) * amp * 0.25
    return base + y


def apple_dunes():
    rng = np.random.default_rng(41)
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    img = vgrad([(0, "#0b1230"), (0.25, "#1a2a5c"), (0.5, "#5b79a8"), (0.62, "#e8b99a"), (1, "#f2c9a0")])
    # soleil bas, très doux, et lueur
    add(img, hexc("#ffd9a8"), np.exp(-(np.hypot(x - W * 0.72, y - H * 0.55) / 600) ** 2) * 0.35)
    etoiles(img, rng, 350, H * 0.3, hexc("#dbe6ff"), 0.55)
    couches = [
        # base, amplitude, fréquences, clair, ombre, brume
        (0.60, 110, [0.8, 1.7], "#b7a1a4", "#4c5f91", 0.55),
        (0.68, 150, [0.7, 1.5, 2.6], "#e6b58c", "#3f4f86", 0.35),
        (0.78, 190, [0.6, 1.3, 2.2], "#d99c6b", "#2a3769", 0.18),
        (0.90, 230, [0.5, 1.1, 1.9], "#b9784c", "#16204a", 0.0),
    ]
    for base, amp, fr, clair, ombre, brume in couches:
        yc = _dune(rng, H * base, amp, fr)
        # le centre reste plus bas et calme
        pente = np.gradient(yc)
        # lumière rasante venue de la droite : pente montante vers la droite = ombre
        lum = 0.5 - 0.5 * np.tanh(pente / 0.55)
        lum = np.convolve(np.pad(lum, 60, mode="edge"), np.ones(121) / 121, "valid")
        d = y - yc[None, :]
        masque = np.clip(d + 0.7, 0, 1)
        col = hexc(ombre)[None, None, :] + (hexc(clair) - hexc(ombre))[None, None, :] * lum[None, :, None]
        # on assombrit en profondeur (vers le bas) pour un volume doux
        prof = np.clip(d / 700, 0, 1)[..., None]
        col = col * (1 - 0.35 * prof)
        # crête illuminée : fin liseré chaud côté lumière
        liseret = np.clip(1 - d / 22, 0, 1) * np.clip(d, 0, 1)
        col = col + hexc("#ffe2bd")[None, None, :] * (liseret * lum[None, :] * 0.35)[..., None]
        col = np.broadcast_to(col, (H, W, 3))
        mix(img, col, masque)
        if brume:
            mix(img, hexc("#c9a7a0"), masque * np.clip(1 - d / 500, 0, 1) * brume)
    vignette(img, 0.25, 2.2)
    sauver(img, "apple-dunes", bruit=0.7, seed=41)


def apple_ondes():
    rng = np.random.default_rng(42)
    w, h = W // 4, H // 4
    y, x = np.mgrid[0:h, 0:w].astype(F32)
    u, v = x / w * 1.6, y / h  # u en 0..1.6 pour garder des proportions
    # déformation du domaine : ondes fluides
    uu = u + 0.14 * np.sin(v * 5.0 + 1.0) + 0.06 * np.sin(u * 6.5 + v * 2.5)
    vv = v + 0.12 * np.sin(u * 3.6 + 2.0) + 0.05 * np.sin(v * 7.0 + u * 3)
    points = [  # position (u, v), couleur, rayon
        (0.15, 0.20, "#2f6bff", 0.55), (1.45, 0.10, "#7b4cff", 0.55), (0.80, 0.55, "#1a2570", 0.65),
        (1.50, 0.85, "#ff9b66", 0.55), (0.30, 0.95, "#ff7fa6", 0.45), (0.95, 1.05, "#5a3ad0", 0.5),
        (0.05, 0.60, "#4a2fb8", 0.45), (1.15, 0.30, "#3d8bff", 0.4),
    ]
    num = np.zeros((h, w, 3), F32)
    den = np.zeros((h, w), F32)
    for (pu, pv, c, r) in points:
        wgt = np.exp(-(((uu - pu) ** 2 + (vv - pv) ** 2) / r ** 2) * 2.2) + 1e-4
        num += hexc(c) * wgt[..., None]
        den += wgt
    img = num / den[..., None]
    # passe 2 : moins saturé, moins boueux (on tire vers le gris-bleu clair)
    gris = img.mean(-1, keepdims=True)
    img = (gris + (img - gris) * 0.82) * 1.06
    # rubans lumineux doux qui suivent les ondes
    ruban = np.sin((uu * 2.2 + vv * 3.0) * np.pi) * 0.5 + 0.5
    img += hexc("#ffd1b0") * (ruban ** 6 * 0.07)[..., None]
    img *= (0.92 + 0.14 * (1 - np.abs(np.sin((vv - 0.2) * 2.4 + uu))) ** 3)[..., None]
    img = resize3(img, W, H)
    vignette(img, 0.18, 2.4)
    sauver(img, "apple-ondes", bruit=0.8, seed=42)


# --------------------------------------------------------------------------
# 5. Catppuccin Mocha
# --------------------------------------------------------------------------
def catppuccin_brume():
    """Ciel de crépuscule en pastel : clair en haut à droite, profond en bas à gauche."""
    rng = np.random.default_rng(51)
    w, h = W // 4, H // 4
    y, x = np.mgrid[0:h, 0:w].astype(F32)
    u, v = x / w, y / h
    img = np.broadcast_to(hexc("#1e1e2e"), (h, w, 3)).copy()
    # gros bruit lent : déforme l'espace pour des formes organiques
    dx = (fbm(w, h, rng, 2, 3) - 0.5) * 0.30
    dy = (fbm(w, h, rng, 2, 3) - 0.5) * 0.30
    # clarté : 0 en bas à gauche, 1 en haut à droite
    clair = np.clip((u * 0.55 + (1 - v) * 0.45) + (dx + dy) * 0.4, 0, 1)
    formes = [  # centre u,v ; rayons rx, ry ; angle ; couleur ; opacité
        (0.30, 0.95, 0.65, 0.40, 0.25, "#cba6f7", 0.92),   # grand mauve profond, bas gauche
        (0.05, 0.45, 0.35, 0.40, -0.3, "#89b4fa", 0.80),   # bleu à gauche
        (0.70, 0.70, 0.55, 0.35, 0.15, "#f5c2e7", 0.85),   # rose milieu droit
        (0.88, 0.12, 0.55, 0.38, -0.25, "#f5c2e7", 0.95),  # rose clair haut droit
        (0.40, 0.18, 0.45, 0.28, 0.2, "#89b4fa", 0.80),    # bleu en haut
        (0.95, 0.80, 0.45, 0.30, 0.3, "#fab387", 0.90),    # pêche bas droit
        (0.60, 0.40, 0.30, 0.20, 0.5, "#cba6f7", 0.70),    # mauve central doux
        (0.97, 0.02, 0.28, 0.20, 0.0, "#fab387", 0.85),    # pêche tout en haut à droite
    ]
    for (cx, cy, rx, ry, ang, c, a) in formes:
        du, dv = u - cx + dx, (v - cy + dy) * (h / w)
        ca, sa = np.cos(ang), np.sin(ang)
        pu, pv = (du * ca + dv * sa) / rx, (-du * sa + dv * ca) / (ry * h / w)
        g = np.exp(-((pu ** 2 + pv ** 2) * 1.3) ** 1.6)     # bord plus net
        col = hexc(c) * (0.86 + 0.30 * clair[..., None])   # plus sombre vers le bas gauche
        mix(img, col, np.clip(g * a, 0, 1))
    # lueur douce en haut à droite
    add(img, hexc("#fff0f5"), np.exp(-(np.hypot(u - 0.9, (v - 0.05) * h / w) / 0.35) ** 2) * 0.10)
    img *= (0.975 + 0.05 * fbm(w, h, rng, 3, 4))[..., None]
    gris = img.mean(-1, keepdims=True)
    img = np.clip(gris + (img - gris) * 1.20, 0, 1)   # couleurs plus nettes, pas de gris
    img = resize3(img, W, H)
    vignette(img, 0.15, 2.4)
    sauver(img, "catppuccin-brume", bruit=0.8, seed=51)


# --------------------------------------------------------------------------
# 6. Nord
# --------------------------------------------------------------------------
def nord_fjord():
    rng = np.random.default_rng(61)
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    yw = int(H * 0.70)                                   # ligne d'eau
    img = vgrad([(0, "#161b25"), (0.30, "#232a38"), (0.55, "#3b4560"), (0.70, "#566580"), (1, "#566580")])
    etoiles(img, rng, 900, H * 0.42, hexc("#eceff4"), 0.8)
    # ruban d'aurore : un seul, souple, de gauche à droite (calcul à mi-résolution)
    h, w = H // 2, W // 2
    yy, xx = np.mgrid[0:h, 0:w].astype(F32) * 2
    u = xx / W
    lent = fbm1d(w, rng, 2, 3, 0.5)[None, :]
    yc = H * 0.34 + 150 * np.sin(u * 3.6 + 0.6) + 60 * np.sin(u * 8.0) + 70 * lent
    ep = 120 + 90 * (0.5 + 0.5 * np.sin(u * 5.0 + 2.0))      # épaisseur variable
    t = (yy - yc) / ep                                       # >0 sous la crête
    prof = np.where(t > 0, np.exp(-(t * 2.4) ** 2), np.exp(-(np.abs(t) / 1.6) ** 1.5))
    env = np.clip(np.sin(np.clip(u, 0, 1) * np.pi), 0, 1) ** 0.5   # s'efface aux bords
    vary = 0.55 + 0.45 * (0.5 + 0.5 * fbm1d(w, rng, 3, 3, 0.5))[None, :]
    inten = prof * env * vary * 1.0
    mixv = np.clip(0.5 - t * 0.6 + (u - 0.5) * 0.7, 0, 1)[..., None]    # vert en bas/à gauche, bleu clair en haut/à droite
    col = hexc("#a3be8c") * mixv + hexc("#88c0d0") * (1 - mixv)
    aur = col * inten[..., None]
    aur = np.stack([blur(aur[..., k], 6) for k in range(3)], -1)
    aur = resize3(aur, W, H)
    img += aur * 1.0
    img += np.stack([blur(aur[..., k], 90) for k in range(3)], -1) * 0.5
    # montagnes en plans superposés, du lointain (clair, brumeux) au proche (sombre)
    haze = hexc("#566580")
    couches = [("#81a1c1", 0.40, 0.50, 5), ("#5e81ac", 0.33, 0.38, 6), ("#434c5e", 0.27, 0.22, 7), ("#3b4252", 0.20, 0.10, 8), ("#2e3440", 0.13, 0.0, 9)]
    for (c, hh, br, oc) in couches:
        masse = 0.5 + 0.5 * fbm1d(W, rng, 2, 3, 0.5)           # grandes masses
        n = fbm1d(W, rng, 4, oc, 0.55)
        pic = (1 - np.abs(n)) ** 2                              # arêtes pointues
        crete = 0.25 + 0.75 * (0.55 * masse + 0.45 * pic) * (0.6 + 0.4 * masse)
        yc = yw - H * hh * 1.05 * crete
        m = np.clip(y - yc[None, :] + 0.5, 0, 1) * (y < yw)
        col = hexc(c) * (1 - br * 0.3) + haze * br * 0.3
        degrade = (1 - 0.35 * np.clip((y - yw + H * hh) / (H * hh), 0, 1))[..., None]   # plus sombre vers le pied
        mix(img, col * degrade, m)
        # brume au pied du plan
        mix(img, haze, np.exp(-(yw - y).clip(0) / 160) * br * 0.35 * (y < yw) * m)
    # eau calme : reflet flou, assombri, avec fines rides
    n = H - yw
    src = img[yw - n:yw][::-1].copy()
    src = np.stack([blur(src[..., k], 4) for k in range(3)], -1)
    decal = (7 * np.sin(np.arange(n) * 0.35) + 5 * np.sin(np.arange(n) * 0.11 + 1.0)).astype(int)
    src = np.stack([np.roll(src[k], int(decal[k]), axis=0) for k in range(n)])
    prof_e = np.linspace(0, 1, n)[:, None, None]
    eau = vgrad([(0, "#2e3440"), (1, "#161b25")], n, W)
    img[yw:] = eau * 0.45 + src * (0.50 - 0.18 * prof_e)
    rides = (rng.random(n) ** 3)[:, None] * 0.12 * (1 - prof_e[..., 0])
    add(img[yw:], hexc("#d8dee9"), rides * (0.6 + 0.4 * fbm(W // 8, n, rng, 4, 3).repeat(8, 1)[:, :W]))
    vignette(img, 0.35, 2.2)
    sauver(img, "nord-fjord", seed=61)


# --------------------------------------------------------------------------
# 7. Dracula
# --------------------------------------------------------------------------
def _lisse(a, b, t):
    """Marche douce (smoothstep) entre a et b."""
    t = np.clip((t - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _sapins(rng, n, haut, larg, y_sol):
    """Profil (hauteur y par colonne) d'une rangée de sapins : pointes en dents de scie, sur un sol y_sol."""
    x = np.arange(W, dtype=F32)
    yc = y_sol.astype(F32).copy()
    for _ in range(n):
        cx = rng.uniform(-50, W + 50)
        h = haut * rng.uniform(0.55, 1.35)
        pente = h / (larg * rng.uniform(0.7, 1.2))
        dx = np.abs(x - cx)
        # étages : la silhouette descend par paliers, comme des branches
        etage = 0.10 * h * np.abs(np.sin(dx / (larg * 0.16) * np.pi)) * np.clip(1 - dx / larg, 0, 1)
        sommet = y_sol - h + dx * pente + etage
        yc = np.minimum(yc, sommet)
    return yc


def dracula_nuit():
    rng = np.random.default_rng(71)
    rose, cyan = hexc("#ff79c6"), hexc("#8be9fd")
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    y0 = H * 0.74
    img = vgrad([(0, "#0c0d14"), (0.30, "#171827"), (0.55, "#2a2350"), (0.74, "#4a3580"), (1, "#4a3580")])
    etoiles(img, rng, 700, H * 0.5, hexc("#e9e4ff"), 0.75)
    # lune pâle, décentrée à droite ; halo large puis disque légèrement texturé (mers)
    cx, cy, R = W * 0.69, H * 0.30, 290.0
    d = np.hypot(x - cx, y - cy)
    add(img, hexc("#bd93f9"), np.exp(-(d / 800) ** 2) * 0.20)
    add(img, hexc("#e3d9ff"), np.exp(-(d / 420) ** 2) * 0.10)
    taches = fbm(W // 4, H // 4, rng, 5, 4)
    taches = resize(taches, W, H)
    lune = interp_stops(np.clip((y - (cy - R)) / (2 * R), 0, 1), [(0, "#f2eeff"), (1, "#d3c6f0")])
    lune = lune * (0.84 + 0.16 * taches[..., None])
    disque = np.clip((R - d) / 2.5 + 0.5, 0, 1)
    # fines bandes de nuages : bruit étiré en largeur, découpé en traînées horizontales
    h4, w4 = H // 4, W // 4
    ondul = resize(fbm(w4, h4, rng, 3, 3), W, H)
    fil = resize(fbm(w4 // 6, h4, rng, 2, 3), W, H)       # variation lente en largeur
    bandes = np.sin((y + 160 * ondul) / 34.0 + 3 * fil) * 0.5 + 0.5
    nuages = _lisse(0.25, 0.85, bandes ** 1.1) * _lisse(0.20, 0.55, fil)
    nuages *= _lisse(H * 0.08, H * 0.30, y) * (1 - _lisse(H * 0.38, H * 0.56, y))
    voile = np.clip(nuages * 0.95, 0, 0.9) * (0.6 + 0.4 * fil)
    mix(img, lune, disque * (1 - voile * 0.5))
    # les nuages sont sombres sur le ciel, lilas là où la lune les éclaire
    mix(img, hexc("#20213a"), nuages * 0.45 * (1 - np.exp(-(d / 620) ** 2)))
    add(img, hexc("#cdbdf5"), nuages * np.exp(-(d / 520) ** 2) * 0.16)
    # plans de collines puis de sapins, du lointain (violet, clair) au proche (presque noir)
    u = np.abs(x[0] / W - 0.5) * 2
    plans = [  # type, base, amplitude, couleur haut, couleur pied, brume rose
        ("col", 0.745, 120, "#4b3a86", "#2a2350", 0.0),
        ("col", 0.795, 130, "#392e6c", "#1d1a3c", 0.34),
        ("sap", 0.86, 70, "#272250", "#14122a", 0.30),
        ("sap", 0.95, 105, "#15142b", "#0a0a14", 0.26),
    ]
    for i, (typ, b, a, haut, pied, brume) in enumerate(plans):
        sol = H * b + 10 * fbm1d(W, rng, 2, 3, 0.5) * 3
        if typ == "col":
            n = fbm1d(W, rng, 2, 4, 0.45)
            yc = sol - a * (0.5 + 0.5 * n)
        else:
            base = sol - a * 0.9 * (0.5 + 0.5 * fbm1d(W, rng, 2, 3, 0.5))
            yc = _sapins(rng, 110 if i == 2 else 70, 170 + 170 * (i - 2), 40 + 30 * (i - 2), base)
        # le centre reste bas et calme
        yc = yc + (1 - u ** 1.5) * (60 + 20 * i)
        dd = y - yc[None, :]
        m = np.clip(dd + 0.6, 0, 1)
        coul = hexc(haut) + (hexc(pied) - hexc(haut)) * np.clip(dd / 520, 0, 1)[..., None]
        mix(img, coul, m)
        if brume:
            # brume rose légère, plus épaisse en bas du plan, modulée par un bruit lent
            # (mesurée à une ligne lisse, pas à la crête : sinon des rayons verticaux)
            ds = y - float(np.mean(yc))
            vap = 0.55 + 0.45 * resize(fbm(w4 // 2, h4 // 2, rng, 3, 3), W, H)
            mix(img, rose, np.clip(np.exp(-(ds / 130) ** 2) * vap * brume * 0.40, 0, 1))
    vignette(img, 0.45, 2.0)
    sauver(img, "dracula-nuit", seed=71)


def dracula_ondes():
    rng = np.random.default_rng(72)
    w, h = W // 2, H // 2
    y, x = np.mgrid[0:h, 0:w].astype(F32)
    u = x / w
    fond = hexc("#282a36")
    # fond : très léger relief de lumière (le haut gauche un peu plus clair)
    img = np.broadcast_to(fond, (h, w, 3)).copy()
    add(img, hexc("#44475a"), np.exp(-(np.hypot(u - 0.2, (y / h - 0.1) * 0.62) / 0.55) ** 2) * 0.28)
    img *= (1 - 0.30 * np.clip(np.hypot(u - 0.5, (y / h - 0.5) * 0.62) / 0.75, 0, 1) ** 2)[..., None]
    violet, rose, cyan = hexc("#bd93f9"), hexc("#ff79c6"), hexc("#8be9fd")
    rubans = [  # ordre : du fond (flou, sombre) au premier plan (net, lumineux)
        # base y, amplitude, fréquence, phase, épaisseur, couleur A -> B, flou, intensité
        (0.30, 0.16, 1.3, 0.4, 150, violet, rose, 18, 0.30),
        (0.72, 0.13, 1.7, 2.1, 170, cyan, violet, 14, 0.26),
        (0.50, 0.20, 1.1, 4.0, 120, rose, violet, 9, 0.46),
        (0.62, 0.14, 1.9, 1.0, 95, violet, cyan, 5, 0.70),
        (0.38, 0.11, 2.3, 5.3, 70, rose, rose, 2, 0.78),
        (0.80, 0.09, 1.5, 3.3, 58, violet, violet, 1, 0.80),
    ]
    for (b, a, f, ph, ep, ca, cb, fl, k) in rubans:
        # centre du ruban : deux sinusoïdes (fluide) ; épaisseur qui respire
        yc = h * (b + a * np.sin(u * f * 2 * np.pi + ph) + 0.4 * a * np.sin(u * f * 4.1 * np.pi + ph * 1.7))
        e = ep / 2 * (0.75 + 0.45 * np.sin(u * f * 2.6 * np.pi + ph * 0.6))
        t = (y - yc) / e                               # -1 au bord haut, +1 au bord bas
        alpha = _lisse(1.0, 0.82, np.abs(t))
        # volume : dégradé en travers (clair en haut, plus profond en bas) et le long du ruban
        ombre = 1.0 - 0.52 * _lisse(-0.7, 1.0, t)
        along = np.clip(0.5 + 0.5 * np.sin(u * 2.4 * np.pi + ph), 0, 1)[..., None]
        col = (ca * (1 - along) + cb * along) * ombre[..., None]
        # tire vers le fond pour les rubans éloignés : moins de contraste, plus sombres
        col = fond + (col - fond) * k
        a2 = alpha
        if fl > 1:
            a2 = blur(a2.astype(F32), fl)
            col = np.stack([blur(col[..., c], fl) for c in range(3)], -1)
        # fine ligne de lumière sur l'arête haute des rubans nets
        if fl <= 5:
            add(col, hexc("#f8f8f2"), (_lisse(-0.82, -0.98, t) * 0.0 + np.clip(1 - np.abs(t + 0.9) / 0.1, 0, 1) * 0.10 * alpha))
        mix(img, col, a2 * (0.55 + 0.45 * k))
    img = resize3(img, W, H)
    vignette(img, 0.30, 2.2)
    sauver(img, "dracula-ondes", bruit=0.8, seed=72)


# --------------------------------------------------------------------------
# 8. Nord glacier
# --------------------------------------------------------------------------
def nord_glacier():
    rng = np.random.default_rng(81)
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    # cellules larges (grille irrégulière de points), chacune cassée en éclats autour de son centre
    pts = []
    pas = 760
    for gy in range(-1, H // pas + 2):
        for gx in range(-1, W // pas + 2):
            pts.append((gx * pas + rng.uniform(-0.35, 0.35) * pas * 1.4 + (gy % 2) * pas / 2,
                        gy * pas + rng.uniform(-0.35, 0.35) * pas))
    pts = np.array(pts, F32)
    dmin = np.full((H, W), 1e9, F32)
    cell = np.zeros((H, W), np.int32)
    for i, (px, py) in enumerate(pts):
        d = (x - px) ** 2 + (y - py) ** 2
        m = d < dmin
        dmin[m], cell[m] = d[m], i
    px, py = pts[cell, 0], pts[cell, 1]
    k = rng.integers(2, 4, len(pts))                   # nombre d'éclats par cellule
    dec = rng.uniform(0, 2 * np.pi, len(pts)).astype(F32)
    ang = np.mod(np.arctan2(y - py, x - px) - dec[cell], 2 * np.pi)
    eclat = np.floor(ang / (2 * np.pi) * k[cell]).astype(np.int32)
    fid = cell * 8 + eclat
    # luminosité par face : normale aléatoire contre une lumière venue du haut à gauche
    nf = (len(pts) + 1) * 8
    nx, ny = rng.normal(0, 1, nf), rng.normal(0, 1, nf)
    nz = rng.uniform(0.35, 1.0, nf)
    nn = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    lum = (nx * -0.55 + ny * -0.55 + nz * 0.63) / nn
    face = np.clip(0.50 + 0.42 * lum, 0, 1).astype(F32)
    b = face[fid]
    # dégradé global : clair en haut (et à gauche), sombre en bas
    v, u = y / H, x / W
    b = b * 0.55 + 0.62 * (1 - v) ** 1.1 + 0.22 * (1 - u) * (1 - v) - 0.16
    # petit dégradé à l'intérieur de chaque face, dans le sens de la lumière
    cxm = pts[cell, 0]
    b = b - 0.02 * np.clip((x - cxm) / 400, -1, 1)
    b = np.clip(b, 0, 1)
    # rampe de couleurs Nord : bleu nuit -> glace -> blanc
    img = interp_stops(b, [(0.0, "#232936"), (0.18, "#2e3440"), (0.34, "#434c5e"), (0.50, "#4c6a96"),
                           (0.64, "#5e81ac"), (0.74, "#81a1c1"), (0.86, "#a9c4d6"), (0.94, "#d8dee9"), (1.0, "#eceff4")])
    # arêtes : fin liseré clair là où l'on change d'éclat (côté lumière), sans bruit
    bord = np.zeros((H, W), F32)
    for sy, sx in ((1, 0), (0, 1)):
        diff = (fid != np.roll(fid, (sy, sx), (0, 1)))
        bord = np.maximum(bord, diff.astype(F32))
    bord = blur(bord, 1.1) * 1.8
    add(img, hexc("#eceff4"), np.clip(bord, 0, 1) * 0.10 * (1 - v)[..., None][..., 0])
    vignette(img, 0.35, 2.2)
    sauver(img, "nord-glacier", seed=81)


# --------------------------------------------------------------------------
# 12 thèmes de plus : rose-aube, everforest, solarized-clair, papier, clair-neutre, sakura, matrice,
# cyberjaune, vaporwave, pluie-verte, brutaliste, ocean (deux fonds chacun)
# --------------------------------------------------------------------------
def _ys():
    return np.arange(H, dtype=F32)[:, None]


def _xs():
    return np.arange(W, dtype=F32)[None, :]


def _lueur(img, cx, cy, r, col, a, ry=None, mode="add"):
    """Grande tache de lumière douce (gaussienne), calculée en petit puis agrandie."""
    s = 8
    yy, xx = np.mgrid[0:H // s, 0:W // s].astype(F32) * s
    g = np.exp(-(((xx - cx) / r) ** 2 + ((yy - cy) / (ry or r)) ** 2))
    g = np.clip(resize(g, W, H), 0, 1) * a
    (add if mode == "add" else mix)(img, col, g)


def _couche(yc):
    """Masque doux sous un profil yc (une valeur par colonne) et distance verticale à la crête."""
    d = _ys() - yc[None, :]
    return np.clip(d + 0.5, 0, 1), d


def _grain_papier(rng, force=1.0):
    """Grain de papier : taches larges, grain moyen et fibres fines (valeurs autour de 0)."""
    g = (fbm(W, H, rng, 40, 5, 0.6) - 0.5) * 0.03 + (fbm(W, H, rng, 8, 3, 0.5) - 0.5) * 0.02
    g += (resize(rng.random((H // 2, W // 2)).astype(F32), W, H) - 0.5) * 0.025
    return g * force


def _compose(img, ov, sigma=1.0):
    """Pose une couche RGBA (PIL) sur img, bords adoucis sans frange sombre."""
    a = np.asarray(ov, F32) / 255
    al = blur(a[..., 3], sigma)
    pre = np.stack([blur(a[..., k] * a[..., 3], sigma) for k in range(3)], -1)
    mix(img, pre / np.maximum(al, 1e-4)[..., None], al)


# 1-2. rose-aube
def rose_aube_collines():
    rng = np.random.default_rng(91)
    crème = hexc("#faf4ed")
    img = vgrad([(0, "#f1d9d3"), (0.35, "#f6e3da"), (0.6, "#fbeee4"), (1, "#faf4ed")])
    _lueur(img, W * 0.68, H * 0.5, 900, hexc("#ea9d34"), 0.30, ry=420)
    _lueur(img, W * 0.22, H * 0.22, 1200, hexc("#d7827e"), 0.14, ry=700, mode="mix")
    couches = [
        (0.50, 70, [0.7, 1.6], "#e9c9c3", 0.55), (0.58, 100, [0.6, 1.4, 2.3], "#dfb4ae", 0.45),
        (0.67, 130, [0.5, 1.2, 2.0], "#cb9ea4", 0.35), (0.77, 160, [0.5, 1.0, 1.8], "#b3a0b9", 0.25),
        (0.88, 190, [0.4, 0.9, 1.5], "#6f93a2", 0.10),
    ]
    ys = _ys()
    for base, amp, fr, col, brume in couches:
        yc = _dune(rng, H * base, amp, fr)
        m, d = _couche(yc)
        c = hexc(col)[None, None, :] * (1 - 0.18 * np.clip(d / 600, 0, 1))[..., None]
        c = c + hexc("#fff1e2") * (np.clip(1 - d / 110, 0, 1) * 0.22)[..., None]
        mix(img, np.broadcast_to(c, (H, W, 3)), m)
        mix(img, crème, (np.exp(-((ys - H * (base + 0.07)) / 190) ** 2) * brume) * np.ones((1, W), F32))
    vignette(img, 0.10, 2.0)
    sauver(img, "rose-aube-collines", bruit=0.75, seed=91)


def rose_aube_papier():
    rng = np.random.default_rng(92)
    img = vgrad([(0, "#f8efe6"), (1, "#faf4ed")])
    for cx, cy, r, ry, col, a in [
        (0.12, 0.30, 1100, 800, "#d7827e", 0.42), (0.86, 0.72, 1200, 700, "#ea9d34", 0.34),
        (0.60, 0.95, 1300, 520, "#907aa9", 0.30), (0.95, 0.10, 800, 600, "#286983", 0.16),
        (0.30, 0.85, 900, 500, "#d7827e", 0.28),
    ]:
        _lueur(img, W * cx, H * cy, r, hexc(col), a, ry=ry, mode="mix")
    img += _grain_papier(rng, 1.3)[..., None]
    vignette(img, 0.08, 2.0)
    sauver(img, "rose-aube-papier", bruit=0.8, seed=92)


# 3-4. everforest
def everforest_sapins():
    rng = np.random.default_rng(93)
    img = vgrad([(0, "#1f2629"), (0.4, "#2d353b"), (0.62, "#3d4b4a"), (1, "#3d4b4a")])
    _lueur(img, W * 0.5, H * 0.56, 1400, hexc("#83c092"), 0.22, ry=520)
    _lueur(img, W * 0.8, H * 0.30, 800, hexc("#dbbc7f"), 0.06)
    etoiles(img, rng, 220, H * 0.35, hexc("#d3c6aa"), 0.35)
    brume = hexc("#5e7d72")
    plans = [("#55706a", 0.57, 70, 240, 90, 0.55), ("#46605c", 0.62, 56, 330, 110, 0.45),
             ("#364a48", 0.67, 40, 440, 140, 0.35), ("#27363a", 0.73, 30, 560, 180, 0.25),
             ("#1c262a", 0.80, 24, 700, 230, 0.15), ("#12181b", 0.90, 18, 840, 300, 0.0)]
    for col, yb, n, haut, larg, b in plans:
        y_sol = H * yb + fbm1d(W, rng, 3, 4, 0.5) * 40
        yc = _sapins(rng, n, haut, larg, y_sol)
        m, d = _couche(yc)
        mix(img, hexc(col), m)
        mix(img, brume, m * np.clip(1 - d / 420, 0, 1) * b)
    vignette(img, 0.32, 2.0)
    sauver(img, "everforest-sapins", seed=93)


def everforest_sousbois():
    rng = np.random.default_rng(94)
    img = vgrad([(0, "#14191c"), (0.5, "#2d353b"), (1, "#1b2124")])
    s = 4
    yy, xx = np.mgrid[0:H // s, 0:W // s].astype(F32) * s
    th = np.arctan2(xx - W * 0.78, yy + H * 0.2)
    prof = fbm1d(1024, rng, 14, 4, 0.6) * 0.5 + 0.5
    u = np.clip((th + 0.9) / 1.2 * 1023, 0, 1023)
    ray = _lisse(0.42, 0.9, np.interp(u, np.arange(1024), prof)) ** 1.3
    ray *= np.exp(-np.hypot(xx - W * 0.78, yy + H * 0.2) / 2300)
    ray = np.clip(resize(ray.astype(F32), W, H), 0, 1)
    add(img, hexc("#a7c080"), ray * 0.20)
    _lueur(img, W * 0.7, H * 0.25, 1000, hexc("#83c092"), 0.12)
    ys, xs = _ys(), _xs()
    fog = hexc("#3b5a4d")
    for n, larg, col, soft, lean, fogk in [(26, 16, "#41564d", 18, 0.02, 0.30), (16, 30, "#2c3d38", 10, 0.03, 0.22),
                                          (9, 54, "#1b2625", 5, 0.04, 0.12), (5, 100, "#0e1314", 3, 0.05, 0.0)]:
        for _ in range(n):
            cx = rng.uniform(-50, W + 50)
            w = larg * rng.uniform(0.6, 1.5)
            m = np.clip(1 - (np.abs(xs - cx - (rng.normal() * lean) * (ys - H / 2)) - w / 2) / soft, 0, 1)
            mix(img, hexc(col), m * np.clip(0.4 + ys / (H * 0.3), 0, 1))
        mix(img, fog, np.exp(-((ys - H * 0.80) / 260) ** 2) * fogk * np.ones((1, W), F32))
    vignette(img, 0.35, 2.0)
    sauver(img, "everforest-sousbois", seed=94)


# 5-6. solarized-clair
def solarized_clair_cercles():
    rng = np.random.default_rng(95)
    img = vgrad([(0, "#fdf6e3"), (1, "#f6efd8")])
    img += ((fbm(W, H, rng, 6, 4, 0.5) - 0.5) * 0.03)[..., None]
    ys, xs = _ys(), _xs()
    cols = [hexc(c) for c in ("#268bd2", "#2aa198", "#b58900", "#cb4b16")]
    for cx, cy, pas, k, haut in [(0.74, 0.92, 70, 1900, 0.8), (0.10, 0.18, 90, 900, 0.5)]:
        r = np.hypot(xs - W * cx, ys - H * cy)
        disc = np.clip((k * 0.8 - r) / 2, 0, 1) * 0.55
        mix(img, hexc("#eee8d5"), disc)
        a = ligne_aa(r / pas, 1.0 / pas, 2.4) * np.exp(-r / k) * haut
        idx = (r // 450).astype(int) % 4
        for i in range(4):
            mix(img, cols[i], a * (idx == i))
        for R, c in [(600, 0), (1200, 1), (1800, 2)]:
            mix(img, cols[c], np.clip(3.5 - np.abs(r - R * pas / 70), 0, 1) * 0.5 * np.exp(-r / (k * 1.2)))
    vignette(img, 0.06, 2.0)
    sauver(img, "solarized-clair-cercles", bruit=0.75, seed=95)


def solarized_clair_dunes():
    rng = np.random.default_rng(96)
    img = vgrad([(0, "#f4ecd4"), (0.5, "#fdf6e3"), (1, "#fdf6e3")])
    ys, xs = _ys(), _xs()
    _lueur(img, W * 0.70, H * 0.46, 600, hexc("#fff3c6"), 0.55, mode="mix")
    r = np.hypot(xs - W * 0.70, ys - H * 0.46)
    mix(img, hexc("#268bd2"), ligne_aa(r / 110, 1 / 110, 2.2) * np.exp(-r / 520) * 0.45)
    couches = [(0.55, 100, [0.8, 1.7], "#f1e9cf", "#d8cfb4", 0.5, 0.0), (0.64, 140, [0.7, 1.5, 2.4], "#ebdfbf", "#cdc1a0", 0.35, 0.16),
               (0.74, 180, [0.6, 1.3, 2.2], "#e4d3aa", "#bdb08a", 0.2, 0.2), (0.86, 220, [0.5, 1.1, 1.9], "#ddc894", "#a99b72", 0.0, 0.18)]
    for i, (base, amp, fr, clair, ombre, brume, ln) in enumerate(couches):
        yc = _dune(rng, H * base, amp, fr)
        lum = 0.5 - 0.5 * np.tanh(np.gradient(yc) / 0.55)
        lum = np.convolve(np.pad(lum, 60, mode="edge"), np.ones(121) / 121, "valid")
        m, d = _couche(yc)
        col = hexc(ombre)[None, None, :] + (hexc(clair) - hexc(ombre))[None, None, :] * lum[None, :, None]
        col = col * (1 - 0.22 * np.clip(d / 700, 0, 1))[..., None]
        col = np.broadcast_to(col, (H, W, 3))
        mix(img, col, m)
        if ln:
            lc = hexc("#cb4b16" if i == 3 else "#b58900")
            mix(img, lc, ligne_aa(d / 38, 1 / 38, 1.7) * np.clip(1 - d / 900, 0, 1) * (d > 0) * ln)
        if brume:
            mix(img, hexc("#fdf6e3"), m * np.clip(1 - d / 450, 0, 1) * brume)
    vignette(img, 0.08, 2.0)
    sauver(img, "solarized-clair-dunes", bruit=0.75, seed=96)


# 7-8. papier
def papier_estampe():
    rng = np.random.default_rng(97)
    papier, encre, gris = hexc("#f4f1ea"), hexc("#1a1a1a"), hexc("#666666")
    img = vgrad([(0, "#f6f3ec"), (1, "#f1ede4")])
    ys, xs = _ys(), _xs()
    d0 = np.hypot(xs - W * 0.72, ys - H * 0.28)
    mix(img, hexc("#b3261e"), np.clip(170 - d0, 0, 1) * 0.92)
    for i, (base, amp) in enumerate([(0.54, 360), (0.64, 320), (0.75, 270), (0.87, 210)]):
        yc = _crete(rng, H * base, amp, 6, 0.0, 3 + i)
        g = np.gradient(yc)[None, :]
        m, d = _couche(yc)
        mix(img, papier * (1 - 0.04 * (i + 1)) + gris * 0.04 * (i + 1) * 0.5, m)
        hach = ligne_aa(d / 15, 1 / 15, 1.2) * np.clip(1 - d / 190, 0, 1) * (d > 0) * (0.18 + 0.07 * i)
        mix(img, gris, hach)
        lw = 2.2 + 0.7 * i
        mix(img, encre, np.clip(lw * np.sqrt(1 + g ** 2) / 2 + 0.5 - np.abs(d), 0, 1) * (0.35 + 0.2 * i))
    img *= 1 + _grain_papier(rng, 1.6)[..., None]
    vignette(img, 0.10, 2.0)
    sauver(img, "papier-estampe", bruit=0.8, seed=97)


def papier_vide():
    rng = np.random.default_rng(98)
    img = vgrad([(0, "#f6f3ec"), (1, "#f2eee6")])
    ys, xs = _ys(), _xs()
    cx, cy = W * 0.5, H * 0.62
    d = np.hypot(xs - cx, ys - cy)
    ombre = np.exp(-(np.hypot(xs - cx - 22, ys - cy - 30) / 330) ** 2)
    img *= (1 - 0.07 * ombre)[..., None]
    mix(img, hexc("#b3261e"), np.clip(230 - d, 0, 1) * 0.94)
    mix(img, hexc("#666666"), np.clip(1.5 - np.abs(ys - H * 0.80), 0, 1) * ((xs > W * 0.34) & (xs < W * 0.66)) * 0.35)
    for k in range(9):
        mix(img, hexc("#666666"), np.clip(1.2 - np.abs(xs - (W * 0.34 + k * W * 0.04)), 0, 1) * ((ys > H * 0.795) & (ys < H * 0.815)) * 0.35)
    img *= 1 + _grain_papier(rng, 1.7)[..., None]
    vignette(img, 0.10, 2.0)
    sauver(img, "papier-vide", bruit=0.8, seed=98)


# 9-10. clair-neutre
def _forme(img, dist, cx, cy, r, ca, cb, ang, a, ombre=0.12, dec=(0, 46)):
    """Forme à dégradé et ombre portée douce. dist(xx, yy) = distance signée (négatif dedans)."""
    s = 4
    yy, xx = np.mgrid[0:H // s, 0:W // s].astype(F32) * s
    sh = blur(np.clip(0.5 - dist(xx - dec[0], yy - dec[1]), 0, 1), 18)
    sh = np.clip(resize(sh, W, H), 0, 1)
    img *= (1 - ombre * sh)[..., None]
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    t = np.clip(((x - cx) * np.cos(ang) + (y - cy) * np.sin(ang)) / (2 * r) + 0.5, 0, 1)
    col = hexc(ca)[None, None, :] + (hexc(cb) - hexc(ca))[None, None, :] * t[..., None]
    mix(img, np.broadcast_to(col, (H, W, 3)), np.clip(0.5 - dist(x, y), 0, 1) * a)


def clair_neutre_formes():
    rng = np.random.default_rng(99)
    img = vgrad([(0, "#fafafa"), (1, "#eef1f6")])
    _lueur(img, W * 0.92, H * 0.92, 1500, hexc("#3584e4"), 0.20, mode="mix")
    _lueur(img, W * 0.06, H * 0.12, 1000, hexc("#deddda"), 0.45, mode="mix")
    c1 = (W * 0.17, H * 0.80, 700)
    _forme(img, lambda x, y: np.hypot(x - c1[0], y - c1[1]) - c1[2], c1[0], c1[1], c1[2], "#9ec5f2", "#3584e4", 0.9, 0.92)
    c2 = (W * 0.84, H * 0.30, 400)
    _forme(img, lambda x, y: np.hypot(x - c2[0], y - c2[1]) - c2[2], c2[0], c2[1], c2[2], "#fafafa", "#cfe0f7", 1.2, 0.95, 0.10)
    q = (W * 0.70, H * 0.84, 380, 130)

    def rr(x, y):
        dx, dy = np.abs(x - q[0]) - q[2] + q[3], np.abs(y - q[1]) - q[2] + q[3]
        return np.hypot(np.maximum(dx, 0), np.maximum(dy, 0)) + np.minimum(np.maximum(dx, dy), 0) - q[3]
    _forme(img, rr, q[0], q[1], q[2], "#bcd6f6", "#4a93e8", 0.8, 0.9)
    c3 = (W * 0.42, H * 0.95, 330)
    _forme(img, lambda x, y: np.hypot(x - c3[0], y - c3[1]) - c3[2], c3[0], c3[1], c3[2], "#deddda", "#fafafa", 1.5, 1.0, 0.09)
    img += ((fbm(W, H, rng, 6, 3) - 0.5) * 0.012)[..., None]
    sauver(img, "clair-neutre-formes", bruit=0.7, seed=99)


def clair_neutre_vagues():
    rng = np.random.default_rng(100)
    img = vgrad([(0, "#fafafa"), (0.5, "#eef3fa"), (1, "#e4edf9")])
    _lueur(img, W * 0.5, H * 0.1, 1800, hexc("#3584e4"), 0.07, ry=500, mode="mix")
    x = np.linspace(0, 1, W, dtype=F32)
    cols = ["#f3f6fb", "#e0ebf9", "#c4daf4", "#9bc2ef", "#6ba5ea", "#3584e4", "#2b6fc3"]
    for k, c in enumerate(cols):
        base = 0.42 + 0.085 * k
        yc = np.full(W, H * base, F32)
        for f in (0.6 + 0.3 * k, 1.4 + 0.5 * k, 2.6):
            yc += np.sin(2 * np.pi * (f * x + rng.random())) * (46 - 3 * k) * (1.1 - 0.15 * f / 3)
        yc += fbm1d(W, rng, 3, 3, 0.5) * 30
        m, d = _couche(yc)
        img *= (1 - 0.17 * (np.exp(np.clip(d, -500, 0) / 55) * (d < 0)))[..., None]
        cc = hexc(c)[None, None, :] * (1 - 0.10 * np.clip(d / 800, 0, 1))[..., None]
        mix(img, np.broadcast_to(cc, (H, W, 3)), m)
        mix(img, hexc("#ffffff"), np.clip(1 - np.abs(d - 1.5) / 2.5, 0, 1) * 0.35)
    sauver(img, "clair-neutre-vagues", bruit=0.7, seed=100)


# 11-12. sakura
def _branche(rng, dr, tips, x, y, ang, L, wid, prof):
    pas = 16
    steps = max(2, int(L // pas))
    courbe = rng.normal(0, 0.012)
    px, py = x, y
    for s in range(steps):
        ang += courbe + rng.normal(0, 0.07)
        x += np.cos(ang) * pas
        y += np.sin(ang) * pas
        if 0.28 * W < x < 0.72 * W and y < 0.17 * H:
            return
        w = max(2, int(wid * (1 - 0.65 * s / steps)))
        dr.line([(px, py), (x, y)], fill=(59, 47, 51, 255), width=w)
        if w > 6:
            dr.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=(59, 47, 51, 255))
        px, py = x, y
        if prof < 3 and s > 3 and L > 200 and rng.random() < 0.10:
            _branche(rng, dr, tips, x, y, ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.0), L * rng.uniform(0.3, 0.5), wid * 0.55, prof + 1)
        if prof >= 1 and rng.random() < 0.22:
            tips.append((x, y))
    tips.append((x, y))


def _fleur(dr, rng, x, y, r):
    col = [(229, 163, 180, 255), (239, 188, 203, 255), (247, 212, 222, 255)][int(rng.integers(0, 3))]
    a0 = rng.random() * 6.283
    for k in range(5):
        a = a0 + k * 6.283 / 5
        cx, cy = x + np.cos(a) * r * 0.55, y + np.sin(a) * r * 0.55
        dr.ellipse([cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55], fill=col)
    dr.ellipse([x - r * 0.2, y - r * 0.2, x + r * 0.2, y + r * 0.2], fill=(201, 123, 146, 255))


def _petales(img, rng, n, rmin, rmax, y0, y1, sigma, alpha=1.0):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    t = np.linspace(0, 2 * np.pi, 16)
    for _ in range(n):
        r = rng.uniform(rmin, rmax)
        x, y, th = rng.uniform(0, W), rng.uniform(y0, y1) * H, rng.uniform(0, 6.283)
        pts = [(x + r * np.cos(u) * np.cos(th) - r * 0.55 * np.sin(u) * np.sin(th),
                y + r * np.cos(u) * np.sin(th) + r * 0.55 * np.sin(u) * np.cos(th)) for u in t]
        c = [(229, 163, 180), (239, 188, 203), (247, 212, 222)][int(rng.integers(0, 3))]
        dr.polygon(pts, fill=c + (int(255 * alpha),))
    _compose(img, ov, sigma)


def sakura_branche():
    rng = np.random.default_rng(101)
    img = vgrad([(0, "#fff5f7"), (0.6, "#fdeef1"), (1, "#f9e3e8")])
    _lueur(img, W * 0.18, H * 0.22, 700, hexc("#fffafb"), 0.7, mode="mix")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    tips = []
    _branche(rng, dr, tips, W + 80, H * 0.40, np.pi + 0.12, 2500, 36, 0)
    _branche(rng, dr, tips, -60, H * 0.86, -0.22, 1500, 26, 0)
    for x, y in tips:
        if rng.random() < 0.5:
            dr.ellipse([x + 10, y - 6, x + 62, y + 12], fill=(154, 184, 154, 255))
    for x, y in tips:
        for _ in range(int(rng.integers(1, 4))):
            _fleur(dr, rng, x + rng.normal(0, 28), y + rng.normal(0, 28), rng.uniform(24, 46))
    _compose(img, ov, 1.1)
    _petales(img, rng, 70, 14, 26, 0.18, 1.0, 1.2)
    _petales(img, rng, 14, 40, 70, 0.1, 1.0, 7.0, 0.8)
    img += ((fbm(W, H, rng, 6, 3) - 0.5) * 0.012)[..., None]
    vignette(img, 0.06, 2.0)
    sauver(img, "sakura-branche", bruit=0.75, seed=101)


def sakura_lune():
    rng = np.random.default_rng(102)
    img = vgrad([(0, "#fcecf0"), (0.5, "#fff5f7"), (1, "#f7e4e9")])
    ys, xs = _ys(), _xs()
    cx, cy = W * 0.70, H * 0.30
    _lueur(img, cx, cy, 900, hexc("#e5a3b4"), 0.30, mode="mix")
    r = np.hypot(xs - cx, ys - cy)
    mix(img, hexc("#fff9fa"), np.clip(330 - r, 0, 1) * 0.96)
    mar = fbm(W, H, rng, 6, 4, 0.55)
    mix(img, hexc("#ecd2d9"), np.clip(330 - r, 0, 1) * _lisse(0.5, 0.8, mar) * 0.35)
    mix(img, hexc("#e5a3b4"), ligne_aa(r / 620, 1 / 620, 2.0) * (r < 640) * 0.35)
    for base, amp, col, b in [(0.80, 90, "#e4eee1", 0.5), (0.88, 110, "#cfe1cd", 0.3), (0.96, 130, "#b6cfb5", 0.0)]:
        yc = _dune(rng, H * base, amp, [0.6, 1.3, 2.2])
        m, d = _couche(yc)
        mix(img, hexc(col), m)
        mix(img, hexc("#fff5f7"), m * np.clip(1 - d / 300, 0, 1) * b)
    _petales(img, rng, 90, 14, 26, 0.12, 0.95, 1.2)
    _petales(img, rng, 16, 40, 76, 0.05, 1.0, 7.0, 0.8)
    img += ((fbm(W, H, rng, 6, 3) - 0.5) * 0.012)[..., None]
    sauver(img, "sakura-lune", bruit=0.75, seed=102)


# 7-8. matrice
def _points(p, I, rmin, rmax):
    """Grille de points de pas p dont le rayon suit I (une valeur par cellule). Renvoie (alpha, I plein cadre)."""
    Ir = np.repeat(np.repeat(I.astype(F32), p, 0), p, 1)[:H, :W]
    dy = (np.arange(H) % p - p / 2 + 0.5).astype(F32)[:, None]
    dx = (np.arange(W) % p - p / 2 + 0.5).astype(F32)[None, :]
    r = rmin + (rmax - rmin) * Ir
    return np.clip(r - np.hypot(dx, dy) + 0.5, 0, 1), Ir


def _point_rouge(img, x, y, r):
    yy, xx = np.ogrid[max(0, int(y - 300)):min(H, int(y + 300)), max(0, int(x - 300)):min(W, int(x + 300))]
    sub = img[max(0, int(y - 300)):min(H, int(y + 300)), max(0, int(x - 300)):min(W, int(x + 300))]
    d = np.hypot(xx - x, yy - y).astype(F32)
    rouge = hexc("#d71920")
    add(sub, rouge, np.exp(-(d / (r * 4.5)) ** 2) * 0.55)
    mix(sub, rouge, np.clip(r - d + 0.5, 0, 1))


def matrice_relief():
    rng = np.random.default_rng(103)
    p = 40
    ny, nx = H // p, W // p
    gy, gx = np.mgrid[0:ny, 0:nx].astype(F32)
    gx = (gx + 0.5) / nx
    gy = (gy + 0.5) / ny
    rel = 1 - np.abs(2 * fbm(nx, ny, rng, 3, 4, 0.5) - 1)
    rel = rel ** 2.0 * (0.35 + 0.65 * _lisse(0.2, 0.8, gy))
    rel += 0.45 * np.exp(-(((gx - 0.2) / 0.16) ** 2 + ((gy - 0.75) / 0.2) ** 2))
    I = np.clip(0.10 + 0.9 * rel, 0, 1)
    I *= 1 - 0.88 * np.exp(-(((gx - 0.5) / 0.26) ** 2 + ((gy - 0.10) / 0.2) ** 2))
    a, Ir = _points(p, I, 1.6, 10.5)
    img = np.zeros((H, W, 3), F32)
    add(img, np.array([1, 1, 1], F32), a * (0.22 + 0.78 * Ir))
    ix, iy = int(0.66 * nx), int(0.60 * ny)
    _point_rouge(img, (ix + 0.5) * p, (iy + 0.5) * p, 15)
    vignette(img, 0.30, 2.0)
    sauver(img, "matrice-relief", bruit=0.35, seed=103)


def matrice_cercle():
    rng = np.random.default_rng(104)
    p = 36
    ny, nx = -(-H // p), -(-W // p)
    gy, gx = np.mgrid[0:ny, 0:nx].astype(F32)
    cxr, cyr, R = W * 0.5, H * 0.65, 800
    X, Y = (gx + 0.5) * p, (gy + 0.5) * p
    dist = np.hypot(X - cxr, Y - cyr)
    th = np.arctan2(Y - cyr, X - cxr)
    Rv = R + 45 * np.sin(3 * th + 0.8)
    ring = np.exp(-((dist - Rv) / 75) ** 2) * (0.65 + 0.35 * np.cos(2 * th - 0.6))
    inner = 0.30 * np.exp(-((dist - R * 0.55) / 40) ** 2) + 0.14 * np.exp(-((dist - R * 1.35) / 50) ** 2)
    I = np.clip(0.07 + ring + inner, 0, 1)
    I *= 1 - 0.85 * np.exp(-((((X - W / 2) / 1000) ** 2) + ((Y - H * 0.10) / 380) ** 2))
    a, Ir = _points(p, I, 1.4, 8.5)
    img = np.zeros((H, W, 3), F32)
    add(img, np.array([1, 1, 1], F32), a * (0.20 + 0.80 * Ir))
    t = -0.62
    ix, iy = int((cxr + R * np.cos(t)) // p), int((cyr + R * np.sin(t)) // p)
    _point_rouge(img, (ix + 0.5) * p, (iy + 0.5) * p, 14)
    vignette(img, 0.30, 2.0)
    sauver(img, "matrice-cercle", bruit=0.35, seed=104)


# 9-10. cyberjaune
_NEONS = [(252, 238, 10), (0, 240, 255), (255, 0, 60)]


def _ville_plan(rng, yg, hmin, hmax, wmin, wmax, col, p_lit, pas, p_neon):
    """Une rangée d'immeubles : renvoie (couche RGBA des masses, image RGB des lumières)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lu = Image.new("RGB", (W, H), (0, 0, 0))
    d, dl = ImageDraw.Draw(im), ImageDraw.Draw(lu)
    x = -int(rng.integers(0, 120))
    while x < W:
        w = int(rng.integers(wmin, wmax))
        h = int(rng.uniform(hmin, hmax))
        if abs(x + w / 2 - W / 2) < 900:
            h = min(h, int(yg - H * 0.36))
        y1 = yg - h
        d.rectangle([x, y1, x + w, yg + 4], fill=col + (255,))
        if rng.random() < 0.3:  # antenne ou étage en retrait
            d.rectangle([x + w // 4, y1 - int(h * 0.12), x + 3 * w // 4, y1], fill=col + (255,))
        ny, nx = max(1, (h - 60) // pas), max(1, (w - 24) // pas)
        lit = rng.random((ny, nx))
        for j in range(ny):
            for i in range(nx):
                if lit[j, i] < p_lit:
                    u = rng.random()
                    c = (252, 238, 10) if u < 0.6 else (0, 240, 255) if u < 0.9 else (255, 245, 200)
                    k = rng.uniform(0.45, 1.0)
                    wx, wy = x + 14 + i * pas, y1 + 36 + j * pas
                    dl.rectangle([wx, wy, wx + pas * 0.45, wy + pas * 0.55], fill=tuple(int(v * k) for v in c))
        if rng.random() < p_neon:  # néon vertical sur l'arête ou enseigne
            c = _NEONS[int(rng.choice(3, p=[0.45, 0.4, 0.15]))]
            if rng.random() < 0.55:
                ln = int(rng.uniform(0.3, 0.8) * h)
                dl.rectangle([x + w - 9, y1 + 20, x + w - 3, y1 + 20 + ln], fill=c)
            else:
                sw, sh = int(w * rng.uniform(0.4, 0.8)), int(rng.uniform(26, 50))
                sy = y1 + int(rng.uniform(0.1, 0.6) * h)
                dl.rectangle([x + 10, sy, x + 10 + sw, sy + sh], outline=c, width=5)
        x += w + int(rng.integers(0, 12))
    return im, lu


def cyberjaune_ville():
    rng = np.random.default_rng(105)
    yg = int(H * 0.80)
    img = vgrad([(0, "#0d0d0d"), (0.5, "#14111a"), (0.8, "#2a2308"), (1, "#0d0d0d")])
    _lueur(img, W * 0.5, H * 0.80, 2300, hexc("#fcee0a"), 0.20, ry=420)
    _lueur(img, W * 0.18, H * 0.70, 900, hexc("#00f0ff"), 0.12, ry=500)
    _lueur(img, W * 0.88, H * 0.62, 800, hexc("#ff003c"), 0.08, ry=500)
    etoiles(img, rng, 120, H * 0.3, hexc("#e8e0c0"), 0.25)
    plans = [(480, 1150, 120, 280, (18, 17, 24), 0.18, 34, 0.5, 0.45),
             (340, 900, 150, 340, (11, 11, 15), 0.22, 40, 0.6, 0.6),
             (220, 620, 200, 420, (6, 6, 8), 0.16, 48, 0.7, 0.8)]
    for hmin, hmax, wmin, wmax, col, p_lit, pas, p_neon, glow in plans:
        im, lu = _ville_plan(rng, yg, hmin, hmax, wmin, wmax, col, p_lit, pas, p_neon)
        _compose(img, im, 1.0)
        lum = np.asarray(lu, F32) / 255
        halo = np.stack([blur(lum[..., k], 16) for k in range(3)], -1)
        img += lum * 0.9 + halo * (1.6 * glow)
        mix(img, hexc("#1b1708"), 0.14)
    hh = H - yg
    refl = img[yg - hh:yg][::-1].copy()
    xi = (np.arange(W)[None, :] + (12 * np.sin(np.arange(hh)[:, None] / 8.0)).astype(int)) % W
    refl = refl[np.arange(hh)[:, None], xi]
    fade = ((1 - np.arange(hh) / hh) ** 1.4)[:, None, None].astype(F32)
    img[yg:] = hexc("#0b0b0f") * (1 - 0.4 * fade) + refl * 0.65 * fade
    ys = _ys()
    mix(img, hexc("#00f0ff"), np.clip(1 - np.abs(ys - (yg + 3)) / 2.5, 0, 1) * 0.5 * np.ones((1, W), F32))
    add(img, hexc("#fcee0a"), np.exp(-((ys - yg) / 40) ** 2) * 0.10 * np.ones((1, W), F32))
    vignette(img, 0.38, 2.0)
    sauver(img, "cyberjaune-ville", bruit=0.45, seed=105)


def cyberjaune_circuits():
    rng = np.random.default_rng(106)
    img = vgrad([(0, "#0d0d0d"), (1, "#111114")])
    ys, xs = _ys(), _xs()
    u = (xs * 0.82 + ys * 0.57) / 260
    v = u % 1
    add(img, np.array([1, 1, 1], F32), (_lisse(0.0, 0.01, v) * (1 - _lisse(0.5, 0.51, v))) * 0.022)
    mix(img, hexc("#fcee0a"), ligne_aa(u, 1 / 260, 2.0) * ((np.floor(u) % 4) == 0) * 0.12)
    _lueur(img, W * 0.85, H * 0.9, 1000, hexc("#00f0ff"), 0.10, ry=700)
    _lueur(img, W * 0.1, H * 0.85, 900, hexc("#fcee0a"), 0.08, ry=600)
    tr = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(tr)
    dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    pas = 60
    for _ in range(190):
        x, y = int(rng.integers(0, W // pas)) * pas, int(rng.integers(0, H // pas)) * pas
        u_ = rng.random()
        c = _NEONS[0] if u_ < 0.68 else _NEONS[1] if u_ < 0.93 else _NEONS[2]
        pts, k = [(x, y)], int(rng.integers(8))
        for _s in range(int(rng.integers(3, 8))):
            k = (k + int(rng.choice([-1, 0, 1]))) % 8
            L = int(rng.integers(2, 8)) * pas
            x, y = x + dirs[k][0] * L, y + dirs[k][1] * L
            pts.append((x, y))
        if any(1000 < px < 2840 and py < 700 for px, py in pts):
            continue
        dim = rng.uniform(0.35, 0.75)
        d.line(pts, fill=tuple(int(q * dim) for q in c), width=4, joint="curve")
        for px, py in pts[1:-1]:
            d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=tuple(int(q * dim) for q in c))
        px, py = pts[-1]
        d.ellipse([px - 11, py - 11, px + 11, py + 11], fill=c)
        px, py = pts[0]
        d.ellipse([px - 15, py - 15, px + 15, py + 15], outline=c, width=4)
    t = np.asarray(tr, F32) / 255
    t = np.stack([blur(t[..., k], 1.0) for k in range(3)], -1)
    halo = np.stack([blur(t[..., k], 14) for k in range(3)], -1)
    img += t + halo * 1.1
    vignette(img, 0.35, 2.0)
    sauver(img, "cyberjaune-circuits", bruit=0.45, seed=106)


# 11-12. vaporwave
def vaporwave_mer():
    rng = np.random.default_rng(107)
    y0 = int(H * 0.60)
    img = vgrad([(0, "#2b1055"), (0.28, "#6a2f94"), (0.46, "#ff71ce"), (0.60, "#ffd1c9"),
                 (0.6003, "#9b3fb8"), (1, "#2b1055")])
    ys, xs = _ys(), _xs()
    etoiles(img, rng, 260, H * 0.2, hexc("#fffb96"), 0.45)
    cl = np.zeros((H, W), F32)
    for nh, nw, am in [(10, 3, 1.0), (22, 7, 0.5), (46, 14, 0.25)]:
        cl += resize(rng.random((nh, nw)).astype(F32), W, H) * am
    cl = (cl - cl.min()) / (cl.max() - cl.min())
    bande = _lisse(0.15 * H, 0.27 * H, ys) * (1 - _lisse(0.50 * H, 0.58 * H, ys))
    t = np.clip((ys - 0.15 * H) / (0.43 * H), 0, 1)
    ccol = (hexc("#01cdfe") * (1 - t) + hexc("#ff9ee0") * t).reshape(H, 1, 3)
    mix(img, np.broadcast_to(ccol, (H, W, 3)), _lisse(0.55, 0.72, cl) * bande * 0.55)
    cx, cy, r = W * 0.5, H * 0.50, 340
    dist = np.hypot(xs - cx, ys - cy)
    disc = np.clip((r - dist) / 2 + 0.5, 0, 1) * np.clip(y0 - ys, 0, 1)
    f = ((ys - cy) / 36.0) % 1
    thr = np.clip((ys - cy) / r, 0, 1) * 0.62
    disc = disc * (1 - np.clip((thr - f) * 40, 0, 1))
    ts = np.clip((ys - (cy - r)) / (2 * r), 0, 1)
    scol = np.broadcast_to((hexc("#fffb96") * (1 - ts) + hexc("#ff71ce") * ts).reshape(H, 1, 3), (H, W, 3))
    _lueur(img, cx, cy, 800, hexc("#ff71ce"), 0.25, ry=600)
    mix(img, scol, disc)
    tm = np.maximum(ys - y0, 0)
    prof = np.clip(tm / (H - y0), 0, 1)
    wob = 22 * np.sin(ys / 21.0) * prof
    colonne = np.exp(-((xs - cx - wob) / (50 + tm * 0.33)) ** 2)
    dash = _lisse(0.30, 0.62, 0.5 + 0.5 * np.sin(2 * np.pi * 6500 / np.maximum(tm, 8)))
    refl = colonne * dash * np.clip(tm / 60, 0, 1) * (tm > 0) * (1 - 0.45 * prof)
    mix(img, hexc("#fffb96"), refl * 0.75)
    ah, _av, pr = sol_perspective(y0, k_h=5200.0)
    mix(img, hexc("#01cdfe"), ah * 0.12 * (1 - pr))
    _lueur(img, W / 2, y0, 2300, hexc("#fffb96"), 0.35, ry=60)
    vignette(img, 0.22, 2.0)
    sauver(img, "vaporwave-mer", bruit=0.5, seed=107)


def vaporwave_damier():
    rng = np.random.default_rng(108)
    y0 = int(H * 0.56)
    img = vgrad([(0, "#2b1055"), (0.22, "#6a2f94"), (0.38, "#ff71ce"), (0.56, "#ffd9ef"), (1, "#ffd9ef")])
    _lueur(img, W * 0.18, H * 0.40, 1100, hexc("#01cdfe"), 0.32, ry=380, mode="mix")
    _lueur(img, W * 0.86, H * 0.46, 1000, hexc("#01cdfe"), 0.26, ry=300, mode="mix")
    _lueur(img, W * 0.5, y0, 1500, hexc("#fffb96"), 0.30, ry=300)
    etoiles(img, rng, 200, H * 0.2, hexc("#fffb96"), 0.4)
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    t = np.maximum(y - y0, 0.5)
    k, c, cx = 9000.0, 4.2, W / 2
    u, v = (x - cx) * c / t, k / t
    du, dv = np.hypot(c / t, (x - cx) * c / t ** 2), k / t ** 2
    s = np.clip(np.sin(np.pi * u) * np.sin(np.pi * v) / (0.5 * np.pi * (du + dv) + 1e-6), -1, 1)
    m = 0.5 + 0.5 * s
    sol = hexc("#3d1a78") * (1 - m)[..., None] + hexc("#ff71ce") * 0.9 * m[..., None]
    lines = np.maximum(ligne_aa(u, du, 2.4), ligne_aa(v, dv, 2.4))
    prof = np.clip(t / (H - y0), 0, 1)
    mix(sol, hexc("#01cdfe"), lines * 0.45 * (0.3 + 0.7 * prof))
    mix(sol, hexc("#ffd9ef"), (1 - prof) ** 2.2 * 0.9)
    img = np.where((y > y0)[..., None], sol, img).astype(F32)
    _lueur(img, W / 2, y0, 2400, hexc("#01cdfe"), 0.30, ry=70)
    vignette(img, 0.25, 2.0)
    sauver(img, "vaporwave-damier", bruit=0.5, seed=108)


# 13-14. pluie-verte
def _colonnes(rng, pas, bh, lw, lmin, lmax, nseg, ymin, ymax, pw=1.0, vmin=0.5):
    """Colonnes verticales de petits blocs (tête vive en bas, queue qui s'éteint)."""
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    tete, queue = np.array([0, 255, 65], F32), np.array([0, 143, 17], F32)
    for x0 in range(int(rng.integers(0, pas)), W, pas):
        for _ in range(int(rng.integers(1, nseg + 1))):
            n = int(rng.integers(lmin, lmax + 1))
            yh = ymax - rng.random() ** pw * (ymax - ymin)
            for kk in range(n):
                y1 = yh - kk * bh * 1.3
                if y1 < ymin or y1 - bh > ymax:
                    continue
                tt = kk / n
                vv = (1 - tt) ** 1.5 * rng.uniform(vmin, 1)
                col = (tete * (1 - tt) + queue * tt) * vv
                if kk == 0:
                    col = tete * 0.75 + 64
                d.rectangle([x0, y1 - bh, x0 + lw, y1], fill=tuple(int(q) for q in col))
    return np.asarray(im, F32) / 255


def _poser_colonnes(img, lay, att=None, glow=0.8):
    if att is not None:
        lay = lay * att[..., None]
    img += lay
    add(img, hexc("#00ff41"), blur(lay[..., 1], 12) * glow)


def pluie_verte_colonnes():
    rng = np.random.default_rng(109)
    img = np.zeros((H, W, 3), F32) + hexc("#000d00")
    add(img, hexc("#008f11"), (fbm(W, H, rng, 6, 5, 0.55) ** 2) * 0.07)
    ys, xs = _ys(), _xs()
    att = 1 - 0.88 * np.exp(-((((xs - W / 2) / 1250) ** 2) + ((ys - H * 0.12) / 520) ** 2))
    att = att.astype(F32)
    _poser_colonnes(img, _colonnes(rng, 26, 9, 11, 14, 60, 2, -50, H + 50, 0.8, 0.35) * 0.55, att, 0.5)
    _poser_colonnes(img, _colonnes(rng, 96, 30, 44, 8, 26, 2, -100, H + 100, 0.9, 0.55), att, 0.9)
    vignette(img, 0.35, 2.0)
    sauver(img, "pluie-verte-colonnes", bruit=0.4, seed=109)


def pluie_verte_horizon():
    rng = np.random.default_rng(110)
    y0 = int(H * 0.60)
    img = np.zeros((H, W, 3), F32) + hexc("#000d00")
    add(img, hexc("#008f11"), (fbm(W, H, rng, 12, 5, 0.6) ** 2) * 0.10)
    ys, xs = _ys(), _xs()
    _lueur(img, W / 2, y0, 2600, hexc("#00ff41"), 0.40, ry=200)
    att = 1 - 0.85 * np.exp(-((((xs - W / 2) / 1300) ** 2) + ((ys - H * 0.12) / 500) ** 2))
    att = att.astype(F32)
    _poser_colonnes(img, _colonnes(rng, 34, 12, 14, 10, 50, 2, 0, y0, 2.2, 0.35) * 0.65, att, 0.5)
    _poser_colonnes(img, _colonnes(rng, 110, 34, 50, 6, 20, 1, 0, y0, 2.0, 0.55), att, 0.9)
    hh = H - y0
    refl = img[y0 - hh:y0][::-1].copy()
    xi = (np.arange(W)[None, :] + (16 * np.sin(np.arange(hh)[:, None] / 7.0 + np.arange(hh)[:, None] ** 0.5)).astype(int)) % W
    refl = refl[np.arange(hh)[:, None], xi]
    fade = ((1 - np.arange(hh) / hh) ** 1.3)[:, None, None].astype(F32)
    img[y0:] = img[y0:] * 0.25 + refl * 0.55 * fade
    mix(img, hexc("#00ff41"), np.clip(1 - np.abs(ys - y0) / 2.2, 0, 1) * 0.85 * np.ones((1, W), F32))
    vignette(img, 0.38, 2.0)
    sauver(img, "pluie-verte-horizon", bruit=0.4, seed=110)


# 15-16. brutaliste
def _beton(rng, grain=1.0):
    """Béton clair : grain fin, taches larges, joints de coffrage et trous de banche."""
    img = np.zeros((H, W, 3), F32) + hexc("#f0f0ef")
    g = (fbm(W, H, rng, 4, 4, 0.55) - 0.5) * 0.05 + (fbm(W, H, rng, 90, 2, 0.5) - 0.5) * 0.03
    g += (resize(rng.random((H // 2, W // 2)).astype(F32), W, H) - 0.5) * 0.03
    img += (g * grain)[..., None]
    ys, xs = _ys(), _xs()
    pw, ph = 960, 600
    for f, per in ((xs, pw), (ys, ph)):
        e = np.minimum(f % per, per - f % per)
        mix(img, hexc("#8a8a88"), np.clip(1.6 - e / 1.2, 0, 1) * 0.35 * np.ones((H, W), F32))
    for hx in (200, 760):
        for hy in (150, 450):
            dd = np.hypot((xs % pw) - hx, (ys % ph) - hy)
            mix(img, hexc("#a2a2a0"), np.clip(10 - dd, 0, 1) * 0.9)
            mix(img, hexc("#fafafa"), np.clip(1 - np.abs(dd - 11), 0, 1) * 0.5)
    return img


def brutaliste_beton():
    rng = np.random.default_rng(111)
    img = _beton(rng)
    ys, xs = _ys(), _xs()
    x0 = int(W * 0.74)
    ombre = np.clip(1 - (x0 - xs) / 150, 0, 1) * (xs < x0) * (ys < H * 0.78)
    mix(img, np.zeros(3, F32), ombre * 0.22)
    dalle = hexc("#0a0a0a") + (fbm(W, H, rng, 30, 3, 0.5) - 0.5)[..., None] * 0.03
    img[:int(H * 0.78), x0:] = dalle[:int(H * 0.78), x0:]
    yb, xb = int(H * 0.80), int(W * 0.08)
    img[yb:yb + 130, xb:int(W * 0.62)] = hexc("#000000")
    mix(img, np.zeros(3, F32), np.clip(1 - (ys - (yb + 130)) / 120, 0, 1) * ((ys > yb + 130) * (xs > xb + 90) * (xs < W * 0.62 + 90)) * 0.2)
    sx = int(W * 0.46)
    img[yb - 420:yb, sx:sx + 420] = hexc("#ffe600")
    vignette(img, 0.06, 2.0)
    sauver(img, "brutaliste-beton", bruit=0.7, seed=111)


def _bloc(d, x, yb, w, h, dep, cf, cs, ct):
    dx, dy = int(dep * 0.85), int(dep * 0.45)
    d.polygon([(x + w, yb - h), (x + w + dx, yb - h - dy), (x + w + dx, yb - dy), (x + w, yb)], fill=cs)
    d.polygon([(x, yb - h), (x + dx, yb - h - dy), (x + w + dx, yb - h - dy), (x + w, yb - h)], fill=ct)
    d.rectangle([x, yb - h, x + w, yb], fill=cf)


def brutaliste_blocs():
    rng = np.random.default_rng(112)
    img = _beton(rng, 0.9)
    ys = _ys()
    sol = int(H * 0.82)
    mix(img, hexc("#c8c8c6"), np.clip((ys - sol) / 3, 0, 1) * 0.6 * np.ones((1, W), F32))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    blocs = [(2780, 1930, 520, 1250, 200), (3180, 1990, 540, 800, 220), (110, 1950, 560, 1000, 240),
             (560, 2060, 420, 520, 180), (2480, 2100, 300, 380, 130)]
    for x, yb, w, h, dep in blocs:
        dx = int(dep * 0.85)
        d.polygon([(x + w, yb), (x + w + dx, yb - int(dep * 0.45)), (x + w + dx + int(h * 0.55), yb - int(dep * 0.45)),
                   (x + w + int(h * 0.55), yb)], fill=(0, 0, 0, 70))
    gris = [("#d4d4d2", "#9c9c9a", "#ebebea"), ("#0b0b0b", "#050505", "#202020"), ("#c2c2c0", "#868684", "#dededc"),
            ("#a9a9a7", "#6f6f6d", "#c8c8c6"), ("#dcdcda", "#a4a4a2", "#f1f1f0")]
    for (x, yb, w, h, dep), (cf, cs, ct) in zip(blocs, gris):
        rgb = lambda s: tuple(int(s[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
        _bloc(d, x, yb, w, h, dep, rgb(cf), rgb(cs), rgb(ct))
    x, yb, w, h, _ = blocs[2]
    d.rectangle([x + 60, yb - h + 140, x + w - 60, yb - h + 205], fill=(0, 0, 0, 255))
    d.rectangle([x + 60, yb - h + 330, x + w - 60, yb - h + 395], fill=(0, 0, 0, 255))
    x, yb, w, h, _ = blocs[0]
    d.rectangle([x + 40, yb - h + 90, x + w - 40, yb - h + 104], fill=(255, 59, 48, 255))
    d.rectangle([x + 60, yb - 330, x + 150, yb - 20], fill=(0, 0, 0, 255))
    x, yb, w, h, _ = blocs[1]
    d.rectangle([x + 110, yb - h + 80, x + 110 + 300, yb - h + 380], fill=(255, 230, 0, 255))
    x, yb, w, h, _ = blocs[4]
    d.rectangle([x + 40, yb - h + 50, x + w - 40, yb - h + 130], fill=(0, 0, 0, 255))
    _compose(img, im, 0.8)
    img += ((resize(rng.random((H // 2, W // 2)).astype(F32), W, H) - 0.5) * 0.02)[..., None]
    vignette(img, 0.06, 2.0)
    sauver(img, "brutaliste-blocs", bruit=0.7, seed=112)


# 17-18. ocean
def ocean_rayons():
    rng = np.random.default_rng(113)
    img = vgrad([(0, "#1e88e5"), (0.22, "#126bb0"), (0.55, "#0a2a48"), (1, "#0a1929")])
    _lueur(img, W * 0.35, -H * 0.05, 1600, hexc("#26c6da"), 0.25, ry=900)
    s = 4
    yy, xx = np.mgrid[0:H // s, 0:W // s].astype(F32) * s
    ox, oy = W * 0.62, -H * 0.30
    th = np.arctan2(xx - ox, yy - oy)
    for seedk, n, a_, sp in [(1, 16, 0.20, 1.3), (2, 30, 0.10, 1.0)]:
        prof = fbm1d(1024, rng, n, 4, 0.55) * 0.5 + 0.5
        u = np.clip((th + 0.9) / 1.8 * 1023, 0, 1023)
        ray = _lisse(0.45, 0.9, np.interp(u, np.arange(1024), prof)) ** sp
        ray *= np.exp(-np.hypot(xx - ox, yy - oy) / 2900)
        add(img, hexc("#26c6da"), np.clip(resize(ray.astype(F32), W, H), 0, 1) * a_)
    ys, xs = _ys(), _xs()
    yc = _dune(rng, H * 0.87, 60, [0.8, 1.6, 2.7])
    m, d = _couche(yc)
    sable = hexc("#ffe0b2") * 0.55 + hexc("#0a2a48") * 0.45
    ca = fbm(W, H, rng, 36, 3, 0.5)
    caus = np.clip(1 - np.abs(ca - 0.5) / 0.035, 0, 1) ** 2
    rid = 0.5 + 0.5 * np.sin(ys / 9.0 + 40 * fbm(W, H, rng, 6, 2, 0.5))
    col = sable * (1 - 0.35 * np.clip(d / 500, 0, 1))[..., None] * (0.92 + 0.08 * rid[..., None])
    mix(img, col, m)
    add(img, hexc("#e3f2fd"), caus * m * 0.10)
    mix(img, hexc("#0a2a48"), m * np.clip(1 - d / 500, 0, 1) * 0.0 + np.exp(-(d / 70) ** 2) * m * 0.0)
    etoiles(img, rng, 700, H * 0.85, hexc("#e3f2fd"), 0.30)
    vignette(img, 0.30, 2.0)
    sauver(img, "ocean-rayons", bruit=0.5, seed=113)


def ocean_lune():
    rng = np.random.default_rng(114)
    y0 = int(H * 0.46)
    img = vgrad([(0, "#0a1929"), (0.3, "#0f2744"), (0.46, "#12324f"), (1, "#12324f")])
    ys, xs = _ys(), _xs()
    etoiles(img, rng, 520, H * 0.40, hexc("#e3f2fd"), 0.55)
    cx, cy, r = W * 0.66, H * 0.26, 150
    _lueur(img, cx, cy, 900, hexc("#1e88e5"), 0.20)
    _lueur(img, cx, cy, 380, hexc("#e3f2fd"), 0.30)
    dist = np.hypot(xs - cx, ys - cy)
    cr = fbm(W, H, rng, 14, 4, 0.5)
    disque = np.clip((r - dist) / 1.6 + 0.5, 0, 1)
    mix(img, hexc("#e3f2fd") * (0.9 + 0.1 * cr[..., None]) * (1 - 0.10 * np.clip((xs - cx) / r, 0, 1))[..., None], disque)
    mix(img, hexc("#12324f"), np.clip(y0 - ys + 0.5, -1, 0) * 0 + (ys > y0) * 1.0)
    n = 7
    for i in range(n):
        f = i / (n - 1)
        base = y0 + (H - y0) * (0.015 + 0.80 * f ** 1.5)
        yc = _dune(rng, base, 8 + 46 * f, [4 + 9 * (1 - f), 9 + 14 * (1 - f)])
        m, dd = _couche(yc)
        c0 = hexc("#1a4f7e") * (1 - f) + hexc("#071322") * f
        col = c0 * (1 - 0.35 * np.clip(dd / 280, 0, 1))[..., None]
        mix(img, col, m)
        mix(img, hexc("#1e88e5"), np.clip(1 - np.abs(dd) / (2.0 + 2.5 * f), 0, 1) * (0.30 + 0.25 * (1 - f)))
    tm = np.maximum(ys - y0, 0)
    prof = np.clip(tm / (H - y0), 0, 1)
    rowr = (fbm1d(H, rng, 120, 2, 0.5) * 0.5 + 0.5).astype(F32)[:, None]
    wob = 25 * np.sin(ys / 17.0) * prof
    colonne = np.exp(-((xs - cx - wob) / (24 + tm * 0.16)) ** 2)
    refl = colonne * _lisse(0.40, 0.65, rowr) * np.clip(tm / 40, 0, 1) * (tm > 0) * (1 - 0.6 * prof)
    add(img, hexc("#e3f2fd"), refl * 0.55)
    mix(img, hexc("#1e88e5"), np.clip(1 - np.abs(ys - y0) / 2.0, 0, 1) * 0.6 * np.ones((1, W), F32))
    vignette(img, 0.30, 2.0)
    sauver(img, "ocean-lune", bruit=0.5, seed=114)




IMAGES = {
    "retro-grille": retro_grille, "retro-ambre": retro_ambre,
    "synthwave-soleil": synthwave_soleil, "synthwave-montagnes": synthwave_montagnes,
    "tokyo-ville": tokyo_ville, "tokyo-pluie": tokyo_pluie,
    "apple-dunes": apple_dunes, "apple-ondes": apple_ondes,
    "catppuccin-brume": catppuccin_brume, "nord-fjord": nord_fjord,
    "dracula-nuit": dracula_nuit, "dracula-ondes": dracula_ondes, "nord-glacier": nord_glacier,
    "rose-aube-collines": rose_aube_collines,
    "rose-aube-papier": rose_aube_papier,
    "everforest-sapins": everforest_sapins,
    "everforest-sousbois": everforest_sousbois,
    "solarized-clair-cercles": solarized_clair_cercles,
    "solarized-clair-dunes": solarized_clair_dunes,
    "papier-estampe": papier_estampe,
    "papier-vide": papier_vide,
    "clair-neutre-formes": clair_neutre_formes,
    "clair-neutre-vagues": clair_neutre_vagues,
    "sakura-branche": sakura_branche,
    "sakura-lune": sakura_lune,
    "matrice-relief": matrice_relief,
    "matrice-cercle": matrice_cercle,
    "cyberjaune-ville": cyberjaune_ville,
    "cyberjaune-circuits": cyberjaune_circuits,
    "vaporwave-mer": vaporwave_mer,
    "vaporwave-damier": vaporwave_damier,
    "pluie-verte-colonnes": pluie_verte_colonnes,
    "pluie-verte-horizon": pluie_verte_horizon,
    "brutaliste-beton": brutaliste_beton,
    "brutaliste-blocs": brutaliste_blocs,
    "ocean-rayons": ocean_rayons,
    "ocean-lune": ocean_lune,
}

if __name__ == "__main__":
    depot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if len(sys.argv) < 2 or os.path.commonpath([depot, os.path.abspath(sys.argv[1])]) == depot:
        sys.exit("usage : generer_fonds.py DOSSIER [nom...] (DOSSIER hors du dépôt)")
    ICI = os.path.abspath(sys.argv[1])
    noms = sys.argv[2:] or list(IMAGES)
    for nom in noms:
        if nom not in IMAGES:
            sys.exit("inconnu : %s (choix : %s)" % (nom, ", ".join(IMAGES)))
        t0 = time.time()
        IMAGES[nom]()
        print("%-22s %.1f s" % (nom, time.time() - t0), flush=True)
