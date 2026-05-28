import discord
from discord import ui
from cogs.Stock.utils import get_stock_quote, StockManager, fugle_api_lock
from cogs.Stock.stock_config import FUGLE_TOKEN
from cogs.BasicDiscordObject import ValidatedModal 

class StockAddModal(ValidatedModal):
    symbol = ui.TextInput(label="股票代號", placeholder="例如: 2330 (不支持指數監控)", min_length=4, max_length=10)
    shares = ui.TextInput(label="持股數量", placeholder="例如: 1000", default="0", required=False)
    total_cost = ui.TextInput(label="總投入成本 (含手續費)", placeholder="例如: 650000", default="0", required=False)
    up_percent = ui.TextInput(label="漲幅預警 (%)", placeholder="例如: 5 (代表 5%)", required=False)
    down_percent = ui.TextInput(label="跌幅預警 (%)", placeholder="例如: -3 (代表 -3%)", required=False)

    def __init__(self, bot):
        super().__init__(title="新增監控股票")
        self.bot = bot

    async def execute_logic(self, interaction: discord.Interaction) -> str | None:
        """執行校驗與存檔 (交給父類別自動驗證)"""
        return await StockAddModal.check(
            self.symbol.value, 
            self.shares.value, 
            self.total_cost.value, 
            self.up_percent.value, 
            self.down_percent.value, 
            interaction.user.id, 
            interaction.user.name
        )

    async def on_success(self, interaction: discord.Interaction):
        """成功後的畫面更新"""
        from cogs.Stock.ui.View.StockDashboardView import StockDashboardView
        
        embed, view = StockDashboardView.create_dashboard(self.bot, interaction.user.id)
        embed.title = "✅ 新增成功！"

        await interaction.response.edit_message(embed=embed, view=view)
         
        
    @staticmethod
    async def check(symbol: str, shares, total_cost, up_percent, down_percent, user_id, user_name):
        sym = str(symbol).strip().upper()
        try:
            num_shares = int(float(str(shares).strip() or 0))
            cost_val = float(str(total_cost).strip() or 0.0)
            
            if num_shares < 0 or cost_val < 0:
                return "❌ 數量或成本不合理：持股與成本不能為負數！"
                
            avg_price = cost_val / num_shares if num_shares > 0 else None
            
            up = None
            if up_percent is not None and str(up_percent).strip():
                up_val = float(str(up_percent).replace('%', '').strip())
                if up_val <= 0:
                    return "❌ 漲幅預警錯誤：必須是「大於 0 的正數」喔！(例如: 5)"
                up = up_val / 100

            down = None
            if down_percent is not None and str(down_percent).strip():
                down_val = float(str(down_percent).replace('%', '').strip())
                if down_val >= 0:
                    return "❌ 跌幅預警錯誤：必須是「小於 0 的負數」喔！(例如: -3)"
                down = down_val / 100

            async with fugle_api_lock:
                info = get_stock_quote(sym, FUGLE_TOKEN)
            
            if not info or "lastPrice" not in info:
                return f"❌ 找不到股票 `{sym}`，請確認代號是否正確。"

            data = {
                'symbol': sym, 'name': info['name'], 'shares': num_shares,
                'total_cost': cost_val, 'buy_price': avg_price, 'up': up, 'down': down
            }
            
            StockManager.add_stock(user_id, user_name, data)
            return None 
            
        except ValueError:
            return "❌ 格式錯誤！請確保您填入的都是「正確的數字」(不要包含奇怪的符號)。"
        except Exception as e:
            print(f"❌ 新增出錯: {e}")
            return f"❌ 系統錯誤: {e}"