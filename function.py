import os
import time
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# 讀取 Gemini API Key 與模型設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.5-flash"

# 讀取知識庫檔案 (knowledge.txt)
def load_knowledge_base() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "knowledge.txt")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"讀取 knowledge.txt 失敗: {e}")
    return "暫無外部知識庫資料。"

KNOWLEDGE_DATA = load_knowledge_base()

# 建立 System Prompt
SYSTEM_INSTRUCTION = f"""
你是由東吳大學學生團隊開發的「東吳新生專屬 AI 導師（東吳新生小幫手）」。
你的身份是一位熱心、親切、幽默且經驗豐富的東吳大學高年級學長姐。

你的任務是陪伴大一新生，以自然對話的形式回答他們關於校園生活、選課、宿舍、交通、社團、行政手續等所有疑問，減緩他們初入大學的焦慮。

以下是「東吳大學新生指南知識庫」，請優先根據以下資訊回答：
==================== 知識庫開始 ====================
{KNOWLEDGE_DATA}
==================== 知識庫結束 ====================

【回覆指導原則】
1. **自然聊天**：學生不需輸入完全一樣的關鍵字，請理解學生的口語表達（例如「肚子餓了雙溪有啥吃的」、「外雙溪怎麼去」、「選課沒選到怎麼辦」、「想交朋友」等），直接如同朋友般對話。
2. **語氣風格**：親切、同理、繁體中文（台灣習慣用語，如：學長姐、大一、學分、加退選、體檢、宿舍等），適度使用 Emoji 增加生動感。
3. **資訊精確**：校內相關規定請嚴格依據知識庫回答；若學生詢問的細節不在知識庫中，請誠實說明並指引學生洽詢對應處室（例如：選課洽課務組、住宿找住宿中心、學雜費洽生輔組或註冊組），並附上電話或分機。
4. **格式適中**：考慮到學生多用手機或 LINE 閱讀，回覆條理分明、善用列點，避免一大坨難以閱讀的文字。
"""

# 用於管理各使用者的對話 Session（以 user_id 為 Key）
user_chats: Dict[str, Any] = {}
user_last_active: Dict[str, float] = {}

def get_or_create_chat(user_id: str):
    """取得或建立使用者的 Gemini Chat Session"""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return None

    # 清理閒置超過 30 分鐘的連線
    now = time.time()
    if len(user_chats) > 500:
        expired = [uid for uid, t in user_last_active.items() if now - t > 1800]
        for uid in expired:
            user_chats.pop(uid, None)
            user_last_active.pop(uid, None)

    if user_id not in user_chats:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                system_instruction=SYSTEM_INSTRUCTION
            )
            chat = model.start_chat(history=[])
            user_chats[user_id] = chat
        except Exception as e:
            print(f"建立 Gemini Chat 失敗: {e}")
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel(
                    model_name="gemini-3.5-flash",
                    system_instruction=SYSTEM_INSTRUCTION
                )
                chat = model.start_chat(history=[])
                user_chats[user_id] = chat
            except Exception as ex:
                print(f"Fallback 建立 Chat 也失敗: {ex}")
                return None

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
            "並在 Hugging Face Space 的 Settings ➔ Variables and secrets 中新增 `GEMINI_API_KEY`。"
        )

    try:
        chat = get_or_create_chat(user_id)
        if not chat:
            return "抱歉，目前 AI 伺服器忙碌中，請稍後再試一次！"

        response = chat.send_message(msg)
        return response.text.strip()

    except Exception as e:
        error_msg = str(e)
        print(f"Gemini API 呼叫錯誤: {error_msg}")
        
        # 若 Session 失效或配額超限，重置該用戶的 Session
        user_chats.pop(user_id, None)
        return (
            f"哎呀，恍神了一下（{error_msg[:60]}...），"
            "可以請你再傳送一次剛剛的問題嗎？"
        )
