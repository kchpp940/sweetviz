import pandas as pd
import numpy as np
import sweetviz as sv

np.random.seed(42)
n = 100

df = pd.DataFrame({
    'Age': np.random.randint(18, 70, n),
    'Income': np.random.normal(50000, 15000, n),
    'Category': np.random.choice(['A', 'B', 'C', 'D'], n),
    'Status': np.random.choice(['Active', 'Inactive', 'Pending'], n),
})

print("DataFrame created:", df.shape)

report = sv.analyze(df)
report.show_html(filepath='_test_r1.html', open_browser=False, layout='widescreen')
print("Widescreen done")

report2 = sv.analyze(df)
report2.show_html(filepath='_test_r2.html', open_browser=False, layout='vertical')
print("Vertical done")

print("ALL DONE")
