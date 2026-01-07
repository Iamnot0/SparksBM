"""Context mapper - converts ISMS objects to agent-readable context"""
from typing import List, Dict, Any, Optional
import sys
import os

# Add scripts to path
_currentDir = os.path.dirname(os.path.abspath(__file__))
_scriptsPath = os.path.join(_currentDir, '..', '..', 'SparksbmISMS', 'scripts')
if os.path.exists(_scriptsPath) and _scriptsPath not in sys.path:
    sys.path.insert(0, _scriptsPath)

try:
    from sparksbmMgmt import SparksBMClient, API_URL
    ISMS_AVAILABLE = True
except ImportError:
    ISMS_AVAILABLE = False
    SparksBMClient = None
    API_URL = "http://localhost:8070"


class ContextMapper:
    """Maps ISMS objects to agent context"""
    
    def __init__(self):
        self.client = None
        if ISMS_AVAILABLE:
            try:
                self.client = SparksBMClient()
            except Exception:
                pass
    
    def buildContext(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build context from sources (ISMS objects or uploaded files)
        
        Returns:
            Dict with context string and metadata (excelFileCount, hasProcessedDocument, etc.)
        """
        if not sources:
            return {
                'context': "",
                'hasProcessedDocument': False,
                'documentCount': 0,
                'excelFileCount': 0,
                'activeSources': []
            }
        
        contextParts = []
        excelFileCount = 0
        documentCount = 0
        
        for source in sources:
            sourceId = source.get('id')
            sourceType = source.get('type')
            sourceName = source.get('name', 'Unknown')
            
            # Check if this is an uploaded file (has 'data' field)
            if 'data' in source:
                fileData = source.get('data', {})
                fileType = sourceType or fileData.get('fileType', '')
                contextParts.append(self._formatFileData(sourceName, sourceType, fileData))
                documentCount += 1
                if fileType == 'excel' or fileData.get('sheets') or fileData.get('data'):
                    excelFileCount += 1
            # Otherwise, treat as ISMS object
            else:
                domainId = source.get('domainId')
                if not sourceId or not sourceType or not domainId:
                    continue
                
                # Fetch object details
                objectData = self._fetchObject(sourceType, domainId, sourceId)
                if objectData:
                    contextParts.append(self._formatObject(objectData, sourceType))
        
        contextStr = "\n\n".join(contextParts) if contextParts else ""
        
        return {
            'context': contextStr,
            'hasProcessedDocument': documentCount > 0,
            'documentCount': documentCount,
            'excelFileCount': excelFileCount,
            'activeSources': sources
        }
    
    def _fetchObject(self, objectType: str, domainId: str, objectId: str) -> Optional[Dict]:
        """Fetch object from ISMS API"""
        if not self.client or not self.client.accessToken:
            return None
        
        try:
            objectTypeMap = {
                "scope": "scopes",
                "asset": "assets",
                "control": "controls",
                "process": "processes",
                "person": "persons",
                "scenario": "scenarios",
                "incident": "incidents",
                "document": "documents"
            }
            
            plural = objectTypeMap.get(objectType.lower())
            if not plural:
                return None
            
            url = f"{API_URL}/domains/{domainId}/{plural}/{objectId}"
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            return response.json()
            
        except Exception:
            return None
    
    def _formatObject(self, objectData: Dict, objectType: str) -> str:
        """Format object data for agent context"""
        name = objectData.get('name', 'Unknown')
        objId = objectData.get('id', '')
        description = objectData.get('description', '')
        subType = objectData.get('subType', '')
        
        parts = [f"{objectType.capitalize()}: {name}"]
        
        if objId:
            parts.append(f"ID: {objId}")
        
        if subType:
            parts.append(f"SubType: {subType}")
        
        if description:
            parts.append(f"Description: {description[:200]}")
        
        # Add key properties
        for key in ['status', 'priority', 'riskLevel']:
            if key in objectData:
                parts.append(f"{key}: {objectData[key]}")
        
        return "\n".join(parts)
    
    def _formatFileData(self, fileName: str, fileType: str, fileData: Dict) -> str:
        """Format uploaded file data for agent context"""
        parts = [f"Uploaded File: {fileName}"]
        parts.append(f"Type: {fileType}")
        
        # Format Excel data
        if fileType == 'excel' and isinstance(fileData, dict):
            if 'sheets' in fileData:
                parts.append(f"Sheets: {', '.join(fileData.get('sheets', []))}")
            if 'data' in fileData:
                data = fileData.get('data', {})
                if isinstance(data, dict):
                    for sheetName, sheetData in data.items():
                        if isinstance(sheetData, list) and len(sheetData) > 0:
                            parts.append(f"\nSheet '{sheetName}' ({len(sheetData)} rows):")
                            # Show first few rows as sample
                            for i, row in enumerate(sheetData[:5]):
                                parts.append(f"  Row {i+1}: {row}")
                            if len(sheetData) > 5:
                                parts.append(f"  ... and {len(sheetData) - 5} more rows")
        
        # Format Word data
        elif fileType == 'word' and isinstance(fileData, dict):
            if 'text' in fileData:
                text = fileData.get('text', '')
                preview = text[:500] if len(text) > 500 else text
                parts.append(f"\nContent preview:\n{preview}")
                if len(text) > 500:
                    parts.append(f"\n... ({len(text) - 500} more characters)")
            if 'paragraphs' in fileData:
                paragraphs = fileData.get('paragraphs', [])
                parts.append(f"\nParagraphs: {len(paragraphs)}")
                for i, para in enumerate(paragraphs[:3]):
                    parts.append(f"  Para {i+1}: {para[:100]}...")
        
        # Fallback: show raw data structure
        else:
            parts.append(f"\nData: {str(fileData)[:500]}")
        
        return "\n".join(parts)
