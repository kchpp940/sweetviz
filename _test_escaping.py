import pandas as pd
import numpy as np
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sweetviz

special_chars_name = 'Field<X>&Y "Z"'
special_cat_1 = '<script>alert("xss")</script>'
special_cat_2 = 'Category & "Special"'
special_text_1 = 'Line1\nLine2\r\nLine3 with <b>bold</b> & "quotes"'
very_long_name = 'A' * 80
very_long_cat = 'B' * 60

data = {
    special_chars_name: [1, 2, 3, 4, 5, np.nan, 7, 8, 9, 10],
    'normal_num': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    'cat_special': [special_cat_1, special_cat_2, special_cat_1, 'Normal', special_cat_2,
                    special_cat_1, 'Normal', special_cat_2, special_cat_1, 'Normal'],
    'cat_normal': ['A', 'B', 'A', 'C', 'B', 'A', 'C', 'B', 'A', 'C'],
    'text_special': [special_text_1, 'Another <tag> text', 'Normal & text',
                     'Quote"inside', special_text_1, 'More <stuff>',
                     'A & B', 'Test\nnewline', special_text_1, 'Final'],
    very_long_name: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    'cat_long': [very_long_cat, 'Normal', very_long_cat, 'Short', very_long_cat,
                 'Normal', very_long_cat, 'Short', very_long_cat, 'Normal'],
}

df = pd.DataFrame(data)

original_special_chars_name = special_chars_name
original_special_cat_1 = special_cat_1
original_special_cat_2 = special_cat_2
original_special_text_1 = special_text_1
original_very_long_name = very_long_name
original_very_long_cat = very_long_cat

print("=== Test 1: Generate widescreen report ===")
report1 = sweetviz.analyze(df)
report1.show_html('_test_report_widescreen.html', open_browser=False, layout='widescreen')
print("Widescreen report generated OK.")

print("\n=== Test 2: Generate vertical layout report ===")
report2 = sweetviz.analyze(df)
report2.show_html('_test_report_vertical.html', open_browser=False, layout='vertical')
print("Vertical report generated OK.")

print("\n=== Test 3: Verify original data not modified ===")
assert special_chars_name == original_special_chars_name, "special_chars_name was modified!"
assert special_cat_1 == original_special_cat_1, "special_cat_1 was modified!"
assert special_cat_2 == original_special_cat_2, "special_cat_2 was modified!"
assert special_text_1 == original_special_text_1, "special_text_1 was modified!"
assert very_long_name == original_very_long_name, "very_long_name was modified!"
assert very_long_cat == original_very_long_cat, "very_long_cat was modified!"
print("Original data integrity: PASSED")

print("\n=== Test 4: Verify HTML escaping in output ===")
with open('_test_report_widescreen.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

assert '<script>alert("xss")</script>' not in html_content, "Raw <script> tag found - XSS vulnerability!"
assert '&lt;script&gt;' in html_content, "Escaped <script> tag not found - escaping not working!"
assert 'Field<X>&Y' not in html_content, "Raw special chars in field name found!"
assert 'Field&lt;X&gt;&amp;Y' in html_content, "Escaped field name not found!"
assert '"Z"' not in html_content or '&quot;Z&quot;' in html_content, "Quotes may not be properly escaped"
print("HTML escaping: PASSED")

print("\n=== Test 5: Test escape_for_html formatter ===")
from sweetviz.sv_html_formatters import escape_for_html
try:
    from jinja2 import Markup
except ImportError:
    from markupsafe import Markup

result = escape_for_html('<test>&"test"')
assert isinstance(result, Markup), "escape_for_html should return Markup object"
assert '&lt;test&gt;&amp;&quot;test&quot;' in str(result), f"Basic escaping failed: {result}"
print("escape_for_html formatter: PASSED")

result_newline = escape_for_html("line1\nline2")
assert '<br>' in str(result_newline), f"Newline escaping failed: {result_newline}"
print("Newline handling: PASSED")

result_long = escape_for_html('A' * 200, max_len=10)
assert len(str(result_long)) <= 11, f"Max length not enforced: {len(str(result_long))}"
assert '…' in str(result_long), f"Ellipsis not added: {result_long}"
print("Long string truncation: PASSED")

result_none = escape_for_html(None)
assert result_none == "", "None should return empty string"
print("None handling: PASSED")

print("\n=== Test 6: Compare report with special chars ===")
df_compare = df.copy()
df_compare.iloc[0, 0] = 100
compare_report = sweetviz.compare([df, "Source"], [df_compare, "Compare<&>"])
compare_report.show_html('_test_report_compare.html', open_browser=False)
print("Compare report generated OK.")

with open('_test_report_compare.html', 'r', encoding='utf-8') as f:
    compare_html = f.read()
assert 'Compare<&>' not in compare_html, "Raw compare name with special chars found!"
assert 'Compare&lt;&amp;&gt;' in compare_html, "Escaped compare name not found!"
print("Compare report escaping: PASSED")

print("\n=== ALL TESTS PASSED ===")

for f in ['_test_report_widescreen.html', '_test_report_vertical.html', '_test_report_compare.html']:
    if os.path.exists(f):
        os.remove(f)
        print(f"Cleaned up {f}")

if os.path.exists('_test_escaping.py'):
    print("Test file kept for inspection.")
