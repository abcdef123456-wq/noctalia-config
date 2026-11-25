#pragma once

#include <hyprland/src/render/transformer/Transformer.hpp>

#include <chrono>
#include <optional>

namespace NcGestes {
    // Geste d'ouverture « goutte » : la vraie texture de la fenêtre naît sous l'île, pend au bout
    // d'un col liquide, se détache puis tombe à sa place. Purement visuel : la fenêtre est déjà
    // posée, focalisable et à sa géométrie finale.
    class CGoutteTransformer : public Render::IWindowTransformer {
      public:
        // anchor : pilule de l'île, en coordonnées logiques globales.
        CGoutteTransformer(PHLWINDOWREF window, const CBox& anchor, std::chrono::milliseconds duration);

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
        CBox                             m_anchor;
        std::chrono::milliseconds        m_duration;
        clock::time_point                m_created = clock::now();
        std::optional<clock::time_point> m_start; // premier rendu réel : rien n'est consommé avant le premier pixel
        float                            m_t      = 0.F;
        bool                             m_active = true;
    };
}
