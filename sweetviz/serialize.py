import json
import math
import numbers
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def _convert_value(val: Any) -> Any:
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(val, bool):
        return val
    if isinstance(val, numbers.Integral):
        return int(val)
    if isinstance(val, numbers.Real):
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return {k: _convert_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_convert_value(v) for v in val]
    if isinstance(val, (pd.Series, pd.DataFrame)):
        return None
    if val is None:
        return None
    return val


def to_json(report_data: dict, filepath: str = None, indent: int = 2) -> str:
    safe_data = _convert_value(report_data)
    json_str = json.dumps(safe_data, ensure_ascii=False, indent=indent, default=str)
    if filepath is not None:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json_str)
    return json_str
