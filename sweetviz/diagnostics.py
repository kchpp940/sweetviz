"""
Sweetviz 内部诊断层
支持"每个报告/每次调用一个诊断上下文"，避免全局状态泄漏。

架构：
- DiagnosticManager: 可独立实例化的诊断管理器，每个报告持有一个实例
- 全局默认实例: 用于向后兼容的全局 API（set_verbosity/get_warnings 等）
- 便捷函数: 支持可选的 diag 参数，传入则使用指定实例，否则使用全局默认
"""

import sys
import traceback
from enum import Enum
from typing import Optional, List


class ErrorCategory(Enum):
    INPUT_DATA = "input_data"
    CONFIG = "config"
    RESOURCE = "resource"
    PROCESSING = "processing"
    INTERNAL = "internal"


class LogLevel(Enum):
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10
    SILENT = 100


class SweetvizError(Exception):
    """Sweetviz 所有自定义异常的基类。

    属性:
        category: 错误类别，帮助用户判断问题来源
        user_message: 用户可读的友好提示
        resolution: 建议的解决方案
        original_error: 原始异常（如果是包装的底层异常）
    """

    def __init__(self,
                 message: str,
                 category: ErrorCategory = ErrorCategory.INTERNAL,
                 user_message: Optional[str] = None,
                 resolution: Optional[str] = None,
                 original_error: Optional[Exception] = None):
        self.category = category
        self.user_message = user_message or message
        self.resolution = resolution
        self.original_error = original_error
        super().__init__(message)

    def __str__(self) -> str:
        parts = [f"[{self.category.value.upper()}] {self.user_message}"]
        if self.resolution:
            parts.append(f"\n建议解决方案: {self.resolution}")
        return "".join(parts)


class SweetvizInputError(SweetvizError, ValueError):
    """输入数据相关错误。

    例如：混合数据类型、目标列缺失、重复列名、空数据等。
    同时继承自 ValueError，保持向后兼容。
    """

    def __init__(self, message: str, resolution: Optional[str] = None,
                 original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.INPUT_DATA,
            user_message=message,
            resolution=resolution,
            original_error=original_error
        )


class SweetvizConfigError(SweetvizError, ValueError):
    """配置相关错误。

    例如：无效的参数值、不支持的布局模式、feature_config 中的错误等。
    同时继承自 ValueError，保持向后兼容。
    """

    def __init__(self, message: str, resolution: Optional[str] = None,
                 original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.CONFIG,
            user_message=message,
            resolution=resolution,
            original_error=original_error
        )


class SweetvizResourceError(SweetvizError, IOError):
    """资源缺失相关错误。

    例如：模板文件找不到、字体文件缺失、写入权限不足等。
    同时继承自 IOError，保持向后兼容。
    """

    def __init__(self, message: str, resolution: Optional[str] = None,
                 original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.RESOURCE,
            user_message=message,
            resolution=resolution,
            original_error=original_error
        )


class SweetvizProcessingError(SweetvizError, RuntimeError):
    """数据处理过程中的错误。

    例如：关联计算失败、序列化错误、图表生成错误等。
    同时继承自 RuntimeError，保持向后兼容。
    """

    def __init__(self, message: str, resolution: Optional[str] = None,
                 original_error: Optional[Exception] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.PROCESSING,
            user_message=message,
            resolution=resolution,
            original_error=original_error
        )


class WarningRecord:
    """记录一条 warning 的信息。"""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.PROCESSING,
                 feature_name: Optional[str] = None, resolution: Optional[str] = None):
        self.message = message
        self.category = category
        self.feature_name = feature_name
        self.resolution = resolution

    def __str__(self) -> str:
        prefix = f"[{self.category.value.upper()}]"
        if self.feature_name:
            prefix += f" [{self.feature_name}]"
        return f"{prefix} WARNING: {self.message}"


class DiagnosticManager:
    """Sweetviz 诊断管理器，集中处理日志和错误。

    每个 DataframeReport 持有一个独立的 DiagnosticManager 实例，
    确保 verbosity 设置和 warning 记录不会跨报告泄漏。

    同时存在一个全局默认实例，用于向后兼容的全局 API。
    """

    VERBOSITY_MAP = {
        "off": LogLevel.SILENT,
        "progress_only": LogLevel.ERROR,
        "full": LogLevel.INFO,
        "default": LogLevel.INFO,
    }

    def __init__(self, verbosity: str = "default"):
        """创建一个独立的诊断上下文。

        参数:
            verbosity: 初始 verbosity 级别 ("off", "progress_only", "full", "default")
        """
        self._verbosity: str = "default"
        self._log_level: LogLevel = LogLevel.INFO
        self._warnings: List[WarningRecord] = []
        self._errors: List[SweetvizError] = []
        self._progress_enabled: bool = True
        self._debug_enabled: bool = False
        self.set_verbosity(verbosity)

    def set_verbosity(self, verbosity: str) -> None:
        """设置 verbosity 级别，与原有参数兼容。

        只影响当前诊断上下文，不影响全局或其他报告。

        参数:
            verbosity: "off", "progress_only", "full", "default"
        """
        if verbosity == "default":
            from sweetviz.config import config
            verbosity = config["General"].get("default_verbosity", "full")

        if verbosity not in self.VERBOSITY_MAP:
            raise SweetvizConfigError(
                f"无效的 verbosity 值: '{verbosity}'",
                resolution="请使用以下值之一: 'off', 'progress_only', 'full', 'default'"
            )

        self._verbosity = verbosity
        self._log_level = self.VERBOSITY_MAP[verbosity]
        self._progress_enabled = verbosity in ("full", "progress_only", "default")

    def get_verbosity(self) -> str:
        return self._verbosity

    def is_progress_enabled(self) -> bool:
        return self._progress_enabled

    def set_debug(self, enabled: bool) -> None:
        """启用或禁用 debug 日志（只影响当前上下文）。"""
        self._debug_enabled = enabled

    def _should_log(self, level: LogLevel) -> bool:
        if level == LogLevel.DEBUG:
            return self._debug_enabled
        return level.value >= self._log_level.value

    def error(self, message: str, category: ErrorCategory = ErrorCategory.INTERNAL,
              feature_name: Optional[str] = None, resolution: Optional[str] = None,
              raise_exception: bool = False, exc_type: type = SweetvizError) -> SweetvizError:
        """记录错误，可选地抛出异常。"""
        error = exc_type(message=message, resolution=resolution)
        error.category = category
        self._errors.append(error)

        if self._should_log(LogLevel.ERROR):
            prefix = f"[{category.value.upper()}]"
            if feature_name:
                prefix += f" [{feature_name}]"
            print(f"{prefix} ERROR: {message}", file=sys.stderr)
            if resolution and self._log_level.value <= LogLevel.WARNING.value:
                print(f"  建议: {resolution}", file=sys.stderr)

        if raise_exception:
            raise error
        return error

    def warn(self, message: str, category: ErrorCategory = ErrorCategory.PROCESSING,
             feature_name: Optional[str] = None, resolution: Optional[str] = None) -> WarningRecord:
        """记录一条 warning。"""
        record = WarningRecord(
            message=message,
            category=category,
            feature_name=feature_name,
            resolution=resolution
        )
        self._warnings.append(record)

        if self._should_log(LogLevel.WARNING):
            prefix = f"[{category.value.upper()}]"
            if feature_name:
                prefix += f" [{feature_name}]"
            print(f"{prefix} WARNING: {message}")
            if resolution:
                print(f"  建议: {resolution}")

        return record

    def info(self, message: str, feature_name: Optional[str] = None) -> None:
        """输出信息级别的日志。"""
        if not self._should_log(LogLevel.INFO):
            return

        prefix = "[INFO]"
        if feature_name:
            prefix += f" [{feature_name}]"
        print(f"{prefix}: {message}")

    def debug(self, message: str, feature_name: Optional[str] = None) -> None:
        """输出 debug 级别的日志。

        需要先通过 set_debug(True) 启用。
        """
        if not self._should_log(LogLevel.DEBUG):
            return

        prefix = "[DEBUG]"
        if feature_name:
            prefix += f" [{feature_name}]"
        print(f"{prefix}: {message}")

    def get_warnings(self) -> List[WarningRecord]:
        """获取当前上下文所有记录的 warnings。"""
        return list(self._warnings)

    def get_errors(self) -> List[SweetvizError]:
        """获取当前上下文所有记录的错误。"""
        return list(self._errors)

    def clear(self) -> None:
        """清除当前上下文所有记录的警告和错误。"""
        self._warnings.clear()
        self._errors.clear()

    def wrap_exception(self, exc: Exception, category: ErrorCategory,
                       user_message: Optional[str] = None,
                       resolution: Optional[str] = None) -> SweetvizError:
        """将底层异常包装成 SweetvizError。"""
        message = user_message or str(exc)
        error_map = {
            ErrorCategory.INPUT_DATA: SweetvizInputError,
            ErrorCategory.CONFIG: SweetvizConfigError,
            ErrorCategory.RESOURCE: SweetvizResourceError,
            ErrorCategory.PROCESSING: SweetvizProcessingError,
            ErrorCategory.INTERNAL: SweetvizError,
        }
        exc_class = error_map.get(category, SweetvizError)
        return exc_class(
            message=message,
            resolution=resolution,
            original_error=exc
        )

    def print_warnings_summary(self) -> None:
        """输出警告摘要（如果有的话）。"""
        if not self._warnings or not self._should_log(LogLevel.WARNING):
            return

        count = len(self._warnings)
        print(f"\n--- 警告摘要: {count} 条警告 ---")
        for i, w in enumerate(self._warnings, 1):
            print(f"  {i}. {w}")
        print()

    def format_exception_for_user(self, exc: Exception) -> str:
        """格式化异常信息，提供用户友好的输出。"""
        if isinstance(exc, SweetvizError):
            return str(exc)

        return (
            f"处理过程中发生错误: {type(exc).__name__}\n"
            f"错误信息: {str(exc)}\n"
            f"如果问题持续存在，请检查输入数据和配置参数。"
        )


_default_diagnostic_manager: Optional[DiagnosticManager] = None


def get_default_diagnostic_manager() -> DiagnosticManager:
    """获取全局默认诊断管理器实例（用于向后兼容）。

    注意：新代码应该为每个报告创建独立的 DiagnosticManager 实例。
    """
    global _default_diagnostic_manager
    if _default_diagnostic_manager is None:
        _default_diagnostic_manager = DiagnosticManager()
    return _default_diagnostic_manager


def create_diagnostic_manager(verbosity: str = "default") -> DiagnosticManager:
    """创建一个新的、独立的诊断管理器实例。

    用于每次 analyze/compare 调用，确保上下文隔离。

    参数:
        verbosity: 初始 verbosity 级别

    返回:
        新的 DiagnosticManager 实例
    """
    return DiagnosticManager(verbosity=verbosity)


def _resolve_diag(diag: Optional[DiagnosticManager]) -> DiagnosticManager:
    """解析要使用的诊断管理器：优先使用传入的，否则使用全局默认。"""
    return diag if diag is not None else get_default_diagnostic_manager()


def set_verbosity(verbosity: str) -> None:
    """设置全局默认 verbosity 级别（向后兼容）。

    注意：这只会影响全局默认实例和未来未显式指定 verbosity 的报告。
    已创建的报告不会受到影响。
    """
    get_default_diagnostic_manager().set_verbosity(verbosity)


def get_verbosity() -> str:
    """获取全局默认 verbosity 级别（向后兼容）。"""
    return get_default_diagnostic_manager().get_verbosity()


def error(message: str, category: ErrorCategory = ErrorCategory.INTERNAL,
          feature_name: Optional[str] = None, resolution: Optional[str] = None,
          raise_exception: bool = False, exc_type: type = SweetvizError,
          diag: Optional[DiagnosticManager] = None) -> SweetvizError:
    """记录错误（向后兼容的全局 API）。

    参数:
        diag: 可选的诊断管理器实例，传入则使用该实例，否则使用全局默认
    """
    return _resolve_diag(diag).error(
        message, category, feature_name, resolution, raise_exception, exc_type
    )


def warn(message: str, category: ErrorCategory = ErrorCategory.PROCESSING,
         feature_name: Optional[str] = None, resolution: Optional[str] = None,
         diag: Optional[DiagnosticManager] = None) -> WarningRecord:
    """记录一条 warning（向后兼容的全局 API）。

    参数:
        diag: 可选的诊断管理器实例，传入则使用该实例，否则使用全局默认
    """
    return _resolve_diag(diag).warn(message, category, feature_name, resolution)


def info(message: str, feature_name: Optional[str] = None,
         diag: Optional[DiagnosticManager] = None) -> None:
    """输出信息级别的日志（向后兼容的全局 API）。

    参数:
        diag: 可选的诊断管理器实例，传入则使用该实例，否则使用全局默认
    """
    _resolve_diag(diag).info(message, feature_name)


def debug(message: str, feature_name: Optional[str] = None,
          diag: Optional[DiagnosticManager] = None) -> None:
    """输出 debug 级别的日志（向后兼容的全局 API）。

    参数:
        diag: 可选的诊断管理器实例，传入则使用该实例，否则使用全局默认
    """
    _resolve_diag(diag).debug(message, feature_name)


def set_debug(enabled: bool) -> None:
    """设置全局默认 debug 开关（向后兼容）。"""
    get_default_diagnostic_manager().set_debug(enabled)


def is_progress_enabled(diag: Optional[DiagnosticManager] = None) -> bool:
    """检查是否启用进度条（向后兼容的全局 API）。

    参数:
        diag: 可选的诊断管理器实例，传入则使用该实例，否则使用全局默认
    """
    return _resolve_diag(diag).is_progress_enabled()


def get_warnings(diag: Optional[DiagnosticManager] = None) -> List[WarningRecord]:
    """获取 warnings（向后兼容的全局 API）。

    参数:
        diag: 可选的诊断管理器实例，传入则使用该实例，否则使用全局默认
    """
    return _resolve_diag(diag).get_warnings()


def clear_diagnostics(diag: Optional[DiagnosticManager] = None) -> None:
    """清除诊断记录（向后兼容的全局 API）。

    参数:
        diag: 可选的诊断管理器实例，传入则清除该实例，否则清除全局默认
    """
    _resolve_diag(diag).clear()


def wrap_exception(exc: Exception, category: ErrorCategory,
                   user_message: Optional[str] = None,
                   resolution: Optional[str] = None,
                   diag: Optional[DiagnosticManager] = None) -> SweetvizError:
    """包装异常（向后兼容的全局 API）。

    参数:
        diag: 可选的诊断管理器实例，传入则使用该实例，否则使用全局默认
    """
    return _resolve_diag(diag).wrap_exception(exc, category, user_message, resolution)
