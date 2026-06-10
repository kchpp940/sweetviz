from enum import Enum, unique
from dataclasses import dataclass, field
import json
import pandas as pd


# Adding spaces to avoid collisions: this should NEVER be in a dataset :)
OTHERS_GROUPED = "     (Other)"


@dataclass
class FileOutputOptions:
    enabled: bool = False
    filepath: str = None
    layout: str = "widescreen"
    scale: float = 1.0


@dataclass
class RenderOptions:
    layout: str = "widescreen"
    scale: float = 1.0
    page_height: int = 0
    show_logo: bool = True
    use_cjk_font: bool = False
    association_min_to_bold: float = 0.1

    collapse_details: bool = False
    open_features: list = field(default_factory=list)
    hide_associations: bool = False

    iframe_width: str = None
    iframe_height: str = None

    file_output: FileOutputOptions = field(default_factory=FileOutputOptions)

    def to_dict(self) -> dict:
        return {
            'layout': self.layout,
            'scale': self.scale,
            'page_height': self.page_height,
            'show_logo': self.show_logo,
            'use_cjk_font': self.use_cjk_font,
            'association_min_to_bold': self.association_min_to_bold,
            'collapse_details': self.collapse_details,
            'open_features': list(self.open_features) if self.open_features else [],
            'hide_associations': self.hide_associations,
        }

    def to_json(self, for_script_tag: bool = True) -> str:
        data = self.to_dict()
        json_str = json.dumps(data, ensure_ascii=False)
        if for_script_tag:
            json_str = json_str.replace('</', '<\\/')
        return json_str

    def validate(self):
        if self.layout not in ['widescreen', 'vertical']:
            raise ValueError(
                f"'layout' parameter must be either 'widescreen' or 'vertical', got '{self.layout}'")
        if self.scale <= 0:
            raise ValueError(
                f"'scale' parameter must be positive, got {self.scale}")
        if not isinstance(self.open_features, list):
            raise ValueError(
                f"'open_features' parameter must be a list of column names, got {type(self.open_features)}")
        if self.file_output.enabled:
            if self.file_output.filepath is None:
                raise ValueError("file_output.filepath must be set when file_output.enabled is True")
            if self.file_output.layout not in ['widescreen', 'vertical']:
                raise ValueError(
                    f"file_output.layout must be either 'widescreen' or 'vertical', got '{self.file_output.layout}'")
            if self.file_output.scale <= 0:
                raise ValueError(
                    f"file_output.scale must be positive, got {self.file_output.scale}")

@unique
class FeatureType(Enum):
    TYPE_CAT = "CATEGORICAL"
    TYPE_BOOL = "BOOL"
    TYPE_NUM = "NUMERIC"
    TYPE_TEXT = "TEXT"
    TYPE_UNSUPPORTED = "UNSUPPORTED"
    TYPE_ALL_NAN = "ALL_NAN"
    TYPE_UNKNOWN = "UNKNOWN"
    TYPE_SKIPPED = "SKIPPED"
    def __str__(self):
        return "TYPE_" + str(self.value)

class NumWithPercent:
    def __init__(self, number, total_for_percentage):
        # Meant to be very flexible, negative numbers are allowed etc.
        if total_for_percentage == 0:
            self.number = None
            self.perc = None
            # raise ValueError
        else:
            self.number = number
            self.perc = 100.0 * number / total_for_percentage

    def __int__(self):
        return self.number

    def __float__(self):
        return float(self.number)

    def __repr__(self):
        if self.number is not None:
            return f"{self.number} ({self.perc:.2f}%)"
        else:
            return "[INVALID]"

class FeatureToProcess:
    def __init__(self, order: int, source: pd.Series, compare=None, source_target=None,
                 compare_target=None, predetermined_type: FeatureType = None,
                 predetermined_type_target: FeatureType = None):
        self.order = order

        # Cleanup names
        source.name = str(source.name)
        if compare is not None:
            compare.name = str(compare.name)
        if source_target is not None:
            source_target.name = str(source_target.name)
        if compare_target is not None:
            compare_target.name = str(compare_target.name)

        self.source = source
        self.source_counts = None
        self.source_target  = source_target

        self.compare = compare
        self.compare_counts = None
        self.compare_target = compare_target

        if predetermined_type:
            self.predetermined_type = predetermined_type
        else:
            self.predetermined_type = FeatureType.TYPE_UNKNOWN

        # Validate TARGET type
        if predetermined_type_target:
            if predetermined_type_target not in (FeatureType.TYPE_BOOL,
                                                 FeatureType.TYPE_NUM):
                if predetermined_type_target == FeatureType.TYPE_CAT:
                    raise ValueError("TARGET values can only be of NUMERICAL or BOOLEAN type for now.\n"
                                     "CATEGORICAL type was detected; if you meant the target to be\n"
                                     "NUMERICAL, use a FeatureConfig(force_num=...) object.")
                else:
                    raise ValueError("TARGET values can only be of NUMERICAL or BOOLEAN type for now.")
            self.predetermined_type_target = predetermined_type_target
        else:
            self.predetermined_type_target = FeatureType.TYPE_UNKNOWN

    def is_target(self):
        return self.order == -1

    def __repr__(self):
        out = str()
        if self.source is not None:
            out = out + f"Src: {self.source.name} "
            if self.source_target is not None:
                out = out + f"(Target: {self.source_target.name}) "
        if self.compare is not None:
            out = out + f"[WITH COMPARISON]"
        return out
