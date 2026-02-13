@echo off
REM GitLab AI Review 打包脚本
REM 将前端和后端打包成一个 EXE 程序

chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   GitLab AI Review 打包工具
echo ========================================
echo.

REM 设置项目根目录
set PROJECT_ROOT=%~dp0
set BUILD_DIR=%PROJECT_ROOT%build
set DIST_DIR=%PROJECT_ROOT%dist

REM 1. 清理旧的构建文件
echo [1/6] 清理旧的构建文件...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
mkdir "%BUILD_DIR%"
mkdir "%DIST_DIR%"
echo 清理完成！
echo.

REM 2. 构建前端
echo [2/6] 构建前端...
cd /d "%PROJECT_ROOT%web"
call npm install
if errorlevel 1 (
    echo 前端依赖安装失败！
    pause
    exit /b 1
)
call npm run build
if errorlevel 1 (
    echo 前端构建失败！
    pause
    exit /b 1
)
echo 前端构建完成！
echo.

REM 3. 复制前端构建产物到 build 目录
echo [3/6] 复制前端文件...
xcopy /s /e /y "%PROJECT_ROOT%web\dist" "%BUILD_DIR%\web\dist\"
echo 前端文件复制完成！
echo.

REM 4. 复制后端文件
echo [4/6] 复制后端文件...
xcopy /s /e /y "%PROJECT_ROOT%server" "%BUILD_DIR%\server\"
xcopy /s /e /y "%PROJECT_ROOT%src" "%BUILD_DIR%\src\"
copy /y "%PROJECT_ROOT%server.py" "%BUILD_DIR%\"
copy /y "%PROJECT_ROOT%requirements.txt" "%BUILD_DIR%\"
echo 后端文件复制完成！
echo.

REM 5. 创建 PyInstaller 配置文件
echo [5/6] 创建 PyInstaller 配置...
(
echo # -*- mode: python ; coding: utf-8 -*-
echo.
echo block_cipher = None
echo.
echo a = Analysis(
echo     ['server.py'],
echo     pathex=[],
echo     binaries=[],
echo     datas=[
echo         ^(r'web\dist', 'web\dist'^),
echo         ^(r'server', 'server'^),
echo         ^(r'src', 'src'^),
echo     ],
echo     hiddenimports=[
echo         'uvicorn.logging',
echo         'uvicorn.loops',
echo         'uvicorn.loops.auto',
echo         'uvicorn.protocols',
echo         'uvicorn.protocols.http',
echo         'uvicorn.protocols.http.auto',
echo         'uvicorn.protocols.websockets',
echo         'uvicorn.protocols.websockets.auto',
echo         'uvicorn.lifespan',
echo         'uvicorn.lifespan.on',
echo         'fastapi',
echo         'passlib.hash.bcrypt',
echo         'passlib.handlers.bcrypt',
echo         'bcrypt',
echo         'pygments',
echo         'pygments.lexers',
echo         'pygments.formatters',
echo         'pygments.styles',
echo         'websockets',
echo         'websockets.legacy',
echo         'websockets.legacy.server',
echo         'sqlalchemy.dialects.sqlite',
echo         'sqlalchemy.ext.declarative',
echo         'python-jose',
echo         'jose',
echo         'dotenv',
echo     ],
echo     hookspath=[],
echo     hooksconfig={},
echo     runtime_hooks=[],
echo     excludes=[],
echo     win_no_prefer_redirects=False,
echo     win_private_assemblies=False,
echo     cipher=block_cipher,
echo     noarchive=False,
echo )
echo.
echo pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher^)
echo.
echo exe = EXE(
echo     pyz,
echo     a.scripts,
echo     [],
echo     exclude_binaries=True,
echo     name='GitLab-AI-Review',
echo     debug=False,
echo     bootloader_ignore_signals=False,
echo     strip=False,
echo     upx=True,
echo     console=False,
echo     disable_windowed_traceback=False,
echo     argv_emulation=False,
echo     target_arch=None,
echo     codesign_identity=None,
echo     entitlements_file=None,
echo     icon='icon.ico' if exist 'icon.ico' else None,
echo )
echo.
echo coll = COLLECT(
echo     exe,
echo     a.binaries,
echo     a.zipfiles,
echo     a.datas,
echo     strip=False,
echo     upx=True,
echo     upx_exclude=[],
echo     name='GitLab-AI-Review',
echo )
) > "%BUILD_DIR%\gitlab_ai_review.spec"
echo PyInstaller 配置文件创建完成！
echo.

REM 6. 使用 PyInstaller 打包
echo [6/6] 使用 PyInstaller 打包...
cd /d "%BUILD_DIR%"

REM 检查是否安装了 pyinstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 安装 PyInstaller...
    pip install pyinstaller
)

pyinstaller --clean gitlab_ai_review.spec --workpath "%BUILD_DIR%\build" --distpath "%DIST_DIR%"

if errorlevel 1 (
    echo PyInstaller 打包失败！
    pause
    exit /b 1
)

REM 复制 EXE 到项目根目录
copy /y "%DIST_DIR%\GitLab-AI-Review\GitLab-AI-Review.exe" "%PROJECT_ROOT%\GitLab-AI-Review.exe"

echo.
echo ========================================
echo   打包完成！
echo ========================================
echo.
echo EXE 文件位置:
echo   %PROJECT_ROOT%GitLab-AI-Review.exe
echo.
echo 完整分发目录:
echo   %DIST_DIR%\GitLab-AI-Review\
echo.

pause
