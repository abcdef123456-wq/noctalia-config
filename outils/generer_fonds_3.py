#!/usr/bin/env python3
"""Fonds d'écran générés, série 3 : seize images pour huit thèmes.

Sans ressource externe : numpy + Pillow, graines fixes, rendu reproductible.
Les utilitaires viennent de generer_fonds.py (non modifié).

    usage : generer_fonds_3.py DOSSIER [nom...]

DOSSIER doit être hors du dépôt ; chaque image y arrive en DOSSIER/jpg/<nom>.jpg
(3840x2400, JPEG 4:2:0 réglé pour rester sous 900 Ko).
"""
import io
import math
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generer_fonds import (F32, H, W, add, blur, fbm, fbm1d, hexc,  # noqa: E402,F401
                           interp_stops, ligne_aa, mix, vgrad)

ICI = ""        # le dossier de sortie, donné en premier argument
SS = 2          # suréchantillonnage des dessins
POIDS_MAX = 880_000


# --------------------------------------------------------------------------
# Outils communs
# --------------------------------------------------------------------------
class Toile:
    """Dessin suréchantillonné x2 (antialiasing) : masque 'L'."""

    def __init__(self):
        self.im = Image.new("L", (W * SS, H * SS), 0)
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def _p(pts):
        return [(x * SS, y * SS) for x, y in pts]

    def poly(self, pts, v=255):
        self.d.polygon(self._p(pts), fill=int(v))

    def ell(self, cx, cy, rx, ry=None, v=255):
        ry = rx if ry is None else ry
        self.d.ellipse([(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS], fill=int(v))

    def rect(self, x0, y0, x1, y1, v=255):
        self.d.rectangle([x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1], fill=int(v))

    def ligne(self, pts, ep, v=255):
        self.d.line(self._p(pts), fill=int(v), width=max(1, int(round(ep * SS))))

    def a(self):
        return np.asarray(self.im.reduce(SS), F32) / 255


def lisse(a, b, t):
    t = np.clip((t - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def sauver3(img, nom, grain=0.7, seed=0):
    """Grain léger puis JPEG 4:2:0 progressif, qualité réglée pour rester léger."""
    rng = np.random.default_rng(seed + 4242)
    g = rng.normal(0, grain, img.shape[:2]).astype(F32)[..., None]
    out = np.clip(np.clip(img, 0, 1) * 255 + g + 0.5, 0, 255).astype(np.uint8)
    im = Image.fromarray(out, "RGB")
    bas, haut, bon = 55, 93, None
    while bas <= haut:
        q = (bas + haut) // 2
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, subsampling=2, optimize=True, progressive=True)
        if buf.tell() <= POIDS_MAX:
            bon, bas = buf.getvalue(), q + 1
        else:
            haut = q - 1
    if bon is None:
        sys.exit("%s : impossible de passer sous le poids max" % nom)
    os.makedirs(os.path.join(ICI, "jpg"), exist_ok=True)
    with open(os.path.join(ICI, "jpg", nom + ".jpg"), "wb") as f:
        f.write(bon)


def points_hex(pas):
    """Réseau hexagonal de points : (xs, ys) en tableaux 1D."""
    dy = pas * math.sqrt(3) / 2
    xs, ys = [], []
    j, y = 0, 0.0
    n = int(W / pas) + 1
    while y < H:
        xs.append((pas / 2 if j % 2 else 0) + pas * np.arange(n))
        ys.append(np.full(n, y))
        y += dy
        j += 1
    return np.concatenate(xs), np.concatenate(ys)


# --------------------------------------------------------------------------
# 1. matrice : noir, blanc, rouge — tout en points
# --------------------------------------------------------------------------
def matrice_relief():
    rng = np.random.default_rng(301)
    t = Toile()
    n_rang = 78
    bruit = fbm(700, n_rang, rng, base=5, octaves=5, gain=0.55)
    for r in range(n_rang):
        k = r / (n_rang - 1)
        yb = 980 + 1450 * k ** 1.7
        amp = 70 + 520 * k ** 1.15
        pas = 9 + 30 * k
        ray = 1.1 + 3.6 * k
        xs = np.arange(-40, W + 40, pas)
        col = np.clip((xs + 40) / (W + 80) * 699, 0, 699).astype(int)
        cote = 0.35 + 0.65 * np.clip(np.abs(xs - W / 2) / (W / 2), 0, 1) ** 1.2
        ys = yb - amp * (bruit[r, col] - 0.25) * cote
        # la rangée efface ce qui est derrière elle
        t.poly([(xs[0], ys[0])] + list(zip(xs, ys)) + [(xs[-1], H + 10), (xs[0], H + 10)], 0)
        v = int(95 + 160 * k ** 0.6)
        for x, y in zip(xs, ys):
            t.ell(x, y, ray, v=v)
    m = t.a()
    ciel = Toile()
    for _ in range(420):
        x, y = rng.random() * W, rng.random() * 900
        ciel.ell(x, y, 1.0 + rng.random() * 1.3, v=int(70 + 120 * rng.random()))
    haut = np.clip(1 - np.arange(H, dtype=F32) / 1050, 0, 1)[:, None]
    cx = lisse(0.15, 0.45, np.abs(np.arange(W, dtype=F32) - W / 2) / (W / 2))[None, :]
    rx, ry = 3050, 560
    rouge = Toile()
    rouge.ell(rx, ry, 17)
    for i in range(48):
        a = i / 48 * 2 * math.pi
        rouge.ell(rx + 62 * math.cos(a), ry + 62 * math.sin(a), 3.2)
    for i in range(90):
        a = i / 90 * 2 * math.pi
        rouge.ell(rx + 108 * math.cos(a), ry + 108 * math.sin(a), 2.0, v=170)
    img = np.zeros((H, W, 3), F32)
    mix(img, hexc("#ffffff"), np.maximum(m, ciel.a() * haut * (0.25 + 0.75 * cx)))
    mix(img, hexc("#d71920"), rouge.a())
    sauver3(img, "matrice-collines", grain=0.0)


def matrice_cercle():
    rng = np.random.default_rng(302)
    xs, ys = points_hex(18)
    cx, cy, R = 2330.0, 1530.0, 830.0
    L = np.array([-0.55, -0.6, 0.58])
    L /= np.linalg.norm(L)
    blanc, rouge = Toile(), Toile()
    dx, dy = xs - cx, ys - cy
    d2 = dx * dx + dy * dy
    dentro = d2 < R * R
    nz = np.sqrt(np.maximum(R * R - d2, 0)) / R
    lamb = np.clip((dx / R) * L[0] + (dy / R) * L[1] + nz * L[2], 0, 1)
    ray = 0.2 + 7.6 * lamb ** 0.85
    for x, y, r in zip(xs[dentro], ys[dentro], ray[dentro]):
        if r > 0.7:
            blanc.ell(x, y, r)
    choix = (~dentro) & (rng.random(len(xs)) < 0.035)
    for x, y in zip(xs[choix], ys[choix]):
        blanc.ell(x, y, 0.9 + rng.random() * 1.8, v=90 + 130 * rng.random())
    # anneau incliné : la moitié arrière passe derrière la planète
    inc = math.radians(-14)
    for k in range(7):
        rr = 1.22 + 0.075 * k
        n = int(2 * math.pi * rr * R / 15)
        for i in range(n):
            a = i / n * 2 * math.pi
            ex, ey = rr * R * math.cos(a), rr * R * 0.17 * math.sin(a)
            x = cx + ex * math.cos(inc) - ey * math.sin(inc)
            y = cy + ex * math.sin(inc) + ey * math.cos(inc)
            devant = math.sin(a) > 0
            if not devant and (x - cx) ** 2 + (y - cy) ** 2 < R * R:
                continue
            blanc.ell(x, y, 2.1 if devant else 1.6, v=240 if devant else 150)
    # petite lune rouge, en points aussi
    mx, my, mr_ = 760.0, 1650.0, 190.0
    ddx, ddy = xs - mx, ys - my
    dd = ddx * ddx + ddy * ddy
    ok = dd < mr_ * mr_
    nzm = np.sqrt(np.maximum(mr_ * mr_ - dd, 0)) / mr_
    lm = np.clip((ddx / mr_) * L[0] + (ddy / mr_) * L[1] + nzm * L[2], 0, 1)
    for x, y, v in zip(xs[ok], ys[ok], lm[ok]):
        r = 0.2 + 6.4 * v ** 0.85
        if r > 0.7:
            rouge.ell(x, y, r)
    img = np.zeros((H, W, 3), F32)
    mix(img, hexc("#ffffff"), blanc.a())
    mix(img, hexc("#d71920"), rouge.a())
    sauver3(img, "matrice-planete", grain=0.0)


def hsh(a, b=0, seed=0):
    """Hasard déterministe par cellule, dans [0,1)."""
    n = (np.asarray(a, np.int64) * 374761393 + np.asarray(b, np.int64) * 668265263
         + seed * 144665) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n = n ^ (n >> 16)
    return ((n & 0xFFFF) / 65536.0).astype(F32)


def soft1d(x, demi, e):
    """Créneau doux de demi-largeur `demi`, bords de largeur `e`."""
    return np.clip((demi - np.abs(x)) / e + 0.5, 0, 1).astype(F32)


def vers_canaux(a, fn):
    return np.stack([fn(a[..., c]) for c in range(3)], -1)


# --------------------------------------------------------------------------
# 2. cyberjaune
# --------------------------------------------------------------------------
def cyberjaune_ville():
    rng = np.random.default_rng(311)
    VX, VY = 1920.0, -1500.0
    yy, xx = np.mgrid[0:H, 0:W].astype(F32)
    dx, dy = xx - VX, yy - VY
    r = np.hypot(dx, dy)
    ang = np.degrees(np.arctan2(dy, dx))
    del dx, dy
    # bandes d'immeubles : droite, trou central (rue + ciel), gauche
    bords_d = [74.0]
    while bords_d[-1] > 20:
        bords_d.append(bords_d[-1] - rng.uniform(4, 8))
    bords_d = [0.0] + bords_d[::-1][:]
    bords_d[0] = -5.0
    bords_g = [106.0]
    while bords_g[-1] < 160:
        bords_g.append(bords_g[-1] + rng.uniform(4, 8))
    bandes = []
    for a, b in zip(bords_d[:-1], bords_d[1:]):
        bandes.append((a, b, 74 - b))
    bandes.append((74.0, 106.0, None))
    for a, b in zip(bords_g[:-1], bords_g[1:]):
        bandes.append((a, b, a - 106))
    nb = len(bandes)
    lo = np.array([b[0] for b in bandes], F32)
    trou = np.array([b[2] is None for b in bandes])
    d = np.array([0 if b[2] is None else b[2] for b in bandes], F32)
    wcol = rng.uniform(0.8, 1.5, nb).astype(F32)
    ton = rng.uniform(0.75, 1.5, nb).astype(F32)
    rtop = (1300 + d * 45 + rng.uniform(-250, 250, nb)).astype(F32)
    soff = rng.random(nb).astype(F32)
    neon = rng.integers(0, 3, nb)          # 0 rien, 1 cyan, 2 rouge
    enseigne = rng.random(nb) < 0.5
    eteint = rng.random(nb) < 0.18
    bi = np.digitize(ang, lo[1:])
    a0, w, tn, rt = lo[bi], wcol[bi], ton[bi], rtop[bi]
    bat = (~trou[bi]) & (r > rt)
    col = (ang - a0) / w
    ci = np.floor(col)
    u = col - ci
    kf = 110000.0 / r + soff[bi] * 10
    fi = np.floor(kf)
    t = kf - fi
    et = np.maximum(110000.0 / (r * r), 0.004)
    eu = 1.0 / (r * np.radians(w))
    win = soft1d(t - 0.5, 0.26, et) * soft1d(u - 0.5, 0.30, eu)
    cell = ci + bi * 1000
    h1 = hsh(cell, fi, 1)
    h2 = hsh(cell, fi, 2)
    h3 = hsh(cell, fi, 3)
    lit = (h1 < 0.46) & ~eteint[bi]
    c_j, c_c, c_r = hexc("#fcee0a"), hexc("#00f0ff"), hexc("#ff003c")
    coul = np.where((h2 < 0.68)[..., None], c_j, np.where((h2 < 0.88)[..., None], c_c, c_r))
    # rangées d'enseignes
    rang = enseigne[bi] & (np.mod(fi, 17) == 5)
    winr = soft1d(t - 0.5, 0.22, et) * soft1d(u - 0.5, 0.5, eu)
    cr = np.where((neon[bi] == 2)[..., None], c_r, c_c)
    base = hexc("#0d0d0d")
    wall = base[None, None, :] * tn[..., None]
    # liseré sombre entre colonnes
    wall = wall * (0.55 + 0.45 * lisse(0.0, 0.06, u) * lisse(1.0, 0.94, u))[..., None]
    img = np.empty((H, W, 3), F32)
    ciel = base * 0.55 + c_c * 0.05 * lisse(1100, 2700, r)[..., None] + c_r * 0.04 * lisse(2200, 4200, r)[..., None]
    img[:] = ciel
    unlit = wall * 1.0 + c_c * 0.012
    f = bat[..., None]
    corps = wall * (1 - win[..., None]) + unlit * win[..., None]
    img = np.where(f, corps, img)
    E = np.zeros((H, W, 3), F32)
    E += (win * lit * bat * (0.65 + 0.55 * h3))[..., None] * coul
    E += (winr * rang * bat * 0.9)[..., None] * cr
    nb_ = np.isin(neon[bi], (1, 2)) & bat
    ligne_n = np.clip(1 - u / (3.0 * eu), 0, 1) ** 1.5 * nb_
    E += ligne_n[..., None] * cr * 0.9
    # liseré de toit
    toit = np.clip(1 - np.abs(r - rt) / 5.0, 0, 1) * (~trou[bi]) * (rt < 2800)
    E += toit[..., None] * np.where((neon[bi] == 2)[..., None], c_r, c_c) * 0.7
    img = img + E
    g1 = vers_canaux(E, lambda a: blur(a, 14))
    g2 = vers_canaux(E, lambda a: blur(a, 60))
    img = img + g1 * 0.9 + g2 * 1.5
    # brume de la rue
    y_ = np.arange(H, dtype=F32)[:, None, None]
    brume = lisse(1500, 2400, y_) * (0.5 + 0.5 * lisse(1500, 400, np.abs(xx - W / 2))[..., None])
    img = img + brume * (c_c * 0.06 + c_r * 0.05)
    # pluie
    rain = Toile()
    for _ in range(3200):
        x, y = rng.random() * (W + 400), rng.random() * H
        ln = 40 + rng.random() * 90
        rain.ligne([(x, y), (x - ln * 0.18, y + ln)], 1.4, v=int(60 + 150 * rng.random()))
    m = rain.a()
    lum = np.clip((g1 + g2).sum(-1) * 0.8, 0, 1)
    img = img + (m * (0.05 + 0.5 * lum))[..., None] * np.array([0.8, 1.0, 1.0], F32)
    # vignette
    vig = 1 - 0.45 * lisse(0.55, 1.25, np.hypot((xx - W / 2) / (W / 2), (yy - H * 0.45) / (H / 2)))
    img = img * vig[..., None]
    sauver3(img, "cyberjaune-avenue", grain=0.9, seed=311)


def cyberjaune_circuits():
    rng = np.random.default_rng(312)
    noir_t, rouge_t, cyan_t, puces = Toile(), Toile(), Toile(), Toile()
    calme = (1050, 2790, 0, 760)          # zone calme : haut au centre

    def dans_calme(x, y, m=60):
        return calme[0] - m < x < calme[1] + m and y < calme[3] + m

    dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    pas = 54
    for i in range(70):
        # départ sur un bord latéral ou le bas
        cote = rng.integers(0, 3)
        if cote == 0:
            x, y = -20.0, (rng.integers(0, H // pas)) * pas + 30.0
            d = 0
        elif cote == 1:
            x, y = W + 20.0, (rng.integers(0, H // pas)) * pas + 30.0
            d = 4
        else:
            x, y = (rng.integers(0, W // pas)) * pas + 30.0, H - 230.0
            d = 6
        pts = [(x, y)]
        for _ in range(int(rng.integers(3, 8))):
            L = float(rng.integers(2, 7) * pas)
            vx, vy = dirs[d]
            n = math.hypot(vx, vy)
            nx, ny = x + vx / n * L, y + vy / n * L
            if dans_calme(nx, ny) or not (-60 < nx < W + 60 and -60 < ny < H):
                break
            x, y = nx, ny
            pts.append((x, y))
            d = (d + int(rng.choice([-1, 1, -2, 2]))) % 8
        if len(pts) < 2:
            continue
        ep = float(rng.choice([8, 12, 16]))
        noir_t.ligne(pts, ep)
        for p in pts[1:-1]:
            noir_t.ell(p[0], p[1], ep / 2)
        x, y = pts[-1]
        R = 22 + ep
        noir_t.ell(x, y, R)
        noir_t.ell(x, y, R - 8, v=0)
        noir_t.ell(x, y, R - 14)
        t_ = rng.random()
        if t_ < 0.22:
            cyan_t.ell(x, y, R - 14)
        elif t_ < 0.34:
            rouge_t.ell(x, y, R - 14)
    # puces à pattes
    for (cx, cy, w_, h_) in [(430, 640, 420, 300), (3340, 760, 380, 340), (780, 1500, 300, 420),
                             (3060, 1560, 440, 280), (1900, 1520, 360, 260)]:
        if dans_calme(cx, cy, 0):
            continue
        n = 9
        for k in range(n):
            px = cx - w_ / 2 + (k + 0.5) * w_ / n
            puces.rect(px - 9, cy - h_ / 2 - 52, px + 9, cy - h_ / 2 + 4)
            puces.rect(px - 9, cy + h_ / 2 - 4, px + 9, cy + h_ / 2 + 52)
        puces.rect(cx - w_ / 2, cy - h_ / 2, cx + w_ / 2, cy + h_ / 2)
        puces.ell(cx - w_ / 2 + 44, cy - h_ / 2 + 44, 14, v=0)
        puces.rect(cx - w_ / 2 + 80, cy - 24, cx + w_ / 2 - 80, cy + 24, v=0)
        puces.rect(cx - w_ / 2 + 96, cy - 10, cx + w_ / 2 - 96, cy + 10)
    # bande à rayures diagonales en bas
    rayures, zone = Toile(), Toile()
    zone.rect(0, 2190, W, H)
    for k in range(-4, 60):
        x0 = k * 120
        rayures.poly([(x0, H), (x0 + 60, H), (x0 + 60 + 240, 2190), (x0 + 240, 2190)])
    bande = rayures.a() * zone.a()
    z_haut = Toile()
    z_haut.poly([(0, 0), (520, 0), (0, 520)])
    z2 = Toile()
    for k in range(-4, 14):
        z2.poly([(k * 90, 0), (k * 90 + 45, 0), (k * 90 - 475, 520), (k * 90 - 520, 520)])
    coin = z2.a() * z_haut.a()
    noir = np.maximum(np.maximum(noir_t.a(), puces.a()), np.maximum(bande, coin))
    jaune = hexc("#fcee0a")
    y_ = np.arange(H, dtype=F32)[:, None]
    x_ = np.arange(W, dtype=F32)[None, :]
    lum = 1.0 + 0.05 * (1 - np.hypot((x_ - W / 2) / W, (y_ - 120) / H) * 1.6)
    grain_f = fbm(W // 4, H // 4, rng, base=6, octaves=4)
    lum = lum * (0.97 + 0.05 * np.asarray(Image.fromarray((grain_f * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), F32) / 255)
    img = jaune[None, None, :] * lum[..., None]
    ombre = blur(np.roll(np.roll(noir, 7, 0), 9, 1), 9)
    img = img * (1 - 0.30 * ombre)[..., None]
    mix(img, hexc("#0d0d0d"), noir)
    mix(img, hexc("#00f0ff"), cyan_t.a() * (1 - bande))
    mix(img, hexc("#ff003c"), rouge_t.a() * (1 - bande))
    sauver3(img, "cyberjaune-puces", grain=0.8, seed=312)


def _lueur(a, s1=10, s2=40):
    """Lueur douce d'un masque : somme de deux flous."""
    return blur(a, s1) * 0.8 + blur(a, s2) * 1.2


def pluie_verte_colonnes():
    rng = np.random.default_rng(321)
    vx, vy = 1920.0, 1180.0
    vif, fonce, faces, leds = Toile(), Toile(), Toile(), Toile()
    ds = [0.42 * 1.22 ** i for i in range(22)]
    for sgn in (-1, 1):
        for i in range(len(ds) - 1):
            d0, d1 = ds[i], ds[i + 1]
            xs0, xs1 = vx + sgn * 900 / d0, vx + sgn * 900 / d1
            t0, t1 = vy - 760 / d0, vy - 760 / d1
            b0, b1 = vy + 520 / d0, vy + 520 / d1
            ep = max(2.0, 9 / d0)
            faces.poly([(xs0, t0), (xs1, t1), (xs1, b1), (xs0, b0)])
            vif.ligne([(xs0, t0), (xs0, b0)], ep)
            for k in range(0, 9):                       # étagères
                f = k / 8
                (vif if k % 4 == 0 else fonce).ligne(
                    [(xs0, t0 + (b0 - t0) * f), (xs1, t1 + (b1 - t1) * f)], ep * 0.8)
                if k < 8:
                    for j in range(3):                  # voyants
                        u = 0.2 + 0.3 * j + rng.random() * 0.1
                        px = xs0 + (xs1 - xs0) * u
                        py = t0 + (b0 - t0) * (f + 0.06) + (t1 - t0 - (b0 - b1 + t0 - t1)) * 0
                        py = (t0 + (t1 - t0) * u) + ((b0 - t0) + ((b1 - t1) - (b0 - t0)) * u) * (f + 0.06)
                        if rng.random() < 0.55:
                            leds.ell(px, py, max(2.0, 7 / d0))
        # sol : lignes de dalles
    for i in range(len(ds)):
        d = ds[i]
        y = vy + 520 / d
        fonce.ligne([(vx - 900 / d, y), (vx + 900 / d, y)], max(1.5, 5 / d))
    for k in range(-8, 9):
        fx = k / 8
        fonce.ligne([(vx + fx * 900 / ds[0], vy + 520 / ds[0]), (vx + fx * 900 / ds[-1], vy + 520 / ds[-1])], 3)
    # plafond : rails lumineux discrets, hors zone calme
    for fx in (-0.62, 0.62):
        vif.ligne([(vx + fx * 900 / ds[0], vy - 760 / ds[0]), (vx + fx * 900 / ds[-1], vy - 760 / ds[-1])], 6)
    y_ = np.arange(H, dtype=F32)[:, None]
    x_ = np.arange(W, dtype=F32)[None, :]
    prof = np.clip(1 - np.hypot((x_ - vx) / 3200, (y_ - vy) / 1900), 0, 1)
    brillance = 0.35 + 0.9 * prof ** 1.3
    vif_a, fonce_a, faces_a, leds_a = vif.a(), fonce.a(), faces.a(), leds.a()
    img = np.zeros((H, W, 3), F32)
    img += hexc("#000d00")[None, None, :]
    mix(img, hexc("#001a05"), faces_a * 0.9)
    mix(img, hexc("#008f11"), fonce_a * brillance * 0.9)
    mix(img, hexc("#00ff41"), vif_a * brillance)
    mix(img, hexc("#00ff41"), leds_a * 0.85)
    glow = _lueur(vif_a * brillance + leds_a)
    img += hexc("#00ff41")[None, None, :] * (0.55 * glow)[..., None]
    # lueur du fond de couloir
    img += hexc("#008f11")[None, None, :] * (0.5 * np.exp(-(((x_ - vx) / 700) ** 2 + ((y_ - vy) / 420) ** 2)))[..., None]
    img *= (1 - 0.55 * np.clip(np.hypot((x_ - W / 2) / 2400, (y_ - H / 2) / 1500) - 0.35, 0, 1))[..., None]
    sauver3(img, "pluie-verte-couloir", grain=0.9, seed=321)


def pluie_verte_horizon():
    rng = np.random.default_rng(322)
    pas = 30
    gx, gy = W // pas, 1500 // pas
    terre = fbm(gx, gy, rng, base=2, octaves=5, gain=0.5)
    yy = np.linspace(-1, 1, gy)[:, None]
    xx = np.linspace(-1, 1, gx)[None, :]
    terre = terre - 0.35 * np.abs(yy) ** 2 - 0.12 * np.abs(xx) ** 3
    seuil = np.quantile(terre, 0.52)
    sol = terre > seuil
    y0 = 620                                  # le planisphère est sous la zone calme
    pts, vifs = Toile(), Toile()
    liste = []
    for j in range(gy):
        for i in range(gx):
            if sol[j, i]:
                cx, cy = i * pas + pas / 2, y0 + j * pas
                liste.append((cx, cy))
                r = 5.2 if (i + j) % 2 == 0 else 4.2
                pts.ell(cx, cy, r)
                if rng.random() < 0.012:
                    vifs.ell(cx, cy, 11)
    liste = np.array(liste)
    arcs = Toile()
    for _ in range(34):
        a, b = liste[rng.integers(0, len(liste))], liste[rng.integers(0, len(liste))]
        dist = math.hypot(*(b - a))
        if dist < 450:
            continue
        m = (a + b) / 2 - np.array([0, dist * 0.32])
        t = np.linspace(0, 1, 60)[:, None]
        c = (1 - t) ** 2 * a + 2 * (1 - t) * t * m + t ** 2 * b
        arcs.ligne([tuple(p) for p in c], 3.0)
        vifs.ell(a[0], a[1], 12)
        vifs.ell(b[0], b[1], 12)
    y_ = np.arange(H, dtype=F32)[:, None]
    x_ = np.arange(W, dtype=F32)[None, :]
    base = vgrad([(0, "#000d00"), (0.55, "#001404"), (1, "#000d00")])
    img = base.copy()
    sph = np.exp(-(((x_ - W / 2) / 1800) ** 2 + ((y_ - 1400) / 900) ** 2))
    img += hexc("#008f11")[None, None, :] * (0.14 * sph)[..., None]
    pa, va, aa = pts.a(), vifs.a(), arcs.a()
    fade = np.clip((y_ - 560) / 300, 0, 1) * np.clip((2250 - y_) / 300, 0, 1)
    mix(img, hexc("#008f11"), pa * fade)
    mix(img, hexc("#008f11"), aa * 0.9)
    mix(img, hexc("#00ff41"), va)
    mix(img, hexc("#00ff41"), pa * 0.55 * sph * fade)
    img += hexc("#00ff41")[None, None, :] * (0.5 * _lueur(va + aa * 0.3))[..., None]
    img *= (1 - 0.5 * np.clip(np.hypot((x_ - W / 2) / 2400, (y_ - H / 2) / 1500) - 0.4, 0, 1))[..., None]
    sauver3(img, "pluie-verte-reseau", grain=0.9, seed=322)


def brutaliste_beton():
    rng = np.random.default_rng(331)
    y_ = np.arange(H, dtype=F32)[:, None]
    x_ = np.arange(W, dtype=F32)[None, :]
    clair = hexc("#f2f2f2")
    grain = fbm(W // 2, H // 2, rng, base=40, octaves=4, gain=0.55)
    grain = np.asarray(Image.fromarray((grain * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), F32) / 255
    taches = np.asarray(Image.fromarray((fbm(W // 8, H // 8, rng, base=4, octaves=4) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), F32) / 255
    lum = 0.80 + 0.07 * grain + 0.07 * taches
    lum = lum * (1.04 - 0.10 * (y_ / H))
    img = clair[None, None, :] * lum[..., None]
    # joints de coffrage : panneaux de 480 x 400
    joints = Toile()
    for x in range(0, W + 1, 480):
        joints.rect(x - 1.5, 0, x + 1.5, H)
    for y in range(0, H + 1, 400):
        joints.rect(0, y - 1.5, W, y + 1.5)
    img *= (1 - 0.16 * joints.a())[..., None]
    for x in range(120, W, 480):                      # trous de banche
        for y in range(80, H, 400):
            img[int(y) - 6:int(y) + 6, x - 6:x + 6] *= 0.72
    # grille de fenêtres, hors zone calme du haut
    cadre, creux, jaune_m, rouge_m = Toile(), Toile(), Toile(), Toile()
    wx, wy, px, py = 240, 300, 480, 400
    jaune_cell = (5, 3)
    for j, y in enumerate(range(920, H - 100, py)):
        for i, x in enumerate(range(0, W, px)):
            x0, y0 = x + 120, y + 50
            creux.rect(x0, y0, x0 + wx, y0 + wy)
            if (i, j) == jaune_cell:
                jaune_m.rect(x0, y0, x0 + wx, y0 + wy)
            elif (i, j) == (2, 2):
                rouge_m.rect(x0, y0, x0 + wx, y0 + wy)
    c = creux.a()
    # ombre portée de la façade sur le creux (lumière en haut à gauche)
    dec = np.roll(np.roll(c, 26, 0), 22, 1)
    ombre_int = np.clip(c - np.roll(np.roll(c, 26, 0), 22, 1) * 0 , 0, 1) * np.clip(1 - dec, 0, 1) * 0
    fond_fen = hexc("#0d0d0d")[None, None, :] * (0.55 + 0.45 * (y_ / H))[..., None]
    interieur = np.clip(1 - 0.0 * c, 0, 1)
    mix(img, hexc("#1b1b1b"), c * 0.96)
    # reflet doux dans les vitres (dégradé diagonal)
    refl = np.clip(0.5 + 0.5 * np.sin((x_ + y_) / 260), 0, 1) * 0.10
    mix(img, hexc("#4a4a4a"), c * refl)
    mix(img, hexc("#ffe600"), jaune_m.a())
    mix(img, hexc("#ff3b30"), rouge_m.a() * 0.0)
    # ombre intérieure en haut et à gauche de chaque creux
    haut = np.clip(c - np.roll(c, 36, 0), 0, 1)
    gauche = np.clip(c - np.roll(c, 30, 1), 0, 1)
    img *= (1 - 0.55 * np.maximum(haut, gauche) * (1 - jaune_m.a()))[..., None]
    # ombre portée dehors, bas et droite
    ext = blur(np.roll(np.roll(c, 18, 0), 14, 1), 9) * (1 - c)
    ext[:200] = 0                                     # le roll ramène l'ombre du bas en haut
    img *= (1 - 0.32 * ext)[..., None]
    # dalle sombre du bandeau en haut du premier étage
    bandeau = Toile()
    bandeau.rect(0, 840, W, 880)
    img *= (1 - 0.35 * bandeau.a())[..., None]
    img *= (1 - 0.18 * np.clip(np.hypot((x_ - W / 2) / 2400, (y_ - 500) / 1700) - 0.45, 0, 1))[..., None]
    sauver3(img, "brutaliste-facade", grain=1.3, seed=331)


def brutaliste_blocs():
    rng = np.random.default_rng(332)
    y_ = np.arange(H, dtype=F32)[:, None]
    x_ = np.arange(W, dtype=F32)[None, :]
    papier = hexc("#f2f2f2")
    fib = fbm(W // 4, H // 4, rng, base=24, octaves=3)
    fib = np.asarray(Image.fromarray((fib * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), F32) / 255
    img = papier[None, None, :] * (0.93 + 0.04 * fib - 0.04 * (y_ / H))[..., None]
    noir, jaune, rouge = Toile(), Toile(), Toile()
    # gros blocs
    noir.rect(160, 1000, 1700, 2240)
    jaune.ell(2700, 1500, 640)
    rouge.rect(1700, 1500, 3000, 1740)
    noir.rect(3000, 780, 3680, 2240)
    # barres abstraites façon lignes de texte, sans aucune lettre
    noir.rect(160, 300, 760, 420)
    jaune.rect(160, 520, 1360, 640)
    noir.rect(160, 740, 440, 860)
    # bande de rayures verticales
    for k in range(14):
        noir.rect(1900 + k * 60, 300, 1900 + k * 60 + 28, 1300)
    rouge.ell(3280, 480, 120)
    # chevauchements : le cercle jaune passe sous la barre rouge
    n, j, r = noir.a(), jaune.a(), rouge.a()
    ombre = blur(np.roll(np.roll(np.maximum(np.maximum(n, j), r), 14, 0), 14, 1), 8)
    img *= (1 - 0.22 * ombre)[..., None]
    mix(img, hexc("#ffe600"), j)
    mix(img, hexc("#0d0d0d"), n)
    mix(img, hexc("#ff3b30"), r)
    # demi-teinte : points noirs sur le bloc noir pour le relief
    sauver3(img, "brutaliste-affiche", grain=1.1, seed=332)


def _sous(f):
    """Masque AA de la zone sous une courbe f(x) (tableau de W valeurs)."""
    y = np.arange(H, dtype=F32)[:, None]
    return np.clip(y - f[None, :] + 0.5, 0, 1)


def _ombre_haut(m, dy=26, s=14, k=0.30):
    """Ombre portée vers le haut d'une couche de papier (masque m)."""
    return blur(np.roll(m, -dy, 0), s) * k * (1 - m)


def _plein(a, h=H, w=W):
    return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), F32) / 255


def clair_neutre_formes():
    rng = np.random.default_rng(351)
    x = np.arange(W, dtype=F32)
    img = vgrad([(0, "#f6f8fb"), (0.6, "#eef2f8"), (1, "#e4ebf5")])
    # grand disque pâle à droite
    yy, xx = np.mgrid[0:H, 0:W].astype(F32)
    d = np.hypot(xx - 2900, yy - 900)
    mix(img, hexc("#cfe0f6"), np.clip((560 - d) / 3 + 0.5, 0, 1) * 0.55)
    couches = [(1150, "#dfe9f6", 140, 0.0), (1400, "#c9dcf3", 170, 1.3), (1660, "#a7c6ee", 190, 2.1),
               (1920, "#7fb0e8", 170, 3.4), (2150, "#3584e4", 120, 4.2)]
    for k, (base, col, amp, ph) in enumerate(couches):
        f = base + amp * np.sin(x / 520 + ph) + amp * 0.45 * np.sin(x / 190 + ph * 2.3)
        m = _sous(f)
        img *= (1 - _ombre_haut(m, 30, 22, 0.22))[..., None]
        c = hexc(col)
        if k == 0:
            c = hexc("#deddda") * 0.4 + c * 0.6
        # dégradé doux dans la colline
        t = np.clip((np.arange(H, dtype=F32)[:, None] - f[None, :]) / 500, 0, 1)
        mix(img, c, m)
        img *= (1 - 0.10 * t * m)[..., None]
    sauver3(img, "clair-neutre-collines", grain=0.9, seed=351)


def clair_neutre_vagues():
    rng = np.random.default_rng(352)
    x = np.arange(W, dtype=F32)
    img = vgrad([(0, "#f5f5f4"), (1, "#ecedee")])
    gris, bleu = hexc("#deddda"), hexc("#3584e4")
    n = 9
    for k in range(n):
        t = k / (n - 1)
        base = 700 + k * 205
        lam = 700 - 25 * k
        ph = k * 1.7
        f = base + 90 * np.sin(2 * np.pi * x / lam + ph) + 40 * np.sin(2 * np.pi * x / (lam * 0.37) + ph * 3)
        m = _sous(f)
        img *= (1 - _ombre_haut(m, 34, 20, 0.20))[..., None]
        col = gris * (1 - t ** 1.3) + bleu * t ** 1.3
        col = col * 0.55 + hexc("#f0f4fa") * 0.45 * (1 - t) + col * 0.0
        col = col * (1 - 0.0)
        mix(img, np.clip(col, 0, 1), m)
    sauver3(img, "clair-neutre-papier", grain=0.9, seed=352)


def gruvbox_ble():
    rng = np.random.default_rng(361)
    hz = 1250
    img = vgrad([(0, "#1d2021"), (0.25, "#3c2a22"), (0.42, "#af3a03"), (0.5, "#fe8019"), (0.53, "#fabd2f")])
    yy, xx = np.mgrid[0:H, 0:W].astype(F32)
    sx, sy = 2600, hz - 80
    d = np.hypot(xx - sx, yy - sy)
    mix(img, hexc("#fabd2f"), np.clip((200 - d) / 3 + 0.5, 0, 1) * 0.9)
    img += hexc("#fe8019")[None, None, :] * (0.35 * np.exp(-(d / 700) ** 2))[..., None]
    # champ
    y = np.arange(H, dtype=F32)[:, None]
    t = np.clip((y - hz) / (H - hz), 0, 1)
    fine = _plein(rng.random((H // 3, W // 2)).astype(F32), H, W)
    raies = _plein(rng.random((H // 90, W // 3)).astype(F32), H, W)
    raies = blur(raies, 2)
    luma = np.clip(0.55 * fine + 0.9 * raies, 0, 1.2)
    lum_sol = np.exp(-((xx - sx) / (900 + 900 * t)) ** 2)
    champ = hexc("#b57614")[None, None, :] * (0.35 + 0.65 * luma[..., None])
    champ = champ * (0.45 + 0.35 * t[..., None]) + hexc("#fabd2f")[None, None, :] * (0.55 * lum_sol * (0.4 + 0.6 * luma))[..., None] * (1 - 0.5 * t)[..., None]
    champ = champ + hexc("#b8bb26")[None, None, :] * (0.07 * fine * t)[..., None]
    mfield = np.clip(y - hz + 0.5, 0, 1) + 0 * xx
    # vague douce sur la ligne d'horizon
    mix(img, np.clip(champ, 0, 1), mfield)
    brume = np.exp(-((y - hz) / 90) ** 2) * 0.35
    img += hexc("#fe8019")[None, None, :] * brume[..., None] * 0.4
    # arbre seul, à gauche
    ar = Toile()
    tx, tb = 1050, hz + 60
    ar.poly([(tx - 26, tb), (tx - 12, tb - 330), (tx - 90, tb - 480), (tx - 70, tb - 490), (tx - 6, tb - 400),
             (tx + 6, tb - 420), (tx + 80, tb - 560), (tx + 98, tb - 548), (tx + 16, tb - 380), (tx + 28, tb)])
    couronne = [(0, -640, 300), (-250, -580, 220), (260, -600, 230), (-380, -480, 170), (380, -490, 170),
                (-120, -770, 190), (150, -790, 180), (0, -500, 260), (-260, -420, 120), (300, -400, 120)]
    for dx, dy, r in couronne:
        ar.ell(tx + dx, tb + dy, r, r * 0.8)
    for _ in range(90):                                  # feuilles qui dépassent
        a = rng.uniform(0, 2 * np.pi)
        r = rng.uniform(280, 440)
        ar.ell(tx + np.cos(a) * r * 1.0, tb - 560 + np.sin(a) * r * 0.75, rng.uniform(14, 40))
    am = ar.a()
    ombre = np.clip(1 - np.abs(xx - tx - 420 + 0) / 0.1, 0, 0)  # pas d'ombre au sol détaillée
    mix(img, hexc("#1d2021"), am)
    # liseré de lumière du soleil sur le bord droit de l'arbre
    bord = np.clip(am - np.roll(am, -6, 1), 0, 1)
    mix(img, hexc("#fe8019"), bord * 0.55)
    # ombre allongée de l'arbre sur le champ
    sh = blur(np.roll(am, (-int(hz * 0.0) + 0), 0), 1) * 0
    img *= (1 - 0.5 * np.clip(1 - np.hypot((xx - W / 2) / 3000, (yy - H / 2) / 2000), 0, 1) * 0)[..., None]
    img *= (1 - 0.35 * np.clip(np.hypot((xx - W / 2) / 2200, (yy - 1000) / 1600) - 0.55, 0, 1))[..., None]
    sauver3(img, "gruvbox-ble", grain=1.4, seed=361)


def _gauss1(a, s):
    k = np.arange(-int(4 * s), int(4 * s) + 1)
    g = np.exp(-(k / s) ** 2 / 2)
    g /= g.sum()
    return np.convolve(np.pad(a, len(k) // 2, mode="edge"), g, "valid").astype(F32)


def gruvbox_canyon():
    rng = np.random.default_rng(362)
    img = vgrad([(0, "#1d2021"), (0.22, "#3c3836"), (0.4, "#8f3f1a"), (0.5, "#d65d0e"), (0.56, "#fe8019"), (0.62, "#fabd2f")])
    yy, xx = np.mgrid[0:H, 0:W].astype(F32)
    sx, sy = 2500, 1180
    d = np.hypot(xx - sx, yy - sy)
    mix(img, hexc("#fabd2f"), np.clip((170 - d) / 3 + 0.5, 0, 1))
    img += hexc("#fe8019")[None, None, :] * (0.4 * np.exp(-(d / 650) ** 2))[..., None]
    x = np.arange(W, dtype=F32)
    y = np.arange(H, dtype=F32)[:, None]
    n = 6
    ciel = hexc("#fe8019")
    for k in range(n):
        t = k / (n - 1)
        base = 1160 + k * 235
        amp = 250 - 14 * k
        prof = fbm1d(W, rng, base=2 + k // 3, octaves=3, gain=0.5)
        prof = prof / (np.abs(prof).max() + 1e-6)
        niv = np.floor(prof * 2.6 + 0.5) / 2.6                    # plateaux larges
        f = base - amp * _gauss1(niv, 12 + 5 * k) + 7 * fbm1d(W, rng, base=40, octaves=2)
        m = _sous(f)
        # strates horizontales nettes (hauteur absolue, comme la roche réelle)
        p = 16 + 7 * k
        idx = ((y + rng.integers(0, p)) // p).astype(int)
        val = rng.random(idx.max() + 2).astype(F32)[idx]
        cloin = hexc("#e0782e") * (1 - t) + hexc("#43200f") * t
        col = cloin[None, None, :] * (0.80 + 0.40 * (val - 0.5) + 0.0)[..., None] * np.ones((1, W, 1), F32)
        col = col + hexc("#d79921")[None, None, :] * (0.10 * (val > 0.8) * (1 - t))[..., None]
        # parois à pente : plus sombres ; sommets éclairés
        g = np.abs(np.gradient(f))
        paroi = np.clip(g / 2.0, 0, 1)
        prof_s = np.clip(1 - (y - f[None, :]) / (amp * 1.2), 0, 1)
        col = col * (1 - 0.40 * paroi[None, :] * prof_s)[..., None]
        sommet = np.clip(1 - (y - f[None, :]) / 10, 0, 1)
        col = col + hexc("#fabd2f")[None, None, :] * (0.55 * sommet * (1 - 0.5 * t))[..., None]
        # brume entre les plans
        fog = (1 - t) ** 1.5 * 0.55
        col = col * (1 - fog) + ciel[None, None, :] * fog * 0.75
        col = col * (1 - 0.30 * np.clip((y - f[None, :]) / 600, 0, 1))[..., None]
        img *= (1 - _ombre_haut(m, 24, 18, 0.30 * t))[..., None]
        mix(img, np.clip(col, 0, 1), m)
    img *= (1 - 0.35 * np.clip(np.hypot((xx - W / 2) / 2200, (yy - 1000) / 1700) - 0.55, 0, 1))[..., None]
    sauver3(img, "gruvbox-canyon", grain=1.3, seed=362)


def kanagawa_brume():
    rng = np.random.default_rng(371)
    img = vgrad([(0, "#1a1a22"), (0.3, "#252535"), (0.55, "#3a3a52"), (0.7, "#54546d")])
    yy, xx = np.mgrid[0:H, 0:W].astype(F32)
    sx, sy = 2650, 880
    d = np.hypot(xx - sx, yy - sy)
    mix(img, hexc("#c34043"), np.clip((230 - d) / 3 + 0.5, 0, 1) * 0.85)
    img += hexc("#d27e99")[None, None, :] * (0.30 * np.exp(-(d / 560) ** 2))[..., None]
    x = np.arange(W, dtype=F32)
    y = np.arange(H, dtype=F32)[:, None]
    fog = hexc("#54546d")
    n = 7
    for k in range(n):
        t = k / (n - 1)
        base = 1000 + k * 190
        prof = fbm1d(W, rng, base=2 + k // 2, octaves=5, gain=0.55)
        pic = np.abs(prof) ** 1.1 * (0.7 + 0.5 * np.sin(x / (1300 - 70 * k) + k * 2.0) ** 2)
        f = base - 420 * (1 - 0.5 * t) * pic
        m = _sous(f)
        ink = hexc("#16161d") * t + hexc("#43436c") * (1 - t)
        col = np.broadcast_to(ink, (H, W, 3)).copy()
        # la brume monte du pied : plus claire en bas de chaque couche
        b = np.clip(1 - (y - f[None, :]) / 380, 0, 1)
        h2 = 1 - b
        col = col * (1 - 0.0)
        col = col * (1 - 0.65 * (1 - t) ** 0.5 * h2[..., None]) + fog[None, None, :] * (0.65 * (1 - t) ** 0.5 * h2[..., None]) * 0
        # brume : bas de couche vers fog
        bas = np.clip((y - f[None, :]) / 300, 0, 1)
        col = col * (1 - 0.8 * bas[..., None] * (0.9 - 0.4 * t)) + fog[None, None, :] * (0.8 * bas[..., None] * (0.9 - 0.4 * t))
        # crête éclairée par le soleil (lueur rose)
        crete = np.exp(-((y - f[None, :]) / 6) ** 2) * 0.35 * (1 - t) * np.exp(-((x[None, :] - sx) / 1500) ** 2)
        col = col + hexc("#d27e99")[None, None, :] * crete[..., None]
        mix(img, np.clip(col, 0, 1), m)
    # voile de brume diffus
    voile = _plein(fbm(W // 16, H // 16, rng, base=3, octaves=3))
    img += fog[None, None, :] * (0.10 * voile * np.exp(-((yy - 1500) / 600) ** 2))[..., None]
    sauver3(img, "kanagawa-brume", grain=1.2, seed=371)


def kanagawa_ressac():
    encre = hexc("#1f1f28")
    img = np.broadcast_to(encre, (H, W, 3)).copy()
    R = 290
    pas_x, pas_y = 2 * R, R // 2
    bandes = [("#dcd7ba", 1.0), ("#7e9cd8", 0.82), ("#dcd7ba", 0.64), ("#7e9cd8", 0.46), ("#dcd7ba", 0.28), ("#7e9cd8", 0.12)]
    for j, cy in enumerate(range(-R, H + 2 * R, pas_y)):
        dec = 0 if j % 2 == 0 else R
        # les rangées du haut s'enfoncent dans l'encre
        vis = float(np.clip((cy - 250) / (H * 0.55), 0, 1)) ** 1.1
        for cx in range(-R + dec - 2 * R, W + 2 * R, pas_x):
            x0, x1 = max(cx - R, 0), min(cx + R, W)
            y0, y1 = max(cy - R, 0), min(cy + R, H)
            if x1 <= x0 or y1 <= y0:
                continue
            gy, gx = np.mgrid[y0:y1, x0:x1].astype(F32)
            r = np.hypot(gx - cx, gy - cy) / R
            reg = img[y0:y1, x0:x1]
            mix(reg, encre, np.clip((1 - r) * R / 1.2, 0, 1))
            for c, lim in bandes:
                cc = hexc(c) * vis + encre * (1 - vis)
                if c == "#7e9cd8":
                    cc = cc * 0.9 + hexc("#957fb8") * 0.1 * vis
                mix(reg, cc, np.clip((lim - r) * R / 1.2, 0, 1))
    yy = np.arange(H, dtype=F32)[:, None]
    xx = np.arange(W, dtype=F32)[None, :]
    img *= (1 - 0.30 * np.clip(np.hypot((xx - W / 2) / 2400, (yy - 1500) / 1700) - 0.5, 0, 1))[..., None]
    sauver3(img, "kanagawa-ressac", grain=1.2, seed=372)


def _ciel_vapor(hz, sx, sy, r):
    """Ciel dégradé et grand soleil pâle à fentes (jusqu'à l'horizon hz)."""
    img = vgrad([(0, "#2b1055"), (0.22, "#5a2a8a"), (0.38, "#b04aa8"), (0.5, "#ff71ce"), (hz / H, "#ffc2ea"), (1, "#ffc2ea")])
    yy, xx = np.mgrid[0:H, 0:W].astype(F32)
    d = np.hypot(xx - sx, yy - sy)
    img += hexc("#ff71ce")[None, None, :] * (0.30 * np.exp(-(d / (r * 1.8)) ** 2))[..., None]
    t = np.clip((yy - (sy - r)) / (2 * r), 0, 1)
    sol = hexc("#fffb96")[None, None, :] * (1 - t[..., None]) + hexc("#ff9de0")[None, None, :] * t[..., None]
    disque = np.clip((r - d) / 3 + 0.5, 0, 1)
    # fentes horizontales de plus en plus larges vers le bas
    fentes = np.ones((H, W), F32)
    for i in range(9):
        yc = sy + r * (0.05 + 0.105 * i)
        ep = 4 + 5 * i
        fentes = np.minimum(fentes, np.clip(np.abs(yy - yc) / 2 - ep / 2 + 0.5, 0, 1))
    mix(img, sol * 0.97, disque * fentes * 0.92)
    return img, yy, xx


def _sphere(img, cx, cy, r, clair, sombre, lum=(-0.5, -0.6, 0.62)):
    x0, x1 = int(max(cx - r - 3, 0)), int(min(cx + r + 3, W))
    y0, y1 = int(max(cy - r - 3, 0)), int(min(cy + r + 3, H))
    gy, gx = np.mgrid[y0:y1, x0:x1].astype(F32)
    nx, ny = (gx - cx) / r, (gy - cy) / r
    rr = np.hypot(nx, ny)
    nz = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    L = np.array(lum, F32)
    L /= np.linalg.norm(L)
    dif = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    col = hexc(sombre)[None, None, :] * (1 - dif[..., None]) + hexc(clair)[None, None, :] * dif[..., None]
    col = col + hexc("#ffffff")[None, None, :] * (0.55 * dif ** 18)[..., None]
    col = col + hexc("#01cdfe")[None, None, :] * (0.25 * np.clip(rr - 0.6, 0, 1) * (ny > 0))[..., None]
    mix(img[y0:y1, x0:x1], np.clip(col, 0, 1), np.clip((r - rr * r) / 1.5, 0, 1))


def vaporwave_damier():
    rng = np.random.default_rng(341)
    hz = 1400
    img, yy, xx = _ciel_vapor(hz, 2500, 1010, 470)
    # sol en damier en perspective (suréchantillonné 4x4 contre le moiré)
    d0 = hz
    y0 = hz
    n_y = H - y0
    A, B = hexc("#ff9de0"), hexc("#7fdcf5")
    acc = np.zeros((n_y, W), F32)
    for sy_ in range(4):
        for sx_ in range(4):
            gy = (np.arange(n_y, dtype=F32)[:, None] + (sy_ + 0.5) / 4) + 0.0
            gx = np.arange(W, dtype=F32)[None, :] + (sx_ + 0.5) / 4
            u = (gx - W / 2) / gy
            v = 1000.0 / gy
            acc += ((np.floor(u) + np.floor(v)) % 2).astype(F32)
    tm = (acc / 16)[..., None]
    sol = A[None, None, :] * (1 - tm) + B[None, None, :] * tm
    dd = np.arange(n_y, dtype=F32)[:, None]
    prof = np.clip(dd / 700, 0, 1)
    sol = sol * (0.55 + 0.45 * prof[..., None])
    # lointain : fondu vers la couleur de l'horizon (les carreaux deviennent trop fins)
    lointain = np.exp(-(dd / 90)) * 0.9
    sol = sol * (1 - lointain[..., None]) + hexc("#ffc2ea")[None, None, :] * lointain[..., None]
    img[y0:] = sol
    # lueur du soleil sur le sol
    img[y0:] += hexc("#fffb96")[None, None, :] * (0.16 * np.exp(-((xx[y0:] - 2500) / 700) ** 2) * np.exp(-dd / 300))[..., None]
    # colonnes en perspective, de chaque côté (de la plus loin à la plus proche)
    for cote in (-1, 1):
        for d in (50, 75, 110, 160, 235, 340, 500, 700):
            s = float(d)
            xc = W / 2 + cote * 2.3 * s * (1.0 if cote < 0 else 1.0)
            larg = 0.62 * s
            yb = hz + d
            ht = 6.0 * s
            cx0, cx1 = int(xc - larg / 2), int(xc + larg / 2)
            if cx1 < 0 or cx0 > W:
                continue
            ytop = int(max(yb - ht, 0))
            ybi = int(min(yb, H))
            ax0, ax1 = max(cx0, 0), min(cx1, W)
            u = (np.arange(ax0, ax1, dtype=F32) - xc) / (larg / 2)
            cyl = np.sqrt(np.clip(1 - u ** 2, 0, 1))
            lum = np.clip(0.55 + 0.45 * u, 0, 1) * cyl ** 0.4
            base = hexc("#fff0fa")[None, None, :] * lum[None, :, None] + hexc("#6a3a9a")[None, None, :] * (1 - lum)[None, :, None]
            hh = ybi - ytop
            if hh <= 0:
                continue
            # bague de chapiteau et de base
            base = base * np.ones((hh, 1, 1), F32)
            base[: max(int(0.05 * s), 2)] *= 0.75
            fog = float(np.clip(1 - d / 520, 0, 1)) * 0.45
            base = base * (1 - fog) + hexc("#ffc2ea")[None, None, :] * fog
            mix(img[ytop:ybi, ax0:ax1], np.clip(base, 0, 1), np.broadcast_to(np.clip((larg / 2 * cyl - 0.0) / 1.5, 0, 1)[None, :], (hh, ax1 - ax0)))
            # ombre au sol, étirée vers la gauche (le soleil est à droite)
            ex0, ex1 = int(max(cx0 - 1.6 * s, 0)), int(min(cx1, W))
            ey0, ey1 = int(yb - 0.04 * s), int(min(yb + 0.12 * s + 2, H))
            if ex1 > ex0 and ey1 > ey0:
                gy2, gx2 = np.mgrid[ey0:ey1, ex0:ex1].astype(F32)
                om = np.clip(1 - np.abs(gy2 - yb - 0.04 * s) / (0.08 * s), 0, 1) * np.clip((gx2 - (cx0 - 1.6 * s)) / (0.4 * s), 0, 1) * np.clip((cx1 - gx2) / 4, 0, 1)
                img[ey0:ey1, ex0:ex1] *= (1 - 0.35 * om)[..., None]
    img *= (1 - 0.28 * np.clip(np.hypot((xx - W / 2) / 2300, (yy - 1000) / 1700) - 0.6, 0, 1))[..., None]
    sauver3(img, "vaporwave-colonnade", grain=1.0, seed=341)


def vaporwave_mer():
    rng = np.random.default_rng(342)
    hz = 1320
    img, yy, xx = _ciel_vapor(hz, 1920, 1030, 430)
    # formes flottantes dans le ciel
    _sphere(img, 1150, 860, 170, "#7fe9ff", "#1a1066")
    _sphere(img, 2900, 700, 120, "#ff9de0", "#5a1a7a")
    _sphere(img, 3180, 1000, 60, "#05ffa1", "#0a5a6a")
    # anneau incliné autour de la grosse sphère
    an = Toile()
    an.ell(1150, 860, 330, 70)
    an.ell(1150, 860, 290, 52, 0)
    am = an.a()
    am *= 1 - ((yy < 860) & (np.hypot(xx - 1150, yy - 860) < 170))
    haut = np.clip(1 - (yy - 860) / 70, 0, 1) * 0.5 + 0.5
    cadre = np.zeros((H, W), F32)
    cadre[:860] = 1
    mix(img, hexc("#fffb96") * haut[..., None] + hexc("#ff71ce") * (1 - haut[..., None]), am * 0.9)
    # pyramide
    py = Toile()
    px, pb, ph = 2250, 600, 280
    py.poly([(px, pb - ph), (px - 150, pb), (px + 20, pb + 30)], 255)
    pm1 = py.a()
    py2 = Toile()
    py2.poly([(px, pb - ph), (px + 20, pb + 30), (px + 175, pb - 10)], 255)
    pm2 = py2.a()
    mix(img, hexc("#fffb96"), pm1)
    mix(img, hexc("#ff3fa8") * 0.75 + hexc("#2b1055") * 0.25, pm2)
    # mer : reflet retourné du ciel avec ondulation
    n = H - hz
    src = 2 * hz - np.arange(hz, H)
    refl = img[src].copy()
    dd = np.arange(n, dtype=F32)
    amp = 3 + 22 * np.clip(dd / 900, 0, 1)
    ph_ = dd / 9.0 + np.sin(dd / 41) * 3
    dx = (amp * np.sin(ph_) * np.clip(dd / 40, 0, 1)).astype(int)
    idx = (np.arange(W)[None, :] + dx[:, None]) % W
    refl = np.take_along_axis(refl, idx[..., None], 1)
    # rides : bandes claires et sombres, étirées à l'horizontale
    rides = _plein(fbm(W // 40, n // 3, rng, base=4, octaves=3), n, W) - 0.5
    rides = rides * (0.15 + 0.5 * np.clip(dd / 800, 0, 1))[:, None]
    teinte = hexc("#01cdfe") * 0.5 + hexc("#2b1055") * 0.5
    t = np.clip(dd / 1000, 0, 1)[:, None, None]
    refl = refl * (0.78 - 0.30 * t) + teinte[None, None, :] * (0.15 + 0.25 * t)
    refl = refl * (1 + rides[..., None] * 1.4)
    lointain = np.exp(-dd / 40)[:, None, None] * 0.5
    refl = refl * (1 - lointain) + hexc("#ffc2ea")[None, None, :] * lointain
    img[hz:] = np.clip(refl, 0, 1)
    img *= (1 - 0.28 * np.clip(np.hypot((xx - W / 2) / 2300, (yy - 1000) / 1700) - 0.6, 0, 1))[..., None]
    sauver3(img, "vaporwave-astres", grain=1.0, seed=342)


IMAGES = {
    "clair-neutre-collines": clair_neutre_formes,
    "clair-neutre-papier": clair_neutre_vagues,
    "gruvbox-ble": gruvbox_ble,
    "gruvbox-canyon": gruvbox_canyon,
    "vaporwave-colonnade": vaporwave_damier,
    "vaporwave-astres": vaporwave_mer,
    "kanagawa-brume": kanagawa_brume,
    "kanagawa-ressac": kanagawa_ressac,
    "brutaliste-facade": brutaliste_beton,
    "brutaliste-affiche": brutaliste_blocs,
    "pluie-verte-reseau": pluie_verte_horizon,
    "pluie-verte-couloir": pluie_verte_colonnes,
    "matrice-collines": matrice_relief,
    "matrice-planete": matrice_cercle,
    "cyberjaune-avenue": cyberjaune_ville,
    "cyberjaune-puces": cyberjaune_circuits,
}


if __name__ == "__main__":
    depot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if len(sys.argv) < 2 or os.path.commonpath([depot, os.path.abspath(sys.argv[1])]) == depot:
        sys.exit("usage : generer_fonds_3.py DOSSIER [nom...] (DOSSIER hors du dépôt)")
    ICI = os.path.abspath(sys.argv[1])
    noms = sys.argv[2:] or list(IMAGES)
    for nom in noms:
        if nom not in IMAGES:
            sys.exit("inconnu : %s (choix : %s)" % (nom, ", ".join(IMAGES)))
        t0 = time.time()
        IMAGES[nom]()
        print("%-22s %.1f s" % (nom, time.time() - t0), flush=True)
