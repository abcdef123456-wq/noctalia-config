// Débits du panneau VPN : la somme des débits reçus (↓) et envoyés (↑) des interfaces des tunnels montés, en octets par seconde,
// calculés sur l'intervalle entre deux relevés d'une seconde des compteurs du noyau (VpnCompteur.qml). Le relevé ne tourne que si
// « actif » : fenêtre ouverte ET écran allumé (Vpn.qml le lie à VpnEtat.panneauOuvert et Etat.ecranVu) ; sinon aucun Timer ne tourne
// et tout est remis à zéro. Il tient aussi l'heure (VpnEtat.maintenant) pour la durée de connexion.
// bas / haut : -1 = pas encore mesuré ou indisponible (aucune interface lisible, compteur remis à zéro) ; « mesure » dit lequel.
import QtQuick

Item {
    id: d
    property var interfaces: []                   // noms d'interfaces des tunnels montés
    property bool actif: false
    property real bas: -1                         // octets reçus par seconde
    property real haut: -1                        // octets envoyés par seconde
    property int tics: 0                          // nombre de relevés faits depuis la création (les tests s'en servent)
    readonly property bool mesure: tics >= 3 || bas >= 0
    visible: false

    property real precRx: -1
    property real precTx: -1
    property int precN: 0
    property real precT: 0

    function remettre() { bas = -1; haut = -1; precRx = -1; precTx = -1; precN = 0; precT = 0 }
    onActifChanged: if (!actif) remettre()
    onInterfacesChanged: remettre()

    function pas() {
        tics++
        var t = Date.now()
        VpnEtat.maintenant = t / 1000
        var rx = 0, tx = 0, n = 0
        for (var i = 0; i < compteurs.count; i++) {
            var c = compteurs.itemAt(i)
            if (c && c.rx >= 0 && c.tx >= 0) { rx += c.rx; tx += c.tx; n++ }
        }
        if (n > 0 && n === precN && precT > 0 && rx >= precRx && tx >= precTx && t > precT) {
            var dt = (t - precT) / 1000
            bas = (rx - precRx) / dt
            haut = (tx - precTx) / dt
        } else { bas = -1; haut = -1 }
        precRx = rx; precTx = tx; precN = n; precT = n > 0 ? t : 0
        for (var j = 0; j < compteurs.count; j++) { var k = compteurs.itemAt(j); if (k) k.recharger() }
    }

    Repeater {
        id: compteurs
        model: d.actif ? d.interfaces : []
        VpnCompteur { interfaceNom: modelData }
    }
    Timer { interval: 1000; repeat: true; running: d.actif; triggeredOnStart: true; onTriggered: d.pas() }
}
