import QtQuick

CloudCarte {
    id: connexion
    objectName: "nc-cloud-connexion"
    required property bool pret
    required property var taille
    readonly property bool enLigne: pret && Object.keys(CloudEtat.etat).length > 0
    readonly property bool quotaConnu: enLigne && typeof CloudEtat.etat.used_bytes === "number" && CloudEtat.etat.used_bytes >= 0
                                      && typeof CloudEtat.etat.quota_bytes === "number" && CloudEtat.etat.quota_bytes > 0
    readonly property real part: quotaConnu ? Math.min(1, CloudEtat.etat.used_bytes / CloudEtat.etat.quota_bytes) : 0
    readonly property real reserve: quotaConnu && typeof CloudEtat.etat.reserved_bytes === "number" ? Math.max(0, CloudEtat.etat.reserved_bytes) : 0
    readonly property real partReservee: quotaConnu ? Math.min(1 - part, reserve / CloudEtat.etat.quota_bytes) : 0

    Flow {
        id: ligneEtat
        width: parent.width; spacing: 8
        readonly property bool surUneLigne: width >= commandesEtat.implicitWidth + spacing + 240
        Item {
            width: ligneEtat.surUneLigne ? parent.width - commandesEtat.implicitWidth - parent.spacing : parent.width
            height: Math.max(42, libellesEtat.implicitHeight)
            Rectangle {
                id: voyant
                width: 10; height: 10; radius: Couleurs.rayon(5, width, height); anchors.verticalCenter: parent.verticalCenter
                color: connexion.enLigne ? Couleurs.vert : (!CloudEtat.actif ? Couleurs.texteSec : Couleurs.orange)
            }
            Column {
                id: libellesEtat
                anchors.left: voyant.right; anchors.leftMargin: 10; anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter; spacing: 3
                Texte {
                    objectName: "nc-cloud-connexion-statut"
                    width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 17; font.weight: Font.DemiBold
                    text: connexion.enLigne ? Reglages.t("Connecté à ton serveur", "Connected to your server")
                          : connexion.pret && CloudEtat.occupe ? Reglages.t("Connexion en cours…", "Connecting…")
                          : Reglages.t("Cloud indisponible", "Cloud unavailable")
                }
                Texte {
                    visible: connexion.pret; width: parent.width; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 12
                    text: CloudEtat.occupe ? Reglages.t("Actualisation…", "Refreshing…")
                          : connexion.enLigne ? Reglages.t("Un espace pour tous tes PC associés", "One space for all your paired PCs")
                          : Reglages.t("Vérifie la connexion à ton serveur.", "Check the connection to your server.")
                }
            }
        }
        Row {
            id: commandesEtat
            height: 42; spacing: 8
            CloudBouton {
                objectName: "nc-cloud-actualiser"; visible: connexion.pret; anchors.verticalCenter: parent.verticalCenter
                icone: "refresh"; texte: Reglages.t("Actualiser", "Refresh"); enabled: !CloudEtat.occupe
                onClic: CloudEtat.actualiser()
            }
            BoutonReglages { anchors.verticalCenter: parent.verticalCenter; section: "Cloud JARVIS" }
        }
    }
    Texte {
        objectName: "nc-cloud-coupe"
        visible: !CloudEtat.actif
        width: parent.width; wrapMode: Text.Wrap; secondaire: true
        text: Reglages.t("Le Cloud JARVIS est coupé : active-le dans les réglages (⚙, section Cloud JARVIS).",
                         "The JARVIS Cloud is off: turn it on in the settings (⚙, JARVIS Cloud section).")
    }
    Texte {
        objectName: "nc-cloud-non-associe"
        visible: CloudEtat.actif && !CloudEtat.associe
        width: parent.width; wrapMode: Text.Wrap; secondaire: true
        text: Reglages.t("Ce PC n'est pas associé : associe-le dans les réglages (⚙, « Associer ce PC »).",
                         "This PC is not paired: pair it in the settings (⚙, “Pair this PC”).")
    }
    Rectangle { visible: connexion.pret; width: parent.width; height: 1; color: Qt.alpha(Couleurs.texte, 0.08) }
    Item {
        visible: connexion.pret
        width: parent.width; height: Math.max(stockage.implicitHeight, quota.implicitHeight)
        Texte {
            id: stockage
            width: parent.width - quota.width - 8; elide: Text.ElideRight
            text: Reglages.t("Stockage utilisé", "Storage used"); secondaire: true; font.pixelSize: 12
        }
        Texte {
            id: quota
            objectName: "nc-cloud-quota"; anchors.right: parent.right
            text: connexion.quotaConnu ? connexion.taille(CloudEtat.etat.used_bytes) + Reglages.t(" sur ", " of ")
                                         + connexion.taille(CloudEtat.etat.quota_bytes) : "—"
            font.pixelSize: 12; font.weight: Font.DemiBold
        }
    }
    Rectangle {
        visible: connexion.pret
        width: parent.width; height: 6; radius: Couleurs.rayon(3, width, height); color: Couleurs.gris2
        Rectangle {
            width: parent.width * connexion.part; height: parent.height; radius: Couleurs.rayon(3, width, height)
            color: connexion.part > 0.9 ? Couleurs.orange : Couleurs.accent
        }
        Rectangle {
            x: parent.width * connexion.part; width: parent.width * connexion.partReservee
            height: parent.height; radius: Couleurs.rayon(3, width, height); color: Qt.alpha(Couleurs.accent, 0.5)
        }
    }
    Flow {
        visible: connexion.pret && (CloudEtat.fichiersPossible || connexion.reserve > 0)
        width: parent.width; spacing: 8
        CloudBouton {
            objectName: "nc-cloud-fichiers"; visible: CloudEtat.fichiersPossible
            icone: "folder_open"; texte: Reglages.t("Ouvrir dans Fichiers", "Open in Files"); enabled: !CloudEtat.occupe
            onClic: CloudEtat.ouvrirFichiers()
        }
        Texte {
            width: Math.min(implicitWidth, parent.width); height: Math.max(30, implicitHeight)
            verticalAlignment: Text.AlignVCenter; wrapMode: Text.Wrap; secondaire: true; font.pixelSize: 11
            text: [CloudEtat.etat.webdav === "read_write" ? Reglages.t("Fichiers : créer, déplacer et supprimer", "Files: create, move and delete")
                   : CloudEtat.etat.webdav === "read_only" ? Reglages.t("Fichiers : consultation et téléchargement", "Files: browse and download") : "",
                   connexion.reserve > 0 ? connexion.taille(connexion.reserve) + Reglages.t(" réservés", " reserved") : ""].filter(x => x !== "").join(" · ")
            visible: text !== ""
        }
    }
}
