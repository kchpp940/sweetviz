from decimal import Decimal
import html as html_module
import re
import hashlib
from textwrap import wrap as _textwrap_wrap
import numpy as np
try:
    from jinja2 import Markup
except ImportError:
    from markupsafe import Markup
from sweetviz.graph_associations import CORRELATION_ERROR, CORRELATION_IDENTICAL


def escape_for_html(value, max_len=None):
    if value is None:
        return ""
    text = str(value)
    text = html_module.escape(text, quote=True)
    text = text.replace("\n", "<br>")
    text = text.replace("\r", "")
    if max_len is not None and len(text) > max_len:
        text = text[:max_len] + "…"
    return Markup(text)


def _wrap_custom_graph_label(source_text, separator_chars, width, keep_separators=True):
    current_length = 0
    latest_separator = -1
    current_chunk_start = 0
    output = ""
    char_index = 0
    while char_index < len(source_text):
        if source_text[char_index] in separator_chars:
            latest_separator = char_index
        output += source_text[char_index]
        current_length += 1
        if current_length == width:
            if latest_separator >= current_chunk_start:
                cutting_length = char_index - latest_separator
                if not keep_separators:
                    cutting_length += 1
                if cutting_length:
                    output = output[:-cutting_length]
                output += "\n"
                current_chunk_start = latest_separator + 1
                char_index = current_chunk_start
            else:
                output += "\n"
                current_chunk_start = char_index + 1
                latest_separator = current_chunk_start - 1
                char_index += 1
            current_length = 0
        else:
            char_index += 1
    return output


class DisplayValue:
    def __init__(self, raw_value):
        self.raw = raw_value
        self._text = str(raw_value) if raw_value is not None else ""

    @property
    def plain_text(self):
        text = self._text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
        return text

    @property
    def html_text(self):
        return escape_for_html(self.raw)

    @property
    def display_key(self):
        text = self._text
        safe = re.sub(r'[^\w\-]', '_', text, flags=re.UNICODE)
        if len(safe) == 0:
            safe = "_empty_"
        if len(safe) > 40:
            h = hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
            safe = safe[:31] + "_" + h
        return safe

    def graph_label(self, max_len=None, wrap_len=None, break_chars=None, keep_break_chars=True):
        text = self.plain_text.replace("$", r"\$")
        if max_len is not None and len(text) > max_len:
            text = text[:max_len - 3] + "..."
        if wrap_len is not None and len(text) > wrap_len:
            if break_chars:
                text = _wrap_custom_graph_label(text, break_chars, wrap_len, keep_break_chars)
            else:
                text = "\n".join(_textwrap_wrap(text, wrap_len, break_long_words=True,
                                                break_on_hyphens=False))
        return text

    def __str__(self):
        return str(self.html_text)

    def __html__(self):
        return str(self.html_text)


def make_display_value(raw_value):
    return DisplayValue(raw_value)


def fmt_int_commas(value: float) -> str:
    return f"{value:,}"


def fmt_int_limit(value: float) -> str:
    # Use commas until 1 million, then "12.5M" etc.
    if value is None:
        # Support for empty fields
        return "---"
    if value > 999999:
        return f"{value/1000000:.1f}M"
    return f"{value:,}"


def fmt_assoc(value: float) -> str:
    if value == CORRELATION_IDENTICAL:
        value = 1.0
    if value == CORRELATION_ERROR:
        return "---"
    return f"{value:.2f}"


def fmt_percent_parentheses(value: float) -> str:
    # This returns the percentage as a rounded number. 100% is only used if truly 100%
    if value > 99.0 and value < 100.0:
        return "(>99%)"
    if  value < 1.0 and value > 0.0:
        return "(<1%)"
    rounded = round(value)
    return f"({rounded:.0f}%)"


def fmt_percent(value: float) -> str:
    # This returns the percentage as a rounded number. 100% is only used if truly 100%
    if value is None or np.isnan(value):
        # Support for empty fields
        return "---"
    if value < 1.0 and value > 0.0:
        return "<1%"
    if value > 99.0 and value < 100.0:
        return ">99%"
    rounded = round(value)
    return f"{rounded:.0f}%"


def fmt_percent1d(value: float) -> str:
    if value is None or np.isnan(value):
        return "---"
    if value < 0.1 and value > 0.0:
        return "<0.1%"
    if value > 99.9 and value < 100.0:
        return ">99.9%"
    return f"{value:.1f}%"


def fmt_smart(value: float) -> str:
    # Mainly used to shall average, etc. in the second column of numerical summary
    # Keep to ~5 display digits based on scale of input number
    if np.isnan(value):
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
    # Keep to ~5 display digits based on scale of input number
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
    # Keep to ~5 display digits based on scale given by range number
    if np.isnan(value):
        return "---"
    absolute_range = abs(range)
    if absolute_range == 0.0:
        return "0.00"
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
    # Used for graph labels
    # Keep to ~4 display digits based on scale given by range number
    if np.isnan(value):
        return "---"
    absolute_range = abs(range)
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
        # 99.9M
        return f"{value / 1000000.0:.1f}M"
    elif absolute_range < 999999999:
        return f"{value / 1000000.0:.0f}M"
    elif absolute_range < 99999999999:
        # 99.9B
        return f"{value / 1000000000.0:.1f}B"
    elif absolute_range < 999999999999:
        return f"{value / 1000000000.0:.0f}B"
    else :
        return f"{value / 1000000000000.0:.1f}T"

def fmt_div_color_override_missing(value: float) -> str:
    if value is None or np.isnan(value) or value <= 0:
        return Markup('')
    return Markup('style="color:#202020"')

def fmt_div_icon_missing(value: float) -> str:
    if value is None or np.isnan(value) or value <= 0:
        return Markup('')

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
    return Markup(returned)