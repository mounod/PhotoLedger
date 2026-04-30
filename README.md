# PhotoLedger
一个面向长期使用的轻量级照片资产管理脚本。   
A lightweight yet powerful photo asset management script for long-term use.

**注：全程使用ChatGPT编写。**

# 项目简介

这是一个用于**批量整理照片与视频文件**的Python工具。   
   
核心目标是解决：   

- 文件命名混乱
- 时间信息不统一
- 设备来源不清晰
- 作者信息缺失
- 操作不可回滚

本项目提供：

- 自动/手动命名系统
- EXIF作者写入
- 全过程日志记录
- 一键撤销（Undo）
- 执行统计分析

# 功能特性

## 1. 多种命名模式

### 1.自动设备 + 自动时间

自动从照片的EXIF信息读取设备名与时间。   
如：`设备简称_YYYYMMDD_HHMMSS`   

**注：首次使用需要手动配置*device_map.json*以完成设备完整名与简称的对应。**

### 2.手动设备 + 自动时间

舍弃了**模式1**的自动读取设备名，改为手动输入，其他保持不变。

### 3.手动日期 + 序号

主要使用于照片无EXIF信息或以序号整理。   
如： 
`设备简称_YYYYMMDD_HHMMSS`
`SONY_20240101_001.jpg`

### 4.仅写作者（不改名）

仅更改照片的EXIF信息中摄影师一项，可作为前三模式附加运行。   
   
支持格式：
- JPG / JPEG（标准EXIF）
- PNG（文本元数据）
   
**注：命令行模式仅支持输入摄影师检查，详细请手动配置*photographer_map.json*以完成摄影师简称与完整姓名的对应。**

## 2. 日志系统

每次运行生成：
`logs/run_YYYYMMDD_HHMMSS.log`

内容包括：

- 重命名记录
- EXIF修改记录
- 错误信息
- 完整统计

## 3. 统计分析

执行结束输出：   
成功: X   
忽略: X   
失败: X   
并记录：   
- 忽略原因
- 失败原因

## 4. Undo 回滚

支持：

- 恢复文件名
- 恢复EXIF作者

完全基于日志，安全可靠。

# 安装依赖

```bash
pip install exifread piexif pillow
```

# 使用方法

## 0.配置文件

### 1.device_map.json

适用于**模式1**的负责自动对应设备完整名与设备简称。   
主要读取照片的EXIF信息。

参考如下：   
```
{
  "Canon EOS 1200D": "C120D",
  "iPhone 13": "IP13"
}
```

### 2.photographer_map.json
适用于**模式4**。   

参考如下：   
```
{
  "cxr": "Chen X.R.",
  "abc": "Author Name"
}
```
   
## 1.运行主脚本
```bash
python do.py
```

## 2.输入示例：
```bash
路径：D:\Photos   
模式：1   
附加写作者？(y/n)：y   
摄影师key：cxr   
确认执行？(y/n)：y   
```

## 3.撤销操作

```bash
python undo.py
```
输入日志路径：
`logs/run_20260430_123456.log`

---

# 支持格式
- 图片：JPG / JPEG / PNG / HEIC
- 视频：MP4 / MOV

# 注意事项
- 建议先在测试文件夹运行
- Undo 依赖日志，请勿删除 logs 文件夹
- PNG 会重写元数据（保留图像内容）
