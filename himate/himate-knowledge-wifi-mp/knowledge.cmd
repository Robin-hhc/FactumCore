@echo off
if defined HIMATE_KNOWLEDGE_PYTHON goto configured
py -3.11 -c "import sys" >nul 2>&1
if not errorlevel 1 goto python311
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 goto python312
py -3.10 -c "import sys" >nul 2>&1
if not errorlevel 1 goto python310
python -c "import sys; sys.exit(0 if sys.version_info[:2] in {(3,10),(3,11),(3,12)} else 1)" >nul 2>&1
if not errorlevel 1 goto pythonpath
echo Knowledge requires a prepared Python 3.10, 3.11 or 3.12 on this execution host. 1>&2
exit /b 3
:configured
"%HIMATE_KNOWLEDGE_PYTHON%" -B "%~dp0knowledge.py" %*
exit /b %errorlevel%
:python311
py -3.11 -B "%~dp0knowledge.py" %*
exit /b %errorlevel%
:python312
py -3.12 -B "%~dp0knowledge.py" %*
exit /b %errorlevel%
:python310
py -3.10 -B "%~dp0knowledge.py" %*
exit /b %errorlevel%
:pythonpath
python -B "%~dp0knowledge.py" %*
exit /b %errorlevel%
