# 下拉箭头修复 - 2026-04-16 13:45

## 问题
`image: none` + `border` 三角在 Qt 里不生效，始终显示 Qt 默认的黑色方块箭头。

## 解决方案
用真实的 PNG 图片替代 CSS border 三角，Qt 显示图片没有兼容性问题。

## 改动

### 1. 新建箭头图片
`gui/assets/arrow_down.png` — 14×9px，深灰色（#323232）向下三角箭头，用 Python 手写 PNG 二进制生成（不依赖 PIL）

### 2. QSS 改用图片
```css
QComboBox::down-arrow {
    image: url(gui/assets/arrow_down.png);
    border: none;
    width: 14px;
    height: 9px;
}
```

### 3. 修复了文件损坏
之前 `edit` 操作时不小心在 `format_combo` 代码区引入了重复垃圾代码，已清理并恢复。

## 验证
语法检查通过 ✅
