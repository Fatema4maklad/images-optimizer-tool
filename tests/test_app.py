from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_without_errors() -> None:
    app_path = Path(__file__).parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=15)

    assert not app.exception
    assert app.title[0].value == "RAM World Image Optimizer"
    assert app.text_input[0].label == "Event, company, or partner name"
    buttons = {button.label: button for button in app.button}
    assert {"Clear logo", "Clear cover", "Clear gallery", "Clear all uploads"} <= set(
        buttons
    )
    assert buttons["Optimize and save images"].disabled
    assert buttons["Clear all uploads"].disabled

    app.text_input[0].input("منتدى الرياض الاقتصادي").run(timeout=15)

    assert not app.exception
    assert any(
        "ramworld-منتدى-الرياض-الاقتصادي-cover.webp" in caption.value
        for caption in app.caption
    )
