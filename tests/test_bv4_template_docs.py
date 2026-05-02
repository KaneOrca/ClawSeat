from __future__ import annotations

from pathlib import Path

EN_DOC = Path("docs/INSTALL.md")
ZH_DOC = Path("docs/INSTALL.zh-CN.md")
ARCH_DOC = Path("docs/ARCHITECTURE.md")


def _must_contain_bv4_template_names(text: str) -> None:
    for template in ("cartooner-creative", "clawseat-engineering", "clawseat-solo"):
        assert f"`{template}`" in text, f"missing template reference: {template}"


def test_install_docs_use_bv4_template_roster() -> None:
    for path in (EN_DOC, ZH_DOC):
        text = path.read_text(encoding="utf-8")
        _must_contain_bv4_template_names(text)
        assert "clawseat-creative" not in text
        assert "clawseat-minimal" not in text.lower()


def test_install_docs_template_section_has_only_bv4() -> None:
    en = EN_DOC.read_text(encoding="utf-8")
    zh = ZH_DOC.read_text(encoding="utf-8")

    # Keep the template family explicit and bounded.
    assert "`cartooner-creative`: 4-seat creative template (memory + writer + visual + patrol)." in en
    assert (
        "`clawseat-engineering`: 5-seat engineering template (memory + planner + builder + reviewer + patrol),"
        in en
    )
    assert (
        "`clawseat-solo`: 3-seat collaboration template (memory + builder + planner-gemini),"
        in en
    )

    assert "| `cartooner-creative` | 4 | 创意类：memory + writer + visual + patrol |" in zh
    assert "| `clawseat-engineering` | 5 | 工程类：creative 基础上增加 reviewer，承担 QA + 视觉审查 |" in zh
    assert "| `clawseat-solo` | 3 | 极简协作，全 OAuth：memory + builder + planner-gemini |" in zh

    # `clawseat-minimal` should only appear in deprecation notes; none currently in these docs.
    assert "clawseat-minimal" not in en.lower()
    assert "clawseat-minimal" not in zh.lower()


def test_install_docs_have_no_default_recommended_creative() -> None:
    en = EN_DOC.read_text(encoding="utf-8")
    zh = ZH_DOC.read_text(encoding="utf-8")

    assert "Recommended★: `clawseat-creative`" not in en
    assert "推荐★：`clawseat-creative`" not in zh


def test_install_template_counts_in_docs_are_bv4() -> None:
    en = EN_DOC.read_text(encoding="utf-8")
    zh = ZH_DOC.read_text(encoding="utf-8")

    assert "cartooner-creative has 4 seats" in en
    assert "engineering has 5" in en
    assert "solo has 3" in en

    assert "cartooner-creative 4 seats" in zh
    assert "engineering 5 seats" in zh
    assert "solo 3 seats" in zh


def test_architecture_reflects_bv4_engineering_row() -> None:
    arch = ARCH_DOC.read_text(encoding="utf-8")
    assert "clawseat-engineering` | memory planner builder reviewer patrol | 5 | Engineering chain with reviewer (QA + visual review)" in arch
    assert "`cartooner-creative` | memory writer visual patrol | 4 |" in arch
    assert "`clawseat-solo` | memory (claude oauth) + builder (codex oauth) + planner (gemini oauth) | 3 |" in arch


def test_architecture_project_layer_no_designer_default() -> None:
    arch = ARCH_DOC.read_text(encoding="utf-8")
    assert "memory`, `planner`, `builder`, `reviewer`, `patrol" in arch
    assert "| `clawseat-engineering` | memory planner builder reviewer patrol | 5 |" in arch
    assert "`designer` row is intentionally not part of `cartooner-creative`" in arch
