@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set KMP_DUPLICATE_LIB_OK=TRUE
call "%~dp0venv\Scripts\activate.bat"
echo ✅ Venv ativado! Agora pode correr: python main.py
