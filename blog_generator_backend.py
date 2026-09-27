"""Blog Generator demo backend powered by Nexarch SDK.

This app is intentionally small and self-contained so it can be used as a
smoke-test target for the installed Nexarch SDK.

Run:
    uvicorn blog_generator_backend:app --host 127.0.0.1 --port 8010 --reload

Optional Azure OpenAI settings:
    AZURE_OPENAI_ENDPOINT
    AZURE_OPENAI_API_KEY
    AZURE_OPENAI_DEPLOYMENT   (defaults to gpt-5)
    AZURE_OPENAI_API_VERSION  (defaults to 2024-10-21)
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from nexarch import NexarchSDK


SDK_API_KEY = os.getenv("NEXARCH_SDK_API_KEY", "nex_OdQ5znaix2NOEf_tuLaA6YW94_mbUwGJ3vEmJUnSR4w")
SDK_HTTP_ENDPOINT = os.getenv("NEXARCH_HTTP_ENDPOINT", "").rstrip("/")
SDK_PROJECT_NAME = os.getenv("NEXARCH_PROJECT_NAME", "blog-generator")
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")


class BlogDraftRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200)
    audience: str = Field(default="technical readers", min_length=3, max_length=120)
    tone: str = Field(default="clear and practical", min_length=3, max_length=120)
    keywords: List[str] = Field(default_factory=list)
    target_length_words: int = Field(default=900, ge=200, le=3000)


class BlogDraftResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    topic: str
    title: str
    slug: str
    summary: str
    outline: List[str]
    draft: str
    model_used: str
    created_at: str


class PublishResponse(BaseModel):
    id: str
    status: str
    published_at: str


app = FastAPI(title="Nexarch Blog Generator Demo", version="1.0.0")
sdk = NexarchSDK(
    api_key=SDK_API_KEY,
    environment="blog-demo",
    service_name="blog-generator-demo",
    project_name=SDK_PROJECT_NAME,
    http_endpoint=SDK_HTTP_ENDPOINT or None,
    enable_auto_discovery=True,
    enable_db_instrumentation=False,
)
sdk.init(app)

BLOGS: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "blog-post"


def _build_prompt(payload: BlogDraftRequest) -> str:
    keywords = ", ".join(payload.keywords) if payload.keywords else "none"
    return (
        f"You are writing for a blog generator platform. "
        f"Write a blog post about: {payload.topic}. "
        f"Audience: {payload.audience}. Tone: {payload.tone}. "
        f"Target length: about {payload.target_length_words} words. "
        f"Include these keywords if relevant: {keywords}. "
        f"Return JSON with keys title, summary, outline, draft. "
        f"Make the draft useful, specific, and structured for a product/engineering blog."
    )


def _fallback_blog(payload: BlogDraftRequest) -> Dict[str, Any]:
    title = f"{payload.topic.strip().title()} for Modern Blog Teams"
    outline = [
        f"Why {payload.topic} matters",
        "Core architecture",
        "Implementation plan",
        "Operational considerations",
        "Next steps",
    ]
    summary = (
        f"A practical blog post about {payload.topic} for {payload.audience}, "
        f"written in a {payload.tone} tone."
    )
    draft = "\n\n".join(
        [
            f"# {title}",
            summary,
            "## Overview\nThis demo app shows how the Nexarch SDK can observe a blog generator backend and capture request telemetry.",
            "## Suggested Structure\n" + "\n".join(f"- {item}" for item in outline),
            "## Notes\nUse Azure OpenAI GPT-5 when configured; otherwise the app returns this deterministic fallback so the API remains testable.",
        ]
    )
    return {
        "title": title,
        "summary": summary,
        "outline": outline,
        "draft": draft,
        "model_used": "fallback-template",
    }


def _generate_with_azure_openai(payload: BlogDraftRequest) -> Dict[str, Any]:
    if not (AZURE_ENDPOINT and AZURE_API_KEY):
        return _fallback_blog(payload)

    url = f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions?api-version={AZURE_API_VERSION}"
    body = {
        "messages": [
            {"role": "system", "content": "You generate JSON only."},
            {"role": "user", "content": _build_prompt(payload)},
        ],
        "temperature": 0.7,
        "max_tokens": 1800,
    }

    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_API_KEY,
        },
        json=body,
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()

    content = data["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
        title = parsed.get("title") or f"{payload.topic.strip().title()}"
        summary = parsed.get("summary") or f"Blog post about {payload.topic}."
        outline = parsed.get("outline") or []
        draft = parsed.get("draft") or content
    except json.JSONDecodeError:
        title = f"{payload.topic.strip().title()}"
        summary = f"AI-generated blog post about {payload.topic}."
        outline = ["Introduction", "Main points", "Conclusion"]
        draft = content

    return {
        "title": title,
        "summary": summary,
        "outline": outline,
        "draft": draft,
        "model_used": f"azure-openai:{AZURE_DEPLOYMENT}",
    }


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "blog-generator-demo",
        "status": "running",
        "mode": "azure-openai" if (AZURE_ENDPOINT and AZURE_API_KEY) else "fallback",
        "timestamp": _now(),
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "healthy", "blogs": len(BLOGS), "timestamp": _now()}


@app.get("/blog-posts")
def list_blog_posts() -> List[Dict[str, Any]]:
    return list(BLOGS.values())


@app.get("/blog-posts/{post_id}")
def get_blog_post(post_id: str) -> Dict[str, Any]:
    blog = BLOGS.get(post_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    return blog


@app.post("/blog-posts/generate", response_model=BlogDraftResponse)
def generate_blog_post(payload: BlogDraftRequest) -> BlogDraftResponse:
    generated = _generate_with_azure_openai(payload)
    post_id = str(uuid.uuid4())
    slug = _slugify(generated["title"])

    blog = {
        "id": post_id,
        "topic": payload.topic,
        "title": generated["title"],
        "slug": slug,
        "summary": generated["summary"],
        "outline": generated["outline"],
        "draft": generated["draft"],
        "model_used": generated["model_used"],
        "created_at": _now(),
        "status": "draft",
        "keywords": payload.keywords,
    }
    BLOGS[post_id] = blog

    return BlogDraftResponse(
        id=post_id,
        topic=payload.topic,
        title=blog["title"],
        slug=blog["slug"],
        summary=blog["summary"],
        outline=blog["outline"],
        draft=blog["draft"],
        model_used=blog["model_used"],
        created_at=blog["created_at"],
    )


@app.post("/blog-posts/{post_id}/publish", response_model=PublishResponse)
def publish_blog_post(post_id: str) -> PublishResponse:
    blog = BLOGS.get(post_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    blog["status"] = "published"
    blog["published_at"] = _now()
    return PublishResponse(id=post_id, status="published", published_at=blog["published_at"])


@app.delete("/blog-posts/{post_id}")
def delete_blog_post(post_id: str) -> Dict[str, Any]:
    if post_id not in BLOGS:
        raise HTTPException(status_code=404, detail="Blog post not found")
    removed = BLOGS.pop(post_id)
    return {"status": "deleted", "id": post_id, "title": removed["title"]}
