from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class Category(str, Enum):
    POLITICS = "Política"
    ECONOMICS = "Economia"
    SOCIAL = "Social Trends"
    TECH = "Tecnologia"


class Geography(str, Enum):
    GLOBAL = "Global"
    PORTUGAL = "Portugal"





class Source(BaseModel):
    name: str
    url: str
    category: Category
    geography: Geography = Geography.GLOBAL
    language: str = "en"
    research_hint: str = ""


class Article(BaseModel):
    title: str
    url: str
    source_name: str
    category: Category
    abstract: str = ""
    elevator_pitch: str = ""
    image_url: str = ""
    published_date: str = ""





class BriefingSection(BaseModel):
    category: Category
    bullets: list[str] = Field(default_factory=list)


class ExecutiveSummary(BaseModel):
    date: str
    sections: list[BriefingSection] = Field(default_factory=list)
    meta_narrative: str = ""


class TokenStats(BaseModel):
    total_budget: int
    tokens_used: int
    tokens_remaining: int
    sources_processed: int
    sources_skipped: int


class DailyBriefing(BaseModel):
    date: str
    summary: ExecutiveSummary
    articles: list[Article] = Field(default_factory=list)
    token_stats: TokenStats
    errors: list[str] = Field(default_factory=list)
