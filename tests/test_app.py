from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_without_errors(tmp_path: Path) -> None:
    app_path = Path(__file__).parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=15)

    assert not app.exception
    assert app.title[0].value == "RAM World Image Optimizer"
    assert app.text_input[0].label == "Output folder"
    assert app.button[0].label == "Browse…"
    assert any(
        "Select an output folder" in information.value
        for information in app.info
    )

    app.text_input[0].input(str(tmp_path)).run(timeout=15)

    assert not app.exception
    entity_name_input = next(
        field
        for field in app.text_input
        if field.label == "Event, company, or partner name"
    )
    assert app.radio[0].label == "Filename language / لغة أسماء الملفات"
    buttons = {button.label: button for button in app.button}
    assert {"Clear logo", "Clear cover", "Clear gallery", "Clear all uploads"} <= set(
        buttons
    )
    assert buttons["Optimize and save images"].disabled
    assert buttons["Clear all uploads"].disabled
    assert any(caption.value == "made by Eng. fatem ★" for caption in app.caption)

    entity_name_input.input("منتدى الرياض الاقتصادي").run(timeout=15)

    assert not app.exception
    assert any(
        "ramworld-منتدى-الرياض-الاقتصادي-cover.webp" in caption.value
        for caption in app.caption
    )

    app.radio[0].set_value("العربية").run(timeout=15)

    assert not app.exception
    assert any(
        "عالم-رام-منتدى-الرياض-الاقتصادي-الغلاف.webp" in caption.value
        for caption in app.caption
    )
