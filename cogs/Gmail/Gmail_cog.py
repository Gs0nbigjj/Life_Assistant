from discord.ext import commands, tasks
from cogs.Gmail.utils import EmailDatabaseManager, EmailTools
from cogs.Gmail.utils import Gmail_AI_Analyzer
from database.models import EmailConfig

class Gmail(commands.Cog):
    def __init__(self, bot, db_session):
        self.bot = bot
        self.db_manager = EmailDatabaseManager(db_session)

    async def cog_load(self):
        if not self.test_check_mail.is_running():
            self.test_check_mail.start()
            print("[Gmail] 背景收信排程已成功啟動！")

    @tasks.loop(seconds=30)
    async def test_check_mail(self):
        """Layer 01"""
        await self.bot.wait_until_ready()
        try:
            with self.db_manager.session() as session:
                user_ids = [c.user_id for c in session.query(EmailConfig.user_id).all()]
        except Exception as e:
            print(f"[資料庫輪詢] 查詢設定失敗: {e}")
            return

        if not user_ids:
            return

        for user_id in user_ids:
            try:
                await self._process_user_mailbox(user_id)
            except Exception as e:
                print(f"⚠️ [輪詢異常] 使用者 {user_id} 發生未知錯誤: {e}")

    async def _process_user_mailbox(self, user_id: str):
        """Layer 02"""
        user_config = EmailDatabaseManager.get_user_config(user_id)
        if not user_config: 
            return

        user_email = user_config['email']
        user_password = user_config['password']
        last_id = user_config['last_email_id']

        if not user_email or not user_password: 
            return

        tools = EmailTools(user_email, user_password)
        
        try:
            new_emails, drift_fix_id = await tools.get_unread_emails(last_id)
        except ValueError as ve:
            if str(ve) == "AUTH_FAILED":
                await self._handle_auth_failure(user_id, user_email)
                return
            raise ve
        except Exception as fetch_error:
            print(f"⚠️ [EmailTools] 使用者 {user_email} 暫時性抓取失敗: {fetch_error}")
            return 

        # 若有校正 ID
        if drift_fix_id:
            self.db_manager.update_last_email_id(user_id, drift_fix_id)
            print(f"🔧 [自動修復] 使用者 {user_email} ID 校正為: {drift_fix_id}")

        # 處理新郵件
        if new_emails:
            await self._analyze_and_archive_emails(user_id, user_email, new_emails)

    async def _handle_auth_failure(self, user_id: str, user_email: str):
        """Layer 03"""
        print(f"[密碼錯誤] 使用者 {user_email} 驗證失敗。")
        
        # 1. 發送私訊通知使用者
        user = self.bot.get_user(int(user_id))
        if user:
            try:
                msg = (
                    f"⚠️ **Gmail 設定已被系統移除**\n"
                    f"您先前綁定的帳號 `{user_email}` 登入失敗（帳號/密碼錯誤或授權失效）。\n"
                    f"為了您的帳號安全，系統已**自動刪除**該筆錯誤的信箱設定。\n"
                    f"請檢查您的「應用程式專用密碼」後，重新使用指令綁定以恢复功能。"
                )
                await user.send(msg)
                print(f"已私訊通知使用者 {user_id}")
            except Exception as dm_err:
                print(f"無法私訊使用者 {user_id}: {dm_err}")
        
        # 2. 資料庫刪除該筆錯誤設定
        try:
            with self.db_manager.session() as session:
                config_to_delete = session.query(EmailConfig).filter_by(user_id=user_id).first()
                if config_to_delete:
                    session.delete(config_to_delete)
                    session.commit()
                    print(f"[資料刪除] 已強制移除使用者 {user_id} 的錯誤信箱設定")
        except Exception as db_err:
            print(f"刪除使用者資料庫紀錄時失敗: {db_err}")

    async def _analyze_and_archive_emails(self, user_id: str, user_email: str, new_emails: list):
        """Layer 04"""
        user_categories = EmailDatabaseManager.get_user_categories(user_id)

        for email_info in new_emails:
            print(f"🔍 分析信件：{email_info['subject']} ...")
            
            cat_name, summary = await Gmail_AI_Analyzer.analyze_and_classify_email(
                subject=email_info['subject'],
                body=email_info['body'],
                categories=user_categories
            )
            
            email_info['ai_summary'] = summary
            email_info['category'] = cat_name

            if cat_name:
                target_cat = next((c for c in user_categories if c['name'] == cat_name), None)
                if target_cat:
                    self.db_manager.save_categorized_email(target_cat['id'], email_info, summary)
                    print(f"📁 歸檔至 [{cat_name}]")
            else:
                print("⏩ 未符合分類，略過。")

            # 更新進度
            self.db_manager.update_last_email_id(user_id, str(email_info['id']))