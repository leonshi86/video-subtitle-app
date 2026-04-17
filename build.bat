@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================================
echo    视频字幕工具 - 打包脚本
echo ============================================================
echo.

:: 切换到项目目录
cd /d "%~dp0"

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9-3.11
    pause
    exit /b 1
)

:: 检查 PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [信息] 正在安装 PyInstaller...
    pip install pyinstaller -q
)

:: 检查依赖
echo [步骤 1/3] 检查依赖...
pip install -r requirements.txt -q

:: 清理旧构建
echo [步骤 2/3] 清理旧构建...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

:: 执行打包
echo [步骤 3/3] 正在打包（可能需要几分钟）...
python -m PyInstaller build.spec --clean

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo ============================================================
echo    打包完成！
echo    输出文件: dist\视频字幕工具.exe
echo ============================================================
echo.

:: 询问是否打开输出目录
set /p OPEN_DIR="是否打开输出目录？(Y/N): "
if /i "%OPEN_DIR%"=="Y" explorer "dist"

pause
