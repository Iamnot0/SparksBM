"""
Document Coordinator - Phase 2 Refactoring
Handles all document processing operations (Excel, Word, PDF)

CRITICAL: This coordinator handles EXECUTION only.
Routing decisions (single vs bulk, which operation) stay in MainAgent.
"""

from typing import Dict, Optional, Any, Tuple
from ..excelDoc import ExcelDocHandler
from ..wordDoc import WordDocHandler
from ..pdfDoc import PDFDocHandler


class DocumentCoordinator:
    """
    Coordinates document processing operations.
    
    Does NOT handle routing decisions - those stay in MainAgent.
    This coordinator only executes document operations.
    """
    
    def __init__(self, state: Dict, tools: Dict, contextManager=None, llmTool=None, reasoningEngine=None, veriniceTool=None, formatVeriniceResult=None):
        """
        Initialize Document Coordinator.
        
        Args:
            state: Agent state dictionary (for lastProcessed, processedCount, etc.)
            tools: Tool registry dictionary
            contextManager: Context manager for document storage (optional)
            llmTool: LLM tool for document analysis (optional, for backward compatibility)
            reasoningEngine: ReasoningEngine for document analysis (preferred, optional)
            veriniceTool: Verinice tool for ISMS operations (optional)
            formatVeriniceResult: Function to format Verinice results (optional)
        """
        self.state = state
        self.tools = tools
        self.contextManager = contextManager
        self.llmTool = llmTool  # Kept for backward compatibility
        self._reasoningEngine = reasoningEngine  # Preferred method
        self.veriniceTool = veriniceTool
        self.formatVeriniceResult = formatVeriniceResult
        
        # Lazy initialization of handlers
        self._excelHandler = None
        self._wordHandler = None
        self._pdfHandler = None
    
    def _ensureExcelHandler(self):
        """Initialize Excel handler if needed"""
        if not self._excelHandler:
            self._excelHandler = ExcelDocHandler(self.llmTool, self.veriniceTool, self.formatVeriniceResult)
    
    def _ensureWordHandler(self):
        """Initialize Word handler if needed"""
        if not self._wordHandler:
            self._wordHandler = WordDocHandler(self.llmTool)
    
    def _ensurePDFHandler(self):
        """Initialize PDF handler if needed"""
        if not self._pdfHandler:
            self._pdfHandler = PDFDocHandler(self.llmTool)
    
    def _executeTool(self, toolName: str, **kwargs) -> Any:
        """Execute a tool by name"""
        if toolName not in self.tools:
            raise ValueError(f"Tool '{toolName}' not available")
        tool = self.tools[toolName]['func']
        return tool(**kwargs)
    
    def processFile(self, filePath: str) -> Dict:
        """
        Process Excel, Word, or PDF file.
        
        This is the EXECUTION logic - routing decision stays in MainAgent.
        """
        if 'readExcel' not in self.tools and 'readWord' not in self.tools and 'readPDF' not in self.tools:
            return {'status': 'error', 'result': None, 'error': 'No document reading tools registered'}
        
        try:
            # Determine file type and read file
            if filePath.endswith(('.xlsx', '.xls')):
                data = self._executeTool('readExcel', filePath=filePath)
            elif filePath.endswith(('.docx', '.doc')):
                data = self._executeTool('readWord', filePath=filePath)
            elif filePath.endswith('.pdf'):
                data = self._executeTool('readPDF', filePath=filePath)
            else:
                return {'status': 'error', 'result': None, 'error': f'Unsupported file type: {filePath}'}
            
            # Store in state
            self.state['lastProcessed'] = data
            self.state['processedCount'] = self.state.get('processedCount', 0) + 1
            
            # Store in context manager
            if self.contextManager:
                import uuid
                import os
                docId = str(uuid.uuid4())
                fileName = os.path.basename(filePath)
                docType = 'excel' if filePath.endswith(('.xlsx', '.xls')) else ('word' if filePath.endswith(('.docx', '.doc')) else 'pdf')
                self.contextManager.addDocument(docId, data, fileName, docType)
                self.state['lastProcessedDocId'] = docId
            
            # For Excel files, check if it looks like an asset inventory and suggest bulk import
            if filePath.endswith(('.xlsx', '.xls')):
                self._ensureExcelHandler()
                bulkImportSuggestion = self._excelHandler.detectAssetInventory(data)
                if bulkImportSuggestion:
                    data['_bulkImportSuggestion'] = bulkImportSuggestion
            
            return {'status': 'success', 'result': data, 'next_steps': ['validateData', 'transformForVerinice']}
        
        except FileNotFoundError as e:
            return {'status': 'error', 'result': None, 'error': f'File not found: {str(e)}'}
        except Exception as e:
            return {'status': 'error', 'result': None, 'error': f'Failed to process file: {str(e)}'}
    
    def processData(self, data: Dict) -> Dict:
        """Process already structured data"""
        self.state['lastProcessed'] = data
        return {'status': 'success', 'result': data, 'next_steps': ['validateData', 'transformForVerinice']}
    
    def getDocumentContent(self, lastData: Dict, fileName: str = None, fileType: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract document content from lastData.
        Returns: (docContent, docType) or (None, None) if not found
        """
        if not lastData or not isinstance(lastData, dict):
            return (None, None)
        
        # Unwrap nested data if needed
        if 'data' in lastData and isinstance(lastData.get('data'), dict):
            nestedData = lastData.get('data')
            if any(k in nestedData for k in ['text', 'pages', 'sheets', 'paragraphs']):
                for key, value in nestedData.items():
                    if key not in lastData or lastData[key] is None:
                        lastData[key] = value
        
        # Get content based on structure
        if 'sheets' in lastData:
            self._ensureExcelHandler()
            return (self._excelHandler.formatForLLM(lastData), 'Excel')
        elif 'paragraphs' in lastData:
            self._ensureWordHandler()
            return (self._wordHandler.formatForLLM(lastData), 'Word')
        elif 'text' in lastData or 'pages' in lastData:
            self._ensurePDFHandler()
            return (self._pdfHandler.formatForLLM(lastData), 'PDF')
        
        return (None, None)
    
    def handleExcelComparison(self, message: str, context: Dict, errorFunc, successFunc) -> Optional[Dict]:
        """
        Handle Excel file comparison request.
        
        Args:
            message: User message (for context, not used in execution)
            context: Context dictionary with activeSources
            errorFunc: Function to create error responses
            successFunc: Function to create success responses
        
        Returns:
            Comparison result or None
        """
        try:
            # Get Excel files from context
            activeSources = context.get('activeSources', [])
            if not activeSources:
                return errorFunc("No files found in session. Please upload at least 2 Excel files first.")
            
            # Filter Excel files from sources
            excelFiles = []
            for source in activeSources:
                sourceData = source.get('data', {})
                fileType = sourceData.get('fileType', '') or source.get('type', '')
                if fileType == 'excel' or (sourceData.get('sheets') or sourceData.get('data')):
                    excelFiles.append({
                        'fileName': sourceData.get('fileName') or source.get('name', 'Unknown'),
                        'data': sourceData
                    })
            
            # Also check lastProcessed if it's Excel
            lastProcessed = self.state.get('lastProcessed', {})
            if lastProcessed and (lastProcessed.get('fileType') == 'excel' or lastProcessed.get('sheets') or lastProcessed.get('data')):
                fileName = lastProcessed.get('fileName', 'Last Processed')
                # Check if not already in excelFiles
                if not any(f['fileName'] == fileName for f in excelFiles):
                    excelFiles.append({
                        'fileName': fileName,
                        'data': lastProcessed
                    })
            
            # Need at least 2 Excel files to compare
            if len(excelFiles) < 2:
                return errorFunc(
                    f"Need at least 2 Excel files to compare. Currently have {len(excelFiles)} Excel file(s). "
                    f"Please upload another Excel file first."
                )
            
            # Use the two most recent Excel files
            file1 = excelFiles[-2]
            file2 = excelFiles[-1]
            
            # Initialize Excel handler
            self._ensureExcelHandler()
            
            # Perform comparison
            comparisonResult = self._excelHandler.compareExcelFiles(
                file1['data'],
                file2['data'],
                file1['fileName'],
                file2['fileName']
            )
            
            if not comparisonResult.get('success'):
                return errorFunc(comparisonResult.get('error', 'Failed to compare files'))
            
            # Format comparison results
            differences = comparisonResult.get('differences', [])
            summary = comparisonResult.get('summary', {})
            
            # Build formatted response
            response = []
            response.append("📊 **Excel File Comparison**")
            response.append("")
            response.append(f"**File 1:** {file1['fileName']}")
            response.append(f"**File 2:** {file2['fileName']}")
            response.append("")
            
            # Summary
            response.append("**Summary:**")
            response.append(f"- File 1: {summary.get('file1', {}).get('rows', 0)} rows, {len(summary.get('file1', {}).get('columns', []))} columns")
            response.append(f"- File 2: {summary.get('file2', {}).get('rows', 0)} rows, {len(summary.get('file2', {}).get('columns', []))} columns")
            response.append(f"- Total differences found: {comparisonResult.get('total_differences', 0)}")
            response.append("")
            
            # Differences
            if differences:
                response.append("**Differences Found:**\n")
                for idx, diff in enumerate(differences[:20], 1):  # Limit to 20 differences
                    diffType = diff.get('type', 'unknown')
                    diffMsg = diff.get('message', '')
                    sheet = diff.get('sheet', '')
                    
                    if sheet:
                        response.append(f"{idx}. [{diffType.upper()}] {sheet}: {diffMsg}")
                    else:
                        response.append(f"{idx}. [{diffType.upper()}] {diffMsg}")
                    
                    # Add details for data differences
                    if diffType == 'data_difference' and diff.get('differences'):
                        dataDiffs = diff.get('differences', [])[:5]  # Show first 5
                        for dataDiff in dataDiffs:
                            response.append(f"   - Row '{dataDiff.get('key')}', Column '{dataDiff.get('column')}':")
                            response.append(f"     File 1: {dataDiff.get('file1_value')}")
                            response.append(f"     File 2: {dataDiff.get('file2_value')}")
                    
                    response.append("")
                
                if len(differences) > 20:
                    response.append(f"\n... and {len(differences) - 20} more differences")
            else:
                response.append("\n✅ **No differences found!** The files are identical.")
            
            return successFunc("\n".join(response))
            
        except Exception:
            return errorFunc("Error comparing Excel files")
    
    def analyzeDocumentWithLLM(self, message: str, errorFunc, successFunc) -> Dict:
        """
        Analyze document using LLM.
        
        Args:
            message: User message/query
            errorFunc: Function to create error responses
            successFunc: Function to create success responses
        
        Returns:
            Analysis result
        """
        # Try to find document from multiple sources
        lastData = self.state.get('lastProcessed')
        
        if lastData:
            # Check if data is None or empty
            if lastData.get('data') is None and not any(k in lastData for k in ['text', 'pages', 'sheets', 'paragraphs']):
                # Data is None - try to re-read from filePath if available
                filePath = lastData.get('filePath')
                fileName = lastData.get('fileName', '')
                fileType = lastData.get('fileType', '').lower()
                
                if filePath:
                    import os
                    if os.path.exists(filePath):
                        try:
                            # Re-read the file
                            if fileType == 'pdf' or fileName.lower().endswith('.pdf'):
                                lastData = self._executeTool('readPDF', filePath=filePath)
                            elif fileType in ['xlsx', 'xls'] or fileName.lower().endswith(('.xlsx', '.xls')):
                                lastData = self._executeTool('readExcel', filePath=filePath)
                            elif fileType in ['docx', 'doc'] or fileName.lower().endswith(('.docx', '.doc')):
                                lastData = self._executeTool('readWord', filePath=filePath)
                            
                            if isinstance(lastData, dict):
                                lastData['fileName'] = fileName
                                lastData['fileType'] = fileType
                                lastData['filePath'] = filePath
                                # Update state with re-read data
                                self.state['lastProcessed'] = lastData
                        except Exception:
                            return errorFunc("Failed to re-read file")
        
        # If no lastProcessed or data is None/empty, check context manager
        if not lastData or (isinstance(lastData, dict) and lastData.get('data') is None and not any(k in lastData for k in ['text', 'pages', 'sheets', 'paragraphs'])):
            if self.contextManager and hasattr(self.contextManager, 'documents'):
                docs = self.contextManager.documents
                if docs:
                    # Get most recent document
                    latestDocId = max(docs.keys(), key=lambda k: docs[k].get('addedAt', ''))
                    docInfo = docs[latestDocId]
                    docData = docInfo.get('data', {})
                    if isinstance(docData, dict):
                        lastData = docData.copy()
                        lastData['fileName'] = docInfo.get('fileName', 'Unknown')
                        lastData['fileType'] = docInfo.get('fileType', 'unknown')
        
        if not lastData:
            return errorFunc("No document found. Please upload a file first.")
        
        # Get document content
        docContent, docType = self.getDocumentContent(lastData, lastData.get('fileName'), lastData.get('fileType'))
        
        if docContent:
            # Use ReasoningEngine for analysis (preferred) or LLMTool (fallback)
            reasoningEngine = self._reasoningEngine or (self.state.get('_agent') and getattr(self.state['_agent'], '_reasoningEngine', None))
            
            if reasoningEngine and reasoningEngine.isAvailable():
                try:
                    analysisPrompt = f"Analyze this {docType} document and answer: {message}\n\nDocument content:\n{docContent[:5000]}"  # Limit content size
                    system_prompt = f"You are an expert document analyst. Analyze {docType} documents thoroughly and provide detailed insights."
                    context = {
                        "documents": [f"{lastData.get('fileName', 'Unknown')} ({docType})"]
                    }
                    analysisResult = reasoningEngine.reason(analysisPrompt, context=context, system_prompt=system_prompt)
                    return successFunc(analysisResult)
                except Exception as e:
                    # Fallback to basic analysis on error
                    return self._fallbackDocumentAnalysis(lastData, lastData.get('fileName', 'Unknown'), docType, docContent, errorFunc, successFunc)
            elif self.llmTool:
                # Fallback to old LLMTool if ReasoningEngine not available
                try:
                    analysisPrompt = f"Analyze this {docType} document and answer: {message}\n\nDocument content:\n{docContent[:5000]}"
                    if hasattr(self.llmTool, 'generateText'):
                        analysisResult = self.llmTool.generateText(analysisPrompt, maxTokens=1000)
                    else:
                        analysisResult = self.llmTool.generate(analysisPrompt, maxTokens=1000)
                    return successFunc(analysisResult)
                except Exception:
                    return self._fallbackDocumentAnalysis(lastData, lastData.get('fileName', 'Unknown'), docType, docContent, errorFunc, successFunc)
            else:
                # No LLM available - use fallback
                return self._fallbackDocumentAnalysis(lastData, lastData.get('fileName', 'Unknown'), docType, docContent, errorFunc, successFunc)
        else:
            return errorFunc("Could not extract content from document.")
    
    def _fallbackDocumentAnalysis(self, lastData: Dict, fileName: str, docType: str, docContent: Any, errorFunc, successFunc) -> Dict:
        """Fallback document analysis when LLM is unavailable"""
        from presenters.text import TextPresenter
        
        presenter = TextPresenter()
        
        # Basic analysis based on document type
        if docType == 'Excel':
            sheets = lastData.get('sheets', {})
            sheetCount = len(sheets)
            totalRows = sum(len(sheet.get('rows', [])) for sheet in sheets.values())
            
            analysis = {
                'title': f'Analysis of {fileName}',
                'sections': {
                    'Document Type': 'Excel Spreadsheet',
                    'Structure': [
                        f'Number of sheets: {sheetCount}',
                        f'Total rows: {totalRows}',
                        f'Sheets: {", ".join(sheets.keys())}'
                    ],
                    'Content Preview': 'Use "query" command to ask specific questions about the data.'
                }
            }
        elif docType == 'Word':
            paragraphs = lastData.get('paragraphs', [])
            paraCount = len(paragraphs)
            
            analysis = {
                'title': f'Analysis of {fileName}',
                'sections': {
                    'Document Type': 'Word Document',
                    'Structure': [
                        f'Number of paragraphs: {paraCount}',
                        f'Preview: {paragraphs[0][:200] if paragraphs else "No content"}...'
                    ]
                }
            }
        elif docType == 'PDF':
            pages = lastData.get('pages', [])
            pageCount = len(pages)
            
            analysis = {
                'title': f'Analysis of {fileName}',
                'sections': {
                    'Document Type': 'PDF Document',
                    'Structure': [
                        f'Number of pages: {pageCount}',
                        f'Preview: {pages[0][:200] if pages else "No content"}...'
                    ]
                }
            }
        else:
            return errorFunc("Unknown document type")
        
        formatted = presenter.present(analysis)
        content = formatted.get('content', str(formatted)) if isinstance(formatted, dict) else formatted
        return successFunc(content)
