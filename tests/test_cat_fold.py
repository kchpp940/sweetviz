import os
import sys
import re
import json
import tempfile
import unittest

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sweetviz as sv


def generate_test_reports(output_dir):
    """生成所有测试报表并返回文件路径映射"""
    np.random.seed(42)
    n = 5000
    categories = [f"Category_{i:03d}" for i in range(50)]
    probabilities = np.random.dirichlet(np.ones(50) * 0.5)

    df = pd.DataFrame({
        "high_card_cat": np.random.choice(categories, size=n, p=probabilities),
        "numeric_col": np.random.randn(n),
        "bool_target": np.random.choice([0, 1], size=n, p=[0.7, 0.3]),
        "num_target": np.random.randn(n)
    })

    df_compare = pd.DataFrame({
        "high_card_cat": np.random.choice(categories, size=n, p=probabilities * 1.2 / (probabilities * 1.2).sum()),
        "numeric_col": np.random.randn(n) + 0.5,
        "bool_target": np.random.choice([0, 1], size=n, p=[0.6, 0.4]),
        "num_target": np.random.randn(n) + 0.3
    })

    paths = {}

    # 1. Widescreen, no target, no compare
    report = sv.analyze(df)
    paths['wide_no_target'] = os.path.join(output_dir, 'wide_no_target.html')
    report.show_html(paths['wide_no_target'], open_browser=False, layout="widescreen")

    # 2. Widescreen, BOOL target, no compare
    report = sv.analyze(df, target_feat="bool_target")
    paths['wide_bool_target'] = os.path.join(output_dir, 'wide_bool_target.html')
    report.show_html(paths['wide_bool_target'], open_browser=False, layout="widescreen")

    # 3. Widescreen, BOOL target + compare
    report = sv.compare([df, "Source"], [df_compare, "Compare"], target_feat="bool_target")
    paths['wide_bool_compare'] = os.path.join(output_dir, 'wide_bool_compare.html')
    report.show_html(paths['wide_bool_compare'], open_browser=False, layout="widescreen")

    # 4. Widescreen, NUMERIC target + compare
    report = sv.compare([df, "Source"], [df_compare, "Compare"], target_feat="num_target")
    paths['wide_num_compare'] = os.path.join(output_dir, 'wide_num_compare.html')
    report.show_html(paths['wide_num_compare'], open_browser=False, layout="widescreen")

    # 5. Vertical, no target
    report = sv.analyze(df)
    paths['vert_no_target'] = os.path.join(output_dir, 'vert_no_target.html')
    report.show_html(paths['vert_no_target'], open_browser=False, layout="vertical")

    # 6. Vertical, BOOL target + compare
    report = sv.compare([df, "Source"], [df_compare, "Compare"], target_feat="bool_target")
    paths['vert_bool_compare'] = os.path.join(output_dir, 'vert_bool_compare.html')
    report.show_html(paths['vert_bool_compare'], open_browser=False, layout="vertical")

    # 7. Vertical, NUMERIC target + compare
    report = sv.compare([df, "Source"], [df_compare, "Compare"], target_feat="num_target")
    paths['vert_num_compare'] = os.path.join(output_dir, 'vert_num_compare.html')
    report.show_html(paths['vert_num_compare'], open_browser=False, layout="vertical")

    return paths


def find_feature_indices(html_text):
    """从 HTML 中找出 high_card_cat 列的 feature index"""
    m = re.search(r'<script type="application/json" id="cat-data-f(\d+)">', html_text)
    if not m:
        return None
    return m.group(1)


class TestCatFoldStaticHtml(unittest.TestCase):
    """静态 HTML 结构断言：JSON 存储、初始渲染状态"""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix='sv_catfold_test_')
        cls.report_paths = generate_test_reports(cls.tmpdir)
        cls.html_cache = {}
        for name, path in cls.report_paths.items():
            with open(path, 'r', encoding='utf-8') as f:
                cls.html_cache[name] = f.read()

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _extract_between(self, html, start_pattern, end_pattern, feature_idx):
        """提取两个标记之间的内容，用于检查 folded 区间"""
        start_m = re.search(start_pattern, html)
        end_m = re.search(end_pattern, html)
        if not start_m or not end_m:
            return None
        if start_m.end() > end_m.start():
            return None
        return html[start_m.end():end_m.start()]

    def _check_report(self, name):
        html = self.html_cache[name]

        # 断言 1: 存在 JSON data 存储标签
        data_m = re.search(r'<script type="application/json" id="cat-data-f(\d+)">(.+?)</script>', html, re.DOTALL)
        self.assertTrue(data_m, f"[{name}] Missing cat-data JSON script tag")

        feature_idx = data_m.group(1)
        full_data = json.loads(data_m.group(2))

        # 断言 2: JSON 数据包含足够多的类别（需触发折叠，至少远大于 max_num_breakdown_categories=10）
        category_rows = [r for r in full_data if not r.get('is_total')]
        self.assertGreaterEqual(len(category_rows), 40,
                                f"[{name}] Expected >= 40 category rows in JSON, got {len(category_rows)}")
        total_rows = [r for r in full_data if r.get('is_total')]
        self.assertEqual(len(total_rows), 1,
                         f"[{name}] Expected 1 ALL row in JSON, got {len(total_rows)}")

        # 断言 3: JSON 中每行有正确的字段（根据场景不同）
        first_row = category_rows[0]
        self.assertIn('name', first_row, f"[{name}] Missing 'name' in JSON row")
        self.assertIn('count', first_row, f"[{name}] Missing 'count' in JSON row")
        self.assertIsNotNone(first_row['count'], f"[{name}] 'count' should not be None")
        self.assertIn('number', first_row['count'], f"[{name}] Missing count.number")
        self.assertIn('perc', first_row['count'], f"[{name}] Missing count.perc")

        if 'compare' in name:
            self.assertIn('count_compare', first_row,
                          f"[{name}] Expected 'count_compare' in compare report")
            self.assertIsNotNone(first_row['count_compare'],
                                 f"[{name}] 'count_compare' should not be None in compare report")

        if 'bool' in name or 'num' in name:
            self.assertIn('target_stats', first_row,
                          f"[{name}] Expected 'target_stats' when target column present")
            self.assertIsNotNone(first_row['target_stats'],
                                 f"[{name}] 'target_stats' should not be None when target present")

        if 'bool_compare' in name or 'num_compare' in name:
            self.assertIn('target_stats_compare', first_row,
                          f"[{name}] Expected 'target_stats_compare' when target + compare")

        # 断言 4: 存在 layout JSON 存储标签
        layout_m = re.search(rf'<script type="application/json" id="cat-layout-f{feature_idx}">(.+?)</script>',
                             html, re.DOTALL)
        self.assertTrue(layout_m, f"[{name}] Missing cat-layout JSON script tag")
        layout = json.loads(layout_m.group(1))
        self.assertIn('cols', layout, f"[{name}] Missing 'cols' in layout JSON")
        self.assertIn('page_layout', layout, f"[{name}] Missing 'page_layout' in layout JSON")
        expected_layout = 'vertical' if 'vert' in name else 'widescreen'
        self.assertEqual(layout['page_layout'], expected_layout,
                         f"[{name}] Expected page_layout='{expected_layout}'")

        # 断言 5: folded 容器存在、默认可见（不含 isHidden）、包含 breakdown-row
        folded_open_m = re.search(
            rf'<div id="cat-folded-f{feature_idx}"([^>]*)>',
            html
        )
        self.assertTrue(folded_open_m, f"[{name}] Missing cat-folded-f{feature_idx} opening tag")
        folded_attrs = folded_open_m.group(1)
        self.assertIn('cat-rows-container', folded_attrs,
                      f"[{name}] cat-folded-f{feature_idx} should have class cat-rows-container")
        self.assertNotIn('isHidden', folded_attrs,
                         f"[{name}] cat-folded-f{feature_idx} should NOT have isHidden by default")

        # 断言 5b: 提取 folded 容器起始到 full 容器起始之间的区间，检查内容
        folded_content = self._extract_between(
            html,
            rf'<div id="cat-folded-f{feature_idx}"[^>]*>',
            rf'<div id="cat-full-f{feature_idx}"',
            feature_idx
        )
        self.assertIsNotNone(folded_content,
                             f"[{name}] Cannot locate folded/full container region")
        self.assertIn('breakdown-row', folded_content,
                      f"[{name}] cat-folded region should contain breakdown rows")

        # 断言 6: full 容器存在、初始为空、带 isHidden class
        full_m = re.search(
            rf'<div id="cat-full-f{feature_idx}"([^>]*)>(.*?)</div>',
            html, re.DOTALL
        )
        self.assertTrue(full_m, f"[{name}] Missing cat-full-f{feature_idx} container")
        full_attrs = full_m.group(1)
        full_content = full_m.group(2).strip()
        self.assertEqual(full_content, '',
                         f"[{name}] cat-full-f{feature_idx} should be empty initially, got: {full_content[:200]}")
        self.assertIn('isHidden', full_attrs,
                      f"[{name}] cat-full-f{feature_idx} should have isHidden class initially, attrs: {full_attrs}")
        self.assertIn('cat-rows-container', full_attrs,
                      f"[{name}] cat-full-f{feature_idx} should also have cat-rows-container class")

        # 断言 7: 展开/收起按钮存在，文字为"显示全部类别"
        btn_m = re.search(
            rf'<button id="cat-toggle-btn-f{feature_idx}"[^>]*>\s*显示全部类别\s*</button>',
            html, re.DOTALL
        )
        self.assertTrue(btn_m, f"[{name}] Missing cat-toggle-btn-f{feature_idx} with text '显示全部类别'")

        # 断言 8: folded 区域中包含 (Other) 行
        self.assertIn('(Other)', folded_content,
                      f"[{name}] cat-folded region should contain '(Other)' aggregation row")

        # 断言 9: JSON 中不包含 (Other)（Other 是 folded 特有的，完整数据里是所有类别）
        json_names = [r['name'] for r in full_data]
        self.assertNotIn('(Other)', json_names,
                         f"[{name}] JSON full data should NOT contain '(Other)'")

        return feature_idx, full_data

    def test_all_reports_static(self):
        """对所有生成的报表执行静态断言"""
        for name in self.report_paths.keys():
            with self.subTest(report=name):
                self._check_report(name)

    def test_widescreen_data_content(self):
        """Widescreen BOOL+compare 报告：验证 JSON 数据正确性"""
        name = 'wide_bool_compare'
        _, full_data = self._check_report(name)
        # 验证所有计数之和等于 ALL 行
        total_row = next(r for r in full_data if r.get('is_total'))
        cat_rows = [r for r in full_data if not r.get('is_total')]
        sum_count = sum(r['count']['number'] for r in cat_rows)
        self.assertEqual(sum_count, total_row['count']['number'],
                         f"[{name}] Sum of source category counts != ALL row")
        sum_compare = sum(r['count_compare']['number'] for r in cat_rows)
        self.assertEqual(sum_compare, total_row['count_compare']['number'],
                         f"[{name}] Sum of compare category counts != ALL row")


if __name__ == '__main__':
    print("=" * 70)
    print("SweetViz 高基数类别折叠 - 静态 HTML 断言测试")
    print("=" * 70)
    unittest.main(verbosity=2, exit=False)
    print()
    print("提示：浏览器交互断言（展开/收起/切换字段/高度重算）需要通过")
    print("       integrated_browser 手动或自动化测试。")
