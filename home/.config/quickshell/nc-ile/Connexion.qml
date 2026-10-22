pragma Singleton
// Connexion à internet, lue par NetworkManager (Quickshell.Networking) : sans elle, l'IA disparaît de l'île.
// Ce module est facultatif dans Quickshell (compilé sans, par exemple une ancienne installation Debian) : il est chargé
// ici à part, et s'il manque, l'île démarre quand même et suppose qu'on est en ligne (avant, toute l'île plantait).

import QtQuick
import Quickshell

Singleton {
    id: c
    property var sonde: null
    readonly property bool enLigne: sonde ? sonde.enLigne : true
    readonly property bool disponible: sonde !== null

    Component.onCompleted: {
        try {
            sonde = Qt.createQmlObject("import QtQuick; import Quickshell.Networking; QtObject { readonly property bool enLigne: "
                + "Networking.connectivity !== NetworkConnectivity.None && Networking.connectivity !== NetworkConnectivity.Portal }",
                c, "Connexion")
        } catch (e) {
            console.warn("Quickshell.Networking absent : connexion supposée présente (" + e + ")")
        }
    }
}
