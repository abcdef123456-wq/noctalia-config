#pragma once

#include <hyprland/src/helpers/signal/Signal.hpp>
#include <hyprland/src/render/transformer/Transformer.hpp>

#include <array>
#include <chrono>
#include <optional>

namespace NcGestes {
    // Numéro de la goutte dans le shader (u_mode) : seul geste qui dessine hors du cadre de la fenêtre.
    inline constexpr int GESTE_GOUTTE = 1;

    // Couleurs de l'île (Émail) : surface de la pilule puis accent, en RVB 0..1. Absentes : teinte par défaut du shader.
    using Couleurs = std::optional<std::array<float, 6>>;

    // Geste d'ouverture d'une fenêtre, rendu sur sa vraie texture (u_mode du shader : 1 goutte, 2..14 les autres).
    // Purement visuel : la fenêtre est déjà posée, focalisable et à sa géométrie finale.
    class CGestureTransformer : public Render::IWindowTransformer {
      public:
        // anchor : pilule de l'île, en coordonnées logiques globales (seule la goutte s'en sert, avec couleurs).
        CGestureTransformer(PHLWINDOWREF window, int mode, const CBox& anchor, const Couleurs& couleurs, std::chrono::milliseconds duration);

        virtual Render::SWindowTransformBuffer transform(Render::CRenderContext& ctx, const Render::SWindowTransformBuffer& in,
                                                         const Render::SWindowTransformContext& context) override;
        virtual bool                           active() const override;
        virtual CBox                           transformedExtents(const CBox& currentBox) const override;

        // Avance l'horloge ; false quand le geste est terminé.
        bool tick();
        void deactivate();

      private:
        using clock = std::chrono::steady_clock;

        PHLWINDOWREF                     m_window;
        int                              m_mode;
        CBox                             m_anchor;
        Couleurs                         m_couleurs;
        std::chrono::milliseconds        m_duration;
        clock::time_point                m_created = clock::now();
        std::optional<clock::time_point> m_start; // premier rendu réel : rien n'est consommé avant le premier pixel
        // Contenu prêt : premier commit de l'appli après l'ouverture (le geste montre l'émail jusque-là), au plus tard
        // à 72 % du geste.
        std::optional<clock::time_point> m_pretDepuis;
        CHyprSignalListener              m_commit;
        float                            m_t      = 0.F;
        float                            m_pret   = 0.F; // fondu du vrai contenu, 0..1
        bool                             m_active = true;
    };
}
