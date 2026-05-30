# cogs\LifeTracker\utils\AI_Analyzer.py
from openai import AsyncOpenAI
from config import OPENROUTER_API_KEY

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

class AiAnalyzer:
    SUMMARY_MODEL_ID = "nvidia/nemotron-3-super-120b-a12b:free"
    CLASSIFY_MODEL_ID = "nvidia/nemotron-3-super-120b-a12b:free"

    @staticmethod
    async def analyze_lifestyle(category_name, data_content):
        if not data_content or str(data_content).strip() in ["", "[]", "None"]:
            return "本週尚無相關紀錄，繼續保持追蹤習慣喔！"

        prompt = f"""
        你是一位專業的生活導師。以下是使用者在「{category_name}」分類下的近期紀錄：
        {data_content}
        
        請進行客觀分析：
        1. 總結整體情況（約75字）。
        2. 具體行動建議（約75字）。
        使用繁體中文，總字數 150 字以內。
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

        prompt = f"""
        你是一位消費紀錄分類專家。請將以下購買品項分類到指定的標籤清單中。
        標籤清單：{subcats_str}
        
        品項清單：
        {items_text}
        
        請嚴格按照以下格式回覆，每行一個，請直接輸出純文字，不要有任何多餘的解釋：
        品項名稱:標籤名稱
        
        如果真的找不到適合的，請填寫「其他」。
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
                    return AiAnalyzer._parse_classify_response(result_text, subcat_list)
                        
            return {}
            
        except Exception as e:
            print(f"❌ AI 批次分類失敗: {e}")
            return {}
        
    @staticmethod
    def _parse_classify_response(result_text: str, subcat_list: list) -> dict:
        """解析大模型回傳的逐行文字，並進行格式相容性與標籤防呆"""
        result_mapping = {}
        
        for line in result_text.split('\n'):
            line = line.strip()
            
            # 支援中英文冒號切分
            if ':' in line:
                parts = line.split(':', 1)
            elif '：' in line:
                parts = line.split('：', 1)
            else:
                continue
                
            if len(parts) == 2:
                k = parts[0].strip("- *")
                v = parts[1].strip()
                
                # 確保標籤在預期清單中，否則校正歸類為「其他」
                if v not in subcat_list:
                    v = "其他"
                result_mapping[k] = v
                
        return result_mapping