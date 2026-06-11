# sweetviz public interface
# -----------------------------------------------------------------------------------
try:
    from importlib.metadata import metadata # Python 3.8+
except ImportError:
    from importlib_metadata import metadata # Python 3.7

_metadata = metadata("sweetviz")
__title__ = _metadata["name"]
__version__ = _metadata["version"]
__author__ = _metadata["Author-email"]
__license__ = "MIT"

# These are the main API functions
from sweetviz.sv_public import analyze, compare, compare_intra
from sweetviz.feature_config import FeatureConfig

# This is the main report class; holds the report data
# and is used to output the final report
from sweetviz.dataframe_report import DataframeReport

# This is the config_parser, use to customize settings
from sweetviz.config import config as config_parser

# Unified example / demo runner: reproducible datasets + end-to-end examples
from sweetviz.example_runner import (
    load_dataset,
    run_all_examples,
    run_analyze,
    run_compare,
    run_compare_intra,
    run_with_target,
    run_with_feature_cfg,
    run_export_html,
    run_export_json,
    run_notebook_demo,
    ExampleResult,
    DEFAULT_OUTPUT_DIR,
)
