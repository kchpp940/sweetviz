import configparser
import copy
from typing import Any, Dict, FrozenSet, IO, Sequence


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
            "_doc_default": "full",
            "validator": _validate_choice(["full", "progress_only", "off"]),
        },
        "use_cjk_font": {
            "type": int,
            "_doc_default": 0,
            "validator": _validate_choice([0, 1]),
        },
        "association_min_to_bold": {
            "type": float,
            "_doc_default": 0.1,
            "validator": _validate_range(0.0, 1.0),
        },
    },
    "Output_Defaults": {
        "html_layout": {
            "type": str,
            "_doc_default": "widescreen",
            "validator": _validate_choice(["widescreen", "vertical"]),
        },
        "html_scale": {
            "type": float,
            "_doc_default": 1.0,
            "validator": _validate_positive,
        },
        "notebook_layout": {
            "type": str,
            "_doc_default": "vertical",
            "validator": _validate_choice(["widescreen", "vertical"]),
        },
        "notebook_scale": {
            "type": float,
            "_doc_default": 1.0,
            "validator": _validate_positive,
        },
        "notebook_width": {
            "type": str,
            "_doc_default": "100%",
            "validator": None,
        },
        "notebook_height": {
            "type": int,
            "_doc_default": 750,
            "validator": _validate_positive,
        },
    },
    "comet_ml_defaults": {
        "html_layout": {
            "type": str,
            "_doc_default": "vertical",
            "validator": _validate_choice(["widescreen", "vertical"]),
        },
        "html_scale": {
            "type": float,
            "_doc_default": 0.9,
            "validator": _validate_positive,
        },
    },
    "Type_Detection": {
        "max_numeric_distinct_to_be_categorical": {
            "type": int,
            "_doc_default": 10,
            "validator": _validate_non_negative,
        },
        "max_text_distinct_to_be_categorical": {
            "type": int,
            "_doc_default": 101,
            "validator": _validate_non_negative,
        },
        "max_text_fraction_distinct_to_be_categorical": {
            "type": float,
            "_doc_default": 0.33,
            "validator": _validate_range(0.0, 1.0),
        },
    },
    "Processing": {
        "association_auto_threshold": {
            "type": int,
            "_doc_default": 200,
            "validator": _validate_non_negative,
        },
    },
    "Graphs": {
        "num_summary_graph_width": {
            "type": float,
            "_doc_default": 2.9,
            "validator": _validate_positive,
        },
        "cat_summary_graph_width": {
            "type": float,
            "_doc_default": 5.9,
            "validator": _validate_positive,
        },
        "summary_graph_height": {
            "type": float,
            "_doc_default": 1.2,
            "validator": _validate_positive,
        },
        "summary_graph_categorical_gap": {
            "type": float,
            "_doc_default": 20.0,
            "validator": _validate_range(0.0, 100.0),
        },
        "legend_width": {
            "type": float,
            "_doc_default": 6.0,
            "validator": _validate_positive,
        },
        "legend_height": {
            "type": float,
            "_doc_default": 0.27,
            "validator": _validate_positive,
        },
        "detail_graph_width": {
            "type": float,
            "_doc_default": 5.8,
            "validator": _validate_positive,
        },
        "detail_graph_height_numeric": {
            "type": float,
            "_doc_default": 5.3,
            "validator": _validate_positive,
        },
        "detail_graph_height_base": {
            "type": float,
            "_doc_default": 0.0,
            "validator": _validate_non_negative,
        },
        "detail_graph_height_per_elem": {
            "type": float,
            "_doc_default": 0.6,
            "validator": _validate_non_negative,
        },
        "detail_graph_categorical_gap": {
            "type": float,
            "_doc_default": 10.0,
            "validator": _validate_range(0.0, 100.0),
        },
        "detail_graph_categorical_max_height": {
            "type": float,
            "_doc_default": 5.3,
            "validator": _validate_positive,
        },
        "summary_graph_max_categories": {
            "type": int,
            "_doc_default": 5,
            "validator": _validate_positive,
        },
        "detail_graph_max_categories": {
            "type": int,
            "_doc_default": 18,
            "validator": _validate_positive,
        },
    },
    "Associations": {
        "association_graph_width": {
            "type": float,
            "_doc_default": 8.7,
            "validator": _validate_positive,
        },
        "association_graph_height": {
            "type": float,
            "_doc_default": 7.6,
            "validator": _validate_positive,
        },
        "association_graph_size_scale": {
            "type": float,
            "_doc_default": 150000,
            "validator": _validate_positive,
        },
    },
    "Summary_Stats": {
        "summary_max_text_rows": {
            "type": int,
            "_doc_default": 7,
            "validator": _validate_positive,
        },
        "text_max_string_len": {
            "type": int,
            "_doc_default": 300,
            "validator": _validate_positive,
        },
    },
    "Detail_Stats": {
        "max_num_numeric_top_values": {
            "type": int,
            "_doc_default": 30,
            "validator": _validate_positive,
        },
        "max_num_top_associations": {
            "type": int,
            "_doc_default": 14,
            "validator": _validate_positive,
        },
        "detail_max_text_rows": {
            "type": int,
            "_doc_default": 60,
            "validator": _validate_positive,
        },
        "max_num_breakdown_categories": {
            "type": int,
            "_doc_default": 50,
            "validator": _validate_positive,
        },
    },
    "Layout": {
        "show_logo": {
            "type": int,
            "_doc_default": 1,
            "validator": _validate_choice([0, 1]),
        },
        "full_page_padding_widescreen": {
            "type": int,
            "_doc_default": 160,
            "validator": _validate_non_negative,
        },
        "full_page_padding_vertical": {
            "type": int,
            "_doc_default": 300,
            "validator": _validate_non_negative,
        },
        "character_width_estimate": {
            "type": int,
            "_doc_default": 6,
            "validator": _validate_positive,
        },
        "summary_text_max_width": {
            "type": int,
            "_doc_default": 618,
            "validator": _validate_positive,
        },
        "pair_spacing": {
            "type": int,
            "_doc_default": 84,
            "validator": _validate_non_negative,
        },
        "col_spacing": {
            "type": int,
            "_doc_default": 15,
            "validator": _validate_non_negative,
        },
        "summary_top": {
            "type": int,
            "_doc_default": 150,
            "validator": _validate_non_negative,
        },
        "summary_spacing": {
            "type": int,
            "_doc_default": 0,
            "validator": _validate_non_negative,
        },
        "summary_height_per_element": {
            "type": int,
            "_doc_default": 162,
            "validator": _validate_positive,
        },
        "summary_vertical_detail_pos": {
            "type": int,
            "_doc_default": 157,
            "validator": _validate_non_negative,
        },
        "summary_vertical_padding": {
            "type": int,
            "_doc_default": 8,
            "validator": _validate_non_negative,
        },
        "cat_detail_graph_y": {
            "type": int,
            "_doc_default": 75,
            "validator": _validate_non_negative,
        },
        "cat_detail_breakdown_y_offset": {
            "type": int,
            "_doc_default": 9,
            "validator": _validate_non_negative,
        },
        "cat_detail_col_1_max_x": {
            "type": int,
            "_doc_default": 217,
            "validator": _validate_positive,
        },
        "cat_detail_col_x_padding_after_name": {
            "type": int,
            "_doc_default": 30,
            "validator": _validate_non_negative,
        },
        "cat_detail_col_target_extra_spacing": {
            "type": int,
            "_doc_default": 15,
            "validator": _validate_non_negative,
        },
        "cat_detail_col_spacing": {
            "type": int,
            "_doc_default": 81,
            "validator": _validate_non_negative,
        },
        "num_detail_max_listed_values": {
            "type": int,
            "_doc_default": 15,
            "validator": _validate_positive,
        },
        "detail_text_max_width": {
            "type": int,
            "_doc_default": 800,
            "validator": _validate_positive,
        },
    },
}

_INI_FALLBACK_ALLOWLIST: FrozenSet[str] = frozenset()


def _convert_value_to_type(value: Any, target_type: type) -> Any:
    if target_type is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.lower().strip() in ("1", "true", "yes", "on")
        raise TypeError(f"Cannot convert '{value}' to bool")
    if target_type is int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(float(value.strip()))
        raise TypeError(f"Cannot convert '{value}' to int")
    if target_type is float:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            return float(value.strip())
        raise TypeError(f"Cannot convert '{value}' to float")
    if target_type is str:
        if isinstance(value, str):
            return value.replace("%%", "%")
        return str(value)
    return value


def _ingest_ini_to_values(
    ini_parser: configparser.ConfigParser,
    schema: Dict[str, Dict[str, Dict[str, Any]]],
    values: Dict[str, Dict[str, Any]],
    source_label: str,
):
    missing = []
    for section, keys in schema.items():
        if section not in values:
            values[section] = {}
        for key, meta in keys.items():
            if ini_parser.has_section(section) and ini_parser.has_option(section, key):
                raw_value = ini_parser.get(section, key)
            else:
                missing.append((section, key))
                continue
            try:
                typed_value = _convert_value_to_type(raw_value, meta["type"])
                if meta.get("validator"):
                    typed_value = meta["validator"](typed_value)
                values[section][key] = typed_value
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Invalid value in {source_label} for "
                    f"[{section}] {key} = '{raw_value}': {e}"
                ) from e
    if missing:
        allowed = set(_INI_FALLBACK_ALLOWLIST)
        unallowed = [(s, k) for s, k in missing if f"{s}.{k}" not in allowed]
        if unallowed:
            details = ", ".join(f"[{s}] {k}" for s, k in unallowed)
            raise ValueError(
                f"Configuration source '{source_label}' is missing required keys: {details}. "
                f"Every key in the schema must be present in the ini file. "
                f"Add the missing keys or, if truly optional, add them to _INI_FALLBACK_ALLOWLIST."
            )
        for section, key in missing:
            if f"{section}.{key}" in allowed:
                meta = schema[section][key]
                doc_default = meta.get("_doc_default")
                if doc_default is not None:
                    typed_value = _convert_value_to_type(doc_default, meta["type"])
                    if meta.get("validator"):
                        typed_value = meta["validator"](typed_value)
                    values[section][key] = typed_value


class _SyncedConfigSection:
    def __init__(self, owner: "_SyncedConfigParser", section: str):
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_section", section)

    def _check_section(self):
        if self._section not in self._owner._values:
            raise KeyError(self._section)

    def _norm(self, key: str) -> str:
        return self._owner.optionxform(key)

    def __getitem__(self, key: str):
        self._check_section()
        key_norm = self._norm(key)
        if key_norm not in self._owner._values[self._section]:
            raise KeyError(key)
        return str(self._owner._values[self._section][key_norm])

    def __setitem__(self, key: str, value):
        self._owner.set(self._section, key, value)

    def __delitem__(self, key: str):
        raise TypeError(
            "Deleting config keys is not supported: keys are schema-managed. "
            "Use sweetviz.settings.override() to change values."
        )

    def __contains__(self, key: str):
        if self._section not in self._owner._values:
            return False
        return self._norm(key) in self._owner._values[self._section]

    def get(self, key: str, fallback=None):
        try:
            return self[key]
        except KeyError:
            return fallback

    def getint(self, key: str) -> int:
        self._check_section()
        key_norm = self._norm(key)
        val = self._owner._values[self._section][key_norm]
        if isinstance(val, bool):
            return int(val)
        if isinstance(val, int):
            return val
        return int(float(str(val).strip()))

    def getfloat(self, key: str) -> float:
        self._check_section()
        key_norm = self._norm(key)
        val = self._owner._values[self._section][key_norm]
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        return float(str(val).strip())

    def getboolean(self, key: str) -> bool:
        self._check_section()
        key_norm = self._norm(key)
        val = self._owner._values[self._section][key_norm]
        if isinstance(val, bool):
            return val
        if isinstance(val, int):
            return bool(val)
        if isinstance(val, str):
            return val.lower().strip() in ("1", "true", "yes", "on")
        return bool(val)

    def keys(self):
        self._check_section()
        return list(self._owner._values[self._section].keys())

    def values(self):
        self._check_section()
        return [str(v) for v in self._owner._values[self._section].values()]

    def items(self):
        self._check_section()
        return [(k, str(v)) for k, v in self._owner._values[self._section].items()]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        self._check_section()
        return len(self._owner._values[self._section])

    def clear(self):
        raise TypeError(
            "clear() is not supported on config sections: keys are schema-managed and cannot be removed."
        )

    def pop(self, key: str, *args):
        raise TypeError(
            "pop() is not supported on config sections: keys are schema-managed and cannot be removed. "
            "Use sweetviz.settings.override() to change values."
        )

    def popitem(self):
        raise TypeError(
            "popitem() is not supported on config sections: keys are schema-managed and cannot be removed."
        )

    def update(self, *args, **kwargs):
        other = {}
        if args:
            other.update(args[0])
        other.update(kwargs)
        for key, value in other.items():
            self._owner.set(self._section, key, value)

    def setdefault(self, key: str, default=None):
        key_norm = self._norm(key)
        self._check_section()
        if key_norm in self._owner._values[self._section]:
            return str(self._owner._values[self._section][key_norm])
        self._owner.set(self._section, key, default)
        return str(default)


class _SyncedConfigParser(configparser.ConfigParser):
    def __init__(self, sv_config_ref: "SweetvizConfig"):
        super().__init__()
        object.__setattr__(self, "_sv_ref", sv_config_ref)

    @property
    def _values(self):
        return object.__getattribute__(self, "_sv_ref")._values

    @property
    def _schema(self):
        return object.__getattribute__(self, "_sv_ref")._schema

    def _norm_option(self, option: str) -> str:
        return self.optionxform(option)

    def _ingest_temp_parser(self, temp_parser: configparser.ConfigParser, source_label: str):
        sv = object.__getattribute__(self, "_sv_ref")
        sv._check_frozen()
        for section in temp_parser.sections():
            for key in temp_parser.options(section):
                raw_value = temp_parser.get(section, key)
                self.set(section, key, raw_value)

    def has_section(self, section: str) -> bool:
        return section in self._values

    def sections(self):
        return list(self._values.keys())

    def has_option(self, section: str, option: str) -> bool:
        if section not in self._values:
            return False
        return self._norm_option(option) in self._values[section]

    def options(self, section: str):
        if section not in self._values:
            raise configparser.NoSectionError(section)
        return list(self._values[section].keys())

    def get(self, section: str, option: str, *, raw=False, vars=None, fallback=...):
        if section not in self._values:
            if fallback is not ...:
                return fallback
            raise configparser.NoSectionError(section)
        opt_norm = self._norm_option(option)
        if opt_norm not in self._values[section]:
            if fallback is not ...:
                return fallback
            raise configparser.NoOptionError(option, section)
        return str(self._values[section][opt_norm])

    def getint(self, section: str, option: str, *, raw=False, vars=None, fallback=...):
        if section not in self._values:
            if fallback is not ...:
                return fallback
            raise configparser.NoSectionError(section)
        opt_norm = self._norm_option(option)
        if opt_norm not in self._values[section]:
            if fallback is not ...:
                return fallback
            raise configparser.NoOptionError(option, section)
        val = self._values[section][opt_norm]
        if isinstance(val, bool):
            return int(val)
        if isinstance(val, int):
            return val
        return int(float(str(val).strip()))

    def getfloat(self, section: str, option: str, *, raw=False, vars=None, fallback=...):
        if section not in self._values:
            if fallback is not ...:
                return fallback
            raise configparser.NoSectionError(section)
        opt_norm = self._norm_option(option)
        if opt_norm not in self._values[section]:
            if fallback is not ...:
                return fallback
            raise configparser.NoOptionError(option, section)
        val = self._values[section][opt_norm]
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        return float(str(val).strip())

    def getboolean(self, section: str, option: str, *, raw=False, vars=None, fallback=...):
        if section not in self._values:
            if fallback is not ...:
                return fallback
            raise configparser.NoSectionError(section)
        opt_norm = self._norm_option(option)
        if opt_norm not in self._values[section]:
            if fallback is not ...:
                return fallback
            raise configparser.NoOptionError(option, section)
        val = self._values[section][opt_norm]
        if isinstance(val, bool):
            return val
        if isinstance(val, int):
            return bool(val)
        if isinstance(val, str):
            return val.lower().strip() in ("1", "true", "yes", "on")
        return bool(val)

    def set(self, section: str, option: str, value):
        sv = object.__getattribute__(self, "_sv_ref")
        sv._check_frozen()
        if section not in self._schema:
            raise KeyError(f"Unknown config section: '{section}'")
        opt_norm = self._norm_option(option)
        if opt_norm not in self._schema[section]:
            raise KeyError(f"Unknown config key '{option}' in section '{section}'")
        meta = self._schema[section][opt_norm]
        try:
            typed_value = _convert_value_to_type(value, meta["type"])
            if meta.get("validator"):
                typed_value = meta["validator"](typed_value)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid value for [{section}] {option} = {value!r}: {e}"
            ) from e
        self._values[section][opt_norm] = typed_value

    def read(self, filenames: Any, encoding: str = None) -> Sequence[str]:
        temp = configparser.ConfigParser()
        result = temp.read(filenames, encoding=encoding)
        self._ingest_temp_parser(temp, source_label=str(filenames))
        return result

    def read_file(self, f: IO, source: str = "<???>") -> None:
        temp = configparser.ConfigParser()
        temp.read_file(f, source=source)
        self._ingest_temp_parser(temp, source_label=source)

    def read_string(self, string: str, source: str = "<string>") -> Sequence[str]:
        temp = configparser.ConfigParser()
        result = temp.read_string(string, source=source)
        self._ingest_temp_parser(temp, source_label=source)
        return result

    def read_dict(self, dictionary: Dict, source: str = "<dict>") -> None:
        temp = configparser.ConfigParser()
        temp.read_dict(dictionary, source=source)
        self._ingest_temp_parser(temp, source_label=source)

    def readfp(self, fp: IO, filename=None) -> None:
        if filename is None:
            if hasattr(fp, "name"):
                filename = fp.name
            else:
                filename = "<???>"
        self.read_file(fp, source=filename)

    def add_section(self, section: str):
        raise TypeError(
            "add_section() is not supported: sections are schema-managed. "
            "Use sweetviz.settings.override() to set values on existing sections."
        )

    def remove_section(self, section: str) -> bool:
        raise TypeError(
            "remove_section() is not supported: sections are schema-managed and cannot be removed."
        )

    def remove_option(self, section: str, option: str) -> bool:
        raise TypeError(
            "remove_option() is not supported: keys are schema-managed and cannot be removed."
        )

    def clear(self):
        raise TypeError(
            "clear() is not supported: configuration sections and keys are schema-managed."
        )

    def pop(self, section: str, *args):
        raise TypeError(
            "pop() is not supported: sections are schema-managed and cannot be removed."
        )

    def popitem(self):
        raise TypeError(
            "popitem() is not supported: sections are schema-managed and cannot be removed."
        )

    def update(self, *args, **kwargs):
        other = {}
        if args:
            if hasattr(args[0], "keys"):
                for section in args[0]:
                    if section not in other:
                        other[section] = {}
                    other[section].update(args[0][section])
            else:
                for section, section_data in args[0]:
                    if section not in other:
                        other[section] = {}
                    other[section].update(section_data)
        for section, section_data in kwargs.items():
            if section not in other:
                other[section] = {}
            other[section].update(section_data)
        for section, section_data in other.items():
            for key, value in section_data.items():
                self.set(section, key, value)

    def defaults(self):
        return {}

    def items(self, section: str = ..., raw=False, vars=None):
        if section is ...:
            return [(s, _SyncedConfigSection(self, s)) for s in self._values.keys()]
        if section not in self._values:
            raise configparser.NoSectionError(section)
        return [(k, str(v)) for k, v in self._values[section].items()]

    def __getitem__(self, section: str):
        if section not in self._values:
            raise KeyError(section)
        return _SyncedConfigSection(self, section)

    def __setitem__(self, section: str, value):
        raise TypeError(
            "Direct section assignment is not supported. "
            "Use config[section][key] = value or sweetviz.settings.override()."
        )

    def __delitem__(self, section: str):
        raise TypeError(
            "Deleting sections is not supported: sections are schema-managed."
        )

    def __contains__(self, section: str):
        return section in self._values

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values.keys())


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
        if isinstance(val, bool):
            return int(val)
        if not isinstance(val, int):
            raise TypeError(f"Config key '{key}' is not an int (got {type(val).__name__})")
        return val

    def getfloat(self, key: str) -> float:
        val = self[key]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
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
        self._load_from_ini()

    def _load_from_ini(self):
        ini_parser = configparser.ConfigParser()
        ini_file = pkg_resources.open_text("sweetviz", "sweetviz_defaults.ini")
        try:
            ini_parser.read_file(ini_file)
            _ingest_ini_to_values(
                ini_parser, self._schema, self._values,
                source_label="sweetviz_defaults.ini",
            )
        finally:
            ini_file.close()

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
            typed_value = _convert_value_to_type(value, meta["type"])
            if meta.get("validator"):
                typed_value = meta["validator"](typed_value)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid override value for [{section}] {key} = {value!r}: {e}"
            ) from e
        self._values[section][key] = typed_value

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
        return {k: v for k, v in self._values["Layout"].items()}

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


sv_config = SweetvizConfig()
config = _SyncedConfigParser(sv_config)
