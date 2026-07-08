#!/bin/bash
# ==========================================
# yacht-opencv 打包脚本 (Windows + PyInstaller)
# ==========================================

set -e

# 取消环境变量避免 uv 路径警告，uv 会自动发现项目下的 .venv
unset VIRTUAL_ENV

# 从 PATH 中去掉 JDK 目录，避免 PyInstaller 扫描依赖时看到无关的系统 DLL
NEW_PATH=""
IFS=":"
for p in $PATH; do
  case "$(echo "$p" | tr '[:upper:]' '[:lower:]')" in
    *jdk*|*openjdk*) ;;
    *) NEW_PATH="$NEW_PATH:$p" ;;
  esac
done
PATH="${NEW_PATH#:}"
unset IFS NEW_PATH p

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="yacht-opencv"
ICON="logo.ico"
UPX_DIR="/d/Program Files/upx"
ENTRY="src/yacht_opencv/__main__.py"

echo "=========================================="
echo "  打包 $APP_NAME"
echo "=========================================="

# 检查图标
if [ ! -f "$ICON" ]; then
    echo "⚠ 未找到 $ICON，跳过图标设置"
    ICON=""
fi

# 检查 PyInstaller
UV="uv"
if ! $UV run pyinstaller --version &>/dev/null; then
    echo ""
    echo "[1/3] 安装 PyInstaller..."
    $UV pip install pyinstaller
fi
echo ""
echo "[1/3] PyInstaller 已就绪"

# 清理旧构建
echo ""
echo "[2/3] 清理旧构建..."
rm -rf build dist *.spec

# 打包
echo ""
echo "[3/3] 打包中..."
echo "      入口: $ENTRY"
echo "      图标: ${ICON:-无}"
echo "      UPX : $UPX_DIR"
echo ""

PYINSTALLER_ARGS=(
    --clean
    --noconsole
    --name "$APP_NAME"
    --add-data "templates;templates"
    --add-data "logo.ico;."
    --hidden-import "pystray._win32"
    --hidden-import "PIL._tkinter_finder"
    # 排除不用模块，减小体积
    --exclude-module setuptools
    --exclude-module wheel
    --exclude-module pip
    --exclude-module tomli
)

if [ -n "$ICON" ]; then
    PYINSTALLER_ARGS+=(--icon "$ICON")
fi

if [ -d "$UPX_DIR" ]; then
    UPX_DIR_WIN="$(cygpath -w "$UPX_DIR")"
    PYINSTALLER_ARGS+=(--upx-dir "$UPX_DIR_WIN")
    echo "      UPX 路径: $UPX_DIR_WIN"
else
    echo "⚠ 未找到 UPX 目录: $UPX_DIR，跳过压缩"
fi

$UV run pyinstaller "${PYINSTALLER_ARGS[@]}" "$ENTRY"

# 终止运行中的旧程序，否则 rm 会权限失败
taskkill -f -im "$APP_NAME.exe" 2>/dev/null || true

cd 'D:\Program Files\yacht-opencv' && rm _internal yacht-opencv.exe -rf
cd "$SCRIPT_DIR" && cp -a dist/yacht-opencv/* 'D:\Program Files\yacht-opencv'

# 完成
echo ""
echo "=========================================="
echo "  打包完成！"
echo "  输出目录: $SCRIPT_DIR/dist/$APP_NAME/"
echo "=========================================="
