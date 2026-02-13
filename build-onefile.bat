@echo off
REM GitLab AI Review 单文件打包脚本
REM 生成单个 EXE 文件，包含所有依赖

chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   GitLab AI Review 单文件打包
echo ========================================
echo.

set PROJECT_ROOT=%~dp0
set BUILD_DIR=%PROJECT_ROOT%build_onefile

REM 1. 构建前端
echo [1/4] 构建前端...
cd /d "%PROJECT_ROOT%web"
if not exist "node_modules" (
    echo 安装前端依赖...
    call npm install
)
call npm run build
if errorlevel 1 (
    echo 前端构建失败！
    pause
    exit /b 1
)
echo 前端构建完成！
echo.

REM 2. 准备打包目录
echo [2/4] 准备打包目录...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
mkdir "%BUILD_DIR%"

REM 复制必要文件
xcopy /s /e /y "%PROJECT_ROOT%web\dist" "%BUILD_DIR%\web\dist\" >nul
xcopy /s /e /y "%PROJECT_ROOT%server" "%BUILD_DIR%\server\" >nul
xcopy /s /e /y "%PROJECT_ROOT%src" "%BUILD_DIR%\src\" >nul
copy /y "%PROJECT_ROOT%server.py" "%BUILD_DIR%\" >nul
copy /y "%PROJECT_ROOT%build\onefile.py" "%BUILD_DIR%\onefile.spec" >nul

echo 准备完成！
echo.

REM 3. 检查 PyInstaller
echo [3/4] 检查依赖...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 安装 PyInstaller...
    pip install pyinstaller
)
echo 依赖检查完成！
echo.

REM 4. 使用 PyInstaller 打包
echo [4/4] 开始打包（这可能需要几分钟）...
cd /d "%BUILD_DIR%"

pyinstaller --clean onefile.spec

if errorlevel 1 (
    echo.
    echo 打包失败！请检查错误信息。
    pause
    exit /b 1
)

REM 复制到项目根目录
copy /y "%BUILD_DIR%\dist\GitLab-AI-Review.exe" "%PROJECT_ROOT%\"

echo.
echo ========================================
echo   打包完成！
echo ========================================
echo.
echo 单文件 EXE 位置:
echo   %PROJECT_ROOT%GitLab-AI-Review.exe
echo.
echo 大小:
dir "%PROJECT_ROOT%GitLab-AI-Review.exe" | find "GitLab-AI-Review.exe"
echo.

REM 询问是否清理
set /p CLEAN="是否删除临时构建文件？(Y/N): "
if /i "%CLEAN%"=="Y" (
    rmdir /s /q "%BUILD_DIR%"
    echo 临时文件已清理。
)

pause
