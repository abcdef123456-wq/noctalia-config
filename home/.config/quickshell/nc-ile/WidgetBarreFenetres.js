.pragma library
.import Quickshell as Qs

function classe(fenetre) {
    const ipc = fenetre ? fenetre.lastIpcObject : null
    return ipc ? ipc.class || ipc.initialClass || "" : ""
}
function application(classe) {
    const nom = classe.replace(/\.desktop$/, "")
    return nom ? Qs.DesktopEntries.byId(nom) || Qs.DesktopEntries.heuristicLookup(nom) : null
}
function icone(nom, appli, symbolique = false) {
    const id = appli && appli.icon || nom.toLowerCase()
    if (id.startsWith("/")) return "file://" + id
    return (symbolique && id ? Qs.Quickshell.iconPath(id + "-symbolic", true) : "")
        || (id ? Qs.Quickshell.iconPath(id, true) : "") || Qs.Quickshell.iconPath("application-x-executable")
}
function titre(fenetre) { return fenetre ? fenetre.title || classe(fenetre) : "" }
function adresse(fenetre) {
    const a = fenetre ? String(fenetre.address) : ""
    return a.startsWith("0x") ? a : "0x" + a
}
function agir(bin, geste, fenetre) {
    if (!fenetre) return
    Qs.Quickshell.execDetached([bin + "nc-fenetre", geste, adresse(fenetre)])
}
function surEcran(fenetre, ecran) {
    const moniteur = fenetre.monitor || (fenetre.workspace ? fenetre.workspace.monitor : null)
    return !ecran || !!moniteur && moniteur.name === ecran.name
}
function position(fenetre) {
    const a = fenetre.lastIpcObject && fenetre.lastIpcObject.at
    return a ? a[0] * 10000 + a[1] : 0
}
