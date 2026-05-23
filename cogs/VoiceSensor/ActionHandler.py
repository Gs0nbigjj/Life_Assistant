from database.db_utils import upsert_mem
from cogs.LifeTracker.utils import LifeTracker_Manager
import discord
from datetime import datetime
from config import TW_TZ
from cogs.Gmail.ui.View.GmailDashboardView import GmailDashboardView
from cogs.Gmail.utils import EmailDatabaseManager
from cogs.Stock.utils import StockManager
from cogs.Stock.ui.View.StockDashboardView import StockDashboardView
import asyncio
            
            
class ActionHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_actions(self, message, processing_msg, actions):
        embed, view, content, attachments = None, None, "", []
        for step in actions:
            pack = await self.execute_action(message, step)
            if not pack:
                content = "在AI分析意圖時，發生不可預期錯誤。"
            else:
                embed, view, content, attachments = pack
        await processing_msg.edit(embed=embed, view=view, content=content, attachments=attachments)
        
    
    async def execute_action(self, message, step):
        action = step.get("action")
        data = step.get("data", {})
        print(f"action = {action}")

        action_handlers = {
            # 1. 系統主選單模組
            "OPEN_SYSTEM_START": self._handle_system_start,
            "OPEN_LIFE_ASSISTANT": self._handle_life_assistant,
            
            # 2. 記帳生活追蹤模組
            "OPEN_LIFE_DIARY": self._handle_life_diary,
            "CREATE_CATEGORY_EMPTY": self._handle_create_category_empty,
            "CREATE_CATEGORY_WITH_DATA": self._handle_create_category_with_data,
            "DELETE_CATEGORY": self._handle_delete_category,
            
            # 3. 行事曆行程模組
            "CREATE_ITINERARY_EMPTY": self._handle_create_itinerary_empty,
            "CREATE_ITINERARY_WITH_DATA": self._handle_create_itinerary_with_data,
            "DELETE_ITINERARY": self._handle_delete_itinerary,
            "VIEW_ITINERARY": self._handle_view_itinerary,
            
            # 4. Gmail 連結模組
            "GMAIL_HOME": self._handle_gmail_home,
            "CREATE_GMAIL_CATEGORY_EMPTY": self._handle_create_gmail_category_empty,
            "CREATE_GMAIL_CATEGORY_WITH_DATA": self._handle_create_gmail_category_with_data,
            "DELETE_GMAIL_CATEGORY": self._handle_delete_gmail_category,
            "SET_GMAIL_ACCOUNT_EMPTY": self._handle_set_gmail_account_empty,
            "SET_GMAIL_ACCOUNT_WITH_DATA": self._handle_set_gmail_account_with_data,
            "GMAIL_SETUP_GUIDE": self._handle_gmail_setup_guide,
            
            # 5. 股市監控模組
            "STOCK_MONITOR_HOME": self._handle_stock_monitor_home,
            "STOCK_PROFIT_DETAIL": self._handle_stock_profit_detail,
            "ADD_STOCK_MONITOR_EMPTY": self._handle_add_stock_monitor_empty,
            "ADD_STOCK_MONITOR_WITH_DATA": self._handle_add_stock_monitor_with_data,
            "REMOVE_STOCK_MONITOR": self._handle_remove_stock_monitor,
            "QUICK_STOCK_QUERY": self._handle_quick_stock_query,
            
            # 6. 大模型聊天模組
            "CHAT": self._handle_chat
        }

        handler = action_handlers.get(action)
        
        if handler:
            # 執行對應的獨立處置器並回傳
            return await handler(message, data)
            
        # Default fallback (原本的 else 區塊)
        print(f"action: {action} 尚未設置")
        return None


    # --- 1. 系統控制選單 ---
    async def _handle_system_start(self, message, data):
        
        from cogs.System.ui.View.SystemStartView import SystemStartView
        embed, view = SystemStartView.create_start_ui(self.bot)
        return embed, view, "", []

    async def _handle_life_assistant(self, message, data):
        
        from cogs.System.ui.View.SystemStartView import MainControlView
        embed, view = MainControlView.create_dashboard_ui(self.bot)
        return embed, view, "", []

    # --- 2. 記帳模組 ---
    async def _handle_life_diary(self, message, data):
        
        from cogs.LifeTracker.ui.View import LifeDashboardView
        embed, view = LifeDashboardView.create_dashboard(self.bot, message.author.id)
        return embed, view, "", []

    async def _handle_create_category_empty(self, message, data):
        
        from cogs.LifeTracker.ui.Button.SetupBtn import SetupBtn
        view = ActionHandler.get_button_view(SetupBtn(self.bot))
        return None, view, "", []

    async def _handle_create_category_with_data(self, message, data):
        
        embed, view, content = None, None, ""
        property_names = ["category_name", "fields", "subcategories"]
        category_name, fields, subcategories = (data.get(x) for x in property_names)
        
        cat_name = category_name.strip()
        fields_list = [f.strip() for f in fields if f.strip()]
        subcats_list = [s.strip() for s in subcategories if s.strip()] if subcategories else []
           
        success, error_msg = LifeTracker_Manager.create_category(
            user_id=message.author.id, username=message.author.name,
            cat_name=cat_name, fields_list=fields_list, subcats_list=subcats_list
        )
        if not success:
            content = error_msg
        else:
            from cogs.LifeTracker.ui.Modal.SetupCategoryModal import SetupCategoryModal
            embed, view = SetupCategoryModal.create_dashboard(self.bot, message.author.id)
        return embed, view, content, []

    async def _handle_delete_category(self, message, data):
        
        embed, view, content = None, None, ""
        name = data.get("category_name", "").strip()
        if name:
            if LifeTracker_Manager.delete_category(category_name=name):
                from cogs.LifeTracker.ui.Select.DeleteCategorySelect import DeleteCategorySelect
                embed, view = DeleteCategorySelect.create_dashboard(self.bot, message.author.id)
            else:
                cats = LifeTracker_Manager.get_deletable_categories(user_id=message.author.id)
                content = f"刪除錯誤 {name} 並不存在或不可刪除\n目前可刪除目錄:\n" + "\n".join([f" - {cat.name}" for cat in cats]) if cats else f"刪除錯誤 {name} 並不存在或不可刪除\n目前無刪除目錄"
        else:
            from cogs.LifeTracker.ui.Button.DeleteCategoryBtn import DeleteCategoryBtn
            btn = DeleteCategoryBtn.get_Btn_with_user_id(self.bot, message.author.id)
            embed, view = btn.create_dashboard()
        return embed, view, content, []

    # --- 3. 行事曆模組 ---
    async def _handle_create_itinerary_empty(self, message, data):
        
        from cogs.Itinerary.ui.View.ItineraryAddView import ItineraryAddView
        embed, view = ItineraryAddView.create_ui()
        return embed, view, "", []

    async def _handle_create_itinerary_with_data(self, message, data):
        
        attachments = []
        property_names = ["description", "year", "month", "day", "hour", "minute", "is_private"]
        description, year, month, day, hour, minute, is_private = (data.get(x) for x in property_names)
        
        minute = minute or 0
        is_private = 1 if is_private is None else is_private
        event_time = datetime(int(year), int(month), int(day), int(hour), minute, tzinfo=TW_TZ)
        clean_time = event_time.replace(tzinfo=None, second=0, microsecond=0)
        
        from cogs.Itinerary.utils.calendar_manager import CalendarDatabaseManager
        from cogs.Itinerary.itinerary_cog import Itinerary
        success, report = CalendarDatabaseManager.add_event(
            user_id=message.author.id, user_name=message.author.name,
            event_time=clean_time, description=description, is_private=(is_private == 1)
        )
        if not success:
            content = report
            embed, view = None, None
        else:
            embed, view, file = Itinerary.create_itinerary_dashboard_ui(message.author.id)
            embed.title = "✅ 行程新增成功！"
            embed.color = discord.Color.green()
            attachments = [file]
            content = ""
        return embed, view, content, attachments

    async def _handle_delete_itinerary(self, message, data):
        
        from cogs.Itinerary.ui.View.ItineraryDeleteView import ItineraryDeleteView
        embed, view = ItineraryDeleteView.create_ui(message.author.id)
        return embed, view, "", []

    async def _handle_view_itinerary(self, message, data):
        
        from cogs.Itinerary.ui.View.ItineraryDashboardView import ItineraryDashboardView
        embed, view, file = ItineraryDashboardView.create_ui(message.author.id)
        return embed, view, "", [file]

    # --- 4. Gmail 模組 ---
    async def _handle_gmail_home(self, message, data):
        
        embed, view = GmailDashboardView.create_ui(message.author.id)
        return embed, view, "", []

    async def _handle_create_gmail_category_empty(self, message, data):
        
        from cogs.Gmail.ui.Button.AddCategoryBtn import AddCategoryBtn
        view = ActionHandler.get_button_view(AddCategoryBtn(message.author.id))
        return None, view, "", []

    async def _handle_create_gmail_category_with_data(self, message, data):
        
        embed, view, content = None, None, ""
        category_name = data.get("category_name")
        description = data.get("description")
        from cogs.Gmail.ui.Modal.AddCategoryModal import AddCategoryModal
        success, msg = AddCategoryModal.add_and_check(message.author.id, category_name, description)
        
        if not success:
            content = msg
        else:
            embed, view = GmailDashboardView.create_ui(message.author.id)
            if msg:
                embed.description = f"🎉 **{msg}**\n\n{embed.description}"
        return embed, view, content, []

    async def _handle_delete_gmail_category(self, message, data):
        
        embed, view, content = None, None, ""
        category_name = data.get("category_name")
        categories = EmailDatabaseManager.get_user_categories(message.author.id)
        
        if not categories:
            content = "目前沒有可刪除的GMAIL分類"
        elif category_name:
            if EmailDatabaseManager.delete_category(category_name=category_name):
                content = f"GMAIL分類({category_name})以成功刪除"
            else:
                content = f"刪除錯誤 {category_name} 並不存在或不可刪除\n目前可刪除目錄:\n" + "\n".join([f' - {cat["name"]}' for cat in categories])
        else:
            from cogs.Gmail.ui.View.DeleteCategoryView import DeleteCategoryView
            embed, view = DeleteCategoryView.create_ui(message.author.id, categories)
        return embed, view, content, []

    async def _handle_set_gmail_account_empty(self, message, data):
        
        from cogs.Gmail.ui.Button.SetupMailBtn import SetupMailBtn
        view = ActionHandler.get_button_view(SetupMailBtn())
        return None, view, "", []

    async def _handle_set_gmail_account_with_data(self, message, data):
        
        gmail_address, app_password = data.get("gmail_address"), data.get("app_password")
        from cogs.Gmail.utils import EmailTools
        clean_address = EmailTools()._extract_pure_email(gmail_address)
        report = EmailDatabaseManager.save_user_config(message.author.id, message.author.name, clean_address, app_password)    
        content = report if "❌" in report else "GMAIL已成功連結"
        return None, None, content, []

    async def _handle_gmail_setup_guide(self, message, data):
        
        from cogs.Gmail.ui.View.HelpView import HelpView
        view = HelpView(message.author.id)
        embed = view.generate_embed()
        return embed, view, "", []

    # --- 5. 股市模組 ---
    async def _handle_stock_monitor_home(self, message, data):
        
        embed, view = StockDashboardView.create_dashboard(self.bot, message.author.id)
        return embed, view, "", []

    async def _handle_stock_profit_detail(self, message, data):
        
        embed, view, content = None, None, ""
        stocks = StockManager.get_user_stocks(message.author.id)
        if not stocks:
            content = "⚠️ 你的監控清單目前是空的。"
        else:
            from cogs.Stock.ui.View.StockListView import StockListView
            embed, view = await StockListView.create_ui(self.bot, message.author.id, message.author.name)
        return embed, view, content, []

    async def _handle_add_stock_monitor_empty(self, message, data):
        
        from cogs.Stock.ui.Button.StockAddBtn import StockAddBtn
        view = ActionHandler.get_button_view(StockAddBtn(self.bot))
        return None, view, "", []

    async def _handle_add_stock_monitor_with_data(self, message, data):
        
        embed, view, content = None, None, ""
        from cogs.Stock.ui.Modal.StockAddModal import StockAddModal
        error_msg = await StockAddModal.check(
            data.get("stock_code"), data.get("share_quantity"), data.get("total_cost"),
            data.get("rise_alert_percent"), data.get("fall_alert_percent"),
            message.author.id, message.author.name
        )
        if error_msg:
            content = error_msg
        else:
            embed, view = StockDashboardView.create_dashboard(self.bot, message.author.id)
            embed.title = "✅ 新增成功！"
        return embed, view, content, []

    async def _handle_remove_stock_monitor(self, message, data):
        
        embed, view, content = None, None, ""
        stock_code = data.get("stock_code")
        stocks = StockManager.get_user_stocks(message.author.id)
        if not stocks:
            content = "您目前沒有監控任何股票，無法執行刪除操作！"
        elif not stock_code:
            from cogs.Stock.ui.View.StockDeleteView import StockDeleteView
            embed, view = StockDeleteView.create_ui(self.bot, message.author.id)
        else:
            from cogs.Stock.ui.Select.StockDeleteSelect import StockDeleteSelect
            embed, view = StockDeleteSelect.create_dashboard(self.bot, message.author.id, stock_code)
        return embed, view, content, []

    async def _handle_quick_stock_query(self, message, data):
        
        embed, view = None, None
        stock_code = data.get("stock_code")
        if not stock_code:
            from cogs.Stock.ui.Button.StockQueryBtn import StockQueryBtn
            view = ActionHandler.get_button_view(StockQueryBtn(self.bot))
        else:
            from cogs.Stock.ui.Modal.StockQueryModal import StockQueryModal
            embed, view = await StockQueryModal.create_dashboard(self.bot, message.author.id, stock_code)
        return embed, view, "", []

    # --- 6. AI 聊天記憶模組 ---
    async def _handle_chat(self, message, data):
        
        content = data.get("message", "")
        mem_text = data.get("memory")
        if mem_text:
            upsert_mem(message.author.id, message.author.name, mem_text)
        return None, None, content, []

    @staticmethod
    def get_button_view(button):
        view = discord.ui.View(timeout=60)
        view.add_item(button)
        return view