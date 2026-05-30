import json
import re
from openai import AsyncOpenAI
from config import OPENROUTER_POOL
import asyncio
import os
import anyio
prompt_path = os.path.join(os.path.dirname(__file__), "gmail_prompt.txt")
class GmailAiAnalyzer:
    MODEL_ID = "nvidia/nemotron-3-super-120b-a12b:free" 
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
                    print(f"🔄 [Gmail] 額度耗盡，已自動切換至第 {OPENROUTER_POOL.current_index + 1} 組 API Key！")
                    return True
                else:
                    print("❌ [Gmail] ！所有的 API Key 額度都已經耗盡！")
                    return False
            return True
        
    @staticmethod
    def _build_prompt(prompt_template: str, subject: str, body: str, categories: list[dict]) -> str:
        if not categories:
            categories_prompt = "目前沒有任何分類。請在 category 欄位回傳 null。"
        else:
            cat_list_str = "\n".join([f"- {c['name']} (判斷規則: {c['desc']})" for c in categories])
            categories_prompt = (
                f"請從以下分類中挑選最適合的一個（必須完全符合名稱，絕對不要加上任何括號）。"
                f"如果都不適合，請在 category 欄位回傳 null。\n現有分類：\n{cat_list_str}"
            )

        return prompt_template.replace("{subject}", subject)\
                              .replace("{body}", body)\
                              .replace("{categories_prompt}", categories_prompt)

    @staticmethod
    def _parse_ai_response(raw_result: str, categories: list[dict]) -> tuple[str, str]:
        clean_json_str = re.sub(r"```json\n?|\n?```", "", raw_result).strip()
        parsed_data = json.loads(clean_json_str)
        
        category_name = parsed_data.get("category")
        summary = parsed_data.get("summary", "（無法生成摘要）")
        
        if isinstance(category_name, str):
            category_name = category_name.strip("【】「」[]'\" ")
        
        valid_category_names = [c["name"] for c in categories]
        if category_name not in valid_category_names:
            category_name = None
            
        print(f"💡 [解析結果] 最終分類: {category_name} | 摘要: {summary}")
        return category_name, summary

    @staticmethod
    async def analyze_and_classify_email(subject: str, body: str, categories: list[dict]) -> tuple[str, str]:
        # 非同步讀取 Prompt 範本 
        path = anyio.Path(prompt_path)
        prompt_template = await path.read_text(encoding="utf-8")

        # 組合最終 Prompt
        prompt = GmailAiAnalyzer._build_prompt(prompt_template, subject, body, categories)
        raw_result = "（無回傳內容）"
        
        while True:
            current_index = OPENROUTER_POOL.current_index
            client = GmailAiAnalyzer.get_client()

            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=GmailAiAnalyzer.MODEL_ID,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1
                    ),
                    timeout=120.0
                )
                
                if not hasattr(response, 'choices') or not response.choices:
                    print("❌ [API 異常] OpenRouter 回傳了無效的格式")
                    return None, "（API 回傳異常）"
                    
                message = response.choices[0].message
                if not message or not message.content:
                    print("❌ [API 異常] AI 回傳了空內容")
                    return None, "（AI 回傳空內容）"
                
                raw_result = message.content.strip()
                print(f"🤖 [AI 原始回覆]:\n{raw_result}")
                
                # 呼交輔助方法解析成果
                return GmailAiAnalyzer._parse_ai_response(raw_result, categories)

            except asyncio.TimeoutError:
                print(f"⏱️ [AI 超時] 分析信件 '{subject}' 時反應過慢，已跳過。")
                return None, "（AI 分析超時）"
                
            except json.JSONDecodeError:
                print(f"❌ [格式錯誤] AI 回傳內容非標準 JSON: {raw_result}")
                return None, "（摘要解析失敗）"
                
            except Exception as e:
                error_msg = str(e)
                if any(err in error_msg for err in ["402", "429", "insufficient_quota"]):
                    print(f"⚠️ [Gmail分析] 第 {current_index + 1} 組 Key 失敗")
                    if await GmailAiAnalyzer.safe_switch_key(current_index):
                        continue
                    return None, "（所有備用金鑰均已耗盡）"
                else:
                    import traceback
                    traceback.print_exc()
                    print(f"❌ [AI 錯誤] 分析失敗: {e}")
                    return None, "（AI 暫時無法連線）"