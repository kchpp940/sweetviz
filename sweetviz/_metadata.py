from pathlib import Path

_DEFAULT_NAME = "sweetviz"
_DEFAULT_VERSION = "unknown"
_DEFAULT_AUTHOR = ""
_LICENSE = "MIT"


def _get_pyproject_path():
    return Path(__file__).resolve().parent.parent / "pyproject.toml"


def _load_from_importlib():
    try:
        try:
            from importlib.metadata import metadata
        except ImportError:
            from importlib_metadata import metadata
        dist = metadata("sweetviz")
        return {
            "name": dist.get("name", _DEFAULT_NAME),
            "version": dist.get("version", _DEFAULT_VERSION),
            "author": dist.get("Author-email", dist.get("Author", _DEFAULT_AUTHOR)),
        }
    except Exception:
        return None


def _load_from_pyproject():
    pyproject_path = _get_pyproject_path()
    if not pyproject_path.is_file():
        return None
    try:
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return None
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        project = data.get("project", {})
        authors = project.get("authors", [])
        author_str = ""
        if authors:
            parts = []
            for a in authors:
                name = a.get("name", "")
                email = a.get("email", "")
                if name and email:
                    parts.append(f"{name} <{email}>")
                elif name:
                    parts.append(name)
                elif email:
                    parts.append(email)
            author_str = ", ".join(parts)
        return {
            "name": project.get("name", _DEFAULT_NAME),
            "version": project.get("version", _DEFAULT_VERSION),
            "author": author_str,
        }
    except Exception:
        return None


def get_package_metadata():
    meta = _load_from_importlib()
    if meta is not None:
        return meta

    meta = _load_from_pyproject()
    if meta is not None:
        return meta

    return {
        "name": _DEFAULT_NAME,
        "version": _DEFAULT_VERSION,
        "author": _DEFAULT_AUTHOR,
    }


__all__ = ["get_package_metadata", "_LICENSE"]
