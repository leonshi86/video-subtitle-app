# 任务摘要 - 工业级重构 2026-04-17

## 目标
工业级代码重构、自测与修复，输出稳定可商用版本

## 执行结果

### 一、代码结构分析
- 原架构：QMediaPlayer + QVideoWidget（Qt Multimedia）
- 新架构：python-vlc（VLC 媒体播放器）
- 关键模块：播放器核心、VLC 播放控制、UI 界面、线程分离、字幕逻辑、历史记录、音量控制

### 二、核心修改（共 14 阶段）

#### 1. VLC 迁移
- `import vlc` 替换 Qt Multimedia imports
- `QVideoWidget` → `QWidget`
- `_setup_media_player` 完全重写为 VLC 初始化

#### 2. 播放控制
- `play()`/`pause()`/`stop()` → `_vlc_player` 对应方法
- `setPosition()` → `set_time()`
- `duration()` → `get_length()`

#### 3. 状态管理
- 新增 `_poll_vlc_state()` 轮询定时器（80ms）
- 替换 Qt 信号连接为轮询检测
- `_on_vlc_state_changed()` 处理播放状态

#### 4. 新功能
- **进度条点击定位**：`mousePressEvent` 覆盖，任意位置点击精准跳转
- **可拖动分割线**：`QSplitter` + `setMinimumWidth(180)`
- **历史不置顶**：`_add_to_history` 改为原地更新或追加末尾
- **音量控制**：`−/+` 按钮 + 滑块，`audio_set_volume()` 实时调节
- **字幕开关**：`subtitle_toggle_btn` 控制 `subtitle_panel` 可见性
- **80ms 节流**：`_on_position_changed` 添加节流避免高频刷新

#### 5. 其他优化
- 移除所有 `@Slot` 装饰器（VLC 不需要）
- `closeEvent` 添加 VLC 资源释放
- QSplitter handle 样式优化
- `_get_display_title()` 统一标题获取

### 三、验证结果
- ✅ 语法正确（ast.parse 通过）
- ✅ 无 QMediaPlayer 残留引用
- ✅ 无 media_player 残留引用

## 文件变更
- `gui/main_window.py` — 完整重构

## 待测试项
1. 本地文件播放/暂停/停止
2. 流媒体 URL 加载
3. 进度条点击跳转
4. 音量调节
5. 字幕开关
6. 历史记录不置顶
7. 分割线拖动
8. 转写功能
9. 导出 SRT/TXT
