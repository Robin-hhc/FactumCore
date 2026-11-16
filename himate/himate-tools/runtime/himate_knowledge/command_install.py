"""Install and check the user command without binding a knowledge group."""

import ast
import os
from pathlib import Path
import shlex
import shutil
import stat
import sys
import tempfile

from .protocol import NodeError as CommandError, envelope, relative_to_existing_root


DISPATCHER = "knowledge-dispatch.py"
DISPATCH_PREFIX = '''"""Launch the installed HiMate tool with the caller's knowledge selection."""
import sys
def normalized(value):
    value = value.replace("\\\\", "/").rstrip("/")
    return value.casefold() if sys.platform == "win32" else value
prefixes = tuple(normalized(p) for p in {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix} if p)
sys.path[:] = [p for p in sys.path if p and any(normalized(p) == base or normalized(p).startswith(base + "/") for base in prefixes)]
import subprocess
''' + 'raise SystemExit(subprocess.call([sys.executable, "-B", '
DISPATCH_SUFFIX = ", *sys.argv[1:]]))\n"
WINDOWS_PREFIX = '@echo off\r\n"'
WINDOWS_SUFFIX = '" -B "%~dp0knowledge-dispatch.py" %*\r\nexit /b %errorlevel%\r\n'
POSIX_PREFIX = "#!/bin/sh\nexec "
POSIX_SUFFIX = ' -B "$(dirname -- "$0")/knowledge-dispatch.py" "$@"\n'


def _bin_directory(bin_dir):
    if bin_dir:
        return Path(bin_dir).expanduser().absolute()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))).absolute() / "HiMate/bin"
    return Path.home() / ".local/bin"


def _launcher_name():
    return "knowledge.cmd" if os.name == "nt" else "knowledge"


def _launcher_text(python):
    if os.name == "nt":
        return WINDOWS_PREFIX + python.replace("%", "%%") + WINDOWS_SUFFIX
    return POSIX_PREFIX + shlex.quote(python) + POSIX_SUFFIX


def _command_files(destination, tool_root):
    dispatch = DISPATCH_PREFIX + repr(str(tool_root / "knowledge.py")) + DISPATCH_SUFFIX
    return {
        destination / DISPATCHER: dispatch.encode("utf-8"),
        destination / _launcher_name(): _launcher_text(sys.executable).encode("utf-8"),
    }


def _linked(metadata):
    return stat.S_ISLNK(metadata.st_mode) or (
        getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _validate_directory(destination, tool_root, knowledge_root=None):
    for path in (destination, *destination.parents):
        try:
            if _linked(path.lstat()):
                raise CommandError("LINKED_OUTPUT", "Command directory must not be linked", path)
        except FileNotFoundError:
            pass
        if ((path / "governance/sources.lock.yaml").is_file()
                or ((path / "docs-raw").is_dir() and (path / "knowledge").is_dir())):
            raise CommandError("COMMAND_INSIDE_KNOWLEDGE", "Install the command outside every knowledge repository", path)
    resolved = destination.resolve()
    if relative_to_existing_root(resolved, tool_root) is not None:
        raise CommandError("COMMAND_INSIDE_TOOL", "Install the command outside the tool package", destination)
    if knowledge_root is not None and relative_to_existing_root(resolved, knowledge_root) is not None:
        raise CommandError("COMMAND_INSIDE_KNOWLEDGE", "Install the command outside the knowledge repository", destination)


def _read_command_file(path):
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    if _linked(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise CommandError("COMMAND_EXISTS", "Existing command files are preserved", path)
    if metadata.st_size > 32 * 1024:
        return b""
    return path.read_bytes()


def _owned_file(path, raw):
    """Accept exact HiMate launcher formats, including the pre-upgrade pair."""
    try:
        value = raw.decode("utf-8")
        if path.name == DISPATCHER:
            if not value.startswith(DISPATCH_PREFIX) or not value.endswith(DISPATCH_SUFFIX):
                return False
            entry = ast.literal_eval(value[len(DISPATCH_PREFIX):-len(DISPATCH_SUFFIX)])
            if not isinstance(entry, str) or not Path(entry).is_absolute() or Path(entry).name != "knowledge.py":
                return False
            return value == DISPATCH_PREFIX + repr(entry) + DISPATCH_SUFFIX

        prefix, suffix = (WINDOWS_PREFIX, WINDOWS_SUFFIX) if os.name == "nt" else (POSIX_PREFIX, POSIX_SUFFIX)
        if not value.startswith(prefix) or not value.endswith(suffix):
            return False
        runtime = value[len(prefix):-len(suffix)]
        if os.name == "nt":
            return Path(runtime).is_absolute() and not any(char in runtime for char in '"\r\n')
        parts = shlex.split(runtime)
        return len(parts) == 1 and Path(parts[0]).is_absolute() and value == _launcher_text(parts[0])
    except (UnicodeError, ValueError, SyntaxError):
        return False


def _path_key(path):
    return os.path.normcase(os.path.normpath(path))


def _resolved_command(launcher):
    found = shutil.which("knowledge")
    if not found:
        return False, None
    if _path_key(Path(found).resolve()) == _path_key(launcher):
        return True, None
    return False, found


def _notify_user_path_changed():
    from ctypes import c_void_p, c_wchar_p, cast, windll
    from ctypes.wintypes import HWND, UINT, WPARAM

    # WM_SETTINGCHANGE lets Explorer refresh its environment for new terminals.
    settings = c_wchar_p("Environment")
    windll.user32.SendMessageTimeoutW(
        HWND(0xFFFF), UINT(0x001A), WPARAM(0), cast(settings, c_void_p),
        UINT(0x0002), UINT(250), None,
    )


def _user_path(destination, *, add=False):
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            current, kind = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        current, kind = "", winreg.REG_EXPAND_SZ
    registered = _path_key(destination) in {
        _path_key(winreg.ExpandEnvironmentStrings(part.strip().strip('"')))
        for part in current.split(";") if part.strip()
    }
    if add and not registered:
        updated = ";".join(filter(None, (current.rstrip(";"), str(destination))))
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            winreg.SetValueEx(key, "Path", 0, kind, updated)
        _notify_user_path_changed()
        return True
    return registered


def inspect_command(tool_root, bin_dir=None):
    """Inspect the pinned launcher and PATH without changing either."""
    destination = _bin_directory(bin_dir)
    _validate_directory(destination, tool_root)
    paths = _command_files(destination, tool_root)
    launcher = destination / _launcher_name()
    installed = all(_read_command_file(path) == expected for path, expected in paths.items())
    if installed and os.name != "nt":
        installed = os.access(launcher, os.X_OK)
    registered = os.name == "nt" and _user_path(destination)
    if os.name == "nt" and bin_dir is None:
        installed = installed and registered
    on_path, shadowed_by = _resolved_command(launcher)
    if bin_dir is None and shadowed_by:
        installed = False
    return {"path": str(launcher), "bin_dir": str(destination), "dispatcher": str(destination / DISPATCHER),
            "installed": installed, "path_registered": bool(registered),
            "on_path": on_path, "shadowed_by": shadowed_by}


def _write_command_file(path, payload, previous, executable):
    if previous == payload:
        if executable and not os.access(path, os.X_OK):
            path.chmod(0o755)
        return

    stream = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            stream.write(payload)
        if executable:
            temporary.chmod(0o755)
        if previous is None:
            # Publish complete bytes without overwriting a concurrent install.
            if os.name == "nt":
                temporary.rename(path)
            else:
                os.link(temporary, path)
        else:
            if _read_command_file(path) != previous:
                raise CommandError("COMMAND_EXISTS", "The installed command changed during deployment", path)
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def deploy_command(tool_root, bin_dir=None, *, knowledge_root=None, add_path=False):
    if add_path and os.name != "nt":
        raise CommandError("PATH_REGISTRATION_UNAVAILABLE", "Add the command directory to your shell PATH explicitly")
    destination = _bin_directory(bin_dir)
    _validate_directory(destination, tool_root, knowledge_root)
    if bin_dir is None:
        _, shadowed_by = _resolved_command(destination / _launcher_name())
        if shadowed_by:
            raise CommandError("COMMAND_PATH_CONFLICT", "A different knowledge command takes precedence on PATH", shadowed_by)
    files = _command_files(destination, tool_root)
    previous = {}
    for path, payload in files.items():
        existing = _read_command_file(path)
        if existing is not None and existing != payload and not _owned_file(path, existing):
            raise CommandError("COMMAND_EXISTS", "Existing command files are preserved", path)
        previous[path] = existing
    destination.mkdir(parents=True, exist_ok=True)
    for path, payload in files.items():
        try:
            _write_command_file(path, payload, previous[path], os.name != "nt" and path.name == _launcher_name())
        except FileExistsError as exc:
            raise CommandError("COMMAND_EXISTS", "Existing command files are preserved", path) from exc
    if add_path:
        try:
            _user_path(destination, add=True)
        except OSError as exc:
            raise CommandError("PATH_REGISTRATION_FAILED", "Could not register the user command directory on PATH", destination) from exc
    return inspect_command(tool_root, bin_dir)


def install_command(args, tool_root, knowledge_root):
    if args.arguments or args.input or args.action:
        raise CommandError("INVALID_ACTION", "install-command takes options only")
    data = deploy_command(tool_root, args.bin_dir, knowledge_root=knowledge_root, add_path=args.add_path)
    data.update(command=data["path"], tool_root=str(tool_root),
                next_step="Open a new terminal with this directory on PATH")
    return envelope("ok", "command_installed", data), 0
