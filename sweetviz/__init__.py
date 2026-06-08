# sweetviz public interface
# -----------------------------------------------------------------------------------
from pathlib import Path

__license__ = "MIT"

def _get_package_metadata():
    try:
        try:
            from importlib.metadata import metadata
        except ImportError:
            from importlib_metadata import metadata
        dist = metadata("sweetviz")
        return {
            "name": dist.get("name", "sweetviz"),
            "version": dist.get("version", "unknown"),
            "author": dist.get("Author-email", dist.get("Author", "")),
        }
    except Exception:
        pass

    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject_path.is_file():
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            project = data.get("project", {})
            authors = project.get("authors", [])
            author_str = ""
            if authors:
                parts = []
                for a in authors:
                    name = a.get("name", "")
                    email = a.get("email", "")
                    if name and email:
                        parts.append(f"{name} <{email}>")
                    elif name:
                        parts.append(name)
                    elif email:
                        parts.append(email)
                author_str = ", ".join(parts)
            return {
                "name": project.get("name", "sweetviz"),
                "version": project.get("version", "unknown"),
                "author": author_str,
            }
        except Exception:
            pass

    return {
        "name": "sweetviz",
        "version": "unknown",
        "author": "",
    }

_meta = _get_package_metadata()
__title__ = _meta["name"]
__version__ = _meta["version"]
__author__ = _meta["author"]

# These are the main API functions
from sweetviz.sv_public import analyze, compare, compare_intra
from sweetviz.feature_config import FeatureConfig

# This is the main report class; holds the report data
# and is used to output the final report
from sweetviz.dataframe_report import DataframeReport

# This is the config_parser, use to customize settings
from sweetviz.config import config as config_parser
