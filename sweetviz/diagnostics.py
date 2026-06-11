"""
Sweetviz 内部诊断层
集中处理用户可读错误、warning、debug 日志和静默模式。
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

    单例模式，全局共享一个实例。
    支持 verbosity 级别控制，与原有 verbosity 参数兼容。
    """

    _instance: Optional['DiagnosticManager'] = None

    VERBOSITY_MAP = {
        "off": LogLevel.SILENT,
        "progress_only": LogLevel.ERROR,
        "full": LogLevel.INFO,
        "default": LogLevel.INFO,
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._verbosity: str = "default"
        self._log_level: LogLevel = LogLevel.INFO
        self._warnings: List[WarningRecord] = []
        self._errors: List[SweetvizError] = []
        self._progress_enabled: bool = True
        self._debug_enabled: bool = False

    def set_verbosity(self, verbosity: str) -> None:
        """设置 verbosity 级别，与原有参数兼容。

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
        """启用或禁用 debug 日志。"""
        self._debug_enabled = enabled

    def _should_log(self, level: LogLevel) -> bool:
        if level == LogLevel.DEBUG:
            return self._debug_enabled
        return level.value >= self._log_level.value

    def error(self, message: str, category: ErrorCategory = ErrorCategory.INTERNAL,
              feature_name: Optional[str] = None, resolution: Optional[str] = None,
              raise_exception: bool = False, exc_type: type = SweetvizError) -> SweetvizError:
        """记录错误，可选地抛出异常。

        参数:
            message: 错误消息
            category: 错误类别
            feature_name: 相关的特征列名（如果适用）
            resolution: 建议的解决方案
            raise_exception: 是否立即抛出异常
            exc_type: 异常类型（默认为 SweetvizError）
        """
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
        """记录一条 warning。

        参数:
            message: warning 消息
            category: 警告类别
            feature_name: 相关的特征列名（如果适用）
            resolution: 建议的解决方案
        """
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
        """输出信息级别的日志。

        参数:
            message: 信息消息
            feature_name: 相关的特征列名（如果适用）
        """
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
        """获取所有记录的 warnings。"""
        return list(self._warnings)

    def get_errors(self) -> List[SweetvizError]:
        """获取所有记录的错误。"""
        return list(self._errors)

    def clear(self) -> None:
        """清除所有记录的警告和错误。"""
        self._warnings.clear()
        self._errors.clear()

    def wrap_exception(self, exc: Exception, category: ErrorCategory,
                       user_message: Optional[str] = None,
                       resolution: Optional[str] = None) -> SweetvizError:
        """将底层异常包装成 SweetvizError。

        参数:
            exc: 原始异常
            category: 错误类别
            user_message: 用户可读的消息（不提供则使用异常消息）
            resolution: 建议的解决方案
        """
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
        """格式化异常信息，提供用户友好的输出。

        对于 SweetvizError，展示分类和建议；
        对于其他异常，展示友好提示并隐藏技术细节。
        """
        if isinstance(exc, SweetvizError):
            return str(exc)

        return (
            f"处理过程中发生错误: {type(exc).__name__}\n"
            f"错误信息: {str(exc)}\n"
            f"如果问题持续存在，请检查输入数据和配置参数。"
        )


_diagnostic_manager: Optional[DiagnosticManager] = None


def get_diagnostic_manager() -> DiagnosticManager:
    """获取全局诊断管理器实例。"""
    global _diagnostic_manager
    if _diagnostic_manager is None:
        _diagnostic_manager = DiagnosticManager()
    return _diagnostic_manager


def set_verbosity(verbosity: str) -> None:
    """设置全局 verbosity 级别。"""
    get_diagnostic_manager().set_verbosity(verbosity)


def get_verbosity() -> str:
    """获取当前 verbosity 级别。"""
    return get_diagnostic_manager().get_verbosity()


def error(message: str, category: ErrorCategory = ErrorCategory.INTERNAL,
          feature_name: Optional[str] = None, resolution: Optional[str] = None,
          raise_exception: bool = False, exc_type: type = SweetvizError) -> SweetvizError:
    return get_diagnostic_manager().error(
        message, category, feature_name, resolution, raise_exception, exc_type
    )


def warn(message: str, category: ErrorCategory = ErrorCategory.PROCESSING,
         feature_name: Optional[str] = None, resolution: Optional[str] = None) -> WarningRecord:
    return get_diagnostic_manager().warn(message, category, feature_name, resolution)


def info(message: str, feature_name: Optional[str] = None) -> None:
    get_diagnostic_manager().info(message, feature_name)


def debug(message: str, feature_name: Optional[str] = None) -> None:
    get_diagnostic_manager().debug(message, feature_name)


def set_debug(enabled: bool) -> None:
    get_diagnostic_manager().set_debug(enabled)


def is_progress_enabled() -> bool:
    return get_diagnostic_manager().is_progress_enabled()


def get_warnings() -> List[WarningRecord]:
    return get_diagnostic_manager().get_warnings()


def clear_diagnostics() -> None:
    get_diagnostic_manager().clear()


def wrap_exception(exc: Exception, category: ErrorCategory,
                   user_message: Optional[str] = None,
                   resolution: Optional[str] = None) -> SweetvizError:
    return get_diagnostic_manager().wrap_exception(exc, category, user_message, resolution)
