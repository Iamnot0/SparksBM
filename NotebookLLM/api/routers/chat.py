"""Chat router - handles chat endpoints"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Dict, Any, List, Optional
import sys
import os
import tempfile
import time

# Add project root to path
_currentDir = os.path.dirname(os.path.abspath(__file__))
_projectRoot = os.path.join(_currentDir, '..', '..')
if _projectRoot not in sys.path:
    sys.path.insert(0, _projectRoot)

from api.models.chat import ChatRequest, ChatResponse, ContextRequest, ContextResponse
from api.services.agentService import AgentService

router = APIRouter(prefix="/api/agent", tags=["agent"])

agentService = AgentService()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process chat message"""
    try:
        result = agentService.chat(
            message=request.message,
            sources=[s.dict() for s in request.sources] if request.sources else [],
            sessionId=request.sessionId
        )
        return ChatResponse(**result)
    except Exception as e:
        return ChatResponse(
            status='error',
            result=None,
            error=str(e)
        )


@router.post("/session", response_model=Dict[str, Any])
async def createSession(userId: str = "default"):
    """Create new session"""
    try:
        result = agentService.createSession(userId)
        return result
    except Exception as e:
        return {
            'status': 'error',
            'sessionId': None,
            'error': str(e)
        }


@router.get("/tools", response_model=Dict[str, Any])
async def getAvailableTools():
    """Get available agent tools"""
    try:
        tools = agentService.getAvailableTools()
        return {
            'status': 'success',
            'tools': tools
        }
    except Exception as e:
        return {
            'status': 'error',
            'tools': [],
            'error': str(e)
        }


@router.get("/context/{sessionId}", response_model=ContextResponse)
async def getContext(sessionId: str):
    """Get active context"""
    result = agentService.getContext(sessionId)
    return ContextResponse(**result)


@router.post("/context", response_model=ContextResponse)
async def addContext(request: ContextRequest):
    """Add source to context"""
    result = agentService.addContext(
        sessionId=request.sessionId,
        source=request.source.dict()
    )
    return ContextResponse(**result)


@router.delete("/context/{sessionId}/{sourceId}", response_model=ContextResponse)
async def removeContext(sessionId: str, sourceId: str):
    """Remove source from context"""
    result = agentService.removeContext(sessionId, sourceId)
    return ContextResponse(**result)


@router.post("/isms", response_model=Dict[str, Any])
async def ismsOperation(request: Dict[str, Any]):
    """Direct ISMS operation - bypasses pattern matching for efficiency"""
    try:
        from api.services.agentService import AgentService
        agentService = AgentService()
        
        # Get agent and ISMS handler
        agent = agentService.agentBridge.agent
        if not agent:
            return {
                'status': 'error',
                'result': None,
                'error': 'Agent not initialized'
            }
        
        # Initialize ISMS handler if needed
        if not hasattr(agent, '_ismsHandler') or not agent._ismsHandler:
            # Import from Agentic Framework
            import sys
            agenticFrameworkPath = os.path.join(_projectRoot, '..', 'Agentic Framework')
            if agenticFrameworkPath not in sys.path:
                sys.path.insert(0, agenticFrameworkPath)
            
            from agents.ismsHandler import ISMSHandler
            veriniceTool = getattr(agent, '_veriniceTool', None)
            if not veriniceTool:
                return {
                    'status': 'error',
                    'result': None,
                    'error': 'ISMS client not available. Please check your configuration.'
                }
            llmTool = getattr(agent, '_llmTool', None)
            agent._ismsHandler = ISMSHandler(veriniceTool, agent._formatVeriniceResult, llmTool)
        
        # Extract operation parameters
        operation = request.get('operation')
        objectType = request.get('objectType')
        name = request.get('name')
        objectId = request.get('id')
        field = request.get('field')
        value = request.get('value')
        
        # Build message for handler
        message = f"{operation} {objectType}"
        if name:
            message += f" {name}"
        elif objectId:
            message += f" {objectId}"
        if field and value:
            message += f" {field} {value}"
        
        # Execute directly via ISMS handler (bypasses pattern matching)
        result = agent._ismsHandler.execute(operation, objectType, message)
        
        # Format response
        if result.get('status') == 'success':
            responseData = result.get('result', '')
            return {
                'status': 'success',
                'result': responseData,
                'type': 'isms_operation'
            }
        else:
            return {
                'status': 'error',
                'result': None,
                'error': result.get('error', 'Unknown error')
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'result': None,
            'error': str(e)
        }


@router.post("/upload", response_model=Dict[str, Any])
async def uploadFile(
    file: UploadFile = File(...),
    sessionId: Optional[str] = Form(None)
):
    """Upload and process file"""
    try:
        if not file.filename:
            return {
                'status': 'error',
                'error': 'No filename provided'
            }
        
        if not sessionId:
            sessionResult = agentService.createSession("default")
            sessionId = sessionResult.get('sessionId')
        
        # Validate file type
        fileExt = os.path.splitext(file.filename)[1].lower()
        allowedExts = ['.xlsx', '.xls', '.docx', '.doc', '.pdf', '.txt']
        
        if fileExt not in allowedExts:
            return {
                'status': 'error',
                'error': f'File type {fileExt} not supported. Allowed: {", ".join(allowedExts)}'
            }
        
        # Validate file size (max 50MB)
        content = await file.read()
        maxSize = 50 * 1024 * 1024  # 50MB
        if len(content) > maxSize:
            return {
                'status': 'error',
                'error': f'File size exceeds maximum of 50MB. File size: {len(content) / 1024 / 1024:.2f}MB'
            }
        
        # Store file in persistent location (uploads directory)
        uploadsDir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
        os.makedirs(uploadsDir, exist_ok=True)
        
        # Create unique filename with session ID to avoid conflicts
        safeFileName = f"{sessionId}_{int(time.time())}_{file.filename}"
        filePath = os.path.join(uploadsDir, safeFileName)
        
        # Write file
        with open(filePath, 'wb') as f:
            f.write(content)
        
        try:
            # Process file through agent
            result = agentService.processFile(filePath, file.filename, sessionId)
            return result
        except Exception as e:
            # Clean up on error
            if os.path.exists(filePath):
                os.unlink(filePath)
            raise
                
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
