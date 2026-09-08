import os
import time
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()

# 讀取 Gemini API Key 與模型設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# 備選模型清單：優先使用 3.5-flash，若失敗自動降級嘗試 2.5-flash 與 3.5-flash-lite
FALLBACK_MODELS = [PRIMARY_MODEL, "gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-1.5-flash"]
MODELS_TO_TRY = []
for m in FALLBACK_MODELS:
    if m and m not in MODELS_TO_TRY:
        MODELS_TO_TRY.append(m)

# 讀取知識庫檔案 (knowledge.txt)
def load_knowledge_base() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "knowledge.txt")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"讀取 knowledge.txt 失敗: {e}", flush=True)
    return "暫無外部知識庫資料。"

KNOWLEDGE_DATA = load_knowledge_base()

# 建立 System Prompt
SYSTEM_INSTRUCTION = f"""
你是由東吳大學學長翔鳶開發的「東吳新生小幫手」。
你的身份是一位熱心、親切、幽默且經驗豐富的東吳大學高年級學長姐。

你的任務是陪伴大一新生，以自然對話的形式回答他們關於校園生活、選課、宿舍、交通、社團、行政手續等所有疑問，減緩他們初入大學的焦慮。

以下是「東吳大學新生指南知識庫」，請優先根據以下資訊回答：
==================== 知識庫開始 ====================
{KNOWLEDGE_DATA}
==================== 知識庫結束 ====================

【回覆指導原則】
1. **自然聊天**：學生不需輸入完全一樣的關鍵字，請理解學生的口語表達（例如「肚子餓了雙溪有啥吃的」、「外雙溪怎麼去」、「選課沒選到怎麼辦」、「想交朋友」等），直接如同朋友般對話。
2. **語氣風格**：親切、同理、繁體中文（台灣習慣用語，如：學長姐、大一、學分、加退選、體檢、宿舍等），適度使用 Emoji 增加生動感。
3. **資訊精確**：校內相關規定請嚴格依據知識庫回答
4. **避免誤導**：若學生詢問的細節不在知識庫中，請誠實說明回答不知道。若詢問非學校問題，請說「我的開發者很懶，沒有設計此問題回答」。
5. **格式適中**：考慮到學生多用手機或 LINE 閱讀，回覆條理分明、善用列點，避免一大坨難以閱讀的文字。
6. **附上連結**：若有連結務必附上連結。
"""

# 用於管理各使用者的對話 Session
user_chats: Dict[str, Any] = {}
user_last_active: Dict[str, float] = {}

# 全域持久化 Google GenAI Client，防止局部變數被回收導致 client closed
_global_genai_client = None

def get_genai_client():
    global _global_genai_client
    if _global_genai_client is None and GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
        try:
            from google import genai
            _global_genai_client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            print(f"google-genai 初始化異常: {e}", flush=True)
    return _global_genai_client

def create_chat_with_fallback():
    """優先使用官方 google-genai，備選 google-generativeai，並在可用模型間依序嘗試"""
    # 1. 優先嘗試新版官方 google-genai SDK
    client = get_genai_client()
    if client:
        for model_name in MODELS_TO_TRY:
            try:
                chat = client.chats.create(
                    model=model_name,
                    config={
                        "system_instruction": SYSTEM_INSTRUCTION,
                        "temperature": 0.7,
                    }
                )
                print(f"✅ [google-genai] 成功連線模型: {model_name}", flush=True)
                return chat
            except Exception as err:
                print(f"⚠️ [google-genai] 模型 {model_name} 嘗試失敗: {err}", flush=True)

    # 2. 備選嘗試傳統 google-generativeai SDK
    try:
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=GEMINI_API_KEY)
        for model_name in MODELS_TO_TRY:
            try:
                model = legacy_genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=SYSTEM_INSTRUCTION
                )
                chat = model.start_chat(history=[])
                print(f"✅ [google-generativeai] 成功連線模型: {model_name}", flush=True)
                return chat
            except Exception as err:
                print(f"⚠️ [google-generativeai] 模型 {model_name} 嘗試失敗: {err}", flush=True)
    except Exception as e:
        print(f"google-generativeai 初始化異常: {e}", flush=True)

    return None

def get_or_create_chat(user_id: str):
    """取得或建立使用者的 Gemini Chat Session"""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return None

    now = time.time()
    if len(user_chats) > 500:
        expired = [uid for uid, t in user_last_active.items() if now - t > 1800]
        for uid in expired:
            user_chats.pop(uid, None)
            user_last_active.pop(uid, None)

    if user_id not in user_chats:
        chat = create_chat_with_fallback()
        if not chat:
            return None
        user_chats[user_id] = chat

    user_last_active[user_id] = now
    return user_chats[user_id]

def get_bot_reply(user_msg: str, user_id: str = "default_user") -> str:
    """
    接收使用者文字訊息，呼叫 Gemini AI 產生智能回覆
    """
    msg = user_msg.strip()
    if not msg:
        return "哈囉！有什麼關於東吳大學的疑問想聊聊嗎？隨時問我喔！"

    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return (
            "⚠️ 【系統提示】尚未設定 Gemini API Key！\n\n"
            "請至 Google AI Studio (https://aistudio.google.com/) 免費取得 API Key，\n"
            "並在 Render 的 Environment Variables 中設定 `GEMINI_API_KEY`。"
        )

    try:
        chat = get_or_create_chat(user_id)
        if not chat:
            return "抱歉，目前 AI 伺服器忙碌或模型無法連線，請確認你的 Gemini API Key 是否有效！"

        response = chat.send_message(msg)
        return response.text.strip()

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Gemini API 呼叫錯誤: {error_msg}", flush=True)
        user_chats.pop(user_id, None)
        return (
            f"哎呀，剛剛恍神了一下（{error_msg[:60]}...），"
            "可以請你再傳送一次剛剛的問題嗎？"
        )
