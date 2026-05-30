import json
import os
from datetime import datetime
from openai import AsyncOpenAI
from config import OPENROUTER_API_KEY, COGS_DIR, TW_TZ

# 初始化 OpenRouter 客戶端
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

PROMPT_PATH = os.path.join(COGS_DIR, "VoiceSensor", "utils", "prompt.txt")
prompt = ""
with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
    prompt = f.read() 

class AiAnalyzer:
    MODEL_ID = "nvidia/nemotron-3-nano-30b-a3b:free"
    @staticmethod
    async def parse_ui_action(text: str, memory=None):
        """
        判斷使用者的語音意圖
        """
        print("開始分析文字意圖")
        now = datetime.now(TW_TZ)
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        content = f"現在時間為 {now_str}\n"
        content = prompt
        if memory:
            content += "\n\n上次的記憶為:\n" + memory
        content += "\n\n使用者文字為:\n" + text
        
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
            print("❌ OpenRouter error:", e)
            return json.loads('{"actions": []}')