import pytest

from app.mail_core.renderer import (
    MissingVariablesError,
    RenderMode,
    UnsafeValueError,
    extract_variables,
    render,
)


def test_basic_substitution():
    assert render("Hi {{Full Name}}!", {"Full Name": "Ana"}) == "Hi Ana!"


def test_whitespace_inside_braces_is_tolerated():
    assert render("Hi {{  Full Name  }}", {"Full Name": "Ana"}) == "Hi Ana"


def test_template_without_variables_is_unchanged():
    assert render("Same for everyone", {}) == "Same for everyone"


def test_default_used_when_value_missing_or_blank():
    assert render("Hi {{Name|there}}", {}) == "Hi there"
    assert render("Hi {{Name|there}}", {"Name": "   "}) == "Hi there"


def test_default_ignored_when_value_present():
    assert render("Hi {{Name|there}}", {"Name": "Ana"}) == "Hi Ana"


def test_missing_variables_are_all_reported_once():
    with pytest.raises(MissingVariablesError) as err:
        render("{{A}} {{B}} {{A}}", {})
    assert err.value.names == ["A", "B"]


def test_blank_value_without_default_is_missing():
    with pytest.raises(MissingVariablesError):
        render("Dear {{Name}},", {"Name": ""})


def test_html_mode_preserves_markup_values():
    out = render("<p>{{Name}}</p>", {"Name": "<b>Ana</b> & co"}, RenderMode.HTML)
    assert out == "<p><b>Ana</b> & co</p>"


def test_html_mode_leaves_template_markup_alone():
    assert render("<b>{{Name}}</b>", {"Name": "Ana"}, RenderMode.HTML) == "<b>Ana</b>"


def test_text_mode_flattens_newlines():
    out = render("Hello {{Name}}", {"Name": "Ana\r\nBcc: evil@x.com"})
    assert "\n" not in out and "\r" not in out


@pytest.mark.parametrize("bad", ["../secret", "a/b", "a\\b", "..", "x\0y"])
def test_filename_mode_rejects_unsafe_values(bad):
    with pytest.raises(UnsafeValueError):
        render("{{File}}.pdf", {"File": bad}, RenderMode.FILENAME)


def test_filename_mode_accepts_normal_values():
    out = render("{{Full Name}}.pdf", {"Full Name": "Ana Reyes"}, RenderMode.FILENAME)
    assert out == "Ana Reyes.pdf"


def test_extract_variables_order_and_uniqueness():
    assert extract_variables("{{B}} {{A|x}} {{B}}") == ["B", "A"]


def test_expressions_are_never_executed():
    with pytest.raises(MissingVariablesError) as err:
        render("{{__import__('os').getcwd()}}", {})
    assert err.value.names == ["__import__('os').getcwd()"]
