"""Unified schema for AI tool usage activities and resume output."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActivityType(str, Enum):
    CODING = "coding"
    CHAT = "chat"
    DEBUG = "debug"
    DESIGN = "design"
    DOC = "doc"
    REVIEW = "review"
    IMAGE_GEN = "image-gen"
    AUDIO_GEN = "audio-gen"
    VIDEO_GEN = "video-gen"
    AGENT_RUN = "agent-run"
    COMMIT = "commit"
    OTHER = "other"


class Source(str, Enum):
    CLAUDE_CODE = "claude-code"
    CLAUDE_AI = "claude-ai"
    CLAUDE_DESKTOP = "claude-desktop"
    CHATGPT = "chatgpt"
    CURSOR = "cursor"
    CLINE = "cline"
    CONTINUE = "continue"
    AIDER = "aider"
    WINDSURF = "windsurf"
    COPILOT_VSCODE = "copilot-vscode"
    COPILOT_ACTIVITY = "copilot-activity"
    ZED = "zed"
    GEMINI = "gemini"
    GROK = "grok"
    PERPLEXITY = "perplexity"
    MISTRAL = "mistral"
    POE = "poe"
    NOTEBOOKLM = "notebooklm"
    SORA = "sora"
    COMFYUI = "comfyui"
    A1111 = "a1111"
    MIDJOURNEY = "midjourney"
    RUNWAY = "runway"
    SUNO = "suno"
    ELEVENLABS = "elevenlabs"
    HEYGEN = "heygen"
    DESCRIPT = "descript"
    GIT = "git"
    DEVIN = "devin"
    OTHER = "other"


class Activity(BaseModel):
    """One unit of AI-assisted or AI-generated work."""

    source: Source
    session_id: str
    timestamp_start: datetime
    timestamp_end: datetime | None = None
    project: str | None = Field(default=None, description="Inferred project name or path")
    activity_type: ActivityType = ActivityType.OTHER
    tech_stack: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    summary: str = ""
    user_prompts_count: int = 0
    tool_calls_count: int = 0
    files_touched: list[str] = Field(default_factory=list)
    raw_ref: str = Field(default="", description="file:line or URL for traceability")
    extra: dict[str, Any] = Field(default_factory=dict)


class ProjectGroup(BaseModel):
    """Aggregated activities for one project."""

    name: str
    path: str | None = None
    first_activity: datetime
    last_activity: datetime
    total_sessions: int
    tech_stack: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    summary: str = ""
    achievements: list[str] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)
    category_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Counts of task categories (frontend/backend/bug-fix/...) across activities",
    )
    capability_breadth: int = Field(
        default=0,
        description="Number of distinct task categories — a 'multi-skill' signal",
    )
    headline: str | None = Field(
        default=None,
        description="One-line role summary like 'Full-stack: 20% frontend / 35% backend / 30% DevOps / 15% bug-fix'",
    )
    domain_tags: list[str] = Field(
        default_factory=list,
        description="Non-technical descriptors (SEO, Agent Workflow, ...) kept separate from tech_stack",
    )
    metrics: list[str] = Field(
        default_factory=list,
        description="User-supplied hard numbers pulled from profile.project_metrics",
    )


class UserProfile(BaseModel):
    """User-supplied basic info and customizable sections.

    Extra keys are preserved so a user can drop localized variants like
    `summary_zh_TW` or `title_ja_JP` next to the canonical field; templates
    pick the right one via the `localized()` filter.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    website: str | None = None
    linkedin: str | None = None
    github: str | None = None
    target_role: str | None = None
    summary: str | None = None
    # locale-conditional personal fields. Only rendered when the active
    # locale's `personal_fields` list (see render/i18n.py) includes them and
    # the value is non-empty. Leaving any of these blank is always safe.
    photo_path: str | None = Field(default=None, description="Absolute or relative path to a JPEG/PNG headshot")
    dob: str | None = Field(default=None, description="ISO date YYYY-MM-DD; rendered only in locales that expect it (de_DE / ja_JP / ko_KR)")
    gender: str | None = Field(default=None, description="Free-form; rendered in ja_JP/ko_KR rirekisho-style forms")
    nationality: str | None = Field(default=None, description="Rendered in de_DE Lebenslauf when set")
    marital_status: str | None = Field(default=None, description="Rare modern usage; only rendered when locale + value both present")
    mil_service: str | None = Field(default=None, description="Military service status; relevant for TW/KR male candidates")
    languages: list[str] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)
    custom_sections: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form sections user wants to add, e.g. 'hobbies', 'awards'",
    )
    project_metrics: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Hard numbers user wants to attach to specific projects. "
            "Key = project name (matches display name in aggregated groups), "
            "value = list of strings like ['MAU 5k+', '40% faster iteration']."
        ),
    )


class ResumeDraft(BaseModel):
    """A single versioned resume draft."""

    version: int
    created_at: datetime
    profile: UserProfile
    project_groups: list[ProjectGroup] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tailored_for: str | None = Field(default=None, description="Job description text or role")
    notes: str | None = None


def load_profile(path: Path) -> UserProfile:
    import yaml

    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return UserProfile(**data)
