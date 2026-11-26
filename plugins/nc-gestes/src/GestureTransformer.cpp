#include "GestureTransformer.hpp"
#include "Shaders.hpp"

#include <hyprland/src/desktop/view/window/Window.hpp>
#include <hyprland/src/desktop/view/window/WindowPresentation.hpp>
#include <hyprland/src/output/Monitor.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/protocols/core/Compositor.hpp>
#include <hyprland/src/render/Renderer.hpp>

#include <algorithm>

using namespace NcGestes;

// Délai maximal sans aucun rendu (fenêtre jamais affichée) avant d'abandonner le geste.
static constexpr auto ATTENTE_PREMIER_RENDU = std::chrono::milliseconds(800);
// Goutte : sans nouveau commit de l'appli, son contenu (tel quel) entre quand même pendant l'ouverture, à cette progression.
static constexpr float PRET_AU_PLUS_TARD = 0.72F;
static constexpr auto  FONDU_CONTENU     = std::chrono::milliseconds(120);

CGestureTransformer::CGestureTransformer(PHLWINDOWREF window, int mode, const CBox& anchor, const Couleurs& couleurs, std::chrono::milliseconds duration) :
    m_window(window), m_mode(mode), m_anchor(anchor), m_couleurs(couleurs), m_duration(duration) {
    // Le premier tampon (celui de l'ouverture) est souvent vide : le suivant apporte le vrai contenu.
    const auto W = window.lock();
    if (m_mode == GESTE_GOUTTE && W && W->resource())
        m_commit = W->resource()->m_events.commit.listen([this] {
            if (!m_pretDepuis)
                m_pretDepuis = clock::now();
        });
}

bool CGestureTransformer::active() const {
    return m_active;
}

void CGestureTransformer::deactivate() {
    m_active = false;
    m_commit.reset();
}

bool CGestureTransformer::tick() {
    if (!m_active)
        return false;

    const auto NOW = clock::now();
    if (!m_start)
        return NOW - m_created < ATTENTE_PREMIER_RENDU;

    m_t = std::clamp(std::chrono::duration<float>(NOW - *m_start).count() / std::chrono::duration<float>(m_duration).count(), 0.F, 1.F);
    if (!m_pretDepuis && m_t >= PRET_AU_PLUS_TARD)
        m_pretDepuis = NOW;
    // Fondu court, jamais avant le premier rendu ; borné par la durée du geste pour finir sur la vraie fenêtre.
    const auto FONDU = std::min(FONDU_CONTENU, std::chrono::duration_cast<std::chrono::milliseconds>(m_duration * 0.2));
    m_pret           = m_pretDepuis ? std::clamp(std::chrono::duration<float>(NOW - std::max(*m_pretDepuis, *m_start)).count() /
                                                     std::max(std::chrono::duration<float>(FONDU).count(), 1e-3F),
                                                 0.F, 1.F) :
                                      0.F;
    return m_t < 1.F;
}

CBox CGestureTransformer::transformedExtents(const CBox& currentBox) const {
    const auto PWINDOW = m_window.lock();
    // Seule la goutte sort du cadre de la fenêtre ; les autres gestes n'agrandissent rien.
    if (!m_active || !PWINDOW || m_mode != GESTE_GOUTTE)
        return currentBox;

    // currentBox est local au moniteur au rendu et global pour le damage : on ramène l'ancre
    // dans le même repère en passant par la boîte complète globale de la fenêtre.
    CBox a = m_anchor;
    a.translate(currentBox.pos() - PWINDOW->getFullWindowBoundingBox().pos());

    // Englobe la fenêtre, la pilule, et la goutte (centrée sous la pilule, jamais plus large que la fenêtre) ; marges
    // pour le léger dépassement du ressort à l'ouverture (4 %) et l'ombre douce.
    const double CX = a.middle().x;
    const double MX = currentBox.w * 0.05, MY = currentBox.h * 0.08;
    const double X1 = std::min({currentBox.x - MX, a.x, CX - currentBox.w * 0.5});
    const double X2 = std::max({currentBox.x + currentBox.w + MX, a.x + a.w, CX + currentBox.w * 0.5});
    const double Y1 = std::min(currentBox.y, a.y) - MY;
    const double Y2 = std::max(currentBox.y + currentBox.h, a.y + a.h) + MY;
    return CBox{X1, Y1, X2 - X1, Y2 - Y1}.expand(28.0);
}

Render::SWindowTransformBuffer CGestureTransformer::transform(Render::CRenderContext& ctx, const Render::SWindowTransformBuffer& in,
                                                             const Render::SWindowTransformContext& context) {
    using namespace Render;

    const auto PWINDOW = m_window.lock();
    if (!m_active || !PWINDOW || context.standalone || context.renderingSnapshot || !context.monitor || !in.framebuffer || !in.framebuffer->getTexture())
        return in;

    // Repli : autre moteur de rendu que GL, ou programme indisponible -> fenêtre intacte.
    if (!g_pHyprRenderer || g_pHyprRenderer->type() != IHyprRenderer::RT_GL || !GL::g_pHyprOpenGL)
        return in;

    const auto SHADER = gesteShader();
    if (!SHADER)
        return in;

    if (!m_start)
        m_start = clock::now();

    const double SCALE  = context.monitor->m_scale;
    const auto   CANVAS = pixelBoxForLogical(context.outputBox.copy().expand(1.0 / SCALE), SCALE);
    if (CANVAS.empty())
        return in;

    const auto OUT = g_pHyprRenderer->getWorkBuffer(ctx, CANVAS.size());
    if (!OUT || !OUT->getTexture())
        return {.framebuffer = in.framebuffer, .box = in.box, .success = false};

    // Repère local au moniteur pour la surface et l'ancre, comme context.currentBox.
    const Vector2D OFFSET = context.currentBox.pos() - PWINDOW->getFullWindowBoundingBox().pos();
    const CBox     FULL   = context.currentBox.copy().scale(SCALE);
    const CBox     INNER  = PWINDOW->getWindowMainSurfaceBox().translate(OFFSET).scale(SCALE);
    const CBox     ANCHOR = m_anchor.copy().translate(OFFSET).scale(SCALE);
    const auto     INTEX  = in.framebuffer->getTexture();
    const auto     GLB    = GL::g_pHyprOpenGL.get();

    GL::CFramebufferBindingGuard bindings{g_pHyprRenderer->glBackend()};
    auto                         state = ctx.saveDrawState();
    g_pHyprRenderer->bindFB(ctx, OUT); // fixe aussi le viewport à la taille du tampon

    GLB->disableScissor();
    glClearColor(0.F, 0.F, 0.F, 0.F);
    glClear(GL_COLOR_BUFFER_BIT);

    const bool BLEND = GLB->blendEnabled();
    GLB->blend(false); // on écrit des couleurs prémultipliées sur un fond vide

    GLB->useShader(SHADER->shader);
    glUniform1i(SHADER->tex, 0);
    glUniform2f(SHADER->canvas, CANVAS.x, CANVAS.y);
    glUniform2f(SHADER->texOrigin, in.box.x, in.box.y);
    glUniform2f(SHADER->texSize, INTEX->m_size.x, INTEX->m_size.y);
    glUniform4f(SHADER->full, FULL.x, FULL.y, FULL.w, FULL.h);
    glUniform4f(SHADER->inner, INNER.x, INNER.y, INNER.w, INNER.h);
    glUniform4f(SHADER->anchor, ANCHOR.x, ANCHOR.y, ANCHOR.w, ANCHOR.h);
    glUniform1f(SHADER->t, m_t);
    glUniform1f(SHADER->pret, m_pret);
    // Sans couleurs envoyées par l'île : l'émail vert sombre de la maquette (email-goutte.html), filet gris-vert
    static constexpr std::array<float, 6> EMAIL = {0.176F, 0.231F, 0.200F, 0.396F, 0.475F, 0.424F};
    const auto&                           C     = m_couleurs ? *m_couleurs : EMAIL;
    glUniform3f(SHADER->surface, C[0], C[1], C[2]);
    glUniform3f(SHADER->bord, C[3], C[4], C[5]);
    glUniform1f(SHADER->scale, SCALE);
    glUniform1f(SHADER->radius, PWINDOW->presentation().rounding() * SCALE);
    glUniform1i(SHADER->mode, m_mode);

    GLB->setActiveTexture(GL_TEXTURE0);
    INTEX->bind();
    INTEX->setTexParameter(GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    INTEX->setTexParameter(GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    INTEX->setTexParameter(GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    INTEX->setTexParameter(GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    glBindVertexArray(SHADER->shader->getUniformLocation(SHADER_SHADER_VAO));
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    glBindVertexArray(0);
    INTEX->unbind();

    GLB->blend(BLEND);

    return {.framebuffer = OUT, .box = CANVAS, .success = true};
}
