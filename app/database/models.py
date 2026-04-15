from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class BotUser(Base):
    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(default=False, server_default=text("0"))
    is_banned: Mapped[bool] = mapped_column(default=False, server_default=text("0"))
    broadcast_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tg_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # repair / resale
    model: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))
    stage: Mapped[str] = mapped_column(String(50), default="new", server_default=text("'new'"))
    priority: Mapped[str] = mapped_column(String(20), default="normal", server_default=text("'normal'"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False, server_default=text("0"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    repair_details: Mapped["RepairDetails | None"] = relationship(
        back_populates="item",
        uselist=False,
        cascade="all, delete-orphan",
    )

    resale_details: Mapped["ResaleDetails | None"] = relationship(
        back_populates="item",
        uselist=False,
        cascade="all, delete-orphan",
    )

    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )
    avito_chats: Mapped[list["AvitoChat"]] = relationship(back_populates="linked_item")


class RepairDetails(Base):
    __tablename__ = "repair_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), unique=True)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
    )

    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prepayment_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    final_received_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    item: Mapped["Item"] = relationship(back_populates="repair_details")
    client: Mapped["Client | None"] = relationship(back_populates="repair_details")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    normalized_phone: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    telegram_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_telegram_contact: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    repair_details: Mapped[list["RepairDetails"]] = relationship(back_populates="client")


class ResaleDetails(Base):
    __tablename__ = "resale_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), unique=True)

    buy_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    sell_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    item: Mapped["Item"] = relationship(back_populates="resale_details")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    item: Mapped["Item"] = relationship(back_populates="expenses")


class BotText(Base):
    __tablename__ = "bot_texts"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AvitoAccount(Base):
    __tablename__ = "avito_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(255))
    client_secret: Mapped[str] = mapped_column(String(255))
    avito_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    repair_ad_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    chats: Mapped[list["AvitoChat"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )


class AvitoChat(Base):
    __tablename__ = "avito_chats"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("avito_accounts.id", ondelete="CASCADE"))
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    avito_chat_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ad_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ad_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_avito_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stage: Mapped[str] = mapped_column(String(50), default="new", server_default=text("'new'"))
    linked_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unread_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account: Mapped["AvitoAccount"] = relationship(back_populates="chats")
    linked_item: Mapped["Item | None"] = relationship(back_populates="avito_chats")
    messages: Mapped[list["AvitoMessage"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
    )


class AvitoMessage(Base):
    __tablename__ = "avito_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("avito_chats.id", ondelete="CASCADE"))
    avito_message_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    direction: Mapped[str] = mapped_column(String(20))
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    chat: Mapped["AvitoChat"] = relationship(back_populates="messages")


class QuickReplyTemplate(Base):
    __tablename__ = "quick_reply_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    actor_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
