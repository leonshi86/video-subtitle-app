#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py
────────────────────────────────────────────────────────────────────────────
视频字幕工具 - 程序入口
────────────────────────────────────────────────────────────────────────────
功能概述：
  1. 下载视频/音频（Bilibili、YouTube 等平台）
  2. 自动语音转字幕（Faster-Whisper，纯 CPU 推理）
  3. 视频播放 + 字幕同步显示
  4. 导出 SRT/TXT 字幕文件

运行环境：
  • Python 3.9 / 3.10
  • Windows 10/11
  • Intel UHD Graphics（集成显卡，无 CUDA）

启动命令：
  python main.py

打包命令（可选）：
  pyinstaller --onefile --windowed main.py
"""

import sys
import os
import logging
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 设置环境变量（解决某些编码问题）
os.environ["PYTHONIOENCODING"] = "utf-8"

# ── 日志配置 ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        # 可选：写入文件
        # logging.FileHandler(PROJECT_ROOT / "app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("Main")


# ── 主函数 ────────────────────────────────────────────────────────────────
def main() -> int:
    """应用程序入口"""

    # 检查依赖
    _check_dependencies()

    # ── 播放后端：python-vlc ─────────────────────────────────────────────
    # VLC 自带硬件解码（D3D11VA / DXVA2），不需要 Qt Multimedia。
    # 以下环境变量仅供 yt-dlp / ffmpeg 转写使用，不影响 VLC。
    os.environ["HWACCEL"] = "none"

    # 创建应用
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from gui.main_window import MainWindow

    # 高 DPI 支持（Qt 6 已默认启用）
    # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    # QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    app.setApplicationName("视频字幕工具")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")  # 跨平台风格

    # 设置字体
    font = app.font()
    font.setFamily("Microsoft YaHei")
    app.setFont(font)

    # 创建主窗口
    window = MainWindow()
    window.show()

    logger.info("应用程序启动完成")

    # 运行事件循环
    return app.exec()


def _check_dependencies() -> None:
    """检查关键依赖是否已安装"""

    missing = []

    try:
        import PySide6
    except ImportError:
        missing.append("PySide6")

    try:
        import yt_dlp
    except ImportError:
        missing.append("yt-dlp")

    try:
        import faster_whisper
    except ImportError:
        missing.append("faster-whisper")

    try:
        import ffmpeg
    except ImportError:
        missing.append("ffmpeg-python")

    try:
        import vlc
    except ImportError:
        missing.append("python-vlc")

    if missing:
        print("=" * 60)
        print("缺少依赖包，请运行以下命令安装：")
        print(f"  pip install {' '.join(missing)}")
        print("=" * 60)
        sys.exit(1)


# ── 程序入口 ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.exit(main())
