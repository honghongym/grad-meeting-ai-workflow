# 组会 AI 纪要助手浏览器扩展

这是一个 Chrome/Edge Manifest V3 扩展，用来从会议转写网页提取文本并提交到本地 FastAPI 后端。

## 使用方式

1. 启动后端：

```powershell
python -m uvicorn app.main:app --reload
```

2. 打开 Chrome/Edge 扩展管理页：

```text
chrome://extensions
edge://extensions
```

3. 开启“开发者模式”。
4. 点击“加载已解压的扩展程序”。
5. 选择本目录 `browser-extension/`。
6. 打开任意会议转写网页，点击扩展图标。
7. 点击“提取当前页”，选择会议类型后提交。

## 后端设置

默认后端地址是：

```text
http://localhost:8000
```

如果 `.env` 中设置了：

```env
API_TOKEN=your-token
```

需要在扩展设置页填写同一个 token。

