"""Document query tools - intelligent querying of processed documents"""
from typing import Dict, List, Optional, Any
import re


class DocumentQueryTool:
    """Tools for querying processed document data intelligently"""
    
    @staticmethod
    def getRowCount(documentData: Dict, sheetName: Optional[str] = None) -> int:
        """
        Get row count from Excel document
        
        Args:
            documentData: Data from readExcel
            sheetName: Specific sheet (None = first sheet)
            
        Returns:
            Number of rows
        """
        if 'sheets' in documentData:
            if sheetName:
                sheet = documentData['sheets'].get(sheetName, {})
                return sheet.get('rows', 0)
            else:
                # Return total rows from all sheets
                total = 0
                for sheetData in documentData['sheets'].values():
                    total += sheetData.get('rows', 0)
                return total
        elif 'rows' in documentData:
            return documentData['rows']
        elif 'data' in documentData:
            return len(documentData['data'])
        return 0
    
    @staticmethod
    def getColumn(documentData: Dict, columnName: str, sheetName: Optional[str] = None) -> List[Any]:
        """
        Extract a specific column from Excel document
        
        Args:
            documentData: Data from readExcel
            columnName: Name of column to extract
            sheetName: Specific sheet (None = first sheet)
            
        Returns:
            List of column values
        """
        # Normalize column name (case-insensitive, handle spaces)
        columnNameLower = columnName.lower().strip()
        
        if 'sheets' in documentData:
            # Multi-sheet - use specified sheet or first
            if sheetName:
                sheet = documentData['sheets'].get(sheetName, {})
            else:
                sheet = list(documentData['sheets'].values())[0] if documentData['sheets'] else {}
            
            data = sheet.get('data', [])
            columns = sheet.get('columns', [])
            
            # Find matching column (case-insensitive)
            matchingColumn = None
            for col in columns:
                if col.lower().strip() == columnNameLower:
                    matchingColumn = col
                    break
            
            if not matchingColumn:
                # Try fuzzy match
                for col in columns:
                    if columnNameLower in col.lower() or col.lower() in columnNameLower:
                        matchingColumn = col
                        break
            
            if matchingColumn:
                return [row.get(matchingColumn) for row in data if matchingColumn in row]
            return []
        
        elif 'data' in documentData:
            # Single sheet data
            data = documentData['data']
            columns = documentData.get('columns', [])
            
            # Find matching column
            matchingColumn = None
            for col in columns:
                if col.lower().strip() == columnNameLower:
                    matchingColumn = col
                    break
            
            if not matchingColumn:
                # Try fuzzy match
                for col in columns:
                    if columnNameLower in col.lower() or col.lower() in columnNameLower:
                        matchingColumn = col
                        break
            
            if matchingColumn:
                return [row.get(matchingColumn) for row in data if matchingColumn in row]
            return []
        
        return []
    
    @staticmethod
    def getColumns(documentData: Dict, sheetName: Optional[str] = None) -> List[str]:
        """
        Get list of column names from Excel document
        
        Args:
            documentData: Data from readExcel
            sheetName: Specific sheet (None = first sheet)
            
        Returns:
            List of column names
        """
        if 'sheets' in documentData:
            if sheetName:
                sheet = documentData['sheets'].get(sheetName, {})
                return sheet.get('columns', [])
            else:
                # Return columns from first sheet
                firstSheet = list(documentData['sheets'].values())[0] if documentData['sheets'] else {}
                return firstSheet.get('columns', [])
        elif 'columns' in documentData:
            return documentData['columns']
        return []
    
    @staticmethod
    def filterRows(documentData: Dict, conditions: Dict[str, Any], sheetName: Optional[str] = None) -> List[Dict]:
        """
        Filter rows based on conditions
        
        Args:
            documentData: Data from readExcel
            conditions: Dict of {column: value} to filter by
            sheetName: Specific sheet (None = first sheet)
            
        Returns:
            Filtered list of rows
        """
        # Get data
        if 'sheets' in documentData:
            if sheetName:
                sheet = documentData['sheets'].get(sheetName, {})
            else:
                sheet = list(documentData['sheets'].values())[0] if documentData['sheets'] else {}
            data = sheet.get('data', [])
        elif 'data' in documentData:
            data = documentData['data']
        else:
            return []
        
        # Filter rows
        filtered = []
        for row in data:
            match = True
            for col, value in conditions.items():
                # Case-insensitive column matching
                rowValue = None
                for key in row.keys():
                    if key.lower().strip() == col.lower().strip():
                        rowValue = row[key]
                        break
                
                if rowValue != value:
                    match = False
                    break
            
            if match:
                filtered.append(row)
        
        return filtered
    
    @staticmethod
    def getRows(documentData: Dict, limit: Optional[int] = None, sheetName: Optional[str] = None) -> List[Dict]:
        """
        Get rows from Excel document
        
        Args:
            documentData: Data from readExcel
            limit: Maximum number of rows to return (None = all)
            sheetName: Specific sheet (None = first sheet)
            
        Returns:
            List of row dicts
        """
        # Get data
        if 'sheets' in documentData:
            if sheetName:
                sheet = documentData['sheets'].get(sheetName, {})
            else:
                sheet = list(documentData['sheets'].values())[0] if documentData['sheets'] else {}
            data = sheet.get('data', [])
        elif 'data' in documentData:
            data = documentData['data']
        else:
            return []
        
        if limit:
            return data[:limit]
        return data
    
    @staticmethod
    def searchInDocument(documentData: Dict, query: str, documentType: str = 'word') -> List[Dict]:
        """
        Search for text in Word/PDF documents
        
        Args:
            documentData: Data from readWord or readPDF
            query: Search query
            documentType: 'word' or 'pdf'
            
        Returns:
            List of matches with context
        """
        queryLower = query.lower()
        matches = []
        
        if documentType == 'word':
            text = documentData.get('text', '')
            paragraphs = documentData.get('paragraphs', [])
            
            # Search in paragraphs
            for i, para in enumerate(paragraphs):
                if queryLower in para.lower():
                    matches.append({
                        'type': 'paragraph',
                        'index': i,
                        'text': para,
                        'context': para[:200]
                    })
        
        elif documentType == 'pdf':
            text = documentData.get('text', '')
            pages = documentData.get('pages', [])
            
            # Search in pages
            for page in pages:
                pageText = page.get('text', '')
                if queryLower in pageText.lower():
                    matches.append({
                        'type': 'page',
                        'page_number': page.get('page_number'),
                        'text': pageText[:200],
                        'context': pageText[:200]
                    })
        
        return matches
    
    @staticmethod
    def getDocumentSummary(documentData: Dict, documentType: str) -> Dict[str, Any]:
        """
        Get summary of document structure
        
        Args:
            documentData: Data from readExcel/readWord/readPDF
            documentType: 'excel', 'word', or 'pdf'
            
        Returns:
            Summary dict
        """
        summary = {'type': documentType}
        
        if documentType == 'excel':
            if 'sheets' in documentData:
                summary['sheets'] = list(documentData['sheets'].keys())
                summary['total_rows'] = sum(s.get('rows', 0) for s in documentData['sheets'].values())
                summary['columns'] = {}
                for sheetName, sheetData in documentData['sheets'].items():
                    summary['columns'][sheetName] = sheetData.get('columns', [])
            else:
                summary['rows'] = documentData.get('rows', 0)
                summary['columns'] = documentData.get('columns', [])
        
        elif documentType == 'word':
            summary['paragraphs'] = len(documentData.get('paragraphs', []))
            summary['tables'] = len(documentData.get('tables', []))
            summary['text_length'] = len(documentData.get('text', ''))
        
        elif documentType == 'pdf':
            summary['pages'] = documentData.get('metadata', {}).get('pages', len(documentData.get('pages', [])))
            summary['tables'] = len(documentData.get('tables', []))
            summary['text_length'] = len(documentData.get('text', ''))
        
        return summary

