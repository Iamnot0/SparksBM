"""Enhanced context manager - handles multiple documents, conversation flow, and relationships"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class EnhancedContextManager:
    """Manages context for multiple documents, conversations, and relationships"""
    
    def __init__(self):
        self.documents: Dict[str, Dict[str, Any]] = {}  # docId -> document data
        self.conversation: List[Dict[str, Any]] = []  # Full conversation history
        self.relationships: Dict[str, List[str]] = {}  # docId -> [related docIds]
        self.metadata: Dict[str, Dict[str, Any]] = {}  # docId -> metadata
        self.maxConversationHistory = 50  # Keep last 50 messages
    
    def addDocument(self, docId: str, data: Dict[str, Any], fileName: str, 
                   docType: str, metadata: Optional[Dict] = None) -> bool:
        """
        Add a document to context
        
        Args:
            docId: Unique document identifier
            data: Document data (from readExcel/readWord/readPDF)
            fileName: Original file name
            docType: Document type ('excel', 'word', 'pdf')
            metadata: Optional metadata (upload time, size, etc.)
            
        Returns:
            True if added successfully
        """
        self.documents[docId] = {
            'data': data,
            'fileName': fileName,
            'type': docType,
            'addedAt': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # Store metadata separately for quick access
        self.metadata[docId] = {
            'fileName': fileName,
            'type': docType,
            'addedAt': datetime.now().isoformat(),
            'rowCount': self._getRowCount(data, docType),
            'columnCount': self._getColumnCount(data, docType),
            'size': len(str(data))
        }
        
        return True
    
    def getDocument(self, docId: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        return self.documents.get(docId)
    
    def getAllDocuments(self) -> Dict[str, Dict[str, Any]]:
        """Get all documents"""
        return self.documents.copy()
    
    def getDocumentMetadata(self, docId: str) -> Optional[Dict[str, Any]]:
        """Get document metadata"""
        return self.metadata.get(docId)
    
    def listDocuments(self) -> List[Dict[str, Any]]:
        """List all documents with metadata"""
        return [
            {
                'id': docId,
                **self.metadata[docId]
            }
            for docId in self.metadata.keys()
        ]
    
    def findDocumentByName(self, fileName: str) -> Optional[str]:
        """Find document ID by file name"""
        for docId, meta in self.metadata.items():
            if meta['fileName'].lower() == fileName.lower():
                return docId
        return None
    
    def findDocumentsByType(self, docType: str) -> List[str]:
        """Find all document IDs of a specific type"""
        return [
            docId for docId, meta in self.metadata.items()
            if meta['type'] == docType
        ]
    
    def addToConversation(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add message to conversation history"""
        self.conversation.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        })
        
        # Keep conversation manageable
        if len(self.conversation) > self.maxConversationHistory:
            self.conversation = self.conversation[-self.maxConversationHistory:]
    
    def getConversationContext(self, limit: int = 10) -> str:
        """Get recent conversation context for LLM"""
        recent = self.conversation[-limit:] if len(self.conversation) > limit else self.conversation
        
        context = []
        for msg in recent:
            context.append(f"{msg['role'].upper()}: {msg['content']}")
        
        return "\n".join(context)
    
    def addRelationship(self, docId1: str, docId2: str, relationshipType: str = "related"):
        """Add relationship between two documents"""
        if docId1 not in self.relationships:
            self.relationships[docId1] = []
        
        if docId2 not in self.relationships:
            self.relationships[docId2] = []
        
        # Store bidirectional relationship
        if docId2 not in self.relationships[docId1]:
            self.relationships[docId1].append({
                'docId': docId2,
                'type': relationshipType,
                'createdAt': datetime.now().isoformat()
            })
        
        if docId1 not in self.relationships[docId2]:
            self.relationships[docId2].append({
                'docId': docId1,
                'type': relationshipType,
                'createdAt': datetime.now().isoformat()
            })
    
    def getRelatedDocuments(self, docId: str) -> List[str]:
        """Get related document IDs"""
        return [rel['docId'] for rel in self.relationships.get(docId, [])]
    
    def buildContextForLLM(self, query: str, includeDocuments: Optional[List[str]] = None) -> str:
        """
        Build comprehensive context string for LLM
        
        Args:
            query: Current user query
            includeDocuments: Specific document IDs to include (None = all)
            
        Returns:
            Formatted context string
        """
        contextParts = []
        
        # Add conversation context
        convContext = self.getConversationContext(limit=5)
        if convContext:
            contextParts.append("=== Recent Conversation ===")
            contextParts.append(convContext)
            contextParts.append("")
        
        # Add document context
        docIds = includeDocuments if includeDocuments else list(self.documents.keys())
        
        if docIds:
            contextParts.append("=== Available Documents ===")
            for docId in docIds:
                if docId in self.documents:
                    doc = self.documents[docId]
                    meta = self.metadata.get(docId, {})
                    
                    contextParts.append(f"\nDocument: {meta.get('fileName', 'Unknown')} (ID: {docId})")
                    contextParts.append(f"Type: {meta.get('type', 'unknown')}")
                    
                    if meta.get('type') == 'excel':
                        contextParts.append(f"Rows: {meta.get('rowCount', 'N/A')}")
                        contextParts.append(f"Columns: {meta.get('columnCount', 'N/A')}")
                        
                        # Get column names
                        columns = self._getColumnNames(doc['data'], 'excel')
                        if columns:
                            contextParts.append(f"Column Names: {', '.join(columns[:10])}")
                            if len(columns) > 10:
                                contextParts.append(f"... and {len(columns) - 10} more")
                    
                    elif meta.get('type') in ['word', 'pdf']:
                        textLen = len(doc['data'].get('text', ''))
                        contextParts.append(f"Text Length: {textLen} characters")
                        if 'pages' in doc['data']:
                            contextParts.append(f"Pages: {len(doc['data']['pages'])}")
                    
                    # Add preview
                    preview = self._getDocumentPreview(doc['data'], meta.get('type'))
                    if preview:
                        contextParts.append(f"Preview: {preview[:200]}...")
                    
                    contextParts.append("")
        
        # Add relationships
        if self.relationships:
            contextParts.append("=== Document Relationships ===")
            for docId, rels in self.relationships.items():
                if docId in self.metadata:
                    docName = self.metadata[docId]['fileName']
                    relatedNames = [
                        self.metadata.get(rel['docId'], {}).get('fileName', 'Unknown')
                        for rel in rels
                        if rel['docId'] in self.metadata
                    ]
                    if relatedNames:
                        contextParts.append(f"{docName} is related to: {', '.join(relatedNames)}")
            contextParts.append("")
        
        return "\n".join(contextParts)
    
    def _getRowCount(self, data: Dict, docType: str) -> Optional[int]:
        """Get row count from document data"""
        if docType == 'excel':
            if 'sheets' in data:
                return sum(sheet.get('rows', 0) for sheet in data['sheets'].values())
            elif 'rows' in data:
                return data['rows']
            elif 'data' in data:
                return len(data['data'])
        return None
    
    def _getColumnCount(self, data: Dict, docType: str) -> Optional[int]:
        """Get column count from document data"""
        if docType == 'excel':
            if 'sheets' in data:
                firstSheet = list(data['sheets'].values())[0] if data['sheets'] else {}
                return len(firstSheet.get('columns', []))
            elif 'columns' in data:
                return len(data['columns'])
        return None
    
    def _getColumnNames(self, data: Dict, docType: str) -> List[str]:
        """Get column names from document data"""
        if docType == 'excel':
            if 'sheets' in data:
                firstSheet = list(data['sheets'].values())[0] if data['sheets'] else {}
                return firstSheet.get('columns', [])
            elif 'columns' in data:
                return data['columns']
        return []
    
    def _getDocumentPreview(self, data: Dict, docType: str) -> str:
        """Get preview of document content"""
        if docType == 'excel':
            if 'sheets' in data:
                firstSheet = list(data['sheets'].values())[0] if data['sheets'] else {}
                if firstSheet.get('data'):
                    return str(firstSheet['data'][:2])  # First 2 rows
            elif 'data' in data:
                return str(data['data'][:2])
        elif docType in ['word', 'pdf']:
            return data.get('text', '')[:500]
        return ""
    
    def removeDocument(self, docId: str) -> bool:
        """Remove document from context"""
        if docId in self.documents:
            del self.documents[docId]
        if docId in self.metadata:
            del self.metadata[docId]
        if docId in self.relationships:
            # Remove from other documents' relationships
            for otherDocId, rels in self.relationships.items():
                self.relationships[otherDocId] = [
                    rel for rel in rels if rel['docId'] != docId
                ]
            del self.relationships[docId]
        return True
    
    def getSummary(self) -> Dict[str, Any]:
        """Get summary of current context"""
        return {
            'documentCount': len(self.documents),
            'conversationLength': len(self.conversation),
            'relationshipCount': sum(len(rels) for rels in self.relationships.values()),
            'documents': [
                {
                    'id': docId,
                    'name': meta['fileName'],
                    'type': meta['type']
                }
                for docId, meta in self.metadata.items()
            ]
        }

