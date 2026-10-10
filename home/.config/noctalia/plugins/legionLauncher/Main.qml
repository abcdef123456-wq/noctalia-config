import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Widgets
import qs.Commons as Commons
import qs.Services.Compositor
import qs.Widgets

// Legion Launcher : barre de recherche compacte au centre de l'écran (agent-linux).
// Rien ne s'affiche sous la barre tant qu'on n'a pas tapé. Entrée lance, flèches / Tab pour choisir, Échap ferme.
// Lancement identique au lanceur Noctalia (préfixe legion-launch, terminal) et historique d'utilisation partagé.
// Ouverture : qs -c noctalia-shell ipc call legionLauncher toggle
Item {
    id: root

    property var pluginApi: null

    property var apps: []
    property var results: []
    property int selected: 0
    property var favorites: []          // applications courantes, affichées quand la barre est vide
    property int favSelected: -1        // -1 : aucune tuile choisie (Entrée ne lance rien)
    readonly property int maxFavorites: 7
    property string query: ""
    readonly property int maxRows: 6
    readonly property int rowHeight: 58
    readonly property string fontFamily: Commons.Settings.data.ui.fontDefault

    // ── Applications ─────────────────────────────────────────────────────────
    function loadApps() {
        const all = DesktopEntries.applications.values || [];
        const seen = {};
        const list = [];
        for (const a of all) {
            if (!a || a.noDisplay || a.hidden)
                continue;
            const cmd = (a.command && a.command.length) ? a.command : [];
            const exe = cmd.length ? String(cmd[0]).split("/").pop() : "";
            const dedupe = (a.id || a.name) + "|" + exe;
            if (seen[dedupe])
                continue;
            seen[dedupe] = true;
            list.push({
                "entry": a,
                "key": String(a.id || a.name),
                "name": a.name || "",
                "genericName": a.genericName || "",
                "comment": a.comment || "",
                "keywords": (a.keywords || []).join(" "),
                "exe": exe,
                "icon": a.icon || "application-x-executable"
            });
        }
        apps = list;
        if (query !== "")
            search(query);
    }

    Connections {
        target: DesktopEntries.applications
        function onValuesChanged() {
            root.loadApps();
        }
    }

    Component.onCompleted: loadApps()

    // ── Recherche ────────────────────────────────────────────────────────────
    function search(q) {
        query = q;
        const t = q.trim();
        if (t === "") {
            results = [];
            selected = 0;
            return;
        }
        const found = Commons.FuzzySort.go(t, apps, {
            "keys": ["name", "genericName", "exe", "keywords", "comment"],
            "limit": 40,
            "threshold": 0.3
        });
        // Poids par champ : le nom compte plus que la description ou les mots-clés.
        const weights = [1, 0.85, 0.85, 0.7, 0.55];
        const ranked = [];
        for (const r of found) {
            let rel = 0;
            for (let k = 0; k < weights.length; k++)
                if (r[k] && r[k].target)
                    rel = Math.max(rel, r[k].score * weights[k]);
            if (rel < 0.3)
                continue;
            const uses = Commons.ShellState.getLauncherUsageCount(r.obj.key);
            // Les applications souvent utilisées remontent un peu, sans écraser la pertinence.
            ranked.push({
                "app": r.obj,
                "label": highlightName(r[0], r.obj.name),
                "rank": rel + Math.min(0.25, 0.06 * Math.log(1 + uses))
            });
        }
        ranked.sort((a, b) => b.rank - a.rank);
        results = ranked.slice(0, maxRows);
        selected = 0;
    }

    function escapeHtml(s) {
        return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Lettres trouvées en couleur d'accent (seulement si la correspondance porte sur le nom)
    function highlightName(res, name) {
        if (!res || !res.target || res.target !== name)
            return escapeHtml(name);
        const idx = res.indexes;
        const accent = String(Commons.Color.mPrimary);
        let out = "";
        let j = 0;
        for (let i = 0; i < name.length; i++) {
            const c = escapeHtml(name[i]);
            if (j < idx.length && idx[j] === i) {
                out += "<font color=\"" + accent + "\">" + c + "</font>";
                j++;
            } else {
                out += c;
            }
        }
        return out;
    }

    // ── Applications courantes : souvent ET récemment utilisées ──────────────
    // Score = (1 + nombre de lancements) × poids selon l'ancienneté du dernier lancement.
    // Complété par les applications épinglées du dock si l'historique est encore vide.
    function recencyWeight(ts) {
        if (!ts)
            return 0.8;
        const h = (Date.now() - ts) / 3600000;
        if (h < 4)
            return 4;
        if (h < 24)
            return 2.5;
        if (h < 24 * 7)
            return 1.5;
        if (h < 24 * 30)
            return 1;
        return 0.6;
    }

    function computeFavorites() {
        const last = (pluginApi && pluginApi.pluginSettings && pluginApi.pluginSettings.lastUsed) || {};
        const scored = [];
        for (const a of apps) {
            const uses = Commons.ShellState.getLauncherUsageCount(a.key);
            if (uses > 0 || last[a.key])
                scored.push({
                    "app": a,
                    "score": (1 + uses) * recencyWeight(last[a.key])
                });
        }
        scored.sort((x, y) => y.score - x.score);
        const out = scored.slice(0, maxFavorites).map(x => x.app);
        const pinned = (Commons.Settings.data.dock.pinnedApps || []).map(id => String(id).toLowerCase());
        for (const id of pinned) {
            if (out.length >= maxFavorites)
                break;
            const a = apps.find(x => x.key.toLowerCase().replace(/\.desktop$/, "") === id);
            if (a && out.indexOf(a) < 0)
                out.push(a);
        }
        favorites = out;
        favSelected = -1;
    }

    function rememberLaunch(key) {
        if (!pluginApi)
            return;
        const last = Object.assign({}, (pluginApi.pluginSettings && pluginApi.pluginSettings.lastUsed) || {});
        last[key] = Date.now();
        // On ne garde que les 60 plus récentes
        const keys = Object.keys(last).sort((a, b) => last[b] - last[a]);
        for (const k of keys.slice(60))
            delete last[k];
        pluginApi.pluginSettings.lastUsed = last;
        pluginApi.saveSettings();
    }

    function launch(i) {
        if (i < 0 || i >= results.length)
            return;
        launchApp(results[i].app);
    }

    function launchApp(app) {
        if (!app)
            return;
        Commons.Logger.i("LegionLauncher", "lancement :", app.key);
        Commons.ShellState.recordLauncherUsage(app.key);
        rememberLaunch(app.key);
        close();
        Qt.callLater(() => {
            const s = Commons.Settings.data.appLauncher;
            const prefix = (s.customLaunchPrefixEnabled && s.customLaunchPrefix) ? s.customLaunchPrefix.split(" ") : [];
            let cmd = app.entry.command || [];
            if (app.entry.runInTerminal)
                cmd = s.terminalCommand.split(" ").concat(cmd);
            if (cmd.length)
                Quickshell.execDetached(prefix.concat(cmd));
            else
                app.entry.execute();
        });
    }

    // ── Ouverture / fermeture ────────────────────────────────────────────────
    function open() {
        const scr = CompositorService.getFocusedScreen();
        if (scr)
            win.screen = scr;
        input.text = "";
        search("");
        computeFavorites();
        win.visible = true;
        openAnim.restart();
        Qt.callLater(() => input.forceActiveFocus());
    }

    function close() {
        win.visible = false;
    }

    function toggle() {
        if (win.visible)
            close();
        else
            open();
    }

    IpcHandler {
        target: "legionLauncher"
        function toggle(): string {
            root.toggle();
            return win.visible ? "opened" : "closed";
        }
        function open(): string {
            if (!win.visible)
                root.open();
            return "opened";
        }
        function close(): string {
            root.close();
            return "closed";
        }
        function search(text: string): string {
            if (!win.visible)
                root.open();
            input.text = text;
            return root.results.length + " résultat(s)";
        }
        function favorites(): string {
            if (!win.visible)
                root.open();
            return root.favorites.map(a => a.name).join(", ");
        }
        function activate(): string {
            if (root.query.trim() === "") {
                const fav = root.favorites[Math.max(0, root.favSelected)];
                root.launchApp(fav);
                return fav ? "lancé : " + fav.name : "rien à lancer";
            }
            const name = root.results.length ? root.results[root.selected].app.name : "";
            root.launch(root.selected);
            return name ? "lancé : " + name : "rien à lancer";
        }
    }

    // ── Fenêtre ──────────────────────────────────────────────────────────────
    PanelWindow {
        id: win
        visible: false
        color: "transparent"

        WlrLayershell.namespace: "noctalia:plugins:legionLauncher"
        WlrLayershell.layer: WlrLayershell.Overlay
        WlrLayershell.exclusiveZone: -1
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        // Léger voile sur le bureau ; un clic en dehors de la barre ferme
        Rectangle {
            anchors.fill: parent
            color: "black"
            opacity: 0.22
        }
        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }

        Item {
            id: card
            width: Math.min(660, parent.width - 64)
            height: column.height
            anchors.horizontalCenter: parent.horizontalCenter
            y: Math.round(parent.height * 0.27)
            transformOrigin: Item.Top

            Behavior on height {
                NumberAnimation {
                    duration: 160
                    easing.type: Easing.OutCubic
                }
            }

            ParallelAnimation {
                id: openAnim
                NumberAnimation {
                    target: card
                    property: "scale"
                    from: 0.965
                    to: 1
                    duration: 200
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: card
                    property: "opacity"
                    from: 0
                    to: 1
                    duration: 150
                    easing.type: Easing.OutCubic
                }
            }

            RectangularShadow {
                anchors.fill: bg
                radius: bg.radius
                blur: 36
                offset.y: 12
                color: Qt.alpha("black", 0.42)
            }

            Rectangle {
                id: bg
                anchors.fill: parent
                radius: Commons.Style.radiusL + 4
                color: Qt.alpha(Commons.Color.mSurface, 0.86)
                border.width: 1
                border.color: Qt.alpha(Commons.Color.mPrimary, input.activeFocus ? 0.38 : 0.2)
                clip: true
            }

            // Les clics sur la barre ne la ferment pas
            MouseArea {
                anchors.fill: parent
            }

            Column {
                id: column
                width: parent.width

                Item {
                    width: parent.width
                    height: 66

                    NIcon {
                        id: searchIcon
                        icon: "search"
                        pointSize: 17
                        color: Commons.Color.mPrimary
                        anchors.left: parent.left
                        anchors.leftMargin: 24
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    TextInput {
                        id: input
                        anchors.left: searchIcon.right
                        anchors.leftMargin: 16
                        anchors.right: parent.right
                        anchors.rightMargin: 24
                        anchors.verticalCenter: parent.verticalCenter
                        font.family: root.fontFamily
                        font.pixelSize: 21
                        color: Commons.Color.mOnSurface
                        selectionColor: Qt.alpha(Commons.Color.mPrimary, 0.4)
                        selectedTextColor: Commons.Color.mOnSurface
                        cursorDelegate: Rectangle {
                            width: 2
                            color: Commons.Color.mPrimary
                        }
                        clip: true
                        onTextChanged: root.search(text)

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Rechercher une application"
                            font: input.font
                            color: Qt.alpha(Commons.Color.mOnSurfaceVariant, 0.65)
                            visible: input.text === ""
                        }

                        Keys.onPressed: event => {
                            const n = root.results.length;
                            const ctrl = event.modifiers & Qt.ControlModifier;
                            const f = root.favorites.length;
                            if (input.text === "" && f && event.key !== Qt.Key_Escape) {
                                const next = [Qt.Key_Right, Qt.Key_Down, Qt.Key_Tab].indexOf(event.key) >= 0;
                                const prev = [Qt.Key_Left, Qt.Key_Up, Qt.Key_Backtab].indexOf(event.key) >= 0;
                                if (next)
                                    root.favSelected = (root.favSelected + 1) % f;
                                else if (prev)
                                    root.favSelected = root.favSelected <= 0 ? f - 1 : root.favSelected - 1;
                                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                                    root.launchApp(root.favorites[root.favSelected]);
                                else
                                    return;
                                event.accepted = true;
                                return;
                            }
                            if (event.key === Qt.Key_Escape) {
                                root.close();
                            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                root.launch(root.selected);
                            } else if (n && (event.key === Qt.Key_Down || event.key === Qt.Key_Tab || (ctrl && (event.key === Qt.Key_J || event.key === Qt.Key_N)))) {
                                root.selected = (root.selected + 1) % n;
                            } else if (n && (event.key === Qt.Key_Up || event.key === Qt.Key_Backtab || (ctrl && (event.key === Qt.Key_K || event.key === Qt.Key_P)))) {
                                root.selected = (root.selected - 1 + n) % n;
                            } else {
                                return;
                            }
                            event.accepted = true;
                        }
                    }
                }

                Rectangle {
                    width: parent.width - 32
                    anchors.horizontalCenter: parent.horizontalCenter
                    height: 1
                    color: Qt.alpha(Commons.Color.mOutline, 0.35)
                    visible: root.query.trim() !== ""
                }

                // Applications courantes (barre vide)
                Item {
                    id: favBlock
                    width: parent.width
                    height: 130
                    visible: root.query.trim() === "" && root.favorites.length > 0

                    Rectangle {
                        width: parent.width - 32
                        anchors.horizontalCenter: parent.horizontalCenter
                        height: 1
                        color: Qt.alpha(Commons.Color.mOutline, 0.35)
                    }

                    Text {
                        x: 26
                        y: 12
                        text: "Applications courantes"
                        font.family: root.fontFamily
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        font.letterSpacing: 0.4
                        color: Commons.Color.mOnSurfaceVariant
                    }

                    Row {
                        id: favRow
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 34
                        readonly property real tileW: Math.floor((favBlock.width - 28) / root.maxFavorites)

                        Repeater {
                            model: root.favorites

                            delegate: Item {
                                id: tile
                                required property var modelData
                                required property int index
                                readonly property bool isSel: index === root.favSelected
                                width: favRow.tileW
                                height: 84

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 3
                                    radius: Commons.Style.radiusM
                                    color: tile.isSel ? Qt.alpha(Commons.Color.mPrimary, 0.17) : (tileMouse.containsMouse ? Qt.alpha(Commons.Color.mOnSurface, 0.05) : "transparent")
                                    Behavior on color {
                                        ColorAnimation {
                                            duration: 90
                                        }
                                    }
                                }

                                IconImage {
                                    id: tileIcon
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    y: 12
                                    implicitSize: 40
                                    asynchronous: true
                                    source: Commons.ThemeIcons.iconFromName(tile.modelData.icon, "application-x-executable")
                                }

                                Text {
                                    anchors.top: tileIcon.bottom
                                    anchors.topMargin: 8
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: parent.width - 12
                                    horizontalAlignment: Text.AlignHCenter
                                    text: tile.modelData.name
                                    elide: Text.ElideRight
                                    font.family: root.fontFamily
                                    font.pixelSize: 12
                                    color: tile.isSel ? Commons.Color.mOnSurface : Commons.Color.mOnSurfaceVariant
                                }

                                MouseArea {
                                    id: tileMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onPositionChanged: root.favSelected = tile.index
                                    onClicked: root.launchApp(tile.modelData)
                                }
                            }
                        }
                    }
                }

                Item {
                    width: parent.width
                    height: 54
                    visible: root.query.trim() !== "" && root.results.length === 0

                    Text {
                        anchors.centerIn: parent
                        text: "Aucune application trouvée"
                        font.family: root.fontFamily
                        font.pixelSize: 14
                        color: Commons.Color.mOnSurfaceVariant
                    }
                }

                ListView {
                    id: list
                    width: parent.width
                    height: root.results.length ? root.results.length * root.rowHeight + 16 : 0
                    topMargin: 8
                    bottomMargin: 8
                    interactive: false
                    model: root.results
                    currentIndex: root.selected

                    delegate: Item {
                        id: row
                        required property var modelData
                        required property int index
                        readonly property bool isSel: index === root.selected
                        width: list.width
                        height: root.rowHeight

                        Rectangle {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            radius: Commons.Style.radiusM
                            color: row.isSel ? Qt.alpha(Commons.Color.mPrimary, 0.17) : (hover.containsMouse ? Qt.alpha(Commons.Color.mOnSurface, 0.05) : "transparent")
                            Behavior on color {
                                ColorAnimation {
                                    duration: 90
                                }
                            }
                        }

                        IconImage {
                            id: icon
                            anchors.left: parent.left
                            anchors.leftMargin: 24
                            anchors.verticalCenter: parent.verticalCenter
                            implicitSize: 34
                            asynchronous: true
                            source: Commons.ThemeIcons.iconFromName(row.modelData.app.icon, "application-x-executable")
                        }

                        Column {
                            anchors.left: icon.right
                            anchors.leftMargin: 16
                            anchors.right: hint.left
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 2

                            Text {
                                width: parent.width
                                text: row.modelData.label
                                textFormat: Text.StyledText
                                elide: Text.ElideRight
                                font.family: root.fontFamily
                                font.pixelSize: 15
                                font.weight: Font.Medium
                                color: Commons.Color.mOnSurface
                            }
                            Text {
                                width: parent.width
                                text: row.modelData.app.genericName || row.modelData.app.comment
                                visible: text !== ""
                                elide: Text.ElideRight
                                font.family: root.fontFamily
                                font.pixelSize: 12
                                color: Commons.Color.mOnSurfaceVariant
                            }
                        }

                        Text {
                            id: hint
                            anchors.right: parent.right
                            anchors.rightMargin: 26
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Entrée"
                            font.family: root.fontFamily
                            font.pixelSize: 12
                            color: Commons.Color.mPrimary
                            opacity: row.isSel ? 0.9 : 0
                        }

                        MouseArea {
                            id: hover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onPositionChanged: root.selected = row.index
                            onClicked: root.launch(row.index)
                        }
                    }
                }
            }
        }
    }
}
