import discord
from discord import ui
from cogs.Stock.utils import get_stock_quote, StockManager, fugle_api_lock
from cogs.Stock.stock_config import FUGLE_TOKEN

class StockAddModal(ui.Modal, title="新增監控股票"):
    symbol = ui.TextInput(label="股票代號", placeholder="例如: 2330 (不支持指數監控)", min_length=4, max_length=10)
    shares = ui.TextInput(label="持股數量", placeholder="未持有請填 0", default="0", required=False)
    total_cost = ui.TextInput(label="總投入成本 (含手續費)", placeholder="未持有請填 0", default="0", required=False)
    up_percent = ui.TextInput(label="漲幅預警 (%)", placeholder="例如: 5 (代表 +5%)", required=False)
    down_percent = ui.TextInput(label="跌幅預警 (%)", placeholder="例如: -3 (代表 -3%)", required=False)

    def __init__(self, bot):
        super().__init__(title="新增監控股票")
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        error_msg = await self.execute_logic(interaction)
        
        if error_msg:
            # 發生校驗錯誤時，使用彈出式私訊通知使用者
            await interaction.followup.send(error_msg, ephemeral=True)
        else:
            from cogs.Stock.ui.View import StockDashboardView
            embed, view = StockDashboardView.create_dashboard(self.bot, interaction.user.id)
            embed.title = "✅ 新增成功！"
            await interaction.edit_original_response(embed=embed, view=view)

    async def execute_logic(self, interaction: discord.Interaction) -> str | None:
        """執行校驗與存檔"""
        sym = self.symbol.value.strip().upper()
        
        shares_raw = self.shares.value.strip().replace(",", "")
        if not shares_raw:
            shares_raw = "0"
        if not shares_raw.isdigit():
            return "❌ 【持股數量】格式錯誤！請填入大於或等於 0 的整數數字（不可包含負號或小數點）。"
        num_shares = int(shares_raw)

        cost_raw = self.total_cost.value.strip().replace(",", "")
        if not cost_raw:
            cost_raw = "0"
        try:
            cost_val = float(cost_raw)
            if cost_val < 0:
                return "❌ 【總投入成本】不能為負數！"
        except ValueError:
            return "❌ 【總投入成本】格式錯誤！請填入正確的數字。"

        """
        if num_shares > 0 and cost_val == 0:
            return "❌ 既然您持有股票，【總投入成本】應該大於 0。"
        if num_shares == 0 and cost_val > 0:
            return "❌ 持股數量為 0 時，【總投入成本】也應該為 0。若純監控請皆填 0。"
        """
        
        up_raw = self.up_percent.value.strip().replace("%", "")
        up = None
        if up_raw:
            try:
                up = float(up_raw)
                if up <= 0:
                    return "❌ 【漲幅預警】必須是大於 0 的數字（例如填 5 代表 +5%）。"
            except ValueError:
                return "❌ 【漲幅預警】格式錯誤！請填入純數字。"

        down_raw = self.down_percent.value.strip().replace("%", "")
        down = None
        if down_raw:
            try:
                #負數防呆
                down = -abs(float(down_raw))
            except ValueError:
                return "❌ 【跌幅預警】格式錯誤！請填入純數字。"

        # 檢查通過，送入核心邏輯
        return await StockAddModal.check(sym, num_shares, cost_val, up, down, interaction.user.id, interaction.user.name)
         
    @staticmethod
    async def check(symbol: str, shares: int, total_cost: float, up: float|None, down: float|None, user_id, user_name):
        sym = symbol.strip().upper()
        try:
            avg_price = total_cost / shares if shares > 0 else None
            
            # 串接 API 確認股票是否存在 (透過 fugle_api_lock 確保執行緒安全)
            async with fugle_api_lock:
                info = get_stock_quote(sym, FUGLE_TOKEN)
            
            curr_price = info.get('lastPrice') or info.get('price') if info else None
            
            if not info or not curr_price:
                return f"❌ 找不到股票或指數 `{sym}`，請確認代號是否正確。"

            data = {
                'symbol': sym, 
                'name': info['name'], 
                'shares': shares,
                'total_cost': total_cost, 
                'buy_price': avg_price, 
                'up': up / 100 if up else None, 
                'down': down / 100 if down else None
            }
            
            StockManager.add_stock(user_id, user_name, data)
            return None 
            
        except ValueError:
            return "❌ 格式錯誤！請確保您填入的都是「正確的數字」(不要包含奇怪的符號)。"
        except Exception as e:
            print(f"❌ 新增出錯: {e}")
            return f"❌ 系統錯誤: {e}"