from __future__ import annotations

from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / "core" / "skills" / "memory-oracle" / "SKILL.md"


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_memory_oracle_skill_has_meaning_based_annotation_rule() -> None:
    text = _skill_text()
    assert "## Operator Language Matching(强制)" in text
    assert "memory↔operator 仅" in text
    assert "英文术语默认附「中文注释」,注释要讲功能/作用,不要只做字面翻译" in text
    assert "fan-out「分发出去」" in text
    assert "fan-in「汇总回来」" in text
    assert "stop hook「停止时触发的钩子函数」" in text
    assert "坏例: fan-out「扇出」/ fan-in「扇入」" in text


def test_memory_oracle_skill_keeps_exceptions_and_scope() -> None:
    text = _skill_text()
    assert "命令 / 路径 / API / 缩写 / 已成中文常用词保持原文" in text
    assert "中文术语不加英文注" in text
    assert "注释是 onboarding 工具不是双语辞典" in text
    assert "首次出现" not in text


def test_memory_oracle_skill_is_not_overgrown() -> None:
    assert len(_skill_text().splitlines()) < 500
