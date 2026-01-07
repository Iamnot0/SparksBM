"""Main Agent - Handles documents, LLM, delegates ISMS to ISMSHandler"""
from typing import Dict, Any, Optional, List
import re
import json
from pathlib import Path
from .baseAgent import BaseAgent
from .ismsHandler import ISMSHandler
from .excelDoc import ExcelDocHandler
from .wordDoc import WordDocHandler
from .pdfDoc import PDFDocHandler
from .instructions import (
    VERINICE_OBJECT_TYPES,
    KNOWLEDGE_QUESTION_STARTERS,
    KNOWLEDGE_QUESTION_PHRASES,
    KNOWLEDGE_WHAT_PATTERNS,
    KNOWLEDGE_HOW_TO_CREATE_PATTERNS,
    BULK_IMPORT_TRIGGERS,
    TYPO_VARIATIONS,
    get_error_message,
)
from .helpers import (
    parseSubtypeSelection,
    checkGreeting,
    formatTextResponse,
    successResponse,
    errorResponse,
)
from .coordinators.documentCoordinator import DocumentCoordinator


class MainAgent(BaseAgent):
    """Main agent for document processing and ISMS operations"""
    
    def __init__(self, name: str = "SparksBM DataProcessor", executor=None):
        goals = [
            "Extract data from Excel and Word files",
            "Validate document structure",
            "Transform data for Verinice ISMS"
        ]
        instructions = """You are SparksBM Intelligent, a professional ISMS compliance assistant integrated with Verinice.

Your expertise:
- ISO 27001, ISO 22301, NIS-2 compliance standards
- Verinice ISMS platform operations
- Risk management, asset management, control implementation
- Document analysis (Excel, Word, PDF)

Communication style:
- Professional but friendly and approachable
- Clear, concise, and actionable
- Use ISMS terminology correctly
- Provide context and examples when helpful

CRITICAL RULES:
- NEVER expose tool names, tool calls, or execution steps to users
- ALWAYS narrate actions as if performed by you, not by tools
- Errors must be rewritten as calm, user-facing explanations with next steps
- One action per message, one question max
- No system wording ("service issue", "tool", "operation")
- End with guidance or a choice when appropriate
- When analyzing documents, provide structured summaries with key findings and recommendations"""
        
        super().__init__(name, "DataProcessor", goals, instructions)
        self.executor = executor
        self.processedFiles = []
        self.conversationHistory = []
        self.lastUserMessage = None
        
        # Context management
        try:
            from memory.enhancedContextManager import EnhancedContextManager
            self.contextManager = EnhancedContextManager()
        except ImportError:
            self.contextManager = None
        
        # Intent classifier (lazy initialization)
        self._intentClassifier = None
        
        # Load knowledge base from JSON
        self._knowledgeBase = self._loadKnowledgeBase()
    
        # ISMS handler (initialized when veriniceTool is set)
        self._ismsHandler = None
        
        # Document handlers (initialized lazily)
        self._excelHandler = None
        self._wordHandler = None
        self._pdfHandler = None
        
        # Document Coordinator (Phase 2 - lazy initialization)
        self._docCoordinator = None
        
        # PHASE 3: Chat Router (shadow testing mode)
        self._chatRouter = None
        self._useChatRouter = True  # Feature flag: False = shadow mode, True = active mode - DEPLOYED 2026-01-03
        self._routingLog = []  # Log routing decisions for comparison
    
    def _ensureDocCoordinator(self):
        """Initialize Document Coordinator if needed (Phase 2)"""
        if not self._docCoordinator:
            veriniceTool = getattr(self, "_veriniceTool", None)
            llmTool = getattr(self, "_llmTool", None)
            reasoningEngine = getattr(self, "_reasoningEngine", None)
            formatFunc = self._formatVeriniceResult if hasattr(self, '_formatVeriniceResult') else None
            self._docCoordinator = DocumentCoordinator(
                state=self.state,
                tools=self.tools,
                contextManager=self.contextManager,
                llmTool=llmTool,  # For backward compatibility
                reasoningEngine=reasoningEngine,  # Preferred
                veriniceTool=veriniceTool,
                formatVeriniceResult=formatFunc
            )
            # Store agent reference in state for coordinator to access reasoningEngine
            if reasoningEngine:
                self.state['_agent'] = self
    
    def _ensureExcelHandler(self):
        """Initialize Excel handler if needed"""
        if not self._excelHandler:
            veriniceTool = getattr(self, "_veriniceTool", None)
            llmTool = getattr(self, "_llmTool", None)
            formatFunc = self._formatVeriniceResult if hasattr(self, '_formatVeriniceResult') else None
            # Initialize ISMS handler if needed for Excel handler
            if not self._ismsHandler and veriniceTool:
                self._ismsHandler = ISMSHandler(veriniceTool, formatFunc, llmTool)
            self._excelHandler = ExcelDocHandler(veriniceTool, formatFunc, llmTool, self._ismsHandler)
    
    def _ensureWordHandler(self):
        """Initialize Word handler if needed"""
        if not self._wordHandler:
            llmTool = getattr(self, "_llmTool", None)
            self._wordHandler = WordDocHandler(llmTool)
    
    def _ensurePDFHandler(self):
        """Initialize PDF handler if needed"""
        if not self._pdfHandler:
            llmTool = getattr(self, "_llmTool", None)
            self._pdfHandler = PDFDocHandler(llmTool)
    
    def process(self, inputData: Any) -> Dict:
        """Main entry point - route to appropriate handler"""
        try:
            if isinstance(inputData, str):
                # Extract the actual message if it contains "User: " prefix (from agentBridge)
                actualMessage = inputData
                if '\n\nUser: ' in inputData:
                    actualMessage = inputData.split('\n\nUser: ')[-1]
                elif '\nUser: ' in inputData:
                    actualMessage = inputData.split('\nUser: ')[-1]
                
                # Strip trailing punctuation first to avoid false positives (e.g., "list process.")
                cleaned = actualMessage.rstrip('.,!?;:').strip()
                
                # Explicit check: If message starts with common command words, it's NOT a file
                commandStarters = ['list', 'create', 'get', 'update', 'delete', 'show', 'generate', 'analyze', 'compare']
                isCommand = any(cleaned.lower().startswith(cmd + ' ') or cleaned.lower() == cmd for cmd in commandStarters)
                
                if isCommand:
                    # Definitely a command, not a file
                    return self._processChatMessage(actualMessage)
                
                # Check for file extension (must have non-empty extension after dot)
                parts = cleaned.split('.')
                hasExtension = len(parts) > 1 and len(parts[-1]) > 0 and len(parts[-1]) <= 5 and parts[-1].isalnum()
                hasPathSeparator = '/' in cleaned or '\\' in cleaned
                
                # Only treat as file if it looks like a real file path
                # Must have both extension AND path separator, OR start with common file patterns
                if (hasExtension and hasPathSeparator) or cleaned.startswith(('uploads/', './', '../', '/', 'C:', 'D:')):
                    return self._processFile(inputData)
                else:
                    # Use the actual message for chat processing
                    return self._processChatMessage(actualMessage)
            elif isinstance(inputData, dict):
                return self._processData(inputData)
            else:
                return {'status': 'error', 'result': None, 'error': get_error_message('validation', 'invalid_input_type')}
        except Exception as e:
            return {'status': 'error', 'result': None, 'error': str(e)}
    
    # ==================== DOCUMENT PROCESSING ====================
    
    def _processFile(self, filePath: str) -> Dict:
        """Process Excel, Word, or PDF file - delegates to Document Coordinator (Phase 2)"""
        self._ensureDocCoordinator()
        result = self._docCoordinator.processFile(filePath)
        # Track processed files
        if result.get('status') == 'success':
            self.processedFiles.append(filePath)
        return result
    
    def _processData(self, data: Dict) -> Dict:
        """Process already structured data - delegates to Document Coordinator (Phase 2)"""
        self._ensureDocCoordinator()
        return self._docCoordinator.processData(data)
    
    # ==================== CHAT MESSAGE PROCESSING ====================
    
    def _processChatMessage(self, message: str) -> Dict:
        """Process chat message - AI-driven natural routing"""
        try:
            # PHASE 3: Shadow testing - run new router in parallel
            newRouterDecision = None
            if self._chatRouter or not self._useChatRouter:
                newRouterDecision = self._shadowTestNewRouter(message)
            
            # If using new router (feature flag enabled), execute its decision
            if self._useChatRouter and newRouterDecision:
                return self._executeRoutingDecision(newRouterDecision, message)
            # 0. PRIORITY: Check for follow-up responses FIRST (before any other processing)
            # This ensures follow-up handlers get priority over intent classification
            
            # Check report generation follow-up first (scope selection)
            if self.state.get('pendingReportGeneration'):
                followUpResult = self._handleReportGenerationFollowUp(message)
                if followUpResult:
                    if newRouterDecision:
                        self._logRoutingComparison(message, "follow_up_report", newRouterDecision, followUpResult)
                    return followUpResult
            
            # Check subtype selection follow-up
            followUpResult = self._handleSubtypeFollowUp(message)
            if followUpResult:
                if newRouterDecision:
                    self._logRoutingComparison(message, "follow_up_subtype", newRouterDecision, followUpResult)
                return followUpResult
            
            # Store message (only if not a follow-up)
            self.lastUserMessage = message
            self.conversationHistory.append({'user': message, 'timestamp': None})
            if len(self.conversationHistory) > 10:
                self.conversationHistory.pop(0)
            
            if self.contextManager:
                self.contextManager.addToConversation('user', message)
            
            # 1. Quick greeting check (fast response)
            greeting = self._checkGreeting(message)
            if greeting:
                greetingResult = self._success(greeting)
                if newRouterDecision:
                    self._logRoutingComparison(message, "greeting", newRouterDecision, greetingResult)
                return greetingResult
            
            # 2. Get context from state if available (set by agentBridge with activeSources)
            sessionContext = self.state.get('_sessionContext', {})
            if sessionContext and isinstance(sessionContext, dict):
                # Use session context which has activeSources and metadata from session
                context = sessionContext.copy()
            else:
                # Build basic context if no session context available
                context = {
                    'hasProcessedDocument': bool(self.state.get('lastProcessed')),
                    'documentCount': 1 if self.state.get('lastProcessed') else 0,
                    'excelFileCount': 0,
                    'pendingFileAction': self.state.get('pendingFileAction'),
                    'conversationHistory': self.conversationHistory[-3:] if self.conversationHistory else [],
                    'activeSources': []
                }
                # Count Excel files from processedFiles if available
                if hasattr(self, 'processedFiles'):
                    context['excelFileCount'] = sum(1 for f in self.processedFiles if f.endswith(('.xlsx', '.xls')))
            
            # 3. CRITICAL: Check for Verinice operations FIRST (before IntentClassifier)
            # This ensures ISMS commands work even if IntentClassifier fails or misclassifies
            veriniceOp = self._detectVeriniceOp(message)
            if veriniceOp:
                veriniceResult = self._handleVeriniceOp(veriniceOp, message)
                if newRouterDecision:
                    self._logRoutingComparison(message, "verinice_operation", newRouterDecision, veriniceResult)
                return veriniceResult
            
            # 4. Check for report generation (before IntentClassifier to avoid misclassification)
            reportGen = self._detectReportGeneration(message)
            if reportGen:
                reportResult = self._handleReportGeneration(reportGen, message)
                if newRouterDecision:
                    self._logRoutingComparison(message, "report_generation", newRouterDecision, reportResult)
                return reportResult
            
            # 5. Initialize IntentClassifier if not already initialized (lazy init)
            if not hasattr(self, '_intentClassifier') or not self._intentClassifier:
                try:
                    from orchestrator.intentClassifier import IntentClassifier
                    llmTool = getattr(self, '_llmTool', None)
                    if llmTool:
                        self._intentClassifier = IntentClassifier(llmTool)
                except Exception:
                    self._intentClassifier = None
            
            # 6. Use IntentClassifier to understand what user wants (AI-driven)
            # Only use if pattern-based detection didn't catch it
            if hasattr(self, '_intentClassifier') and self._intentClassifier:
                try:
                    classification = self._intentClassifier.classify(message, context)
                    intent = classification.get('intent', 'unknown')
                    confidence = classification.get('confidence', 0)
                    
                    # Route based on classified intent
                    if confidence >= 0.6:  # Only use if confident enough
                        if intent == 'verinice_create':
                            # Extract operation details and handle
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                        elif intent == 'verinice_list':
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                        elif intent == 'verinice_get':
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                        elif intent == 'verinice_update':
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                        elif intent == 'verinice_delete':
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                        elif intent == 'analyze_document' and context.get('hasProcessedDocument'):
                            return self._analyzeDocumentWithLLM(message)
                        
                        elif intent == 'query_document' and context.get('hasProcessedDocument'):
                            docQuery = self._checkDocumentQuery(message)
                            if docQuery:
                                return docQuery
                        
                        elif intent == 'compare_excel':
                            # Don't require hasProcessedDocument - we check for Excel files in handler
                            comparison = self._handleExcelComparison(message, context)
                            if comparison:
                                return comparison
                except Exception:
                    # Intent classification failed - continue to next handler
                    pass
            
            # 6. Fallback: Check for document operations if document exists
            if context.get('hasProcessedDocument'):
                # IMPORTANT: Re-check for Verinice operations FIRST (even with document uploaded)
                # This ensures ISMS operations like "list scopes" work even when documents are uploaded
                veriniceOp = self._detectVeriniceOp(message)
                if veriniceOp:
                    return self._handleVeriniceOp(veriniceOp, message)
                
                # Try bulk import (user might say "create assets", "import", etc.)
                bulkImport = self._handleBulkAssetImport(message)
                if bulkImport:
                    # If bulk import returned an error, show it (don't fall through to generic fallback)
                    if bulkImport.get('status') == 'error':
                        return bulkImport
                    # If bulk import returned success, return it
                    return bulkImport
                
                # Try document analysis
                if self._isDocumentAnalysisRequest(message):
                    return self._analyzeDocumentWithLLM(message)
                
                # Try document queries (only if not an ISMS operation)
                docQuery = self._checkDocumentQuery(message)
                if docQuery:
                    return docQuery
            
            # 7. Check fallback knowledge base (pattern-based, for backward compatibility)
            fallbackAnswer = self._getFallbackAnswer(message)
            if fallbackAnswer:
                return self._success(fallbackAnswer)
            
            # 8. Route ALL knowledge questions to ReasoningEngine (not just pattern-based)
            reasoningEngine = getattr(self, '_reasoningEngine', None)
            if reasoningEngine and reasoningEngine.isAvailable():
                try:
                    # Check if this looks like a knowledge question
                    messageLower = message.lower().strip()
                    isKnowledgeQuestion = any(
                        starter in messageLower 
                        for starter in KNOWLEDGE_QUESTION_STARTERS
                    ) or messageLower.endswith('?')
                    
                    # Route to ReasoningEngine if it's a knowledge question OR not an ISMS operation
                    isISMSOp = any([
                        'create' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                        'list' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                        'get' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                        'update' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                        'delete' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                    ])
                    
                    if isKnowledgeQuestion or not isISMSOp:
                        # This is a knowledge question or general query - use ReasoningEngine
                        # IMPORTANT: Don't override the concise mode - let ReasoningEngine use its default
                        # The system_prompt will be enhanced by ReasoningEngine with concise constraints
                        system_prompt = f"{self.instructions}\n\nYou are an expert ISMS compliance assistant. Answer questions about ISO 27001, ISMS, Verinice, and related topics clearly and helpfully."
                        context = {
                            "system": "You are an ISMS expert assistant helping users understand ISMS concepts, ISO 27001 compliance, and Verinice operations."
                        }
                        # Explicitly pass response_mode='concise' to ensure concise mode is used
                        response = reasoningEngine.reason(message, context=context, system_prompt=system_prompt, response_mode='concise')
                        return self._success(response)
                except Exception:
                    # Fallback to tool-based generation if ReasoningEngine fails
                    pass
            
            # 9. Fallback: Use generate tool if available (for backward compatibility)
            if 'generate' in self.tools:
                try:
                    response = self.executeTool('generate', prompt=message, systemPrompt=self.instructions)
                    formattedResponse = self._formatTextResponse(response)
                    return self._success(formattedResponse)
                except Exception:
                    pass
            
            # 9. Final fallback
            oldResult = self._success("I can help with documents and ISMS operations. Try: 'list scopes' or upload a file.")
            
            # PHASE 3: Log old routing decision for comparison
            if newRouterDecision:
                self._logRoutingComparison(message, "final_fallback", newRouterDecision, oldResult)
            
            return oldResult
        except Exception as e:
            # Never return None - always provide actionable feedback
            return {
                'status': 'error', 
                'result': f"I encountered an error: {str(e)}\n\nYou can try:\n  • list scopes\n  • create scope MyScope MS Description\n  • upload a document\n  • ask 'help'", 
                'error': str(e)
            }
    
    # ==================== VERINICE OPERATIONS ====================
    
    def _detectVeriniceOp(self, message: str) -> Optional[Dict]:
        """Detect Verinice operation from message - ignore questions"""
        try:
            messageLower = message.lower().strip()
            
            # Skip questions - these should go to LLM for knowledge answers
            if any(messageLower.startswith(phrase) for phrase in KNOWLEDGE_QUESTION_PHRASES):
                return None
    
            # Normalize typos - only replace whole words to avoid substring issues
            # Build typo map from JSON (reverse lookup: typo -> correct)
            typoMap = {}
            for correct, typos in TYPO_VARIATIONS.items():
                for typo in typos:
                    typoMap[typo] = correct
            # Add direct mappings for common typos
            typoMap.update({
                'creat': 'create', 'crate': 'create',
                'assest': 'asset', 'assests': 'assets',
                'scop': 'scope', 'scops': 'scopes',
                'persn': 'person', 'persns': 'persons'
            })
            for typo, correct in typoMap.items():
                # Use word boundaries to only replace whole words, not substrings
                pattern = r'\b' + re.escape(typo) + r'\b'
                messageLower = re.sub(pattern, correct, messageLower)
            
            # Extract object type
            # Check plural forms first to avoid substring matching issues (e.g., "process" in "processes")
            objectType = None
            # Sort to check plurals first (longer strings first), then check for whole word matches
            sortedTypes = sorted(VERINICE_OBJECT_TYPES, key=len, reverse=True)
            for objType in sortedTypes:
                # Use word boundary matching to avoid substring issues
                pattern = r'\b' + re.escape(objType) + r'\b'
                if re.search(pattern, messageLower):
                    # Convert to singular: remove trailing "s" but handle special cases correctly
                    if objType.endswith("es"):
                        # Handle words ending in "es": "processes" -> "process", "scopes" -> "scope"
                        if objType == "processes":
                            objectType = "process"
                        elif objType == "scopes":
                            objectType = "scope"
                        else:
                            objectType = objType[:-2]  # Remove "es" for other words
                    elif objType.endswith("s") and objType != "process":  # Don't modify "process" itself
                        objectType = objType[:-1]  # Remove single "s" (e.g., "assets" -> "asset")
                    else:
                        objectType = objType  # Already singular
                    break
            
            if not objectType:
                return None
        
            # Detect operation - use word boundaries to avoid false matches (e.g., "NEW" triggering "new")
            # Extract keywords from JSON patterns (more maintainable)
            updateKeywords = ['update', 'edit', 'modify']
            deleteKeywords = ['delete', 'remove']
            createKeywords = ['create', 'new', 'add', 'make']
            listKeywords = ['list', 'show', 'display']
            getKeywords = ['get', 'view']
            analyzeKeywords = ['analyze']
            
            # Check UPDATE/DELETE first (most specific)
            if any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in updateKeywords):
                return {'operation': 'update', 'objectType': objectType}
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in deleteKeywords):
                return {'operation': 'delete', 'objectType': objectType}
            # Then CREATE
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in createKeywords) and not any(q in messageLower for q in ['how', 'what', 'why']):
                return {'operation': 'create', 'objectType': objectType}
            # Then LIST/GET
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in listKeywords) and not any(q in messageLower for q in ['how', 'what', 'why']):
                return {'operation': 'list', 'objectType': objectType}
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in getKeywords) and not any(q in messageLower for q in ['how', 'what', 'why']):
                return {'operation': 'get', 'objectType': objectType}
            # Then ANALYZE
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in analyzeKeywords):
                return {'operation': 'analyze', 'objectType': objectType}
            
            return None
        except Exception:
            # If detection fails, return None (don't break the flow)
            return None
    
    def _detectReportGeneration(self, message: str) -> Optional[Dict]:
        """Detect report generation requests"""
        messageLower = message.lower().strip()
        
        # Check for report generation keywords
        reportKeywords = ['generate', 'create', 'make', 'get']
        reportTypes = ['inventory of assets', 'risk assessment', 'statement of applicability', 
                      'inventory', 'risk', 'statement', 'report']
        
        hasReportKeyword = any(keyword in messageLower for keyword in reportKeywords)
        hasReportType = any(reportType in messageLower for reportType in reportTypes)
        
        if hasReportKeyword and hasReportType:
            # Extract report type
            reportType = None
            if 'inventory' in messageLower and 'asset' in messageLower:
                reportType = 'inventory-of-assets'
            elif 'risk' in messageLower and 'assessment' in messageLower:
                reportType = 'risk-assessment'
            elif 'statement' in messageLower and 'applicability' in messageLower:
                reportType = 'statement-of-applicability'
            elif 'inventory' in messageLower:
                reportType = 'inventory-of-assets'
            elif 'risk' in messageLower:
                reportType = 'risk-assessment'
            elif 'statement' in messageLower:
                reportType = 'statement-of-applicability'
            
            if reportType:
                return {'operation': 'generate_report', 'reportType': reportType}
        
        return None
    
    def _handleReportGeneration(self, command: Dict, message: str) -> Dict:
        """Handle report generation - list scopes and ask user to select"""
        reportType = command.get('reportType')
        if not reportType:
            return self._error(get_error_message('user_guidance', 'what_report'))
        
        # Initialize handler if needed
        if not self._ismsHandler:
            veriniceTool = getattr(self, "_veriniceTool", None)
            if not veriniceTool:
                return self._error(get_error_message('connection', 'isms_client_not_available'))
            llmTool = getattr(self, '_llmTool', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool)
        
        # Get available scopes
        domainId, unitId = self._ismsHandler._getDefaults()
        if not domainId:
            return self._error(get_error_message('not_found', 'domain'))
        
        # List scopes
        scopesResult = self._ismsHandler.veriniceTool.listObjects('scope', domainId)
        if not scopesResult.get('success'):
            return self._error(get_error_message('operation_failed', 'list_scopes', error=scopesResult.get('error', 'Unknown error')))
        
        # Extract scopes
        objects = scopesResult.get('objects', {})
        items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
        
        if not items:
            return self._error(get_error_message('not_found', 'scopes'))
        
        # Format report type name
        reportNames = {
            'inventory-of-assets': 'Inventory of Assets',
            'risk-assessment': 'Risk Assessment',
            'statement-of-applicability': 'Statement of Applicability'
        }
        
        # Store pending report generation state
        self.state['pendingReportGeneration'] = {
            'reportType': reportType,
            'reportName': reportNames.get(reportType, reportType.replace('-', ' ').title()),
            'scopes': items,
            'domainId': domainId
        }
        
        # Format scopes list
        from presenters.table import TablePresenter
        presenter = TablePresenter()
        formatted = presenter.present({
            'items': items,
            'columns': ['Name', 'Description'],
            'title': f'Which scope do you want to generate the "{reportNames.get(reportType, reportType.replace("-", " ").title())}" report for?',
            'total': len(items)
        })
        
        if isinstance(formatted, dict) and formatted.get('type') == 'text':
            content = formatted.get('content', str(formatted))
            # Add instruction
            content += "\n\nPlease specify which scope (by name or number) to generate the report for."
            return self._success(content)
        
        return self._success(formatted)
    
    def _handleReportGenerationFollowUp(self, message: str) -> Dict:
        """Handle follow-up response for report generation (scope selection)"""
        pending = self.state.get('pendingReportGeneration')
        if not pending:
            return self._error(get_error_message('not_found', 'pending_report'))
        
        reportType = pending['reportType']
        scopes = pending['scopes']
        domainId = pending['domainId']
        
        # Clear pending state
        del self.state['pendingReportGeneration']
        
        # Parse user input - could be number or scope name
        messageLower = message.strip().lower()
        selectedScope = None
        
        # Try to parse as number
        try:
            scopeIndex = int(messageLower) - 1
            if 0 <= scopeIndex < len(scopes):
                selectedScope = scopes[scopeIndex]
        except ValueError:
            # Not a number, try to find by name
            for scope in scopes:
                scopeName = scope.get('name', '').lower()
                if messageLower in scopeName or scopeName in messageLower:
                    selectedScope = scope
                    break
                            
        if not selectedScope:
            return self._error(get_error_message('not_found', 'scope', name=message))
        
        # Get scope ID
        scopeId = selectedScope.get('id') or selectedScope.get('value')
        if not scopeId:
            return self._error(get_error_message('operation_failed', 'list_scopes', error='Could not determine scope ID.'))
        
        # Generate report
        if not self._ismsHandler:
            veriniceTool = getattr(self, '_veriniceTool', None)
            if not veriniceTool:
                return self._error(get_error_message('connection', 'isms_client_not_available'))
            llmTool = getattr(self, '_llmTool', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool)
        
        # Generate report with scope as target
        params = {
            'outputType': 'application/pdf',
            'language': 'en',
            'targets': [{'id': scopeId, 'modelType': 'scope'}],
            'timeZone': 'UTC'
        }
        
        result = self._ismsHandler.veriniceTool.generateReport(reportType, domainId, params)
        
        if result.get('success'):
            scopeName = selectedScope.get('name', 'Unknown')
            reportId = result.get('reportId', reportType)
            reportSize = result.get('size', 0)
            reportFormat = result.get('format', 'pdf')
            
            # Build success message with report details
            message = f"✅ Report '{pending['reportName']}' generated successfully for scope '{scopeName}'.\n\n"
            message += "Report Details:\n"
            message += f"• Report ID: {reportId}\n"
            message += f"• Format: {reportFormat.upper()}\n"
            message += f"• Size: {reportSize:,} bytes\n"
            message += f"• Scope: {scopeName}\n"
            
            # Include report data in response if available (for verification)
            response_data = {
                'status': 'success',
                'result': message,
                'type': 'chat_response',
                'report': {
                    'id': reportId,
                    'type': reportType,
                    'format': reportFormat,
                    'size': reportSize,
                    'scope': scopeName,
                    'data': result.get('data'),  # Base64 PDF data if available
                    'generated_at': result.get('generated_at')
                }
            }
            return response_data
        else:
            return self._error(get_error_message('operation_failed', 'generate_report', error=result.get('error', 'Unknown error')))
    
    def _handleSubtypeFollowUp(self, message: str) -> Optional[Dict]:
        """Handle follow-up response for subtype selection (e.g., user replies "2" or "PER_DataProtectionOfficer")"""
        # Check both agent state and ISMS handler state
        pending = self.state.get('_pendingSubtypeSelection')
        if not pending and self._ismsHandler and hasattr(self._ismsHandler, 'state'):
            pending = self._ismsHandler.state.get('_pendingSubtypeSelection')
        
        if not pending:
            return None
        
        # Check if message is a number (1-9) or subtype name
        message_clean = message.strip()
        
        # Try to parse as number
        try:
            selection_num = int(message_clean)
            availableSubTypes = pending.get('availableSubTypes', [])
            if 1 <= selection_num <= len(availableSubTypes):
                selectedSubType = availableSubTypes[selection_num - 1]
            else:
                return self._error(get_error_message('validation', 'invalid_selection', max=len(availableSubTypes)))
        except ValueError:
            # Not a number, try to match as subtype name
            availableSubTypes = pending.get('availableSubTypes', [])
            selectedSubType = None
            
            # Exact match
            for subType in availableSubTypes:
                if message_clean.lower() == subType.lower():
                    selectedSubType = subType
                    break
            
            # Partial match
            if not selectedSubType:
                for subType in availableSubTypes:
                    if message_clean.lower() in subType.lower() or subType.lower() in message_clean.lower():
                        selectedSubType = subType
                        break
            
            if not selectedSubType:
                # Clear pending and show error
                self.state.pop('_pendingSubtypeSelection', None)
                if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                    self._ismsHandler.state.pop('_pendingSubtypeSelection', None)
                subtype_list = '\n'.join([f"{idx + 1}. {subType}" for idx, subType in enumerate(availableSubTypes)])
                return self._error(get_error_message('validation', 'invalid_subtype_selection', subtype=message_clean, options=subtype_list, max=len(availableSubTypes)))
        
        # Clear pending state
        self.state.pop('_pendingSubtypeSelection', None)
        if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
            self._ismsHandler.state.pop('_pendingSubtypeSelection', None)
        
        # Complete the creation with selected subtype
        if not self._ismsHandler:
            veriniceTool = getattr(self, "_veriniceTool", None)
            if not veriniceTool:
                return self._error(get_error_message('connection', 'isms_client_not_available'))
            llmTool = getattr(self, '_llmTool', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool)
        
        # Create object with selected subtype
        result = self._ismsHandler.veriniceTool.createObject(
            pending['objectType'],
            pending['domainId'],
            pending['unitId'],
            pending['name'],
            subType=selectedSubType,
            description=pending.get('description', ''),
            abbreviation=pending.get('abbreviation')
        )
        
        if result.get('success'):
            info = f"Created {pending['objectType']} '{pending['name']}'"
            if pending.get('abbreviation'):
                info += f" (abbreviation: {pending['abbreviation']})"
            info += f" (type: {selectedSubType})"
            return self._success(info)
        
        return self._error(get_error_message('operation_failed', 'create', objectType=pending['objectType'], error=result.get('error', 'Unknown error')))
    
    def _handleVeriniceOp(self, command: Dict, message: str) -> Dict:
        """Handle ISMS operation using ISMSHandler"""
        # Lazy initialization of VeriniceTool (fixes timing issue with Keycloak)
        veriniceTool = getattr(self, '_veriniceTool', None)
        if not veriniceTool:
            # Initialize VeriniceTool on first use (Keycloak should be ready by now)
            try:
                from tools.veriniceTool import VeriniceTool
                veriniceTool = VeriniceTool()
                self._veriniceTool = veriniceTool
            except Exception as e:
                return self._error(get_error_message('connection', 'isms_init_failed', error=str(e)))
        
        # Ensure authentication and ObjectManager are ready
        if not veriniceTool._ensureAuthenticated():
            return self._error(get_error_message('connection', 'isms_init_failed', error='ISMS client not available'))
        
        # Ensure ObjectManager is initialized (may have failed at startup)
        # _ensureAuthenticated should create it, but double-check
        if not veriniceTool.objectManager:
            # Try to ensure authentication again (this will create ObjectManager)
            if not veriniceTool._ensureAuthenticated():
                return self._error(get_error_message('connection', 'isms_auth_failed'))
            # If still no ObjectManager after authentication, return error
            if not veriniceTool.objectManager:
                return self._error(get_error_message('connection', 'isms_object_manager_unavailable'))
        
        # Initialize handler if needed
        if not self._ismsHandler:
            # Pass LLM tool if available for intelligent parsing
            llmTool = getattr(self, '_llmTool', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool)
        
        # Execute using simplified handler
        result = self._ismsHandler.execute(
            command['operation'],
            command['objectType'],
            message
        )
        
        # Check if result contains pending subtype selection (from create operation)
        # This happens when agent asks user to select subtype
        # Can be in either success or error response
        if '_pendingSubtypeSelection' in result:
            # Store pending create operation in agent state for follow-up handling
            self.state['_pendingSubtypeSelection'] = result['_pendingSubtypeSelection']
            # Return the message as success (not error) so it doesn't get formatted with error prefix
            # Preserve the metadata for agentBridge to pass through
            response = {'status': 'success', 'result': result.get('result'), 'type': 'tool_result'}
            response['_pendingSubtypeSelection'] = result['_pendingSubtypeSelection']
            return response
        
        return result
    
    # ==================== DOCUMENT ANALYSIS ====================
    
    def _isDocumentAnalysisRequest(self, message: str) -> bool:
        """Check if message is a document analysis request - uses LLM-based intent classification"""
        # Build context for intent classifier
        context = {
            'hasProcessedDocument': self.state.get('lastProcessed') is not None,
            'documentCount': 1 if self.state.get('lastProcessed') else 0
        }
        
        # Check if we have processed documents via agent.state['lastProcessed']
        if self.state.get('lastProcessed'):
            context['hasProcessedDocument'] = True
        
        # Use IntentClassifier (LLM-based)
        if hasattr(self, '_intentClassifier') and self._intentClassifier:
            try:
                classification = self._intentClassifier.classify(message, context=context)
                intent = classification.get('intent', '')
                confidence = classification.get('confidence', 0)
                
                # If LLM classified as analyze_document with good confidence, use it
                if intent == 'analyze_document' and confidence >= 0.7:
                    return True
                
                # If LLM says it's NOT analyze_document, trust it
                if intent != 'analyze_document' and confidence >= 0.8:
                    return False
            except Exception:
                # If LLM unavailable, return False (don't use pattern fallback)
                return False
        
        # If no intent classifier available, return False
        return False
    
    def _getDocumentContent(self, lastData: Dict, fileName: str = None, fileType: str = None) -> tuple:
        """
        Extract document content - delegates to Document Coordinator (Phase 2)
        Returns: (docContent, docType) or (None, None) if not found
        """
        self._ensureDocCoordinator()
        return self._docCoordinator.getDocumentContent(lastData, fileName, fileType)
    
    def _handleExcelComparison(self, message: str, context: Dict) -> Optional[Dict]:
        """Handle Excel file comparison - delegates to Document Coordinator (Phase 2)"""
        self._ensureDocCoordinator()
        return self._docCoordinator.handleExcelComparison(message, context, self._error, self._success)
    
    def _analyzeDocumentWithLLM(self, message: str) -> Dict:
        """Simple LLM-based document analysis"""
        # Try to find document from multiple sources
        lastData = self.state.get('lastProcessed')
        
        if lastData:
            # Check if data is None or empty
            if lastData.get('data') is None and not any(k in lastData for k in ['text', 'pages', 'sheets', 'paragraphs']):
                # Data is None - try to re-read from filePath if available
                filePath = lastData.get('filePath')
                fileName = lastData.get('fileName', '')
                fileType = lastData.get('fileType', '').lower()
                
                if filePath:
                    import os
                    if os.path.exists(filePath):
                        try:
                            # Re-read the file
                            if fileType == 'pdf' or fileName.lower().endswith('.pdf'):
                                lastData = self.executeTool('readPDF', filePath=filePath)
                            elif fileType in ['xlsx', 'xls'] or fileName.lower().endswith(('.xlsx', '.xls')):
                                lastData = self.executeTool('readExcel', filePath=filePath)
                            elif fileType in ['docx', 'doc'] or fileName.lower().endswith(('.docx', '.doc')):
                                lastData = self.executeTool('readWord', filePath=filePath)
                            
                            if isinstance(lastData, dict):
                                lastData['fileName'] = fileName
                                lastData['fileType'] = fileType
                                lastData['filePath'] = filePath
                                # Update state with re-read data
                                self.state['lastProcessed'] = lastData
                        except Exception:
                            return self._error(get_error_message('operation_failed', 're_read_file'))
        
        # If no lastProcessed or data is None/empty, check context manager
        if not lastData or (isinstance(lastData, dict) and lastData.get('data') is None and not any(k in lastData for k in ['text', 'pages', 'sheets', 'paragraphs'])):
            if self.contextManager and hasattr(self.contextManager, 'documents'):
                docs = self.contextManager.documents
                if docs:
                    # Get most recent document
                    latestDocId = max(docs.keys(), key=lambda k: docs[k].get('addedAt', ''))
                    docInfo = docs[latestDocId]
                    docData = docInfo.get('data', {})
                    if isinstance(docData, dict):
                        lastData = docData.copy()
                    else:
                        lastData = {'data': docData}
                    lastData['fileName'] = docInfo.get('fileName', 'document')
                    lastData['fileType'] = docInfo.get('type', 'unknown')
        
        # Check if message references a specific filename (Excel, Word, or PDF)
        # Note: File data should come from session.activeContext, not contextManager
        # contextManager is only for conversation history
        if not lastData:
            import re
            filenamePattern = r'["\']?([\w\-_]+\.(pdf|xlsx|xls|docx|doc))["\']?'
            match = re.search(filenamePattern, message, re.IGNORECASE)
            if match:
                filename = match.group(1)
                # File should be in session.activeContext, which is restored to agent.state['lastProcessed']
                # If not found, we can't proceed without filePath - return error
                return self._error(get_error_message('not_found', 'file', filename=filename))
        
        if not lastData:
            return self._error(get_error_message('not_found', 'document'))
        
        # Ensure lastData is a dict
        if not isinstance(lastData, dict):
            return self._error(get_error_message('data', 'invalid_format'))
        
        # Determine document type and get content
        fileName = lastData.get('fileName', 'document')
        fileType = lastData.get('fileType', '').lower()
        docContent = None
        docType = None
        
        # Get document content using helper method
        docContent, docType = self._getDocumentContent(lastData, fileName, fileType)
        
        # If no content found, try to re-read from filePath
        if not docContent:
            filePath = lastData.get('filePath')
            if filePath:
                import os
                if os.path.exists(filePath):
                    try:
                        # Re-read based on file type
                        if fileType == 'pdf' or (fileName and fileName.lower().endswith('.pdf')):
                            freshData = self.executeTool('readPDF', filePath=filePath)
                        elif fileType in ['xlsx', 'xls'] or (fileName and fileName.lower().endswith(('.xlsx', '.xls'))):
                            freshData = self.executeTool('readExcel', filePath=filePath)
                        elif fileType in ['docx', 'doc'] or (fileName and fileName.lower().endswith(('.docx', '.doc'))):
                            freshData = self.executeTool('readWord', filePath=filePath)
                        else:
                            freshData = None
                        
                        if freshData and isinstance(freshData, dict):
                            lastData.update(freshData)
                            lastData['filePath'] = filePath
                            docContent, docType = self._getDocumentContent(lastData, fileName, fileType)
                    except Exception:
                        pass
        
        # If still no content, provide helpful error
        if not docContent:
            docType = fileType.upper() if fileType else 'document'
            
            # Check for nested data structure and unwrap if needed
            if lastData and 'data' in lastData:
                nestedData = lastData.get('data')
                if isinstance(nestedData, dict) and any(k in nestedData for k in ['text', 'pages', 'sheets', 'paragraphs']):
                    # Unwrap nested data and try to get content again
                    docContent, docType = self._getDocumentContent(lastData, fileName, fileType)
            
            # Last resort: check if we can get data from context manager
            if not docContent and self.contextManager and hasattr(self.contextManager, 'documents'):
                for docId, docInfo in self.contextManager.documents.items():
                    if docInfo.get('fileName', '').lower() == fileName.lower():
                        docData = docInfo.get('data', {})
                        if isinstance(docData, dict) and any(k in docData for k in ['text', 'pages', 'sheets', 'paragraphs']):
                            lastData.update(docData)
                            # Try to get content again
                            docContent, docType = self._getDocumentContent(lastData, fileName, fileType)
                            break
            
            # Error message
            if lastData and lastData.get('data') is None:
                errorMsg = (
                    f"The file '{fileName}' was uploaded but the content could not be extracted. "
                    f"This may happen if:\n"
                    f"1. The file is corrupted or empty\n"
                    f"2. The file is image-based (scanned PDF) - try OCR first\n"
                    f"3. The file is encrypted or password-protected\n"
                    f"4. There was an error during file processing\n\n"
                    f"Please try uploading the file again, or use a different file format."
                )
            else:
                errorMsg = (
                    f"Could not extract content from {docType} document '{fileName}'. "
                    f"The file may be empty, corrupted, image-based (scanned PDF), or encrypted. "
                    f"Please ensure the file contains readable text content.\n\n"
                    f"Tip: If this is a scanned PDF, try using OCR software first."
                )
            return self._error(errorMsg)
        
        # Check if LLM tool is available
        if 'generate' not in self.tools:
            return self._error(get_error_message('connection', 'llm_unavailable'))
        
        # Build analysis prompt - automatically includes all required sections
        analysisPrompt = f"""Analyze this {docType} document ("{fileName}") comprehensively.

Document Content:
{docContent[:10000]}

Provide a detailed, formatted analysis with the following sections:

**Document Structure and Content Overview:**
- Document type and purpose
- Key sections and organization  
- Data structure (if applicable)

**Key Information and Data Points:**
- Important facts, figures, and data
- Key entities, assets, or items mentioned
- Critical information that stands out

**Important Findings or Patterns:**
- Patterns, trends, or anomalies
- Relationships between data points
- Compliance or security-related findings (if applicable)

**Summary and Recommendations:**
- Overall summary of the document
- Actionable recommendations
- ISMS relevance (if applicable - assets, risks, controls, compliance)

Format your response clearly with sections, bullet points, and proper markdown formatting.
Be specific and reference actual data from the document when possible."""
        
        try:
            # Use LLM to analyze
            response = self.executeTool('generate', prompt=analysisPrompt, systemPrompt=self.instructions)
            
            # Format response
            from presenters.text import TextPresenter
            presenter = TextPresenter()
            formatted = presenter.present({'content': response})
            
            return self._success(formatted.get('content', response))
        except Exception as e:
            errorMsg = str(e)
            # If LLM fails due to quota/rate limit, provide non-LLM analysis for Excel files
            if ('quota' in errorMsg.lower() or '429' in errorMsg or 'limit' in errorMsg.lower() or 
                'Both LLM providers failed' in errorMsg or 'rate limit' in errorMsg.lower() or 'service limit' in errorMsg.lower()):
                # Try non-LLM analysis using existing fallback method
                if docType in ['EXCEL', 'excel'] and 'sheets' in lastData:
                    return self._fallbackDocumentAnalysis(lastData, fileName, docType.lower(), docContent)
                # For other file types, provide helpful message
                return self._error(
                    "I've reached a service limit for advanced analysis. Please try again in a few moments.\n\n"
                    "However, you can still:\n"
                    "• Query specific data from the document (e.g., 'how many rows?', 'show column X')\n"
                    "• Import data as assets (type 'create assets' or 'import')\n"
                    "• List and manage ISMS objects\n\n"
                    "For Excel files, try asking specific questions like:\n"
                    "• 'How many rows are in this file?'\n"
                    "• 'What columns does this file have?'\n"
                    "• 'Show me the first 10 rows'"
                )
            return self._error(get_error_message('data', 'document_query_failed'))
    
    def _fallbackDocumentAnalysis(self, lastData: Dict, fileName: str, docType: str, docContent: Any) -> Dict:
        """Fallback document analysis without LLM - provides basic structure and statistics"""
        analysis = []
        analysis.append(f"## Document Analysis: {fileName}\n")
        analysis.append(f"**Document Type:** {docType.upper()}\n")
        
        # Excel analysis
        if docType == 'excel' and isinstance(lastData, dict):
            sheets = lastData.get('sheets', {})
            if sheets:
                analysis.append(f"**Sheets:** {len(sheets)}\n")
                for sheetName, sheetData in sheets.items():
                    if isinstance(sheetData, dict):
                        rows = sheetData.get('data', [])
                        if rows:
                            rowCount = len(rows)
                            if rowCount > 0:
                                colCount = len(rows[0]) if isinstance(rows[0], (list, dict)) else 0
                                analysis.append(f"\n### Sheet: {sheetName}")
                                analysis.append(f"- **Rows:** {rowCount}")
                                analysis.append(f"- **Columns:** {colCount}")
                                
                                # Show column names if available
                                if isinstance(rows[0], dict):
                                    columns = list(rows[0].keys())
                                    analysis.append(f"- **Column Names:** {', '.join(columns[:10])}")
                                    if len(columns) > 10:
                                        analysis.append(f"  (and {len(columns) - 10} more)")
                                elif isinstance(rows[0], list) and rowCount > 0:
                                    analysis.append(f"- **First Row Sample:** {', '.join(str(v)[:30] for v in rows[0][:5])}")
        
        # Word/PDF analysis
        elif docType in ['word', 'pdf']:
            if isinstance(docContent, str):
                wordCount = len(docContent.split())
                charCount = len(docContent)
                analysis.append("\n**Statistics:**")
                analysis.append(f"- **Words:** {wordCount:,}")
                analysis.append(f"- **Characters:** {charCount:,}")
                
                # Show first few paragraphs/sentences
                paragraphs = docContent.split('\n\n')[:3]
                if paragraphs:
                    analysis.append("\n**Preview:**")
                    for i, para in enumerate(paragraphs, 1):
                        preview = para[:200].strip()
                        if len(para) > 200:
                            preview += "..."
                        analysis.append(f"{i}. {preview}")
            elif isinstance(lastData, dict):
                if 'pages' in lastData:
                    pages = lastData.get('pages', [])
                    analysis.append(f"\n**Pages:** {len(pages)}")
                if 'paragraphs' in lastData:
                    paragraphs = lastData.get('paragraphs', [])
                    analysis.append(f"\n**Paragraphs:** {len(paragraphs)}")
        
        analysis.append("\n\n**Note:** Advanced AI analysis is temporarily unavailable due to service limits.")
        analysis.append("You can still query specific data using commands like:")
        analysis.append("- 'how many rows?'")
        analysis.append("- 'show column X'")
        analysis.append("- 'list columns'")
        
        result = "\n".join(analysis)
        from presenters.text import TextPresenter
        presenter = TextPresenter()
        formatted = presenter.present({'content': result})
        
        return self._success(formatted.get('content', result))
    
    # ==================== DOCUMENT QUERIES ====================
    
    def _checkDocumentQuery(self, message: str) -> Optional[Dict]:
        """Check if message is querying processed document (complex queries)"""
        messageLower = message.lower()
        docQueryKeywords = ['row', 'column', 'how many', 'count', 'show', 'get']
        
        # Skip if it's an analysis request (handled separately)
        if 'analyze' in messageLower:
            return None
        
        if any(keyword in messageLower for keyword in docQueryKeywords):
            # Use intelligent orchestrator if available
            if hasattr(self, '_intelligentOrchestrator') and self._intelligentOrchestrator:
                try:
                    lastData = self.state.get('lastProcessed')
                    if not lastData:
                        return self._error("No document has been processed yet. Please upload a file first.")
                    
                    # Ensure lastData is a dict
                    if not isinstance(lastData, dict):
                        return self._error(get_error_message('data', 'invalid_format'))
                    
                    docType = 'excel' if 'sheets' in lastData else ('word' if 'paragraphs' in lastData else 'pdf')
                    result = self._intelligentOrchestrator.understandAndExecute(
                        message,
                        documentData=lastData,
                        documentType=docType,
                        availableTools=list(self.tools.keys())
                    )
                    return result
                except Exception:
                    return self._error(get_error_message('data', 'document_query_failed'))
        
        return None
    
    # ==================== FORMATTING ====================
    
    def _formatVeriniceResult(self, toolName: str, result: dict):
        """Format Verinice results using presenter layer"""
        from presenters import TablePresenter
        
        if not isinstance(result, dict):
            return "No data returned."
        
        # List domains
        if 'domains' in result:
            domains = result.get('domains', [])
            count = len(domains)
            if count == 0:
                return "No domains found."
            
            presenter = TablePresenter()
            formatted = presenter.present({
                'items': domains,
                'columns': ['Name', 'Description'],
                'title': f"I found {count} domain(s)",
                'total': count
            })
            if isinstance(formatted, dict) and formatted.get('type') == 'text':
                return formatted.get('content', str(formatted))
            return formatted
        
        # List units
        if 'units' in result:
            units = result.get('units', [])
            count = len(units)
            if count == 0:
                return "No units found."
            
            presenter = TablePresenter()
            formatted = presenter.present({
                'items': units,
                'columns': ['Name', 'Description'],
                'title': f"I found {count} unit(s)",
                'total': count
            })
            if isinstance(formatted, dict) and formatted.get('type') == 'text':
                return formatted.get('content', str(formatted))
            return formatted
        
        # Object details (getVeriniceObject) - check BEFORE list/creation
        # This must come BEFORE checking for 'objects' to avoid confusion
        if toolName == 'getVeriniceObject' and result.get('success'):
            data = result.get('data')
            # Ensure data is a single object dict, not a list
            if isinstance(data, dict) and not isinstance(data, list):
                # Format object details - single object
                name = data.get('name', 'Unknown')
                description = data.get('description', '')
                objType = result.get('objectType', 'object')
                lines = [f"**{objType.capitalize()}: {name}**"]
                if description:
                    lines.append(f"Description: {description}")
                # Add other important fields
                for key in ['status', 'subType', 'createdAt', 'updatedAt', 'abbreviation', 'designator']:
                    if key in data and data[key]:
                        lines.append(f"{key.capitalize()}: {data[key]}")
                return "\n".join(lines)
            elif isinstance(data, list) and len(data) == 1:
                # Handle case where API returns a list with one item
                singleObj = data[0]
                if isinstance(singleObj, dict):
                    name = singleObj.get('name', 'Unknown')
                    description = singleObj.get('description', '')
                    objType = result.get('objectType', 'object')
                    lines = [f"**{objType.capitalize()}: {name}**"]
                    if description:
                        lines.append(f"Description: {description}")
                    for key in ['status', 'subType', 'createdAt', 'updatedAt', 'abbreviation', 'designator']:
                        if key in singleObj and singleObj[key]:
                            lines.append(f"{key.capitalize()}: {singleObj[key]}")
                    return "\n".join(lines)
        
        # List objects
        if 'objects' in result:
            objects = result.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            count = len(items)
            objectType = result.get('objectType', 'object')
            if count == 0:
                # Fix pluralization: "process" -> "processes", not "processs"
                if objectType == 'process':
                    return "No processes found."
                elif objectType.endswith('s'):
                    return f"No {objectType} found."
                else:
                    return f"No {objectType}s found."
            # Fix pluralization for title
            if objectType == 'process':
                objectTypePlural = 'processes'
            elif objectType.endswith('s'):
                objectTypePlural = objectType
            else:
                objectTypePlural = f"{objectType}s"
            
            # Determine columns based on object type
            # Essential columns (shown by default) and all columns (for expansion)
            if objectType == 'asset':
                # For assets: essential = Name, SubType; all = Name, SubType, Abbreviation, Description
                essential_columns = ['Name', 'SubType']
                all_columns = ['Name', 'SubType', 'Abbreviation', 'Description']
            elif objectType == 'scope':
                essential_columns = ['Name']
                all_columns = ['Name', 'Description']
            elif objectType == 'person':
                essential_columns = ['Name']
                all_columns = ['Name', 'Abbreviation', 'Description']
            else:
                essential_columns = ['Name']
                all_columns = ['Name', 'Description']
            
            presenter = TablePresenter()
            formatted = presenter.present({
                'items': items,
                'columns': all_columns,  # All available columns
                'essential_columns': essential_columns,  # Columns to show by default
                'use_essential_columns': True,  # Enable column prioritization
                'title': f"I found {count} {objectTypePlural}",
                'total': count,
                'objectType': objectType,
                'page': 1,  # Default to first page
                'page_size': 15  # Show 15 items per page when paginated
            })
            # TablePresenter now returns structured table data
            return formatted
        
        # Object creation
        if result.get('success') and 'objectId' in result and toolName == 'createVeriniceObject':
            objName = result.get('objectName', result.get('name', 'Object'))
            objType = result.get('objectType', 'object')
            return f"Created {objType} '{objName}'"
        
        # Object details (getVeriniceObject) - check AFTER creation
        if 'data' in result and result.get('success') and toolName == 'getVeriniceObject':
            data = result.get('data', {})
            if isinstance(data, dict):
                # Format object details
                name = data.get('name', 'Unknown')
                description = data.get('description', '')
                objType = result.get('objectType', 'object')
                lines = [f"**{objType.capitalize()}: {name}**"]
                if description:
                    lines.append(f"Description: {description}")
                # Add other important fields
                for key in ['status', 'subType', 'createdAt', 'updatedAt']:
                    if key in data and data[key]:
                        lines.append(f"{key.capitalize()}: {data[key]}")
                return "\n".join(lines)
        
        # Success
        if result.get('success'):
            return result.get('message', 'Operation completed successfully')
        
        # Error
        if result.get('success') is False:
            return f"Error: {result.get('error', 'Unknown error')}"
        
        return "No data to display."
    
    # ==================== HELPERS ====================
    
    def _parseSubtypeSelection(self, message: str, availableSubTypes: List[str]) -> Optional[str]:
        """Parse subtype selection - delegates to helper function"""
        return parseSubtypeSelection(message, availableSubTypes)
    
    def _checkGreeting(self, message: str) -> Optional[str]:
        """Check for greeting - delegates to helper function"""
        processedCount = self.state.get('processedCount', 0)
        return checkGreeting(message, processedCount)
    
    def _loadKnowledgeBase(self) -> Dict:
        """Load knowledge base from JSON file"""
        try:
            # knowledgeBase.json is in utils directory
            kbPath = Path(__file__).parent.parent / 'utils' / 'knowledgeBase.json'
            with open(kbPath, 'r') as f:
                return json.load(f)
        except Exception:
            # Fallback to empty knowledge base if file missing
            return {'topics': {}, 'how_to_create': {}}
    
    def _formatKnowledgeTopic(self, topic: str, data: Dict) -> str:
        """Format a knowledge topic from JSON into readable text"""
        lines = [f"**What is {topic.replace('_', ' ').title()}?**\n"]
        
        # Definition
        if 'definition' in data:
            lines.append("**Definition**")
            lines.append(f"  {data['definition']}\n")
        
        # Types (for assets)
        if 'types' in data:
            lines.append("**Types**")
            for t in data['types']:
                lines.append(f"  • {t}")
            lines.append("")
        
        # Context
        if 'context' in data:
            ctx = data['context']
            lines.append(f"**{ctx.get('title', 'Context')}**")
            for point in ctx.get('points', []):
                lines.append(f"  • {point}")
            lines.append("")
        
        # Elements (for ISMS)
        if 'elements' in data:
            elem = data['elements']
            lines.append(f"**{elem.get('title', 'Elements')}**")
            for point in elem.get('points', []):
                lines.append(f"  • {point}")
            lines.append("")
        
        # Benefits (for ISMS)
        if 'benefits' in data:
            ben = data['benefits']
            lines.append(f"**{ben.get('title', 'Benefits')}**")
            for point in ben.get('points', []):
                lines.append(f"  • {point}")
            lines.append("")
        
        # Examples
        if 'examples' in data:
            lines.append("**Examples**")
            for ex in data['examples']:
                lines.append(f"  • {ex}")
            lines.append("")
        
        # Relationship
        if 'relationship' in data:
            lines.append("**Relationship**")
            lines.append(f"  {data['relationship']}\n")
        
        # Commands
        if 'commands' in data:
            lines.append("**Commands**")
            for cmd in data['commands']:
                lines.append(f"  • `{cmd}`")
        
        return "\n".join(lines)
    
    def _formatComparison(self, data: Dict) -> str:
        """Format a comparison topic (e.g., scope vs asset)"""
        from presenters.text import TextPresenter
        presenter = TextPresenter()
        
        sections = {}
        if 'comparison' in data:
            sections.update(data['comparison'])
        if 'relationship' in data:
            sections['Relationship'] = data['relationship']
        if 'commands' in data:
            sections['Commands'] = data['commands']
        
            formatted = presenter.present({
            'title': 'Scope vs Asset in ISO 27001',
            'sections': sections
            })
            return formatted.get('content', str(formatted)) if isinstance(formatted, dict) else formatted
        
    def _formatHowToCreate(self, objectType: str, data: Dict) -> str:
        """Format 'how to create' instructions from JSON"""
        lines = [f"**How to Create {objectType.title()}**\n"]
        
        # If detailed steps exist
        if 'steps' in data:
            for step in data['steps']:
                lines.append(f"**{step['title']}**")
                lines.append(f"  {step['content']}\n")
        else:
            # Simple format (for smaller object types)
            if 'format' in data:
                lines.append("**Command Format**")
                lines.append(f"  `{data['format']}`\n")
            if 'example' in data:
                lines.append("**Example**")
                lines.append(f"  `{data['example']}`\n")
            if 'optional' in data:
                lines.append("**Optional Details**")
                lines.append(f"  {data['optional']}\n")
            if 'view' in data:
                lines.append("**View All**")
                lines.append(f"  `{data['view']}`\n")
        
        # Note
        if 'note' in data:
            lines.append("**Note**")
            lines.append(f"  {data['note']}")
        
        return "\n".join(lines)
    
    def _getFallbackAnswer(self, message: str) -> Optional[str]:
        """Provide fallback answers for common knowledge questions using JSON knowledge base"""
        messageLower = message.lower().strip()
        topics = self._knowledgeBase.get('topics', {})
        howToCreate = self._knowledgeBase.get('how_to_create', {})
        
        # 1. Scope vs Asset comparison (most specific)
        if 'scope' in messageLower and 'asset' in messageLower and ('difference' in messageLower or 'vs' in messageLower or 'versus' in messageLower):
            if 'scope_vs_asset' in topics:
                return self._formatComparison(topics['scope_vs_asset'])
        
        # 2. "What is X?" questions - check specific before general
        if any(q in messageLower for q in KNOWLEDGE_WHAT_PATTERNS):
            # Asset (check before ISMS to avoid conflicts)
            if 'asset' in messageLower and 'scope' not in messageLower and 'asset' in topics:
                return self._formatKnowledgeTopic('asset', topics['asset'])
            
            # Scope (exclude if asset mentioned)
            if 'scope' in messageLower and 'asset' not in messageLower and 'scope' in topics:
                return self._formatKnowledgeTopic('scope', topics['scope'])
            
            # ISMS (general - check last, exclude if asset/scope mentioned)
            if 'isms' in messageLower and 'asset' not in messageLower and 'scope' not in messageLower and 'isms' in topics:
                return self._formatKnowledgeTopic('isms', topics['isms'])
        
        # 3. "How to create X?" questions - dynamic for all object types
        if any(pattern in messageLower for pattern in KNOWLEDGE_HOW_TO_CREATE_PATTERNS) and 'create' in messageLower:
            for objType in VERINICE_OBJECT_TYPES:
                if objType in messageLower and objType in howToCreate:
                    return self._formatHowToCreate(objType, howToCreate[objType])
        
        return None
    
    def _handleBulkAssetImport(self, message: str) -> Optional[Dict]:
        """Handle bulk asset import from Excel"""
        # Check if user confirmed bulk import - be more specific to avoid false positives
        messageLower = message.lower().strip()
        
        # FIRST: Check if this is a single asset creation (has explicit name) vs bulk import
        # Pattern: "create asset [Name] [ABBR] [Description]" indicates single creation
        import re
        # Match "create asset" followed by at least one word (the asset name)
        # Use word boundary to capture the first word after "create asset"
        singleAssetPattern = r'create\s+asset\s+(\w+)'
        singleAssetMatch = re.search(singleAssetPattern, messageLower)
        
        # If message has explicit asset name after "create asset", it's single creation, not bulk
        if singleAssetMatch:
            assetName = singleAssetMatch.group(1).strip()
            # If name is a bulk keyword, don't treat as single creation
            if assetName in ['asset', 'assets', 'all', 'the']:
                # This might be bulk import, continue to bulk trigger check
                pass
            # If name is substantial and not a bulk keyword, it's single creation
            elif (len(assetName) > 2 and 
                  'import' not in assetName and 'bulk' not in assetName):
                return None  # This is single creation, not bulk import - let _detectVeriniceOp handle it
        
        # Check if we're in pending file action state
        pendingAction = self.state.get('pendingFileAction')
        if pendingAction and pendingAction.get('fileType') == 'excel':
            # User is responding to file upload prompt
            # For 2 files: i=compare, ii=create assets, iii=analyze, iv=custom
            # For 1 file: i=create assets, ii=analyze, iii=custom
            
            # Check for option ii (create assets when multiple files)
            if (messageLower in ['ii', '2', 'two'] or 
                any(phrase in messageLower for phrase in ['create assets', 'create all assets', 'import assets'])):
                # User wants to create assets (bulk)
                # DEBUG: User selected "ii" - proceeding to bulk import
                pass  # Continue to bulk import logic below
            # Check for option i (could be create assets or compare, depending on context)
            elif (messageLower in ['i', '1', 'one']):
                # Check how many files we have
                sessionContext = self.state.get('_sessionContext', {})
                activeSources = sessionContext.get('activeSources', [])
                excelCount = sum(1 for s in activeSources if s.get('type') == 'excel' or s.get('data', {}).get('fileType') == 'excel')
                
                if excelCount >= 2:
                    # Multiple files - 'i' means compare, not bulk import
                    return None  # Let comparison handler deal with it
                else:
                    # Single file - 'i' means create assets
                    pass  # Continue to bulk import logic below
            elif (messageLower in ['iii', '3', 'three'] or 
                  any(phrase in messageLower for phrase in ['analyze', 'analysis'])):
                # User wants to analyze - handle this in document analysis
                return None  # Let document analysis handle it
            elif messageLower in ['iv', '4', 'four']:
                # User wants to tell us what to do
                return self._success("What would you like me to do with this file? Please describe your request.")
            else:
                # Try to understand the intent
                # Check for explicit bulk keywords
                if any(phrase in messageLower for phrase in ['import', 'bulk', 'create assets', 'create all']):
                    # Likely wants to create assets (bulk)
                    pass  # Continue to bulk import logic
                else:
                    # Not a clear bulk import request
                    return None
        else:
            # No pending file action - check if this is still a bulk trigger
            # (User might type "create assets" without file upload prompt)
            pass  # Continue to check bulk triggers below
        
        # Specific bulk import triggers (only for actual bulk operations)
        # Note: "create asset" (singular) removed - only triggers if plural or bulk keywords
        bulkTriggers = BULK_IMPORT_TRIGGERS
        
        # Check if message contains any bulk trigger (as whole words/phrases)
        isBulkRequest = False
        for trigger in bulkTriggers:
            if trigger in messageLower:
                # Make sure it's not part of another word (e.g., "analyze" shouldn't trigger)
                # Check if it's at word boundaries or standalone
                pattern = r'\b' + re.escape(trigger) + r'\b'
                if re.search(pattern, messageLower):
                    isBulkRequest = True
                    break
        
        if not isBulkRequest:
            return None  # Not a bulk import request
        
        # Ensure Excel handler is initialized
        self._ensureExcelHandler()
        
        # Get Excel data and filePath
        excelData = self.state.get('lastProcessed')
        filePath = excelData.get('filePath') if excelData else None
        if not filePath:
            pendingAction = self.state.get('pendingFileAction')
            if pendingAction:
                filePath = pendingAction.get('filePath')
        
        # Delegate to Excel handler
        return self._excelHandler.handleBulkAssetImport(
            excelData or {},
            filePath,
            self.state,
            self.tools,
            self.executeTool,
            self._error,
            self._success
        )
    
    def _formatTextResponse(self, text: str) -> str:
        """Format text responses - delegates to helper function"""
        return formatTextResponse(text)
    
    def _success(self, result: Any) -> Dict:
        """Success response - delegates to helper function"""
        return successResponse(result)
    
    def _error(self, message: str) -> Dict:
        """Error response - delegates to helper function"""
        return errorResponse(message)
    
    # ==================== PHASE 3: SHADOW TESTING ====================
    
    def _ensureChatRouter(self):
        """Initialize ChatRouter if not already initialized (Phase 3)"""
        if not self._chatRouter:
            from orchestrator.chatRouter import ChatRouter
            from .instructions import VERINICE_OBJECT_TYPES
            self._chatRouter = ChatRouter(VERINICE_OBJECT_TYPES)
    
    def _shadowTestNewRouter(self, message: str) -> Optional[Dict]:
        """
        Run new ChatRouter in shadow mode (doesn't affect execution)
        
        This allows us to compare old vs new routing decisions without
        affecting live users. Logs are written for later analysis.
        """
        try:
            # Initialize router if needed
            self._ensureChatRouter()
            
            # Build context for router
            sessionContext = self.state.get('_sessionContext', {})
            if sessionContext and isinstance(sessionContext, dict):
                context = sessionContext.copy()
            else:
                context = {
                    'hasProcessedDocument': bool(self.state.get('lastProcessed')),
                    'documentCount': 1 if self.state.get('lastProcessed') else 0,
                    'excelFileCount': 0,
                    'pendingFileAction': self.state.get('pendingFileAction'),
                    'conversationHistory': self.conversationHistory[-3:] if self.conversationHistory else [],
                    'activeSources': []
                }
                if hasattr(self, 'processedFiles'):
                    context['excelFileCount'] = sum(1 for f in self.processedFiles if f.endswith(('.xlsx', '.xls')))
            
            # Initialize IntentClassifier if needed
            if not hasattr(self, '_intentClassifier') or not self._intentClassifier:
                try:
                    from orchestrator.intentClassifier import IntentClassifier
                    llmTool = getattr(self, '_llmTool', None)
                    if llmTool:
                        self._intentClassifier = IntentClassifier(llmTool)
                except Exception:
                    self._intentClassifier = None
            
            # Route using new router (pass state by reference)
            intentClassifier = getattr(self, '_intentClassifier', None)
            decision = self._chatRouter.route(message, self.state, context, intentClassifier)
            return decision
        except Exception as e:
            # If new router fails, log error but don't break execution
            self._routingLog.append({
                'message': message,
                'newRouter': 'ERROR',
                'error': str(e)
            })
            return None
    
    def _logRoutingComparison(self, message: str, oldRoute: str, newDecision: Dict, oldResult: Dict):
        """
        Log routing decision comparison for analysis
        
        Args:
            message: User message
            oldRoute: Old routing decision (string identifier)
            newDecision: New router decision dict
            oldResult: Result from old routing
        """
        logEntry = {
            'message': message[:100],  # Truncate long messages
            'oldRoute': oldRoute,
            'newRoute': newDecision.get('route'),
            'newHandler': newDecision.get('handler'),
            'newConfidence': newDecision.get('confidence'),
            'match': oldRoute == newDecision.get('route')
        }
        
        self._routingLog.append(logEntry)
        
        # Keep log size reasonable (last 100 entries)
        if len(self._routingLog) > 100:
            self._routingLog.pop(0)
    
    def _executeRoutingDecision(self, decision: Dict, message: str) -> Dict:
        """
        Execute a routing decision from ChatRouter
        
        This method maps router decisions to actual handler calls.
        Used when feature flag is enabled (active mode).
        """
        handler = decision.get('handler')
        data = decision.get('data', {})
        
        # Map handler names to actual methods
        if handler == '_handleVeriniceOp':
            return self._handleVeriniceOp(data, message)
        elif handler == '_handleReportGeneration':
            return self._handleReportGeneration(data, message)
        elif handler == '_handleReportGenerationFollowUp':
            return self._handleReportGenerationFollowUp(message)
        elif handler == '_handleSubtypeFollowUp':
            return self._handleSubtypeFollowUp(message)
        elif handler == '_checkGreeting':
            greeting = self._checkGreeting(message)
            return self._success(greeting) if greeting else self._error("Error processing greeting")
        elif handler == '_analyzeDocumentWithLLM':
            return self._analyzeDocumentWithLLM(message)
        elif handler == '_checkDocumentQuery':
            result = self._checkDocumentQuery(message)
            return result if result else self._error("Could not process document query")
        elif handler == '_handleBulkAssetImport':
            result = self._handleBulkAssetImport(message)
            return result if result else self._error("Could not process bulk import")
        elif handler == '_handleExcelComparison':
            sessionContext = self.state.get('_sessionContext', {})
            context = sessionContext if sessionContext else {}
            result = self._handleExcelComparison(message, context)
            return result if result else self._error("Could not process Excel comparison")
        elif handler == '_getFallbackAnswer':
            answer = self._getFallbackAnswer(message)
            return self._success(answer) if answer else self._error("No fallback answer available")
        elif handler == 'llm_generate':
            # Use LLM for general chat
            if 'generate' in self.tools:
                try:
                    response = self.executeTool('generate', prompt=message, systemPrompt=self.instructions)
                    formattedResponse = self._formatTextResponse(response)
                    return self._success(formattedResponse)
                except Exception:
                    return self._success("I can help with documents and ISMS operations. Try: 'list scopes' or upload a file.\n\nFor knowledge questions, please check your LLM API configuration.")
            return self._success("I can help with documents and ISMS operations. Try: 'list scopes' or upload a file.")
        else:
            # Unknown handler - fallback
            return self._success("I can help with documents and ISMS operations. Try: 'list scopes' or upload a file.")
    
    def getRoutingLog(self) -> List[Dict]:
        """Get routing comparison log (for debugging and validation)"""
        return self._routingLog.copy()
    
    def clearRoutingLog(self):
        """Clear routing log"""
        self._routingLog = []
    
    def enableChatRouter(self):
        """Enable ChatRouter (switch from shadow to active mode)"""
        self._useChatRouter = True
    
    def disableChatRouter(self):
        """Disable ChatRouter (switch back to old routing)"""
        self._useChatRouter = False


