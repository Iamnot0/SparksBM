"""
Chat Router - Extracts routing logic from MainAgent (Phase 3)

This module handles all chat message routing decisions:
- Follow-up detection (subtype selection, report generation)
- Greeting detection
- Verinice operation detection (ISMS commands)
- Report generation detection
- Intent classification (LLM-based fallback)
- Document operation routing
- Fallback routing

CRITICAL: This router MUST maintain the exact routing priority order:
1. Follow-ups (highest priority)
2. Greetings
3. Verinice operations (pattern-based)
4. Report generation (pattern-based)
5. Intent classifier (LLM-based)
6. Document operations
7. Fallback knowledge base
8. LLM general chat
9. Final fallback

State Management:
- Router receives state by REFERENCE (not copy)
- All state mutations are preserved
- Prevents Bug #3 regression (context loss)
"""

from typing import Dict, Optional, Any, List
import re


class ChatRouter:
    """Routes chat messages to appropriate handlers based on intent and context"""
    
    # Routing decision types (for logging and debugging)
    ROUTE_FOLLOW_UP = "follow_up"
    ROUTE_GREETING = "greeting"
    ROUTE_VERINICE = "verinice_operation"
    ROUTE_REPORT = "report_generation"
    ROUTE_INTENT_CLASSIFIER = "intent_classifier"
    ROUTE_DOCUMENT = "document_operation"
    ROUTE_FALLBACK_KB = "fallback_knowledge"
    ROUTE_LLM = "llm_chat"
    ROUTE_FINAL_FALLBACK = "final_fallback"
    
    def __init__(self, veriniceObjectTypes: List[str]):
        """
        Initialize ChatRouter
        
        Args:
            veriniceObjectTypes: List of valid Verinice object types for pattern matching
        """
        self.veriniceObjectTypes = veriniceObjectTypes
    
    def route(self, message: str, state: Dict, context: Dict, intentClassifier=None) -> Dict:
        """
        Route a chat message to the appropriate handler
        
        Args:
            message: User's chat message
            state: Agent state (passed by REFERENCE - mutations are preserved)
            context: Session context with document/file information
            intentClassifier: Optional IntentClassifier instance for LLM-based routing
        
        Returns:
            Dict with routing decision:
            {
                'route': str,  # Route type (ROUTE_* constants)
                'handler': str,  # Handler method name to call
                'data': dict,  # Handler-specific data (e.g., veriniceOp, reportGen)
                'confidence': float  # Confidence in routing decision (0-1)
            }
        """
        # Validate state (prevent Bug #3 regression)
        self._validateState(state)
        
        # 0. PRIORITY: Check for follow-up responses FIRST
        followUp = self._checkFollowUp(message, state)
        if followUp:
            return followUp
        
        # 1. Quick greeting check
        greeting = self._checkGreeting(message, state)
        if greeting:
            return greeting
        
        # 2. CRITICAL: Check for Verinice operations FIRST (before IntentClassifier)
        veriniceOp = self._detectVeriniceOp(message)
        if veriniceOp:
            return {
                'route': self.ROUTE_VERINICE,
                'handler': '_handleVeriniceOp',
                'data': veriniceOp,
                'confidence': 0.95
            }
        
        # 3. Check for report generation
        reportGen = self._detectReportGeneration(message)
        if reportGen:
            return {
                'route': self.ROUTE_REPORT,
                'handler': '_handleReportGeneration',
                'data': reportGen,
                'confidence': 0.9
            }
        
        # 4. Use IntentClassifier (LLM-based) if available
        if intentClassifier:
            intentRoute = self._useIntentClassifier(message, context, intentClassifier)
            if intentRoute:
                return intentRoute
        
        # 5. Fallback: Check for document operations if document exists
        if context.get('hasProcessedDocument'):
            # IMPORTANT: Re-check for Verinice operations FIRST
            veriniceOp = self._detectVeriniceOp(message)
            if veriniceOp:
                return {
                    'route': self.ROUTE_VERINICE,
                    'handler': '_handleVeriniceOp',
                    'data': veriniceOp,
                    'confidence': 0.95
                }
            
            # Check for bulk import
            if self._isBulkImport(message, state):
                return {
                    'route': self.ROUTE_DOCUMENT,
                    'handler': '_handleBulkAssetImport',
                    'data': {},
                    'confidence': 0.8
                }
            
            # Check for document analysis
            if self._isDocumentAnalysis(message, intentClassifier, context):
                return {
                    'route': self.ROUTE_DOCUMENT,
                    'handler': '_analyzeDocumentWithLLM',
                    'data': {},
                    'confidence': 0.85
                }
            
            # Check for document queries
            if self._isDocumentQuery(message):
                return {
                    'route': self.ROUTE_DOCUMENT,
                    'handler': '_checkDocumentQuery',
                    'data': {},
                    'confidence': 0.75
                }
        
        # 6. Check fallback knowledge base
        if self._hasFallbackAnswer(message):
            return {
                'route': self.ROUTE_FALLBACK_KB,
                'handler': '_getFallbackAnswer',
                'data': {},
                'confidence': 0.7
            }
        
        # 7. Route to LLM for general chat
        return {
            'route': self.ROUTE_LLM,
            'handler': 'llm_generate',
            'data': {},
            'confidence': 0.5
        }
    
    # ==================== STATE VALIDATION ====================
    
    def _validateState(self, state: Dict) -> None:
        """
        Validate that state has required structure
        
        Prevents Bug #3 regression by ensuring state is passed by reference
        and has necessary keys for routing decisions
        """
        if not isinstance(state, dict):
            raise ValueError(f"State must be a dict, got {type(state)}")
        
        # State should have these keys (create if missing)
        if '_sessionContext' not in state:
            state['_sessionContext'] = {}
        if 'lastProcessed' not in state:
            state['lastProcessed'] = None
    
    # ==================== FOLLOW-UP DETECTION ====================
    
    def _checkFollowUp(self, message: str, state: Dict) -> Optional[Dict]:
        """Check for follow-up responses (subtype selection, report generation)"""
        # Report generation follow-up
        if state.get('pendingReportGeneration'):
            return {
                'route': self.ROUTE_FOLLOW_UP,
                'handler': '_handleReportGenerationFollowUp',
                'data': {},
                'confidence': 1.0
            }
        
        # Subtype selection follow-up
        pending = state.get('_pendingSubtypeSelection')
        if pending:
            return {
                'route': self.ROUTE_FOLLOW_UP,
                'handler': '_handleSubtypeFollowUp',
                'data': {},
                'confidence': 1.0
            }
        
        return None
    
    # ==================== GREETING DETECTION ====================
    
    def _checkGreeting(self, message: str, state: Dict) -> Optional[Dict]:
        """Check if message is a greeting"""
        messageLower = message.lower().strip()
        greetings = ['hi', 'hello', 'hey', 'greetings', 'good morning', 
                    'good afternoon', 'good evening']
        
        # Only treat as greeting if message is ONLY greeting (no other words)
        if messageLower in greetings:
            return {
                'route': self.ROUTE_GREETING,
                'handler': '_checkGreeting',
                'data': {},
                'confidence': 1.0
            }
        
        return None
    
    # ==================== VERINICE OPERATION DETECTION ====================
    
    def _detectVeriniceOp(self, message: str) -> Optional[Dict]:
        """Detect Verinice operation from message - ignore questions"""
        try:
            messageLower = message.lower().strip()
            
            # Skip questions - these should go to LLM for knowledge answers
            questionStarters = ['how do', 'how can', 'how to', 'what is', 'what are', 'what does', 
                               'what should', 'why', 'explain', 'tell me about', 'describe']
            if any(messageLower.startswith(starter) for starter in questionStarters):
                return None
        
            # Normalize typos - only replace whole words to avoid substring issues
            typoMap = {
                'creat': 'create', 'crate': 'create',
                'assest': 'asset', 'assests': 'assets',
                'scop': 'scope', 'scops': 'scopes',
                'persn': 'person', 'persns': 'persons'
            }
            for typo, correct in typoMap.items():
                # Use word boundaries to only replace whole words, not substrings
                pattern = r'\b' + re.escape(typo) + r'\b'
                messageLower = re.sub(pattern, correct, messageLower)
            
            # Extract object type
            objectType = None
            # Sort to check plurals first (longer strings first)
            sortedTypes = sorted(self.veriniceObjectTypes, key=len, reverse=True)
            for objType in sortedTypes:
                # Use word boundary matching to avoid substring issues
                pattern = r'\b' + re.escape(objType) + r'\b'
                if re.search(pattern, messageLower):
                    # Convert to singular
                    if objType.endswith("es"):
                        if objType == "processes":
                            objectType = "process"
                        elif objType == "scopes":
                            objectType = "scope"
                        else:
                            objectType = objType[:-2]
                    elif objType.endswith("s") and objType != "process":
                        objectType = objType[:-1]
                    else:
                        objectType = objType
                    break
            
            if not objectType:
                return None
        
            # Detect operation - only for direct commands, not questions
            if any(word in messageLower for word in ['create', 'new', 'add', 'make']) and not any(q in messageLower for q in ['how', 'what', 'why']):
                return {'operation': 'create', 'objectType': objectType}
            elif any(word in messageLower for word in ['list', 'show', 'display']) and not any(q in messageLower for q in ['how', 'what', 'why']):
                return {'operation': 'list', 'objectType': objectType}
            elif any(word in messageLower for word in ['get', 'view']) and not any(q in messageLower for q in ['how', 'what', 'why']):
                return {'operation': 'get', 'objectType': objectType}
            elif any(word in messageLower for word in ['delete', 'remove']):
                return {'operation': 'delete', 'objectType': objectType}
            elif any(word in messageLower for word in ['update', 'edit', 'modify']):
                return {'operation': 'update', 'objectType': objectType}
            elif 'analyze' in messageLower:
                return {'operation': 'analyze', 'objectType': objectType}
            
            return None
        except Exception:
            return None
    
    # ==================== REPORT GENERATION DETECTION ====================
    
    def _detectReportGeneration(self, message: str) -> Optional[Dict]:
        """Detect report generation requests"""
        messageLower = message.lower().strip()
        
        # Check for report generation keywords
        reportKeywords = ['generate', 'create', 'make', 'get']
        reportTypes = ['inventory of assets', 'risk assessment', 'statement of applicability', 
                      'inventory', 'risk', 'statement']
        
        hasReportKeyword = any(keyword in messageLower for keyword in reportKeywords)
        hasReportType = any(reportType in messageLower for reportType in reportTypes)
        
        # Also check for generic "report" (but only if it's not too ambiguous)
        hasGenericReport = 'report' in messageLower and not any(q in messageLower for q in ['what', 'how', 'why', 'which'])
        
        if hasReportKeyword and (hasReportType or hasGenericReport):
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
            elif hasGenericReport:
                # Generic "generate report" - default to inventory
                reportType = 'inventory-of-assets'
            
            if reportType:
                return {'operation': 'generate_report', 'reportType': reportType}
        
        return None
    
    # ==================== INTENT CLASSIFIER ====================
    
    def _useIntentClassifier(self, message: str, context: Dict, intentClassifier) -> Optional[Dict]:
        """Use IntentClassifier (LLM-based) for routing"""
        try:
            classification = intentClassifier.classify(message, context)
            intent = classification.get('intent', 'unknown')
            confidence = classification.get('confidence', 0)
            
            # Only use if confident enough
            if confidence >= 0.6:
                # Map intent to handler
                if intent in ['verinice_create', 'verinice_list', 'verinice_get', 
                             'verinice_update', 'verinice_delete']:
                    # Re-detect to get operation details
                    veriniceOp = self._detectVeriniceOp(message)
                    if veriniceOp:
                        return {
                            'route': self.ROUTE_INTENT_CLASSIFIER,
                            'handler': '_handleVeriniceOp',
                            'data': veriniceOp,
                            'confidence': confidence
                        }
                
                elif intent == 'analyze_document' and context.get('hasProcessedDocument'):
                    return {
                        'route': self.ROUTE_INTENT_CLASSIFIER,
                        'handler': '_analyzeDocumentWithLLM',
                        'data': {},
                        'confidence': confidence
                    }
                
                elif intent == 'query_document' and context.get('hasProcessedDocument'):
                    return {
                        'route': self.ROUTE_INTENT_CLASSIFIER,
                        'handler': '_checkDocumentQuery',
                        'data': {},
                        'confidence': confidence
                    }
                
                elif intent == 'compare_excel':
                    return {
                        'route': self.ROUTE_INTENT_CLASSIFIER,
                        'handler': '_handleExcelComparison',
                        'data': {},
                        'confidence': confidence
                    }
                
                elif intent in ['process_file', 'bulk_import'] and context.get('hasProcessedDocument'):
                    return {
                        'route': self.ROUTE_INTENT_CLASSIFIER,
                        'handler': '_handleBulkAssetImport',
                        'data': {},
                        'confidence': confidence
                    }
        except Exception:
            pass
        
        return None
    
    # ==================== DOCUMENT OPERATIONS ====================
    
    def _isBulkImport(self, message: str, state: Dict) -> bool:
        """Check if message is requesting bulk asset import"""
        messageLower = message.lower().strip()
        
        # Check single asset pattern first
        import re
        singleAssetPattern = r'create\s+asset\s+(\w+)'
        singleAssetMatch = re.search(singleAssetPattern, messageLower)
        
        if singleAssetMatch:
            assetName = singleAssetMatch.group(1).strip()
            if assetName not in ['asset', 'assets', 'all', 'the']:
                if len(assetName) > 2 and 'import' not in assetName and 'bulk' not in assetName:
                    return False
        
        # Check pending file action
        pendingAction = state.get('pendingFileAction')
        if pendingAction and pendingAction.get('fileType') == 'excel':
            if (messageLower in ['i', '1', 'one'] or 
                any(phrase in messageLower for phrase in ['import', 'bulk', 'yes', 'y', 'create assets', 'create asset all'])):
                return True
        
        # Bulk triggers
        bulkTriggers = [
            'yes', 'y', 'i', '1',
            'import all', 'import assets', 'import the assets', 'import',
            'create all', 'create all assets', 'create assets',
            'create asset all',
            'bulk', 'bulk import', 'bulk create'
        ]
        
        for trigger in bulkTriggers:
            if trigger in messageLower:
                pattern = r'\b' + re.escape(trigger) + r'\b'
                if re.search(pattern, messageLower):
                    return True
        
        return False
    
    def _isDocumentAnalysis(self, message: str, intentClassifier, context: Dict) -> bool:
        """Check if message is a document analysis request"""
        # Use IntentClassifier if available
        if intentClassifier:
            try:
                classification = intentClassifier.classify(message, context=context)
                intent = classification.get('intent', '')
                confidence = classification.get('confidence', 0)
                
                if intent == 'analyze_document' and confidence >= 0.7:
                    return True
                
                if intent != 'analyze_document' and confidence >= 0.8:
                    return False
            except Exception:
                pass
        
        return False
    
    def _isDocumentQuery(self, message: str) -> bool:
        """Check if message is querying document"""
        messageLower = message.lower()
        docQueryKeywords = ['row', 'column', 'how many', 'count', 'show', 'get']
        
        if 'analyze' in messageLower:
            return False
        
        return any(keyword in messageLower for keyword in docQueryKeywords)
    
    # ==================== FALLBACK ====================
    
    def _hasFallbackAnswer(self, message: str) -> bool:
        """Check if message has a fallback knowledge base answer"""
        messageLower = message.lower().strip()
        
        # Check for knowledge questions
        knowledgePatterns = [
            ('scope' in messageLower and 'asset' in messageLower and 
             ('difference' in messageLower or 'vs' in messageLower)),
            ('asset' in messageLower and ('what' in messageLower or 'explain' in messageLower)),
            ('scope' in messageLower and ('what' in messageLower or 'explain' in messageLower)),
            ('isms' in messageLower and ('what' in messageLower or 'explain' in messageLower)),
            ('create' in messageLower and 'scope' in messageLower and 
             ('how' in messageLower or 'do i' in messageLower))
        ]
        
        return any(knowledgePatterns)
