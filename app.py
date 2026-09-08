import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse

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
api_client = ApiClient(configuration) if configuration else None
line_bot_api = MessagingApi(api_client) if api_client else None

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
    print(f"📩 收到 LINE 請求: signature={x_line_signature}", flush=True)
    if not handler or not configuration:
        print("❌ LINE 憑證未設定！", flush=True)
        raise HTTPException(
            status_code=500,
            detail="LINE 憑證未設定，請在 Render 的 Environment Variables 中設定 LINE_CHANNEL_SECRET 與 LINE_CHANNEL_ACCESS_TOKEN"
        )

    if not x_line_signature:
        print("❌ 缺少 X-Line-Signature 標頭！", flush=True)
        raise HTTPException(status_code=400, detail="缺少 X-Line-Signature 標頭")

    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        handler.handle(body_str, x_line_signature)
        print("✅ LINE Webhook 處理完成！", flush=True)
    except InvalidSignatureError:
        print("❌ LINE 數位簽名驗證失敗 (InvalidSignatureError)！請檢查 LINE_CHANNEL_SECRET 是否填錯！", flush=True)
        raise HTTPException(status_code=400, detail="無效的 LINE 簽名 (Invalid Signature)")
    except Exception as e:
        print(f"❌ 處理 Webhook 錯誤: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))

    return "OK"

# 註冊 LINE 訊息處理器
if handler:
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event):
        user_text = event.message.text
        user_id = getattr(event.source, "user_id", "default_line_user")
        print(f"👤 收到學生訊息 [{user_id[:8]}...]: {user_text}", flush=True)
        
        # 呼叫搭載 Gemini 的智能回覆
        reply_text = get_bot_reply(user_text, user_id=user_id)
        print(f"🤖 Gemini 生成回覆: {reply_text[:60]}...", flush=True)

        if line_bot_api:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
            print("🚀 已成功將回覆傳送至 LINE！", flush=True)

# 供網頁測試使用的輕量 API 端點
@app.post("/api/test-chat")
async def web_test_chat(request: Request):
    data = await request.json()
    msg = data.get("message", "")
    reply = get_bot_reply(msg, user_id="web_test_user")
    return {"reply": reply}

# 極致輕量原生網頁介面（免載入龐大 UI 套件，0.1 秒秒開）
@app.get("/", response_class=HTMLResponse)
def index():
    line_status = "🟢 已就緒" if (handler and configuration) else "⚠️ 未設定憑證"
    gemini_status = "🟢 已就緒" if (GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here") else "⚠️ 未設定 API Key"

    return f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>東吳新生 AI 小幫手</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f1f5f9; margin: 0; padding: 24px; display: flex; justify-content: center; }}
            .card {{ background: white; max-width: 580px; width: 100%; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); padding: 28px; box-sizing: border-box; }}
            h1 {{ color: #0f172a; font-size: 22px; margin-top: 0; display: flex; align-items: center; gap: 8px; }}
            .badges {{ margin-bottom: 12px; display: flex; gap: 8px; }}
            .status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; background: #e0f2fe; color: #0369a1; }}
            .info-box {{ background: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 4px; margin: 16px 0; font-size: 13px; color: #334155; line-height: 1.6; }}
            .chat-box {{ margin-top: 16px; border-top: 1px solid #e2e8f0; padding-top: 16px; }}
            .chat-history {{ height: 230px; overflow-y: auto; background: #fafafa; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px; margin-bottom: 12px; font-size: 14px; }}
            .chat-msg {{ margin-bottom: 10px; line-height: 1.5; }}
            .user-msg {{ color: #2563eb; font-weight: 600; }}
            .bot-msg {{ color: #1e293b; white-space: pre-wrap; }}
            .input-group {{ display: flex; gap: 8px; }}
            input[type="text"] {{ flex: 1; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; outline: none; }}
            input[type="text"]:focus {{ border-color: #3b82f6; }}
            button {{ background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.15s; }}
            button:hover {{ background: #2563eb; }}
            button:disabled {{ background: #94a3b8; cursor: not-allowed; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🎓 東吳新生 AI 小幫手</h1>
            <div class="badges">
                <span class="status-badge">LINE: {line_status}</span>
                <span class="status-badge">Gemini: {gemini_status}</span>
            </div>
            <div class="info-box">
                📌 <b>Webhook URL：</b><code>https://scu-freshman.onrender.com/callback</code><br>
                💡 伺服器運作正常，搭載 Gemini 3.5-flash 與東吳校園知識庫。
            </div>
            
            <div class="chat-box">
                <h3 style="margin: 0 0 10px 0; font-size: 15px; color: #475569;">💬 即時對話測試（免開 LINE，直接在網頁聊天）</h3>
                <div class="chat-history" id="chatHistory">
                    <div class="chat-msg bot-msg">🤖 <b>小幫手：</b>學弟妹好！我是東吳新生小幫手，關於校園、宿舍、選課等問題都可以直接問我喔！</div>
                </div>
                <div class="input-group">
                    <input type="text" id="userInput" placeholder="例如：外雙溪有什麼好吃的？" onkeypress="if(event.key==='Enter') sendTestMsg()">
                    <button onclick="sendTestMsg()" id="sendBtn">傳送</button>
                </div>
            </div>
        </div>

        <script>
            async function sendTestMsg() {{
                const input = document.getElementById('userInput');
                const history = document.getElementById('chatHistory');
                const sendBtn = document.getElementById('sendBtn');
                const msg = input.value.trim();
                if (!msg) return;

                history.innerHTML += `<div class="chat-msg user-msg">👤 <b>你：</b>${{msg}}</div>`;
                input.value = '';
                sendBtn.disabled = true;
                sendBtn.innerText = '思考中...';
                history.scrollTop = history.scrollHeight;

                try {{
                    const res = await fetch('/api/test-chat', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ message: msg }})
                    }});
                    const data = await res.json();
                    history.innerHTML += `<div class="chat-msg bot-msg">🤖 <b>小幫手：</b>${{data.reply}}</div>`;
                }} catch (e) {{
                    history.innerHTML += `<div class="chat-msg" style="color: red;">❌ 連線異常，請稍後再試</div>`;
                }} finally {{
                    sendBtn.disabled = false;
                    sendBtn.innerText = '傳送';
                    history.scrollTop = history.scrollHeight;
                }}
            }}
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
