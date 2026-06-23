"""Tests for per-role LLM model routing."""

from backend.core.llm import (
    MODEL_ROLE_CONTENT,
    MODEL_ROLE_WEB_BUILD,
    resolve_model,
)
from configs import settings


def test_resolve_model_explicit():
    assert resolve_model(model="custom-model") == "custom-model"


def test_resolve_model_content_role():
    assert resolve_model(role=MODEL_ROLE_CONTENT) == settings.deepseek_model_content


def test_resolve_model_web_build_role():
    assert resolve_model(role=MODEL_ROLE_WEB_BUILD) == settings.deepseek_model_web_build


def test_resolve_model_default():
    assert resolve_model() == settings.deepseek_model


def test_role_defaults_match_requirements():
    assert "flash" in settings.deepseek_model_content
    assert "pro" in settings.deepseek_model_web_build
