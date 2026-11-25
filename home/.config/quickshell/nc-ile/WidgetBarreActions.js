.pragma library
.import Quickshell as Qs

// Intercepte uniquement le raccourci standard, pour transmettre l'écran et le bord du widget.
function lancerDepuisBarre(action, ouvrir) {
    if (typeof action === "string") {
        const match = /^exec\s+(\S+)\s+ile\s+([a-z]+)(?:\s+([a-z]+))?$/.exec(action.trim())
        if (match && match[1] === Qs.Quickshell.env("HOME") + "/.local/bin/nc-shell-msg" && ouvrir(match[2], match[3]))
            return true
    }
    return lancer(action)
}

// Les commandes sont celles de la configuration locale de la barre, jamais des données d'un widget.
function lancer(action) {
    if (typeof action !== "string" || !action.trim()) return false
    const texte = action.trim()
    if (texte === "none") return true
    if (/^exec\s/.test(texte)) {
        Qs.Quickshell.execDetached(["sh", "-c", texte.slice(5)])
        return true
    }
    // Pour l'IPC, prendre les arguments littéralement : jamais de deuxième interprétation par un shell.
    const mots = texte.replace(/^ipc\s+/, "").match(/(?:[^\s"'\\]|\\.|"[^"]*"|'[^']*')+/g)
    if (!mots || !/^[a-z][a-z0-9-]*$/.test(mots[0])) return false
    Qs.Quickshell.execDetached(["noctalia", "msg"].concat(mots.map(m =>
        m.replace(/"([^"]*)"|'([^']*)'|\\(.)/g, (_, d, s, e) => d ?? s ?? e))))
    return true
}
