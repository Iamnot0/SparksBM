"""Chat request/response models"""
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field


class SourceModel(BaseModel):
    """Source model - supports both ISMS objects and uploaded files"""
    id: str = Field(..., description="Source ID")
    type: str = Field(..., description="Type (ISMS object type or file type: pdf, excel, word)")
    name: Optional[str] = Field(None, description="Name (for files)")
    domainId: Optional[str] = Field(None, description="Domain ID (for ISMS objects)")
    data: Optional[Dict[str, Any]] = Field(None, description="Source data (for files)")


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., description="User message")
    sources: Optional[List[SourceModel]] = Field(default=[], description="Sources (ISMS objects or uploaded files)")
    sessionId: str = Field(..., description="Session ID")


class ChatResponse(BaseModel):
    """Chat response model"""
    status: str = Field(..., description="Response status")
    result: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Response text or structured data")
    type: Optional[str] = Field(None, description="Response type")
    dataType: Optional[str] = Field(None, description="Data type if result is structured (table, object_detail)")
    error: Optional[str] = Field(None, description="Error message")
    report: Optional[Dict[str, Any]] = Field(None, description="Report data (for report generation responses)")


class ContextRequest(BaseModel):
    """Context request model"""
    source: SourceModel = Field(..., description="Source to add")
    sessionId: str = Field(..., description="Session ID")


class ContextResponse(BaseModel):
    """Context response model"""
    status: str = Field(..., description="Response status")
    sources: List[SourceModel] = Field(default=[], description="Active sources")
    error: Optional[str] = Field(None, description="Error message")
