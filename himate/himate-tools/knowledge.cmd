@echo off
setlocal DisableDelayedExpansion
set "KNOWLEDGE_VERSION_PROBE=import sys; sys.exit(not ((3, 10) <= sys.version_info[:2] <= (3, 12)))"
if defined HIMATE_KNOWLEDGE_PYTHON (
  "%HIMATE_KNOWLEDGE_PYTHON%" -I -S -B -c "%KNOWLEDGE_VERSION_PROBE%" >nul 2>&1
  if not errorlevel 1 goto configured
)
py -3.11 -I -S -B -c "%KNOWLEDGE_VERSION_PROBE%" >nul 2>&1
if not errorlevel 1 goto python311
py -3.12 -I -S -B -c "%KNOWLEDGE_VERSION_PROBE%" >nul 2>&1
if not errorlevel 1 goto python312
py -3.10 -I -S -B -c "%KNOWLEDGE_VERSION_PROBE%" >nul 2>&1
if not errorlevel 1 goto python310
python -I -S -B -c "%KNOWLEDGE_VERSION_PROBE%" >nul 2>&1
if not errorlevel 1 goto pythonpath
python3 -I -S -B -c "%KNOWLEDGE_VERSION_PROBE%" >nul 2>&1
if not errorlevel 1 goto python3path

rem Last resort without system Python on PATH. Refuse any reparse-point managed root.
set "KNOWLEDGE_USER_HOME=%USERPROFILE%"
if not defined KNOWLEDGE_USER_HOME set "KNOWLEDGE_USER_HOME=%HOMEDRIVE%%HOMEPATH%"
if not defined KNOWLEDGE_USER_HOME goto unavailable
set "KNOWLEDGE_MANAGED_VENV=%KNOWLEDGE_USER_HOME%\.himate\knowledge\.venv"
if not exist "%KNOWLEDGE_MANAGED_VENV%\pyvenv.cfg" goto unavailable
for %%I in ("%KNOWLEDGE_MANAGED_VENV%") do set "KNOWLEDGE_VENV_ATTRIBUTES=%%~aI"
if not defined KNOWLEDGE_VENV_ATTRIBUTES goto unavailable
if not "%KNOWLEDGE_VENV_ATTRIBUTES:l=%"=="%KNOWLEDGE_VENV_ATTRIBUTES%" goto unavailable
set "KNOWLEDGE_MANAGED_PYTHON=%KNOWLEDGE_MANAGED_VENV%\Scripts\python.exe"
"%KNOWLEDGE_MANAGED_PYTHON%" -I -S -B -c "%KNOWLEDGE_VERSION_PROBE%" >nul 2>&1
if not errorlevel 1 goto managed

:unavailable
echo Knowledge requires a prepared Python 3.10, 3.11 or 3.12 on this execution host. 1>&2
exit /b 3
:configured
"%HIMATE_KNOWLEDGE_PYTHON%" -I -B "%~dp0knowledge.py" %*
exit /b %errorlevel%
:managed
"%KNOWLEDGE_MANAGED_PYTHON%" -I -S -B "%~dp0knowledge.py" --_bootstrap-python %*
exit /b %errorlevel%
:python311
py -3.11 -I -S -B "%~dp0knowledge.py" --_bootstrap-python %*
exit /b %errorlevel%
:python312
py -3.12 -I -S -B "%~dp0knowledge.py" --_bootstrap-python %*
exit /b %errorlevel%
:python310
py -3.10 -I -S -B "%~dp0knowledge.py" --_bootstrap-python %*
exit /b %errorlevel%
:pythonpath
python -I -S -B "%~dp0knowledge.py" --_bootstrap-python %*
exit /b %errorlevel%
:python3path
python3 -I -S -B "%~dp0knowledge.py" --_bootstrap-python %*
exit /b %errorlevel%
