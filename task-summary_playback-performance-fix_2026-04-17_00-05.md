任务摘要：视频播放卡顿/掉帧修复

时间：2026-04-16 23:53 - 2026-04-17 00:05 GMT+8

## 问题

视频加载和播放过程中存在明显卡顿和掉帧。

## 根因诊断

1. [致命] QT_MULTIMEDIA_PREFER_SOFTWARE=1 强制全软解 -> 1080p h264 软解占 4 核 CPU -> UI 事件循环响应慢
2. [中等] QVideoWidget 无 QSurfaceFormat 配置 -> 无 vsync、无双缓冲 -> 画面撕裂
3. [中等] QAudioOutput 使用默认 1 秒缓冲 -> 音频延迟
4. [中等] 切换视频时未释放旧媒体源 -> 解码器帧缓冲累积
5. [低] 流媒体临时文件未清理 -> 磁盘占满后 IO 阻塞

之前禁用硬解的原因：B 站 AV1 格式导致 D3D11VA 帧缓冲池溢出。
正确方案：保留 H264/H265 硬解，在 yt-dlp -f 参数中排除 AV1 格式（已实现）。

## 修复内容

### main.py (2处)
1. 移除 QT_MULTIMEDIA_PREFER_SOFTWARE=1，保留 QT_ENABLE_HWACCELERATION=0 和 HWACCEL=none
2. 在 QApplication 创建前配置 QSurfaceFormat：swapInterval=1(vsync), DoubleBuffer, 禁用不需要的 depth/stencil 缓冲

### main_window.py (5处)
3. _setup_media_player: QAudioOutput.setBufferSize(300KB) 减少音频延迟
4. _setup_media_player: 补充 QNetworkAccessManager import
5. _load_video: 切换视频前先 stop() + setSource(QUrl()) 释放旧资源
6. _delayed_set_source: 同上，释放旧资源
7. closeEvent: 清理流媒体临时目录 shutil.rmtree
8. StreamUrlWorker.get_url: 移除多余的环境变量设置

## 架构分析结论

当前 QMediaPlayer + QVideoWidget 架构本身是合理的：
- QMediaPlayer 内部使用 Qt FFmpeg 后端，解码在独立线程池
- QVideoWidget 通过 OpenGL 渲染，GPU 合成
- 信号驱动 UI 更新，已通过节流优化

不需要替换为 python-vlc 或 PyAV+OpenGL 方案，QMediaPlayer 足够。
瓶颈在配置层面（强制软解、无 vsync、缓冲过大、资源泄漏）。

## 文件变更
- video-subtitle-app/main.py
- video-subtitle-app/gui/main_window.py