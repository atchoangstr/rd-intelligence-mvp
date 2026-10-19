"""Smoke tests for the initial Streamlit home page."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_home_page_renders_project_introduction():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_path).run()

    assert not app.exception
    assert app.title[0].value == "R&D Intelligence MVP"
    assert "organizing research" in app.markdown[0].value
    assert "No business data or credentials are required." in app.markdown[0].value
