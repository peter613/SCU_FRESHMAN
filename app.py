import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Header
import gradio as gr

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from function import get_bot_reply, GEMINI_API_KEY

# 讀取環境變數
load_dotenv()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

# 初始化 LINE Bot SDK
handler = WebhookHandler(CHANNEL_SECRET) if CHANNEL_SECRET and CHANNEL_SECRET != "your_channel_secret_here" else None
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN) if CHANNEL_ACCESS_TOKEN and CHANNEL_ACCESS_TOKEN != "your_channel_access_token_here" else None

# 初始化 FastAPI
app = FastAPI(title="東吳新生系統 - Gemini LINE Bot API")

@app.get("/health")
def health_check():
    """健康檢查端點"""
    is_ready = bool(handler and configuration and GEMINI_API_KEY)
    return {
        "status": "running",
        "line_ready": bool(handler and configuration),
        "gemini_ready": bool(GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here")
    }

@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None)):
    """接收 LINE Webhook 訊息"""
    if not handler or not configuration:
        raise HTTPException(
            status_code=500,
            detail="LINE 憑證未設定，請在 Settings ➔ Variables and secrets 中設定 LINE_CHANNEL_SECRET 與 LINE_CHANNEL_ACCESS_TOKEN"
        )

    if not x_line_signature:
        raise HTTPException(status_code=400, detail="缺少 X-Line-Signature 標頭")

    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        handler.handle(body_str, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="無效的 LINE 簽名 (Invalid Signature)")
    except Exception as e:
        print(f"處理 Webhook 錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return "OK"

# 註冊 LINE 訊息處理器
if handler:
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event):
        user_text = event.message.text
        # 取得傳送訊息的 LINE User ID，以維持個別學生的對話脈絡 (Context)
        user_id = getattr(event.source, "user_id", "default_line_user")
        
        # 呼叫搭載 Gemini 的智能回覆
        reply_text = get_bot_reply(user_text, user_id=user_id)

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

# 定義 Gradio 對話函式 (供網頁端測試使用)
def gradio_chat(message: str, history: list):
    return get_bot_reply(message, user_id="gradio_web_user")

# 建立 Gradio Web 管理與聊天測試介面
with gr.Blocks(title="東吳新生小幫手 AI (Gemini 驅動)") as demo:
    gr.Markdown("# 🎓 東吳新生 AI 小幫手 (LINE Bot + Gemini 智能問答)")
    
    line_ok = bool(handler and configuration)
    gemini_ok = bool(GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here")
    
    status_line = "🟢 已設定" if line_ok else "⚠️ 尚未設定"
    status_gemini = "🟢 已設定" if gemini_ok else "⚠️ 尚未設定"

    gr.Markdown(
        f"""
| 模組 | 狀態 | 說明 |
| :--- | :--- | :--- |
| **LINE Bot 憑證** | {status_line} | `LINE_CHANNEL_SECRET` / `LINE_CHANNEL_ACCESS_TOKEN` |
| **Gemini AI 引擎** | {status_gemini} | `GEMINI_API_KEY` (至 Google AI Studio 免費申請) |

📌 **LINE Webhook URL**：`https://<你的-Space-名稱>.hf.space/callback`  
💡 **自訂資料庫**：可以直接編輯 `knowledge.txt` 隨時擴充新生資料與校園常見問題！
        """
    )
    
    gr.Markdown("---")
    gr.Markdown("### 💬 即時 AI 對話測試（直接與搭載東吳知識庫的 Gemini 聊天）")
    
    gr.ChatInterface(
        fn=gradio_chat,
        textbox=gr.Textbox(
            placeholder="你可以隨意用口語詢問，例如：「大一必修有哪些？」、「外雙溪附近有什麼好吃的？」、「合江學舍離學校遠嗎？」",
            scale=7
        )
    )

# 將 Gradio 掛載至 FastAPI 根路徑
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
