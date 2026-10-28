// La liste de la fenêtre VPN, selon le filtre (VpnFiltres.qml) et la recherche :
//   - pays de l'application Mullvad (nc-vpn mullvad pays-json) : « Connecter » / « Changer » choisit le pays puis connecte ;
//   - profils de NetworkManager (VPN et WireGuard, importés ou créés à la main) : un clic connecte ;
//   - un fournisseur qui n'est pas prêt (Proton et Nord : bientôt ; Mullvad absent ou sans compte) : une carte d'état à la place
//     de la liste (VpnCarteFournisseur.qml), jamais un faux bouton.
// Pendant un partage d'écran : les profils s'appellent « Tunnel N », sans drapeau, et aucune ligne n'est marquée active.
// La liste défile (molette) au-delà de maxHauteur.
import QtQuick

Item {
    id: l
    signal connecterCompte(string id)
    property string filtre: "tous"
    property string recherche: ""
    property real maxHauteur: 300
    height: carteEtat ? carte.height : Math.min(maxHauteur, Math.max(vide.visible ? vide.implicitHeight : 0, colonne.implicitHeight))

    // L'onglet Proton ouvert : seul moment (avec la fin d'une connexion au compte) où `protonvpn info` est lancé (une fois par ouverture)
    onFiltreChanged: if (filtre === "proton") VpnEtat.verifierProton(false)
    Component.onCompleted: if (filtre === "proton") VpnEtat.verifierProton(false)
    readonly property var fiche: VpnEtat.fournisseurs.find(p => p.id === filtre) || null
    readonly property bool carteEtat: fiche !== null && (fiche.bientot || fiche.etat !== "pret")

    function lignes() {
        var q = recherche.trim().toLowerCase()
        var masque = VpnEtat.masque
        var mv = VpnEtat.mullvad
        var res = []
        var mullvadPret = VpnEtat.fournisseurs.some(p => p.id === "mullvad" && p.etat === "pret")
        if ((filtre === "tous" || filtre === "mullvad") && mullvadPret) {
            VpnEtat.mullvadPays.forEach(p => res.push({
                cle: "mullvad:" + p.cc, nom: p.nom, cc: p.cc, drapeau: VpnEtat.drapeauDe(p.cc), detail: "Mullvad · WireGuard",
                actif: !masque && mv.connecte && mv.pays === p.cc, changer: !masque && mv.connecte, mullvad: true, uuid: "" }))
        }
        VpnEtat.fournisseurs.forEach(p => {
            var x = VpnEtat.externe[p.id]
            if ((p.id !== "nord" && p.id !== "proton") || !x || p.etat !== "pret" || (filtre !== "tous" && filtre !== p.id)) return
            p.pays.forEach(q => res.push({ cle: p.id + ":" + q.cc, nom: q.nom, cc: q.cc, drapeau: VpnEtat.drapeauDe(q.cc), detail: p.fournisseur,
                actif: !masque && x.connecte && x.paysActif === q.cc, changer: !masque && x.connecte, mullvad: false, externe: p.id, uuid: "" }))
        })
        VpnEtat.connexions.forEach((c, i) => {
            var f = typeof c.fournisseur === "string" ? c.fournisseur : ""
            var ok = filtre === "tous" || (filtre === "perso" && f === "") || (filtre === "mullvad" && f === "Mullvad")
                     || (filtre === "cyberghost" && f === "CyberGhost")
            if (!ok) return
            res.push({ cle: c.uuid, nom: masque ? Reglages.t("Tunnel ", "Tunnel ") + (i + 1) : String(c.nom || ""),
                       cc: masque ? "" : (typeof c.pays === "string" ? c.pays : ""),
                       drapeau: masque ? "" : VpnEtat.drapeauDe(c.pays),
                       detail: (f !== "" && !masque ? f : Reglages.t("Profil", "Profile")) + " · " + (c.type === "wireguard" ? "WireGuard" : "VPN"),
                       actif: c.active === true, changer: !masque && c.active !== true && VpnEtat.actives.length > 0, mullvad: false, uuid: c.uuid })
        })
        if (q === "") return res
        return res.filter(x => (x.nom + " " + x.detail + " " + x.cc).toLowerCase().indexOf(q) >= 0)
    }
    readonly property var liste: lignes()

    VpnCarteFournisseur {
        id: carte
        objectName: "nc-vpn-carte-fournisseur"
        visible: l.carteEtat
        width: parent.width
        onConnecterCompte: id => l.connecterCompte(id)
        modele: l.fiche || ({ fournisseur: "", etat: "absent", bientot: false })
    }
    Texte {
        id: vide
        objectName: "nc-vpn-vide"
        visible: !l.carteEtat && l.liste.length === 0
        anchors.left: parent.left; anchors.right: parent.right
        wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
        text: l.recherche.trim() !== "" ? Reglages.t("Aucun résultat pour cette recherche.", "No result for this search.")
              : (l.filtre === "perso" || VpnEtat.connexions.length === 0 ? Reglages.t("Aucun profil. Importe un fichier .ovpn ou .conf (« Importer un profil »).", "No profile. Import an .ovpn or .conf file (\"Import a profile\").")
                                                                         : Reglages.t("Rien à afficher.", "Nothing to show."))
    }
    Flickable {
        objectName: "nc-vpn-liste"
        visible: !l.carteEtat && l.liste.length > 0
        anchors.fill: parent
        contentWidth: width; contentHeight: colonne.implicitHeight
        clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: colonne
            width: parent.width; spacing: 6
            Repeater {
                model: l.carteEtat ? [] : l.liste
                VpnRangee {
                    objectName: modelData.mullvad || modelData.externe ? "nc-vpn-pays" : "nc-vpn-autre"
                    width: colonne.width
                    nom: modelData.nom; drapeau: modelData.drapeau; detail: modelData.detail
                    actif: modelData.actif; changer: modelData.changer
                    occupe: VpnEtat.cible === (modelData.externe ? "ext:" + modelData.externe : (modelData.mullvad ? "mullvad" : modelData.uuid))
                    onClic: { if (modelData.externe) VpnEtat.fournisseurVers(modelData.externe, modelData.cc); else if (modelData.mullvad) VpnEtat.mullvadVers(modelData.cc); else VpnEtat.connecter(modelData.uuid) }
                }
            }
        }
    }
}
