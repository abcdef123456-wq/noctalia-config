#pragma once

#include <hyprland/src/render/transformer/Transformer.hpp>

#include <chrono>
#include <optional>

namespace NcGestes {
    // Numéro de la goutte dans le shader (u_mode) : seul geste qui dessine hors du cadre de la fenêtre.
    inline constexpr int GESTE_GOUTTE = 1;

    // Geste d'ouverture d'une fenêtre, rendu sur sa vraie texture (u_mode du shader : 1 goutte, 2..14 les autres).
    // Purement visuel : la fenêtre est déjà posée, focalisable et à sa géométrie finale.
    class CGestureTransformer : public Render::IWindowTransformer {
      public:
        // anchor : pilule de l'île, en coordonnées logiques globales (seule la goutte s'en sert).
        CGestureTransformer(PHLWINDOWREF window, int mode, const CBox& anchor, std::chrono::milliseconds duration);

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
        std::chrono::milliseconds        m_duration;
        clock::time_point                m_created = clock::now();
        std::optional<clock::time_point> m_start; // premier rendu réel : rien n'est consommé avant le premier pixel
        float                            m_t      = 0.F;
        bool                             m_active = true;
    };
}
