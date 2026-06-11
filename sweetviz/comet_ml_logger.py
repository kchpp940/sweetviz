_comet_available = None
_Experiment = None
_ImportError = None


def _ensure_comet():
    global _comet_available, _Experiment, _ImportError
    if _comet_available is not None:
        return _comet_available
    try:
        from comet_ml import Experiment
        _Experiment = Experiment
        _comet_available = True
    except ImportError as e:
        _ImportError = e
        _comet_available = False
    except Exception as e:
        _ImportError = e
        _comet_available = False
    return _comet_available


def is_comet_available():
    return _ensure_comet()


def get_comet_error():
    _ensure_comet()
    return _ImportError


def require_comet():
    if not _ensure_comet():
        raise ImportError(
            "comet_ml is required for this feature. "
            "Install it with: pip install sweetviz[comet] "
            "or pip install comet_ml>=3.0.0"
        ) from _ImportError


class CometLogger():
    def __init__(self):
        self._logging = False
        self._experiment = None
        if not _ensure_comet():
            return
        try:
            self._experiment = _Experiment(
                auto_metric_logging=False,
                display_summary_level=0
            )
            self._experiment.log_other("Created from", "sweetviz!")
            self._logging = True
        except Exception as e:
            print(
                "ERROR: comet_ml is installed, but not configured properly "
                "(e.g. check API key setup). HTML reports will not be uploaded. "
                f"Details: {e}"
            )

    def log_html(self, html_content):
        if self._logging:
            try:
                self._experiment.log_html(html_content)
            except Exception as e:
                print(f"comet_ml.log_html(): error occurred during call: {e}")
        else:
            if not is_comet_available():
                print(
                    "comet_ml.log_html(): comet_ml is not installed. "
                    "Install it with: pip install sweetviz[comet]"
                )
            else:
                print(
                    "comet_ml.log_html(): comet_ml is installed but not "
                    "configured properly (e.g. check API key setup)."
                )

    def end(self):
        if self._logging:
            try:
                self._experiment.end()
            except Exception as e:
                print(f"comet_ml.end(): error occurred during call: {e}")
        else:
            if not is_comet_available():
                print(
                    "comet_ml.end(): comet_ml is not installed. "
                    "Install it with: pip install sweetviz[comet]"
                )
