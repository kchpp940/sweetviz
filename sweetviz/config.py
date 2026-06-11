import configparser
import os
import copy
from typing import Any, Callable, Dict, Optional, Union


try:
    import importlib.resources as pkg_resources
except ImportError:
    import importlib_resources as pkg_resources


def _validate_choice(choices):
    def _validator(value):
        if value not in choices:
            raise ValueError(f"Value '{value}' is not one of the allowed choices: {choices}")
        return value
    return _validator


def _validate_range(min_val=None, max_val=None):
    def _validator(value):
        if min_val is not None and value < min_val:
            raise ValueError(f"Value {value} is less than minimum allowed {min_val}")
        if max_val is not None and value > max_val:
            raise ValueError(f"Value {value} is greater than maximum allowed {max_val}")
        return value
    return _validator


def _validate_positive(value):
    if value <= 0:
        raise ValueError(f"Value {value} must be positive")
    return value


def _validate_non_negative(value):
    if value < 0:
        raise ValueError(f"Value {value} must be non-negative")
    return value


_CONFIG_SCHEMA: Dict[str, Dict[str, Dict[str, Any]]] = {
    "General": {
        "default_verbosity": {
            "type": str,
            "default": "full",
            "validator": _validate_choice(["full", "progress_only", "off"]),
        },
        "use_cjk_font": {
            "type": int,
            "default": 0,
            "validator": _validate_choice([0, 1]),
        },
        "association_min_to_bold": {
            "type": float,
            "default": 0.1,
            "validator": _validate_range(0.0, 1.0),
        },
    },
    "Output_Defaults": {
        "html_layout": {
            "type": str,
            "default": "widescreen",
            "validator": _validate_choice(["widescreen", "vertical"]),
        },
        "html_scale": {
            "type": float,
            "default": 1.0,
            "validator": _validate_positive,
        },
        "notebook_layout": {
            "type": str,
            "default": "vertical",
            "validator": _validate_choice(["widescreen", "vertical"]),
        },
        "notebook_scale": {
            "type": float,
            "default": 1.0,
            "validator": _validate_positive,
        },
        "notebook_width": {
            "type": str,
            "default": "100%",
            "validator": None,
        },
        "notebook_height": {
            "type": int,
            "default": 750,
            "validator": _validate_positive,
        },
    },
    "comet_ml_defaults": {
        "html_layout": {
            "type": str,
            "default": "vertical",
            "validator": _validate_choice(["widescreen", "vertical"]),
        },
        "html_scale": {
            "type": float,
            "default": 0.9,
            "validator": _validate_positive,
        },
    },
    "Type_Detection": {
        "max_numeric_distinct_to_be_categorical": {
            "type": int,
            "default": 10,
            "validator": _validate_non_negative,
        },
        "max_text_distinct_to_be_categorical": {
            "type": int,
            "default": 101,
            "validator": _validate_non_negative,
        },
        "max_text_fraction_distinct_to_be_categorical": {
            "type": float,
            "default": 0.33,
            "validator": _validate_range(0.0, 1.0),
        },
    },
    "Processing": {
        "association_auto_threshold": {
            "type": int,
            "default": 200,
            "validator": _validate_non_negative,
        },
    },
    "Graphs": {
        "num_summary_graph_width": {
            "type": float,
            "default": 2.9,
            "validator": _validate_positive,
        },
        "cat_summary_graph_width": {
            "type": float,
            "default": 5.9,
            "validator": _validate_positive,
        },
        "summary_graph_height": {
            "type": float,
            "default": 1.2,
            "validator": _validate_positive,
        },
        "summary_graph_categorical_gap": {
            "type": float,
            "default": 20.0,
            "validator": _validate_range(0.0, 100.0),
        },
        "legend_width": {
            "type": float,
            "default": 6.0,
            "validator": _validate_positive,
        },
        "legend_height": {
            "type": float,
            "default": 0.27,
            "validator": _validate_positive,
        },
        "detail_graph_width": {
            "type": float,
            "default": 5.8,
            "validator": _validate_positive,
        },
        "detail_graph_height_numeric": {
            "type": float,
            "default": 5.3,
            "validator": _validate_positive,
        },
        "detail_graph_height_base": {
            "type": float,
            "default": 0.0,
            "validator": _validate_non_negative,
        },
        "detail_graph_height_per_elem": {
            "type": float,
            "default": 0.6,
            "validator": _validate_non_negative,
        },
        "detail_graph_categorical_gap": {
            "type": float,
            "default": 10.0,
            "validator": _validate_range(0.0, 100.0),
        },
        "detail_graph_categorical_max_height": {
            "type": float,
            "default": 5.3,
            "validator": _validate_positive,
        },
        "summary_graph_max_categories": {
            "type": int,
            "default": 5,
            "validator": _validate_positive,
        },
        "detail_graph_max_categories": {
            "type": int,
            "default": 18,
            "validator": _validate_positive,
        },
    },
    "Associations": {
        "association_graph_width": {
            "type": float,
            "default": 8.7,
            "validator": _validate_positive,
        },
        "association_graph_height": {
            "type": float,
            "default": 7.6,
            "validator": _validate_positive,
        },
        "association_graph_size_scale": {
            "type": float,
            "default": 150000,
            "validator": _validate_positive,
        },
    },
    "Summary_Stats": {
        "summary_max_text_rows": {
            "type": int,
            "default": 7,
            "validator": _validate_positive,
        },
        "text_max_string_len": {
            "type": int,
            "default": 300,
            "validator": _validate_positive,
        },
    },
    "Detail_Stats": {
        "max_num_numeric_top_values": {
            "type": int,
            "default": 30,
            "validator": _validate_positive,
        },
        "max_num_top_associations": {
            "type": int,
            "default": 14,
            "validator": _validate_positive,
        },
        "detail_max_text_rows": {
            "type": int,
            "default": 60,
            "validator": _validate_positive,
        },
        "max_num_breakdown_categories": {
            "type": int,
            "default": 50,
            "validator": _validate_positive,
        },
    },
    "Layout": {
        "show_logo": {
            "type": int,
            "default": 1,
            "validator": _validate_choice([0, 1]),
        },
        "full_page_padding_widescreen": {
            "type": int,
            "default": 160,
            "validator": _validate_non_negative,
        },
        "full_page_padding_vertical": {
            "type": int,
            "default": 300,
            "validator": _validate_non_negative,
        },
        "character_width_estimate": {
            "type": int,
            "default": 6,
            "validator": _validate_positive,
        },
        "summary_text_max_width": {
            "type": int,
            "default": 618,
            "validator": _validate_positive,
        },
        "pair_spacing": {
            "type": int,
            "default": 84,
            "validator": _validate_non_negative,
        },
        "col_spacing": {
            "type": int,
            "default": 15,
            "validator": _validate_non_negative,
        },
        "summary_top": {
            "type": int,
            "default": 150,
            "validator": _validate_non_negative,
        },
        "summary_spacing": {
            "type": int,
            "default": 0,
            "validator": _validate_non_negative,
        },
        "summary_height_per_element": {
            "type": int,
            "default": 162,
            "validator": _validate_positive,
        },
        "summary_vertical_detail_pos": {
            "type": int,
            "default": 157,
            "validator": _validate_non_negative,
        },
        "summary_vertical_padding": {
            "type": int,
            "default": 8,
            "validator": _validate_non_negative,
        },
        "cat_detail_graph_y": {
            "type": int,
            "default": 75,
            "validator": _validate_non_negative,
        },
        "cat_detail_breakdown_y_offset": {
            "type": int,
            "default": 9,
            "validator": _validate_non_negative,
        },
        "cat_detail_col_1_max_x": {
            "type": int,
            "default": 217,
            "validator": _validate_positive,
        },
        "cat_detail_col_x_padding_after_name": {
            "type": int,
            "default": 30,
            "validator": _validate_non_negative,
        },
        "cat_detail_col_target_extra_spacing": {
            "type": int,
            "default": 15,
            "validator": _validate_non_negative,
        },
        "cat_detail_col_spacing": {
            "type": int,
            "default": 81,
            "validator": _validate_non_negative,
        },
        "num_detail_max_listed_values": {
            "type": int,
            "default": 15,
            "validator": _validate_positive,
        },
        "detail_text_max_width": {
            "type": int,
            "default": 800,
            "validator": _validate_positive,
        },
    },
}


class _FrozenConfig:
    def __init__(self, data: Dict[str, Dict[str, Any]]):
        object.__setattr__(self, "_data", data)

    def __getattr__(self, section: str):
        data = object.__getattribute__(self, "_data")
        if section not in data:
            raise AttributeError(f"No such config section: '{section}'")
        return _FrozenSection(data[section])

    def __getitem__(self, section: str):
        data = object.__getattribute__(self, "_data")
        if section not in data:
            raise KeyError(f"No such config section: '{section}'")
        return _FrozenSection(data[section])

    def __setattr__(self, key, value):
        raise TypeError("SweetvizConfig is read-only at runtime. Use 'override()' to make changes before analysis.")

    def __setitem__(self, key, value):
        raise TypeError("SweetvizConfig is read-only at runtime. Use 'override()' to make changes before analysis.")

    def __contains__(self, section: str):
        data = object.__getattribute__(self, "_data")
        return section in data

    def _as_dict(self) -> Dict[str, Dict[str, Any]]:
        return copy.deepcopy(object.__getattribute__(self, "_data"))


class _FrozenSection:
    def __init__(self, section_data: Dict[str, Any]):
        object.__setattr__(self, "_section_data", section_data)

    def __getattr__(self, key: str):
        data = object.__getattribute__(self, "_section_data")
        if key not in data:
            raise AttributeError(f"No such config key: '{key}'")
        return data[key]

    def __getitem__(self, key: str):
        data = object.__getattribute__(self, "_section_data")
        if key not in data:
            raise KeyError(f"No such config key: '{key}'")
        return data[key]

    def __setattr__(self, key, value):
        raise TypeError("SweetvizConfig sections are read-only at runtime.")

    def __setitem__(self, key, value):
        raise TypeError("SweetvizConfig sections are read-only at runtime.")

    def get(self, key: str, default: Any = None) -> Any:
        data = object.__getattribute__(self, "_section_data")
        return data.get(key, default)

    def getint(self, key: str) -> int:
        val = self[key]
        if not isinstance(val, int):
            raise TypeError(f"Config key '{key}' is not an int (got {type(val).__name__})")
        return val

    def getfloat(self, key: str) -> float:
        val = self[key]
        if not isinstance(val, (int, float)):
            raise TypeError(f"Config key '{key}' is not a float (got {type(val).__name__})")
        return float(val)

    def getboolean(self, key: str) -> bool:
        val = self[key]
        if isinstance(val, bool):
            return val
        if isinstance(val, int):
            return bool(val)
        if isinstance(val, str):
            return val.lower() in ("1", "true", "yes", "on")
        raise TypeError(f"Config key '{key}' cannot be converted to boolean")

    def __contains__(self, key: str):
        data = object.__getattribute__(self, "_section_data")
        return key in data

    def keys(self):
        return object.__getattribute__(self, "_section_data").keys()

    def values(self):
        return object.__getattribute__(self, "_section_data").values()

    def items(self):
        return object.__getattribute__(self, "_section_data").items()

    def __iter__(self):
        return iter(object.__getattribute__(self, "_section_data"))


class SweetvizConfig:
    def __init__(self):
        self._schema: Dict[str, Dict[str, Dict[str, Any]]] = _CONFIG_SCHEMA
        self._values: Dict[str, Dict[str, Any]] = {}
        self._frozen: bool = False
        self._load_defaults()
        self._load_from_ini()

    def _load_defaults(self):
        for section, keys in self._schema.items():
            self._values[section] = {}
            for key, meta in keys.items():
                self._values[section][key] = copy.deepcopy(meta["default"])

    def _load_from_ini(self):
        ini_parser = configparser.ConfigParser()
        ini_file = pkg_resources.open_text("sweetviz", "sweetviz_defaults.ini")
        try:
            ini_parser.read_file(ini_file)
            for section, keys in self._schema.items():
                if not ini_parser.has_section(section):
                    continue
                for key, meta in keys.items():
                    if ini_parser.has_option(section, key):
                        raw_value = ini_parser.get(section, key)
                        try:
                            typed_value = self._convert_type(raw_value, meta["type"])
                            if meta.get("validator"):
                                typed_value = meta["validator"](typed_value)
                            self._values[section][key] = typed_value
                        except (ValueError, TypeError) as e:
                            raise ValueError(
                                f"Invalid value in sweetviz_defaults.ini for "
                                f"[{section}] {key} = '{raw_value}': {e}"
                            ) from e
        finally:
            ini_file.close()

    @staticmethod
    def _convert_type(value: str, target_type: type) -> Any:
        if target_type is bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.lower().strip() in ("1", "true", "yes", "on")
            raise TypeError(f"Cannot convert '{value}' to bool")
        if target_type is int:
            return int(float(value)) if isinstance(value, str) else int(value)
        if target_type is float:
            return float(value)
        if target_type is str:
            if isinstance(value, str):
                return value.replace("%%", "%")
            return str(value)
        return value

    def _check_frozen(self):
        if self._frozen:
            raise TypeError(
                "SweetvizConfig is frozen (read-only) during analysis. "
                "Make configuration changes before calling analyze()/compare()."
            )

    def override(self, section: str, key: str, value: Any):
        self._check_frozen()
        if section not in self._schema:
            raise KeyError(f"Unknown config section: '{section}'")
        if key not in self._schema[section]:
            raise KeyError(f"Unknown config key '{key}' in section '{section}'")
        meta = self._schema[section][key]
        try:
            typed_value = self._convert_type(value, meta["type"])
            if meta.get("validator"):
                typed_value = meta["validator"](typed_value)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid override value for [{section}] {key} = {value!r}: {e}"
            ) from e
        self._values[section][key] = typed_value
        config.set(section, key, str(value))

    def override_dict(self, overrides: Dict[str, Dict[str, Any]]):
        self._check_frozen()
        for section, keys in overrides.items():
            for key, value in keys.items():
                self.override(section, key, value)

    def get(self, section: str, key: str) -> Any:
        if section not in self._values:
            raise KeyError(f"No such config section: '{section}'")
        if key not in self._values[section]:
            raise KeyError(f"No such config key: '{key}' in section '{section}'")
        return self._values[section][key]

    def freeze(self) -> _FrozenConfig:
        self._frozen = True
        return _FrozenConfig(self._values)

    def unfreeze(self):
        self._frozen = False

    def is_frozen(self) -> bool:
        return self._frozen

    def as_dict(self) -> Dict[str, Dict[str, Any]]:
        return copy.deepcopy(self._values)

    def get_layout_for_template(self) -> Dict[str, int]:
        result = {}
        for key in self._values["Layout"]:
            result[key] = self._values["Layout"][key]
        return result

    def get_general_for_template(self) -> Dict[str, Any]:
        return {
            "use_cjk_font": self._values["General"]["use_cjk_font"],
            "association_min_to_bold": self._values["General"]["association_min_to_bold"],
        }

    def __getitem__(self, section: str) -> _FrozenSection:
        if section not in self._values:
            raise KeyError(f"No such config section: '{section}'")
        return _FrozenSection(self._values[section])

    def __contains__(self, section: str) -> bool:
        return section in self._values


config = configparser.ConfigParser()
the_open = pkg_resources.open_text("sweetviz", "sweetviz_defaults.ini")
config.read_file(the_open)
the_open.close()


sv_config = SweetvizConfig()
