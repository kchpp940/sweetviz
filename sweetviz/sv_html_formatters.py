from decimal import Decimal
import numpy as np
from sweetviz.graph_associations import CORRELATION_ERROR
from sweetviz.graph_associations import CORRELATION_IDENTICAL
from sweetviz.utils import is_valid_finite


def _needs_marker(value) -> bool:
    return not is_valid_finite(value)


def fmt_int_commas(value: float) -> str:
    if _needs_marker(value):
        return "---"
    return f"{value:,}"


def fmt_int_limit(value: float) -> str:
    if _needs_marker(value):
        return "---"
    if value > 999999:
        return f"{value/1000000:.1f}M"
    return f"{value:,}"


def fmt_assoc(value: float) -> str:
    if value == CORRELATION_IDENTICAL:
        value = 1.0
    if value == CORRELATION_ERROR or _needs_marker(value):
        return "---"
    return f"{value:.2f}"


def fmt_percent_parentheses(value: float) -> str:
    if _needs_marker(value):
        return "(---)"
    if value > 99.0 and value < 100.0:
        return "(>99%)"
    if  value < 1.0 and value > 0.0:
        return "(<1%)"
    rounded = round(value)
    return f"({rounded:.0f}%)"


def fmt_percent(value: float) -> str:
    if _needs_marker(value):
        return "---"
    if value < 1.0 and value > 0.0:
        return "<1%"
    if value > 99.0 and value < 100.0:
        return ">99%"
    rounded = round(value)
    return f"{rounded:.0f}%"


def fmt_percent1d(value: float) -> str:
    if _needs_marker(value):
        return "---"
    if value < 0.1 and value > 0.0:
        return "<0.1%"
    if value > 99.9 and value < 100.0:
        return ">99.9%"
    return f"{value:.1f}%"


def fmt_smart(value: float) -> str:
    if _needs_marker(value):
        return "---"
    absolute = abs(value)
    if absolute == 0.0:
        return "0.00"
    elif absolute < 0.001:
        return f"{Decimal(float(value)):.2e}"
    elif absolute < 0.1:
        return f"{value:.3f}"
    elif absolute < 1.0:
        return f"{value:.3f}"
    elif absolute < 10:
        return f"{value:.2f}"
    elif absolute < 100:
        return f"{value:,.1f}"
    elif absolute < 99999:
        return f"{value:,.0f}"
    elif absolute < 999999:
        return f"{value/1000.0:.0f}k"
    elif absolute < 999999999:
        return f"{value / 1000000.0:.1f}M"
    elif absolute < 999999999999:
        return f"{value/1000000000.0:.1f}B"
    else:
        return f"{value/1000000000000.0:.1f}T"

def fmt_RAM(value: float) -> str:
    if _needs_marker(value):
        return "---"
    absolute = abs(value)
    if absolute < 1000:
        return f"{value:,.0f}b"
    elif absolute < 1000000:
        return f"{value/1000.0:,.1f} kb"
    elif absolute < 1000000000:
        return f"{value/1000000.0:,.1f} MB"
    else:
        return f"{value/1000000000.0:.1f} GB"

def fmt_smart_range(value: float, range: float) -> str:
    if _needs_marker(value):
        return "---"
    absolute_range = abs(range) if _needs_marker(range) == False else 0.0
    if absolute_range == 0.0:
        return fmt_smart(value)
    elif absolute_range < 0.001:
        return f"{value:.5f}"
    elif absolute_range < 0.1:
        return f"{value:.3f}"
    elif absolute_range < 1.0:
        return f"{value:.3f}"
    elif absolute_range < 10:
        return f"{value:.2f}"
    elif absolute_range < 100:
        return f"{value:,.1f}"
    elif absolute_range < 99999:
        return f"{value:,.0f}"
    elif absolute_range < 999999:
        return f"{value / 1000.0:.0f}k"
    elif absolute_range < 999999999:
        return f"{value / 1000000.0:.1f}M"
    elif absolute_range < 999999999999:
        return f"{value / 1000000000.0:.1f}B"
    else :
        return f"{value / 1000000000000.0:.1f}T"

def fmt_smart_range_tight(value: float, range: float) -> str:
    if _needs_marker(value):
        return "---"
    absolute_range = abs(range) if _needs_marker(range) == False else 0.0
    if absolute_range < 1.0:
        return f"{value:.3f}"
    elif absolute_range < 10:
        return f"{value:.2f}"
    elif absolute_range < 100:
        return f"{value:,.1f}"
    elif absolute_range < 4999:
        return f"{value:,.0f}"
    elif absolute_range < 99999:
        return f"{value / 1000.0:,.1f}k"
    elif absolute_range < 999999:
        return f"{value / 1000.0:.0f}k"
    elif absolute_range < 99999999:
        return f"{value / 1000000.0:.1f}M"
    elif absolute_range < 999999999:
        return f"{value / 1000000.0:.0f}M"
    elif absolute_range < 99999999999:
        return f"{value / 1000000000.0:.1f}B"
    elif absolute_range < 999999999999:
        return f"{value / 1000000000.0:.0f}B"
    else :
        return f"{value / 1000000000000.0:.1f}T"

def fmt_div_color_override_missing(value: float) -> str:
    if _needs_marker(value) or value <= 0:
        return ''
    return 'style="color:#202020"'

def fmt_div_icon_missing(value: float) -> str:
    if _needs_marker(value) or value <= 0:
        return ''

    returned = '<div class="'
    if value <= 15:
        returned += "ic-missing-green"
    elif value <= 50:
        returned += "ic-missing-yellow"
    elif value <= 75:
        returned += "ic-missing-orange"
    else:
        returned += "ic-missing-red"
    returned += '"></div>'
    return returned