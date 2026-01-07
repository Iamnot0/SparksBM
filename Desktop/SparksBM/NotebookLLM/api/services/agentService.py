"""Agent service - main service layer for agent operations"""
from typing import Dict, Any, Optional, List
import sys
import os

# Add project root to path
_currentDir = os.path.dirname(os.path.abspath(__file__))
_projectRoot = os.path.join(_currentDir, '..', '..')
if _projectRoot not in sys.path:
    sys.path.insert(0, _projectRoot)

from integration.agentBridge import AgentBridge
from integration.contextMapper import ContextMapper
from api.services.sessionService import SessionService


class AgentService:
    """Main service for agent operations"""
    
    def __init__(self):
        self.agentBridge = AgentBridge()
        self.contextMapper = ContextMapper()
        self.sessionService = SessionService()
        # Initialize bridge - this will register all tools including PDF
        self.agentBridge.initialize()
    
    def chat(self, message: str, sources: List[Dict[str, Any]], sessionId: str) -> Dict[str, Any]:
        """Process chat message"""
        session = self.sessionService.getSession(sessionId)
        if not session:
            return {
                'status': 'error',
                'result': None,
                'error': 'Invalid session'
            }
        
        # CRITICAL: Only update session context if sources have actual data
        # Frontend may send empty sources with data: {}, which would overwrite real data
        if sources:
            # Check if sources have actual data before overwriting
            hasRealData = any(
                source.get('data') and 
                (isinstance(source.get('data'), dict) and (
                    'sheets' in source.get('data', {}) or 
                    'text' in source.get('data', {}) or 
                    'pages' in source.get('data', {}) or
                    'paragraphs' in source.get('data', {}) or
                    len([k for k in source.get('data', {}).keys() if k not in ['fileName', 'fileType']]) > 0
                )) or
                (not isinstance(source.get('data'), dict) and source.get('data') is not None)
                for source in sources
            )
            if hasRealData:
                self.sessionService.setContext(sessionId, sources)
            # If sources are empty/placeholder, keep existing session context (don't overwrite)
        
        activeSources = session.get('activeContext', [])
        contextDict = self.contextMapper.buildContext(activeSources)
        # Extract context string and metadata - contextDict is now a dict with metadata
        context = contextDict.get('context', '')
        # Use contextDict directly as context (it has all metadata)
        context = contextDict
        
        # Update agent state with context data for tool access
        agent = self.agentBridge.agent
        
        # CRITICAL: Always try to restore data from session context, even if activeSources is empty
        # This ensures data is available when user responds to prompts
        if agent:
            # Get activeSources from session (might be empty from frontend, but data is in session)
            if not activeSources:
                # Try to get from session directly
                activeSources = session.get('activeContext', [])
            
            # Get the most recent source data
            latestSource = activeSources[-1] if activeSources else None
            
            # If no latestSource but we have pendingFileAction, try to restore from state
            if not latestSource and agent.state.get('pendingFileAction'):
                pendingAction = agent.state.get('pendingFileAction')
                filePath = pendingAction.get('filePath')
                if filePath and os.path.exists(filePath):
                    # Re-read the file to restore data
                    try:
                        fileType = pendingAction.get('fileType', 'excel')
                        if fileType == 'excel' and 'readExcel' in agent.tools:
                            result = agent.executeTool('readExcel', filePath=filePath)
                            if result:
                                agent.state['lastProcessed'] = result.copy() if isinstance(result, dict) else {'data': result}
                                agent.state['lastProcessed']['fileName'] = pendingAction.get('fileName', 'document')
                                agent.state['lastProcessed']['fileType'] = fileType
                                agent.state['lastProcessed']['filePath'] = filePath
                    except Exception:
                        pass
            
            if latestSource:
                sourceData = latestSource.get('data')
                fileName = latestSource.get('name', '')
                fileType = latestSource.get('type', 'unknown')
                
                # SINGLE SOURCE OF TRUTH: session.activeContext
                # Restore data from session context to agent.state['lastProcessed'] for quick access
                # This is a cache - the real data is in session.activeContext
                if sourceData is not None:
                    # Ensure sourceData is a dict before assigning
                    if isinstance(sourceData, dict):
                        # Check if it's a nested structure (data.data) - unwrap if needed
                        if 'data' in sourceData and len(sourceData) == 1 and 'text' not in sourceData and 'pages' not in sourceData and 'sheets' not in sourceData:
                            # Unwrap nested data only if it doesn't have direct content keys
                            actualData = sourceData.get('data')
                            if isinstance(actualData, dict):
                                agent.state['lastProcessed'] = actualData.copy()
                            else:
                                agent.state['lastProcessed'] = {'data': actualData}
                        else:
                            # Use sourceData directly - it should already have all PDF/Excel/Word data
                            agent.state['lastProcessed'] = sourceData.copy()
                        
                        # Ensure metadata is set (fileName, fileType, filePath)
                        agent.state['lastProcessed']['fileName'] = fileName
                        agent.state['lastProcessed']['fileType'] = fileType
                        filePath = latestSource.get('filePath')
                        if filePath:
                            agent.state['lastProcessed']['filePath'] = filePath
                    else:
                        # If data is not a dict, create a proper structure
                        agent.state['lastProcessed'] = {
                            'data': sourceData,
                            'fileName': fileName,
                            'fileType': fileType
                        }
                        filePath = latestSource.get('filePath')
                        if filePath:
                            agent.state['lastProcessed']['filePath'] = filePath
                else:
                    # Data is None - try to re-read from filePath
                    filePath = latestSource.get('filePath')
                    if filePath and os.path.exists(filePath):
                        try:
                            # Re-read the file based on type
                            if fileType == 'excel':
                                result = agent.executeTool('readExcel', filePath=filePath)
                            elif fileType == 'pdf':
                                result = agent.executeTool('readPDF', filePath=filePath)
                            elif fileType == 'word':
                                result = agent.executeTool('readWord', filePath=filePath)
                            else:
                                result = None
                            
                            if result:
                                agent.state['lastProcessed'] = result.copy() if isinstance(result, dict) else {'data': result}
                                agent.state['lastProcessed']['fileName'] = fileName
                                agent.state['lastProcessed']['fileType'] = fileType
                                agent.state['lastProcessed']['filePath'] = filePath
                        except Exception:
                            pass
        
        result = self.agentBridge.process(message, context)
        
        self.sessionService.addMessage(sessionId, 'user', message)
        if result.get('status') == 'success':
            response = result.get('result', '')
            # For structured data (tables), store a simple text summary
            if isinstance(response, dict) and response.get('type') == 'table':
                responseText = response.get('title', 'Listed items')
            elif isinstance(response, dict):
                responseText = response.get('result', str(response))
            else:
                responseText = str(response)
            self.sessionService.addMessage(sessionId, 'assistant', responseText)
        
        return self._formatResponse(result)
    
    def createSession(self, userId: str) -> Dict[str, Any]:
        """Create new session"""
        sessionId = self.sessionService.createSession(userId)
        return {
            'status': 'success',
            'sessionId': sessionId
        }
    
    def getContext(self, sessionId: str) -> Dict[str, Any]:
        """Get active context for session"""
        session = self.sessionService.getSession(sessionId)
        if not session:
            return {
                'status': 'error',
                'sources': [],
                'error': 'Invalid session'
            }
        
        return {
            'status': 'success',
            'sources': session.get('activeContext', [])
        }
    
    def addContext(self, sessionId: str, source: Dict[str, Any]) -> Dict[str, Any]:
        """Add source to context"""
        session = self.sessionService.getSession(sessionId)
        if not session:
            return {
                'status': 'error',
                'error': 'Invalid session'
            }
        
        sources = session.get('activeContext', [])
        
        sourceId = source.get('id')
        if any(s.get('id') == sourceId for s in sources):
            return {
                'status': 'error',
                'error': 'Source already in context'
            }
        
        sources.append(source)
        self.sessionService.setContext(sessionId, sources)
        
        return {
            'status': 'success',
            'sources': sources
        }
    
    def removeContext(self, sessionId: str, sourceId: str) -> Dict[str, Any]:
        """Remove source from context"""
        session = self.sessionService.getSession(sessionId)
        if not session:
            return {
                'status': 'error',
                'error': 'Invalid session'
            }
        
        sources = session.get('activeContext', [])
        sources = [s for s in sources if s.get('id') != sourceId]
        self.sessionService.setContext(sessionId, sources)
        
        return {
            'status': 'success',
            'sources': sources
        }
    
    def getAvailableTools(self) -> List[Dict[str, Any]]:
        """Get available agent tools"""
        # Ensure agent is initialized
        if not self.agentBridge.isInitialized():
            self.agentBridge.initialize()
        
        tools = []
        agent = self.agentBridge.agent
        
        if agent and hasattr(agent, 'tools'):
            # Filter out LLM tools (internal only, not shown in UI)
            internalTools = ['generate', 'analyze', 'extractEntities']
            
            query_tools_found = []
            for toolName, toolInfo in agent.tools.items():
                # Skip internal LLM tools
                if toolName in internalTools:
                    continue
                
                # Track query tools
                if any(x in toolName.lower() for x in ['row', 'column', 'filter', 'query', 'search', 'summary']):
                    query_tools_found.append(toolName)
                
                description = toolInfo.get('description', '') if isinstance(toolInfo, dict) else ''
                tools.append({
                    'name': toolName,
                    'description': description
                })
        
        return tools
    
    def processFile(self, filePath: str, fileName: str, sessionId: str) -> Dict[str, Any]:
        """Process uploaded file through agent"""
        try:
            session = self.sessionService.getSession(sessionId)
            if not session:
                return {
                    'status': 'error',
                    'error': 'Invalid session'
                }
            
            # Determine file type and process
            fileExt = os.path.splitext(fileName)[1].lower()
            
            if fileExt in ['.xlsx', '.xls']:
                toolName = 'readExcel'
            elif fileExt in ['.docx', '.doc']:
                toolName = 'readWord'
            elif fileExt == '.pdf':
                toolName = 'readPDF'
            else:
                return {
                    'status': 'error',
                    'error': f'File type {fileExt} processing not yet implemented'
                }
            
            # Process file using agent
            agent = self.agentBridge.agent
            if not agent:
                return {
                    'status': 'error',
                    'error': 'Agent not initialized'
                }
            
            # Execute tool with proper exception handling
            try:
                result = agent.executeTool(toolName, filePath=filePath)
            except Exception as e:
                errorMsg = str(e)
                # Provide helpful error messages for common PDF issues
                if 'PDF library' in errorMsg or 'PyPDF2' in errorMsg or 'pdfplumber' in errorMsg:
                    return {
                        'status': 'error',
                        'error': f'PDF library not available. Please install PyPDF2 or pdfplumber: pip install PyPDF2'
                    }
                elif 'encrypted' in errorMsg.lower() or 'password' in errorMsg.lower():
                    return {
                        'status': 'error',
                        'error': f'PDF file is encrypted and requires a password. Please use an unencrypted PDF or provide the password.'
                    }
                elif 'FileNotFoundError' in str(type(e).__name__):
                    return {
                        'status': 'error',
                        'error': f'File not found: {filePath}'
                    }
                else:
                    return {
                        'status': 'error',
                        'error': f'Failed to process {fileExt} file: {errorMsg}'
                    }
            
            # Store in agent state for tool access
            if isinstance(result, dict):
                # Verify file content based on type
                if toolName == 'readPDF':
                    # Check if PDF has extractable content
                    hasText = 'text' in result and result.get('text', '').strip()
                    hasPages = 'pages' in result and result.get('pages', [])
                    
                    if not hasText and not hasPages:
                        return {
                            'status': 'error',
                            'error': f'PDF file was read but contains no extractable text. The file may be empty, image-based (scanned), or corrupted. If this is a scanned PDF, try using OCR software first.'
                        }
                    
                    # Ensure text is available even if only pages exist
                    if not hasText and hasPages:
                        # Extract text from pages
                        pageTexts = []
                        for page in result.get('pages', []):
                            if isinstance(page, dict) and page.get('text'):
                                pageTexts.append(page.get('text', ''))
                        if pageTexts:
                            result['text'] = '\n\n'.join(pageTexts)
                
                elif toolName == 'readExcel':
                    # Verify Excel has data
                    hasSheets = 'sheets' in result and result.get('sheets', {})
                    hasData = 'data' in result and result.get('data', [])
                    
                    if not hasSheets and not hasData:
                        return {
                            'status': 'error',
                            'error': f'Excel file was read but contains no data. The file may be empty or corrupted.'
                        }
                
                elif toolName == 'readWord':
                    # Verify Word has content
                    hasText = 'text' in result and result.get('text', '').strip()
                    hasParagraphs = 'paragraphs' in result and result.get('paragraphs', [])
                    hasTables = 'tables' in result and result.get('tables', [])
                    
                    if not hasText and not hasParagraphs and not hasTables:
                        return {
                            'status': 'error',
                            'error': f'Word file was read but contains no extractable content. The file may be empty or corrupted.'
                        }
                
                # Create a new dict to avoid modifying the original result
                agent.state['lastProcessed'] = result.copy()
                agent.state['lastProcessed']['filePath'] = filePath
                agent.state['lastProcessed']['fileName'] = fileName
                agent.state['lastProcessed']['fileType'] = fileExt[1:]  # Remove the dot
                processedCount = agent.state.get('processedCount', 0)
                agent.state['processedCount'] = processedCount + 1
                if not hasattr(agent, 'processedFiles'):
                    agent.processedFiles = []
                agent.processedFiles.append(fileName)
            elif result is None:
                # Tool returned None - return error
                return {
                    'status': 'error',
                    'error': f'Failed to process {fileExt} file. The tool returned no data. Please check if the file is valid.'
                }
            else:
                # If result is not a dict, create a basic structure
                agent.state['lastProcessed'] = {
                    'filePath': filePath,
                    'fileName': fileName,
                    'fileType': fileExt[1:],
                    'data': result
                }
            
            # Add to context - ensure complete data is stored
            sourceId = f"{sessionId}-{fileName}-{os.path.getmtime(filePath) if os.path.exists(filePath) else 0}"
            # Determine file type
            if fileExt in ['.xlsx', '.xls']:
                fileType = 'excel'
            elif fileExt in ['.docx', '.doc']:
                fileType = 'word'
            elif fileExt == '.pdf':
                fileType = 'pdf'
            else:
                fileType = 'document'
            
            # Ensure result is properly structured with all data
            # CRITICAL: Store ALL PDF/Excel/Word data directly, not nested
            if isinstance(result, dict):
                # Make a complete copy with all fields - this IS the data
                sourceData = result.copy()
                # Add metadata fields
                sourceData['fileName'] = fileName
                sourceData['fileType'] = fileType
                # Verify PDF has content before storing
                if toolName == 'readPDF':
                    if not ('text' in sourceData or 'pages' in sourceData):
                        return {
                            'status': 'error',
                            'error': f'PDF file was processed but contains no extractable content. The file may be empty, image-based, or corrupted.'
                        }
            else:
                # If result is not a dict, wrap it
                sourceData = {
                    'data': result,
                    'fileName': fileName,
                    'fileType': fileType
                }
            
            # Store in session context - sourceData contains ALL the PDF/Excel/Word data
            
            source = {
                'id': sourceId,
                'name': fileName,
                'type': fileType,
                'data': sourceData,  # This contains text, pages, sheets, paragraphs, etc.
                'filePath': filePath  # Store filePath for potential re-reading
            }
            
            sources = session.get('activeContext', [])
            sources.append(source)
            self.sessionService.setContext(sessionId, sources)
            
            # Also ensure agent state has complete data for immediate access
            if agent:
                # CRITICAL: Store the COMPLETE result data, not just sourceData (which might have metadata)
                # For Excel, we need the actual sheets/data structure
                if isinstance(result, dict):
                    # Store the complete result (has sheets/data/columns)
                    agent.state['lastProcessed'] = result.copy()
                    # Add metadata
                    agent.state['lastProcessed']['fileName'] = fileName
                    agent.state['lastProcessed']['fileType'] = fileType
                    agent.state['lastProcessed']['filePath'] = filePath
                else:
                    # Fallback: use sourceData
                    agent.state['lastProcessed'] = sourceData.copy()
            
            response = {
                'status': 'success',
                'sourceId': sourceId,
                'fileName': fileName,
                'result': result
            }
            
            # For Excel files, show interactive prompt with options
            if isinstance(result, dict) and fileExt in ['.xlsx', '.xls']:
                # Check existing Excel files in session
                existingSources = session.get('activeContext', [])
                existingExcelFiles = [
                    s for s in existingSources 
                    if s.get('type') == 'excel' and s.get('name') != fileName
                ]
                hasMultipleExcel = len(existingExcelFiles) >= 1
                
                # Check if detection was already done by agent
                bulkSuggestion = result.get('_bulkImportSuggestion')
                
                # If not, do detection here using the Excel handler
                if not bulkSuggestion and agent:
                    # Ensure Excel handler is initialized
                    if hasattr(agent, '_ensureExcelHandler'):
                        agent._ensureExcelHandler()
                    if hasattr(agent, '_excelHandler') and agent._excelHandler:
                        bulkSuggestion = agent._excelHandler.detectAssetInventory(result)
                
                # Store in agent state that we're waiting for user choice
                if agent:
                    agent.state['pendingFileAction'] = {
                        'fileName': fileName,
                        'fileType': 'excel',
                        'filePath': filePath,  # CRITICAL: Store filePath for re-reading
                        'hasAssetInventory': bulkSuggestion is not None,
                        'rowCount': bulkSuggestion.get('rowCount', 0) if bulkSuggestion else 0
                    }
                
                # Build interactive message - different for multiple files
                if hasMultipleExcel:
                    # Multiple Excel files detected - show single prompt for comparison
                    otherFileNames = [s.get('name', 'file') for s in existingExcelFiles]
                    allFileNames = otherFileNames + [fileName]
                    response['message'] = (
                        f"<i class=\"fas fa-check-circle\"></i> Successfully uploaded: {fileName}\n\n"
                        f"<i class=\"fas fa-chart-bar\"></i> You have **{len(existingExcelFiles) + 1} Excel file(s)** ready:\n"
                        f"   • {allFileNames[0]}\n"
                        f"   • {allFileNames[1]}\n\n"
                        f"**What would you like to do?**\n\n"
                        f"**i.** Compare files - Identify differences between the Excel files\n"
                        f"**ii.** Create assets - Import all rows from a file as assets\n"
                        f"**iii.** Analyze a file - Get a detailed analysis\n"
                        f"**iv.** Tell me what you want - Ask me to do something specific\n\n"
                        f"<i class=\"fas fa-lightbulb\"></i> You can type:\n"
                        f"  - **'i'** or **'compare'** or **'compare files'** to compare the Excel files\n"
                        f"  - **'ii'** or **'create assets'** to import assets\n"
                        f"  - **'iii'** or **'analyze'** to analyze a file\n"
                        f"  - **'iv'** or describe what you want me to do"
                    )
                    response['hasMultipleExcel'] = True
                    response['excelFileCount'] = len(existingExcelFiles) + 1
                elif bulkSuggestion:
                    # Single file with asset inventory detected - show simple confirmation
                    rowCount = bulkSuggestion.get('rowCount', 0)
                    response['message'] = (
                        f"<i class=\"fas fa-check-circle\"></i> Successfully uploaded: {fileName}\n"
                        f"<i class=\"fas fa-chart-bar\"></i> Detected {rowCount} rows that look like an asset inventory.\n\n"
                        f"<i class=\"fas fa-lightbulb\"></i> You can:\n"
                        f"  - Type **'create assets'** or **'import'** to import all rows as assets\n"
                        f"  - Type **'analyze'** to get a detailed analysis\n"
                        f"  - Upload another Excel file to compare files\n"
                        f"  - Or tell me what you'd like to do"
                    )
                    response['bulkImportSuggestion'] = bulkSuggestion
                    result['_bulkImportSuggestion'] = bulkSuggestion
                else:
                    # Single file without asset inventory - show simple confirmation
                    response['message'] = (
                        f"<i class=\"fas fa-check-circle\"></i> Successfully uploaded: {fileName}\n\n"
                        f"<i class=\"fas fa-lightbulb\"></i> You can:\n"
                        f"  - Type **'create assets'** if this contains asset data\n"
                        f"  - Type **'analyze'** to get a detailed analysis\n"
                        f"  - Upload another Excel file to compare files\n"
                        f"  - Or tell me what you'd like to do"
                    )
            
            return response
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _formatResponse(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format agent response for web"""
        if result.get('status') == 'error':
            return {
                'status': 'error',
                'result': None,
                'error': result.get('error', 'Unknown error')
            }
        
        responseData = result.get('result', {})
        
        # Check if responseData is structured (table/object_detail) - preserve as dict
        if isinstance(responseData, dict) and responseData.get('type') in ['table', 'object_detail']:
            response = {
                'status': 'success',
                'result': responseData,  # Preserve structured data as dict
                'type': 'tool_result',
                'dataType': responseData.get('type')  # Add dataType for Pydantic model
            }
        elif isinstance(responseData, dict):
            responseText = responseData.get('result', str(responseData))
            responseType = responseData.get('type', 'chat_response')
            response = {
                'status': 'success',
                'result': responseText,
                'type': responseType
            }
        else:
            responseText = str(responseData)
            response = {
            'status': 'success',
            'result': responseText,
                'type': 'chat_response'
        }
        
        # Include PDF data for report generation
        # Check for report object first (new format)
        if 'report' in result:
            response['report'] = result.get('report')
        # Legacy individual fields (for backward compatibility)
        if 'reportData' in result:
            response['reportData'] = result.get('reportData')
        if 'reportId' in result:
            response['reportId'] = result.get('reportId')
        if 'reportName' in result:
            response['reportName'] = result.get('reportName')
        if 'format' in result:
            response['format'] = result.get('format')
        if 'size' in result:
            response['size'] = result.get('size')
        
        return response
