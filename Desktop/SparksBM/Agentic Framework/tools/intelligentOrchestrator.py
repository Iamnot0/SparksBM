"""Intelligent orchestrator - uses LLM to understand queries and execute tools automatically"""
from typing import Dict, Any, Optional, List
import json
import re


class IntelligentOrchestrator:
    """Uses LLM to understand user queries and automatically execute the right tools"""
    
    def __init__(self, llmTool, documentQueryTool):
        self.llmTool = llmTool
        self.documentQueryTool = documentQueryTool
        self.cache = {}
    
    def understandAndExecute(self, query: str, documentData: Optional[Dict] = None, 
                           documentType: Optional[str] = None, availableTools: List[str] = None) -> Dict[str, Any]:
        """
        Understand user query using LLM and execute appropriate tools
        
        Args:
            query: User's query
            documentData: Processed document data (if available)
            documentType: Type of document ('excel', 'word', 'pdf')
            availableTools: List of available tool names
            
        Returns:
            Dict with 'action', 'tool', 'params', 'result'
        """
        # Build context for LLM
        context = self._buildContext(documentData, documentType, availableTools)
        
        # Use LLM to understand intent
        understanding = self._understandWithLLM(query, context)
        
        # Execute based on understanding
        return self._executeBasedOnUnderstanding(understanding, query, documentData, documentType)
    
    def _buildContext(self, documentData: Optional[Dict], documentType: Optional[str], 
                     availableTools: Optional[List[str]]) -> str:
        """Build context string for LLM"""
        contextParts = []
        
        if documentData and documentType:
            summary = self.documentQueryTool.getDocumentSummary(documentData, documentType)
            contextParts.append(f"Document Type: {documentType}")
            contextParts.append(f"Document Summary: {json.dumps(summary, indent=2)}")
            
            if documentType == 'excel':
                columns = self.documentQueryTool.getColumns(documentData)
                if columns:
                    contextParts.append(f"Available Columns: {', '.join(columns)}")
        
        if availableTools:
            # Filter out LLM tools (internal only)
            visibleTools = [t for t in availableTools if t not in ['generate', 'analyze', 'extractEntities']]
            contextParts.append(f"Available Tools: {', '.join(visibleTools[:10])}")
        
        return "\n".join(contextParts)
    
    def _understandWithLLM(self, query: str, context: str) -> Dict[str, Any]:
        """Use LLM to understand user query"""
        if not self.llmTool:
            raise RuntimeError("LLM tool required for query understanding. Please configure GEMINI_API_KEY.")
        
        prompt = f"""You are an intelligent assistant that understands user queries and determines what action to take.

User Query: "{query}"

Context:
{context}

Available Document Query Operations:
- getRowCount: Get number of rows in Excel
- getColumn: Extract a specific column (e.g., "username", "email")
- getColumns: List all column names
- getRows: Get rows from document
- filterRows: Filter rows by conditions
- searchInDocument: Search for text in Word/PDF
- getDocumentSummary: Get document structure summary

Determine:
1. What does the user want? (intent)
2. What tool/operation should be executed?
3. What parameters are needed?

Respond in JSON format:
{{
    "intent": "intent_description",
    "action": "tool_name",
    "params": {{"param1": "value1", "param2": "value2"}},
    "confidence": 0.0-1.0
}}

Examples:
- "how many rows?" → {{"intent": "count_rows", "action": "getRowCount", "params": {{}}, "confidence": 0.95}}
- "show usernames" → {{"intent": "extract_column", "action": "getColumn", "params": {{"columnName": "username"}}, "confidence": 0.9}}
- "show rows" → {{"intent": "get_rows", "action": "getRows", "params": {{}}, "confidence": 0.9}}
- "what columns are there?" → {{"intent": "list_columns", "action": "getColumns", "params": {{}}, "confidence": 0.95}}
"""
        
            response = self.llmTool.generate(prompt, maxTokens=300)
            
            # Extract JSON from response
            jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if jsonMatch:
                result = json.loads(jsonMatch.group(0))
                return result
            
        raise RuntimeError("Failed to extract query understanding from LLM response. Please try again.")
    
    def _executeBasedOnUnderstanding(self, understanding: Dict[str, Any], query: str,
                                    documentData: Optional[Dict], documentType: Optional[str]) -> Dict[str, Any]:
        """Execute tool based on LLM understanding"""
        action = understanding.get('action')
        params = understanding.get('params', {})
        
        if not documentData:
            return {
                'status': 'error',
                'result': "No document data available. Please upload and process a document first.",
                'type': 'error'
            }
        
        try:
            # Execute document query tools
            if action == 'getRowCount':
                result = self.documentQueryTool.getRowCount(documentData, params.get('sheetName'))
                return {
                    'status': 'success',
                    'result': f"📊 **Row Count:** {result} rows",
                    'type': 'tool_result',
                    'data': {'rowCount': result}
                }
            
            elif action == 'getColumn':
                columnName = params.get('columnName')
                if not columnName:
                    # Try to extract from query
                    columnName = self._extractColumnName(query)
                
                if columnName:
                    result = self.documentQueryTool.getColumn(documentData, columnName, params.get('sheetName'))
                    if result:
                        return {
                            'status': 'success',
                            'result': f"📋 **Column '{columnName}':**\n\n" + "\n".join([f"- {val}" for val in result[:20]]) + (f"\n\n... ({len(result) - 20} more)" if len(result) > 20 else ""),
                            'type': 'tool_result',
                            'data': {'column': columnName, 'values': result}
                        }
                    else:
                        return {
                            'status': 'error',
                            'result': f"Column '{columnName}' not found. Available columns: {', '.join(self.documentQueryTool.getColumns(documentData))}",
                            'type': 'error'
                        }
                else:
                    return {
                        'status': 'error',
                        'result': "I need to know which column to extract. Please specify, e.g., 'show username column' or 'get email column'.",
                        'type': 'error'
                    }
            
            elif action == 'getColumns':
                result = self.documentQueryTool.getColumns(documentData, params.get('sheetName'))
                return {
                    'status': 'success',
                    'result': f"📋 **Available Columns:**\n\n" + "\n".join([f"- {col}" for col in result]),
                    'type': 'tool_result',
                    'data': {'columns': result}
                }
            
            elif action == 'getRows':
                limit = params.get('limit', 20)  # Default limit
                result = self.documentQueryTool.getRows(documentData, limit, params.get('sheetName'))
                return {
                    'status': 'success',
                    'result': f"📊 **Rows (showing {len(result)}):**\n\n" + self._formatRows(result),
                    'type': 'tool_result',
                    'data': {'rows': result}
                }
            
            elif action == 'filterRows':
                conditions = params.get('conditions', {})
                result = self.documentQueryTool.filterRows(documentData, conditions, params.get('sheetName'))
                return {
                    'status': 'success',
                    'result': f"🔍 **Filtered Rows ({len(result)} found):**\n\n" + self._formatRows(result[:20]),
                    'type': 'tool_result',
                    'data': {'rows': result}
                }
            
            elif action == 'searchInDocument':
                searchQuery = params.get('query', query)
                result = self.documentQueryTool.searchInDocument(documentData, searchQuery, documentType or 'word')
                return {
                    'status': 'success',
                    'result': f"🔍 **Search Results ({len(result)} found):**\n\n" + self._formatSearchResults(result),
                    'type': 'tool_result',
                    'data': {'matches': result}
                }
            
            else:
                # Fallback: use LLM to generate response
                return {
                    'status': 'success',
                    'result': f"I understand you want: {understanding.get('intent')}. Let me help with that.",
                    'type': 'chat_response'
                }
        
        except Exception as e:
            return {
                'status': 'error',
                'result': f"Error executing query: {str(e)}",
                'type': 'error'
            }
    
    def _extractColumnName(self, query: str) -> Optional[str]:
        """Extract column name from query"""
        queryLower = query.lower()
        
        # Common column patterns
        columnPatterns = [
            r'(username|user name)',
            r'(email|e-mail)',
            r'(name|full name)',
            r'(id|identifier)',
            r'column\s+([a-z]+)',
            r'([a-z]+)\s+column'
        ]
        
        for pattern in columnPatterns:
            match = re.search(pattern, queryLower)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        
        return None
    
    def _formatRows(self, rows: List[Dict]) -> str:
        """Format rows for display"""
        if not rows:
            return "No rows found."
        
        formatted = []
        for i, row in enumerate(rows[:10], 1):
            rowStr = ", ".join([f"{k}: {v}" for k, v in list(row.items())[:5]])
            formatted.append(f"{i}. {rowStr}")
        
        if len(rows) > 10:
            formatted.append(f"\n... ({len(rows) - 10} more rows)")
        
        return "\n".join(formatted)
    
    def _formatSearchResults(self, results: List[Dict]) -> str:
        """Format search results for display"""
        if not results:
            return "No matches found."
        
        formatted = []
        for i, result in enumerate(results[:5], 1):
            formatted.append(f"{i}. {result.get('type', 'match')}: {result.get('context', '')[:100]}...")
        
        if len(results) > 5:
            formatted.append(f"\n... ({len(results) - 5} more matches)")
        
        return "\n".join(formatted)

