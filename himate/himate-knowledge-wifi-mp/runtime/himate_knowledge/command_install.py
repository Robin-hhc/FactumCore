"""Install the optional machine command shim without binding a knowledge group."""

import os
from pathlib import Path
import shlex
import sys

from .protocol import NodeError as CommandError, envelope

def install_command(args, root):
    if args.arguments:
        raise CommandError("INVALID_ACTION", "install-command takes options only")
    if args.add_path and os.name != "nt":
        raise CommandError("PATH_REGISTRATION_UNAVAILABLE", "Add the command directory to your shell PATH explicitly")
    destination = Path(args.bin_dir).expanduser().absolute() if args.bin_dir else (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HiMate/bin" if os.name == "nt"
        else Path.home() / ".local/bin")
    if destination.resolve().is_relative_to(root):
        raise CommandError("COMMAND_INSIDE_KNOWLEDGE", "Install the machine command outside the knowledge repository")
    for path in (destination, *destination.parents):
        if path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400):
            raise CommandError("LINKED_OUTPUT", "Command directory must not be linked")
        if (path / "governance/framework.lock.yaml").is_file():
            raise CommandError("COMMAND_INSIDE_KNOWLEDGE", "Install the machine command outside every knowledge repository")
    destination.mkdir(parents=True, exist_ok=True)
    dispatcher = destination / "knowledge-dispatch.py"
    dispatch = '''"""Machine command shim; selects the current repository, never a fixed group."""
import sys
def normalized(value):
    value = value.replace("\\\\", "/").rstrip("/")
    return value.casefold() if sys.platform == "win32" else value
prefixes = tuple(normalized(p) for p in {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix} if p)
sys.path[:] = [p for p in sys.path if p and any(normalized(p) == base or normalized(p).startswith(base + "/") for base in prefixes)]
import os
from pathlib import Path
import subprocess
for directory in (Path.cwd(), *Path.cwd().parents):
    entry = directory / "knowledge.py"
    if entry.is_file() and (directory / "governance/framework.lock.yaml").is_file():
        raise SystemExit(subprocess.call([sys.executable, "-B", str(entry), *sys.argv[1:]]))
print('{"status":"error","phase":"invalid","diagnostics":[{"code":"KNOWLEDGE_ROOT_NOT_FOUND","message":"Run knowledge inside the intended knowledge directory"}]}')
raise SystemExit(2)
'''
    if os.name == "nt":
        launcher = destination / "knowledge.cmd"
        command = '@echo off\r\n"' + sys.executable + '" -B "%~dp0knowledge-dispatch.py" %*\r\nexit /b %errorlevel%\r\n'
    else:
        launcher = destination / "knowledge"
        command = "#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' -B "$(dirname -- "$0")/knowledge-dispatch.py" "$@"\n'
    payload = {dispatcher: dispatch.encode("utf-8"), launcher: command.encode("utf-8")}
    for path in payload:
        if path.exists() or path.is_symlink():
            raise CommandError("COMMAND_EXISTS", "Existing command files are preserved: " + str(path))
    for path, raw in payload.items():
        with path.open("xb") as stream:
            stream.write(raw)
    if os.name != "nt":
        launcher.chmod(0o755)
    if args.add_path:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            try:
                current, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current, kind = "", winreg.REG_EXPAND_SZ
            if str(destination).casefold() not in {p.rstrip("\\/").casefold() for p in current.split(";")}:
                winreg.SetValueEx(key, "Path", 0, kind, current.rstrip(";") + (";" if current else "") + str(destination))
    return envelope("ok", "command_installed", {"command": str(launcher), "bin_dir": str(destination),
                    "path_registered": args.add_path, "next_step": "Open a new terminal with this directory on PATH"}), 0
