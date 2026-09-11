@echo off
setlocal enabledelayedexpansion

:: Prevent python from buffering standard I/O streams on Windows
set PYTHONUNBUFFERED=1

:: Run your project virtual environment interpreter securely
"C:\Users\Abraham.Kemboi\PycharmProjects\Nexus-os\.venv\Scripts\python.exe" -u "C:\Users\Abraham.Kemboi\PycharmProjects\Nexus-os\mcp_server.py" %*
