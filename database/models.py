# database/models.py
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, Boolean, Text, JSON, func, Float, Date
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

CASCADE_DELETE_ORPHAN = "all, delete-orphan"
USER_FK_TARGET = "users.discord_id"

class BotSettings(Base):
    __tablename__ = 'bot_settings'

    id = Column(BigInteger, primary_key=True, autoincrement=False) 
    
    dashboard_channel_id = Column(BigInteger, nullable=True)
    login_notify_channel_id = Column(BigInteger, nullable=True)
    calendar_notify_channel_id = Column(BigInteger, nullable=True)
    gpt_channel_id = Column(BigInteger, nullable=True)
    
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class User(Base):
    __tablename__ = 'users'

    discord_id = Column(BigInteger, primary_key=True, autoincrement=False)
    username = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    email_config = relationship("EmailConfig", back_populates="user", uselist=False, cascade=CASCADE_DELETE_ORPHAN)
    email_categories = relationship("EmailCategory", back_populates="user", cascade=CASCADE_DELETE_ORPHAN)
    calendar_events = relationship("CalendarEvent", back_populates="user", cascade=CASCADE_DELETE_ORPHAN)
    stocks = relationship("UserStockWatch", back_populates="user", cascade=CASCADE_DELETE_ORPHAN)
    einvoice_config = relationship("EInvoiceConfig", back_populates="user", uselist=False, cascade=CASCADE_DELETE_ORPHAN)

class EmailConfig(Base):
    __tablename__ = 'email_configs'


    user_id = Column(BigInteger, ForeignKey(USER_FK_TARGET), primary_key=True)
    
    email_address = Column(String, nullable=False)
    email_password = Column(String, nullable=False)
    last_email_id = Column(String, nullable=True)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    user = relationship("User", back_populates="email_config")
    is_active = Column(Boolean, default=True, nullable=False)

class EmailCategory(Base):
    """使用者自訂的郵件分類"""
    __tablename__ = 'email_categories'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(BigInteger, ForeignKey(USER_FK_TARGET))
    name = Column(String, nullable=False)        # 分類名稱 (例如: 繳費通知)
    description = Column(String, nullable=False) # 給 AI 判斷用的描述
    
    user = relationship("User", back_populates="email_categories")
    emails = relationship("CategorizedEmail", back_populates="category", cascade=CASCADE_DELETE_ORPHAN)

class CategorizedEmail(Base):
    """被 AI 成功分類並摘要的郵件"""
    __tablename__ = 'categorized_emails'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    category_id = Column(BigInteger, ForeignKey('email_categories.id'))
    
    subject = Column(String, nullable=False)
    ai_summary = Column(String, nullable=False) 
    gmail_link = Column(String, nullable=False) 
    received_at = Column(String, nullable=False) 

    category = relationship("EmailCategory", back_populates="emails")

class CalendarEvent(Base):
    __tablename__ = 'calendar_events'

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(BigInteger, ForeignKey(USER_FK_TARGET), nullable=False)
    description = Column(Text, nullable=True)
    event_time = Column(DateTime, nullable=False)
    is_private = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="calendar_events")

class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(BigInteger, ForeignKey(USER_FK_TARGET), nullable=False)
    memory_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
class TrackerCategory(Base):
    __tablename__ = 'tracker_categories'

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(BigInteger, ForeignKey(USER_FK_TARGET), nullable=False)
    
    name = Column(String, nullable=False)
    range_options = Column(JSON, default=lambda: [7, 30, 180, 365])
    current_range = Column(Integer, default=7)
    fields = Column(JSON, nullable=False) 
    
    last_ai_analysis = Column(Text, nullable=True)
    analysis_updated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.now)

    subcategories = relationship("TrackerSubCategory", back_populates="category", cascade=CASCADE_DELETE_ORPHAN)
    records = relationship("LifeRecord", back_populates="category", cascade=CASCADE_DELETE_ORPHAN)

class TrackerSubCategory(Base):
    __tablename__ = 'tracker_subcategories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('tracker_categories.id'), nullable=False)
    
    name = Column(String, nullable=False)

    category = relationship("TrackerCategory", back_populates="subcategories")
    records = relationship("LifeRecord", back_populates="subcategory")

class EInvoiceConfig(Base):
    __tablename__ = 'einvoice_configs'


    user_id = Column(BigInteger, ForeignKey(USER_FK_TARGET), primary_key=True)
    
    phone_number = Column(String, nullable=True)
    password = Column(String, nullable=True)
    last_fetch_date = Column(Date, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    user = relationship("User", back_populates="einvoice_config")

class LifeRecord(Base):
    __tablename__ = 'life_records'

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(BigInteger, ForeignKey(USER_FK_TARGET), nullable=False)
    category_id = Column(Integer, ForeignKey('tracker_categories.id'), nullable=False)
    
    subcategory_id = Column(Integer, ForeignKey('tracker_subcategories.id'), nullable=True)
    subcat_name = Column(String, nullable=True) 
    
    values = Column(JSON, nullable=False) 
    note = Column(String, nullable=True) 
    created_at = Column(DateTime, default=datetime.now)

    category = relationship("TrackerCategory", back_populates="records")
    subcategory = relationship("TrackerSubCategory", back_populates="records")

class UserStockWatch(Base):
    __tablename__ = 'user_stock_watch'

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(BigInteger, ForeignKey(USER_FK_TARGET), nullable=False)

    stock_symbol = Column(String(10), nullable=False) 
    stock_name = Column(String(50), nullable=True)   
    
    shares = Column(Integer, default=0)              
    total_cost = Column(Float, default=0)            
    buy_price = Column(Float, nullable=True)          
    
    target_up = Column(Float, nullable=True)          
    target_down = Column(Float, nullable=True)        
    
    last_notified_price = Column(Float, nullable=True) 
    last_close_price = Column(Float, nullable=True)    
    last_up_date = Column(String, nullable=True)   
    last_down_date = Column(String, nullable=True) 
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="stocks")