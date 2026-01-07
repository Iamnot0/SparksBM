"""PDF document handler - handles PDF-specific operations"""
from typing import Dict, Optional, List, Any
import re
import json


class PDFDocHandler:
    """Handles PDF document operations: formatting, entity extraction, and analysis using LLM"""
    
    def __init__(self, llmTool=None):
        self.llmTool = llmTool
    
    def formatForLLM(self, data: Dict) -> str:
        """Format PDF data for LLM analysis"""
        # Try to get text directly
        text = data.get('text', '')
        if text and isinstance(text, str) and len(text.strip()) > 0:
            return text[:5000]
        
        # Fallback to pages
        pages = data.get('pages', [])
        if isinstance(pages, list) and pages:
            pageTexts = []
            for page in pages[:10]:
                if isinstance(page, dict):
                    pageText = page.get('text', '')
                    if pageText:
                        pageTexts.append(pageText)
                else:
                    pageTexts.append(str(page))
            if pageTexts:
                return '\n\n'.join(pageTexts)[:5000]
        
        # Last resort: return string representation
        return str(data)[:5000] if data else "No content available"
    
    def extractEntities(self, pdfData: Dict, entityType: str = "document") -> List[Dict]:
        """
        Extract entities from PDF document using LLM
        
        Args:
            pdfData: Data from readPDF
            entityType: Type of entity to extract
            
        Returns:
            List of entity dicts
        """
        if not self.llmTool:
            raise RuntimeError("LLM tool required for entity extraction. Please configure GEMINI_API_KEY.")
        
        # Format document content for LLM
        docContent = self.formatForLLM(pdfData)
        pages = pdfData.get('pages', [])
        pageCount = len(pages) if pages else 0
        
        prompt = f"""Extract structured entities from this PDF document.

Document Content:
{docContent[:8000]}

Document Metadata:
- Pages: {pageCount}
- Entity Type: {entityType}

Extract meaningful entities such as:
- Key sections or topics
- Important data points or facts
- Structured information from tables
- Key concepts or terms
- Page-specific information (if relevant)

For each entity, provide:
- name: A clear, descriptive name
- description: Brief summary (max 200 chars)
- content: Full content or relevant excerpt
- rawData: Any structured data (from tables, page numbers, etc.)

Respond in JSON format:
{{
    "entities": [
        {{
            "name": "entity_name",
            "description": "brief description",
            "content": "full content",
            "rawData": {{"key": "value", "pageNumber": 1}}
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
            raise RuntimeError(f"Failed to extract entities from PDF document: {str(e)}")
    
    def analyzeStructure(self, pdfData: Dict) -> Dict[str, Any]:
        """
        Analyze PDF document structure using LLM
        
        Args:
            pdfData: Data from readPDF
            
        Returns:
            Dict with structure analysis
        """
        if not self.llmTool:
            pages = pdfData.get('pages', [])
            return {
                'pages': len(pages),
                'tables': len(pdfData.get('tables', [])),
                'textLength': len(pdfData.get('text', ''))
            }
        
        docContent = self.formatForLLM(pdfData)
        pages = pdfData.get('pages', [])
        pageCount = len(pages) if pages else 0
        
        prompt = f"""Analyze the structure of this PDF document.

Document Content:
{docContent[:8000]}

Document Metadata:
- Total Pages: {pageCount}

Provide a structured analysis including:
- Document type and purpose
- Main sections or topics
- Key information categories
- Data structure (if applicable)
- Important patterns or themes
- Page organization (if relevant)

Respond in JSON format:
{{
    "documentType": "type_description",
    "purpose": "document_purpose",
    "mainSections": ["section1", "section2"],
    "keyCategories": ["category1", "category2"],
    "dataStructure": "description",
    "patterns": ["pattern1", "pattern2"],
    "pageOrganization": "description"
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

