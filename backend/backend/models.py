"""Pydantic request/response models for the backend API."""

from typing import Literal

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    path: str = Field(
        ...,
        min_length=1,
        description="Absolute or relative path to the repo to scan.",
    )


class ScanResponse(BaseModel):
    jobId: str


class StatusResponse(BaseModel):
    status: Literal["pending", "running", "done", "error"]
    error: str | None = None
    details: str | None = None
