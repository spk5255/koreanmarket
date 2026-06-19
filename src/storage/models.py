"""SQLAlchemy ORM models — the starter schema from CLAUDE.md §6.

Conventions
-----------
* ``ticker``  : 6-digit KRX code (str), FK to :class:`Company`.
* ``date``    : a trading date (``Date``).
* ``period``  : a filing period label, e.g. ``"2024Q1"`` (str).
* ``week``    : an ISO week label, e.g. ``"2026-W25"`` (str) — the projection horizon.
* ``ts``      : a timezone-naive UTC timestamp (``DateTime``) for news items.

These tables are intentionally light for Phase 0; later phases add columns and
indexes as the analysis needs them.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Company(Base):
    __tablename__ = "companies"

    ticker: Mapped[str] = mapped_column(String(6), primary_key=True)
    corp_code: Mapped[str | None] = mapped_column(String(8), index=True)  # DART corp number
    name: Mapped[str] = mapped_column(String(128))
    market: Mapped[str] = mapped_column(String(8))   # KOSPI | KOSDAQ | KONEX
    sector: Mapped[str | None] = mapped_column(String(64), index=True)

    prices: Mapped[list["Price"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    fundamentals: Mapped[list["Fundamental"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    flows: Mapped[list["InvestorFlow"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    news: Mapped[list["News"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class Price(Base):
    __tablename__ = "prices"

    ticker: Mapped[str] = mapped_column(String(6), ForeignKey("companies.ticker"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger)

    company: Mapped["Company"] = relationship(back_populates="prices")


class Fundamental(Base):
    __tablename__ = "fundamentals"

    ticker: Mapped[str] = mapped_column(String(6), ForeignKey("companies.ticker"), primary_key=True)
    period: Mapped[str] = mapped_column(String(8), primary_key=True)  # e.g. "2024Q1"

    revenue: Mapped[float | None] = mapped_column(Float)
    op_profit: Mapped[float | None] = mapped_column(Float)
    net_income: Mapped[float | None] = mapped_column(Float)
    total_assets: Mapped[float | None] = mapped_column(Float)
    total_liab: Mapped[float | None] = mapped_column(Float)
    equity: Mapped[float | None] = mapped_column(Float)
    ocf: Mapped[float | None] = mapped_column(Float)     # operating cash flow
    capex: Mapped[float | None] = mapped_column(Float)

    company: Mapped["Company"] = relationship(back_populates="fundamentals")


class InvestorFlow(Base):
    __tablename__ = "investor_flows"

    ticker: Mapped[str] = mapped_column(String(6), ForeignKey("companies.ticker"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    foreign_net: Mapped[float | None] = mapped_column(Float)   # net buy value
    inst_net: Mapped[float | None] = mapped_column(Float)      # institutional net buy value
    short_balance: Mapped[float | None] = mapped_column(Float)

    company: Mapped["Company"] = relationship(back_populates="flows")


class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(6), ForeignKey("companies.ticker"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    source: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    snippet: Mapped[str | None] = mapped_column(String(2048))
    url: Mapped[str] = mapped_column(String(1024))
    sentiment: Mapped[float | None] = mapped_column(Float)        # -1..1
    event_tags: Mapped[list | None] = mapped_column(JSON)         # ["earnings_surprise", ...]

    company: Mapped["Company"] = relationship(back_populates="news")

    __table_args__ = (UniqueConstraint("url", name="uq_news_url"),)


class FactorScore(Base):
    __tablename__ = "factor_scores"

    ticker: Mapped[str] = mapped_column(String(6), ForeignKey("companies.ticker"), primary_key=True)
    asof: Mapped[date] = mapped_column(Date, primary_key=True)
    fundamental: Mapped[float | None] = mapped_column(Float)
    technical: Mapped[float | None] = mapped_column(Float)
    supply_demand: Mapped[float | None] = mapped_column(Float)
    sentiment: Mapped[float | None] = mapped_column(Float)
    composite: Mapped[float | None] = mapped_column(Float)  # 0..100


class Projection(Base):
    __tablename__ = "projections"

    ticker: Mapped[str] = mapped_column(String(6), ForeignKey("companies.ticker"), primary_key=True)
    week: Mapped[str] = mapped_column(String(8), primary_key=True)  # ISO week, e.g. "2026-W25"
    base: Mapped[float | None] = mapped_column(Float)      # base-case projected price/return
    bull: Mapped[float | None] = mapped_column(Float)
    bear: Mapped[float | None] = mapped_column(Float)
    prob_up: Mapped[float | None] = mapped_column(Float)   # 0..1
    confidence: Mapped[str | None] = mapped_column(String(16))  # low|medium|high


class ProjectionOutcome(Base):
    __tablename__ = "projection_outcomes"

    ticker: Mapped[str] = mapped_column(String(6), ForeignKey("companies.ticker"), primary_key=True)
    week: Mapped[str] = mapped_column(String(8), primary_key=True)
    actual_return: Mapped[float | None] = mapped_column(Float)
    hit: Mapped[bool | None] = mapped_column(Boolean)  # did direction match?


# Convenience: every mapped table, for bootstrap/inspection.
ALL_MODELS = (
    Company,
    Price,
    Fundamental,
    InvestorFlow,
    News,
    FactorScore,
    Projection,
    ProjectionOutcome,
)
