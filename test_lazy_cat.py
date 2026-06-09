import pandas as pd
import numpy as np
import sweetviz as sv

# 生成一个高基数分类列的数据集
np.random.seed(42)
n = 5000
categories = [f"Category_{i:03d}" for i in range(50)]  # 50个类别，超过默认10
probabilities = np.random.dirichlet(np.ones(50) * 0.5)  # 长尾分布

df = pd.DataFrame({
    "high_card_cat": np.random.choice(categories, size=n, p=probabilities),
    "numeric_col": np.random.randn(n),
    "bool_target": np.random.choice([0, 1], size=n, p=[0.7, 0.3])
})

# 同时测试 compare 报告
df_compare = pd.DataFrame({
    "high_card_cat": np.random.choice(categories, size=n, p=probabilities * 1.2 / (probabilities * 1.2).sum()),
    "numeric_col": np.random.randn(n) + 0.5,
    "bool_target": np.random.choice([0, 1], size=n, p=[0.6, 0.4])
})

print("生成高基数分类报表（无目标，无 compare）...")
report1 = sv.analyze(df)
report1.show_html("test_lazy_cat_widescreen.html", open_browser=False, layout="widescreen")
report1.show_html("test_lazy_cat_vertical.html", open_browser=False, layout="vertical")

print("生成高基数分类报表（BOOL 目标）...")
report2 = sv.analyze(df, target_feat="bool_target")
report2.show_html("test_lazy_cat_target_widescreen.html", open_browser=False, layout="widescreen")
report2.show_html("test_lazy_cat_target_vertical.html", open_browser=False, layout="vertical")

print("生成高基数分类报表（BOOL 目标 + compare）...")
report3 = sv.compare([df, "Source"], [df_compare, "Compare"], target_feat="bool_target")
report3.show_html("test_lazy_cat_compare_widescreen.html", open_browser=False, layout="widescreen")
report3.show_html("test_lazy_cat_compare_vertical.html", open_browser=False, layout="vertical")

# 测试 NUMERIC 目标
df["num_target"] = np.random.randn(n)
df_compare["num_target"] = np.random.randn(n) + 0.3
print("生成高基数分类报表（NUMERIC 目标 + compare）...")
report4 = sv.compare([df, "Source"], [df_compare, "Compare"], target_feat="num_target")
report4.show_html("test_lazy_cat_numeric_target_widescreen.html", open_browser=False, layout="widescreen")
report4.show_html("test_lazy_cat_numeric_target_vertical.html", open_browser=False, layout="vertical")

print("\n所有测试报表已生成！")
print("重点检查：")
print("  1. HTML 体积：full_count 应该在 JSON script 标签里，而不是完整渲染 DOM")
print("  2. 初始显示：只渲染 top-10 + (Other)")
print("  3. 点击'显示全部类别'：完整类别列表懒加载")
print("  4. 切换字段后：展开状态重置为折叠")
print("  5. Vertical 布局：展开/收起类别后容器高度自动重算")
