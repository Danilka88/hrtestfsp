"""Схемы профиля кандидата."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Contacts(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)
    telegram: Optional[str] = Field(default=None, max_length=64)


class PrivacySettings(BaseModel):
    show_contacts: bool = False
    show_stack: bool = True
    show_experience: bool = True
    show_fsp: bool = True


class CandidateProfileIn(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=200)
    contacts: Contacts = Field(default_factory=Contacts)
    specialization: Optional[str] = Field(default=None, max_length=120)
    grade: Optional[str] = Field(default=None, max_length=20)
    experience_years: Optional[int] = Field(default=None, ge=0, le=60)
    stack: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    summary: Optional[str] = Field(default=None, max_length=4000)


class CandidateProfileOut(CandidateProfileIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    resume_source: str
    resume_filename: Optional[str] = None
    privacy: PrivacySettings
    created_at: datetime
    updated_at: datetime


class ParsedResume(BaseModel):
    """Результат автораспознавания резюме (данные провайдера, без додумывания)."""

    full_name: Optional[str] = None
    contacts: Dict[str, Optional[str]] = Field(default_factory=dict)
    stack: List[str] = Field(default_factory=list)
    grade: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    experience_years: Optional[int] = None
    soft_skills: List[str] = Field(default_factory=list)
    source: str = "mock"


class ResumeUploadResponse(BaseModel):
    profile: CandidateProfileOut
    parsed: ParsedResume
    text_chars: int
    message: str


class PrivacyUpdateRequest(BaseModel):
    show_contacts: Optional[bool] = None
    show_stack: Optional[bool] = None
    show_experience: Optional[bool] = None
    show_fsp: Optional[bool] = None
