"""Agent bridge - wraps MainAgent for web integration"""
import sys
import os
from typing import Dict, Any, Optional

# Add Agentic Framework to path
_currentDir = os.path.dirname(os.path.abspath(__file__))
_agenticFrameworkPath = os.path.join(_currentDir, '..', '..', 'Agentic Framework')
if os.path.exists(_agenticFrameworkPath) and _agenticFrameworkPath not in sys.path:
    sys.path.insert(0, _agenticFrameworkPath)

from agents.mainAgent import MainAgent
from orchestrator.executor import AgentExecutor
from tools.excelTool import ExcelTool
from tools.wordTool import WordTool
from tools.pdfTool import PDFTool
from orchestrator.reasoningEngine import createReasoningEngine
from integration.responseFormatter import ResponseFormatter


class AgentBridge:
    """Bridge between web API and MainAgent"""
    
    def __init__(self):
        self.agent = None
        self.executor = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize agent and register tools"""
        try:
            # Create agent
            self.agent = MainAgent("SparksBM DataProcessor")
            
            # Register Excel tool
            excelTool = ExcelTool()
            self.agent.registerTool('readExcel', excelTool.readExcel, 'Read Excel files')
            
            # Register Word tool
            wordTool = WordTool()
            self.agent.registerTool('readWord', wordTool.readWord, 'Read Word documents')
            
            # Register PDF tool
            try:
                pdfTool = PDFTool()
                self.agent.registerTool('readPDF', pdfTool.readPDF, 'Read PDF files')
            except Exception:
                pass
            
            # Register Reasoning Engine (Ollama Cloud API) - INTERNAL ONLY, not shown in UI
            try:
                reasoningEngine = createReasoningEngine("ollama")
                
                # Store reasoning engine reference for document handlers and knowledge questions
                self.agent._reasoningEngine = reasoningEngine
                
                # Create LLMTool adapter for backward compatibility with IntentClassifier, QueryPlanner, etc.
                # These components still expect LLMTool interface, so we create a simple adapter
                class ReasoningEngineAdapter:
                    """Adapter to make ReasoningEngine compatible with old LLMTool interface"""
                    def __init__(self, engine):
                        self.engine = engine
                        self.provider = 'ollama'
                    
                    def generate(self, prompt: str, systemPrompt: str = "", maxTokens: int = 512, **kwargs) -> str:
                        """Generate text using ReasoningEngine"""
                        context = {"system": systemPrompt} if systemPrompt else None
                        return self.engine.reason(prompt, context=context)
                    
                    def analyze(self, data: Any, analysisType: str = "summary", **kwargs) -> str:
                        """Analyze data using ReasoningEngine"""
                        prompt = f"Analyze the following data ({analysisType}):\n\n{data}"
                        return self.engine.reason(prompt)
                    
                    def extractEntities(self, text: str, entityTypes: list, **kwargs) -> dict:
                        """Extract entities using ReasoningEngine"""
                        prompt = f"Extract the following entity types from the text: {', '.join(entityTypes)}\n\nText:\n{text}\n\nReturn as JSON."
                        response = self.engine.reason(prompt)
                        # Try to parse JSON from response
                        import json
                        try:
                            if '```json' in response:
                                json_str = response.split('```json')[1].split('```')[0].strip()
                            elif '```' in response:
                                json_str = response.split('```')[1].split('```')[0].strip()
                            else:
                                json_str = response.strip()
                            return json.loads(json_str)
                        except (json.JSONDecodeError, ValueError, KeyError, IndexError):
                            return {'raw': response, 'entities': []}
                
                # Create adapter for backward compatibility
                llmAdapter = ReasoningEngineAdapter(reasoningEngine) if reasoningEngine.isAvailable() else None
                
                if llmAdapter:
                    # Register LLM tools (via adapter) but mark them as internal (not for UI display)
                    self.agent.registerTool('generate', llmAdapter.generate, 'Generate text using LLM')
                    self.agent.registerTool('analyze', llmAdapter.analyze, 'Analyze data using LLM')
                    self.agent.registerTool('extractEntities', llmAdapter.extractEntities, 'Extract entities from text')
                    # Store adapter reference for backward compatibility
                    self.agent._llmTool = llmAdapter
                    
                    # Initialize Intent Classifier (uses adapter for backward compatibility)
                    if hasattr(self.agent, '_intentClassifier') and self.agent._intentClassifier is None:
                        from orchestrator.intentClassifier import IntentClassifier
                        self.agent._intentClassifier = IntentClassifier(llmAdapter)
                    
                    # Initialize query planner with adapter
                    if hasattr(self.agent, 'queryPlanner') and self.agent.queryPlanner is None:
                        from orchestrator.queryPlanner import QueryPlanner
                        self.agent.queryPlanner = QueryPlanner(llmAdapter)
                    
                    # Initialize tool chain
                    if hasattr(self.agent, 'toolChain') and self.agent.toolChain is None:
                        from orchestrator.toolChain import ToolChain
                        self.agent.toolChain = ToolChain(self.agent)
                else:
                    print("⚠️  Reasoning Engine not available, some features may be limited")
                    
            except Exception as e:
                print(f"⚠️  Failed to initialize Reasoning Engine: {e}")
                # Continue without LLM - agent can still process files and ISMS operations
            
            # Register Document Query Tools (for intelligent document querying)
            try:
                from tools.documentQueryTool import DocumentQueryTool
                from tools.intelligentOrchestrator import IntelligentOrchestrator
                
                documentQueryTool = DocumentQueryTool()
                
                # Register query tools
                self.agent.registerTool('getRowCount', documentQueryTool.getRowCount, 'Get row count from Excel')
                self.agent.registerTool('getColumn', documentQueryTool.getColumn, 'Extract column from Excel')
                self.agent.registerTool('getColumns', documentQueryTool.getColumns, 'List all columns')
                self.agent.registerTool('getRows', documentQueryTool.getRows, 'Get rows from document')
                self.agent.registerTool('filterRows', documentQueryTool.filterRows, 'Filter rows by conditions')
                self.agent.registerTool('searchInDocument', documentQueryTool.searchInDocument, 'Search in Word/PDF')
                self.agent.registerTool('getDocumentSummary', documentQueryTool.getDocumentSummary, 'Get document summary')
                
                # Create intelligent orchestrator (uses ReasoningEngine via adapter)
                if hasattr(self.agent, '_llmTool') and self.agent._llmTool:
                    self.agent._intelligentOrchestrator = IntelligentOrchestrator(
                        self.agent._llmTool, 
                        documentQueryTool
                    )
            except Exception:
                pass
            
            # Register ISMS tool (lazy initialization - will initialize on first use)
            # Don't initialize at startup to avoid timing issues with Keycloak
            # Tool will be initialized when first ISMS operation is requested
            self.agent._veriniceTool = None
            
            # Create executor
            self.executor = AgentExecutor([self.agent])
            self.agent.executor = self.executor
            
            self._initialized = True
            return True
            
        except Exception as e:
            return False
    
    def process(self, message: str, context: Optional[Any] = None) -> Dict[str, Any]:
        """Process message with optional context"""
        if not self._initialized:
            if not self.initialize():
                return {
                    'status': 'error',
                    'result': None,
                    'error': 'Failed to initialize agent'
                }
        
        try:
            # Handle context - can be string or dict
            if isinstance(context, dict):
                # Store context dict in agent state for access during processing
                if self.agent:
                    # Store activeSources and metadata in agent state
                    self.agent.state['_sessionContext'] = context
                    # Build context string for message
                    contextStr = context.get('context', '')
                    fullMessage = f"{contextStr}\n\nUser: {message}" if contextStr else message
                else:
                    fullMessage = message
            else:
                # Context is a string (legacy format)
                fullMessage = f"{context}\n\nUser: {message}" if context else message
            
            # Execute via executor
            result = self.executor.execute(
                task="Chat message",
                inputData=fullMessage
            )
            
            if result.get('success'):
                # Extract response from result
                resultData = result.get('result', {})
                
                # Determine result type
                if isinstance(resultData, dict):
                    resultType = resultData.get('type', 'chat_response')
                else:
                    resultType = 'chat_response'
                
                # Use presenter layer if result is structured, otherwise use formatter
                if isinstance(resultData, dict) and resultData.get('type') in ['table', 'object_detail', 'report']:
                    # Already formatted by presenter layer - use as-is
                    formattedResponse = resultData
                else:
                    # Use smart formatter for other types
                    formattedResponse = ResponseFormatter.format(
                        resultData,
                        resultType=resultType,
                        context={'message': message, 'context': context}
                    )
                
                # Extract content if formattedResponse is a text type dictionary
                if isinstance(formattedResponse, dict) and formattedResponse.get('type') == 'text':
                    formattedResponse = formattedResponse.get('content', str(formattedResponse))
                
                # Preserve PDF data and other metadata if present
                # If formattedResponse is structured data (table/object_detail), preserve it
                response = {
                    'status': 'success',
                    'result': formattedResponse,
                    'type': resultType
                }
                
                # If result is structured data, add type indicator
                if isinstance(formattedResponse, dict) and formattedResponse.get('type') in ['table', 'object_detail']:
                    response['dataType'] = formattedResponse.get('type')
                
                # Include PDF data for report generation
                # Check for report object first (new format from handler)
                if isinstance(resultData, dict):
                    if 'report' in resultData:
                        response['report'] = resultData.get('report')
                    # Legacy individual fields (for backward compatibility)
                    if 'reportData' in resultData:
                        response['reportData'] = resultData.get('reportData')
                    if 'reportId' in resultData:
                        response['reportId'] = resultData.get('reportId')
                    if 'reportName' in resultData:
                        response['reportName'] = resultData.get('reportName')
                    if 'format' in resultData:
                        response['format'] = resultData.get('format')
                    if 'size' in resultData:
                        response['size'] = resultData.get('size')
                
                return response
            else:
                # Handle error results with smart formatting
                resultData = result.get('result', {})
                errorMsg = None
                
                if isinstance(resultData, dict):
                    errorMsg = resultData.get('error') or resultData.get('result') or 'Unknown error'
                else:
                    errorMsg = result.get('error') or str(resultData) or 'Unknown error'
                
                # Format error intelligently
                formattedError = ResponseFormatter.format(errorMsg, resultType='error', context={'message': message})
                
                return {
                    'status': 'error',
                    'result': formattedError,
                    'error': formattedError
                }
                
        except Exception as e:
            import traceback
            # Format exception intelligently
            errorMsg = ResponseFormatter.format(
                str(e),
                resultType='error',
                context={'message': message, 'exception': True}
            )
            return {
                'status': 'error',
                'result': errorMsg,
                'error': errorMsg
            }
    
    def isInitialized(self) -> bool:
        """Check if agent is initialized"""
        return self._initialized
