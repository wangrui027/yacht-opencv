@echo off
REM 使用 PyInstaller 打包为单文件 exe
cd /d "%~dp0"
uv run pyinstaller yacht-opencv.spec --clean
pause
