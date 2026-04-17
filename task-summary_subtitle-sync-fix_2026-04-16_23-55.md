任务摘要：字幕与播放不同步修复

时间：2026-04-16 23:47-23:55 GMT+8

## 问题

用户报告：视频声音正常播放，但下方字幕文字明显滞后（声音到第5秒，字幕还停在第3秒）。

## 根因分析

1. positionChanged信号频率约15-30Hz，Qt事件队列在UI高负载时排队延迟50-100ms，累积后字幕滞后1-3秒
2. _highlight_subtitle_row每次创建新QFont对象，触发GC和布局重算，加重UI线程负担
3. 流式阶段的_scroll_timer(100ms批量滚动)与positionChanged高亮滚动互相竞争

## 修复内容（4处）

### 1. 预分配QFont对象（消除GC压力）
- 新增 _font_normal / _font_highlight 两个实例变量
- _highlight_subtitle_row 使用缓存字体而非每次 QFont(...)

### 2. positionChanged节流（核心修复）
- 新增 _sync_last_pos_ms 状态变量跟踪上次处理位置
- _on_position_changed 增加节流：正常播放时距离上次>=80ms才执行字幕同步
- 跳转/seek场景（负delta或大跳跃>500ms）立即强制更新，不节流
- 滑块和时间标签始终实时更新（轻量操作不节流）

### 3. seek/stop/load重置节流状态
- _seek_position: 跳转前 _sync_last_pos_ms = -1
- _stop_playback: 停止时 _sync_last_pos_ms = -1
- _load_video: 加载新视频时 _sync_last_pos_ms = -1

### 4. 缩进修复
- _load_video中 current_subtitle_label.setText 移入 skip_subtitle 条件块内

## 文件变更
- video-subtitle-app/gui/main_window.py

## 技术选型说明

为什么不用QTimer替代positionChanged：
- positionChanged已经是QMediaPlayer原生驱动，精度由播放器控制
- QTimer需要额外管理启停和精度，且无法获得seek/stop等场景的精确同步点
- 现有方案只需在已有回调中加节流判断，改动最小效果最大