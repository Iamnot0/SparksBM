"""Advanced query planner - understands complex queries and creates execution plans"""
from typing import Dict, List, Any, Optional
import re
import json


class QueryPlanner:
    """Plans execution of complex queries"""
    
    def __init__(self, llmTool=None):
        """
        Args:
            llmTool: LLM tool for understanding complex queries
        """
        self.llmTool = llmTool
        self.cache = {}
    
    def plan(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create execution plan for a query
        
        Args:
            query: User query
            context: Current context (documents, available tools, etc.)
            
        Returns:
            Execution plan with steps
        """
        queryLower = query.lower()
        
        # Check cache
        cacheKey = f"{queryLower}_{hash(str(context))}"
        if cacheKey in self.cache:
            return self.cache[cacheKey]
        
        # Try pattern-based planning first
        plan = self._patternBasedPlan(query, context)
        
        # If pattern-based has low confidence, use LLM
        if plan.get('confidence', 0) < 0.7 and self.llmTool:
            llmPlan = self._llmBasedPlan(query, context)
            if llmPlan.get('confidence', 0) > plan.get('confidence', 0):
                plan = llmPlan
        
        # Validate plan
        validatedPlan = self._validatePlan(plan, context)
        
        # Cache result
        self.cache[cacheKey] = validatedPlan
        
        return validatedPlan
    
    def _patternBasedPlan(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create plan using pattern matching"""
        queryLower = query.lower()
        
        # Simple queries (single tool)
        if any(phrase in queryLower for phrase in ['how many rows', 'row count', 'count rows']):
            return {
                'type': 'single',
                'steps': [{
                    'tool': 'getRowCount',
                    'params': self._extractParams(query, context)
                }],
                'confidence': 0.9
            }
        
        # Column extraction
        if any(word in queryLower for word in ['show', 'get', 'extract', 'list']):
            columnName = self._extractColumnName(query)
            if columnName:
                return {
                    'type': 'single',
                    'steps': [{
                        'tool': 'getColumn',
                        'params': {'columnName': columnName, **self._extractParams(query, context)}
                    }],
                    'confidence': 0.8
                }
        
        # Multi-step queries
        if any(word in queryLower for word in ['then', 'and', 'after', 'next']):
            return self._planMultiStep(query, context)
        
        # Comparison queries
        if any(word in queryLower for word in ['compare', 'difference', 'same', 'different']):
            return self._planComparison(query, context)
        
        # Filter queries
        if any(word in queryLower for word in ['where', 'filter', 'find', 'search']):
            return self._planFilter(query, context)
        
        # Default: analyze with LLM
        return {
            'type': 'complex',
            'steps': [{
                'tool': 'analyze',
                'params': {'query': query, 'context': context}
            }],
            'confidence': 0.5,
            'requiresLLM': True
        }
    
    def _planMultiStep(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Plan multi-step query"""
        # Split by connectors
        parts = re.split(r'\s+(then|and|after|next)\s+', query.lower())
        
        steps = []
        for i, part in enumerate(parts):
            if part in ['then', 'and', 'after', 'next']:
                continue
            
            # Plan each part
            partPlan = self._patternBasedPlan(part, context)
            if partPlan.get('steps'):
                steps.extend(partPlan['steps'])
        
        return {
            'type': 'multi',
            'steps': steps,
            'confidence': 0.7
        }
    
    def _planComparison(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Plan comparison query"""
        # Extract document names or references
        docRefs = self._extractDocumentReferences(query, context)
        
        if len(docRefs) >= 2:
            steps = []
            for i, docRef in enumerate(docRefs[:2]):
                steps.append({
                    'tool': 'getDocumentSummary',
                    'params': {'documentId': docRef},
                    'storeAs': f'doc{i+1}'
                })
            
            # Add comparison step (would need a compare tool)
            steps.append({
                'tool': 'compareDocuments',
                'params': {
                    'doc1': '$doc1',
                    'doc2': '$doc2'
                }
            })
            
            return {
                'type': 'multi',
                'steps': steps,
                'confidence': 0.7
            }
        
        return {
            'type': 'complex',
            'steps': [{'tool': 'analyze', 'params': {'query': query}}],
            'confidence': 0.5
        }
    
    def _planFilter(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Plan filter query"""
        # Extract filter conditions
        conditions = self._extractFilterConditions(query)
        
        if conditions:
            return {
                'type': 'single',
                'steps': [{
                    'tool': 'filterRows',
                    'params': {
                        'conditions': conditions,
                        **self._extractParams(query, context)
                    }
                }],
                'confidence': 0.8
            }
        
        return {
            'type': 'complex',
            'steps': [{'tool': 'analyze', 'params': {'query': query}}],
            'confidence': 0.5
        }
    
    def _llmBasedPlan(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to create plan"""
        if not self.llmTool:
            return {'type': 'complex', 'steps': [], 'confidence': 0}
        
        prompt = f"""Analyze this query and create an execution plan.

Query: "{query}"

Context:
{json.dumps(context, indent=2)}

Available Tools: getRowCount, getColumn, getColumns, getRows, filterRows, searchInDocument

Create a JSON plan with:
{{
    "type": "single" | "multi",
    "steps": [
        {{
            "tool": "tool_name",
            "params": {{"param": "value"}},
            "storeAs": "variable_name" (optional)
        }}
    ],
    "confidence": 0.0-1.0
}}
"""
        
        try:
            response = self.llmTool.generate(prompt, maxTokens=500)
            
            # Extract JSON
            jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if jsonMatch:
                plan = json.loads(jsonMatch.group(0))
                plan['method'] = 'llm'
                return plan
        except Exception:
            pass
        
        return {'type': 'complex', 'steps': [], 'confidence': 0.3}
    
    def _extractParams(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract parameters from query"""
        params = {}
        
        # Extract sheet name if mentioned
        sheetMatch = re.search(r'sheet[:\s]+(\w+)', query, re.IGNORECASE)
        if sheetMatch:
            params['sheetName'] = sheetMatch.group(1)
        
        # Extract limit if mentioned
        limitMatch = re.search(r'(?:first|top|limit)[:\s]+(\d+)', query, re.IGNORECASE)
        if limitMatch:
            params['limit'] = int(limitMatch.group(1))
        
        return params
    
    def _extractColumnName(self, query: str) -> Optional[str]:
        """Extract column name from query"""
        # Common patterns
        patterns = [
            r'(?:column|col)[:\s]+(\w+)',
            r'(?:show|get|extract|list)[:\s]+(\w+)',
            r'(\w+)(?:\s+column|\s+col)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Try common column names
        commonColumns = ['username', 'email', 'name', 'id', 'user', 'email address']
        queryLower = query.lower()
        for col in commonColumns:
            if col in queryLower:
                return col
        
        return None
    
    def _extractFilterConditions(self, query: str) -> Dict[str, Any]:
        """Extract filter conditions from query"""
        conditions = {}
        
        # Pattern: "where column = value" or "where column contains value"
        whereMatch = re.search(r'where\s+(\w+)\s+(?:is|equals?|==|=|contains?)\s+([^\s]+)', query, re.IGNORECASE)
        if whereMatch:
            conditions[whereMatch.group(1)] = whereMatch.group(2)
        
        return conditions
    
    def _extractDocumentReferences(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Extract document references from query"""
        # This would match document names to IDs
        # For now, return empty
        return []
    
    def _validatePlan(self, plan: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate execution plan"""
        if not plan.get('steps'):
            plan['valid'] = False
            plan['error'] = 'No steps in plan'
            return plan
        
        # Check if tools are available
        availableTools = context.get('availableTools', [])
        
        for step in plan['steps']:
            toolName = step.get('tool')
            if toolName and toolName not in availableTools:
                plan['valid'] = False
                plan['error'] = f"Tool '{toolName}' not available"
                return plan
        
        plan['valid'] = True
        return plan

