@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================================
echo    视频字幕工具 - 完整安装包构建
echo ============================================================
echo.

:: 切换到项目目录
cd /d "%~dp0"

:: 检查 NSIS
where makensis >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 NSIS，正在尝试安装...
    winget install NSIS.NSIS --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo [错误] NSIS 安装失败
        echo 请手动安装: winget install NSIS.NSIS
        pause
        exit /b 1
    )
    :: 刷新环境变量
    call refreshenv >nul 2>&1 || echo [提示] 请重启终端后再次运行
)

:: 先执行 PyInstaller 打包
echo.
echo [步骤 1/2] PyInstaller 打包...
call build.bat

if errorlevel 1 (
    echo [错误] PyInstaller 打包失败
    pause
    exit /b 1
)

:: 创建 NSIS 安装包
echo.
echo [步骤 2/2] 创建安装程序...
makensis installer.nsi

if errorlevel 1 (
    echo [错误] 安装包创建失败
    echo 请检查 installer.nsi 脚本
    pause
    exit /b 1
)

echo.
echo ============================================================
echo    构建完成！
echo    
echo    输出文件:
echo    - dist\视频字幕工具.exe (单文件 EXE)
echo    - 视频字幕工具_安装程序.exe (安装包)
echo ============================================================
echo.

pause
