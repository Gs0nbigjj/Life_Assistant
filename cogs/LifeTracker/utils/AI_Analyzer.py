# cogs\LifeTracker\utils\AI_Analyzer.py
from openai import AsyncOpenAI
import asyncio
from config import OPENROUTER_POOL
import os
import anyio
classify_prompt_path = os.path.join(os.path.dirname(__file__), "classify_prompt.txt")
summary_prompt_path = os.path.join(os.path.dirname(__file__), "summary_prompt.txt")
class AiAnalyzer:
    SUMMARY_MODEL_ID = "nvidia/nemotron-3-super-120b-a12b:free"
    CLASSIFY_MODEL_ID = "nvidia/nemotron-3-super-120b-a12b:free"

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
                    print(f"🔄 [消費追蹤] 額度耗盡，已自動切換至第 {OPENROUTER_POOL.current_index + 1} 組 API Key！")
                    return True
                else:
                    print("❌ [消費追蹤] 彈盡援絕！所有的 API Key 額度都已經耗盡！")
                    return False
            return True

    @staticmethod
    async def analyze_lifestyle(category_name, data_content):
        if not data_content or str(data_content).strip() in ["", "[]", "None"]:
            return "本週尚無相關紀錄，繼續保持追蹤習慣喔！"

        path = anyio.Path(summary_prompt_path)
        prompt_template = await path.read_text(encoding="utf-8")

        prompt = prompt_template.replace("{category_name}", category_name)\
                                .replace("{data_content}", str(data_content))
        while True:
            current_index = OPENROUTER_POOL.current_index
            client = AiAnalyzer.get_client()

            try:
                response = await client.chat.completions.create(
                    model=AiAnalyzer.SUMMARY_MODEL_ID,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    timeout=180.0
                )
                if hasattr(response, 'choices') and response.choices:
                    content = response.choices[0].message.content
                    return content.strip() if content else "⚠️ AI 未回傳分析結果。"
                else:
                    return "⚠️ 分析服務目前忙線中，回傳格式異常。"
            except Exception as e:
                error_msg = str(e)
                if "402" in error_msg or "429" in error_msg or "insufficient_quota" in error_msg:
                    print(f"⚠️ [週總結] 第 {current_index + 1} 組 Key 失敗")
                    if await AiAnalyzer.safe_switch_key(current_index):
                        continue
                    return "⚠️ 所有 AI 備用金鑰均已耗盡，服務暫時不可用。"
                else:
                    print(f"❌ OpenRouter 分析失敗: {e}")
                    return "⚠️ 分析服務暫時不可用。"

    @staticmethod
    async def classify_consumption_batch(item_names: list, subcat_list: list) -> dict:
        """
        使用小模型進行「批次」消費分類
        """
        if not item_names or not subcat_list: 
            return {}

        items_text = "\n".join([f"- {item}" for item in item_names])
        subcats_str = ", ".join(subcat_list)

        path = anyio.Path(classify_prompt_path)
        prompt_template = await path.read_text(encoding="utf-8")

        prompt = prompt_template.replace("{subcats_str}", subcats_str)\
                                .replace("{items_text}", items_text)
        while True:
            current_index = OPENROUTER_POOL.current_index
            client = AiAnalyzer.get_client()

            try:
                response = await client.chat.completions.create(
                    model=AiAnalyzer.CLASSIFY_MODEL_ID,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0
                )
                
                if hasattr(response, 'choices') and response.choices:
                    result_text = response.choices[0].message.content
                    if result_text:
                        return AiAnalyzer._parse_classify_response(result_text, subcat_list)
                            
                return {}
                
            except Exception as e:
                error_msg = str(e)
                if "402" in error_msg or "429" in error_msg or "insufficient_quota" in error_msg:
                    print(f"⚠️ [發票分類] 第 {current_index + 1} 組 Key 失敗")
                    if await AiAnalyzer.safe_switch_key(current_index):
                        continue
                    return {}
                else:
                    print(f"❌ AI 批次分類失敗: {e}")
                    return {}
        
    @staticmethod
    def _parse_classify_response(result_text: str, subcat_list: list) -> dict:
        """解析大模型回傳的逐行文字，並進行格式相容性與標籤防呆"""
        result_mapping = {}
        
        for line in result_text.split('\n'):
            line = line.strip()
            
            if ':' in line:
                parts = line.split(':', 1)
            elif '：' in line:
                parts = line.split('：', 1)
            else:
                continue
                
            if len(parts) == 2:
                k = parts[0].strip("- *")
                v = parts[1].strip()
                
                if v not in subcat_list:
                    v = "其他"
                result_mapping[k] = v
                
        return result_mapping