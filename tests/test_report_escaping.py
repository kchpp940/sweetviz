import os
import re
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import sweetviz
from sweetviz.sv_html_formatters import make_display_value, escape_for_attr
from sweetviz.graph import Graph


@pytest.fixture(scope="module")
def test_data():
    special_chars_name = 'Field<X>&Y "Z"'
    special_cat_1 = '<script>alert("xss")</script>'
    special_cat_2 = 'Category & "Special"'
    special_text_1 = 'Line1\nLine2\r\nLine3 with <b>bold</b> & "quotes"'
    very_long_name = 'A' * 350
    very_long_cat = 'B' * 300
    very_long_compare_name = 'Compare<' + 'Z' * 200 + '>&"'
    special_target_name = 'Target<&>"Field'

    n = 20
    rng = np.random.default_rng(42)
    data = {
        special_chars_name: list(rng.integers(1, 100, n)),
        'normal_num': list(rng.integers(10, 200, n)),
        'cat_special': [special_cat_1, special_cat_2, special_cat_1, 'Normal', special_cat_2] * 4,
        'cat_normal': ['A', 'B', 'A', 'C', 'B'] * 4,
        'text_special': [special_text_1, 'Another <tag> text', 'Normal & text',
                         'Quote"inside', special_text_1] * 4,
        very_long_name: list(rng.integers(1, 50, n)),
        'cat_long': [very_long_cat, 'Normal', very_long_cat, 'Short', very_long_cat] * 4,
        special_target_name: ['yes', 'no', 'yes', 'no', 'yes'] * 4,
    }
    df = pd.DataFrame(data)
    return {
        'df': df,
        'special_chars_name': special_chars_name,
        'special_cat_1': special_cat_1,
        'special_cat_2': special_cat_2,
        'special_text_1': special_text_1,
        'very_long_name': very_long_name,
        'very_long_cat': very_long_cat,
        'very_long_compare_name': very_long_compare_name,
        'special_target_name': special_target_name,
    }


def _cleanup(paths):
    for p in paths:
        if os.path.exists(p):
            os.remove(p)


def _assert_html_escaping(html_content, label, td):
    assert '<script>alert("xss")</script>' not in html_content, \
        f"[{label}] Raw <script> tag found - XSS vulnerability!"
    assert '&lt;script&gt;' in html_content, \
        f"[{label}] Escaped <script> tag not found!"

    assert 'Field<X>&Y' not in html_content, \
        f"[{label}] Raw special chars in field name found!"
    assert 'Field&lt;X&gt;&amp;Y' in html_content, \
        f"[{label}] Escaped field name not found!"

    assert 'Category & "Special"' not in html_content, \
        f"[{label}] Raw category special chars found!"

    detail_divs = re.findall(r'data-detail-div="([^"]*)"', html_content)
    rollover_spans = re.findall(r'data-rollover-span="([^"]*)"', html_content)
    all_attr_vals = detail_divs + rollover_spans
    if all_attr_vals:
        for attr_val in all_attr_vals:
            assert '<' not in attr_val, \
                f"[{label}] data-detail/rollover attr contains '<': {attr_val}"
            assert '&' not in attr_val, \
                f"[{label}] data-detail/rollover attr contains '&': {attr_val}"
            assert '"' not in attr_val, \
                f"[{label}] data-detail/rollover attr contains '\"': {attr_val}"
            assert len(attr_val) < 50, \
                f"[{label}] data-detail/rollover attr too long ({len(attr_val)}): {attr_val[:50]}"
            assert td['very_long_cat'][:20] not in attr_val, \
                f"[{label}] data-detail/rollover attr contains user category data"


def _assert_data_display_keys(html_content, label, td):
    display_keys = re.findall(r'data-display-key="([^"]*)"', html_content)
    assert len(display_keys) > 0, f"{label}: No data-display-key attributes found!"
    for dk in display_keys:
        assert len(dk) <= 40, f"{label}: data-display-key too long ({len(dk)}): {dk}"
        assert '<' not in dk and '&' not in dk and ' ' not in dk and '"' not in dk, \
            f"{label}: data-display-key contains unsafe chars: {dk}"
        if not dk.startswith("_") and not dk[0].isalpha():
            assert not dk[0].isdigit(), f"{label}: data-display-key starts with digit: {dk}"

    special_dv = make_display_value(td['special_chars_name'])
    assert special_dv.display_key in display_keys, \
        f"{label}: special field display_key '{special_dv.display_key}' not found in HTML"


def test_widescreen_report_no_crash(test_data):
    tmpdir = tempfile.mkdtemp()
    out = Path(tmpdir) / "test_widescreen.html"
    try:
        report = sweetviz.analyze(test_data['df'], target_feat=test_data['special_target_name'])
        report.show_html(str(out), open_browser=False, layout='widescreen')
        assert out.exists() and out.stat().st_size > 10000
        with open(out, 'r', encoding='utf-8') as f:
            html = f.read()
        _assert_html_escaping(html, "widescreen", test_data)
        _assert_data_display_keys(html, "widescreen", test_data)
        assert 'widescreen' in html.lower() or 'layout' in html.lower()
    finally:
        _cleanup([str(out)])


def test_vertical_report_no_crash(test_data):
    tmpdir = tempfile.mkdtemp()
    out = Path(tmpdir) / "test_vertical.html"
    try:
        report = sweetviz.analyze(test_data['df'], target_feat=test_data['special_target_name'])
        report.show_html(str(out), open_browser=False, layout='vertical')
        assert out.exists() and out.stat().st_size > 10000
        with open(out, 'r', encoding='utf-8') as f:
            html = f.read()
        _assert_html_escaping(html, "vertical", test_data)
        _assert_data_display_keys(html, "vertical", test_data)
        assert 'vertical' in html.lower() or 'layout' in html.lower()
    finally:
        _cleanup([str(out)])


def test_compare_report(test_data):
    tmpdir = tempfile.mkdtemp()
    out = Path(tmpdir) / "test_compare.html"
    try:
        df_compare = test_data['df'].copy()
        df_compare.iloc[0, 0] = 9999
        compare_report = sweetviz.compare(
            [test_data['df'], "Source<&>"],
            [df_compare, test_data['very_long_compare_name']]
        )
        compare_report.show_html(str(out), open_browser=False)
        with open(out, 'r', encoding='utf-8') as f:
            html = f.read()
        assert 'Source<&>' not in html, "Raw compare Source name special chars!"
        assert 'Source&lt;&amp;&gt;' in html, "Escaped compare Source name not found"
        assert test_data['very_long_compare_name'] not in html, \
            "Raw 200+ char compare name present (should be truncated in legend)"
        _assert_html_escaping(html, "compare", test_data)
    finally:
        _cleanup([str(out)])


def test_original_data_not_modified(test_data):
    assert len(test_data['very_long_name']) == 350
    assert len(test_data['very_long_cat']) == 300
    assert test_data['special_chars_name'] == 'Field<X>&Y "Z"'
    assert test_data['special_cat_1'] == '<script>alert("xss")</script>'
    assert test_data['special_target_name'] == 'Target<&>"Field'


def test_notebook_iframe_srcdoc_escaping(test_data):
    report = sweetviz.analyze(test_data['df'])
    report.page_layout = 'widescreen'
    report.scale = 1.0
    from sweetviz import sv_html
    sv_html.load_layout_globals_from_config()
    page_html = sv_html.generate_html_dataframe_page(report)

    import html as html_stdlib
    escaped = str(escape_for_attr(page_html))
    assert '&' in escaped or len(escaped) > len(page_html), \
        "iframe srcdoc content not HTML-escaped"

    decoded = html_stdlib.unescape(escaped)
    assert decoded == page_html, "HTML escape round-trip failed for iframe srcdoc"
    assert '<script>alert("xss")</script>' not in escaped, \
        "Raw XSS payload not escaped in iframe srcdoc"


def test_padding_safety_clamping():
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 1, figsize=(2, 1))
    try:
        Graph._set_subplot_padding_from_pixels(fig, [0, 9999, 0, 9999])
    finally:
        plt.close(fig)

    fig2, ax2 = plt.subplots(1, 1, figsize=(3, 2))
    try:
        Graph._set_subplot_padding_from_pixels(fig2, [10, 20, 10, 20])
    finally:
        plt.close(fig2)


def test_explicit_html_text_in_templates(test_data):
    tmpdir = tempfile.mkdtemp()
    out = Path(tmpdir) / "test_explicit.html"
    try:
        report = sweetviz.analyze(test_data['df'])
        report.show_html(str(out), open_browser=False, layout='widescreen')
        with open(out, 'r', encoding='utf-8') as f:
            html = f.read()
        assert '|as_display }}' not in html, \
            "Found implicit |as_display usage in output - should be explicit .html_text"
        assert '.html_text' not in html, \
            ".html_text literal should not appear in rendered output"
    finally:
        _cleanup([str(out)])
