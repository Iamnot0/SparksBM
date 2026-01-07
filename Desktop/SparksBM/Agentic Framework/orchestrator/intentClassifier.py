"""Intelligent Intent Classifier - uses LLM to understand user intent instead of pattern matching"""
from typing import Dict, List, Any, Optional, Tuple
import re
import json


class IntentClassifier:
    """Classifies user intents intelligently using LLM with pattern fallback"""
    
    def __init__(self, llmTool=None):
        """
        Args:
            llmTool: LLM tool for intelligent classification (optional)
        """
        self.llmTool = llmTool
        self.cache = {}  # Cache classifications
        self.confidence_threshold = 0.7  # Minimum confidence for LLM classification
    
    def classify(self, query: str, context: Optional[Dict] = None, 
                 intentTypes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Classify user query intent
        
        Args:
            query: User query
            context: Optional context (processed documents, conversation history, etc.)
            intentTypes: List of possible intent types to consider
            
        Returns:
            Dict with 'intent', 'confidence', 'entities', 'reasoning'
        """
        queryLower = query.lower().strip()
        
        # Check cache
        cacheKey = f"{queryLower}_{hash(str(context))}"
        if cacheKey in self.cache:
            return self.cache[cacheKey]
        
        # Use LLM for classification (primary method)
        if self.llmTool:
            try:
                result = self._llmBasedClassification(query, context, intentTypes)
                # Cache result
                self.cache[cacheKey] = result
                return result
            except Exception:
                # Only fallback to pattern if LLM completely fails
                pass
        
        # Fallback: pattern-based only when LLM unavailable
        result = self._patternBasedClassification(query, context, intentTypes)
        self.cache[cacheKey] = result
        return result
    
    def _patternBasedClassification(self, query: str, context: Optional[Dict], 
                                   intentTypes: Optional[List[str]]) -> Dict[str, Any]:
        """Fast pattern-based classification"""
        queryLower = query.lower()
        intent = 'unknown'
        confidence = 0.5
        entities = {}
        reasoning = "Pattern-based classification"
        
        # Document analysis intents
        if any(phrase in queryLower for phrase in ['what is', 'what\'s', 'tell me about', 'describe', 'explain', 
                                                   'analyze', 'summary', 'summarize', 'what does', 'what contains']):
            # Check if there's a processed document
            hasDoc = context and (context.get('hasProcessedDocument') or context.get('documentCount', 0) > 0)
            if hasDoc:
                intent = 'analyze_document'
                confidence = 0.9
                reasoning = "Question about uploaded document detected"
            else:
                intent = 'general_question'
                confidence = 0.6
        
        # Document query intents
        elif any(phrase in queryLower for phrase in ['how many rows', 'row count', 'count rows', 'number of rows']):
            intent = 'query_row_count'
            confidence = 0.9
        
        elif any(phrase in queryLower for phrase in ['show', 'get', 'extract', 'list']) and any(word in queryLower for word in ['column', 'col', 'username', 'email', 'name']):
            intent = 'query_column'
            confidence = 0.8
            # Extract column name
            columnMatch = re.search(r'(username|email|name|id|column|col)', queryLower)
            if columnMatch:
                entities['columnName'] = columnMatch.group(1)
        
        elif any(phrase in queryLower for phrase in ['what columns', 'list columns', 'show columns', 'column names']):
            intent = 'query_columns_list'
            confidence = 0.9
        
        # Excel comparison intent
        elif any(phrase in queryLower for phrase in ['compare', 'difference', 'diff', 'match', 'identify difference', 
                                                      'what\'s different', 'what is different', 'check difference']):
            # Check if there are multiple Excel files
            hasMultipleExcel = context and context.get('excelFileCount', 0) >= 2
            # Also check for "i" or "1" which might be user selecting comparison option
            isComparisonOption = queryLower.strip() in ['i', '1', 'compare', 'compare files', 'compare these files']
            if hasMultipleExcel or isComparisonOption or any(word in queryLower for word in ['excel', 'xls', 'file', 'files']):
                intent = 'compare_excel'
                confidence = 0.95 if (hasMultipleExcel or isComparisonOption) else 0.8
                reasoning = "Excel file comparison request detected"
        
        # Bulk import intent (when document is uploaded and user wants to create assets)
        elif any(word in queryLower for word in ['create asset', 'create assets', 'import', 'bulk import', 'bulk create']):
            hasDoc = context and (context.get('hasProcessedDocument') or context.get('documentCount', 0) > 0)
            if hasDoc:
                intent = 'bulk_import'
                confidence = 0.9
                reasoning = "User wants to create assets from uploaded document"
        
        # Verinice intents
        elif any(word in queryLower for word in ['create', 'new', 'add', 'make']) and not any(q in queryLower for q in ['what', 'how', 'why']):
            # Check if it's about uploaded document vs Verinice
            hasDoc = context and (context.get('hasProcessedDocument') or context.get('documentCount', 0) > 0)
            if hasDoc and any(q in queryLower for q in ['what', 'about', 'tell']):
                intent = 'analyze_document'
                confidence = 0.8
            else:
                intent = 'verinice_create'
                confidence = 0.7
        
        elif any(word in queryLower for word in ['list', 'show', 'display', 'get all']):
            intent = 'verinice_list'
            confidence = 0.7
        
        # File processing intents
        elif any(word in queryLower for word in ['process', 'read', 'load', 'upload', 'open']) and any(ext in queryLower for ext in ['.xlsx', '.xls', '.docx', '.doc', '.pdf']):
            intent = 'process_file'
            confidence = 0.9
        
        # Capability queries
        elif any(phrase in queryLower for phrase in ['what can', 'can you', 'show capabilities', 'help', 'what do you do']):
            intent = 'show_capabilities'
            confidence = 0.9
        
        return {
            'intent': intent,
            'confidence': confidence,
            'entities': entities,
            'reasoning': reasoning,
            'method': 'pattern'
        }
    
    def _llmBasedClassification(self, query: str, context: Optional[Dict], 
                               intentTypes: Optional[List[str]]) -> Dict[str, Any]:
        """LLM-powered intent classification"""
        if not self.llmTool:
            return {'intent': 'unknown', 'confidence': 0, 'method': 'llm_unavailable'}
        
        try:
            # Build context string
            contextStr = ""
            if context:
                if context.get('hasProcessedDocument'):
                    contextStr += "User has uploaded/processed documents.\n"
                if context.get('documentCount', 0) > 0:
                    contextStr += f"User has {context['documentCount']} processed document(s).\n"
                if context.get('conversationHistory'):
                    contextStr += f"Recent conversation: {str(context['conversationHistory'][-3:])}\n"
            
            # Build intent types list
            if not intentTypes:
                intentTypes = [
                    'analyze_document',  # Analyze uploaded document content
                    'query_document',    # Query document data (rows, columns, etc.)
                    'process_file',      # Process/upload a file
                    'bulk_import',       # Create assets from uploaded Excel file
                    'compare_excel',     # Compare two Excel files
                    'verinice_create',   # Create Verinice object
                    'verinice_list',     # List Verinice objects
                    'verinice_get',      # Get Verinice object details
                    'verinice_update',   # Update Verinice object
                    'verinice_delete',   # Delete Verinice object
                    'show_capabilities', # Show what agent can do
                    'general_question',  # General question/chat
                    'unknown'            # Unknown intent
                ]
            
            prompt = f"""Classify this user query into one of these intents: {', '.join(intentTypes)}

User Query: "{query}"

Context:
{contextStr if contextStr else 'No additional context'}

Important Rules:
1. If user asks "what is this document about?" or similar questions AND there's a processed document, classify as 'analyze_document' (NOT 'verinice_create')
2. If user asks about document data (rows, columns, etc.), classify as 'query_document'
3. If user explicitly says "create X", classify as 'verinice_create'
4. Questions starting with "what", "how", "why" are usually analysis/queries, NOT creation commands

Respond in JSON format:
{{
    "intent": "intent_name",
    "confidence": 0.0-1.0,
    "entities": {{"key": "value"}},
    "reasoning": "brief explanation"
}}

Intent Descriptions:
- analyze_document: User wants to understand/analyze uploaded document content
- query_document: User wants to query document data (rows, columns, filters)
- process_file: User wants to process/upload a file
- verinice_create: User wants to CREATE a Verinice object (explicit create command)
- verinice_list: User wants to list Verinice objects
- show_capabilities: User wants to know what the agent can do
- general_question: General question or chat
"""
            
            response = self.llmTool.generate(prompt, maxTokens=300)
            
            # Extract JSON from response
            jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if jsonMatch:
                result = json.loads(jsonMatch.group(0))
                result['method'] = 'llm'
                return result
            
            # Fallback: extract intent from text
            return self._extractIntentFromText(response, query)
            
        except Exception as e:
            # Fallback to pattern-based
            return self._patternBasedClassification(query, context, intentTypes)
    
    def _extractIntentFromText(self, text: str, query: str) -> Dict[str, Any]:
        """Extract intent from LLM text response"""
        textLower = text.lower()
        
        intent = 'unknown'
        confidence = 0.5
        
        if 'analyze_document' in textLower or 'analyze' in textLower:
            intent = 'analyze_document'
            confidence = 0.7
        elif 'query' in textLower:
            intent = 'query_document'
            confidence = 0.7
        elif 'create' in textLower:
            intent = 'verinice_create'
            confidence = 0.6
        elif 'list' in textLower:
            intent = 'verinice_list'
            confidence = 0.6
        
        return {
            'intent': intent,
            'confidence': confidence,
            'entities': {},
            'reasoning': f"Extracted from LLM response: {text[:100]}",
            'method': 'llm_fallback'
        }
    
    def isDocumentAnalysis(self, query: str, context: Optional[Dict] = None) -> bool:
        """Check if query is asking to analyze uploaded document"""
        classification = self.classify(query, context)
        return classification.get('intent') == 'analyze_document' and classification.get('confidence', 0) > 0.7
    
    def isDocumentQuery(self, query: str, context: Optional[Dict] = None) -> bool:
        """Check if query is asking to query document data"""
        classification = self.classify(query, context)
        return classification.get('intent') == 'query_document' and classification.get('confidence', 0) > 0.7
    
    def isVeriniceOperation(self, query: str, context: Optional[Dict] = None) -> bool:
        """Check if query is a Verinice operation"""
        classification = self.classify(query, context)
        intent = classification.get('intent', '')
        return intent.startswith('verinice_') and classification.get('confidence', 0) > 0.6
    
    def getIntent(self, query: str, context: Optional[Dict] = None) -> str:
        """Get intent name (shortcut method)"""
        return self.classify(query, context).get('intent', 'unknown')
    
    def clearCache(self):
        """Clear classification cache"""
        self.cache.clear()

