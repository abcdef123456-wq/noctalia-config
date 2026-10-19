// Coordonnées Hyprland en points. Une topologie identique conserve exactement le rectangle d'origine.
function adapter(m, mx, my, mw, mh) {
    if (!(m.mw > 0 && m.mh > 0 && mw > 0 && mh > 0)) return m
    if (Math.abs(m.mx - mx) < 1 && Math.abs(m.my - my) < 1
            && Math.abs(m.mw - mw) < 1 && Math.abs(m.mh - mh) < 1) return m
    var e = Math.min(mw / m.mw, mh / m.mh)
    var w = Math.min(mw, m.w * e), h = Math.min(mh, m.h * e)
    return { x: mx + Math.max(0, Math.min(mw - w, (m.x - m.mx) * e)),
             y: my + Math.max(0, Math.min(mh - h, (m.y - m.my) * e)), w: w, h: h }
}
