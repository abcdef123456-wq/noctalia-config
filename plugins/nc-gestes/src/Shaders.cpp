#include "Shaders.hpp"

#include <optional>
#include <string>

namespace {
    // Quadrilatère plein cadre : CShader crée le VAO dès qu'il trouve l'attribut « pos » (0..1).
    const std::string VERT = R"GLSL(#version 300 es
precision highp float;
in vec2 pos;
void main() {
    gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
}
)GLSL";

    // Toutes les grandeurs sont en pixels du moniteur, origine en haut à gauche, y vers le bas.
    // Le tampon de sortie suit la même orientation que la texture d'entrée : aucune inversion.
    const std::string FRAG = R"GLSL(#version 300 es
precision highp float;

uniform sampler2D tex;
uniform vec2  u_canvas;     // origine du tampon de sortie
uniform vec2  u_texOrigin;  // origine de la texture d'entrée
uniform vec2  u_texSize;    // taille de la texture d'entrée
uniform vec4  u_full;       // boîte complète de la fenêtre (bordure, ombre)
uniform vec4  u_inner;      // surface de la fenêtre, à sa place finale
uniform vec4  u_anchor;     // pilule de l'île
uniform float u_t;          // progression 0..1
uniform float u_scale;      // échelle du moniteur
uniform float u_radius;     // arrondi de la fenêtre
uniform int   u_mode;       // geste : 1 goutte, 2..14 voir geste()

uniform float u_pret;       // goutte : fondu du vrai contenu de la fenêtre, 0..1
uniform vec3  u_surface;    // goutte : surface de la pilule (Émail du thème)
uniform vec3  u_bord;       // goutte : accent du thème, pour le filet

out vec4 fragColor;

const float PI        = 3.14159265;
const float T_RUPTURE = 0.56; // la goutte se détache (maquette email-goutte.html : 0,54)

float sdBox(vec2 p, vec2 b, float r) {
    r = min(r, min(b.x, b.y));
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

// Union lisse (polynôme cubique) : le liquide se raccorde sans arête.
float smin(float a, float b, float k) {
    k = max(k, 1e-3);
    float h = max(k - abs(a - b), 0.0) / k;
    return min(a, b) - h * h * h * k / 6.0;
}

vec4 echantillon(vec2 px) {
    return texture(tex, (px - u_texOrigin) / u_texSize);
}

vec4 fenPx(vec2 px);

// Profil de goutte (capsule inégale) : cercle r1 à l'origine, cercle r2 à (0, h), y vers le haut. Exacte, donc un
// contour net à un pixel près quelle que soit la taille.
float sdGoutte(vec2 q, float r1, float r2, float h) {
    q.x     = abs(q.x);
    float b = (r1 - r2) / h;
    float a = sqrt(max(1.0 - b * b, 0.0));
    float k = dot(q, vec2(-b, a));
    if (k < 0.0)
        return length(q) - r1;
    if (k > a * h)
        return length(q - vec2(0.0, h)) - r2;
    return dot(q, vec2(a, b)) - r1;
}

// Col en sablier, vertical de y0 à y1 : demi-largeur a en haut, b en bas, w au pincement (à la fraction uw).
float sdCou(vec2 p, float x, float y0, float y1, float a, float b, float w, float uw) {
    float len = y1 - y0;
    if (len < 0.5)
        return 1e5;
    float u    = clamp((p.y - y0) / len, 0.0, 1.0);
    float demi = u < uw ? mix(a, w, smoothstep(0.0, 1.0, u / uw)) : mix(w, b, smoothstep(0.0, 1.0, (u - uw) / (1.0 - uw)));
    vec2  d    = vec2(abs(p.x - x) - demi, max(y0 - p.y, p.y - y1));
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

// Ressort amorti (dépassement d'environ 2,5 %, posé à x = 1).
float ressort(float x) {
    return 1.0 - exp(-7.0 * x) * (cos(6.0 * x) + 1.1667 * sin(6.0 * x));
}

// Corps de la goutte, posé par goutte() et relu pour l'ombre. Repère local : x de l'écran, y compté depuis le bord de
// l'île vers la fenêtre (la goutte pend toujours « vers le bas », même sous une pilule en bas d'écran).
vec2  gC;    // centre du grand cercle, puis de la fenêtre qui s'ouvre
float gR1;   // rayon du bulbe
float gRH;   // rayon du haut, côté col
float gH;    // écart des deux centres
vec2  gEt;   // étirement de la chute
vec2  gDemi; // demi-taille de la fenêtre qui s'ouvre
float gRR;   // son arrondi
float gM;    // 0 goutte -> 1 fenêtre

float corps(vec2 L) {
    vec2  q  = (L - gC) / gEt;
    float dG = sdGoutte(vec2(q.x, -q.y), gR1, gRH, gH) * min(gEt.x, gEt.y);
    if (gM <= 0.0)
        return dG;
    return mix(dG, sdBox(L - gC, gDemi, gRR), gM);
}

// 1 · Goutte (rose-aube) : une goutte de l'émail de l'île gonfle sous la pilule, pend à un col qui s'amincit en
// sablier, se pince et se détache (une gouttelette suit), tombe en s'étirant un peu, puis s'ouvre en fenêtre à sa place
// sur un ressort amorti. Le vrai contenu entre en fondu dès que l'appli l'a dessiné.
vec4 goutte(vec2 p, float t) {
    float s    = u_scale;
    vec2  iS   = max(u_inner.zw, vec2(1.0));
    float ww   = iS.x, wh = iS.y;
    vec2  winC = u_inner.xy + iS * 0.5;
    vec2  aC   = u_anchor.xy + u_anchor.zw * 0.5;

    // La goutte pend sous l'île, ou monte au-dessus si la pilule est en bas.
    float dir     = winC.y >= aC.y ? 1.0 : -1.0;
    float bordIle = dir > 0.0 ? u_anchor.y + u_anchor.w : u_anchor.y;
    vec2  L       = vec2(p.x, (p.y - bordIle) * dir);
    vec2  wC      = vec2(winC.x, (winC.y - bordIle) * dir);

    // Bulbe à la rupture : un tiers de la largeur, rond, jamais plus grand que la fenêtre.
    float R  = 0.5 * min(clamp(0.34 * ww, 80.0 * s, 320.0 * s), 0.6 * min(ww, wh));
    float Lc = clamp(0.55 * R, 22.0 * s, 80.0 * s); // col au plus long (maquette : un quart du bulbe)

    float g       = clamp(t / T_RUPTURE, 0.0, 1.0);
    float gonfle  = smoothstep(0.0, 0.85, g);
    float poids   = smoothstep(0.55, 1.0, g);
    float tension = pow(smoothstep(0.4, 1.0, g), 1.3);
    bool  casse   = t > T_RUPTURE;
    float f       = clamp((t - T_RUPTURE) / (1.0 - T_RUPTURE), 0.0, 1.0);
    float recul   = smoothstep(0.0, 0.22, f);   // la queue rentre dans la goutte, qui s'arrondit
    float xc      = clamp(f / 0.72, 0.0, 1.0);
    float chute   = xc * xc * (3.0 - 2.0 * xc);
    float xo      = clamp((f - 0.16) / 0.84, 0.0, 1.0);
    float ouvre   = ressort(xo);
    // La goutte, déjà ronde après le recul, devient une boîte arrondie (un disque) qui s'ouvre en fenêtre.
    gM            = casse ? smoothstep(0.0, 0.18, f) : 0.0;

    // Goutte suspendue : elle gonfle, puis s'alourdit (le haut s'affine, le col s'allonge). Après la rupture, valeurs
    // de la rupture (g = 1).
    float r1   = mix(4.0 * s, R, gonfle) * (1.0 + 0.04 * poids);
    float rH   = r1 * mix(0.6, 0.38, poids);
    float h    = r1 * mix(0.2, 0.55, poids);
    float col  = mix(4.0 * s, Lc, gonfle) * (1.0 + 0.35 * poids);
    float cBas = col + rH + h;
    if (casse) {
        rH = mix(rH, r1 * 0.9, recul);
        h  = mix(h, r1 * 0.12, recul);
    }
    gR1 = r1;
    gRH = rH;
    gH  = max(h, abs(r1 - rH) + 0.5);
    gC  = casse ? mix(vec2(aC.x, cBas), wC, chute) : vec2(aC.x, cBas);
    float et = 4.0 * xc * (1.0 - xc) * (1.0 - clamp(ouvre, 0.0, 1.0));
    gEt      = vec2(1.0 - 0.08 * et, 1.0 + 0.16 * et);
    gDemi    = mix(vec2(r1), iS * 0.5, ouvre) * gEt;
    gRR      = mix(min(gDemi.x, gDemi.y), u_radius, smoothstep(0.0, 0.7, clamp(ouvre, 0.0, 1.0)));

    float dCorps = corps(L);

    // Collerette sous la pilule (cachée par l'île, l'île est au-dessus des fenêtres), col, restes de la rupture.
    float capDemi = clamp(u_anchor.z * 0.5 - u_anchor.w * 0.5, 2.0 * s, 30.0 * s) * (0.7 + 0.3 * gonfle);
    float d, dEclats = 1e5;
    if (!casse) {
        // Col en sablier : large contre la pilule, il s'évase dans l'épaule du bulbe et se pince entre les deux.
        float a      = min(u_anchor.z * 0.2, 26.0 * s) * mix(1.0, 0.55, tension);
        float b      = rH * mix(0.9, 0.7, tension);
        float taille = mix(min(a, b) * 0.6, 0.35, tension); // jusqu'à un fil d'un demi-pixel avant de céder
        float dCou   = sdCou(L, aC.x, -6.0 * s, col + rH * 0.6, a, b, taille, 0.6);
        float dCap   = sdBox(L - vec2(aC.x, -8.0 * s), vec2(capDemi, 6.0 * s), 6.0 * s);
        d            = smin(smin(dCorps, dCou, mix(28.0, 8.0, tension) * s), dCap, 12.0 * s);
    } else {
        float reste = 1.0 - smoothstep(0.0, 0.15, f);
        float dCap  = sdBox(L - vec2(aC.x, -8.0 * s), vec2(capDemi * mix(1.0, 0.6, recul), 6.0 * s), 6.0 * s);
        float bout  = col * 0.2 * reste; // ménisque qui remonte dans la pilule
        float dBout = reste > 0.01 ? length(L - vec2(aC.x, clamp(L.y, -6.0 * s, bout))) - 5.0 * s * reste : 1e5;
        // Gouttelette née au pincement, qui suit plus lentement et se résorbe.
        float rs   = max(r1 * 0.035, 2.5 * s) * (1.0 - smoothstep(0.25, 0.6, f));
        vec2  cs   = vec2(mix(aC.x, gC.x, 0.5 * chute), -6.0 * s + 0.6 * (col + 0.23 * r1 + 6.0 * s) + (gC.y - cBas) * 0.5);
        float dSat = rs > 0.2 ? length(L - cs) - rs : 1e5;
        dEclats    = min(dSat, smin(dCap, dBout, 6.0 * s));
        d          = min(dCorps, dEclats);
    }

    float M  = 1.0 - smoothstep(-0.5, 0.5, d);      // anticrénelage sur un pixel physique
    float Mc = 1.0 - smoothstep(-0.5, 0.5, dCorps);

    // Émail : la surface de la pilule, teintée de l'accent (un peu plus sur un thème sombre, où elle se fondrait dans le
    // fond), une lumière douce en haut (comme l'île fermée).
    bool  sombre = dot(u_surface, vec3(0.299, 0.587, 0.114)) < 0.5;
    vec3  S      = mix(u_surface, u_bord, sombre ? 0.14 : 0.08);
    float haut   = gC.y - mix(gH + gRH, gDemi.y, gM);
    float rel    = clamp((L.y - haut) / max(mix(gH + gRH + gR1, 2.0 * gDemi.y, gM), 1.0), 0.0, 1.0);
    vec3  c      = mix(S, vec3(1.0), (sombre ? 0.12 : 0.3) * (1.0 - smoothstep(0.0, 0.6, rel)));
    // Ménisque et gouttelette, trop petits pour un filet : plus soutenus pour rester visibles.
    c            = mix(c, mix(S, u_bord, 0.5), (1.0 - smoothstep(-0.5, 0.5, dEclats)) * (1.0 - Mc));

    // Vrai contenu, une fois dessiné par l'appli : dans la goutte qui tombe, sans déformation (il la couvre, sans
    // bordure), puis exact quand la fenêtre se pose.
    float cyL  = mix(gC.y + 0.5 * (gR1 - gH - gRH) * gEt.y, gC.y, gM);
    vec2  ech  = mix(vec2(gR1, 0.5 * (gH + gRH + gR1)) * gEt, gDemi, gM) / (iS * 0.5);
    vec2  cR   = vec2(gC.x, bordIle + dir * cyL);
    vec2  q    = (p - cR) / mix(vec2(max(ech.x, ech.y)), ech, smoothstep(0.5, 1.0, clamp(ouvre, 0.0, 1.0))) + winC;
    vec4  cw   = fenPx(clamp(q, u_inner.xy + 1.0, u_inner.xy + iS - 1.0));
    float cA   = u_pret * smoothstep(T_RUPTURE - 0.1, T_RUPTURE + 0.12, t) * Mc;
    c          = c * (1.0 - cA * cw.a) + cA * cw.rgb;

    // Filet fin de l'accent et reflet en haut : la goutte se lit sur un thème clair comme sur un sombre. Ils s'effacent
    // quand la fenêtre se pose.
    float arete  = 1.0 - smoothstep(0.8, 0.95, t);
    float filet  = 1.0 - smoothstep(0.6 * s, 1.4 * s, -(casse ? dCorps : d));
    c            = mix(c, mix(S, u_bord, sombre ? 0.8 : 0.7), filet * (sombre ? 0.85 : 0.6) * arete);
    float bande  = smoothstep(1.0 * s, 1.8 * s, -dCorps) * (1.0 - smoothstep(2.0 * s, 3.0 * s, -dCorps));
    c            = mix(c, mix(S, vec3(1.0), sombre ? 0.4 : 0.85), bande * (1.0 - smoothstep(0.0, 0.3, rel)) * 0.8 * arete);

    // Ombre douce du corps, vers le bas de l'écran.
    vec2  pO    = p - vec2(0.0, 8.0 * s);
    float dO    = corps(vec2(pO.x, (pO.y - bordIle) * dir));
    float ombre = (sombre ? 0.32 : 0.22) * (1.0 - smoothstep(-6.0 * s, 20.0 * s, dO)) * clamp(r1 / (20.0 * s), 0.0, 1.0) * arete;

    vec4 res = vec4(c, 1.0) * M + vec4(0.0, 0.0, 0.0, ombre) * (1.0 - M); // alpha prémultiplié
    // Fin : la vraie fenêtre (bordure et ombre comprises), au pixel près.
    return mix(res, fenPx(p), smoothstep(0.86, 1.0, t));
}

// ---- Gestes 2 à 14 : la fenêtre reste dans son cadre ----

float eo(float x) {
    x = clamp(x, 0.0, 1.0);
    return 1.0 - pow(1.0 - x, 3.0);
}

float segment(vec2 p, vec2 a, vec2 b) {
    vec2  pa = p - a, ba = b - a;
    float h  = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-4), 0.0, 1.0);
    return length(pa - ba * h);
}

float hash(float n) {
    return fract(sin(n * 12.9898) * 43758.5453);
}

float bayer4(vec2 cellule) {
    int m[16] = int[16](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
    return float(m[int(mod(cellule.y, 4.0)) * 4 + int(mod(cellule.x, 4.0))]);
}

// Fenêtre (bordure et ombre comprises) au pixel px, transparente hors de sa boîte complète.
vec4 fenPx(vec2 px) {
    if (any(lessThan(px, u_full.xy)) || any(greaterThan(px, u_full.xy + u_full.zw)))
        return vec4(0.0);
    return echantillon(px);
}

// Même chose en coordonnées normalisées de la surface (0..1 = la surface, au-delà : bordure et ombre).
vec4 fen(vec2 q) {
    return fenPx(u_inner.xy + q * max(u_inner.zw, vec2(1.0)));
}

// Teinte une couleur prémultipliée sans toucher à son alpha (ni le dépasser).
vec4 teinte(vec4 c, float f) {
    return vec4(min(c.rgb * f, vec3(c.a)), c.a);
}

// ---- Finition commune (même niveau que la goutte) ----

// Couverture d'une distance signée en pixels physiques, sur un pixel : contour net, sans crénelage.
float couvre(float d) {
    return 1.0 - smoothstep(-0.5, 0.5, d);
}

bool themeSombre() {
    return dot(u_surface, vec3(0.299, 0.587, 0.114)) < 0.5;
}

// Émail du thème : la surface de la pilule, teintée de l'accent (un peu plus sur un thème sombre).
vec3 email() {
    return mix(u_surface, u_bord, themeSombre() ? 0.14 : 0.08);
}

// Accent de l'île, opaque, pondéré (prémultiplié) : filets et traits des gestes.
vec4 trait(float a) {
    return vec4(u_bord, 1.0) * a;
}

// Pose b (prémultiplié) par-dessus a.
vec4 sur(vec4 a, vec4 b) {
    return b + a * (1.0 - b.a);
}

// Carte d'émail à la place de la surface (q normalisé : 0..1 = la surface) : ce que montre un geste tant que l'appli
// n'a rien dessiné. Arrondi de la fenêtre, lumière douce en haut, filet de l'accent.
vec4 carte(vec2 q) {
    vec2  iS     = max(u_inner.zw, vec2(1.0));
    float d      = sdBox((q - 0.5) * iS, iS * 0.5, u_radius);
    bool  sombre = themeSombre();
    vec3  c      = mix(email(), vec3(1.0), (sombre ? 0.12 : 0.3) * (1.0 - smoothstep(0.0, 0.5, q.y)));
    float filet  = 1.0 - smoothstep(0.6 * u_scale, 1.4 * u_scale, -d);
    c            = mix(c, mix(email(), u_bord, sombre ? 0.8 : 0.7), filet * (sombre ? 0.85 : 0.6));
    return vec4(c, 1.0) * couvre(d);
}

// Ce que montre un geste en q : la carte d'émail, puis le vrai contenu (bordure et ombre comprises) en fondu dès que
// l'appli l'a dessiné.
vec4 matiere(vec2 q) {
    return mix(carte(q), fen(q), u_pret);
}

vec4 matierePx(vec2 px) {
    return matiere((px - u_inner.xy) / max(u_inner.zw, vec2(1.0)));
}

vec4 geste(int mode, vec2 p, float t) {
    float s    = u_scale;
    vec2  iS   = max(u_inner.zw, vec2(1.0));
    vec2  q    = (p - u_inner.xy) / iS;
    vec2  pi   = p - u_inner.xy;
    vec2  winC = u_inner.xy + iS * 0.5;
    float e    = eo(t);
    float apparait = smoothstep(0.0, 0.18, t);
    float efface   = 1.0 - smoothstep(0.75, 1.0, t); // les traits de l'accent s'en vont avant la fin

    if (mode == 2) {
        // Paravent (sakura) : un paravent japonais de quatre panneaux, replié en zigzag, se déplie à plat. Chaque panneau
        // garde son morceau de fenêtre ; ceux tournés vers l'ombre sont plus sombres, et l'arête qui vient vers nous est
        // un peu plus haute. Filet de l'accent dans les plis tant qu'ils existent.
        float th   = (1.0 - e) * 1.35;
        float W    = iS.x * cos(th);
        float x    = (p.x - (winC.x - 0.5 * W)) / max(W, 1e-3);
        float k    = clamp(floor(x * 4.0), 0.0, 3.0);
        float u    = clamp(x * 4.0 - k, 0.0, 1.0);
        bool  pair = mod(k, 2.0) < 0.5;
        float hs   = 1.0 + 0.1 * sin(th) * (pair ? u : 1.0 - u);
        float m    = couvre(max((abs(x - 0.5) - 0.5) * W, abs(p.y - winC.y) - 0.5 * iS.y * hs));
        vec4  col  = matiere(vec2(x, 0.5 + (p.y - winC.y) / (iS.y * hs)));
        col        = teinte(col, 1.0 - (pair ? 0.08 : 0.42) * sin(th)) * m;
        float pli  = abs(x * 4.0 - floor(x * 4.0 + 0.5)) * W / 4.0;
        float dans = step(0.5, x * 4.0) * step(x * 4.0, 3.5);
        return sur(col, trait(0.8 * couvre(pli - 0.5 * s) * dans * sin(th) * m)) * apparait;
    }
    if (mode == 3) {
        // Plan de coupe (solarized-clair) : deux repères de coupe en L, qui dépassent du cadre comme sur une épreuve,
        // tracent le cadre ; puis le contenu le remplit en diagonale, derrière un front fin.
        float lp  = eo(t / 0.5);
        vec2  a   = u_inner.xy, b = u_inner.xy + iS;
        float deb = 10.0 * s;
        float dl  = min(min(segment(p, a - vec2(deb, 0.0), a + vec2(lp * iS.x, 0.0)), segment(p, a - vec2(0.0, deb), a + vec2(0.0, lp * iS.y))),
                        min(segment(p, b + vec2(deb, 0.0), b - vec2(lp * iS.x, 0.0)), segment(p, b + vec2(0.0, deb), b - vec2(0.0, lp * iS.y))));
        float rep = couvre(dl - 0.5 * s) * smoothstep(0.0, 0.06, t) * efface;
        float f   = smoothstep(0.36, 0.95, t);
        float dd  = ((pi.x + pi.y) - f * (iS.x + iS.y) * 1.02) * 0.7071;
        vec4  col = matiere(q) * couvre(dd);
        float front = couvre(abs(dd) - 0.5 * s) * step(0.001, f) * (1.0 - f) * couvre(sdBox(p - winC, iS * 0.5, u_radius));
        return sur(sur(col, trait(front)), trait(rep));
    }
    if (mode == 4) {
        // Horizon (nord) : une ligne d'horizon froide s'étend au bord bas, la fenêtre remonte de derrière elle.
        float ligne = u_inner.y + iS.y;
        vec4  col   = matierePx(p - vec2(0.0, (1.0 - e) * 0.5 * iS.y)) * couvre(p.y - ligne) * apparait;
        float large = 0.5 * iS.x * mix(0.25, 1.0, eo(t / 0.3));
        float dansX = couvre(abs(p.x - winC.x) - large);
        float lueur = exp(-max(ligne - p.y, 0.0) / (16.0 * s)) * 0.3 * (1.0 - e) * step(p.y, ligne) * dansX;
        float trace = couvre(abs(p.y - ligne) - 0.5 * s) * dansX * efface;
        return sur(sur(col, trait(lueur)), trait(trace));
    }
    if (mode == 5) {
        // Marée (ocean) : une ligne d'eau ondulante monte, ourlée d'écume, et découvre le contenu ; juste sous elle,
        // l'eau teinte encore un peu la fenêtre.
        float niveau = mix(1.06, -0.06, e);
        float vague  = (0.018 * sin(q.x * 9.0 + t * 7.0) + 0.007 * sin(q.x * 23.0 - t * 11.0)) * (1.0 - e);
        float dpx    = (niveau + vague - q.y) * iS.y;
        vec4  col    = matiere(q) * couvre(dpx);
        float prof   = clamp(-dpx / (28.0 * s), 0.0, 1.0);
        col          = vec4(mix(col.rgb, u_bord * col.a, 0.3 * (1.0 - prof) * (1.0 - e)), col.a);
        float ecume  = couvre(abs(dpx) - 0.75 * s) * couvre(abs(p.x - winC.x) - 0.5 * iS.x) * efface;
        return sur(col, trait(ecume));
    }
    if (mode == 6) {
        // Éventail (everforest) : cinq lames de la fenêtre, refermées l'une sur l'autre au milieu, pivotent autour du
        // milieu du bord bas et s'écartent jusqu'à leur place ; filet de l'accent sur leurs arêtes tant qu'elles bougent.
        vec2  P   = vec2(winC.x, u_inner.y + iS.y);
        vec2  v   = p - P;
        float lw  = iS.x / 5.0;
        vec4  res = vec4(0.0);
        for (int j = 0; j < 5; ++j) {
            // Les lames extérieures d'abord : celle du milieu reste par-dessus.
            float fk  = j == 0 ? 0.0 : (j == 1 ? 4.0 : (j == 2 ? 1.0 : (j == 3 ? 3.0 : 2.0)));
            vec2  c   = vec2(u_inner.x + (fk + 0.5) * lw, winC.y);
            float a   = -(1.0 - e) * atan(c.x - P.x, P.y - c.y);
            float ca  = cos(a), sa = sin(a);
            vec2  src = P + vec2(v.x * ca + v.y * sa, -v.x * sa + v.y * ca);
            float d   = sdBox(src - c, vec2(0.5 * lw, 0.5 * iS.y), 0.0);
            vec4  col = teinte(matierePx(src), 1.0 - 0.35 * abs(a)) * couvre(d);
            res       = sur(res, sur(col, trait(couvre(abs(d) - 0.5 * s) * (1.0 - e))));
        }
        return res * apparait;
    }
    if (mode == 7) {
        // Rideau (catppuccin) : deux pans de velours plissé, teints de l'accent, s'ouvrent depuis le milieu et se
        // rassemblent sur les côtés ; la fenêtre est derrière.
        float demi  = 0.5 * iS.x;
        float ax    = abs(p.x - winC.x);
        float bord  = demi * e + 3.0 * s * sin(q.y * 11.0) * (1.0 - e);
        float u     = clamp((ax - bord) / max(demi - bord, 1.0), 0.0, 1.0);
        float pli   = 0.5 + 0.5 * cos(u * PI * mix(16.0, 7.0, e));
        vec3  velours = mix(email(), u_bord, themeSombre() ? 0.45 : 0.3) * mix(0.8, 1.04, pli) * mix(0.85, 1.0, u);
        float cm    = couvre(bord - ax) * couvre(sdBox(p - winC, iS * 0.5, u_radius)) * (1.0 - smoothstep(0.7, 1.0, t));
        vec4  win   = matiere(q);
        return sur(win, vec4(velours, 1.0) * cm) * apparait;
    }
    if (mode == 8) {
        // Ligne cathodique (vaporwave) : un trait de l'accent s'étire, entouré d'une lueur, puis s'ouvre en écran ;
        // des lignes de balayage s'estompent. Aucun éclair blanc.
        float wl  = eo(t / 0.32);
        float hp  = eo((t - 0.32) / 0.68);
        float hh  = mix(1.0 * s, 0.5 * iS.y, hp);
        float hw  = 0.5 * iS.x * wl;
        float m   = couvre(max(abs(p.x - winC.x) - hw, abs(p.y - winC.y) - hh));
        float hf  = max(hh / (0.5 * iS.y), 1e-4);
        float scan = 1.0 - 0.22 * (1.0 - hp) * (0.5 + 0.5 * sin(p.y * PI / (1.5 * s)));
        vec4  col = teinte(matiere(vec2(q.x, 0.5 + (q.y - 0.5) / hf)), scan);
        col       = mix(col, trait(1.0), 0.85 * (1.0 - smoothstep(0.0, 0.3, hp))) * m;
        float lueur = exp(-abs(p.y - winC.y) / (7.0 * s)) * 0.4 * (1.0 - hp) * couvre(abs(p.x - winC.x) - hw);
        return sur(trait(lueur), col);
    }
    if (mode == 9) {
        // Point de fuite (synthwave) : la fenêtre avance depuis une ligne d'horizon, en perspective qui se redresse.
        float yh  = u_inner.y + 0.12 * iS.y;
        float sc  = mix(0.16, 1.0, e);
        vec2  c   = mix(vec2(winC.x, yh + 0.5 * 0.16 * iS.y), winC, e);
        float top = c.y - 0.5 * sc * iS.y;
        float ny  = (p.y - top) / (sc * iS.y);
        float wf  = mix(mix(0.55, 1.0, e), 1.0, clamp(ny, 0.0, 1.0));
        float nx  = 0.5 + (p.x - c.x) / (sc * iS.x * wf);
        float m   = couvre(max((abs(nx - 0.5) - 0.5) * sc * iS.x * wf, (abs(ny - 0.5) - 0.5) * sc * iS.y));
        vec4  col = matiere(vec2(nx, ny)) * m * apparait;
        float hz  = couvre(abs(p.y - yh) - 0.5 * s) * couvre(abs(p.x - winC.x) - 0.5 * iS.x * mix(0.3, 1.0, eo(t / 0.25))) *
                   (1.0 - smoothstep(0.35, 0.8, t));
        return sur(trait(hz), col);
    }
    if (mode == 10) {
        // Vantaux (dracula) : deux battants d'émail moulurés ferment la fenêtre, puis pivotent sur leurs gonds
        // extérieurs ; leur bord libre vient vers nous. La fenêtre sort de l'ombre derrière eux.
        float th  = e * 0.5 * PI;
        float lw  = 0.5 * iS.x * cos(th);
        bool  g   = p.x < winC.x;
        float dx  = abs(p.x - (g ? u_inner.x : u_inner.x + iS.x));
        float u   = clamp(dx / max(lw, 1e-3), 0.0, 1.0);
        float hs  = 1.0 + 0.08 * sin(th) * u;
        float dB  = max(dx - lw, abs(p.y - winC.y) - 0.5 * iS.y * hs);
        float bm  = couvre(dB) * (1.0 - smoothstep(0.85, 1.0, t));
        vec3  bat = mix(email(), u_bord, 0.22) * (1.0 - 0.45 * sin(th) * u);
        float moulure = couvre(abs(dB + 12.0 * s) - 0.5 * s);
        vec4  bv  = sur(vec4(bat, 1.0), trait(0.55 * moulure)) * bm;
        vec4  win = teinte(matiere(q), mix(0.55, 1.0, e));
        return sur(win, bv) * apparait;
    }
    if (mode == 11) {
        // Balayage (matrice) : un front tramé (Bayer 4 × 4, cellules alignées sur les pixels) révèle la fenêtre de
        // gauche à droite ; les cellules qui viennent d'apparaître luisent de l'accent.
        float cell  = max(floor(4.0 * s + 0.5), 1.0);
        float bande = 16.0 * cell / iS.x;
        float front = smoothstep(0.0, 1.0, t) * (1.0 + 2.0 * bande) - bande;
        float u     = (front - q.x) / bande;
        float seuil = (bayer4(floor(pi / cell)) + 0.5) / 16.0;
        float m     = u >= 1.0 ? 1.0 : (u <= 0.0 ? 0.0 : step(seuil, u));
        vec4  col   = matiere(q) * m;
        float tete  = m * (1.0 - smoothstep(0.0, 0.6, u)) * step(0.0, u);
        return mix(col, trait(col.a), 0.65 * tete);
    }
    if (mode == 12) {
        // Averse (pluie-verte) : lignes révélées de haut en bas par colonnes décalées ; la ligne de tête de chaque
        // colonne luit de l'accent.
        float ligne = max(floor(18.0 * s + 0.5), 1.0);
        float colw  = max(floor(36.0 * s + 0.5), 1.0);
        float r     = floor(pi.y / ligne);
        float n     = max(ceil(iS.y / ligne), 1.0);
        float pc    = clamp((t - hash(floor(pi.x / colw)) * 0.15) / 0.85, 0.0, 1.0);
        float front = pc * (n + 1.0);
        float m     = step(r + 1.0, front);
        float tete  = m * step(front, r + 2.0);
        vec4  col   = matiere(q) * m;
        return mix(col, trait(col.a), 0.6 * tete * efface);
    }
    if (mode == 13) {
        // Deux paliers (retro) : une bande s'élargit, puis s'étend en hauteur, par crans, dans un cadre phosphore.
        float w   = mix(1.0 / 12.0, 1.0, floor(eo(t / 0.42) * 6.0) / 6.0);
        float h   = mix(0.12, 1.0, floor(eo((t - 0.45) / 0.55) * 6.0) / 6.0);
        vec2  hw  = vec2(w, h) * 0.5 * iS;
        float d   = sdBox(p - winC, hw, min(u_radius, min(hw.x, hw.y)));
        vec4  col = matiere(q) * couvre(d);
        float cadre = couvre(abs(d) - 0.5 * s) * efface;
        return sur(col, trait(cadre));
    }
    if (mode == 14) {
        // Contour (oled) : le filet de l'accent fait le tour depuis le haut, puis le contenu apparaît dedans.
        float d     = sdBox(p - winC, iS * 0.5, u_radius);
        float a     = abs(atan(p.x - winC.x, -(p.y - winC.y))) / PI;
        float trace = couvre(abs(d) - 0.5 * s) * step(a, eo(t / 0.48)) * efface;
        vec4  col   = matiere(q) * smoothstep(0.35, 1.0, t);
        return sur(col, trait(trace));
    }
    return fen(q);
}

void main() {
    vec2  p = u_canvas + gl_FragCoord.xy;
    float t = clamp(u_t, 0.0, 1.0);
    vec4  g = u_mode == 1 ? goutte(p, t) : geste(u_mode, p, t);
    // Gestes 2 à 14 : fin en fondu sur la vraie fenêtre, au pixel près (la goutte le fait déjà).
    fragColor = u_mode == 1 ? g : mix(g, fenPx(p), smoothstep(0.88, 1.0, t));
}
)GLSL";

    std::optional<NcGestes::SGesteShader> g_geste;
    bool                                  g_failed = false;
}

NcGestes::SGesteShader* NcGestes::gesteShader() {
    if (g_geste)
        return &*g_geste;
    if (g_failed)
        return nullptr;

    SGesteShader s;
    s.shader = makeShared<CShader>();
    // dynamic = true : un échec de compilation rend false au lieu d'arrêter Hyprland.
    if (!s.shader->createProgram(VERT, FRAG, true)) {
        g_failed = true;
        return nullptr;
    }

    const auto PROG = s.shader->program();
    s.tex           = glGetUniformLocation(PROG, "tex");
    s.canvas        = glGetUniformLocation(PROG, "u_canvas");
    s.texOrigin     = glGetUniformLocation(PROG, "u_texOrigin");
    s.texSize       = glGetUniformLocation(PROG, "u_texSize");
    s.full          = glGetUniformLocation(PROG, "u_full");
    s.inner         = glGetUniformLocation(PROG, "u_inner");
    s.anchor        = glGetUniformLocation(PROG, "u_anchor");
    s.t             = glGetUniformLocation(PROG, "u_t");
    s.scale         = glGetUniformLocation(PROG, "u_scale");
    s.radius        = glGetUniformLocation(PROG, "u_radius");
    s.mode          = glGetUniformLocation(PROG, "u_mode");
    s.pret          = glGetUniformLocation(PROG, "u_pret");
    s.surface       = glGetUniformLocation(PROG, "u_surface");
    s.bord          = glGetUniformLocation(PROG, "u_bord");
    g_geste         = std::move(s);
    return &*g_geste;
}

bool NcGestes::gesteShaderFailed() {
    return g_failed;
}

void NcGestes::destroyShaders() {
    g_geste.reset();
    g_failed = false;
}
