from asesor_iol.context.refresh_market import SOURCES, _render


def test_brief_lists_real_sources_with_urls():
    md = _render("2026-05-31 12:00")
    # Cada fuente autoritativa aparece con su URL (cita verificable).
    for s in SOURCES:
        assert s.url in md, s.indicador
    # Indicadores clave pedidos por la spec.
    assert "Inflación" in md
    assert "MEP" in md
    assert "BCRA" in md
    assert "Riesgo país" in md
    # Disciplina de citas: nada se afirma sin re-verificar.
    assert "re-verificar con WebSearch" in md


def test_sources_are_well_formed():
    assert len(SOURCES) >= 5
    for s in SOURCES:
        assert s.url.startswith("https://")
        assert s.fuente and s.indicador and s.como_leer
