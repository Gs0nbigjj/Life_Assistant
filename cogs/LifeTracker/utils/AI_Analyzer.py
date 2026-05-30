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
    async def _execute_lifestyle_request(client, prompt, current_index) -> str:
        """
        執行單次 Lifestyle AI 請求。
        - 成功解析：回傳內容字串
        - 需要切換金鑰重試：回傳字串 "SWITCH_KEY"
        - 致命錯誤：回傳對應的錯誤提示訊息
        """
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
            # 檢查是否需要切換 Key
            if any(err in error_msg for err in ["402", "429", "insufficient_quota"]):
                return "SWITCH_KEY"
            
            print(f"❌ OpenRouter 分析失敗: {e}")
            return "⚠️ 分析服務暫時不可用。"

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

            # 將重責大任交給 execute 輔助方法
            res = await AiAnalyzer._execute_lifestyle_request(client, prompt, current_index)
            
            # 如果回傳結果是要切換金鑰，就觸發切換邏輯並 continue 繼續迴圈
            if res == "SWITCH_KEY":
                print(f"⚠️ [週總結] 第 {current_index + 1} 組 Key 失敗")
                if await AiAnalyzer.safe_switch_key(current_index):
                    continue
                return "⚠️ 所有 AI 備用金鑰均已耗盡，服務暫時不可用。"
            
            # 其他情況（成功拿到結果或遇到致命錯誤），直接回傳結果
            return res

    @staticmethod
    async def _execute_classify_batch_request(client, prompt, subcat_list, current_index) -> dict | str:
        """
        執行單次消費批次分類 AI 請求。
        - 成功拿到內容：交給現有的解析器並回傳 dict 結果
        - 需要切換金鑰重試：回傳字串 "SWITCH_KEY"
        - 致命錯誤/無效格式：回傳空字典 {}
        """
        try:
            response = await client.chat.completions.create(
                model=AiAnalyzer.CLASSIFY_MODEL_ID,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            if hasattr(response, 'choices') and response.choices:
                result_text = response.choices[0].message.content
                if result_text:
                    # 呼叫你原本就寫好的解析方法
                    return AiAnalyzer._parse_classify_response(result_text, subcat_list)
                        
            return {}
            
        except Exception as e:
            error_msg = str(e)
            # 檢查是否需要切換 Key
            if any(err in error_msg for err in ["402", "429", "insufficient_quota"]):
                return "SWITCH_KEY"
            
            print(f"❌ AI 批次分類失敗: {e}")
            return {}

    @staticmethod
    async def classify_consumption_batch(item_names: list, subcat_list: list) -> dict:
        """
        使用小模型進行「批次」消費分類
        """
        if not item_names or not subcat_list: 
            return {}

        items_text = "\n".join([f"- {item}" for item in item_names])
        subcats_str = ", ".join(subcat_list)

        # 非同步讀取檔案
        path = anyio.Path(classify_prompt_path)
        prompt_template = await path.read_text(encoding="utf-8")

        prompt = prompt_template.replace("{subcats_str}", subcats_str)\
                                .replace("{items_text}", items_text)
                                
        while True:
            current_index = OPENROUTER_POOL.current_index
            client = AiAnalyzer.get_client()

            # 將原本 while 迴圈內複雜的 try-except 委託給輔助方法
            res = await AiAnalyzer._execute_classify_batch_request(client, prompt, subcat_list, current_index)
            
            # 如果觸發換 Key 條件，執行切換邏輯並 continue 迴圈
            if res == "SWITCH_KEY":
                print(f"⚠️ [發票分類] 第 {current_index + 1} 組 Key 失敗")
                if await AiAnalyzer.safe_switch_key(current_index):
                    continue
                return {}
            
            # 成功解析或遇到致命錯誤，直接回傳結果
            return res
        
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