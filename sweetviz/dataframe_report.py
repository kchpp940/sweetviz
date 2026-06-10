from typing import Union, List, Tuple, Optional, Dict
import os
import time
import math
import numbers
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from numpy import isnan
from tqdm.auto import tqdm

from sweetviz.sv_types import NumWithPercent, FeatureToProcess, FeatureType
import sweetviz.from_dython as associations
import sweetviz.series_analyzer as sa
import sweetviz.utils as su
from sweetviz.graph_associations import GraphAssoc
from sweetviz.graph_associations import CORRELATION_ERROR
from sweetviz.graph_associations import CORRELATION_IDENTICAL
from sweetviz.graph_legend import GraphLegend
from sweetviz.config import config
import sweetviz.comet_ml_logger as comet_ml_logger
import sweetviz.sv_html as sv_html
from sweetviz.feature_config import FeatureConfig
import webbrowser
from sweetviz.config import config

class DataframeReport:
    def __init__(self,
                 source: Union[pd.DataFrame, Tuple[pd.DataFrame, str]],
                 target_feature_name: str = None,
                 compare: Union[pd.DataFrame, Tuple[pd.DataFrame, str]] = None,
                 pairwise_analysis: str = 'auto',
                 fc: FeatureConfig = None,
                 verbosity: str = 'default'): # verbosity: default (full), full, progress_only, off
        # Parse analysis parameter
        pairwise_analysis = pairwise_analysis.lower()
        if pairwise_analysis not in ["on", "auto", "off"]:
            raise ValueError('"pairwise_analysis" parameter should be one of: "on", "auto", "off"')

        # Parse verbosity parameter
        if verbosity == "default":
            verbosity = config["General"]["default_verbosity"]
        if verbosity not in ["default", "full", "progress_only", "off"]:
            raise ValueError('"verbosity" parameter should be one of: "default", "full", "progress_only", "off"')
        self.verbosity_level = verbosity

        sv_html.load_layout_globals_from_config()

        self._jupyter_html = ""
        self._page_html = ""
        self._features = dict()
        self.compare_name = None
        self._target = None
        self.test_mode = False
        self.corr_warning = list()
        if fc is None:
            fc = FeatureConfig()

        # Associations: _associations[FEATURE][GIVES INFORMATION ABOUT THIS FEATURE]
        self._associations = dict()
        self._associations_compare = dict()
        self._association_graphs = dict()
        self._association_graphs_compare = dict()

        # Handle source and compare dataframes and names
        if type(source) == pd.DataFrame:
            source_df = source
            self.source_name = "DataFrame"
        elif type(source) == list or type(source) == tuple:
            if len(source) != 2:
                raise ValueError('"source" parameter should either be a string or a list of 2 elements: [dataframe, "Name"].')
            source_df = source[0]
            self.source_name = source[1]
        else:
            raise ValueError('"source" parameter should either be a string or a list of 2 elements: [dataframe, "Name"].')
        if len(su.get_duplicate_cols(source_df)) > 0:
            raise ValueError('Duplicate column names detected in "source"; this is not supported.')

        # NEW (12-14-2020): Rename indices that use the reserved name "index"
        # From pandas-profiling:
        # If the DataFrame contains a column or index named `index`, this will produce errors. We rename the {index,column} to be `df_index`.
        if 'index' in source_df.columns:
            source_df = source_df.rename(columns={"index": "df_index"})
            if target_feature_name == 'index':
                target_feature_name = 'df_index'

        all_source_names = [cur_name for cur_name, cur_series in source_df.items()]
        if compare is None:
            compare_df = None
            self.compare_name = None
            all_compare_names = list()
        elif type(compare) == pd.DataFrame:
            compare_df = compare
            if 'index' in compare_df.columns:
                compare_df = compare_df.rename(columns={"index": "df_index"})
            self.compare_name = "Compared"
            all_compare_names = [cur_name for cur_name, cur_series in compare_df.items()]
        elif type(compare) == list or type(compare) == tuple:
            if len(compare) != 2:
                raise ValueError('"compare" parameter should either be a string or a list of 2 elements: [dataframe, "Name"].')
            compare_df = compare[0]
            if 'index' in compare_df.columns:
                compare_df = compare_df.rename(columns={"index": "df_index"})
            self.compare_name = compare[1]
            all_compare_names = [cur_name for cur_name, cur_series in compare_df.items()]
        else:
            raise ValueError('"compare" parameter should either be a string or a list of 2 elements: [dataframe, "Name"].')

        # Validate some params
        if compare_df is not None and len(su.get_duplicate_cols(compare_df)) > 0:
            raise ValueError('Duplicate column names detected in "compare"; this is not supported.')


        if target_feature_name in fc.skip:
            raise ValueError(f'"{target_feature_name}" was also specified as "skip". Target cannot be skipped.')

        for key in fc.get_all_mentioned_features():
            if key not in all_source_names:
                raise ValueError(f'"{key}" was specified in "feature_config" but is not found in source dataframe (watch case-sensitivity?).')

        # Find Features and Target (FILTER SKIPPED)
        filtered_series_names_in_source = [cur_name for cur_name, cur_series in source_df.items()
                                           if cur_name not in fc.skip]
        for skipped in fc.skip:
            if skipped not in all_source_names and skipped not in all_compare_names:
                raise ValueError(f'"{skipped}" was marked as "skip" but is not in any provided dataframe (watch case-sensitivity?).')

        # Progress bar setup
        ratio_progress_of_df_summary_vs_feature = 1.0
        number_features = len(filtered_series_names_in_source)
        exponential_checks = number_features * number_features
        progress_chunks = ratio_progress_of_df_summary_vs_feature \
                            + number_features + (0 if target_feature_name is not None else 0)

        class DummyFile(object):
            def write(self, x):
                pass  # Do nothing
            def flush(self):
                pass  # Do nothing

        if self.verbosity_level in ('full', 'progress_only'):
            self.progress_bar = tqdm(total=progress_chunks, bar_format= \
                    '{desc:45}|{bar}| [{percentage:3.0f}%]   {elapsed} -> ({remaining} left)', \
                    ascii=False, dynamic_ncols=True, position=0, leave= True)
        else:
            # No progress bar, use dummy file
            self.progress_bar = tqdm(total=progress_chunks, bar_format= \
                    '{desc:45}|{bar}| [{percentage:3.0f}%]   {elapsed} -> ({remaining} left)', \
                    ascii=False, dynamic_ncols=True, position=0, leave= True, file=DummyFile())

        # Summarize dataframe
        self.progress_bar.set_description_str("[Summarizing dataframe]")
        self.summary_source = dict()
        self.summarize_dataframe(source_df, self.source_name, self.summary_source, fc.skip)
        # UPDATE 2021-02-05: Count the target as an actual feature!!! It is!!!
        # if target_feature_name:
        #     self.summary_source["num_columns"] = self.summary_source["num_columns"] - 1
        if compare_df is not None:
            self.summary_compare = dict()
            self.summarize_dataframe(compare_df, self.compare_name, self.summary_compare, fc.skip)
            cmp_not_in_src = \
                [name for name in all_compare_names if name not in all_source_names]
            self.summary_compare["num_cmp_not_in_source"] = len(cmp_not_in_src)
            # UPDATE 2021-02-05: Count the target has an actual feature!!! It is!!!
            # if target_feature_name:
            #     if target_feature_name in compare_df.columns:
            #         self.summary_compare["num_columns"] = self.summary_compare["num_columns"] - 1
        else:
            self.summary_compare = None
        self.progress_bar.update(ratio_progress_of_df_summary_vs_feature)

        self.num_summaries = number_features

        # Association check
        if pairwise_analysis == 'auto' and \
                number_features > config["Processing"].getint("association_auto_threshold"):
            print(f"PAIRWISE CALCULATION LENGTH WARNING: There are {number_features} features in "
                  f"this dataframe and the "
                  f"'pairwise_analysis' parameter is set to 'auto'.\nPairwise analysis is exponential in "
                  f"length: {number_features} features will cause ~"
                  f"{number_features * number_features} pairs to be "
                  f"evaluated, which could take a long time.\n\nYou must call the function with the "
                  f"parameter pairwise_analysis='on' or 'off' to explicitly select desired behavior."
                  )
            self.progress_bar.close()
            return

        # Validate and process TARGET
        target_to_process = None
        target_type = None
        if target_feature_name:
            # Make sure target exists
            self.progress_bar.set_description_str(f"Feature: {target_feature_name} (TARGET)")
            targets_found = [item for item in filtered_series_names_in_source
                             if item == target_feature_name]
            if len(targets_found) == 0:
                self.progress_bar.close()
                raise KeyError(f"Feature '{target_feature_name}' was "
                               f"specified as TARGET, but is NOT FOUND in "
                               f"the dataframe (watch case-sensitivity?).")

            # Make sure target has no nan's
            if source_df[targets_found[0]].isnull().values.any():
                self.progress_bar.close()
                raise ValueError(f"\nTarget feature '{targets_found[0]}' contains NaN (missing) values.\n"
                               f"To avoid confusion in interpreting target distribution,\n"
                               f"target features MUST NOT have any missing values at this time.\n")

            # Find Target in compared, if present
            compare_target_series = None
            if compare_df is not None:
                if target_feature_name in compare_df.columns:
                    if compare_df[target_feature_name].isnull().values.any():
                        self.progress_bar.close()
                        raise ValueError(
                            f"\nTarget feature '{target_feature_name}' in COMPARED data contains NaN (missing) values.\n"
                            f"To avoid confusion in interpreting target distribution,\n"
                            f"target features MUST NOT have any missing values at this time.\n")
                    compare_target_series = compare_df[target_feature_name]

            # TARGET processed HERE with COMPARE if present
            target_to_process = FeatureToProcess(-1, source_df[targets_found[0]], compare_target_series,
                                                 None, None, fc.get_predetermined_type(targets_found[0]))
            self._target = sa.analyze_feature_to_dictionary(target_to_process)
            filtered_series_names_in_source.remove(targets_found[0])
            target_type = self._target["type"]
            self.progress_bar.update(1)

        # Set final target series and sanitize targets (e.g. bool->truly bool)
        source_target_series = None
        compare_target_series = None
        if target_feature_name:
            if target_feature_name not in source_df.columns:
                raise ValueError
            if self._target["type"] == sa.FeatureType.TYPE_BOOL:
                source_target_series = self.get_sanitized_bool_series(source_df[target_feature_name])
            else:
                source_target_series = source_df[target_feature_name]

            if compare_df is not None:
                if target_feature_name in compare_df.columns:
                    if self._target["type"] == sa.FeatureType.TYPE_BOOL:
                        compare_target_series = self.get_sanitized_bool_series(compare_df[
                                                                                   target_feature_name])
                    else:
                        compare_target_series = compare_df[target_feature_name]

        # Create list of features to process
        features_to_process = []
        for cur_series_name, cur_order_index in zip(filtered_series_names_in_source,
                                                 range(0, len(filtered_series_names_in_source))):
            # TODO: BETTER HANDLING OF DIFFERENT COLUMNS IN SOURCE/COMPARE
            if compare_df is not None and cur_series_name in \
                    compare_df.columns:
                this_feat = FeatureToProcess(cur_order_index,
                                             source_df[cur_series_name],
                                             compare_df[cur_series_name],
                                             source_target_series,
                                             compare_target_series,
                                             fc.get_predetermined_type(cur_series_name),
                                             target_type)
            else:
                this_feat = FeatureToProcess(cur_order_index,
                                             source_df[cur_series_name],
                                             None,
                                             source_target_series,
                                             None,
                                             fc.get_predetermined_type(cur_series_name),
                                             target_type)
            features_to_process.append(this_feat)


        # Process columns -> features
        self.run_id = hex(int(time.time()))[2:] + "_" # removes the decimals
        # self.temp_folder = config["Files"].get("temp_folder")
        # os.makedirs(os.path.normpath(self.temp_folder), exist_ok=True)

        for f in features_to_process:
            # start = time.perf_counter()
            self.progress_bar.set_description_str(f"Feature: {f.source.name}")
            self._features[f.source.name] = sa.analyze_feature_to_dictionary(f)
            self.progress_bar.update(1)
            # print(f"DONE FEATURE------> {f.source.name}"
            #       f" {(time.perf_counter() - start):.2f}   {self._features[f.source.name]['type']}")
        # self.progress_bar.set_description_str('[FEATURES DONE]')
        # self.progress_bar.close()

        # Wrap up summary
        self.summarize_category_types(source_df, self.summary_source, fc.skip, self._target)
        if compare is not None:
            self.summarize_category_types(compare_df, self.summary_compare, fc.skip, self._target)
        self.dataframe_summary_html = sv_html.generate_html_dataframe_summary(self)

        self.graph_legend = GraphLegend(self)

        # Process all associations
        # ----------------------------------------------------
        # Put target first
        if target_to_process is not None:
            features_to_process.insert(0,target_to_process)

        if pairwise_analysis.lower() != 'off':
            self.progress_bar.reset(total=len(features_to_process))
            self.progress_bar.set_description_str("[Step 2/3] Processing Pairwise Features")
            self.process_associations(features_to_process, source_target_series, compare_target_series)

            self.progress_bar.reset(total=1)
            self.progress_bar.set_description_str("[Step 3/3] Generating associations graph")
            self.associations_html_source = True # Generated later in the process
            self.associations_html_compare = True # Generated later in the process
            self._association_graphs["all"] = GraphAssoc(self, "all", self._associations)
            self._association_graphs_compare["all"] = GraphAssoc(self, "all", self._associations_compare)
            self.progress_bar.set_description_str("Done! Use 'show' commands to display/save. ")
            self.progress_bar.update(1)
        else:
            self._associations = None
            self._associations_compare = None
            self.associations_html_source = None
            self.associations_html_compare = None
        self.progress_bar.close()

        self._report_data = self._build_report_data()
        return

    def verbose_print(self, *args, **kwargs):
        if self.verbosity_level == "full":
            print(*args, **kwargs)

    def __getitem__(self, key):
        # Can also access target
        if key in self._features.keys():
            return self._features[key]
        elif self._target is not None and key == self._target["name"]:
            return self._target
        else:
            return None

    def __setitem__(self, key, value):
        self._features[key] = value

    @staticmethod
    def get_predetermined_type(name: str,
                               feature_predetermined_types: dict):
        if feature_predetermined_types is None:
            return sa.FeatureType.TYPE_UNSUPPORTED
        return sa.FeatureType.TYPE_UNSUPPORTED

    @staticmethod
    def sanitize_bool(value) -> bool:
        if value is bool:
            return value
        elif isinstance(value, str):
            return value.lower() in ['true', '1', 't', 'y', 'yes', '1.0']
        elif isinstance(value, float) or isinstance(value, int):
            return bool(value)
        return False

    @staticmethod
    def get_sanitized_bool_series(source: pd.Series) -> pd.Series:
        # This casting due to nan's causing crashes
        series_only_with_booleans =  source.map(DataframeReport.sanitize_bool, na_action='ignore')
        return (series_only_with_booleans * 1).astype('Int64')

    def get_target_type(self) -> FeatureType:
        if self._target is None:
            return None
        return self._target["type"]

    def get_type(self, feature_name: str) -> FeatureType:
        if self._features.get(feature_name) is None:
            if self._target["name"] == feature_name:
                return self._target["type"]
            else:
                return None
        return self._features[feature_name].get("type")

    def  summarize_dataframe(self, source: pd.DataFrame, name: str, target_dict: dict, skip: List[str]):
        target_dict["name"] = name
        target_dict["num_rows"] = len(source)
        target_dict["num_columns"] = len(source.columns)
        target_dict["num_skipped_columns"] = len(source.columns) - len([x for x in source.columns if x not in skip])

        target_dict["memory_total"] = source.memory_usage(index=True, deep=True).sum()
        if target_dict["num_rows"] > 0:
            target_dict["memory_single_row"] = \
                float(target_dict["memory_total"]) / target_dict["num_rows"]
        else:
            target_dict["memory_single_row"] = 0

        target_dict["duplicates"] = NumWithPercent(sum(source.duplicated()), len(source))
        target_dict["num_cmp_not_in_source"] = 0 # set later, as needed

    def summarize_category_types(self, this_df: pd.DataFrame, dest_dict: dict, skip: List[str], \
            source_target_dict):
        dest_dict["num_cat"] = len([x for x in self._features.values()
                                        if (x["type"] == FeatureType.TYPE_CAT or x["type"] == FeatureType.TYPE_BOOL)
                                            and x["name"] not in skip and x["name"] in this_df])
        dest_dict["num_numerical"] = len([x for x in self._features.values()
                                                    if x["type"] == FeatureType.TYPE_NUM and x["name"] not in skip \
                                                        and x["name"] in this_df])
        dest_dict["num_text"] = len([x for x in self._features.values()
                                               if x["type"] == FeatureType.TYPE_TEXT and x["name"] not in skip \
                                                    and x["name"] in this_df])
        if source_target_dict is not None and source_target_dict["name"] in this_df:
            if source_target_dict["type"] == FeatureType.TYPE_NUM:
                dest_dict["num_numerical"] = dest_dict["num_numerical"] + 1
            elif source_target_dict["type"] == FeatureType.TYPE_CAT or source_target_dict["type"] == FeatureType.TYPE_BOOL:
                dest_dict["num_cat"] = dest_dict["num_cat"] + 1
        return

    def get_what_influences_me(self, feature_name: str) -> dict:
        influenced = dict()
        for cur_name, cur_associations in self._associations.items():
            if cur_name == feature_name:
                continue
            influence = cur_associations.get(feature_name)
            if influence is not None:
                influenced[cur_name] = influence
        return influenced

    # ----------------------------------------------------------------------------------------------
    # ASSOCIATIONS
    # ----------------------------------------------------------------------------------------------
    def process_associations(self, features_to_process: List[FeatureToProcess], source_target_series,
            compare_target_series):

        def mirror_association(association_dict, feature_name, other_name, value):
            if other_name not in association_dict.keys():
                association_dict[other_name] = dict()
            other_dict = association_dict[other_name]
            if feature_name not in other_dict.keys():
                other_dict[feature_name] = value

        for feature in features_to_process:
            feature_name = feature.source.name
            if feature_name not in self._associations.keys():
                self._associations[feature_name] = dict()

            cur_associations = self._associations[feature_name]
            if feature.compare is not None:
                if feature_name not in self._associations_compare.keys():
                    self._associations_compare[feature_name] = dict()
                cur_associations_compare = self._associations_compare[feature_name]
            else:
                cur_associations_compare = None

            for other in features_to_process:
            # for other in [of for of in features_to_process if of.source.name != feature_name]:
                process_compare = cur_associations_compare is not None and other.compare is not None
                # if other.source.name in cur_associations.keys():
                #     print(f"Skipping {feature_name} {other.source.name}")
                #     continue
                if other.source.name == feature_name:
                    cur_associations[other.source.name] = 0.0
                    mirror_association(self._associations, feature_name, other.source.name, 0.0)
                    if process_compare:
                        cur_associations_compare[other.source.name] = 0.0
                        mirror_association(self._associations_compare, feature_name, other.source.name, 0.0)
                    continue

                if self[feature_name]["type"] == FeatureType.TYPE_CAT or \
                    self[feature_name]["type"] == FeatureType.TYPE_BOOL:
                    # CAT/BOOL source
                    # ------------------------------------
                    if self[other.source.name]["type"] == FeatureType.TYPE_CAT or \
                            self[other.source.name]["type"] == FeatureType.TYPE_BOOL:
                        # CAT-CAT
                        cur_associations[other.source.name] = \
                            associations.theils_u(feature.source, other.source)
                        if process_compare:
                            cur_associations_compare[other.source.name] = \
                                associations.theils_u(feature.compare, other.compare)
                    elif self[other.source.name]["type"] == FeatureType.TYPE_NUM:
                        # CAT-NUM
                        # This handles cat-num, then mirrors so no need to process num-cat separately
                        # (symmetrical relationship)
                        cur_associations[other.source.name] = \
                            associations.correlation_ratio(feature.source, other.source)
                        mirror_association(self._associations, feature_name, other.source.name, \
                                           cur_associations[other.source.name])
                        if process_compare:
                            cur_associations_compare[other.source.name] = \
                                associations.correlation_ratio(feature.compare, other.compare)
                            mirror_association(self._associations_compare, feature_name, other.source.name, \
                                               cur_associations_compare[other.source.name])

                elif self[feature_name]["type"] == FeatureType.TYPE_NUM:
                    # NUM source
                    # ------------------------------------
                    if self[other.source.name]["type"] == FeatureType.TYPE_NUM:
                        # NUM-NUM
                        try:
                            cur_associations[other.source.name] = \
                                feature.source.corr(other.source, method='pearson')
                        except FloatingPointError:
                            # This usually happens when there is only 1 non-NaN value in each data series
                            # Assigning the value 1.0 as per
                            # https://stats.stackexchange.com/questions/94150/why-is-the-pearson-correlation-1-when-only-two-data-values-are-available
                            # -> Also showing a warning
                            cur_associations[other.source.name] = 1.0
                            self.corr_warning.append(feature_name + "/" + other.source.name)
                        # TODO: display correlation error better in graph!
                        if isnan(cur_associations[other.source.name]):
                            if feature.source.equals(other.source):
                                cur_associations[other.source.name] = CORRELATION_IDENTICAL
                            else:
                                # ERROR may occur if Nan's in one match values in other, and vice-versa
                                cur_associations[other.source.name] = CORRELATION_ERROR
                        mirror_association(self._associations, feature_name, other.source.name, \
                                           cur_associations[other.source.name])
                        if process_compare:
                            cur_associations_compare[other.source.name] = \
                                feature.compare.corr(other.compare, method='pearson')
                            # TODO: display correlation error better in graph!
                            if isnan(cur_associations_compare[other.source.name]):
                                if feature.compare.equals(other.compare):
                                    cur_associations_compare[other.source.name] = CORRELATION_IDENTICAL
                                else:
                                    # ERROR may occur if Nan's in one match values in other, and vice-versa
                                    cur_associations_compare[other.source.name] = CORRELATION_ERROR
                            mirror_association(self._associations_compare, feature_name, other.source.name, \
                                               cur_associations_compare[other.source.name])
            self.progress_bar.update(1)

    # ----------------------------------------------------------------------------------------------
    # OUTPUT
    # ----------------------------------------------------------------------------------------------
    def use_config_if_none(self, passed_value, config_name):
        if passed_value is None:
            return config["Output_Defaults"][config_name]
        return passed_value

    def generate_comet_friendly_html(self):
        # Enforce comet_ml-friendly layout and re-output report based on INI settings (comet_ml_Defaults)
        self.page_layout = config["comet_ml_defaults"]["html_layout"]
        self.scale = float(config["comet_ml_defaults"]["html_scale"])
        sv_html.set_summary_positions(self)
        sv_html.generate_html_detail(self)
        if self.associations_html_source:
            self.associations_html_source = sv_html.generate_html_associations(self, "source")
        if self.associations_html_compare:
            self.associations_html_compare = sv_html.generate_html_associations(self, "compare")
        self._page_html = sv_html.generate_html_dataframe_page(self)

    def show_html(self, filepath='SWEETVIZ_REPORT.html', open_browser=True, layout='widescreen', scale=None):
        scale = float(self.use_config_if_none(scale, "html_scale"))
        layout = self.use_config_if_none(layout, "html_layout")
        if layout not in ['widescreen', 'vertical']:
            raise ValueError(f"'layout' parameter must be either 'widescreen' or 'vertical'")
        sv_html.load_layout_globals_from_config()
        self.page_layout = layout
        self.scale = scale
        sv_html.set_summary_positions(self)
        sv_html.generate_html_detail(self)
        if self.associations_html_source:
            self.associations_html_source = sv_html.generate_html_associations(self, "source")
        if self.associations_html_compare:
            self.associations_html_compare = sv_html.generate_html_associations(self, "compare")
        self._page_html = sv_html.generate_html_dataframe_page(self)

        f = open(filepath, 'w', encoding="utf-8")
        f.write(self._page_html)
        f.close()
        if open_browser:
            self.verbose_print(f"Report {filepath} was generated! NOTEBOOK/COLAB USERS: the web browser MAY not pop up, regardless, the report IS saved in your notebook/colab files.")
            # Not sure how to work around this: not fatal but annoying...Notebook/colab
            # https://bugs.python.org/issue5993
            webbrowser.open('file://' + os.path.realpath(filepath))
        else:
            self.verbose_print(f"Report {filepath} was generated.")
        if len(self.corr_warning):
            print("---\nWARNING: one or more correlations had an edge-case/error and a 1.0 correlation was assigned\n"
                  "(likely due to only having a single row, containing non-NaN values for both correlated features)\n"
                  "Affected correlations:" + str(self.corr_warning))

        # Auto-log to comet_ml if desired & present
        self._comet_ml_logger = comet_ml_logger.CometLogger()
        if self._comet_ml_logger._logging:
            self.generate_comet_friendly_html()
            self._comet_ml_logger.log_html(self._page_html)
            self._comet_ml_logger.end()

    def show_notebook(self, w=None, h=None, scale=None, layout=None, filepath=None, file_layout=None, file_scale=None):
        w = self.use_config_if_none(w, "notebook_width")
        h = self.use_config_if_none(h, "notebook_height")
        scale = float(self.use_config_if_none(scale, "notebook_scale"))
        layout = self.use_config_if_none(layout, "notebook_layout")
        if layout not in ['widescreen', 'vertical']:
            raise ValueError(f"'layout' parameter must be either 'widescreen' or 'vertical'")

        sv_html.load_layout_globals_from_config()
        self.page_layout = layout
        self.scale = scale
        sv_html.set_summary_positions(self)
        sv_html.generate_html_detail(self)
        if self.associations_html_source:
            self.associations_html_source = sv_html.generate_html_associations(self, "source")
        if self.associations_html_compare:
            self.associations_html_compare = sv_html.generate_html_associations(self, "compare")
        self._page_html = sv_html.generate_html_dataframe_page(self)

        width=w
        height=h
        if str(height).lower() == "full":
            height = self.page_height

        # Output to iFrame
        import html
        self._page_html = html.escape(self._page_html)
        iframe = f' <iframe width="{width}" height="{height}" srcdoc="{self._page_html}" frameborder="0" allowfullscreen></iframe>'
        from IPython.display import display
        from IPython.display import HTML
        display(HTML(iframe))

        if filepath is not None:
            # We cannot just write out the same HTML as the notebook, as that one has been processed so as to
            # remove extraneous headings so it is nicely inserted into the notebook.
            # Instead, just do something similar to the "show_html()" code, but without its less-relevant printouts etc.
            # f = open(filepath, 'w', encoding="utf-8")
            # f.write(self._page_html)
            # f.close()
            scale = float(self.use_config_if_none(file_scale, "html_scale"))
            layout = self.use_config_if_none(file_layout, "html_layout")
            if layout not in ['widescreen', 'vertical']:
                raise ValueError(f"'layout' parameter for file output must be either 'widescreen' or 'vertical'")
            sv_html.load_layout_globals_from_config()
            self.page_layout = layout
            self.scale = scale
            sv_html.set_summary_positions(self)
            sv_html.generate_html_detail(self)
            if self.associations_html_source:
                self.associations_html_source = sv_html.generate_html_associations(self, "source")
            if self.associations_html_compare:
                self.associations_html_compare = sv_html.generate_html_associations(self, "compare")
            self._page_html = sv_html.generate_html_dataframe_page(self)

            f = open(filepath, 'w', encoding="utf-8")
            f.write(self._page_html)
            f.close()
            self.verbose_print(f"Report '{filepath}' was saved to storage.")

        if len(self.corr_warning):
            print("WARNING: one or more correlations had an edge-case/error and a 1.0 correlation was assigned\n"
                  "(likely due to only a single row containing non-NaN values for both correlated features)\n"
                  "Affected correlations:" + str(self.corr_warning))

        # Auto-log to comet_ml if desired & present
        self._comet_ml_logger = comet_ml_logger.CometLogger()
        if self._comet_ml_logger._logging:
            self.generate_comet_friendly_html()
            self._comet_ml_logger.log_html(self._page_html)
            self._comet_ml_logger.end()

    def log_comet(self, experiment: 'comet_ml_logger.Experiment'):
        self.generate_comet_friendly_html()
        try:
            experiment.log_html(self._page_html)
        except:
            print("log_comet(): error logging HTML report.")

    # ----------------------------------------------------------------------------------------------
    # REPORT DATA (stable structure built once after analysis)
    # ----------------------------------------------------------------------------------------------

    @staticmethod
    def _convert_value(val):
        if isinstance(val, NumWithPercent):
            return DataframeReport._nwp_to_dict(val)
        if isinstance(val, FeatureType):
            return val.value
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
            return {k: DataframeReport._convert_value(v) for k, v in val.items()}
        if isinstance(val, (list, tuple)):
            return [DataframeReport._convert_value(v) for v in val]
        if isinstance(val, (pd.Series, pd.DataFrame)):
            return None
        if val is None:
            return None
        return val

    @staticmethod
    def _nwp_to_dict(obj: NumWithPercent) -> Optional[Dict]:
        if obj is None:
            return None
        return {
            "number": DataframeReport._convert_value(obj.number),
            "percentage": DataframeReport._convert_value(obj.perc),
        }

    @staticmethod
    def _extract_base_stats(feature_dict: dict) -> dict:
        base_stats = feature_dict.get("base_stats", {})
        result = {}
        for k, v in base_stats.items():
            result[k] = DataframeReport._convert_value(v)
        if "num_missing" in result and result["num_missing"] is not None:
            missing_pct = result["num_missing"].get("percentage", 0)
            result["missing_rate"] = round(missing_pct, 2) if missing_pct is not None else 0.0
        else:
            result["missing_rate"] = 0.0
        return result

    @staticmethod
    def _extract_stats(feature_dict: dict) -> Optional[dict]:
        stats = feature_dict.get("stats")
        if stats is None or not stats:
            return None
        return DataframeReport._convert_value(stats)

    @staticmethod
    def _extract_details(feature_dict: dict, feature_type: FeatureType) -> Optional[dict]:
        detail = feature_dict.get("detail")
        if detail is None:
            return None
        result = {}
        cv = DataframeReport._convert_value
        if feature_type == FeatureType.TYPE_NUM:
            for key in ("frequent_values", "min_values", "max_values"):
                if key in detail:
                    converted = []
                    for item in detail[key]:
                        if isinstance(item, (list, tuple)):
                            entry = {"value": cv(item[0]), "count": cv(item[1])}
                            if len(item) > 2:
                                entry["count_compare"] = cv(item[2])
                            converted.append(entry)
                        elif isinstance(item, dict):
                            converted.append(cv(item))
                    result[key] = converted
        if feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL, FeatureType.TYPE_TEXT):
            full_count = detail.get("full_count", [])
            converted = []
            for row in full_count:
                if isinstance(row, dict) and not row.get("is_total"):
                    entry = {"name": cv(row.get("name")), "count": cv(row.get("count"))}
                    if row.get("count_compare") is not None:
                        entry["count_compare"] = cv(row.get("count_compare"))
                    converted.append(entry)
            cat_key = "top_categories" if feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL) else "top_values"
            result[cat_key] = converted
        return result if result else None

    @staticmethod
    def _extract_compare(feature_dict: dict) -> Optional[dict]:
        compare_dict = feature_dict.get("compare")
        if compare_dict is None:
            return None
        result = {}
        if "type" in compare_dict:
            result["type"] = compare_dict["type"].value
        if "base_stats" in compare_dict:
            result["base_stats"] = DataframeReport._extract_base_stats(compare_dict)
        if "stats" in compare_dict and compare_dict.get("stats"):
            result["stats"] = DataframeReport._extract_stats(compare_dict)
        return result

    @staticmethod
    def _extract_feature(feature_dict: dict) -> dict:
        feature_type = feature_dict.get("type")
        result = {
            "name": feature_dict.get("name"),
            "display_name": feature_dict.get("display_name", feature_dict.get("name")),
            "type": feature_type.value if feature_type else None,
            "is_target": feature_dict.get("is_target", False),
        }
        if "base_stats" in feature_dict:
            result["base_stats"] = DataframeReport._extract_base_stats(feature_dict)
        stats = DataframeReport._extract_stats(feature_dict)
        if stats:
            result["stats"] = stats
        details = DataframeReport._extract_details(feature_dict, feature_type)
        if details:
            result["details"] = details
        compare = DataframeReport._extract_compare(feature_dict)
        if compare:
            result["compare"] = compare
        if "drift" in feature_dict and feature_dict["drift"] is not None:
            result["drift"] = DataframeReport._convert_value(feature_dict["drift"])
        return result

    # ----------------------------------------------------------------------------------------------
    # DRIFT COMPUTATION
    # ----------------------------------------------------------------------------------------------

    @staticmethod
    def _compute_drift_numeric(source_stats: dict, compare_stats: dict,
                               source_base: dict, compare_base: dict) -> dict:
        details = {"base": {}, "numeric_stats": {}}
        total_score = 0.0
        reasons = []

        base_keys = ["num_values", "num_missing", "num_distinct", "num_zeroes"]
        for key in base_keys:
            src = source_base.get(key)
            cmp = compare_base.get(key)
            if src is None or cmp is None:
                continue
            src_num = src.get("number", 0) or 0
            cmp_num = cmp.get("number", 0) or 0
            src_pct = src.get("percentage", 0) or 0
            cmp_pct = cmp.get("percentage", 0) or 0
            diff_count = cmp_num - src_num
            diff_pct = cmp_pct - src_pct
            details["base"][key] = {
                "source": src, "compare": cmp,
                "diff_count": diff_count,
                "diff_pct_points": round(diff_pct, 4),
            }
            if abs(diff_pct) > 5:
                total_score += abs(diff_pct) * 0.5
                if key == "num_missing":
                    reasons.append("缺失率差异")

        if source_stats and compare_stats:
            numeric_keys = ["max", "perc95", "perc75", "mean", "perc50", "perc25", "perc5", "min",
                            "range", "iqr", "std", "variance", "kurtosis", "skewness", "sum"]
            for key in numeric_keys:
                if key not in source_stats or key not in compare_stats:
                    continue
                src_val = source_stats.get(key)
                cmp_val = compare_stats.get(key)
                if src_val is None or cmp_val is None:
                    continue
                if isinstance(src_val, float) and (math.isnan(src_val) or math.isinf(src_val)):
                    continue
                if isinstance(cmp_val, float) and (math.isnan(cmp_val) or math.isinf(cmp_val)):
                    continue
                diff = cmp_val - src_val
                if abs(src_val) > 1e-10:
                    diff_pct = (diff / abs(src_val)) * 100.0
                else:
                    diff_pct = 0.0 if diff == 0 else float('inf')
                details["numeric_stats"][key] = {
                    "source": src_val, "compare": cmp_val,
                    "diff": diff, "diff_pct": round(diff_pct, 4),
                }
                abs_diff_pct = abs(diff_pct)
                if key in ("std", "variance", "mean", "perc95", "iqr") and abs_diff_pct > 10:
                    total_score += min(abs_diff_pct, 50) * 0.3
                    if key == "std": reasons.append("标准差")
                    elif key == "mean": reasons.append("平均值")
                    elif key == "perc95": reasons.append("95%分位数")
                    elif key == "variance": reasons.append("方差")
                    elif key == "iqr": reasons.append("四分位距")

        score = round(min(total_score, 100), 1)
        severity = "high" if score >= 30 else "medium" if score >= 15 else "low" if score >= 5 else "none"
        return {"score": score, "severity": severity, "top_reasons": reasons[:3], "details": details}

    @staticmethod
    def _compute_drift_categorical(source_details: dict, compare_details: dict,
                                   source_base: dict, compare_base: dict,
                                   feature_type: FeatureType) -> dict:
        details = {"base": {}, "category_shifts": []}
        total_score = 0.0
        reasons = []

        base_keys = ["num_values", "num_missing", "num_distinct"]
        for key in base_keys:
            src = source_base.get(key)
            cmp = compare_base.get(key)
            if src is None or cmp is None:
                continue
            src_num = src.get("number", 0) or 0
            cmp_num = cmp.get("number", 0) or 0
            src_pct = src.get("percentage", 0) or 0
            cmp_pct = cmp.get("percentage", 0) or 0
            diff_count = cmp_num - src_num
            diff_pct = cmp_pct - src_pct
            details["base"][key] = {
                "source": src, "compare": cmp,
                "diff_count": diff_count,
                "diff_pct_points": round(diff_pct, 4),
            }
            if abs(diff_pct) > 5:
                total_score += abs(diff_pct) * 0.5
                if key == "num_missing":
                    reasons.append("缺失率差异")

        cat_key = "top_categories" if feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL) else "top_values"
        src_cats = {item.get("name"): item for item in (source_details or {}).get(cat_key, [])}
        cmp_cats = {item.get("name"): item for item in (compare_details or {}).get(cat_key, [])}

        for name in set(src_cats.keys()) | set(cmp_cats.keys()):
            src_item = src_cats.get(name)
            cmp_item = cmp_cats.get(name)
            src_count = src_item.get("count") if src_item else None
            cmp_count = cmp_item.get("count") if cmp_item else None
            src_num = src_count.get("number", 0) if src_count else 0
            cmp_num = cmp_count.get("number", 0) if cmp_count else 0
            src_pct = src_count.get("percentage", 0) if src_count else 0
            cmp_pct = cmp_count.get("percentage", 0) if cmp_count else 0
            diff_count = cmp_num - src_num
            diff_pct = cmp_pct - src_pct
            details["category_shifts"].append({
                "name": name,
                "source": src_count, "compare": cmp_count,
                "diff_count": diff_count,
                "diff_pct_points": round(diff_pct, 4),
            })
            if abs(diff_pct) > 5:
                total_score += abs(diff_pct) * 0.8
                cat_label = "类别" if feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL) else "值"
                reasons.append(f"{cat_label} '{name}' 占比差异")

        score = round(min(total_score, 100), 1)
        severity = "high" if score >= 30 else "medium" if score >= 15 else "low" if score >= 5 else "none"
        return {"score": score, "severity": severity, "top_reasons": reasons[:3], "details": details}

    def _compute_drift(self, feature_dict: dict) -> Optional[dict]:
        compare_dict = feature_dict.get("compare")
        if compare_dict is None:
            return None
        feature_type = feature_dict.get("type")
        source_base = self._extract_base_stats(feature_dict)
        compare_base = self._extract_base_stats(compare_dict)
        source_stats = self._extract_stats(feature_dict)
        compare_stats = self._extract_stats(compare_dict)
        source_details = self._extract_details(feature_dict, feature_type)
        if feature_type == FeatureType.TYPE_NUM:
            return self._compute_drift_numeric(source_stats, compare_stats, source_base, compare_base)
        elif feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL, FeatureType.TYPE_TEXT):
            compare_details = self._extract_details(compare_dict, feature_type)
            return self._compute_drift_categorical(source_details, compare_details, source_base, compare_base, feature_type)
        return None

    def _compute_all_drifts(self) -> None:
        if self.compare_name is None:
            return
        for fdict in self._features.values():
            if "drift" not in fdict or fdict["drift"] is None:
                fdict["drift"] = self._compute_drift(fdict)
        if self._target is not None and "drift" not in self._target:
            self._target["drift"] = self._compute_drift(self._target)

    def _compute_drift_summary(self) -> Optional[dict]:
        if self.compare_name is None:
            return None
        drift_scores = []
        for fname, fdict in self._features.items():
            drift = fdict.get("drift")
            if drift is not None:
                drift_scores.append({
                    "feature_name": fname,
                    "display_name": fdict.get("display_name", fname),
                    "score": drift.get("score", 0),
                    "severity": drift.get("severity", "none"),
                    "top_reasons": drift.get("top_reasons", []),
                })
        if self._target is not None and self._target.get("drift") is not None:
            drift_scores.append({
                "feature_name": self._target["name"],
                "display_name": self._target.get("display_name", self._target["name"]),
                "score": self._target["drift"].get("score", 0),
                "severity": self._target["drift"].get("severity", "none"),
                "top_reasons": self._target["drift"].get("top_reasons", []),
            })
        if not drift_scores:
            return None
        drift_scores.sort(key=lambda x: x["score"], reverse=True)
        scores = [d["score"] for d in drift_scores]
        severity_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
        for d in drift_scores:
            sev = d["severity"]
            if sev in severity_counts:
                severity_counts[sev] += 1
        return {
            "num_features": len(drift_scores),
            "average_score": round(sum(scores) / len(scores), 1),
            "max_score": max(scores),
            "severity_counts": severity_counts,
            "top_features": drift_scores,
        }

    def _build_report_data(self) -> dict:
        if self.compare_name is not None:
            self._compute_all_drifts()

        metadata = {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_name": self.source_name,
            "compare_name": self.compare_name,
        }
        try:
            import sweetviz
            metadata["sweetviz_version"] = sweetviz.__version__
        except (ImportError, AttributeError):
            pass

        source_summary = self._convert_value(self.summary_source)
        compare_summary = self._convert_value(self.summary_compare) if self.summary_compare else None

        features = {}
        for fname, fdict in self._features.items():
            features[fname] = self._extract_feature(fdict)

        target = None
        if self._target is not None:
            target = self._extract_feature(self._target)

        associations = self._convert_value(self._associations)
        associations_compare = self._convert_value(self._associations_compare)

        drift_summary = self._compute_drift_summary()

        result = {
            "metadata": metadata,
            "source_summary": source_summary,
            "features": features,
        }
        if target is not None:
            result["target"] = target
        if compare_summary is not None:
            result["compare_summary"] = compare_summary
        if associations is not None:
            result["associations"] = associations
        if associations_compare is not None:
            result["associations_compare"] = associations_compare
        if drift_summary is not None:
            result["drift_summary"] = drift_summary
        return result

    # ----------------------------------------------------------------------------------------------
    # PUBLIC API
    # ----------------------------------------------------------------------------------------------

    def get_report_data(self) -> dict:
        return self._report_data

    def to_json(self, filepath: str = None, indent: int = 2) -> str:
        from sweetviz.serialize import to_json
        return to_json(self._report_data, filepath=filepath, indent=indent)
