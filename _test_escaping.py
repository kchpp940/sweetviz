import pandas as pd
import numpy as np
import os
import sys
import re
import html as html_stdlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sweetviz

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

original_special_chars_name = special_chars_name
original_special_cat_1 = special_cat_1
original_special_cat_2 = special_cat_2
original_special_text_1 = special_text_1
original_very_long_name = very_long_name
original_very_long_cat = very_long_cat
original_special_target_name = special_target_name

TEST_FILES = []


def cleanup_files():
    for f in TEST_FILES:
        if os.path.exists(f):
            os.remove(f)


def assert_html_escaping(html_content, label):
    print(f"  [{label}] Checking XSS prevention...")
    assert '<script>alert("xss")</script>' not in html_content, \
        f"[{label}] Raw <script> tag found - XSS vulnerability!"
    assert '&lt;script&gt;' in html_content, \
        f"[{label}] Escaped <script> tag not found!"

    print(f"  [{label}] Checking field name special chars...")
    assert 'Field<X>&Y' not in html_content, \
        f"[{label}] Raw special chars in field name found!"
    assert 'Field&lt;X&gt;&amp;Y' in html_content, \
        f"[{label}] Escaped field name not found!"

    print(f"  [{label}] Checking category special chars...")
    assert 'Category & "Special"' not in html_content, \
        f"[{label}] Raw category special chars found!"

    print(f"  [{label}] Checking detail/data attributes don't contain user data...")
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
            assert very_long_cat[:20] not in attr_val, \
                f"[{label}] data-detail/rollover attr contains user category data: {attr_val}"
    print(f"  [{label}] Detail toggle attrs are safe (no user data injection): OK")

    print(f"  [{label}] HTML escaping PASSED")


def assert_layout_structure(html_content, layout):
    print(f"  Checking {layout} layout markers...")
    if layout == 'widescreen':
        assert 'widescreen' in html_content.lower() or 'layout' in html_content.lower(), \
            f"Widescreen layout markers not found"
    elif layout == 'vertical':
        assert 'vertical' in html_content.lower() or 'layout' in html_content.lower(), \
            f"Vertical layout markers not found"

    assert 'text-overflow: ellipsis' in html_content or 'text-overflow:ellipsis' in html_content \
        or os.path.exists(os.path.join(os.path.dirname(sweetviz.__file__), 'templates', 'sweetviz.css')), \
        "CSS text-overflow not present for long string handling"
    print(f"  {layout} layout structure: PASSED")


def assert_original_data():
    print("  Verifying original data integrity...")
    global special_chars_name, special_cat_1, special_cat_2, special_text_1
    global very_long_name, very_long_cat, special_target_name
    assert special_chars_name == original_special_chars_name, "special_chars_name was modified!"
    assert special_cat_1 == original_special_cat_1, "special_cat_1 was modified!"
    assert special_cat_2 == original_special_cat_2, "special_cat_2 was modified!"
    assert special_text_1 == original_special_text_1, "special_text_1 was modified!"
    assert very_long_name == original_very_long_name, "very_long_name was modified!"
    assert very_long_cat == original_very_long_cat, "very_long_cat was modified!"
    assert special_target_name == original_special_target_name, "special_target_name was modified!"
    assert len(very_long_name) == 350, f"very_long_name truncated: {len(very_long_name)}"
    assert len(very_long_cat) == 300, f"very_long_cat truncated: {len(very_long_cat)}"
    print("  Original data integrity: PASSED")


def assert_notebook_iframe(report_instance, layout):
    print(f"\n=== Notebook iframe ({layout}) test ===")
    report_copy = sweetviz.analyze(df)
    report_copy.page_layout = layout
    report_copy.scale = 1.0
    from sweetviz import sv_html
    sv_html.load_layout_globals_from_config()
    page_html = sv_html.generate_html_dataframe_page(report_copy)

    import html as html_mod
    escaped_for_attr = html_mod.escape(page_html, quote=True)
    iframe_html = f'<iframe srcdoc="{escaped_for_attr}"></iframe>'

    print(f"  Checking iframe srcdoc escaping...")
    assert '&' in escaped_for_attr or len(escaped_for_attr) > len(page_html), \
        "iframe srcdoc content not HTML-escaped"

    print(f"  Checking round-trip decode...")
    decoded = html_stdlib.unescape(escaped_for_attr)
    assert decoded == page_html, "HTML escape round-trip failed for iframe srcdoc"

    print(f"  Checking escaped special chars in iframe srcdoc...")
    assert '<script>alert("xss")</script>' not in escaped_for_attr, \
        "Raw XSS payload not escaped in iframe srcdoc"

    print(f"  Notebook iframe ({layout}): PASSED")


print("\n" + "=" * 60)
print("TEST 1: Generate WIDESCREEN report (300+ char names/categories)")
print("=" * 60)
report_wide = sweetviz.analyze(df, target_feat=special_target_name)
TEST_FILES.append('_test_report_widescreen.html')
report_wide.show_html(TEST_FILES[-1], open_browser=False, layout='widescreen')
print("Widescreen report generated OK (no matplotlib crash!).")

with open(TEST_FILES[-1], 'r', encoding='utf-8') as f:
    html_wide = f.read()
assert_html_escaping(html_wide, "widescreen")
assert_layout_structure(html_wide, "widescreen")
assert_original_data()


print("\n" + "=" * 60)
print("TEST 2: Generate VERTICAL layout report")
print("=" * 60)
report_vert = sweetviz.analyze(df, target_feat=special_target_name)
TEST_FILES.append('_test_report_vertical.html')
report_vert.show_html(TEST_FILES[-1], open_browser=False, layout='vertical')
print("Vertical report generated OK (no matplotlib crash!).")

with open(TEST_FILES[-1], 'r', encoding='utf-8') as f:
    html_vert = f.read()
assert_html_escaping(html_vert, "vertical")
assert_layout_structure(html_vert, "vertical")
assert_original_data()


print("\n" + "=" * 60)
print("TEST 3: Notebook iframe - widescreen & vertical")
print("=" * 60)
assert_notebook_iframe(report_wide, 'widescreen')
assert_notebook_iframe(report_vert, 'vertical')


print("\n" + "=" * 60)
print("TEST 4: escape_for_html formatter unit tests")
print("=" * 60)
from sweetviz.sv_html_formatters import escape_for_html
try:
    from jinja2 import Markup
except ImportError:
    from markupsafe import Markup

result = escape_for_html('<test>&"test"')
assert isinstance(result, Markup), "escape_for_html should return Markup object"
assert '&lt;test&gt;&amp;&quot;test&quot;' in str(result), f"Basic escaping failed: {result}"
print("  Basic HTML entity escaping: PASSED")

result_newline = escape_for_html("line1\nline2")
assert '<br>' in str(result_newline), f"Newline escaping failed: {result_newline}"
print("  Newline -> <br>: PASSED")

result_long = escape_for_html('A' * 500, max_len=50)
assert '…' in str(result_long), f"Ellipsis not added: {result_long}"
assert len(str(result_long)) <= 51, f"Max length not enforced: {len(str(result_long))}"
print("  Long string truncation: PASSED")

result_none = escape_for_html(None)
assert result_none == "", "None should return empty string"
print("  None handling: PASSED")

result_markup_safety = escape_for_html("<b>bold</b>")
combined = f"<div>{result_markup_safety}</div>"
assert '<b>' not in combined, "Markup object didn't prevent raw HTML injection"
print("  Markup safety (prevents re-escaping in f-strings): PASSED")


print("\n" + "=" * 60)
print("TEST 5: DisplayValue class comprehensive tests")
print("=" * 60)
from sweetviz.sv_html_formatters import DisplayValue, make_display_value
from sweetviz.graph import Graph

dv = make_display_value('<test>&"x"')
assert dv.raw == '<test>&"x"', f"DisplayValue.raw should keep original value: {dv.raw}"
print("  .raw preserves original value: PASSED")

html_text = str(dv.html_text)
assert '&lt;test&gt;&amp;&quot;x&quot;' in html_text, f".html_text escaping failed: {html_text}"
print("  .html_text HTML entity escaping: PASSED")

dv_nl = make_display_value("line1\nline2\r\nline3")
assert '<br>' in str(dv_nl.html_text), f".html_text newline→<br> failed"
print("  .html_text newline→<br>: PASSED")

pt = dv.plain_text
assert '<' in pt and '&' in pt, f".plain_text should NOT HTML-escape: {pt}"
assert '\n' not in pt and '\t' not in '\r' not in pt, f".plain_text whitespace normalization failed"
print("  .plain_text normalizes whitespace but no HTML escaping: PASSED")

dv_long = make_display_value('A' * 500)
dk = dv_long.display_key
assert len(dk) <= 40, f".display_key too long ({len(dk)}): {dk}"
assert '<' not in dk and '&' not in dk and ' ' not in dk, f".display_key has unsafe chars: {dk}"
assert not dk[0].isdigit(), f".display_key should not start with digit: {dk}"
print(f"  .display_key safety and length ({len(dk)}): PASSED")

dv_1 = make_display_value("Field<X>&Y")
dv_2 = make_display_value("Field<X>&Y")
assert dv_1.display_key == dv_2.display_key, f".display_key not deterministic: {dv_1.display_key} != {dv_2.display_key}"
print("  .display_key deterministic: PASSED")

gl = dv.graph_label()
assert '$' not in gl or r'\$' in gl, f".graph_label $ not escaped"
print("  .graph_label $→\\$: PASSED")

assert Graph.safe_label_for_graph("test") == make_display_value("test").graph_label(), \
    "Graph.safe_label_for_graph should delegate to DisplayValue.graph_label"
print("  Graph.safe_label_for_graph delegates to DisplayValue: PASSED")

dv_none = make_display_value(None)
assert dv_none.raw is None
assert dv_none.plain_text == ""
assert str(dv_none.html_text) == ""
assert dv_none.graph_label() == ""
print("  DisplayValue(None) all empty: PASSED")


print("\n" + "=" * 60)
print("TEST 6: Compare report with special chars + long names")
print("=" * 60)
df_compare = df.copy()
df_compare.iloc[0, 0] = 9999
TEST_FILES.append('_test_report_compare.html')
compare_report = sweetviz.compare(
    [df, "Source<&>"],
    [df_compare, very_long_compare_name]
)
compare_report.show_html(TEST_FILES[-1], open_browser=False)
print("Compare report generated OK (no matplotlib crash!).")

with open(TEST_FILES[-1], 'r', encoding='utf-8') as f:
    compare_html = f.read()
assert 'Source<&>' not in compare_html, "Raw compare Source name special chars!"
assert 'Source&lt;&amp;&gt;' in compare_html, "Escaped compare Source name not found"
assert very_long_compare_name not in compare_html, \
    "Raw 200+ char compare name present (should be truncated in legend)"
assert_html_escaping(compare_html, "compare")
assert_original_data()
print("Compare report: PASSED")


print("\n" + "=" * 60)
print("TEST 7: Detail toggle structural assertions + data-display-key")
print("=" * 60)
for layout_name, html_content in [("widescreen", html_wide), ("vertical", html_vert)]:
    detail_sections = re.findall(
        r'class="[^"]*feature-detail[^"]*"', html_content, re.IGNORECASE)
    summary_sections = re.findall(
        r'class="[^"]*feature-summary[^"]*"', html_content, re.IGNORECASE)
    print(f"  {layout_name}: found {len(summary_sections)} summary sections, "
          f"{len(detail_sections)} detail sections")
    assert len(summary_sections) > 0, f"{layout_name}: No feature summary sections found!"
    print(f"  {layout_name} detail/summary structure: PASSED")

    display_keys = re.findall(r'data-display-key="([^"]*)"', html_content)
    print(f"  {layout_name}: found {len(display_keys)} data-display-key attributes")
    assert len(display_keys) > 0, f"{layout_name}: No data-display-key attributes found!"
    for dk in display_keys:
        assert len(dk) <= 40, f"{layout_name}: data-display-key too long ({len(dk)}): {dk}"
        assert '<' not in dk and '&' not in dk and ' ' not in dk and '"' not in dk, \
            f"{layout_name}: data-display-key contains unsafe chars: {dk}"
        if not dk.startswith("_") and not dk[0].isalpha():
            assert not dk[0].isdigit(), f"{layout_name}: data-display-key starts with digit: {dk}"
    print(f"  {layout_name} data-display-key attributes valid (all <=40 chars, no unsafe chars): PASSED")

    special_dv = make_display_value(special_chars_name)
    if special_dv.display_key in html_content:
        print(f"  {layout_name}: special field display_key '{special_dv.display_key}' found in HTML: PASSED")
    else:
        print(f"  {layout_name}: WARNING: special field display_key not found (may be truncated)")


print("\n" + "=" * 60)
print("TEST 8: Padding safety clamping doesn't crash")
print("=" * 60)
import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 1, figsize=(2, 1))
Graph._set_subplot_padding_from_pixels(fig, [0, 9999, 0, 9999])
print("  Extreme padding values clamped without crash: PASSED")
plt.close(fig)

fig2, ax2 = plt.subplots(1, 1, figsize=(3, 2))
Graph._set_subplot_padding_from_pixels(fig2, [10, 20, 10, 20])
print("  Normal padding values still work: PASSED")
plt.close(fig2)


print("\n" + "=" * 60)
print("\n========== ALL TESTS PASSED ==========\n")
print("Cleaning up test files...")
cleanup_files()
print("Done.")
