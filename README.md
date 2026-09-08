---
title: 東吳新生 AI 小幫手
emoji: 🎓
colorFrom: blue
colorTo: indigo
sdk: gradio
app_file: app.py
pinned: false
---

# 🎓 東吳新生 AI 小幫手 (LINE Bot + Gemini 智能問答)

專為東吳大學新生設計的智能問答機器人，搭載 **Google Gemini AI** 與 **東吳新生專屬知識庫**。

## 🌟 特色
1. **自然語言對話**：學生不需要輸入固定關鍵字，直接像跟學長姐聊天一樣詢問任何校園問題。
2. **專屬校園知識庫**：內建 `knowledge.txt`，包含外雙溪與城中校區資訊、交通、宿舍申請、選課規定、註冊體檢等。
3. **多輪對話記憶**：針對每一位 LINE 用戶維持對話脈絡。
4. **雙重介面**：
   - **LINE Bot**：供學生透過 LINE 隨時發問。
   - **Gradio Web Chatbot**：網頁端即時測試與管理面板。

## ⚙️ Hugging Face Secrets 設定清單
在 Space 頁面的 **Settings ➔ Variables and secrets** 新增：
- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `GEMINI_API_KEY` (免費申請：https://aistudio.google.com/)
