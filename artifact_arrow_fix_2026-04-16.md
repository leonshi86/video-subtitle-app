# 下拉箭头可见性修复 - 2026-04-16 13:01

## 问题
右侧小三角箭头看不清，怀疑是颜色重叠。

## 原因分析
1. `::drop-down` 区域没有背景色，箭头直接浮在白色背景上
2. 箭头颜色 `#555555` 灰色与白色背景对比度不够
3. 用户自己改成 `#00FF00` 绿色箭头 + `#0000FF` 蓝色背景，但可能还是不够明显

## 修复方案

### 1. ::drop-down 区域加背景
```css
QComboBox::drop-down {
    border: none;
    width: 20px;
    background-color: #F0F0F0;   /* 浅灰背景 */
    border-radius: 0 6px 6px 0;  /* 右侧圆角 */
}
```

### 2. 箭头改成纯黑
```css
QComboBox::down-arrow {
    border-top: 6px solid #000000;  /* 纯黑，对比度最高 */
}
```

### 3. 下拉列表恢复白底黑字
```css
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #000000;
}
```

## 效果
- 箭头区域：浅灰背景 `#F0F0F0`
- 箭头本身：纯黑 `#000000`
- 对比度极高，应该能清晰看到

## 验证
语法检查通过 ✅
