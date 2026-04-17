# 视频字幕工具

> Windows 桌面应用：下载视频 → 语音转字幕 → 播放同步 → 导出文件

## 功能特性

- **多平台下载**：支持 Bilibili、YouTube 等 1000+ 网站（yt-dlp）
- **CPU 语音转写**：Faster-Whisper（int8 量化，无 GPU 依赖）
- **视频播放**：Qt 内置播放器，支持常见格式
- **字幕同步**：实时显示当前时间戳对应的字幕
- **导出功能**：支持 SRT / TXT 格式

## 环境要求

- **操作系统**：Windows 10/11（64 位）
- **Python**：3.9 或 3.10
- **硬件**：任意 CPU（Intel/AMD 均可，无需独立显卡）
- **磁盘**：首次运行需下载 Whisper 模型（约 150MB）

## 快速开始

### 1. 安装 FFmpeg

**方法一：使用 winget（推荐）**
```powershell
winget install ffmpeg
```

**方法二：手动安装**
1. 从 https://www.gyan.dev/ffmpeg/builds/ 下载 `ffmpeg-release-essentials.zip`
2. 解压到 `C:\ffmpeg`
3. 将 `C:\ffmpeg\bin` 添加到系统 PATH

**验证安装**：
```powershell
ffmpeg -version
```

### 2. 创建虚拟环境（推荐）

```powershell
cd video-subtitle-app
python -m venv venv
.\venv\Scripts\activate
```

### 3. 安装 Python 依赖

```powershell
pip install -r requirements.txt
```

### 4. 运行程序

```powershell
python main.py
```

首次运行会自动下载 Faster-Whisper 模型（约 150MB），请耐心等待。

## 使用说明

### 下载视频

1. 在输入框粘贴视频链接（如 `https://www.bilibili.com/video/BV1xx...`）
2. 选择下载类型：
   - **视频+音频**：下载 MP4 视频文件
   - **仅音频**：下载 M4A 音频文件（转写更快）
3. 点击 **下载** 按钮
4. 等待下载完成（进度条显示进度）

### 自动转写

- 下载完成后自动启动语音转写
- 进度条显示转写进度
- 转写完成后字幕自动显示在下方区域

### 播放视频

- 点击 **播放** 按钮开始播放
- 字幕随视频进度自动更新
- 拖动进度条可跳转

### 导出字幕

- **导出 SRT**：生成带时间戳的标准字幕文件
- **导出 TXT**：生成纯文本文件

## 项目结构

```
video-subtitle-app/
├── main.py                 # 程序入口
├── requirements.txt        # Python 依赖
├── README.md               # 本文档
├── core/                   # 核心模块
│   ├── __init__.py
│   ├── downloader.py       # yt-dlp 下载封装
│   └── transcriber.py      # Faster-Whisper 转写封装
├── gui/                    # 界面模块
│   ├── __init__.py
│   └── main_window.py      # PySide6 主窗口
├── downloads/              # 下载文件存储
├── assets/                 # 资源文件（图标等）
└── docs/                   # 文档
```

## 配置选项

### 模型选择

编辑 `gui/main_window.py` 中的 `_start_transcribe` 方法：

```python
self._transcribe_worker = TranscriberWorker(
    model_size="base",  # tiny / base / small / medium / large-v3
    language="zh",      # zh / en / ja / auto
)
```

| 模型 | 参数量 | 内存占用 | 速度 | 准确度 |
|------|--------|----------|------|--------|
| tiny | 39M    | ~500MB   | 最快 | 一般   |
| base | 74M    | ~600MB   | 快   | 较好   |
| small| 244M   | ~1GB     | 中等 | 好     |
| medium| 769M  | ~2GB     | 慢   | 很好   |

**CPU 环境推荐**：`tiny` 或 `base`

### 代理设置

如果需要代理访问 YouTube，编辑 `core/downloader.py`：

```python
self._download_worker = DownloaderWorker(
    output_dir=self._get_download_dir(),
    proxy="http://127.0.0.1:7890",  # 添加代理
)
```

## 常见问题

### Q: 下载失败怎么办？

1. 检查链接是否正确
2. 检查网络连接
3. 某些视频可能需要登录，尝试使用浏览器下载后手动导入

### Q: 转写速度很慢？

1. 使用更小的模型（`tiny` 或 `base`）
2. 下载"仅音频"模式（文件更小）
3. 关闭其他 CPU 密集型程序

### Q: 字幕不准确？

1. 尝试更大的模型（`small` 或 `medium`）
2. 检查音频质量
3. 某些方言或专业术语可能识别不准确

### Q: 视频无法播放？

1. 检查 FFmpeg 是否正确安装
2. 某些特殊格式可能不支持，尝试下载"仅音频"模式

## 打包为 EXE 安装包

### 方式一：快速打包（单文件 EXE）

```powershell
# 安装 PyInstaller
pip install pyinstaller

# 运行打包脚本
.\build.bat
```

打包后的文件：`dist\视频字幕工具.exe`（约 200-500MB，包含所有依赖）

### 方式二：完整安装包（推荐）

```powershell
# 安装 NSIS（Windows 安装程序制作工具）
winget install NSIS.NSIS

# 运行完整构建
.\build-installer.bat
```

输出文件：
- `dist\视频字幕工具.exe` — 单文件可执行程序
- `视频字幕工具_安装程序.exe` — 专业安装包（带卸载、快捷方式）

### 打包注意事项

1. **首次打包较大**：包含 PySide6 + Faster-Whisper，约 200-500MB
2. **FFmpeg 需单独安装**：安装包会检测并提示用户安装 FFmpeg
3. **模型首次运行下载**：Faster-Whisper 模型（约 150MB）首次运行时自动下载
4. **杀毒软件误报**：PyInstaller 打包的程序可能被误报，添加白名单即可

### 减小体积的方法

```powershell
# 使用虚拟环境，只安装必需依赖
python -m venv venv
.\venv\Scripts\activate
pip install PySide6 yt-dlp faster-whisper ffmpeg-python
pip install pyinstaller
.\build.bat
```

### 高级配置

编辑 `build.spec` 文件可自定义：
- `icon='assets/icon.ico'` — 添加应用图标
- `datas=[('assets', 'assets')]` — 打包资源文件
- `console=True` — 显示控制台（用于调试）

## 许可证

MIT License

## 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 视频下载核心
- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper) - 高效语音识别
- [PySide6](https://www.qt.io/qt-for-python) - GUI 框架
