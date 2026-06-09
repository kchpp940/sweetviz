![version](https://img.shields.io/badge/2.3.2-blue.svg?label=version) ![updated](https://img.shields.io/badge/April%204%2C%202026-green.svg?label=updated)

### !!! April 2026 UPDATE !!! -  Version 2.3.2: Long-standing issues fixed

---
![Sweetviz Logo](docs/images/logo.png) 

_In-depth EDA **(target analysis, comparison, feature analysis, correlation)** in two lines of code!_

![Features](docs/images/features.png)

Sweetviz is an open-source Python library that generates beautiful, high-density visualizations to kickstart EDA (Exploratory Data Analysis) with just two lines of code. Output is a fully self-contained HTML application.

The system is built around quickly **visualizing target values** and **comparing datasets**. Its goal is to help quick analysis of target characteristics, training vs testing data, and other such data characterization tasks. 

Usage and parameters are described below, [you can also find an article describing its features in depth and see examples in action HERE](https://medium.com/data-science/powerful-eda-exploratory-data-analysis-in-just-two-lines-of-code-using-sweetviz-6c943d32f34).

**Sweetviz development is still ongoing!** Please let me know if you run into any data, compatibility or install issues! Thank you for [reporting any BUGS in the issue tracking system here](https://github.com/fbdesignpro/sweetviz/issues), and I welcome your feedback and questions on usage/features [in the brand-new GitHub "Discussions" tab right here!](https://github.com/fbdesignpro/sweetviz/discussions).

## Examples & mentions
[**Example HTML report** using the Titanic dataset](https://fbdesignpro.github.io/sweetviz/examples/SWEETVIZ_REPORT.html)

[**Example Notebook w/docs** on Colab (Jupyter/other notebooks should also work)](https://colab.research.google.com/drive/1-md6YEwcVGWVnQWTBirQSYQYgdNoeSWg?usp=sharing)

[**Medium Article** describing its features in depth](https://medium.com/data-science/powerful-eda-exploratory-data-analysis-in-just-two-lines-of-code-using-sweetviz-6c943d32f34)

KD Nugget articles:
[![KDNuggets](https://www.kdnuggets.com/images/tkb-2102-g.png)](https://www.kdnuggets.com/2021/02/powerful-exploratory-data-analysis-sweetviz.html) [![KDNuggets](https://www.kdnuggets.com/images/tkb-2103-g.png)](https://www.kdnuggets.com/2021/03/know-your-data-much-faster-sweetviz-python-library.html)

# Features
- **Target analysis** 
  - Shows how a target value (e.g. "Survived" in the Titanic dataset) relates to other features
- **Visualize and compare**
  - Distinct datasets (e.g. training vs test data)
  - Intra-set characteristics (e.g. male versus female)
- **Mixed-type associations**
  - Sweetviz integrates associations for numerical (Pearson's correlation), categorical (uncertainty coefficient) and categorical-numerical (correlation ratio) datatypes seamlessly, to provide maximum information for all data types.
- **Type inference**
  - Automatically detects numerical, categorical and text features, with optional manual overrides 
- **Summary information** 
  - Type, unique values, missing values, duplicate rows, most frequent values
  - Numerical analysis: 
    - min/max/range, quartiles, mean, mode, standard deviation, sum, median absolute deviation, coefficient of variation, kurtosis, skewness

## New & notable
- Version 2.2: Big compatibility update for python 3.7+ and numpy versions
- Version 2.1: **Comet.ml** support
- Version 2.0: **Jupyter, Colab & other notebook** support, report **scaling & vertical layout**  

_(see below for docs on these features)_

# Upgrading
Some people have experienced mixed results behavior upgrading through `pip`. To update to the latest from an existing install, it is recommended to `pip uninstall sweetviz` first, then simply install.

# Installation
Sweetviz currently supports Python 3.6+ and Pandas 0.25.3+. Reports are output using the base "os" module, so custom environments such as Google Colab which require custom file operations are not yet supported, although I am looking into a solution. 
## Using pip
The best way to install sweetviz (other than from source) is to use pip:
```
pip install sweetviz
```
#### Installation issues & fixes
In some rare cases, users have reported errors such as `ModuleNotFoundError: No module named 'sweetviz'` and `AttributeError: module 'sweetviz' has no attribute 'analyze'`.
In those cases, we suggest the following:
- Make sure none of your scripts are named `sweetviz.py`, as that interferes with the library itself. Delete or rename that script (and any associated `.pyc` files), and try again.
- Try uninstalling the library using `pip uninstall sweetviz`, then reinstalling
- The issue may stem from using multiple versions of Python, or from OS permissions. The following Stack Overflow articles have resolved many of these issues reported: [Article 1](https://stackoverflow.com/questions/32680081/importerror-after-successful-pip-installation/32680082), [Article 2](https://stackoverflow.com/questions/14295680/unable-to-import-a-module-that-is-definitely-installed), [Article 3](https://stackoverflow.com/questions/44528638/after-pip-successful-installed-modulenotfounderror) 
- If all else fails, post a bug issue [here on github](https://github.com/fbdesignpro/sweetviz/issues). Thank you for taking the time, it may help resolve the issue for you and everyone else!
# Basic Usage
Creating a report is a quick 2-line process:
1. Create a `DataframeReport` object using one of: `analyze()`, `compare()` or `compare_intra()`
2. Use a `show_xxx()` function to render the report. You can now use either **html** or **notebook** report options, as well as scaling: (more info on these options below)

![Report_Show_Options](docs/images/Layout-Anim3.gif) 

## Step 1: Create the report
There are 3 main functions for creating reports:
- analyze(...)
- compare(...)
- compare_intra(...)

#### Analyzing a single dataframe (and its optional target feature)
To analyze a single dataframe, simply use the `analyze(...)` function, then the `show_html(...)` function:
```
import sweetviz as sv

my_report = sv.analyze(my_dataframe)
my_report.show_html() # Default arguments will generate to "SWEETVIZ_REPORT.html"
```
When run, this will output a 1080p widescreen html app in your default browser:
![Widescreen demo](docs/images/demo_wide.png)
##### Optional arguments
The `analyze()` function can take multiple other arguments:
```
analyze(source: Union[pd.DataFrame, Tuple[pd.DataFrame, str]],
            target_feat: str = None,
            feat_cfg: FeatureConfig = None,
            pairwise_analysis: str = 'auto',
            verbosity: str = 'default'):
```
- **source:** Either the data frame (as in the example) or a tuple containing the data frame and a name to show in the report. 
e.g. `my_df` or `[my_df, "Training"]`
- **target_feat:** A string representing the name of the feature to be marked as "target". *Only BOOLEAN and NUMERICAL features can be targets for now.*
- **feat_cfg:** A FeatureConfig object representing features to be skipped, or to be forced a certain type in the analysis. The arguments can either be a single string or list of strings. Parameters are `skip`, `force_cat`, `force_num` and `force_text`. The "force_" arguments override the built-in type detection. They can be constructed as follows:
```
feature_config = sv.FeatureConfig(skip="PassengerId", force_text=["Age"])
```
- **verbosity:** **[NEW]** Can be set to `full`, `progress_only` (to only display the progress bar but not report generation messages) and `off` (fully quiet, except for errors or warnings). Default  verbosity can also be set in the INI override, under the "General" heading (see "The Config file" section below for details).
- **pairwise_analysis:** Correlations and other associations can take quadratic time (n^2) to complete. The default setting ("auto") will run without warning until a data set contains "association_auto_threshold" features. Past that threshold, you need to explicitly pass the parameter `pairwise_analysis="on"` (or `="off"`) since processing that many features would take a long time. This parameter also covers the generation of the association graphs (based on [Drazen Zaric's concept](https://towardsdatascience.com/better-heatmaps-and-correlation-matrix-plots-in-python-41445d0f2bec)):

![Pairwise sample](docs/images/pairwise.png)

#### Comparing two dataframes (e.g. Test vs Training sets)
To compare two data sets, simply use the `compare()` function. Its parameters are the same as `analyze()`, except with an inserted second parameter to cover the comparison dataframe. It is recommended to use the [dataframe, "name"] format of parameters to better differentiate between the base and compared dataframes. (e.g. `[my_df, "Train"]` vs `my_df`)
```
my_report = sv.compare([my_dataframe, "Training Data"], [test_df, "Test Data"], "Survived", feature_config)
```
#### Comparing two subsets of the same dataframe (e.g. Male vs Female)
Another way to get great insights is to use the comparison functionality to split your dataset into 2 sub-populations.

Support for this is built in through the `compare_intra()` function. This function takes a boolean series as one of the arguments, as well as an explicit "name" tuple for naming the (true, false) resulting datasets. Note that internally, this creates 2 separate dataframes to represent each resulting group. As such, it is more of a shorthand function of doing such processing manually.
```
my_report = sv.compare_intra(my_dataframe, my_dataframe["Sex"] == "male", ["Male", "Female"], "Survived", feature_config)
```
## Step 2: Show the report
Once you have created your report object (e.g. `my_report` in the examples above), simply pass it into one of the two `show' functions:

### show_html()
```
show_html(  filepath='SWEETVIZ_REPORT.html', 
            open_browser=True, 
            layout='widescreen', 
            scale=None,
            export_json=None,
            export_json_path=None)
```            
**show_html(...)** will create and save an HTML report at the given file path. There are options for:
- **layout**: Either `'widescreen'` or `'vertical'`. The widescreen layout displays details on the right side of the screen, as the mouse goes over each feature. The new (as of 2.0) vertical layout is more compact horizontally and enables expanding each detail area upon clicking.
- **scale**: Use a floating-point number (e.g. `scale = 0.8` or `None`) to scale the entire report. This is very useful to fit reports to any output.
- **open_browser**: Enables the automatic opening of a web browser to show the report. Since under some circumstances this is not desired (or causes issues with some IDE's), you can disable it here.
- **export_json**: When set to `True`, also exports a JSON metadata file alongside the HTML report. When `None` (default), follows the config file setting. When `False`, explicitly disables JSON export even if configured in the INI file.
- **export_json_path**: An optional explicit file path for the JSON metadata file. If not provided, defaults to the same directory/base name as the HTML file with `.json` extension.

### JSON Metadata Export
Sweetviz can also export structured report metadata as JSON, which is useful for programmatic analysis, CI pipelines, and further data processing. The JSON output contains:

- **Top-level metadata**: `schema_version`, `generated_at` (ISO timestamp), `source_name`, `compare_name`
- **Dataframe summaries**: row counts, column counts, memory usage, duplicates, type distributions
- **Per-feature information**: field types, missing rates, unique value counts, top categories, numerical statistics (min/max/mean/std/quartiles/etc.)
- **Associations/correlations**: pairwise association results between features
- **Drift summaries (compare mode)**: unified drift schema aligned with HTML display, covering:
  - `base`: num_values, num_missing, num_distinct, num_zeroes (each with `source`, `compare`, `diff_count`, `diff_pct_points`)
  - `numeric_stats`: all HTML-displayed stats (max, perc95, perc75, mean, perc50, perc25, perc5, min, range, iqr, std, variance, kurtosis, skewness, sum) each with `source`, `compare`, `diff`, `diff_pct`
  - `category_shifts`: per-category count/percentage differences

There are three ways to get JSON metadata:

#### 1. Export alongside HTML via parameter
```python
my_report = sv.analyze(my_dataframe)
my_report.show_html(export_json=True)
# Generates: SWEETVIZ_REPORT.html + SWEETVIZ_REPORT.json

# Or specify a custom JSON path
my_report.show_html(export_json=True, export_json_path='/custom/path/metadata.json')
```

#### 2. Direct JSON export
```python
my_report = sv.analyze(my_dataframe)
my_report.export_json('my_report_metadata.json')
```

#### 3. Get as Python dict or JSON string
```python
my_report = sv.analyze(my_dataframe)

# Get as a Python dictionary
metadata_dict = my_report.to_dict()

# Get as a JSON string
json_str = my_report.to_json(indent=2)
```

#### 4. Enable globally via config
Add this to your override INI file to auto-export JSON every time:
```ini
[Output_Defaults]
export_json_metadata = 1
json_metadata_indent = 2
```

#### JSON Structure Example (fixed schema)
All fields below are **always present** regardless of `analyze` vs `compare` mode. Optional data is expressed as `null` or empty collections, never by omitting the key.

```json
{
  "metadata": {
    "schema_version": "1.0",
    "generated_at": "2026-06-09T12:00:00+00:00",
    "source_name": "Train",
    "compare_name": "Test"
  },
  "source_summary": {
    "name": "Train",
    "num_rows": 712,
    "num_columns": 12,
    "num_skipped_columns": 0,
    "memory_total": 77294,
    "memory_single_row": 108,
    "duplicates": {"number": 0, "percentage": 0.0},
    "num_cat": 5,
    "num_numerical": 6,
    "num_text": 0,
    "num_cmp_not_in_source": null
  },
  "compare_summary": {
    "name": "Test",
    "num_rows": 179,
    "num_columns": 11,
    "num_skipped_columns": 0,
    "memory_total": 18987,
    "memory_single_row": 106,
    "duplicates": {"number": 0, "percentage": 0.0},
    "num_cat": 4,
    "num_numerical": 6,
    "num_text": 0,
    "num_cmp_not_in_source": 1
  },
  "target": {
    "name": "Survived",
    "type": "CATEGORICAL",
    "is_target": true,
    "base_stats": {
      "total_rows": 712,
      "num_values": {"number": 712, "percentage": 100.0},
      "num_missing": {"number": 0, "percentage": 0.0},
      "missing_rate": 0.0,
      "num_zeroes": {"number": 424, "percentage": 59.55},
      "num_distinct": {"number": 2, "percentage": 0.28}
    },
    "stats": {
      "max": null, "perc95": null, "perc75": null, "mean": null, "perc50": null,
      "perc25": null, "perc5": null, "min": null, "range": null, "iqr": null,
      "std": null, "variance": null, "kurtosis": null, "skewness": null, "sum": null
    },
    "details": {
      "top_categories": [
        {"name": 0, "count": {"number": 424, "percentage": 59.55}, "count_compare": {"number": 65, "percentage": 63.11}},
        {"name": 1, "count": {"number": 288, "percentage": 40.45}, "count_compare": {"number": 38, "percentage": 36.89}}
      ],
      "frequent_values": [],
      "min_values": [],
      "max_values": []
    },
    "compare": {
      "type": "CATEGORICAL",
      "base_stats": {
        "total_rows": 103,
        "num_values": {"number": 103, "percentage": 100.0},
        "num_missing": {"number": 0, "percentage": 0.0},
        "missing_rate": 0.0,
        "num_zeroes": {"number": 65, "percentage": 63.11},
        "num_distinct": {"number": 2, "percentage": 1.94}
      },
      "stats": {
        "max": null, "perc95": null, "perc75": null, "mean": null, "perc50": null,
        "perc25": null, "perc5": null, "min": null, "range": null, "iqr": null,
        "std": null, "variance": null, "kurtosis": null, "skewness": null, "sum": null
      }
    },
    "drift": {
      "score": 3.56,
      "severity": "low",
      "top_reasons": ["类别 '0' 占比差异"],
      "details": { ... }
    }
  },
  "features": {
    "Age": {
      "name": "Age",
      "type": "NUMERIC",
      "is_target": false,
      "base_stats": {
        "total_rows": 712,
        "num_values": {"number": 572, "percentage": 80.34},
        "num_missing": {"number": 140, "percentage": 19.66},
        "missing_rate": 19.66,
        "num_zeroes": {"number": 0, "percentage": 0.0},
        "num_distinct": {"number": 88, "percentage": 12.36}
      },
      "stats": {
        "max": 80.0, "perc95": 58.0, "perc75": 38.0, "mean": 29.70, "perc50": 28.0,
        "perc25": 20.0, "perc5": 6.0, "min": 0.42, "range": 79.58, "iqr": 18.0,
        "std": 14.53, "variance": 211.0, "kurtosis": 0.17, "skewness": 0.39, "sum": 17000.5
      },
      "details": {
        "top_categories": [],
        "frequent_values": [
          {"value": 24.0, "count": {"number": 30, "percentage": 4.21}, "count_compare": null}
        ],
        "min_values": [
          {"value": 0.42, "count": {"number": 1, "percentage": 0.14}, "count_compare": null}
        ],
        "max_values": [
          {"value": 80.0, "count": {"number": 1, "percentage": 0.14}, "count_compare": null}
        ]
      },
      "compare": {
        "type": "NUMERIC",
        "base_stats": {
          "total_rows": 179,
          "num_values": {"number": 151, "percentage": 84.36},
          "num_missing": {"number": 28, "percentage": 15.64},
          "missing_rate": 15.64,
          "num_zeroes": {"number": 0, "percentage": 0.0},
          "num_distinct": {"number": 63, "percentage": 35.20}
        },
        "stats": {
          "max": 76.0, "perc95": 62.0, "perc75": 40.0, "mean": 31.2, "perc50": 29.0,
          "perc25": 22.0, "perc5": 8.0, "min": 0.83, "range": 75.17, "iqr": 18.0,
          "std": 14.8, "variance": 219.0, "kurtosis": 0.08, "skewness": 0.31, "sum": 4711.2
        }
      },
      "drift": {
        "score": 12.4,
        "severity": "medium",
        "top_reasons": ["标准差", "平均值", "缺失率差异"],
        "details": {
          "base": {
            "num_values": {
              "source": {"number": 572, "percentage": 80.34},
              "compare": {"number": 151, "percentage": 84.36},
              "diff_count": -421,
              "diff_pct_points": 4.02
            }
          },
          "numeric_stats": {
            "mean": {
              "source": 29.70, "compare": 31.2,
              "diff": 1.5, "diff_pct": 5.05
            }
          },
          "category_shifts": []
        }
      }
    },
    "Sex": {
      "name": "Sex",
      "type": "CATEGORICAL",
      "is_target": false,
      "base_stats": {
        "total_rows": 712,
        "num_values": {"number": 712, "percentage": 100.0},
        "num_missing": {"number": 0, "percentage": 0.0},
        "missing_rate": 0.0,
        "num_zeroes": {"number": 0, "percentage": 0.0},
        "num_distinct": {"number": 2, "percentage": 0.28}
      },
      "stats": {
        "max": null, "perc95": null, "perc75": null, "mean": null, "perc50": null,
        "perc25": null, "perc5": null, "min": null, "range": null, "iqr": null,
        "std": null, "variance": null, "kurtosis": null, "skewness": null, "sum": null
      },
      "details": {
        "top_categories": [
          {"name": "male", "count": {"number": 468, "percentage": 65.73}, "count_compare": {"number": 109, "percentage": 60.89}},
          {"name": "female", "count": {"number": 244, "percentage": 34.27}, "count_compare": {"number": 70, "percentage": 39.11}}
        ],
        "frequent_values": [],
        "min_values": [],
        "max_values": []
      },
      "compare": {
        "type": "CATEGORICAL",
        "base_stats": {
          "total_rows": 179,
          "num_values": {"number": 179, "percentage": 100.0},
          "num_missing": {"number": 0, "percentage": 0.0},
          "missing_rate": 0.0,
          "num_zeroes": {"number": 0, "percentage": 0.0},
          "num_distinct": {"number": 2, "percentage": 1.12}
        },
        "stats": {
          "max": null, "perc95": null, "perc75": null, "mean": null, "perc50": null,
          "perc25": null, "perc5": null, "min": null, "range": null, "iqr": null,
          "std": null, "variance": null, "kurtosis": null, "skewness": null, "sum": null
        }
      },
      "drift": {
        "score": 4.84,
        "severity": "low",
        "top_reasons": ["类别 'male' 占比差异", "类别 'female' 占比差异"],
        "details": {
          "category_shifts": [
            {
              "name": "male",
              "source": {"number": 468, "percentage": 65.73},
              "compare": {"number": 109, "percentage": 60.89},
              "diff_count": -359,
              "diff_pct_points": -4.84
            }
          ]
        }
      }
    }
  },
  "associations": {
    "Survived": {"Pclass": 0.34, "Sex": 0.54, "Age": -0.08},
    "Pclass": {"Survived": 0.34, "Sex": 0.12, "Age": 0.37}
  },
  "associations_compare": {
    "Survived": {"Pclass": 0.31, "Sex": 0.51, "Age": -0.05}
  },
  "drift_summary": {
    "num_features": 11,
    "average_score": 8.2,
    "max_score": 15.7,
    "severity_counts": {"high": 1, "medium": 3, "low": 5, "none": 2},
    "top_features": [
      {"feature_name": "Fare", "score": 15.7, "severity": "high", "top_reasons": ["标准差", "平均值"]},
      {"feature_name": "Age", "score": 12.4, "severity": "medium", "top_reasons": ["标准差", "平均值", "缺失率差异"]}
    ]
  }
}
```

**Notes on schema stability:**
- In `analyze()` mode (no compare): `compare_summary` is still present (all values `null`), every feature's `compare` is `null`, and `drift_summary` is present with `num_features=0` and empty counts/top_features.
- The `stats` dict inside each feature always has 15 keys (matching HTML numeric display). For non-numeric features all values are `null`.
- `associations` and `associations_compare` are always `{}` (empty dict) when pairwise analysis is disabled, never `null` or omitted.

### show_notebook()
```
show_notebook(  w=None, 
                h=None, 
                scale=None,
                layout='widescreen',
                filepath=None,
                file_layout=None,
                file_scale=None,
                export_json=None,
                export_json_path=None)
```            
**show_notebook(...)** is new as of 2.0 and will embed an IFRAME element showing the report right inside a notebook (e.g. Jupyter, Google Colab, etc.). 

Note that since notebooks are generally a more constrained visual environment, it is probably a good idea to use custom width/height/scale values (`w`, `h`, `scale`) and even **set custom default values in an INI override** (see below). The options are:
- **w** (width): Sets the width of the output _window_ for the report (the full report may not fit; use `layout` and/or `scale` for the report itself). Can be as a percentage string (`w="100%"`) or number of pixels (`w=900`).
- **h** (height): Sets the height of the output _window_ for the report. Can be as a number of pixels (`h=700`) or "Full" to stretch the window to be as tall as all the features (`h="Full"`).
- **scale**: Same as for `show_html()`, above.
- **layout**: Same as for `show_html()`, above.
- **filepath**: An OPTIONAL output HTML report.
- **file_layout**: Layout for the OPTIONAL file output ONLY (same as `layout` for `show_html()`, above)
- **file_scale**: Scale for the OPTIONAL file output ONLY (same as `scale` for `show_html()`, above)
- **export_json**: When `filepath` is provided and this is set to `True`, also exports JSON metadata alongside the file. When `None` (default), follows the config file setting. When `False`, explicitly disables JSON export.
- **export_json_path**: An optional explicit file path for the JSON metadata file (only used when `filepath` is also provided). If not provided, defaults to same name as HTML file with `.json` extension.
# Customizing defaults: the Config file
The package contains an INI file for configuration. You can override any setting by providing your own then calling this before creating a report:
```
sv.config_parser.read("Override.ini")
```
**IMPORTANT #1:** it is best to load overrides **before any other command**, as many of the INI options are used in the report generation.  

**IMPORTANT #2:** always **put the header line** (e.g. `[General]`) before a set of values in your override INI file, **otherwise your settings will be ignored**. See examples below. If setting multiple values, only include the `[General]` line once.


### Most useful config overrides
You can look into the file `sweetviz_defaults.ini` for what can be overriden (warning: much of it is a work in progress and not well documented), but the most useful overrides are as follows.

#### Default report layout, size
Override any of these (by putting them in your own INI, again do not forget the header), to avoid having to set them every time you do a "show" command:

**Important**: note the double '%' if specifying a percentage
```
[Output_Defaults]
html_layout = widescreen
html_scale = 1.0
notebook_layout = vertical
notebook_scale = 0.9
notebook_width = 100%%
notebook_height = 700
```

##### Chinese, Japanse, Korean (CJK) character support
```
[General]
use_cjk_font = 1 
```
*\*If setting multiple values for `[general]` only include the `[General]` line once*.

Will switch the font in the graphs to use a CJK-compatible font. Although this font is not as compact, it will get rid of any warnings and "unknown character" symbols for these languages.
##### Remove Sweetviz logo
```
[Layout]
show_logo = 0
```
Will remove the Sweetviz logo from the top of the page. 

##### Set default verbosity level
```
[General]
default_verbosity = off 
```
*\*If setting multiple values for `[general]` only include the `[General]` line once*.

Can be set to `full`, `progress_only` (to only display the progress bar but not report generation messages) and `off` (fully quiet, except for errors or warnings).

# Correlation/Association analysis
A major source of insight and unique feature of Sweetviz' associations graph and analysis is that **it unifies in a single graph** (and detail views):
 - Numerical correlation (between numerical features)
 - Uncertainty coefficient (for categorical-categorical)
 - Correlation ratio (for categorical-numerical)
![Pairwise sample](docs/images/pairwise.png)

 Squares represent categorical-featured-related variables and circles represent numerical-numerical correlations. Note that the trivial diagonal is left empty, for clarity.
 
IMPORTANT: categorical-categorical associations (provided by the SQUARES showing the uncertainty coefficient) are ASSYMMETRICAL, meaning that each row represents **how much the row title (on the left) gives information on each column**. _For example, "Sex", "Pclass" and "Fare" are the elements that give the most information on "Survived"._ 

For the Titanic dataset, this information is rather symmetrical but it is not always the case!

Correlations are also displayed in the detail section of each feature, with the target value highlighted when applicable. e.g.:

![Associations detail](docs/images/associations_detail.PNG)

Finally, it is worth noting these correlation/association methods shouldn’t be taken as gospel as they make some assumptions on the underlying distribution of data and relationships. However they can be a _very_ useful starting point.

# Comet.ml integration
As of 2.1, Sweetviz now fully integrates [Comet.ml](https://www.comet.ml). This means Sweetviz will **automatically log any reports generated** using `show_html()` and `show_notebook()` to your workspace, as long as your API key is set up correctly in your environment.

Additionally, you can also use the new function `report.log_comet(experiment_object)` to explicitly upload a report for a given experiment to your workspace.

You can see an example of a [Colab notebook](https://colab.research.google.com/drive/1SK1I-gU6nLchesbMtFD9ZuzJHyzleFAr?usp=sharing) to generate the report, and its corresponding report in a [Comet.ml workspace](https://www.comet.ml/fbdesignpro/sweetviz-comet/d005158117c24924b07476887cd5ddfa?experiment-tab=html).

## Comet report parameters
You can customize how the Sweetviz report looks in your Comet workspace by overriding the `[comet_ml_defaults]` section of configuration file. See above for more information on using the INI override.

You can choose to use either the `widescreen` (horizontal) or `vertical` layouts, as well as set your preferred scale, by putting the following in your override INI file:
```
[comet_ml_defaults]
html_layout = vertical
html_scale = 0.85
```

# Troubleshooting / FAQ
- **Installation issues**

Please see the "Installation issues & fixes" section at the top of this document
- **Asian characters, "RuntimeWarning: Glyph ### missing from current font"**

See section above regarding CJK characters support. If you find the need for additional character types, definitely [post a request in the issue tracking system.](https://github.com/fbdesignpro/sweetviz/issues)

- **...any other issues**

Development is ongoing so absolutely feel free to report any issues and/or suggestions [in the issue tracking system here](https://github.com/fbdesignpro/sweetviz/issues) or [in our forum (you should be able to log in with your Github account!)](https://sweetviz.fbdesignpro.com)

# Contribute
This is my first open-source project! I built it to be the most useful tool possible and help as many people as possible with their data science work. If it is useful to you, your contribution is more than welcome and can take many forms:
### 1. Spread the word!
A STAR here on GitHub, and a Twitter or Instagram post are the easiest contribution and can potentially help grow this project tremendously! If you find this project useful, these quick actions from you would mean a lot and could go a long way. 

Kaggle notebooks/posts, Medium articles, YouTube video tutorials and other content take more time but will help all the more!

### 2. Report bugs & issues
I expect there to be many quirks once the project is used by more and more people with a variety of new (& "unclean") data. If you found a bug, please [open a new issue here](https://github.com/fbdesignpro/sweetviz/issues).

### 3. Suggest and discuss usage/features
To make Sweetviz as useful as possible we need to hear what you would like it to do, or what it could do better! [Head on to our Discourse server and post your suggestions there; no login required!](https://sweetviz.fbdesignpro.com).

### 4. Contribute to the development
I definitely welcome the help I can get on this project, simply get in touch on the issue tracker and/or our Discourse forum. 

Please note that after a hectic development period, the code itself right now needs a bit of cleanup. :)

# Special thanks & related materials
### Contributors
**A very special thanks to everyone who have contributed on Github, through reports, feedback and commits!** I want to give a special shout out to **Frank Male** who has been of tremendous help for fixing issues and setting up the new build pipeline for 2.2.0.

[![Contributors](https://contrib.rocks/image?repo=fbdesignpro/sweetviz)](https://github.com/fbdesignpro/sweetviz/graphs/contributors)

Made with [contrib.rocks](https://contrib.rocks).
### Related materials
I want Sweetviz to be a hub of the best of what's out there, a way to get the most valuable information and visualization, without reinventing the wheel.

As such, I want to point some of those great resources that were inspiring and integrated into Sweetviz:
- [Pandas-Profiling](https://github.com/pandas-profiling/pandas-profiling) was the original inspiration for this project. Some of its type-detection code was included in Sweetviz.
- [Shaked Zychlinski: The Search for Categorical Correlation](https://towardsdatascience.com/the-search-for-categorical-correlation-a1cf7f1888c9) is a great article about different types of variable interactions that was the basis of that analysis in Sweetviz.
- [Drazen Zaric: Better Heatmaps and Correlation Matrix Plots in Python](https://towardsdatascience.com/better-heatmaps-and-correlation-matrix-plots-in-python-41445d0f2bec) was the basis for our association graphs.

