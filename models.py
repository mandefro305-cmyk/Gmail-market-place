from enum import Enum as PyEnum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import DATABASE_URL

Base = declarative_base()

class AccountStatus(str, PyEnum):
    TASK_AVAILABLE = "TASK_AVAILABLE"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SOLD = "SOLD"

class TransactionType(str, PyEnum):
    PAYOUT = "PAYOUT"
    DEPOSIT = "DEPOSIT"
    PURCHASE = "PURCHASE"
    WITHDRAWAL = "WITHDRAWAL"

class WithdrawalStatus(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    balance = Column(Float, default=0.0)
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    registered_accounts = relationship("Account", back_populates="creator", foreign_keys="Account.creator_id")
    bought_accounts = relationship("Account", back_populates="buyer", foreign_keys="Account.buyer_id")
    transactions = relationship("Transaction", back_populates="user")
    withdrawals = relationship("WithdrawalRequest", back_populates="user")

class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String(50), nullable=False)  # Telebirr or CBE
    account_details = Column(String(255), nullable=False)
    status = Column(Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False)
    rejection_reason = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="withdrawals")

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    dob_year = Column(String(50), nullable=True)
    email = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    recovery_info = Column(String(500), nullable=True)
    notes = Column(String(500), nullable=True)

    status = Column(Enum(AccountStatus), default=AccountStatus.PENDING_REVIEW, nullable=False)
    selling_price = Column(Float, nullable=True)
    creator_payout = Column(Float, nullable=True)
    rejection_reason = Column(String(500), nullable=True)

    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime, nullable=True)
    purchased_at = Column(DateTime, nullable=True)

    creator = relationship("User", foreign_keys=[creator_id], back_populates="registered_accounts")
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="bought_accounts")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="transactions")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(engine_override=None):
    e = engine_override or engine
    Base.metadata.create_all(bind=e)
