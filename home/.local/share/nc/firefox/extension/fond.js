// Couleurs de l'île : l'hôte natif nc_firefox (le script nc-firefox lancé par Firefox) envoie la palette du fond
// d'écran (~/.config/nc/palette-ile.json) au démarrage et à chaque changement ; le thème de Firefox est mis à jour
// aussitôt (browser.theme.update), sans relancer. Si l'hôte manque, nouvel essai toutes les 15 s ; l'extension
// désactivée ou retirée, Firefox revient au thème d'avant tout seul.
// Les thèmes choisis dans Firefox restent prioritaires : les couleurs ne s'appliquent que sur le thème « Système »
// et sur Sombre ou Clair quand il est du même côté que le fond d'écran ; tout autre thème (Alpenglow, un thème
// installé) est laissé tel quel, et l'extension revient dès qu'un thème de base est repris.
"use strict";

const HOTE = "nc_firefox";
const SYSTEME = "default-theme@mozilla.org";
const SOMBRE = "firefox-compact-dark@mozilla.org";
const CLAIR = "firefox-compact-light@mozilla.org";
let port = null;
let palette = null;

async function themeActif() {
  const tous = await browser.management.getAll();
  const t = tous.find((e) => e.type === "theme" && e.enabled);
  return t ? t.id : SYSTEME;
}

async function appliquer() {
  if (!palette) return;
  const actif = await themeActif();
  const sombre = palette.sombre !== false;
  if (actif === SYSTEME || actif === (sombre ? SOMBRE : CLAIR)) browser.theme.update(theme(palette));
  else browser.theme.reset();
}

browser.management.onEnabled.addListener((e) => { if (e.type === "theme") appliquer(); });
browser.management.onDisabled.addListener((e) => { if (e.type === "theme") appliquer(); });

function couleur(p, cle, sinon) {
  const v = p[cle];
  return typeof v === "string" && /^#[0-9a-fA-F]{6}$/.test(v) ? v : sinon;
}

// Mélange de deux couleurs #rrggbb : t = part de b (0 à 1)
function melange(a, b, t) {
  const h = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  const [x, y] = [h(a), h(b)];
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

function theme(p) {
  const fond = couleur(p, "fond", "#1c1b22");
  const texte = couleur(p, "texte", "#fbfbfe");
  const texteSec = couleur(p, "texteSec", texte);
  const carte = couleur(p, "carte", fond);
  const carteSurvol = couleur(p, "carteSurvol", carte);
  const accent = couleur(p, "accent", "#8a8a8a");
  const surAccent = couleur(p, "surAccent", fond);
  const sombre = p.sombre !== false;
  return {
    colors: {
      frame: fond, frame_inactive: fond, toolbar: fond, toolbar_text: texte,
      tab_selected: melange(fond, texte, 0.16), tab_text: texte, tab_background_text: texteSec, tab_line: accent,
      toolbar_field: carte, toolbar_field_text: texte, toolbar_field_focus: carte, toolbar_field_text_focus: texte,
      toolbar_field_border: fond, toolbar_field_border_focus: accent,
      toolbar_field_highlight: accent, toolbar_field_highlight_text: surAccent,
      popup: fond, popup_text: texte, popup_border: carteSurvol, popup_highlight: melange(fond, texte, 0.18), popup_highlight_text: texte,
      sidebar: fond, sidebar_text: texte, sidebar_border: carte, sidebar_highlight: carteSurvol, sidebar_highlight_text: texte,
      ntp_background: fond, ntp_text: texte, icons: texte, icons_attention: accent,
      button_background_hover: carte, button_background_active: carteSurvol,
      toolbar_bottom_separator: fond, toolbar_top_separator: fond, toolbar_vertical_separator: fond,
    },
    properties: { color_scheme: sombre ? "dark" : "light", content_color_scheme: "auto" },
  };
}

function connecter() {
  try {
    port = browser.runtime.connectNative(HOTE);
  } catch (e) {
    setTimeout(connecter, 15000);
    return;
  }
  port.onMessage.addListener((m) => {
    if (m && typeof m === "object" && m.palette) {
      palette = m.palette;
      appliquer();
    }
  });
  port.onDisconnect.addListener(() => {
    port = null;
    setTimeout(connecter, 15000);
  });
  port.postMessage({ demande: "couleurs" });
}

connecter();
