import ast
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


def _parse_toml_string(s):
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        try:
            return ast.literal_eval(s)
        except Exception:
            return s[1:-1]
    return s


def _parse_toml_inline_table(s):
    s = s.strip()
    if not (s.startswith("{") and s.endswith("}")):
        return {}
    inner = s[1:-1].strip()
    if not inner:
        return {}
    result = {}
    for part in inner.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = _parse_toml_string(v.strip())
    return result


def _parse_minimal_toml(text):
    result = {}
    current_section = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.split("#", 1)[0].strip()
        if not line:
            i += 1
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            if current_section not in result:
                result[current_section] = {}
            i += 1
            continue
        if "=" in line and current_section is not None:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if val.startswith("["):
                while not val.endswith("]") and i + 1 < len(lines):
                    i += 1
                    nxt = lines[i].split("#", 1)[0].strip()
                    val += nxt
                    if nxt.endswith("]"):
                        break
                inner = val[1:-1].strip()
                arr = []
                if inner:
                    depth = 0
                    buf = ""
                    for ch in inner:
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                        if ch == "," and depth == 0:
                            arr.append(_parse_toml_inline_table(buf))
                            buf = ""
                        else:
                            buf += ch
                    if buf.strip():
                        arr.append(_parse_toml_inline_table(buf))
                result[current_section][key] = arr
            else:
                result[current_section][key] = _parse_toml_string(val)
        i += 1
    return result


def _extract_authors(data):
    authors = data.get("authors", [])
    if not authors:
        return ""
    parts = []
    for a in authors:
        name = a.get("name", "") if isinstance(a, dict) else ""
        email = a.get("email", "") if isinstance(a, dict) else ""
        if name and email:
            parts.append(f"{name} <{email}>")
        elif name:
            parts.append(name)
        elif email:
            parts.append(email)
    return ", ".join(parts)


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
                tomllib = None
        if tomllib is not None:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            project = data.get("project", {})
            return {
                "name": project.get("name", _DEFAULT_NAME),
                "version": project.get("version", _DEFAULT_VERSION),
                "author": _extract_authors(project),
            }
        with open(pyproject_path, "r", encoding="utf-8") as f:
            text = f.read()
        parsed = _parse_minimal_toml(text)
        project = parsed.get("project", {})
        name = project.get("name", _DEFAULT_NAME)
        version = project.get("version", _DEFAULT_VERSION)
        author = _extract_authors(project)
        if name != _DEFAULT_NAME or version != _DEFAULT_VERSION:
            return {
                "name": name,
                "version": version,
                "author": author,
            }
    except Exception:
        pass
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
