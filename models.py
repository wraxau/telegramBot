from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///database.db")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Questionnaire(Base):
    __tablename__ = "questionnaires"
    user_id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)
    style = Column(String)
    colors = Column(String)

class Subscription(Base):
    __tablename__ = "subscriptions"
    user_id = Column(Integer, primary_key=True)
    subscription_active = Column(Boolean, default=False)
    tariff = Column(String, default="month")
    search_requests_left = Column(Integer, default=5)
    outfit_analysis_left = Column(Integer, default=3)
    advice_messages_left = Column(Integer, default=7)
    subscription_start = Column(DateTime, default=datetime.now)
    duration_days = Column(Integer, default=30)  # Новое поле для длительности подписки в днях

class PendingPayment(Base):
    __tablename__ = "pending_payments"
    user_id = Column(Integer, primary_key=True)
    payment_id = Column(String, nullable=False)
