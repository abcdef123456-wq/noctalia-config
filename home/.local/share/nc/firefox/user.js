// nc-firefox : préférences du dépôt noctalia-config, copiées dans ton profil par « nc-firefox installer ».
// Firefox relit ce fichier à chaque démarrage : ces valeurs l'emportent sur about:config. Pour en changer une,
// modifie-la ici (ou dans ~/.local/share/nc/firefox/user.js puis nc-firefox installer) ; retirer une ligne ne remet
// pas l'ancienne valeur : « nc-firefox desinstaller » enlève le fichier, puis about:config.

// --- Apparence : le style de l'île (chrome/userChrome.css, chrome/userContent.css) ---
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);   // lit chrome/userChrome.css et userContent.css
user_pref("browser.uidensity", 1);                                        // barres compactes
user_pref("browser.compactmode.show", true);                              // « Compact » proposé dans Personnaliser
user_pref("browser.tabs.inTitlebar", 1);                                   // onglets dans la barre de titre (Hyprland n'en dessine pas)
user_pref("ui.key.menuAccessKeyFocuses", false);                           // Alt seul n'ouvre pas la barre de menus (Alt sert aux raccourcis)

// --- Bureau : sélecteur de fichiers du système (la vidéo par la carte graphique est posée en bas, seulement si vainfo répond) ---
user_pref("widget.use-xdg-desktop-portal.file-picker", 1);                // sélecteur de fichiers du bureau (portail)
user_pref("widget.use-xdg-desktop-portal.mime-handler", 1);               // ouvre les liens et fichiers avec les applis du bureau
user_pref("general.autoScroll", true);                                    // clic molette : défilement automatique
user_pref("widget.wayland.fractional-scale.enabled", true);               // net sur un écran à l'échelle 1,25 ou 1,6 (Wayland)
user_pref("full-screen-api.transition-duration.enter", "0 0");            // plein écran instantané (pas de fondu noir)
user_pref("full-screen-api.transition-duration.leave", "0 0");
user_pref("accessibility.browsewithcaret_shortcut.enabled", false);       // F7 ne propose plus la navigation au curseur
user_pref("ui.key.menuAccessKey", 0);                                     // aucune touche n'ouvre la barre de menus par erreur

// --- Session ---
user_pref("browser.startup.page", 3);                                     // rouvre les onglets de la dernière fois
user_pref("browser.sessionstore.interval", 60000);                        // session enregistrée toutes les 60 s (moins d'écritures disque)
user_pref("browser.shell.checkDefaultBrowser", false);                    // ne demande plus s'il doit être le navigateur par défaut
user_pref("browser.aboutConfig.showWarning", false);                      // about:config sans avertissement
user_pref("browser.urlbar.trimHttps", true);                              // https:// masqué dans la barre d'adresse, http:// reste visible
user_pref("findbar.highlightAll", true);                                  // Ctrl + F surligne toutes les occurrences
user_pref("browser.download.alwaysOpenPanel", false);                     // le panneau des téléchargements ne s'ouvre pas tout seul
user_pref("browser.toolbars.bookmarks.visibility", "newtab");             // barre de favoris seulement sur un nouvel onglet
user_pref("browser.tabs.hoverPreview.enabled", true);                     // aperçu de l'onglet au survol
user_pref("network.IDN_show_punycode", true);                             // adresses trompeuses (lettres sosies) affichées telles quelles

// --- Moins de bruit : pas de contenu sponsorisé, de Pocket ni d'études ---
user_pref("extensions.pocket.enabled", false);
user_pref("browser.newtabpage.activity-stream.showSponsored", false);
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);
user_pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);
user_pref("browser.urlbar.suggest.quicksuggest.sponsored", false);
user_pref("browser.urlbar.suggest.quicksuggest.nonsponsored", false);
user_pref("browser.discovery.enabled", false);                            // pas de recommandations d'extensions
user_pref("browser.ml.chat.enabled", false);                              // pas de chatbot IA dans la barre latérale
user_pref("app.shield.optoutstudies.enabled", false);                     // pas d'études Shield
user_pref("app.normandy.enabled", false);                                 // pas de réglages poussés à distance
user_pref("datareporting.healthreport.uploadEnabled", false);             // pas d'envoi de télémétrie
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("privacy.globalprivacycontrol.enabled", true);                  // signale aux sites de ne pas vendre tes données (GPC)
