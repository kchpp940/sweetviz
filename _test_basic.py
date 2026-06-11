import sweetviz as sv
import pandas as pd
import numpy as np
import json

df = pd.DataFrame({'a': np.random.randn(100), 'b': ['x','y','z']*33 + ['x']})
report = sv.analyze(df, pairwise_analysis='off')

print("=== Test 1: Basic report data ===")
rd = report.get_report_data()
print("get_report_data keys:", list(rd.keys()))
print("features:", list(rd['features'].keys()))

print("\n=== Test 2: JSON export ===")
json_str = report.to_json()
data = json.loads(json_str)
print("JSON keys:", list(data.keys()))
print("feature a keys:", list(data['features']['a'].keys()))
print("feature a type:", data['features']['a']['type'])
print("num_values number type:", type(data['features']['a']['base_stats']['num_values']['number']))
print("num_values number value:", data['features']['a']['base_stats']['num_values']['number'])

print("\n=== Test 3: Compare + drift ===")
df1 = pd.DataFrame({'x': np.random.randn(500), 'y': np.random.choice(['A','B','C'], 500)})
df2 = pd.DataFrame({'x': np.random.randn(500)+3, 'y': np.random.choice(['A','D'], 500)})
report2 = sv.compare([df1, "Source"], [df2, "Compare"], pairwise_analysis='off')
rd2 = report2.get_report_data()
print("compare_name:", rd2['metadata']['compare_name'])
print("drift_summary keys:", list(rd2['drift_summary'].keys()) if 'drift_summary' in rd2 else 'None')
if 'drift_summary' in rd2:
    print("drift max_score:", rd2['drift_summary']['max_score'])
    print("feature x drift score:", rd2['features']['x']['drift']['score'] if 'drift' in rd2['features']['x'] else 'no drift')

print("\nAll tests passed!")
