"""Word document handler - handles Word-specific operations"""
from typing import Dict, List, Any
import re
import json


class WordDocHandler:
    """Handles Word document operations: formatting, entity extraction, and analysis using LLM"""
    
    def __init__(self, llmTool=None):
        self.llmTool = llmTool
    
    def formatForLLM(self, data: Dict) -> str:
        """Format Word data for LLM analysis - enhanced with tables"""
        content = []
        
        # Add text/paragraphs
        text = data.get('text', '')
        paragraphs = data.get('paragraphs', [])
        
        if text and isinstance(text, str) and text.strip():
            content.append("Document Text:")
            content.append("=" * 60)
            content.append(text[:5000])
        elif paragraphs and isinstance(paragraphs, list):
            content.append("Document Paragraphs:")
            content.append("=" * 60)
            for para in paragraphs[:100]:
                if para and para.strip():
                    content.append(para)
        
        # Add tables if present
        tables = data.get('tables', [])
        if tables and isinstance(tables, list):
            content.append("\n" + "=" * 60)
            content.append(f"Document Tables ({len(tables)} table(s)):")
            content.append("=" * 60)
            
            for tableIdx, table in enumerate(tables[:10], 1):
                if table and isinstance(table, list):
                    content.append(f"\nTable {tableIdx}:")
                    content.append("-" * 60)
                    for rowIdx, row in enumerate(table[:20]):
                        if isinstance(row, list):
                            content.append(" | ".join(str(cell) for cell in row))
                    if len(table) > 20:
                        content.append(f"... ({len(table) - 20} more rows)")
        
        if not content:
            return str(data)[:10000]
        
        return "\n".join(content)[:10000]
    
    def extractEntities(self, wordData: Dict, entityType: str = "document") -> List[Dict]:
        """
        Extract entities from Word document using LLM
        
        Args:
            wordData: Data from readWord
            entityType: Type of entity to extract
            
        Returns:
            List of entity dicts
        """
        if not self.llmTool:
            raise RuntimeError("LLM tool required for entity extraction. Please configure GEMINI_API_KEY.")
        
        # Format document content for LLM
        docContent = self.formatForLLM(wordData)
        
        prompt = f"""Extract structured entities from this Word document.

Document Content:
{docContent[:8000]}

Entity Type: {entityType}

Extract meaningful entities such as:
- Key sections or topics
- Important data points or facts
- Structured information from tables
- Key concepts or terms

For each entity, provide:
- name: A clear, descriptive name
- description: Brief summary (max 200 chars)
- content: Full content or relevant excerpt
- rawData: Any structured data (from tables, etc.)

Respond in JSON format:
{{
    "entities": [
        {{
            "name": "entity_name",
            "description": "brief description",
            "content": "full content",
            "rawData": {{"key": "value"}}
        }}
    ]
}}

Extract only meaningful, substantial entities. Skip very short or trivial content.
"""
        
        try:
            response = self.llmTool.generate(prompt, maxTokens=2000)
            
            # Extract JSON from response
            jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if jsonMatch:
                result = json.loads(jsonMatch.group())
                entities = result.get('entities', [])
                
                # Ensure all entities have required fields
                for entity in entities:
                    entity['type'] = entityType
                    if 'name' not in entity:
                        entity['name'] = f"{entityType}_entity_{len(entities)}"
                
                return entities if entities else []
            
            return []
        except Exception as e:
            raise RuntimeError(f"Failed to extract entities from Word document: {str(e)}")
    
    def analyzeStructure(self, wordData: Dict) -> Dict[str, Any]:
        """
        Analyze Word document structure using LLM
        
        Args:
            wordData: Data from readWord
            
        Returns:
            Dict with structure analysis
        """
        if not self.llmTool:
            return {
                'paragraphs': len(wordData.get('paragraphs', [])),
                'tables': len(wordData.get('tables', [])),
                'textLength': len(wordData.get('text', ''))
            }
        
        docContent = self.formatForLLM(wordData)
        
        prompt = f"""Analyze the structure of this Word document.

Document Content:
{docContent[:8000]}

Provide a structured analysis including:
- Document type and purpose
- Main sections or topics
- Key information categories
- Data structure (if applicable)
- Important patterns or themes

Respond in JSON format:
{{
    "documentType": "type_description",
    "purpose": "document_purpose",
    "mainSections": ["section1", "section2"],
    "keyCategories": ["category1", "category2"],
    "dataStructure": "description",
    "patterns": ["pattern1", "pattern2"]
}}
"""
        
        try:
            response = self.llmTool.generate(prompt, maxTokens=500)
            
            # Extract JSON from response
            jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if jsonMatch:
                result = json.loads(jsonMatch.group())
                return result
            
            return {}
        except Exception:
            return {}

