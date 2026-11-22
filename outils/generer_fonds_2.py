#!/usr/bin/env python3
"""generer_fonds_2 : seize autres fonds d'écran de thème, dessinés par nous (art procédural), 3840x2400 (16:10).

Suite de generer_fonds.py (il en reprend les outils de base) : deux fonds de plus pour apple, oled, tokyo,
synthwave, retro, catppuccin, dracula et nord. Outil du dépôt, pas un script installé : il demande numpy et Pillow.
Les images livrées sont dans home/Pictures/Wallpapers/<thème>/ (crédits : CREDITS.tsv, « généré par noctalia-config »).

Usage : python3 outils/generer_fonds_2.py DOSSIER [nom...]   (sans nom : tout)
Sortie : DOSSIER/jpg/<nom>.jpg (JPEG de moins de 900 Ko, qualité réglée toute seule). DOSSIER est obligatoire et
ne doit pas être dans le dépôt : rien n'est jamais généré ici. Graine fixe par image : résultat reproductible.
"""
import io
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generer_fonds import (F32, H, W, _lisse, add, blur, fbm, fbm1d, hexc,  # noqa: E402
                           ligne_aa, resize, resize3, vgrad, vignette)

ICI = ""                 # le dossier de sortie, donné en premier argument
MAX_OCTETS = 880_000     # sous les 900 Ko demandés, avec une marge
rgb = hexc


# --------------------------------------------------------------------------
# Outils de plus
# --------------------------------------------------------------------------
def sauver2(img, nom, bruit=0.4, seed=0, noir_pur=False):
    """Tramage léger (contre les bandes) puis JPEG : qualité la plus haute qui tient dans MAX_OCTETS.
    noir_pur : les pixels éteints restent à 0 exact (écran OLED)."""
    rng = np.random.default_rng(seed + 999)
    base = np.clip(img, 0, 1) * 255
    bruit_img = rng.normal(0, bruit, img.shape).astype(F32)
    if noir_pur:
        bruit_img *= (base.max(-1, keepdims=True) > 1.2)
    im = Image.fromarray(np.clip(base + bruit_img + 0.5, 0, 255).astype(np.uint8), "RGB")
    if im.size != (W, H):
        raise SystemExit("taille inattendue : %s" % (im.size,))
    os.makedirs(os.path.join(ICI, "jpg"), exist_ok=True)
    meilleur = None
    for sous in (0, 2):                       # 4:4:4 d'abord, 4:2:0 si la qualité devient trop basse
        bas, haut, ok = 50, 95, None
        while bas <= haut:
            q = (bas + haut) // 2
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=q, subsampling=sous, optimize=True)
            if buf.tell() <= MAX_OCTETS:
                ok, bas = (q, buf.getvalue()), q + 1
            else:
                haut = q - 1
        if ok and (ok[0] >= 82 or sous == 2):
            meilleur = ok
            break
        meilleur = ok or meilleur
    if meilleur is None:
        raise SystemExit("%s : impossible de tenir sous %d octets" % (nom, MAX_OCTETS))
    with open(os.path.join(ICI, "jpg", nom + ".jpg"), "wb") as f:
        f.write(meilleur[1])
    return meilleur[0], len(meilleur[1])


def grille(h=H, w=W):
    return np.mgrid[0:h, 0:w].astype(F32)


def halo(y, x, cx, cy, r):
    """Disque lumineux doux : 1 au centre, s'éteint vers r."""
    return np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * r * r))


def couche(img, masque, col):
    """Remplit img avec la couleur col là où masque (alpha 0..1) ; col peut être un tableau (H, W, 3)."""
    m = np.clip(masque, 0, 1)[..., None]
    if isinstance(col, str):
        col = hexc(col)
    img += (np.asarray(col, F32) - img) * m
    return img


def sous_profil(y, prof):
    """Alpha antialiasé de la zone sous un profil prof (une hauteur par colonne)."""
    return np.clip(y - prof[None, :] + 0.5, 0, 1)


def pointillees(rng, n, ymax, force=(0.2, 1.0), h=H, w=W):
    """Étoiles : points isolés (H, W) à flouter ensuite."""
    p = np.zeros((h, w), F32)
    ys = np.minimum((rng.random(n) ** 1.3 * ymax).astype(int), h - 1)
    p[ys, rng.integers(0, w, n)] = rng.random(n) * (force[1] - force[0]) + force[0]
    return p


def etoiles2(img, rng, n, ymax, col="#dfe6ff", a=0.8, masque=None):
    e = np.clip(blur(pointillees(rng, n, ymax), 1.0) * 5, 0, 1) * a
    if masque is not None:
        e = e * masque
    return add(img, rgb(col), e)


def pil_masque(dessin):
    """Masque 0..1 (H, W) : dessin(draw, k) dessine sur une image PIL 'L' suréchantillonnée de k=2."""
    im = Image.new("L", (W * 2, H * 2), 0)
    dessin(ImageDraw.Draw(im), 2)
    im = im.resize((W, H), Image.Resampling.LANCZOS)
    return np.asarray(im, F32) / 255


# --------------------------------------------------------------------------
# apple : dégradé maillé liquide, collines de crépuscule
# --------------------------------------------------------------------------
def apple_liquide():
    rng = np.random.default_rng(201)
    w, h = 960, 600
    y, x = grille(h, w)
    u, v = x / w, y / h
    u2 = u + (fbm(w, h, rng, 3, 4) - 0.5) * 0.60
    v2 = v + (fbm(w, h, rng, 3, 4) - 0.5) * 0.60
    taches = [(0.10, 0.80, 0.34, "#1f5bff", 1.0), (0.42, 0.70, 0.30, "#8a4dff", 1.0),
              (0.78, 0.88, 0.30, "#ff8a3d", 1.1), (0.58, 1.02, 0.26, "#ff4f9a", 1.0),
              (0.95, 0.46, 0.30, "#3aa8ff", 0.8), (0.18, 0.30, 0.28, "#3b2bd0", 0.7),
              (0.50, 0.02, 0.48, "#050a26", 2.6)]
    num, den = np.zeros((h, w, 3), F32), np.full((h, w), 0.02, F32)
    for cu, cv, r, col, p in taches:
        wgt = p * np.exp(-((u2 - cu) ** 2 + (v2 - cv) ** 2) / (2 * r * r))
        num += rgb(col) * wgt[..., None]
        den += wgt
    img = num / den[..., None]
    s = np.sin((u2 * 5.2 + v2 * 7.4) * 2 * np.pi + 5 * fbm(w, h, rng, 2, 3))
    soie = np.clip(s, 0, 1) ** 3 * _lisse(0.18, 0.75, v)
    img += np.stack([soie * 0.05, soie * 0.045, soie * 0.06], -1)
    img *= (0.42 + 0.58 * _lisse(0.0, 0.62, v))[..., None]       # haut calme et sombre
    img = resize3(img, W, H)
    vignette(img, 0.28, 2.2)
    return sauver2(img, "apple-liquide", seed=201)


def apple_collines():
    rng = np.random.default_rng(202)
    y, x = grille()
    v = y / H
    img = vgrad([(0, "#070b24"), (0.30, "#1c1d5c"), (0.50, "#5a3a92"), (0.64, "#c55a86"),
                 (0.74, "#ff9a64"), (0.82, "#ffd29a"), (1, "#ffc88a")], H, W)
    sx, sy = 0.30 * W, 0.745 * H
    add(img, rgb("#ff9a5a"), 0.55 * halo(y, x, sx, sy, 520))
    add(img, rgb("#ffe0b0"), 0.55 * halo(y, x, sx, sy, 150))
    etoiles2(img, rng, 500, H * 0.36, masque=1 - _lisse(0.15, 0.4, v))
    xs = np.arange(W, dtype=F32)
    n = 6
    for i in range(n):
        k = i / (n - 1)
        prof = (0.60 + 0.075 * i) * H - 150 * fbm1d(W, rng, 2, 3, 0.5) * (1 - 0.35 * k) \
            - 60 * np.sin(xs / W * np.pi * (1.1 + 0.4 * i) + i)
        m = sous_profil(y, prof)
        loin, pres = rgb("#a05a9c"), rgb("#07051c")
        col = loin + (pres - loin) * (k ** 0.85)
        dep = np.clip((y - prof[None, :]) / 520, 0, 1)
        teinte = col + (pres - col) * (0.55 * dep[..., None])
        couche(img, m, teinte)
        cote = np.exp(-((xs - sx) / 1500) ** 2)[None, :]
        add(img, rgb("#ffb070"), m * np.exp(-np.clip(y - prof[None, :], 0, None) / 26) * cote * 0.38 * (1 - 0.8 * k))
        add(img, rgb("#d6808c") * (1 - k) + rgb("#2a1c5e") * k,
            0.16 * np.exp(-((y - prof[None, :] - 80) / 160) ** 2))
    vignette(img, 0.30, 2.2)
    return sauver2(img, "apple-collines", seed=202)


# --------------------------------------------------------------------------
# oled : arc de planète, lignes de niveau
# --------------------------------------------------------------------------
def oled_arc():
    rng = np.random.default_rng(211)
    y, x = grille()
    R, cx, cy = 7400.0, W * 0.5, H * 0.90 + 7400.0
    d = np.hypot(x - cx, y - cy) - R                      # < 0 : dans la planète
    lum = np.exp(-((x - 0.66 * W) / 1250) ** 2) * 0.92 + 0.08
    fin = np.exp(-(np.maximum(-d, 0) / 5.5) ** 1.2) * np.clip(1 - np.maximum(d, 0) / 1.5, 0, 1)
    dehors = np.clip(d, 0, None)
    atmo = (np.exp(-dehors / 22) * 0.55 + np.exp(-dehors / 170) * 0.16) * (d > -1.5)
    dedans = np.exp(-np.maximum(-d, 0) / 70) * 0.30 * (d < 0)
    img = np.zeros((H, W, 3), F32)
    add(img, rgb("#fff1dc"), fin * lum)
    add(img, rgb("#6d9dff"), (atmo + dedans) * lum * 0.85)
    add(img, rgb("#ffb27a"), np.exp(-dehors / 9) * 0.35 * lum * (d > -1.5) * np.exp(-((x - 0.66 * W) / 520) ** 2))
    do = np.abs(np.hypot(x - cx, y - cy) - (R + 330))
    add(img, rgb("#a8b8d8"), np.clip(1.3 - do / 1.1, 0, 1) * 0.16 * np.exp(-((x - 0.5 * W) / 1500) ** 2))
    p = pointillees(rng, 160, H * 0.7, (0.15, 0.65))
    add(img, rgb("#cfd8ff"), np.clip(blur(p, 0.9) * 4.5, 0, 1) * 0.55)
    return sauver2(img, "oled-arc", bruit=0.0, seed=211, noir_pur=True)


def oled_relief():
    rng = np.random.default_rng(212)
    y, x = grille()
    hh = resize(fbm(1280, 800, rng, 3, 5, 0.48), W, H)
    hh = hh + 0.10 * resize(fbm(640, 400, rng, 8, 3, 0.5), W, H)
    f1 = hh * 34
    gy, gx = np.gradient(f1)
    fin = ligne_aa(f1, np.hypot(gx, gy), 2.0)
    f5 = f1 / 5
    gy5, gx5 = np.gradient(f5)
    gras = ligne_aa(f5, np.hypot(gx5, gy5), 3.6)
    nu = np.clip(fin * 0.36 + gras * 0.62, 0, 1)
    r = np.hypot((x - 0.62 * W) / (W * 0.62), (y - 0.62 * H) / (H * 0.62))
    zone = np.clip(1.05 - r ** 1.5, 0, 1)
    calme = 1 - 0.85 * np.exp(-((x - W / 2) / 1100) ** 2) * (1 - _lisse(0.0, 0.34, y / H))
    nu = nu * zone * calme
    img = np.repeat(nu[..., None], 3, -1).astype(F32)
    img[..., 2] *= 1.04
    return sauver2(img, "oled-relief", bruit=0.0, seed=212, noir_pur=True)


# --------------------------------------------------------------------------
# tokyo : tours vues d'en bas, ruelle de néons
# --------------------------------------------------------------------------
def _hash(a, b, s):
    """Hachage entier vectorisé -> valeurs dans [0,1]."""
    h = (a.astype(np.int64) * 73856093) ^ (b.astype(np.int64) * 19349663) ^ (int(s) * 83492791)
    h = ((h ^ (h >> 13)) * 1274126177) & 0x7FFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def _bloom(img, E, poids=((5, 0.9), (22, 0.5), (75, 0.35))):
    for sg, p in poids:
        for k in range(3):
            img[..., k] += p * blur(np.ascontiguousarray(E[..., k]), sg)
    return img


def tokyo_tours():
    rng = np.random.default_rng(221)
    img = vgrad([(0, "#0c1238"), (0.5, "#222a74"), (1, "#b0527a")], H, W)
    vpx, vpy = W / 2, -2500.0
    ys = np.arange(H, dtype=F32)[:, None]
    s = (ys - vpy) / (H - vpy)
    E = np.zeros((H, W, 3), F32)
    tours = []
    for i in range(8):                                           # lointaines, au centre
        tours.append((rng.uniform(-1000, 1000), rng.uniform(100, 190), rng.uniform(28, 44),
                      rng.uniform(0.62, 0.86) if i % 2 else None, 0.80))
    for i in range(7):                                           # moyennes
        c = (1 if i % 2 else -1) * rng.uniform(450, 1400)
        tours.append((c, rng.uniform(200, 320), rng.uniform(30, 46),
                      rng.uniform(0.60, 0.80) if i % 3 == 0 else None, 0.52))
    for c, hw in ((-1750, 470), (1800, 430), (-2300, 380), (2350, 400)):    # proches, sur les bords
        tours.append((c, hw, rng.uniform(34, 48), None, 0.16))
    warm, cool, pink = rgb("#ffd69a"), rgb("#a6d4ff"), rgb("#ff8fc8")
    fogc = rgb("#2d3a96")
    for n, (c, hw, af, stop, fog0) in enumerate(tours):
        smin = float(s[0, 0])
        x0 = int(max(0, vpx + min(c * smin, c) - hw - 12))
        x1 = int(min(W, vpx + max(c * smin, c) + hw + 12))
        if x1 <= x0:
            continue
        xr = np.arange(x0, x1, dtype=F32)[None, :]
        u = (xr - vpx) / s - c
        al = np.clip((hw - np.abs(u)) * s + 0.5, 0, 1)
        ytop = 0.0
        if stop is not None:
            ytop = vpy + (H - vpy) * stop
            al = al * np.clip(ys - ytop + 0.5, 0, 1)
        Lf = af * (1 / s - 1)
        fi, fy = np.floor(Lf), Lf - np.floor(Lf)
        nc = max(3, int(round(2 * hw / rng.uniform(44, 64))))
        cu = (u + hw) / (2 * hw) * nc
        ci, cx = np.floor(cu), cu - np.floor(cu)
        cellpx = (2 * hw / nc) * s
        fpx = (H - vpy) * s ** 2 / af
        wx = np.clip((0.30 - np.abs(cx - 0.5)) * cellpx + 0.5, 0, 1)
        wy = np.clip((0.30 - np.abs(fy - 0.5)) * fpx + 0.5, 0, 1)
        r1, r2, r3 = _hash(ci, fi, n), _hash(ci, fi, n + 100), _hash(fi, ci, n + 200)
        lit = (r1 > 0.56 + 0.12 * (fog0 > 0.6)) * (0.30 + 0.70 * r3)
        pal = warm * (r2 >= 0.2)[..., None] + cool * (r2 < 0.12)[..., None] \
            + pink * ((r2 >= 0.12) & (r2 < 0.2))[..., None]
        win = (wx * wy * lit)[..., None]
        body = rgb("#0a0f30") * (0.8 + 0.4 * _hash(np.array([n]), np.array([0]), 5)[0])
        body = body + rgb("#9c4a7c") * 0.30 * _lisse(0.6, 1.0, s)[..., None] + rgb("#1a2c70") * 0.5 * _lisse(0.9, 0.5, s)[..., None]
        body = body + rgb("#5b72d8") * 0.30 * np.clip(1 - (hw - np.abs(u)) * s / 3.0, 0, 1)[..., None]
        body = body + rgb("#223a8c") * 0.20 * (wx * wy)[..., None]
        fog = fog0 + (1 - fog0) * 0.35 * _lisse(0.9, 0.5, s)
        emi = pal * win * (1 - fog0 * 0.55)
        col = (body + emi) * (1 - fog)[..., None] if np.ndim(fog) else (body + emi) * (1 - fog)
        col = col + fogc * np.asarray(fog)[..., None] if np.ndim(fog) else col + fogc * fog
        if stop is not None:
            rim = np.exp(-np.abs(ys - ytop) / 2.5) * np.clip((hw - np.abs(u)) * s, 0, 1)
            col = col + rgb("#9fb2ff") * (0.35 * rim * (1 - fog0 * 0.6))[..., None]
            ua = c * 0 + hw * rng.uniform(-0.5, 0.5)
            ah = 170.0 * (1 - fog0 * 0.4)
            ant = np.clip(1.5 - np.abs(u - ua) * s, 0, 1) * np.clip(ytop - ys + 0.5, 0, 1) * np.clip(ys - (ytop - ah) + 0.5, 0, 1)
            col = col * (1 - ant[..., None]) + rgb("#0b1030") * ant[..., None]
            al = np.maximum(al, ant)
            yl = ytop - ah
            lampe = np.exp(-((xr - (vpx + (c + ua) * float(np.clip((ytop - vpy) / (H - vpy), 0.5, 1)))) ** 2 + (ys - yl) ** 2) / 18)
            E[:, x0:x1] += rgb("#ff3b3b") * (lampe * 1.4)[..., None] * (1 - fog0 * 0.5)
        sl = img[:, x0:x1]
        sl += (col - sl) * al[..., None]
        e = E[:, x0:x1]
        e *= (1 - al)[..., None]
        e += (emi * (1 - fog)[..., None]) * al[..., None]
    # brume du haut : la zone de la barre et de l'île reste calme
    y, x = grille()
    v = y / H
    add(img, rgb("#4a5ec8"), 0.40 * halo(y, x, W / 2, -150, 1200) * 1.0)
    add(img, rgb("#ff7a62"), 0.22 * _lisse(0.78, 1.0, v))
    calme = halo(y, x, W / 2, 80, 1000)
    img += (img.mean(-1, keepdims=True) - img) * (0.35 * calme)[..., None]
    _bloom(img, E)
    vignette(img, 0.30, 2.2)
    return sauver2(img, "tokyo-tours", seed=221)


def tokyo_ruelle():
    """Ruelle de néons sous la pluie, vue de la rue : murs et sol calculés en perspective, reflets au sol."""
    rng = np.random.default_rng(222)
    y, x = grille()
    f, vpx, vpy, camh, XW = 2000.0, W / 2, 960.0, 1.6, 4.6
    dx = np.abs(x - vpx) + 0.5
    cote = (x > vpx).astype(np.int64)
    Zw = f * XW / dx
    dy = y - vpy
    Zf = f * camh / np.maximum(dy, 1.0)
    mur = (dy <= 1) | (dx * Zf / f > XW)
    Y = camh + (vpy - y) * Zw / f
    m = Zw / f                                                   # mètres par pixel sur le mur
    zz = Zw / 1.8 + cote * 0.5
    zi = np.floor(zz)
    u = (zz - zi) * 1.8
    ri = np.floor(Y / 3.0)
    v = (Y / 3.0 - ri) * 3.0
    ht = 24 + 10 * _hash(np.floor(Zw / 9.0), cote, 11) + 0.9 * Zw
    batiment = Y < ht
    body = rgb("#1a1740") * (0.65 + 0.7 * _hash(zi, cote, 12))[..., None]
    body = body * (0.55 + 0.45 * _lisse(0, 14, Y))[..., None]
    wz = np.clip((0.5 - np.abs(u - 0.9)) / m + 0.5, 0, 1)
    wy = np.clip((0.6 - np.abs(v - 1.7)) / m + 0.5, 0, 1)
    hl = _hash(zi * 7 + cote, ri, 21)
    lit = (hl > 0.55) * (0.3 + 0.5 * _hash(zi, ri, 22)) * (Y > 4.2)
    t = _hash(zi, ri, 23)
    chaud, froid, rose = rgb("#ffc27a"), rgb("#8fd6ff"), rgb("#ff8cc4")
    pal = chaud * (t >= 0.3)[..., None] + froid * (t < 0.15)[..., None] + rose * ((t >= 0.15) & (t < 0.3))[..., None]
    E = pal * (wz * wy * lit * 0.9)[..., None]
    # devantures au rez-de-chaussée
    ws = np.clip((0.75 - np.abs(u - 0.9)) / m + 0.5, 0, 1) * np.clip((1.4 - np.abs(Y - 1.7)) / m + 0.5, 0, 1)
    tc = _hash(zi, cote, 31)
    shop = rgb("#ffb060") * (tc < 0.4)[..., None] + rgb("#ff4fa0") * ((tc >= 0.4) & (tc < 0.6))[..., None] \
        + rgb("#35e0ff") * ((tc >= 0.6) & (tc < 0.8))[..., None] + rgb("#ffe6a8") * (tc >= 0.8)[..., None]
    E = E + shop * (ws * (1.1 - 0.35 * np.clip(Y / 3.0, 0, 1)))[..., None] * 0.9
    # enseignes verticales : des blocs allumés, aucun texte
    hs = _hash(zi, cote, 41) > 0.5
    top = 3.9 + 2.5 + 6 * _hash(zi, cote, 42)
    ws2 = np.clip((0.2 - np.abs(u - 0.9)) / m + 0.5, 0, 1) * np.clip((Y - 3.9) / m + 0.5, 0, 1) \
        * np.clip((top - Y) / m + 0.5, 0, 1) * hs
    on = _hash(zi * 3 + cote, np.floor(Y / 0.55), 43) > 0.28
    tn = _hash(zi, cote, 44)
    neon = rgb("#ff3d9a") * (tn < 0.3)[..., None] + rgb("#27e5ff") * ((tn >= 0.3) & (tn < 0.55))[..., None] \
        + rgb("#ff9a2a") * ((tn >= 0.55) & (tn < 0.8))[..., None] + rgb("#7dff9a") * (tn >= 0.8)[..., None]
    body = body * (1 - 0.7 * (ws2 * 0 + np.clip((0.32 - np.abs(u - 0.9)) / m + 0.5, 0, 1) * hs * (Y > 3.8) * (Y < top))[..., None])
    E = E + neon * (ws2 * (0.3 + 0.7 * on) * 1.7)[..., None]
    fogw = 1 - np.exp(-Zw / 30.0)
    fogc = rgb("#3b2f78")
    # lumière tamisée en haut au centre : la barre et l'île restent lisibles
    calme = (1 - 0.85 * halo(y, x, W / 2, 0, 900))[..., None]
    E = E * (1 - fogw)[..., None] * calme
    paroi = body * (1 - fogw)[..., None] + fogc * fogw[..., None] * 0.9
    ciel = vgrad([(0, "#070924"), (0.4, "#241a58"), (1, "#7a3a86")], H, W)
    img = np.where(batiment[..., None], paroi, ciel)
    img = np.where(mur[..., None], img, 0)
    E = E * (batiment & mur)[..., None]
    # sol mouillé : reflets des murs, par flaques
    yg = vpy + camh / XW * dx
    idx = np.clip(2 * yg - y, 0, H - 1).astype(np.int64)
    R = np.take_along_axis(E, idx[..., None], axis=0)
    for k in range(3):
        R[..., k] = blur(np.ascontiguousarray(R[..., k]), 5)
    flaque = resize(fbm(960, 600, rng, 4, 4), W, H)
    wet = 0.35 + 0.65 * _lisse(0.42, 0.68, flaque)
    frs = 0.25 + 0.9 * np.exp(-np.maximum(dy, 0) / 800.0)
    fog2 = 1 - np.exp(-Zf / 38.0)
    sol = rgb("#0c0b22") * (1 - fog2)[..., None] + fogc * (fog2 * 0.9)[..., None] + R * (wet * frs * 0.8)[..., None]
    sol = sol + rgb("#ff7aa6") * (0.06 * wet * np.exp(-np.maximum(dy, 0) / 500.0))[..., None]
    img = np.where(mur[..., None], img, sol)
    img = np.ascontiguousarray(img, F32)
    add(img, rgb("#ff9ec0"), 0.55 * halo(y, x, vpx, vpy - 30, 260))
    add(img, rgb("#6a5ae0"), 0.30 * halo(y, x, vpx, vpy, 900))
    _bloom(img, E * 0.9)
    vignette(img, 0.32, 2.2)
    return sauver2(img, "tokyo-ruelle", seed=222)


# --------------------------------------------------------------------------
# synthwave : la route vers le soleil, la ville sur l'eau
# --------------------------------------------------------------------------
def _palmier(d, k, x, yb, hh, pen, r):
    pts = [((x + pen * t * t * hh) * k, (yb - hh * t) * k) for t in np.linspace(0, 1, 28)]
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=255, width=int(max(3.0, hh * (0.05 - 0.03 * i / 27)) * k))
    tx, ty = pts[-1]
    L = hh * 0.55
    for a in np.linspace(0, 2 * np.pi, 13)[:-1] + r.uniform(-0.1, 0.1):
        ts = np.linspace(0, 1, 16)
        px = tx + L * np.cos(a) * ts * k
        py = ty - L * 0.42 * ts * k + L * 0.95 * (ts ** 2) * k * (0.6 + 0.4 * abs(np.cos(a)))
        for i in range(15):
            d.line([(px[i], py[i]), (px[i + 1], py[i + 1])], fill=255,
                   width=int(max(2.0, hh * 0.028 * (1 - ts[i])) * k))


def synthwave_route():
    rng = np.random.default_rng(223)
    y, x = grille()
    y0, cx = 0.56 * H, W / 2
    img = vgrad([(0, "#07031f"), (0.30, "#2a0b63"), (0.46, "#8a1b8f"), (0.53, "#ff3f8f"), (0.56, "#ffa04a"),
                 (1, "#ffa04a")], H, W)
    etoiles2(img, rng, 1500, int(y0 * 0.7), masque=_lisse(y0 * 0.62, 0, y))
    # soleil rayé
    scy, sr = y0 - 330, 470.0
    d = np.hypot(x - cx, y - scy)
    tt = (y - (scy - sr)) / (2 * sr)
    sun = np.stack([np.clip(1.0 - 0 * tt, 0, 1)] * 3, -1)
    c1, c2, c3 = rgb("#ffe45c"), rgb("#ff5aa0"), rgb("#b21fa8")
    k1, k2 = _lisse(0.0, 0.55, tt)[..., None], _lisse(0.5, 1.0, tt)[..., None]
    sun = c1 + (c2 - c1) * k1
    sun = sun + (c3 - sun) * k2
    alpha = np.clip(sr - d + 0.5, 0, 1) * np.clip(y0 - y + 0.5, 0, 1)
    for j in range(7):
        tj, th = 0.52 + 0.075 * j, 0.004 + 0.0085 * j
        alpha *= 1 - np.clip((th - np.abs(tt - tj)) * 2 * sr / 2 + 0.5, 0, 1)
    add(img, rgb("#ff2f9a"), 0.38 * halo(y, x, cx, scy, 800) * _lisse(0, y0, y))
    couche(img, alpha, sun)
    # collines lointaines
    amp = 30 + 240 * _lisse(380, 2000, np.abs(np.arange(W, dtype=F32) - cx))
    prof = y0 - 25 - amp * (fbm1d(W, rng, 6, 5, 0.5) * 0.5 + 0.5)
    couche(img, sous_profil(y, prof) * np.clip(y0 - y + 0.5, 0, 1), rgb("#1c0745"))
    # sol et route
    dd = np.maximum(y - y0, 0.0) + 1.0
    sol = rgb("#12053a") + (rgb("#05011a") - rgb("#12053a")) * _lisse(0, 1000, dd)[..., None]
    hw = dd * 1.15
    ax = np.abs(x - cx)
    route = np.clip(hw - ax + 0.5, 0, 1)
    asph = rgb("#100b2c") * np.ones((H, W, 1), F32)
    reflet = np.exp(-(ax / (0.10 * hw + 22)) ** 2 / 2) * np.exp(-dd / 600.0)
    asph = asph + rgb("#ff7a3a") * (0.45 * reflet)[..., None]
    wl = 1.5 + dd * 0.012
    for sg, col in ((-1, "#ff3d9a"), (1, "#28e6ff")):
        ex = np.abs((x - cx) * sg + hw * 0.93)
        ligne = np.exp(-(ex / wl) ** 2) + 0.35 * np.exp(-ex / (wl * 7))
        asph = asph + rgb(col) * (ligne * _lisse(0, 25, dd))[..., None] * 1.3
    fr = (900.0 / dd * 0.5) % 1.0
    dash = np.clip((0.25 - np.abs(fr - 0.25)) * dd * dd / 450.0 + 0.5, 0, 1) * _lisse(30, 160, dd)
    dash = dash * np.clip((4 + dd * 0.012) - ax + 0.5, 0, 1)
    asph = asph + rgb("#ffe9a8") * dash[..., None] * 0.9
    # grille de part et d'autre
    p = (x - cx) / dd
    fq = (p * 4 + 0.5) % 1.0 - 0.5
    gl = np.exp(-((np.abs(fq) / 4 * dd) / (1.2 + dd * 0.004)) ** 2)
    f2 = (1400.0 / dd) % 1.0
    gl = np.maximum(gl, np.exp(-((np.minimum(f2, 1 - f2) * dd * dd / 1400.0) / (1.2 + dd * 0.004)) ** 2))
    gl = gl * _lisse(15, 160, dd) * _lisse(hw * 1.0, hw * 1.08, ax)
    sol = sol + rgb("#c02cff") * (0.5 * gl)[..., None]
    sol = sol + (asph - sol) * route[..., None]
    couche(img, np.clip(y - y0 + 0.5, 0, 1), sol)
    add(img, rgb("#ff8a3a"), 0.30 * np.exp(-np.abs(y - y0) / 14.0))
    # palmiers en silhouette de chaque côté
    pm = np.zeros((H, W), F32)
    for dp, sg in ((60, -1), (60, 1), (150, -1), (150, 1), (330, -1), (330, 1), (700, -1), (700, 1)):
        bx = cx + sg * (1.15 * (dp + 1) * 1.12 + 40 + 0.35 * dp)
        hh = min(dp * 1.6, 1300)
        sg_, bx_, hh_, yb_ = sg, bx, hh, y0 + dp
        r2 = np.random.default_rng(int(dp) * 7 + (sg > 0))
        pm = np.maximum(pm, pil_masque(lambda dr, k, a=bx_, b=yb_, c=hh_, s=sg_, rr=r2:
                                       _palmier(dr, k, a, b, c, -0.18 * s, rr)))
    add(img, rgb("#ff2f9a"), 0.20 * blur(pm, 22))
    couche(img, pm, rgb("#080218"))
    vignette(img, 0.30, 2.2)
    return sauver2(img, "synthwave-route", seed=223)


def _skyline(rng, y0, hmin, hmax, wmin, wmax):
    st = [0]
    while st[-1] < W:
        st.append(st[-1] + int(rng.uniform(wmin, wmax)))
    st = np.array(st)
    n = len(st) - 1
    clus = fbm1d(W, rng, 4, 4, 0.5) * 0.5 + 0.5
    ident = np.searchsorted(st, np.arange(W), side="right") - 1
    hts = rng.uniform(hmin, hmax, n)
    prof = y0 - hts[ident] * (0.55 + 0.9 * clus)
    return ident, st[ident], prof


def synthwave_ville():
    rng = np.random.default_rng(224)
    y, x = grille()
    y0 = 0.64 * H
    img = vgrad([(0, "#05031a"), (0.30, "#1a0a52"), (0.50, "#6a1b9a"), (0.62, "#ff4fa6"), (0.64, "#ffb070"),
                 (1, "#ffb070")], H, W)
    etoiles2(img, rng, 1400, int(y0 * 0.7), masque=_lisse(y0 * 0.7, 0, y))
    mx, my, mr = 0.68 * W, 0.30 * H, 360.0
    add(img, rgb("#ff4fb0"), 0.35 * halo(y, x, mx, my, 650))
    d = np.hypot(x - mx, y - my)
    tt = (y - (my - mr)) / (2 * mr)
    mc = rgb("#ffe6c0") + (rgb("#ff6cb0") - rgb("#ffe6c0")) * _lisse(0.1, 1.0, tt)[..., None]
    mc = mc * (0.9 + 0.2 * resize(fbm(480, 300, rng, 4, 4), W, H))[..., None]
    couche(img, np.clip(mr - d + 0.5, 0, 1), mc)
    couches = ((90, 330, 120, 260, "#4a1a82", 0.10), (80, 300, 100, 240, "#2a0d5c", 0.22), (50, 230, 140, 300, "#0d0526", 0.5))
    for n, (hmin, hmax, wmin, wmax, col, lum) in enumerate(couches):
        ident, st0, prof = _skyline(rng, y0, hmin, hmax, wmin, wmax)
        mask = sous_profil(y, prof) * np.clip(y0 - y + 0.5, 0, 1)
        add(img, rgb("#ff7ac0"), 0.0)
        couche(img, mask, rgb(col))
        xl = np.floor((x - st0[None, :]) / 18.0)
        yl = np.floor(y / 26.0)
        fx = ((x - st0[None, :]) / 18.0) % 1.0
        fy = (y / 26.0) % 1.0
        lit = (_hash(ident[None, :] * 131 + xl, yl, n) > 0.72 - 0.05 * n) * (fx < 0.6) * (fy < 0.5)
        tc = _hash(ident[None, :] * 7 + xl, yl, n + 50)
        wc = rgb("#ffd28a") * (tc > 0.3)[..., None] + rgb("#6fe3ff") * (tc <= 0.3)[..., None]
        add(img, wc, (mask * lit * lum * 0.8)[..., None] if False else mask * lit * lum * 0.8)
        if n == 2:
            ligne = np.clip(1 - np.abs(y - prof[None, :]) / 3.0, 0, 1)
            cn = _hash(ident, ident, 99)
            lc = rgb("#ff3d9a") * (cn > 0.5)[None, :, None] + rgb("#28e6ff") * (cn <= 0.5)[None, :, None]
            img += lc * (ligne * (_hash(ident, ident, 98) > 0.45)[None, :])[..., None] * 1.1
            add(img, rgb("#ff3d9a"), 0.0)
    add(img, rgb("#ff6aa8"), 0.22 * np.exp(-np.abs(y - y0) / 40.0) * (y < y0))
    # eau : reflet du ciel et de la ville, ondulé
    yy = np.clip(2 * y0 - y, 0, H - 1).astype(np.int64)
    ond = (np.sin(y * 0.03 + 8 * resize(fbm(480, 300, rng, 3, 3), W, H)) * ((y - y0) * 0.006 + 1.5)).astype(np.int64)
    xx = np.clip(x.astype(np.int64) + ond, 0, W - 1)
    R = np.take_along_axis(img[yy[:, 0]], np.broadcast_to(xx[..., None], (H, W, 3)), axis=1)
    for k in range(3):
        R[..., k] = blur(np.ascontiguousarray(R[..., k]), 7)
    dep = _lisse(y0, H, y)[..., None]
    eau = (R * 0.62 * (1 - 0.55 * dep)) + rgb("#12063a") * (0.25 + 0.5 * dep)
    colonne = np.exp(-((x - mx) / 260.0) ** 2) * (0.5 + 0.5 * np.sin(y * 0.11 + 9 * resize(fbm(480, 300, rng, 3, 3), W, H)))
    eau = eau + rgb("#ff7ac0") * (0.35 * colonne * np.exp(-(y - y0) / 900.0))[..., None]
    couche(img, np.clip(y - y0 + 0.5, 0, 1), eau)
    vignette(img, 0.30, 2.2)
    return sauver2(img, "synthwave-ville", seed=224)


# --------------------------------------------------------------------------
# retro : oscilloscope vert, trame de points ambre
# --------------------------------------------------------------------------
def retro_oscillo():
    rng = np.random.default_rng(225)
    y, x = grille()
    u, v = (x - W / 2) / (W / 2), (y - H / 2) / (H / 2)
    r2 = u * u + v * v
    img = rgb("#041208") + (rgb("#0e3a1c") - rgb("#041208")) * np.exp(-r2 * 1.6)[..., None]
    x0, y0, gw, gh = 0.07 * W, 0.10 * H, 0.86 * W, 0.80 * H
    sx, sy = gw / 12, gh / 8
    yc = y0 + gh * 0.56
    dx = np.abs(((x - x0) / sx + 0.5) % 1 - 0.5) * sx
    dy = np.abs(((y - y0) / sy + 0.5) % 1 - 0.5) * sy
    dedans = (x > x0 - 2) & (x < x0 + gw + 2) & (y > y0 - 2) & (y < y0 + gh + 2)
    grl = np.maximum(np.exp(-dx ** 2 / 3.0), np.exp(-dy ** 2 / 3.0)) * dedans
    xm = np.abs(((x - x0) / (sx / 5) + 0.5) % 1 - 0.5) * (sx / 5)
    ym = np.abs(((y - y0) / (sy / 5) + 0.5) % 1 - 0.5) * (sy / 5)
    ticks = (np.exp(-xm ** 2 / 2.0) * (np.abs(y - (y0 + gh * 0.5)) < 14)
             + np.exp(-ym ** 2 / 2.0) * (np.abs(x - (x0 + gw * 0.5)) < 14)) * dedans
    add(img, rgb("#2fd25a"), 0.20 * grl + 0.45 * np.clip(ticks, 0, 1))
    xs = np.arange(W, dtype=F32)
    E = np.zeros((H, W, 3), F32)
    for amp, per, ph, col, s, k in ((1.55, 4.6, 0.4, "#9dffb0", 3.4, 1.0), (0.8, 1.9, 2.0, "#4fe27a", 2.6, 0.7)):
        t = (xs - x0) / sx
        ya = yc - sy * amp * (np.sin(2 * np.pi * t / per + ph) + 0.25 * np.sin(6 * np.pi * t / per + 1.0))
        ya = ya + 6 * fbm1d(W, rng, 6, 3)
        sl = np.gradient(ya)
        d2 = (y - ya[None, :]) ** 2 / (1 + sl ** 2)[None, :]
        I = np.exp(-d2 / (2 * s * s)) * (xs > x0 - 6) * (xs < x0 + gw + 6)
        E += (I * k)[..., None] * rgb(col)
    img += E
    _bloom(img, E * 0.5, ((6, 0.8), (26, 0.7), (90, 0.5)))
    img *= (0.86 + 0.14 * np.cos(y * 2 * np.pi / 6))[..., None]
    img *= (0.93 + 0.07 * np.sin(y / 500.0 + 1.0))[..., None]
    img += (resize(fbm(480, 300, rng, 4, 3), W, H) - 0.5)[..., None] * 0.03 * rgb("#2fd25a")
    img *= (1 - np.clip(((np.abs(u) ** 6 + np.abs(v) ** 6) - 0.55) * 1.6, 0, 1))[..., None]
    vignette(img, 0.35, 2.0)
    return sauver2(img, "retro-oscillo", seed=225)


def retro_phosphore():
    rng = np.random.default_rng(226)
    c = 16
    ny, nx = H // c, W // c
    yy, xx = grille(ny, nx)
    u, v = xx / nx, yy / ny
    r = np.sqrt(((u - 0.5) * 1.6) ** 2 + (v - 1.25) ** 2)
    f = 0.5 + 0.5 * np.sin(r * 34 - 7 * fbm(nx, ny, rng, 3, 3))
    b = np.clip(f ** 2.2 * _lisse(0.10, 0.60, v) * (0.55 + 0.9 * fbm(nx, ny, rng, 4, 3)), 0, 1)
    b = np.clip(b + 0.9 * np.exp(-(((u - 0.5) * 1.5) ** 2 + (v - 0.86) ** 2) / 0.02), 0, 1)
    B = b.repeat(c, 0).repeat(c, 1)
    y, x = grille()
    d = np.hypot((x % c) - (c - 1) / 2, (y % c) - (c - 1) / 2)
    rad = 2.0 + 5.6 * B
    dot = blur(np.clip(rad - d + 0.5, 0, 1) * (0.14 + 0.86 * B), 1.6)
    t = (B ** 2)[..., None]
    col = rgb("#ff8a10") * (1 - t) + rgb("#ffe6a8") * t
    E = dot[..., None] * col
    img = np.zeros((H, W, 3), F32) + rgb("#0b0500")
    img += E
    _bloom(img, E, ((8, 0.7), (30, 0.55), (100, 0.4)))
    vignette(img, 0.4, 2.0)
    return sauver2(img, "retro-phosphore", bruit=0.0, seed=226)


# --------------------------------------------------------------------------
# catppuccin : nuages mocha, grande lune
# --------------------------------------------------------------------------
def catppuccin_nuages():
    rng = np.random.default_rng(227)
    w, h = 960, 600
    y, x = grille(h, w)
    v = y / h
    img = vgrad([(0, "#0c0c14"), (0.45, "#1e1e2e"), (0.70, "#3a3560"), (0.88, "#9a6a9c"), (1, "#f2a98a")], h, w)
    for i, (v0, fade, col_lo, haut) in enumerate(((0.38, 0.30, "#cba6f7", 0.7), (0.52, 0.28, "#f5c2e7", 0.85),
                                                 (0.68, 0.30, "#fab387", 1.0))):
        n = resize(fbm(200, 150, rng, 3 + i, 4), w, h)
        n2 = resize(fbm(120, 100, rng, 2, 3), w, h)
        d = _lisse(0.46, 0.66, n + 0.25 * (n2 - 0.5) - 0.9 * np.abs(v - v0 - 0.12) + 0.2)
        d = d * _lisse(v0 - 0.05, v0 + 0.1, v)
        d = blur(d, 1.2)
        dd = d - np.roll(d, 8, axis=0)
        bas = np.clip(-dd * 5, 0, 1)
        hautc = np.clip(dd * 3, 0, 1)
        corps = rgb("#14141f") + (rgb("#2b2840") - rgb("#14141f")) * _lisse(0.0, 1.0, v)[..., None] * haut
        c = corps + rgb(col_lo) * (bas * 0.9 * haut)[..., None] + rgb("#b4befe") * (hautc * 0.25)[..., None]
        couche(img, d * 0.97, c)
    img = resize3(img, W, H)
    yb, xb = grille()
    etoiles2(img, rng, 700, int(H * 0.5), "#cdd6f4", 0.8, _lisse(0.55, 0.1, yb / H))
    vignette(img, 0.32, 2.2)
    return sauver2(img, "catppuccin-nuages", seed=227)


def catppuccin_lune():
    rng = np.random.default_rng(228)
    y, x = grille()
    img = vgrad([(0, "#0b0b12"), (0.5, "#181825"), (0.85, "#313244"), (1, "#45475a")], H, W)
    cx, cy, R = 0.64 * W, 0.40 * H, 400.0
    img += rgb("#b4befe") * (0.22 * halo(y, x, cx, cy, 700) + 0.30 * halo(y, x, cx, cy, 260))[..., None] * 0.55
    etoiles2(img, rng, 1500, int(H * 0.7), "#cdd6f4", 0.8)
    nx_, ny_ = (x - cx) / R, (y - cy) / R
    rr = nx_ ** 2 + ny_ ** 2
    nz = np.sqrt(np.clip(1 - rr, 0, 1))
    lum = np.clip(nx_ * -0.45 + ny_ * -0.35 + nz * 0.82, 0, 1)
    mar = resize(fbm(240, 150, rng, 3, 4), W, H)
    mar2 = resize(fbm(960, 600, rng, 8, 4), W, H)
    sol = rgb("#cdd6f4") * (1 - _lisse(0.45, 0.58, mar)[..., None] * 0.35) + rgb("#9399b2") * (_lisse(0.5, 0.65, mar)[..., None] * 0.5)
    sol = sol * (0.9 + 0.2 * (mar2 - 0.5))[..., None]
    sphere = (rgb("#313244") + (sol - rgb("#313244")) * (lum ** 0.8)[..., None])
    sphere += rgb("#b4befe") * (0.15 * (1 - nz) ** 2)[..., None]
    couche(img, np.clip((R - np.sqrt(rr) * R) + 0.5, 0, 1), sphere)
    prof_def = ((0.80, 120, "#1b1b2b", 0.0), (0.86, 160, "#13131d", 0.0), (0.93, 120, "#0c0c13", 0.0))
    for hy, amp, col, _ in prof_def:
        prof = H * hy + amp * (fbm1d(W, rng, 3, 4) - 0.5 * 0)
        m = sous_profil(y, prof)
        brume = np.exp(-np.clip(y - prof[None, :], 0, None) / 90.0)
        base = np.asarray(rgb(col), F32) + rgb("#585b70") * (0.55 * brume)[..., None] * (hy < 0.9)
        couche(img, m, base)
    vignette(img, 0.35, 2.2)
    return sauver2(img, "catppuccin-lune", seed=228)


# --------------------------------------------------------------------------
# dracula : château sous la lune, chauves-souris
# --------------------------------------------------------------------------
def _ciel_dracula(y, x, cx, cy, R, rng):
    img = vgrad([(0, "#14151c"), (0.4, "#282a36"), (0.75, "#44475a"), (1, "#7a5aa6")], H, W)
    img += rgb("#bd93f9") * (0.30 * halo(y, x, cx, cy, 650) + 0.35 * halo(y, x, cx, cy, 220))[..., None] * 0.7
    etoiles2(img, rng, 900, int(H * 0.55), "#f8f8f2", 0.7)
    nx_, ny_ = (x - cx) / R, (y - cy) / R
    rr = np.sqrt(nx_ ** 2 + ny_ ** 2)
    mar = resize(fbm(200, 125, rng, 3, 4), W, H)
    disque = rgb("#f2e4ff") * (1 - 0.18 * _lisse(0.45, 0.65, mar)[..., None]) * (1 - 0.15 * rr ** 3)[..., None]
    couche(img, np.clip(R - rr * R + 0.5, 0, 1), disque)
    return img


def dracula_chateau():
    rng = np.random.default_rng(229)
    y, x = grille()
    img = _ciel_dracula(y, x, 0.32 * W, 0.32 * H, 300.0, rng)
    base_y = H * 0.80
    x_deb = 0.52 * W
    crag = base_y - 520 * _lisse(0.0, 1.0, np.clip(1 - np.abs((np.arange(W) - 0.74 * W) / (0.30 * W)), 0, 1)) \
        - 60 * fbm1d(W, rng, 6, 4) * (np.arange(W) > x_deb)
    tours = [(0.60, 70, 330), (0.66, 110, 470), (0.725, 60, 380), (0.78, 150, 330), (0.85, 80, 540), (0.915, 90, 300)]

    def dessin(d, k):
        for fx, tw, th in tours:
            xl = fx * W
            ytop = base_y - 380 - th
            d.rectangle([(xl - tw / 2) * k, ytop * k, (xl + tw / 2) * k, (base_y + 20) * k], fill=255)
            d.polygon([((xl - tw / 2 - 14) * k, ytop * k), (xl * k, (ytop - tw * 1.9) * k), ((xl + tw / 2 + 14) * k, ytop * k)], fill=255)
        d.rectangle([(0.60 * W) * k, (base_y - 520) * k, (0.915 * W) * k, (base_y + 20) * k], fill=255)
        for i in range(14):
            d.rectangle([(0.60 * W + i * 0.0225 * W) * k, (base_y - 545) * k, (0.60 * W + i * 0.0225 * W + 0.012 * W) * k, (base_y - 520) * k], fill=255)
    chat = pil_masque(dessin)
    fen = np.zeros((H, W), F32)
    for fx, tw, th in tours:
        for j in range(3):
            if rng.random() < 0.75:
                wx, wy = int(fx * W + rng.integers(-tw // 4, tw // 4 + 1)), int(base_y - 380 - th + 80 + j * 90 + rng.integers(0, 40))
                fen[wy:wy + 36, wx - 7:wx + 8] = 1.0
    for i in range(9):
        wx, wy = int(0.62 * W + i * 0.032 * W), int(base_y - 470 + (i % 2) * 70)
        fen[wy:wy + 26, wx:wx + 12] = 0.8
    fen = fen * (chat > 0.5)
    couche(img, sous_profil(y, crag), "#0d0e14")
    couche(img, chat, "#0d0e14")
    E = fen[..., None] * rgb("#f1fa8c")
    img += E
    _bloom(img, E * 0.6, ((4, 0.8), (20, 0.6)))
    for k, (hy, col, a) in enumerate(((0.80, "#6272a4", 0.28), (0.88, "#8c82c4", 0.22))):
        n = resize(fbm(150, 80, rng, 3, 4), W, H)
        m = np.clip(n * 1.6 - 0.35, 0, 1) * np.exp(-((y - H * hy) / 170.0) ** 2) * a
        img += (rgb(col) - img) * m[..., None]
    av = H * 0.90 + 90 * (fbm1d(W, rng, 4, 4) - 0.5)
    couche(img, sous_profil(y, av), "#08090d")
    vignette(img, 0.35, 2.2)
    return sauver2(img, "dracula-chateau", seed=229)


def dracula_chauves():
    rng = np.random.default_rng(230)
    y, x = grille()
    cx, cy, R = 0.66 * W, 0.56 * H, 420.0
    img = _ciel_dracula(y, x, cx, cy, R, rng)
    img += rgb("#ff79c6") * (0.30 * halo(y, x, cx, cy, 420))[..., None] * 0.5
    bats = []
    for i in range(90):
        ang, rad = rng.random() * 2 * np.pi, abs(rng.normal(0, 900))
        bx, by = cx + np.cos(ang) * rad * 1.3 - 400, cy + np.sin(ang) * rad * 0.7
        if by < 0.2 * H or by > 0.86 * H or bx < 40 or bx > W - 40:
            continue
        bats.append((bx, by, 18 + 100 * rng.random() ** 2.2, rng.uniform(-0.2, 0.9), rng.uniform(-0.3, 0.3)))
    pts = [(0, 0), (-0.55, -0.5), (-1.1, -0.62), (-1.0, -0.2), (-1.25, 0.0), (-0.9, 0.1), (-0.9, 0.35), (-0.5, 0.2), (-0.25, 0.3)]

    def dessin(d, k):
        for bx, by, s, fl, tilt in bats:
            for sg in (-1, 1):
                poly = [((bx + sg * px * s) * k, (by + (py * (1 - fl) + (0.1 if i in (0, 8) else 0) + px * tilt * 0.3) * s) * k)
                        for i, (px, py) in enumerate(pts)]
                d.polygon(poly, fill=255)
            d.ellipse([(bx - 0.17 * s) * k, (by - 0.22 * s) * k, (bx + 0.17 * s) * k, (by + 0.32 * s) * k], fill=255)
            d.polygon([((bx - 0.12 * s) * k, (by - 0.18 * s) * k), ((bx - 0.1 * s) * k, (by - 0.42 * s) * k), ((bx - 0.02 * s) * k, (by - 0.2 * s) * k)], fill=255)
            d.polygon([((bx + 0.12 * s) * k, (by - 0.18 * s) * k), ((bx + 0.1 * s) * k, (by - 0.42 * s) * k), ((bx + 0.02 * s) * k, (by - 0.2 * s) * k)], fill=255)
    couche(img, pil_masque(dessin), "#0b0b10")
    for hy, col, a in ((0.82, "#6272a4", 0.30), (0.90, "#8c82c4", 0.22)):
        n = resize(fbm(150, 80, rng, 3, 4), W, H)
        m = np.clip(n * 1.6 - 0.35, 0, 1) * np.exp(-((y - H * hy) / 170.0) ** 2) * a
        img += (rgb(col) - img) * m[..., None]
    couche(img, sous_profil(y, H * 0.92 + 80 * (fbm1d(W, rng, 4, 4) - 0.5)), "#08090d")
    vignette(img, 0.35, 2.2)
    return sauver2(img, "dracula-chauves", seed=230)


# --------------------------------------------------------------------------
# nord : rideaux d'aurore sur un lac, banquise
# --------------------------------------------------------------------------
def nord_aurore():
    rng = np.random.default_rng(231)
    y, x = grille()
    img = vgrad([(0, "#1d2129"), (0.5, "#2e3440"), (0.75, "#3b4252")], H, W)
    etoiles2(img, rng, 1400, int(H * 0.55), "#eceff4", 0.8)
    xs = np.arange(W, dtype=F32)
    ray0 = fbm1d(W, rng, 90, 3)
    for i, (hb, col_b, col_h, ep) in enumerate(((0.36, "#a3be8c", "#88c0d0", 420), (0.46, "#8fbcbb", "#b48ead", 360),
                                              (0.55, "#a3be8c", "#81a1c1", 300))):
        yb = H * hb + 230 * (fbm1d(W, rng, 2 + i, 3)) + 90 * fbm1d(W, rng, 6, 3)
        dd = (yb[None, :] - y)
        mont = np.where(dd > 0, np.exp(-np.clip(dd, 0, None) / ep), np.exp(np.clip(dd, None, 0) / 30.0))
        ray = np.clip(0.55 + 0.7 * (ray0 if i % 2 == 0 else np.roll(ray0, 400)) * 1.0, 0.1, 1.3)
        ray = np.clip(ray + 0.2 * fbm1d(W, rng, 30, 2), 0.05, 1.5)
        I = mont * ray[None, :] ** 1.5 * _lisse(0.20 * H, 0.38 * H, y) * 0.8
        t = np.clip(dd / (ep * 1.8), 0, 1)[..., None]
        col = rgb(col_b) * (1 - t) + rgb(col_h) * t
        img += col * I[..., None] * 0.95
    prof = H * 0.70 - 330 * np.abs(fbm1d(W, rng, 4, 5)) - 70 * fbm1d(W, rng, 14, 3)
    ciel_avant = img.copy()
    couche(img, sous_profil(y, prof), "#15181f")
    nei = np.exp(-np.clip(y - prof[None, :], 0, None) / 28.0) * (y > prof[None, :]) * 0.35
    img += rgb("#8fbcbb") * (nei * (ciel_avant[..., 1] > 0.3))[..., None] * 0.0
    y0 = H * 0.78
    haut = np.clip((2 * y0 - y).astype(int), 0, H - 1)
    R = img[haut[:, 0]] if False else img[np.clip((2 * y0 - np.arange(H)).astype(int), 0, H - 1)]
    for k in range(3):
        R[..., k] = blur(np.ascontiguousarray(R[..., k]), 7)
    ond = 1 + 0.15 * np.sin(y * 0.09 + 5 * resize(fbm(480, 300, rng, 3, 3), W, H))
    eau = (rgb("#1b1f27") * 0.5 + R * 0.55 * ond[..., None])
    couche(img, np.clip(y - y0 + 0.5, 0, 1), eau)
    vignette(img, 0.32, 2.2)
    return sauver2(img, "nord-aurore", seed=231)


def nord_banquise():
    rng = np.random.default_rng(232)
    w, h = 1920, 1200
    yy, xx = grille(h, w)
    xw = xx + 55 * (fbm(w, h, rng, 4, 3) - 0.5)
    yw = yy + 55 * (fbm(w, h, rng, 4, 3) - 0.5)
    cs = 150
    ncx, ncy = w // cs + 3, h // cs + 3
    sx = (np.arange(ncx)[None, :] - 1 + 0.15 + 0.7 * rng.random((ncy, ncx))) * cs
    sy = (np.arange(ncy)[:, None] - 1 + 0.15 + 0.7 * rng.random((ncy, ncx))) * cs
    ci = np.clip((xw // cs).astype(int), 0, ncx - 3)
    cj = np.clip((yw // cs).astype(int), 0, ncy - 3)
    d1 = np.full((h, w), 1e9, F32)
    d2 = np.full((h, w), 1e9, F32)
    ident = np.zeros((h, w), np.int64)
    for dj in (0, 1, 2):
        for di in (0, 1, 2):
            jj, ii = cj + dj, ci + di
            d = np.hypot(xw - sx[jj, ii], yw - sy[jj, ii])
            neuf = d < d1
            d2 = np.where(neuf, d1, np.minimum(d2, d))
            ident = np.where(neuf, jj * ncx + ii, ident)
            d1 = np.where(neuf, d, d1)
    e = d2 - d1
    alea = rng.random(ncy * ncx).astype(F32)[ident]
    v = yy / h
    glace = rgb("#a9b8cc") * (1 - alea[..., None]) + rgb("#d8e2ef") * alea[..., None]
    glace = glace * (0.72 + 0.4 * alea)[..., None]
    tex = fbm(w, h, rng, 10, 4)
    fis = np.abs(fbm(w, h, rng, 6, 3) - 0.5)
    glace = glace * (0.88 + 0.24 * tex)[..., None]
    glace = glace * (1 - 0.35 * np.clip(1 - fis * 40, 0, 1) * 0.5)[..., None]
    bord = np.clip(1 - e / 26.0, 0, 1)
    glace = glace + rgb("#eceff4") * (0.28 * np.exp(-((e - 7) / 5.0) ** 2))[..., None]
    glace = glace * (1 - 0.25 * bord ** 2)[..., None]
    eau = rgb("#1f3350") + (rgb("#2f4f78") - rgb("#1f3350")) * (fbm(w, h, rng, 3, 3))[..., None]
    img = glace + (eau - glace) * (1 - _lisse(3.0, 8.0, e))[..., None]
    img *= (0.45 + 0.55 * _lisse(0.0, 0.5, v))[..., None]
    img = resize3(img, W, H)
    vignette(img, 0.30, 2.2)
    return sauver2(img, "nord-banquise", seed=232)


# --- fin des scènes ---

IMAGES = {
    "apple-liquide": apple_liquide, "apple-collines": apple_collines,
    "oled-arc": oled_arc, "oled-relief": oled_relief,
    "tokyo-tours": tokyo_tours, "tokyo-ruelle": tokyo_ruelle,
    "synthwave-route": synthwave_route, "synthwave-ville": synthwave_ville,
    "retro-oscillo": retro_oscillo, "retro-phosphore": retro_phosphore,
    "catppuccin-nuages": catppuccin_nuages, "catppuccin-lune": catppuccin_lune,
    "dracula-chateau": dracula_chateau, "dracula-chauves": dracula_chauves,
    "nord-aurore": nord_aurore, "nord-banquise": nord_banquise,
}

if __name__ == "__main__":
    depot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if len(sys.argv) < 2 or os.path.commonpath([depot, os.path.abspath(sys.argv[1])]) == depot:
        sys.exit("usage : generer_fonds_2.py DOSSIER [nom...] (DOSSIER hors du dépôt)")
    ICI = os.path.abspath(sys.argv[1])
    noms = sys.argv[2:] or list(IMAGES)
    for nom in noms:
        if nom not in IMAGES:
            sys.exit("inconnu : %s (choix : %s)" % (nom, ", ".join(IMAGES)))
        t0 = time.time()
        q, taille = IMAGES[nom]()
        print("%-22s %.1f s  q%d  %d Ko" % (nom, time.time() - t0, q, taille // 1024), flush=True)
