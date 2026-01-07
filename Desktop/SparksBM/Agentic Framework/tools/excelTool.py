"""Excel file reading/writing tools"""
import os
from typing import Dict, List, Optional
import pandas as pd


class ExcelTool:
    """Tools for reading and processing Excel files"""
    
    @staticmethod
    def readExcel(filePath: str, sheetName: Optional[str] = None) -> Dict:
        """
        Read Excel file and return structured data
        
        Args:
            filePath: Path to Excel file
            sheetName: Specific sheet to read (None = all sheets)
            
        Returns:
            Dict with 'data' (list of rows) and 'sheets' info
        """
        if not os.path.exists(filePath):
            raise FileNotFoundError(f"Excel file not found: {filePath}")
        
        try:
            if sheetName:
                df = pd.read_excel(filePath, sheet_name=sheetName)
                return {
                    'data': df.to_dict('records'),
                    'sheet': sheetName,
                    'rows': len(df),
                    'columns': list(df.columns)
                }
            else:
                # Read all sheets
                excelFile = pd.ExcelFile(filePath)
                sheets = {}
                for sheet in excelFile.sheet_names:
                    df = pd.read_excel(filePath, sheet_name=sheet)
                    sheets[sheet] = {
                        'data': df.to_dict('records'),
                        'rows': len(df),
                        'columns': list(df.columns)
                    }
                
                return {
                    'sheets': sheets,
                    'sheetNames': excelFile.sheet_names
                }
        except Exception as e:
            raise RuntimeError(f"Failed to read Excel file: {e}")
    
    @staticmethod
    def extractEntities(excelData: Dict, entityType: str = "document") -> List[Dict]:
        """
        Extract entities from Excel data for Verinice
        
        Args:
            excelData: Data from readExcel
            entityType: Type of entity to extract
            
        Returns:
            List of entity dicts
        """
        entities = []
        
        # Get data from first sheet or specified structure
        if 'sheets' in excelData:
            # Multi-sheet - use first sheet
            firstSheet = list(excelData['sheets'].values())[0]
            data = firstSheet['data']
        else:
            data = excelData.get('data', [])
        
        # Convert rows to entities
        for row in data:
            entity = {
                'type': entityType,
                'name': row.get('name') or row.get('title') or f"{entityType}_{len(entities)}",
                'description': row.get('description') or '',
                'rawData': row
            }
            entities.append(entity)
        
        return entities
    
    @staticmethod
    def writeExcel(filePath: str, data: List[Dict], sheetName: str = "Sheet1"):
        """
        Write data to Excel file
        
        Args:
            filePath: Output file path
            data: List of dicts to write
            sheetName: Sheet name
        """
        df = pd.DataFrame(data)
        df.to_excel(filePath, sheet_name=sheetName, index=False)
        return {'success': True, 'filePath': filePath, 'rows': len(data)}

