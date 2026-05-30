import json
import os
from datetime import datetime
from openai import AsyncOpenAI
import asyncio
from config import OPENROUTER_POOL, COGS_DIR, TW_TZ

PROMPT_PATH = os.path.join(COGS_DIR, "VoiceSensor", "utils", "prompt.txt")
prompt = ""
with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
    prompt = f.read() 

class AiAnalyzer:
    MODEL_ID = "nvidia/nemotron-3-nano-30b-a3b:free"
    key_lock = asyncio.Lock()

    @classmethod
    def get_client(cls):
        """動態產生 Client，它會自動從池子裡拿當前最新、可用的金鑰"""
        return AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_POOL.current_key,
        )

    @classmethod
    async def safe_switch_key(cls, failed_index: int) -> bool:
        """安全地切換金鑰 (具備執行緒鎖防護)"""
        async with cls.key_lock:
            if OPENROUTER_POOL.current_index == failed_index:
                if OPENROUTER_POOL.switch_to_next():
                    print(f"🔄 [語音意圖] 額度耗盡，已自動切換至第 {OPENROUTER_POOL.current_index + 1} 組 API Key！")
                    return True
                else:
                    print("❌ [語音意圖] 彈盡援絕！所有的 API Key 額度都已經耗盡！")
                    return False
            return True

    @staticmethod
    async def parse_ui_action(text: str, memory=None):
        """
        判斷使用者的語音意圖
        """
        print("開始分析文字意圖")
        now = datetime.now(TW_TZ)
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        content = f"現在時間為 {now_str}\n"
        content += prompt
        if memory:
            content += "\n\n上次的記憶為:\n" + memory
        content += "\n\n使用者文字為:\n" + text
        
        while True:
            current_index = OPENROUTER_POOL.current_index
            client = AiAnalyzer.get_client()

            try:
                response = await client.chat.completions.create(
                    model=AiAnalyzer.MODEL_ID,
                    messages=[{"role": "user", "content": content}],
                    response_format={ "type": "json_object" }
                )
                result = response.choices[0].message.content.strip() 
                print("分析json的結果:")
                print(result)
                return json.loads(result)
                
            except Exception as e:
                error_msg = str(e)
                if "402" in error_msg or "429" in error_msg or "insufficient_quota" in error_msg:
                    print(f"⚠️ [語音意圖] 第 {current_index + 1} 組 Key 失敗")
                    if await AiAnalyzer.safe_switch_key(current_index):
                        continue
                    return {"actions": []}
                else:
                    print(f"❌ OpenRouter error: {e}")
                    return {"actions": []}