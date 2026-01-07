"""Excel document handler - handles Excel-specific operations"""
from typing import Dict, Optional, List, Any
import re
import json
import os


class ExcelDocHandler:
    """Handles Excel document operations: detection, mapping, bulk import, formatting"""
    
    def __init__(self, veriniceTool=None, formatFunc=None, llmTool=None, ismsHandler=None):
        self.veriniceTool = veriniceTool
        self.formatResult = formatFunc
        self.llmTool = llmTool
        self.ismsHandler = ismsHandler
    
    def detectAssetInventory(self, excelData: Dict) -> Optional[Dict]:
        """
        Detect if Excel file contains asset inventory data using LLM
        
        Returns:
            Dict with detection result or None
        """
        if not self.llmTool:
            return None
        
        try:
            # Get sheet data
            rows = 0
            columns = []
            sampleData = None
            
            if 'sheets' in excelData:
                firstSheetName = list(excelData['sheets'].keys())[0]
                sheetData = excelData['sheets'][firstSheetName]
                columns = sheetData.get('columns', [])
                dataRows = sheetData.get('data', [])
                if isinstance(dataRows, list):
                    rows = len(dataRows)
                    if dataRows:
                        sampleData = dataRows[0] if isinstance(dataRows[0], dict) else None
                elif isinstance(sheetData.get('rows'), int):
                    rows = sheetData.get('rows', 0)
            elif 'data' in excelData:
                dataRows = excelData.get('data', [])
                if isinstance(dataRows, list):
                    rows = len(dataRows)
                    if dataRows:
                        sampleData = dataRows[0] if isinstance(dataRows[0], dict) else None
                columns = excelData.get('columns', [])
            
            if rows < 1:
                return None
            
            # Use LLM to detect if this is an asset inventory
            columnsStr = ', '.join(columns)
            sampleStr = ''
            if sampleData:
                sampleStr = f"\nSample row: {str(sampleData)[:300]}"
            
            prompt = f"""Analyze this Excel file structure and determine if it contains asset inventory data.

Columns: {columnsStr}
Total Rows: {rows}{sampleStr}

An asset inventory typically contains:
- Asset names/identifiers
- Asset types or categories
- Descriptions or details
- Owners, locations, or other asset attributes
- IP addresses, hostnames, or technical identifiers

Respond in JSON format:
{{
    "isAssetInventory": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

If it's an asset inventory, return isAssetInventory: true with confidence >= 0.7.
"""
            
            response = self.llmTool.generate(prompt, maxTokens=200)
            
            # Extract JSON from response
            jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if jsonMatch:
                result = json.loads(jsonMatch.group())
                if result.get('isAssetInventory', False) and result.get('confidence', 0) >= 0.7:
                    return {
                        'detected': True,
                        'rowCount': rows,
                        'columns': columns,
                        'confidence': result.get('confidence', 0.8)
                }
            
            return None
        except Exception:
            return None
    
    def mapColumnsToAssetFields(self, columns: List[str], sampleRow: Optional[Dict] = None) -> Dict[str, str]:
        """
        Map Excel columns to Verinice asset fields using LLM
        
        Returns:
            Dict mapping Excel column names to asset field names
        """
        if not self.llmTool:
            raise RuntimeError("LLM tool required for column mapping. Please configure GEMINI_API_KEY.")
        
            columnsStr = ', '.join(columns)
            sampleStr = ''
            if sampleRow:
                sampleStr = f"\nSample row data: {str(sampleRow)[:500]}"
            
            prompt = f"""Map these Excel column names to Verinice asset fields:

Columns: {columnsStr}{sampleStr}

Verinice asset fields:
- name (required): Asset name/identifier
- abbreviation: Asset abbreviation/short code
- description: Asset description/details
- subType: Asset type (e.g., Server, NetworkDevice, Application, etc.)
- owner: Asset owner/responsible person
- location: Physical or logical location
- ipAddress: IP address
- hostname: Hostname/FQDN
- status: Asset status

Return ONLY a JSON object mapping Excel column names to Verinice field names.
Example: {{"Name": "name", "Abbreviation": "abbreviation", "Description": "description", "Type": "subType"}}
If a column doesn't map to any field, omit it from the result.
"""
            
            response = self.llmTool.generate(prompt, maxTokens=200)
            
        # Extract JSON from response
        jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if jsonMatch:
            mapping = json.loads(jsonMatch.group())
            return mapping
        
        raise RuntimeError("Failed to extract column mapping from LLM response. Please try again.")
    
    def formatForLLM(self, data: Dict) -> str:
        """Format Excel data for LLM analysis"""
        content = []
        
        # Handle multi-sheet Excel files
        sheets = data.get('sheets', {})
        if isinstance(sheets, dict) and sheets:
            for sheetName, sheetData in sheets.items():
                content.append(f"\n{'='*60}")
                content.append(f"Sheet: {sheetName}")
                content.append(f"{'='*60}")
                
                # Get column headers
                columns = sheetData.get('columns', [])
                if columns:
                    content.append(f"Columns: {', '.join(str(col) for col in columns)}")
                
                # Get row count
                rowCount = sheetData.get('rows', 0)
                if isinstance(rowCount, int):
                    content.append(f"Total Rows: {rowCount}")
                elif isinstance(sheetData.get('data'), list):
                    rowCount = len(sheetData.get('data', []))
                    content.append(f"Total Rows: {rowCount}")
                
                # Get data rows (limit to first 100 rows for analysis)
                dataRows = sheetData.get('data', [])
                if isinstance(dataRows, list) and dataRows:
                    # Add header row
                    if columns:
                        content.append("\n" + " | ".join(str(col) for col in columns))
                        content.append("-" * 60)
                    
                    # Add data rows (limit to 100 for LLM)
                    for i, row in enumerate(dataRows[:100]):
                        if isinstance(row, dict):
                            rowStr = " | ".join(f"{k}: {v}" for k, v in list(row.items())[:10])
                            content.append(rowStr)
                        else:
                            content.append(" | ".join(str(cell) for cell in row[:10]))
                    
                    if len(dataRows) > 100:
                        content.append(f"\n... ({len(dataRows) - 100} more rows)")
        
        # Handle single-sheet Excel (data directly in result)
        elif 'data' in data:
            dataRows = data.get('data', [])
            columns = data.get('columns', [])
            
            if columns:
                content.append(f"Columns: {', '.join(str(col) for col in columns)}")
            
            if isinstance(dataRows, list) and dataRows:
                content.append(f"Total Rows: {len(dataRows)}")
                # Add header
                if columns:
                    content.append("\n" + " | ".join(str(col) for col in columns))
                    content.append("-" * 60)
                # Add rows
                for row in dataRows[:100]:
                    if isinstance(row, dict):
                        rowStr = " | ".join(f"{k}: {v}" for k, v in list(row.items())[:10])
                        content.append(rowStr)
                    else:
                        content.append(" | ".join(str(cell) for cell in row[:10]))
        
        if not content:
            return str(data)[:10000]
        
        return "\n".join(content)[:10000]
    
    def handleBulkAssetImport(self, excelData: Dict, filePath: Optional[str], state: Dict, tools: Dict, 
                             executeTool, errorFunc, successFunc) -> Optional[Dict]:
        """
        Handle bulk asset import from Excel
        
        Args:
            excelData: Excel data from state or session
            filePath: Path to Excel file (for re-reading if needed)
            state: Agent state dictionary
            tools: Available tools dictionary
            executeTool: Function to execute tools
            errorFunc: Function to return error response
            successFunc: Function to return success response
        
        Returns:
            Dict with import result or None
        """
        # Get Excel data - try to re-read if missing
        hasValidData = excelData and ('sheets' in excelData or ('data' in excelData and isinstance(excelData.get('data'), list)))
        
        if not hasValidData:
            # Try to re-read from filePath
            if not filePath:
                pendingAction = state.get('pendingFileAction')
                if pendingAction:
                    filePath = pendingAction.get('filePath')
            
            if filePath and os.path.exists(filePath):
                try:
                    if 'readExcel' in tools:
                        freshData = executeTool('readExcel', filePath=filePath)
                        if freshData and ('sheets' in freshData or 'data' in freshData):
                            excelData = freshData.copy()
                            excelData['fileName'] = excelData.get('fileName', 'document')
                            excelData['fileType'] = 'excel'
                            excelData['filePath'] = filePath
                            state['lastProcessed'] = excelData
                            hasValidData = True
                except Exception:
                    pass
            
            if not hasValidData:
                return errorFunc("Excel file data is missing. The file may have been removed or the session expired. Please re-upload the file.")
        
        # Check pending action for detection info
        pendingAction = state.get('pendingFileAction')
        skipDetection = False
        
        if pendingAction and pendingAction.get('hasAssetInventory'):
            skipDetection = True
        
        # Detect asset inventory if needed
        if not skipDetection:
            detection = self.detectAssetInventory(excelData)
            if not detection:
                return errorFunc("The uploaded Excel file doesn't appear to be an asset inventory.")
        else:
            detection = {
                'detected': True,
                'rowCount': pendingAction.get('rowCount', 0),
                'columns': [],
                'confidence': 0.9
            }
        
        # Initialize ISMS handler if needed
        if not self.ismsHandler:
            if not self.veriniceTool:
                return errorFunc('ISMS client not available. Please check your configuration.')
            from .ismsHandler import ISMSHandler
            self.ismsHandler = ISMSHandler(self.veriniceTool, self.formatResult, self.llmTool)
        
        # Get domain/unit
        domainId, unitId = self.ismsHandler._getDefaults()
        if not domainId:
            return errorFunc("No domains available. Please create a domain first.")
        
        # Get sheet data
        rows = []
        columns = []
        
        if 'sheets' in excelData:
            firstSheetName = list(excelData['sheets'].keys())[0]
            sheetData = excelData['sheets'][firstSheetName]
            columns = sheetData.get('columns', [])
            rows = sheetData.get('data', [])
        elif 'data' in excelData and isinstance(excelData['data'], list):
            columns = excelData.get('columns', [])
            rows = excelData['data']
        elif isinstance(excelData, dict):
            if 'columns' in excelData and 'rows' in excelData:
                columns = excelData.get('columns', [])
                if isinstance(excelData.get('rows'), int):
                    if 'sheets' in excelData:
                        firstSheet = list(excelData['sheets'].values())[0]
                        rows = firstSheet.get('data', [])
                    else:
                        rows = excelData.get('data', [])
                else:
                    rows = excelData.get('rows', [])
            else:
                for key, value in excelData.items():
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict):
                            rows = value
                            if value:
                                columns = list(value[0].keys())
                            break
        
        if not rows:
            return errorFunc("Excel file has no data rows. The file structure might be different than expected.")
        
        if not columns and rows:
            if isinstance(rows[0], dict):
                columns = list(rows[0].keys())
        
        # Map columns to asset fields
        columnMapping = self.mapColumnsToAssetFields(columns, rows[0] if rows else None)
        
        if 'name' not in columnMapping.values():
            for col in columns:
                colLower = str(col).lower()
                if 'name' in colLower or 'id' in colLower or 'asset' in colLower:
                    columnMapping[col] = 'name'
                    break
        
        if 'name' not in columnMapping.values():
            return errorFunc("Could not identify a 'name' column in the Excel file. Please ensure there's a column with asset names.")
        
        # Create assets via ISMS handler
        return self.ismsHandler.bulkCreateAssets(rows, columnMapping, domainId, unitId)
    
    def compareExcelFiles(self, excelData1: Dict, excelData2: Dict, fileName1: str = "File 1", fileName2: str = "File 2") -> Dict[str, Any]:
        """
        Compare two Excel files and identify differences
        
        Args:
            excelData1: First Excel file data
            excelData2: Second Excel file data
            fileName1: Name of first file
            fileName2: Name of second file
        
        Returns:
            Dict with comparison results including:
            - differences: List of differences found
            - summary: Summary statistics
            - matches: Matching rows/columns
        """
        differences = []
        summary = {
            'file1': {'rows': 0, 'columns': [], 'sheets': []},
            'file2': {'rows': 0, 'columns': [], 'sheets': []},
            'rowDifferences': 0,
            'columnDifferences': 0,
            'dataDifferences': 0
        }
        
        try:
            # Extract data from both files
            def extractSheetData(excelData):
                """Extract sheet data from Excel file"""
                sheets = {}
                if 'sheets' in excelData:
                    for sheetName, sheetData in excelData['sheets'].items():
                        columns = sheetData.get('columns', [])
                        rows = sheetData.get('data', [])
                        if not rows and isinstance(sheetData.get('rows'), int):
                            # Try to get rows from different structure
                            rows = sheetData.get('rows', [])
                        sheets[sheetName] = {
                            'columns': columns,
                            'rows': rows if isinstance(rows, list) else []
                        }
                elif 'data' in excelData:
                    # Single sheet format
                    columns = excelData.get('columns', [])
                    rows = excelData.get('data', [])
                    sheets['Sheet1'] = {
                        'columns': columns,
                        'rows': rows if isinstance(rows, list) else []
                    }
                return sheets
            
            sheets1 = extractSheetData(excelData1)
            sheets2 = extractSheetData(excelData2)
            
            # Compare sheet structure
            sheets1_names = set(sheets1.keys())
            sheets2_names = set(sheets2.keys())
            
            # Find common sheets
            commonSheets = sheets1_names & sheets2_names
            onlyInFile1 = sheets1_names - sheets2_names
            onlyInFile2 = sheets2_names - sheets1_names
            
            if onlyInFile1:
                differences.append({
                    'type': 'sheet_missing',
                    'file': fileName2,
                    'message': f"Sheet(s) '{', '.join(onlyInFile1)}' exist in {fileName1} but not in {fileName2}"
                })
            
            if onlyInFile2:
                differences.append({
                    'type': 'sheet_missing',
                    'file': fileName1,
                    'message': f"Sheet(s) '{', '.join(onlyInFile2)}' exist in {fileName2} but not in {fileName1}"
                })
            
            # Compare each common sheet
            for sheetName in commonSheets:
                sheet1 = sheets1[sheetName]
                sheet2 = sheets2[sheetName]
                
                cols1 = sheet1['columns']
                cols2 = sheet2['columns']
                rows1 = sheet1['rows']
                rows2 = sheet2['rows']
                
                # Update summary
                summary['file1']['rows'] += len(rows1)
                summary['file2']['rows'] += len(rows2)
                summary['file1']['columns'].extend(cols1)
                summary['file2']['columns'].extend(cols2)
                
                # Compare columns
                cols1_set = set(str(c).lower() for c in cols1)
                cols2_set = set(str(c).lower() for c in cols2)
                
                missingInFile2 = cols1_set - cols2_set
                missingInFile1 = cols2_set - cols1_set
                commonCols = cols1_set & cols2_set
                
                if missingInFile2:
                    differences.append({
                        'type': 'column_missing',
                        'sheet': sheetName,
                        'file': fileName2,
                        'message': f"Column(s) '{', '.join(missingInFile2)}' exist in {fileName1} but not in {fileName2}",
                        'columns': list(missingInFile2)
                    })
                    summary['columnDifferences'] += len(missingInFile2)
                
                if missingInFile1:
                    differences.append({
                        'type': 'column_missing',
                        'sheet': sheetName,
                        'file': fileName1,
                        'message': f"Column(s) '{', '.join(missingInFile1)}' exist in {fileName2} but not in {fileName1}",
                        'columns': list(missingInFile1)
                    })
                    summary['columnDifferences'] += len(missingInFile1)
                
                # Compare row counts
                if len(rows1) != len(rows2):
                    differences.append({
                        'type': 'row_count',
                        'sheet': sheetName,
                        'message': f"Row count mismatch: {fileName1} has {len(rows1)} rows, {fileName2} has {len(rows2)} rows",
                        'file1_rows': len(rows1),
                        'file2_rows': len(rows2)
                    })
                    summary['rowDifferences'] += abs(len(rows1) - len(rows2))
                
                # Compare data rows (if both have same columns)
                if commonCols and rows1 and rows2:
                    # Find a key column for matching rows (prefer 'name', 'id', or first column)
                    keyColumn = None
                    for col in cols1:
                        colLower = str(col).lower()
                        if 'name' in colLower or 'id' in colLower or 'identifier' in colLower:
                            keyColumn = col
                            break
                    if not keyColumn and cols1:
                        keyColumn = cols1[0]
                    
                    if keyColumn:
                        # Build index of rows by key column
                        def buildRowIndex(rows, columns, keyCol):
                            index = {}
                            keyColIdx = None
                            for idx, col in enumerate(columns):
                                if str(col).lower() == str(keyCol).lower():
                                    keyColIdx = idx
                                    break
                            
                            if keyColIdx is not None:
                                for rowIdx, row in enumerate(rows):
                                    if isinstance(row, dict):
                                        key = str(row.get(keyCol, f"row_{rowIdx}")).lower()
                                    elif isinstance(row, list) and keyColIdx < len(row):
                                        key = str(row[keyColIdx]).lower()
                                    else:
                                        key = f"row_{rowIdx}"
                                    index[key] = row
                            return index
                        
                        index1 = buildRowIndex(rows1, cols1, keyColumn)
                        index2 = buildRowIndex(rows2, cols2, keyColumn)
                        
                        # Find rows only in file1
                        onlyInFile1_keys = set(index1.keys()) - set(index2.keys())
                        if onlyInFile1_keys:
                            differences.append({
                                'type': 'row_missing',
                                'sheet': sheetName,
                                'file': fileName2,
                                'message': f"{len(onlyInFile1_keys)} row(s) exist in {fileName1} but not in {fileName2}",
                                'count': len(onlyInFile1_keys),
                                'sample_keys': list(onlyInFile1_keys)[:5]
                            })
                            summary['dataDifferences'] += len(onlyInFile1_keys)
                        
                        # Find rows only in file2
                        onlyInFile2_keys = set(index2.keys()) - set(index1.keys())
                        if onlyInFile2_keys:
                            differences.append({
                                'type': 'row_missing',
                                'sheet': sheetName,
                                'file': fileName1,
                                'message': f"{len(onlyInFile2_keys)} row(s) exist in {fileName2} but not in {fileName1}",
                                'count': len(onlyInFile2_keys),
                                'sample_keys': list(onlyInFile2_keys)[:5]
                            })
                            summary['dataDifferences'] += len(onlyInFile2_keys)
                        
                        # Compare common rows for data differences
                        commonKeys = set(index1.keys()) & set(index2.keys())
                        dataDiffs = []
                        
                        for key in list(commonKeys)[:100]:  # Limit to first 100 for performance
                            row1 = index1[key]
                            row2 = index2[key]
                            
                            # Compare cell values
                            if isinstance(row1, dict) and isinstance(row2, dict):
                                for col in commonCols:
                                    val1 = row1.get(col, '')
                                    val2 = row2.get(col, '')
                                    if str(val1).strip() != str(val2).strip():
                                        dataDiffs.append({
                                            'key': key,
                                            'column': col,
                                            'file1_value': val1,
                                            'file2_value': val2
                                        })
                                        if len(dataDiffs) >= 20:  # Limit differences reported
                                            break
                            elif isinstance(row1, list) and isinstance(row2, list):
                                # Compare by column index
                                for colIdx, col in enumerate(cols1):
                                    if str(col).lower() in commonCols:
                                        val1 = row1[colIdx] if colIdx < len(row1) else ''
                                        val2 = row2[colIdx] if colIdx < len(row2) else ''
                                        if str(val1).strip() != str(val2).strip():
                                            dataDiffs.append({
                                                'key': key,
                                                'column': col,
                                                'file1_value': val1,
                                                'file2_value': val2
                                            })
                                            if len(dataDiffs) >= 20:
                                                break
                            
                            if len(dataDiffs) >= 20:
                                break
                        
                        if dataDiffs:
                            differences.append({
                                'type': 'data_difference',
                                'sheet': sheetName,
                                'message': f"Found {len(dataDiffs)} data value differences in common rows",
                                'differences': dataDiffs[:10],  # Show first 10
                                'total_differences': len(dataDiffs)
                            })
                            summary['dataDifferences'] += len(dataDiffs)
            
            # Update summary with unique columns
            summary['file1']['columns'] = list(set(summary['file1']['columns']))
            summary['file2']['columns'] = list(set(summary['file2']['columns']))
            
            return {
                'success': True,
                'differences': differences,
                'summary': summary,
                'file1_name': fileName1,
                'file2_name': fileName2,
                'total_differences': len(differences)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Error comparing files: {str(e)}",
                'differences': [],
                'summary': summary
            }

