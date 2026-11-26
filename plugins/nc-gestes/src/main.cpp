// nc-gestes : gestes d'ouverture de fenêtres de noctalia-config (la goutte de Rose Aube et 13 autres gestes de thème).

#include "GestureTransformer.hpp"
#include "Shaders.hpp"

#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/animation/AnimationManager.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/view/window/Window.hpp>
#include <hyprland/src/desktop/view/window/WindowEffectsController.hpp>
#include <hyprland/src/desktop/view/window/WindowPresentation.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/ipc/s1/S1.hpp>
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>
#include <hyprland/src/output/Monitor.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/transformer/TransformerList.hpp>

#include <algorithm>
#include <charconv>
#include <format>
#include <map>
#include <ranges>
#include <sstream>
#include <vector>

using namespace NcGestes;

namespace {
    constexpr int TAILLE_MIN = 80;

    struct SGeste {
        std::string_view nom;
        int              mode;    // u_mode du shader (Shaders.cpp)
        int              dureeMs; // durée de base, divisée par la vitesse
    };
    // Noms identiques aux valeurs de FENETRES_GESTE (nc/apparence.lua), qui garde pour chacun un repli natif.
    constexpr SGeste GESTES[] = {
        {"goutte", GESTE_GOUTTE, 680}, {"paravent", 2, 360}, {"coupe", 3, 320},    {"horizon", 4, 340},  {"maree", 5, 380},
        {"eventail", 6, 360},          {"rideau", 7, 320},   {"cathodique", 8, 300}, {"fuite", 9, 360},  {"vantaux", 10, 320},
        {"balayage", 11, 280},         {"averse", 12, 300},  {"paliers", 13, 290},  {"contour", 14, 300},
    };

    const SGeste* gesteNomme(std::string_view nom) {
        const auto IT = std::ranges::find(GESTES, nom, &SGeste::nom);
        return IT != std::end(GESTES) ? &*IT : nullptr;
    }

    struct SConfig {
        bool        enabled = true;
        std::string mode    = "goutte"; // un nom de GESTES, ou « natif »
        float       speed   = 1.F;      // > 1 accélère
    };

    HANDLE                                                      g_handle = nullptr;
    SConfig                                                     g_config;
    std::map<std::string, CBox>                                 g_anchors; // par écran, logique, local à l'écran
    std::vector<PHLWINDOWREF>                                   g_animated;
    std::vector<CHyprSignalListener>                            g_listeners;
    SP<IPC::Socket1::SCommand>                                  g_command;

    CBox anchorFor(const PHLMONITOR& mon) {
        const auto IT    = g_anchors.find(mon->m_name);
        // Ancre par défaut tant que l'île n'a rien envoyé : pilule centrée en haut.
        const CBox LOCAL = IT != g_anchors.end() ? IT->second : CBox{mon->m_size.x * 0.5 - 92.0, 10.0, 184.0, 34.0};
        return LOCAL.copy().translate(mon->m_position);
    }

    bool rendererGL() {
        return g_pHyprRenderer && g_pHyprRenderer->type() == Render::IHyprRenderer::RT_GL;
    }

    void onOpen(PHLWINDOW w) {
        const auto GESTE = gesteNomme(g_config.mode);
        if (!w || !GESTE || !g_config.enabled || !rendererGL() || !Render::GL::g_pHyprOpenGL)
            return;

        const auto MON  = w->m_monitor.lock();
        const auto SIZE = w->size(Desktop::View::IGeometric::GEOMETRIC_GOAL);
        if (!MON || w->isHidden() || w->onSpecialWorkspace() || Fullscreen::controller()->isFullscreen(w) || w->backend().traits().overrideRedirect ||
            SIZE.x < TAILLE_MIN || SIZE.y < TAILLE_MIN)
            return;

        // Compilé ici plutôt qu'au premier rendu : si le programme échoue, l'animation native reste intacte.
        Render::GL::g_pHyprOpenGL->makeEGLCurrent();
        if (!gesteShader())
            return;

        // La fenêtre est posée à sa géométrie finale tout de suite ; seul le rendu est animé.
        w->finishAnimation();
        w->presentation().alpha(Desktop::View::WINDOW_ALPHA_FADE)->warp();

        const auto DUREE = std::chrono::milliseconds(sc<int>(GESTE->dureeMs / std::max(g_config.speed, 0.1F)));
        w->effects().transformers()->emplace<CGestureTransformer>(w->m_self, GESTE->mode, anchorFor(MON), DUREE);
        g_animated.emplace_back(w->m_self);
        g_pHyprRenderer->damageWindow(w);
    }

    void onTick() {
        if (g_animated.empty())
            return;

        std::erase_if(g_animated, [](const PHLWINDOWREF& ref) {
            const auto W = ref.lock();
            if (!W)
                return true;

            const auto T = W->effects().transformers()->get<CGestureTransformer>();
            if (!T)
                return true;

            // Les extents restent fixes pendant tout le geste : un damage par image suffit.
            g_pHyprRenderer->damageWindow(W);
            const bool CONTINUE = T->tick();
            if (!CONTINUE) {
                T->deactivate();
                W->effects().transformers()->removeInactive();
            }

            if (const auto MON = W->m_monitor.lock())
                MON->scheduleFrame(Aquamarine::IOutput::AQ_SCHEDULE_ANIMATION);
            return !CONTINUE;
        });

        if (!g_animated.empty() && Animation::mgr())
            Animation::mgr()->requestTick();
    }

    // Retire les gestes de toutes les fenêtres : aucune vtable du plugin ne doit survivre au dlclose.
    void detachAll() {
        for (auto const& w : Desktop::windowState()->windows()) {
            if (!w)
                continue;
            const auto T = w->effects().transformers()->get<CGestureTransformer>();
            if (!T)
                continue;
            g_pHyprRenderer->damageWindow(w);
            T->deactivate();
            w->effects().transformers()->removeInactive();
        }
        g_animated.clear();
    }

    bool parseFloat(const std::string& s, double& out) {
        const auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), out);
        return ec == std::errc{} && ptr == s.data() + s.size();
    }

    std::string jsonEscape(const std::string& s) {
        std::string out;
        for (const char c : s) {
            if (c == '"' || c == '\\')
                out += '\\';
            if (sc<unsigned char>(c) >= 0x20)
                out += c;
        }
        return out;
    }

    std::string statusJson() {
        std::string anchors;
        for (auto const& [name, box] : g_anchors)
            anchors += std::format("{}\"{}\": [{}, {}, {}, {}]", anchors.empty() ? "" : ", ", jsonEscape(name), box.x, box.y, box.w, box.h);

        return std::format(R"({{"version": "{}", "renderer": "{}", "shader": "{}", "enabled": {}, "mode": "{}", "speed": {}, "active": {}, "anchors": {{{}}}}})",
                           HYPRLAND_API_VERSION, rendererGL() ? "gl" : "autre", gesteShaderFailed() ? "erreur" : "ok", g_config.enabled, g_config.mode,
                           g_config.speed, g_animated.size(), anchors);
    }

    IPC::Socket1::SResponse onIpc(const IPC::Socket1::SRequest& req) {
        std::istringstream       in(req.command);
        std::vector<std::string> args;
        for (std::string word; in >> word;)
            args.emplace_back(word);

        if (args.empty() || args[0] != "nc-gestes")
            return "nc-gestes : commande inconnue";

        const std::string SUB = args.size() > 1 ? args[1] : "status";

        if (SUB == "status")
            return statusJson();

        if (SUB == "anchor") {
            // anchor <écran> <x> <y> <l> <h> : pilule au repos, logique, locale à l'écran.
            double v[4];
            if (args.size() != 7 || !std::ranges::all_of(std::views::iota(0, 4), [&](int i) { return parseFloat(args[3 + i], v[i]); }) || v[2] <= 0 || v[3] <= 0)
                return "nc-gestes : usage anchor <écran> <x> <y> <largeur> <hauteur>";
            g_anchors[args[2]] = CBox{v[0], v[1], v[2], v[3]};
            return "ok";
        }

        if (SUB == "set") {
            // set enabled <0|1> | mode <geste|natif> | speed <0.1..10>, paires cumulables.
            if (args.size() < 4 || args.size() % 2 != 0)
                return "nc-gestes : usage set enabled <0|1> | mode <geste|natif> | speed <nombre>";
            SConfig next = g_config;
            for (size_t i = 2; i + 1 < args.size(); i += 2) {
                const auto& KEY = args[i];
                const auto& VAL = args[i + 1];
                double      num = 0;
                if (KEY == "enabled" && (VAL == "0" || VAL == "1"))
                    next.enabled = VAL == "1";
                else if (KEY == "mode" && (VAL == "natif" || gesteNomme(VAL)))
                    next.mode = VAL;
                else if (KEY == "speed" && parseFloat(VAL, num) && num >= 0.1 && num <= 10.0)
                    next.speed = sc<float>(num);
                else
                    return std::format("nc-gestes : valeur refusée {} {}", KEY, VAL);
            }
            g_config = next;
            return "ok";
        }

        return "nc-gestes : sous-commandes status, anchor, set";
    }
}

APICALL EXPORT std::string PLUGIN_API_VERSION() {
    return HYPRLAND_API_VERSION;
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    g_handle = handle;

    // Un .so compilé pour un autre Hyprland est refusé avant d'enregistrer quoi que ce soit.
    const std::string HASH        = __hyprland_api_get_hash();
    const std::string CLIENT_HASH = __hyprland_api_get_client_hash();
    if (HASH != CLIENT_HASH) {
        HyprlandAPI::addNotification(handle, "[nc-gestes] Version d'Hyprland différente de celle de compilation : plugin non chargé.", CHyprColor{1.0, 0.2, 0.2, 1.0},
                                     5000);
        throw std::runtime_error("[nc-gestes] version mismatch");
    }

    g_listeners.emplace_back(Event::bus()->m_events.window.openLate.listen([](PHLWINDOW w) { onOpen(w); }));
    g_listeners.emplace_back(Event::bus()->m_events.tick.listen([] { onTick(); }));
    g_command = HyprlandAPI::registerHyprCtlCommand(handle, IPC::Socket1::SCommand{.name = "nc-gestes", .match = IPC::Socket1::COMMAND_MATCH_PREFIX, .handler = onIpc});

    return {"nc-gestes", "Gestes d'ouverture de fenêtres de noctalia-config", "noctalia-config", "0.2"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    g_listeners.clear();
    if (g_command)
        HyprlandAPI::unregisterHyprCtlCommand(g_handle, g_command);
    g_command.reset();

    detachAll();

    if (Render::GL::g_pHyprOpenGL) {
        Render::GL::g_pHyprOpenGL->makeEGLCurrent();
        destroyShaders();
    }
}
