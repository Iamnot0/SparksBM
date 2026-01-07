"""PDF file reading tools"""
import os
from typing import Dict, List, Optional

try:
    import PyPDF2
    PDF_LIBRARY = 'PyPDF2'
except ImportError:
    try:
        import pdfplumber
        PDF_LIBRARY = 'pdfplumber'
    except ImportError:
        PDF_LIBRARY = None


class PDFTool:
    """Tools for reading and processing PDF files"""
    
    @staticmethod
    def readPDF(filePath: str) -> Dict:
        """
        Read PDF file and extract text/content
        
        Args:
            filePath: Path to PDF file
            
        Returns:
            Dict with text content, pages, and metadata
        """
        if not os.path.exists(filePath):
            raise FileNotFoundError(f"PDF file not found: {filePath}")
        
        if PDF_LIBRARY is None:
            raise RuntimeError("No PDF library available. Please install PyPDF2 or pdfplumber: pip install PyPDF2")
        
        try:
            if PDF_LIBRARY == 'pdfplumber':
                return PDFTool._readWithPdfplumber(filePath)
            else:
                return PDFTool._readWithPyPDF2(filePath)
        except Exception as e:
            errorMsg = str(e)
            # Check for encryption-related errors
            if 'encrypted' in errorMsg.lower() or 'password' in errorMsg.lower() or 'PyCryptodome' in errorMsg:
                raise RuntimeError(
                    f"PDF file is encrypted. PyCryptodome is required to decrypt it. "
                    f"Please install: pip install pycryptodome\n"
                    f"Original error: {errorMsg}"
                )
            raise RuntimeError(f"Failed to read PDF file: {errorMsg}")
    
    @staticmethod
    def _readWithPyPDF2(filePath: str) -> Dict:
        """Read PDF using PyPDF2"""
        text = []
        pages = []
        metadata = {}
        
        with open(filePath, 'rb') as file:
            pdfReader = PyPDF2.PdfReader(file)
            
            # Check if PDF is encrypted
            if pdfReader.is_encrypted:
                # Try to decrypt with empty password first
                try:
                    pdfReader.decrypt('')
                except Exception:
                    # If that fails, check if PyCryptodome is available
                    try:
                        import Crypto
                    except ImportError:
                        raise RuntimeError(
                            "PDF file is encrypted. PyCryptodome is required for AES algorithm. "
                            "Please install: pip install pycryptodome"
                        )
                    # If PyCryptodome is available but decryption fails, raise error
                    raise RuntimeError(
                        "PDF file is encrypted and requires a password. "
                        "Please provide the password or use an unencrypted PDF."
                    )
            
            # Extract metadata
            if pdfReader.metadata:
                metadata = {
                    'title': pdfReader.metadata.get('/Title', ''),
                    'author': pdfReader.metadata.get('/Author', ''),
                    'subject': pdfReader.metadata.get('/Subject', ''),
                    'creator': pdfReader.metadata.get('/Creator', ''),
                    'producer': pdfReader.metadata.get('/Producer', ''),
                    'creationDate': str(pdfReader.metadata.get('/CreationDate', '')),
                    'modificationDate': str(pdfReader.metadata.get('/ModDate', ''))
                }
            
            # Extract text from each page
            for pageNum, page in enumerate(pdfReader.pages, 1):
                pageText = page.extract_text()
                pages.append({
                    'pageNumber': pageNum,
                    'text': pageText,
                    'charCount': len(pageText)
                })
                text.append(pageText)
            
            fullText = '\n\n'.join(text)
            
            return {
                'text': fullText,
                'pages': pages,
                'pageCount': len(pages),
                'totalCharCount': len(fullText),
                'metadata': metadata
            }
    
    @staticmethod
    def _readWithPdfplumber(filePath: str) -> Dict:
        """Read PDF using pdfplumber (better for tables)"""
        text = []
        pages = []
        tables = []
        metadata = {}
        
        with pdfplumber.open(filePath) as pdf:
            # Extract metadata
            if pdf.metadata:
                metadata = {
                    'title': pdf.metadata.get('Title', ''),
                    'author': pdf.metadata.get('Author', ''),
                    'subject': pdf.metadata.get('Subject', ''),
                    'creator': pdf.metadata.get('Creator', ''),
                    'producer': pdf.metadata.get('Producer', ''),
                    'creationDate': str(pdf.metadata.get('CreationDate', '')),
                    'modificationDate': str(pdf.metadata.get('ModDate', ''))
                }
            
            # Extract text and tables from each page
            for pageNum, page in enumerate(pdf.pages, 1):
                pageText = page.extract_text() or ''
                
                # Extract tables from page
                pageTables = page.extract_tables()
                for table in pageTables:
                    if table:
                        tables.append({
                            'pageNumber': pageNum,
                            'data': table
                        })
                
                pages.append({
                    'pageNumber': pageNum,
                    'text': pageText,
                    'charCount': len(pageText),
                    'tableCount': len(pageTables) if pageTables else 0
                })
                text.append(pageText)
            
            fullText = '\n\n'.join(text)
            
            return {
                'text': fullText,
                'pages': pages,
                'pageCount': len(pages),
                'totalCharCount': len(fullText),
                'tables': tables,
                'tableCount': len(tables),
                'metadata': metadata
            }
    
    @staticmethod
    def extractEntities(pdfData: Dict, entityType: str = "document") -> List[Dict]:
        """
        Extract entities from PDF data for Verinice
        
        Args:
            pdfData: Data from readPDF
            entityType: Type of entity to extract
            
        Returns:
            List of entity dicts
        """
        entities = []
        
        # Extract from text - split by pages or sections
        text = pdfData.get('text', '')
        pages = pdfData.get('pages', [])
        
        # Create entity for each page with significant content
        for page in pages:
            pageText = page.get('text', '')
            if len(pageText.strip()) > 50:  # Skip very short pages
                entity = {
                    'type': entityType,
                    'name': f"{entityType}_page_{page.get('pageNumber', 0)}",
                    'description': pageText[:200],  # First 200 chars
                    'content': pageText,
                    'rawData': {
                        'pageNumber': page.get('pageNumber', 0),
                        'charCount': page.get('charCount', 0)
                    }
                }
                entities.append(entity)
        
        # Also extract from tables if present
        for tableIdx, table in enumerate(pdfData.get('tables', []), 1):
            tableData = table.get('data', [])
            if tableData and len(tableData) > 1:  # Has header row
                # Use first row as headers
                headers = tableData[0]
                for rowIdx, row in enumerate(tableData[1:], 1):
                    entity = {
                        'type': entityType,
                        'name': f"{entityType}_table_{tableIdx}_row_{rowIdx}",
                        'description': f"Data from table {tableIdx} on page {table.get('pageNumber', 0)}",
                        'rawData': dict(zip(headers, row)) if headers else {'row': row}
                    }
                    entities.append(entity)
        
        # If no entities extracted, create one for the whole document
        if not entities:
            entities.append({
                'type': entityType,
                'name': f"{entityType}_document",
                'description': text[:200],
                'content': text
            })
        
        return entities

