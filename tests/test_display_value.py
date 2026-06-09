import pytest
from sweetviz.sv_html_formatters import (
    DisplayValue, make_display_value,
    escape_for_html, escape_for_attr,
    escape_for_js_string, escape_for_css_string,
)
from sweetviz.graph import Graph

try:
    from jinja2 import Markup
except ImportError:
    from markupsafe import Markup


class TestEscapeForHtml:
    def test_basic_entities(self):
        result = escape_for_html('<test>&"test"')
        assert isinstance(result, Markup)
        assert '&lt;test&gt;&amp;&quot;test&quot;' in str(result)

    def test_newline_to_br(self):
        result = escape_for_html("line1\nline2")
        assert '<br>' in str(result)

    def test_carriage_return_removed(self):
        result = escape_for_html("line1\r\nline2")
        assert '\r' not in str(result)
        assert '<br>' in str(result)

    def test_long_string_truncation(self):
        result = escape_for_html('A' * 500, max_len=50)
        assert '…' in str(result)
        assert len(str(result)) <= 51

    def test_none_returns_empty(self):
        assert escape_for_html(None) == ""

    def test_markup_prevents_double_escape(self):
        result = escape_for_html("<b>bold</b>")
        combined = f"<div>{result}</div>"
        assert '<b>' not in combined


class TestEscapeForAttr:
    def test_basic_entities(self):
        result = escape_for_attr('<test>&"x"')
        assert isinstance(result, Markup)
        assert '&lt;test&gt;&amp;&quot;x&quot;' in str(result)

    def test_attr_does_not_convert_newline_to_br(self):
        result = escape_for_attr("line1\nline2")
        assert '<br>' not in str(result)
        assert '&#10;' not in str(result)
        assert '\n' in str(result) or '&' in str(result)

    def test_attr_escapes_double_quote(self):
        result = escape_for_attr('say "hello"')
        assert '&quot;' in str(result)

    def test_attr_none_returns_empty(self):
        assert escape_for_attr(None) == ""

    def test_attr_iframe_srcdoc_roundtrip(self):
        import html as html_stdlib
        inner_html = '<div class="x">hello &amp; goodbye</div>'
        escaped = str(escape_for_attr(inner_html))
        assert '"' not in escaped.replace('&quot;', '')
        decoded = html_stdlib.unescape(escaped)
        assert decoded == inner_html


class TestEscapeForJsString:
    def test_escapes_backslash(self):
        assert escape_for_js_string('a\\b') == 'a\\\\b'

    def test_escapes_single_quote(self):
        assert escape_for_js_string("a'b") == "a\\'b"

    def test_escapes_double_quote(self):
        assert escape_for_js_string('a"b') == 'a\\"b'

    def test_escapes_newline(self):
        assert escape_for_js_string("a\nb") == "a\\nb"

    def test_escapes_carriage_return(self):
        assert escape_for_js_string("a\rb") == "a\\rb"

    def test_escapes_tab(self):
        assert escape_for_js_string("a\tb") == "a\\tb"

    def test_escapes_angle_brackets_for_script_safety(self):
        assert escape_for_js_string("<script>") == "\\x3cscript\\x3e"

    def test_escapes_ampersand(self):
        assert escape_for_js_string("a&b") == "a\\x26b"

    def test_none_returns_empty(self):
        assert escape_for_js_string(None) == ""

    def test_js_string_can_be_embedded(self):
        user_input = '"); alert("xss"); var x = "'
        escaped = escape_for_js_string(user_input)
        wrapped = f'var s = "{escaped}";'
        assert '"); alert("xss")' not in wrapped


class TestEscapeForCssString:
    def test_escapes_backslash(self):
        assert escape_for_css_string('a\\b') == 'a\\\\b'

    def test_escapes_quotes(self):
        assert escape_for_css_string('a"b') == 'a\\"b'
        assert escape_for_css_string("a'b") == "a\\'b"

    def test_newline_becomes_css_escape(self):
        assert escape_for_css_string("a\nb") == "a\\A b"

    def test_carriage_return_removed(self):
        result = escape_for_css_string("a\rb")
        assert '\r' not in result

    def test_none_returns_empty(self):
        assert escape_for_css_string(None) == ""


class TestDisplayValue:
    def test_raw_preserves_original(self):
        dv = make_display_value('<test>&"x"')
        assert dv.raw == '<test>&"x"'

    def test_plain_text_normalizes_whitespace_no_html_escape(self):
        dv = make_display_value("line1\nline2\r\nline3\t<tag>")
        pt = dv.plain_text
        assert '\n' not in pt and '\r' not in pt and '\t' not in pt
        assert '<tag>' in pt

    def test_html_text_escapes_and_adds_br(self):
        dv = make_display_value("<x>&y\nz")
        ht = str(dv.html_text)
        assert '&lt;x&gt;&amp;y' in ht
        assert '<br>' in ht

    def test_attr_text_escapes_no_br(self):
        dv = make_display_value('<x>&"y"\nz')
        at = str(dv.attr_text)
        assert '&lt;x&gt;&amp;&quot;y&quot;' in at
        assert '<br>' not in at

    def test_js_string(self):
        dv = make_display_value('<x>&"y"')
        js = dv.js_string
        assert '\\x3c' in js
        assert '\\"' in js
        assert '\\x26' in js

    def test_css_string(self):
        dv = make_display_value('a"b\nc')
        cs = dv.css_string
        assert '\\"' in cs
        assert '\\A ' in cs

    def test_display_key_safety_and_length(self):
        dv_long = make_display_value('A' * 500)
        dk = dv_long.display_key
        assert len(dk) <= 40
        assert '<' not in dk and '&' not in dk and ' ' not in dk
        assert not dk[0].isdigit()

    def test_display_key_deterministic(self):
        dv1 = make_display_value("Field<X>&Y")
        dv2 = make_display_value("Field<X>&Y")
        assert dv1.display_key == dv2.display_key

    def test_display_key_empty(self):
        dv = make_display_value("")
        assert dv.display_key == "_empty_"

    def test_graph_label_escapes_dollar(self):
        dv = make_display_value("$price")
        assert r'\$' in dv.graph_label()

    def test_graph_label_delegation(self):
        assert Graph.safe_label_for_graph("test") == make_display_value("test").graph_label()

    def test_none_value(self):
        dv = make_display_value(None)
        assert dv.raw is None
        assert dv.plain_text == ""
        assert str(dv.html_text) == ""
        assert str(dv.attr_text) == ""
        assert dv.js_string == ""
        assert dv.css_string == ""
        assert dv.graph_label() == ""
        assert dv.display_key == "_empty_"

    def test_str_uses_html_text(self):
        dv = make_display_value("<x>")
        assert str(dv) == str(dv.html_text)
        assert "&lt;x&gt;" in str(dv)

    def test_html_protocol(self):
        dv = make_display_value("<x>")
        assert dv.__html__() == str(dv.html_text)
