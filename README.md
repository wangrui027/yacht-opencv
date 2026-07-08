# 游艇骰子 cv 助手

## 概述

游戏地址：[https://bloob.io/zh/yacht](https://bloob.io/zh/yacht)

程序基于 `opencv` 技术，截取屏幕识别图片模板中的元素，实现关键步骤的语音通知。

基本流程：

```bash
加载 templates
      |
      |
间隔 0.2s 截屏识别
      |
      |
根据识别模板组织 text 文本
      |
      |
调用 MP3 服务端播放音频
```

MP3 服务端播放示例：

```bash
GET http://localhost:8826/play?text=你好&voice=zh-CN-YunxiNeural
```

程序打包成 exe 双击运行，打开后显示到托盘即可，无需显示到任务栏，logo.ico 为 logo 图标，exe 程序文件、托盘图标都使用这个。