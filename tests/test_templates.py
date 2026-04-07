"""Tests for templates module."""
from __future__ import annotations

import pytest

from chamber.templates import list_templates, load_template, template_to_personas


def test_list_templates_returns_all():
    templates = list_templates()
    names = [t["name"] for t in templates]
    assert "legal-review" in names
    assert "code-review" in names
    assert "threat-model" in names
    assert "red-team" in names
    assert "debate" in names


def test_list_templates_have_descriptions():
    templates = list_templates()
    for t in templates:
        assert "name" in t
        assert "description" in t
        assert len(t["description"]) > 0


def test_load_template_by_name():
    tmpl = load_template("legal-review")
    assert tmpl["name"] == "legal-review"
    assert "personas" in tmpl
    assert len(tmpl["personas"]) >= 2


def test_load_template_code_review():
    tmpl = load_template("code-review")
    assert tmpl["name"] == "code-review"
    roles = [p["role"] for p in tmpl["personas"]]
    assert any("Security" in r for r in roles)


def test_load_template_unknown_raises():
    with pytest.raises(KeyError, match="Unknown template"):
        load_template("nonexistent-template")


def test_template_to_personas():
    tmpl = load_template("debate")
    personas = template_to_personas(tmpl, word_limit=200)
    assert len(personas) == len(tmpl["personas"])
    for p in personas:
        assert p.name
        assert p.role
        assert p.system_prompt
        assert "200 words" in p.system_prompt


def test_template_config_overrides():
    tmpl = load_template("legal-review")
    overrides = tmpl.get("config_overrides", {})
    assert overrides.get("depth") == "deep"
    assert overrides.get("rounds") == 4
