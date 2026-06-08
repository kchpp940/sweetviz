# sweetviz public interface
# -----------------------------------------------------------------------------------

# These are the main API functions
from sweetviz.sv_public import analyze, compare, compare_intra
from sweetviz.feature_config import FeatureConfig

# This is the main report class; holds the report data
# and is used to output the final report
from sweetviz.dataframe_report import DataframeReport

# This is the config_parser, use to customize settings
from sweetviz.config import config as config_parser

# Package metadata (loaded AFTER public API imports so API availability
# does not depend on packaging metadata being present)
from sweetviz._metadata import get_package_metadata, _LICENSE

_meta = get_package_metadata()
__title__ = _meta["name"]
__version__ = _meta["version"]
__author__ = _meta["author"]
__license__ = _LICENSE
