"""Verinice ISMS integration tools - CRUD operations for all object types"""
import sys
import os
from typing import Dict, List, Optional, Any

# Import path utilities and settings
from utils.pathUtils import find_sparksbm_scripts_path, add_to_python_path
from config.settings import Settings

# Add scripts to path for SparksBMClient
SPARKSBM_SCRIPTS_PATH = find_sparksbm_scripts_path()
if SPARKSBM_SCRIPTS_PATH:
    add_to_python_path(SPARKSBM_SCRIPTS_PATH)

try:
    from sparksbmMgmt import SparksBMClient, SparksBMObjectManager, SparksBMUnitManager, SparksBMDomainManager, API_URL
    VERINICE_AVAILABLE = True
    # Use API_URL from sparksbmMgmt if available, otherwise use Settings
    if not API_URL or API_URL == "http://localhost:8070":
        API_URL = Settings.VERINICE_API_URL
except ImportError:
    VERINICE_AVAILABLE = False
    SparksBMClient = None  # type: ignore
    SparksBMObjectManager = None  # type: ignore
    SparksBMUnitManager = None  # type: ignore
    SparksBMDomainManager = None  # type: ignore
    API_URL = Settings.VERINICE_API_URL


class VeriniceTool:
    """Tools for interacting with Verinice ISMS - Full CRUD operations"""
    
    # Object type mappings
    OBJECT_TYPES = {
        "scope": "scopes",
        "asset": "assets",
        "control": "controls",
        "process": "processes",
        "person": "persons",
        "scenario": "scenarios",
        "incident": "incidents",
        "document": "documents"
    }
    
    def __init__(self):
        """Initialize Verinice tool with SparksBM client"""
        self.client = None
        self.objectManager = None
        self.unitManager = None
        self.domainManager = None
        
        if VERINICE_AVAILABLE:
            # Retry authentication up to 3 times with delays
            import time
            max_retries = 3
            retry_delay = 2  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Suppress print output during initialization
                    import io
                    import contextlib
                    f = io.StringIO()
                    with contextlib.redirect_stdout(f):
                        self.client = SparksBMClient()
                    if self.client and self.client.accessToken:
                        self.objectManager = SparksBMObjectManager(self.client)
                        self.unitManager = SparksBMUnitManager(self.client)
                        if SparksBMDomainManager:
                            self.domainManager = SparksBMDomainManager(self.client)
                        break  # Success, exit retry loop
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                    else:
                        self.client = None
    
    def _checkClient(self) -> bool:
        """Check if client is available - tries to ensure authentication"""
        return self._ensureAuthenticated()
    
    def _ensureAuthenticated(self) -> bool:
        """Ensure client is authenticated, refresh token if expired"""
        # If client doesn't exist, try to initialize it
        if not self.client and VERINICE_AVAILABLE:
            try:
                import io
                import contextlib
                f = io.StringIO()
                with contextlib.redirect_stdout(f):
                    self.client = SparksBMClient()
                if self.client and self.client.accessToken:
                    # Ensure ObjectManager is created
                    if not self.objectManager:
                        self.objectManager = SparksBMObjectManager(self.client)
                    if not self.unitManager:
                        self.unitManager = SparksBMUnitManager(self.client)
                    if SparksBMDomainManager and not self.domainManager:
                        self.domainManager = SparksBMDomainManager(self.client)
            except Exception:
                pass
        
        # If client exists but ObjectManager doesn't, create it
        if self.client and self.client.accessToken and not self.objectManager:
            try:
                    self.objectManager = SparksBMObjectManager(self.client)
                    self.unitManager = SparksBMUnitManager(self.client)
                    if SparksBMDomainManager:
                        self.domainManager = SparksBMDomainManager(self.client)
            except Exception:
                pass
        
        if not self.client:
            return False
        
        # Check if token exists
        if not self.client.accessToken:
            # Try to re-authenticate
            if hasattr(self.client, 'getAccessToken'):
                try:
                    self.client.getAccessToken()
                except Exception:
                    return False
            return self.client.accessToken is not None
        
        # Token exists, but might be expired - test it
        try:
            # Use session to make request (has auth headers)
            response = self.client.session.get(f"{self.client.apiUrl}/domains", timeout=5)
            if response.status_code == 401:
                # Token expired, re-authenticate
                if hasattr(self.client, 'getAccessToken'):
                    try:
                        self.client.getAccessToken()
                        return self.client.accessToken is not None
                    except Exception:
                        return False
                return False
            return True
        except Exception as e:
            # Network error or other issue
            return False
    
    # ==================== CREATE OPERATIONS ====================
    
    def createObject(self, objectType: str, domainId: str, unitId: str, 
                    name: str, subType: Optional[str] = None,
                    description: str = "", abbreviation: Optional[str] = None) -> Dict:
        """
        Create an object in Verinice
        
        Args:
            objectType: Type of object (scope, asset, control, process, person, scenario, incident, document)
            domainId: Domain ID
            unitId: Unit ID
            name: Object name
            subType: Optional subType (will use first available if not provided)
            description: Optional description
        
        Returns:
            Dict with success status and data or error
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.objectManager:
            return {'success': False, 'error': 'Object manager not initialized'}
        
        try:
            result = self.objectManager.createObject(
                object_type=objectType,
                name=name,
                domain_id=domainId,
                unit_id=unitId,
                description=description,
                sub_type=subType,
                abbreviation=abbreviation,
                unit_manager=self.unitManager
            )
            
            if result:
                # Use the name parameter we passed, not from result (result doesn't have name)
                return {
                    'success': True,
                    'data': result,
                    'objectId': result.get('resourceId') or result.get('id'),
                    'objectType': objectType,
                    'objectName': name  # Use the name parameter passed to createObject
                }
            else:
                return {'success': False, 'error': 'Failed to create object - check error messages'}
        except Exception as e:
            errorMsg = str(e)
            # Try to extract more details from the exception
            serverResponse = None
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                serverResponse = e.response.text
                errorMsg += f"\n   Server response: {serverResponse[:300]}"
            elif hasattr(e, 'args') and len(e.args) > 0:
                errorMsg += f"\n   Details: {str(e.args[0])[:300]}"
            
            # Check if it's a 500 error (backend issue)
            if '500' in errorMsg or 'Internal Server Error' in errorMsg:
                errorMsg += "\n   [Note: This is a Verinice backend error, not an agent issue]"
                errorMsg += "\n   Check Verinice backend logs for detailed error information"
            
            return {'success': False, 'error': f'Exception creating object: {errorMsg}'}
    
    # ==================== READ OPERATIONS ====================
    
    def listObjects(self, objectType: str, domainId: Optional[str] = None, filters: Optional[Dict] = None, unitId: Optional[str] = None) -> Dict:
        """
        List objects of a specific type in a domain or unit
        
        Args:
            objectType: Type of object (scope, asset, control, process, person, scenario, incident, document)
            domainId: Domain ID (optional for scopes - can list at unit level)
            filters: Optional filters (subType, status, etc. - passed as query parameters)
            unitId: Unit ID (optional, used for scopes when domainId is not available)
        
        Returns:
            Dict with success status and list of objects
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.objectManager:
            return {'success': False, 'error': 'Object manager not initialized'}
        
        plural = self.OBJECT_TYPES.get(objectType.lower())
        if not plural:
            return {
                'success': False,
                'error': f'Unknown object type: {objectType}. Available types: {", ".join(self.OBJECT_TYPES.keys())}'
            }
        
        try:
            # For scopes, can list at unit level if no domain
            if objectType.lower() == 'scope' and not domainId:
                if unitId:
                    # List scopes at unit level
                    url = f"{API_URL}/units/{unitId}/scopes"
                else:
                    # Try to get unit first
                    unitsResult = self.listUnits()
                    if unitsResult.get('success') and unitsResult.get('units'):
                        unitId = unitsResult['units'][0].get('id')
                        url = f"{API_URL}/units/{unitId}/scopes"
                    else:
                        return {'success': False, 'error': 'No unit available to list scopes'}
            elif domainId:
                # Use direct API call to support filters
                url = f"{API_URL}/domains/{domainId}/{plural}"
            else:
                return {'success': False, 'error': 'Domain ID or Unit ID required to list objects'}
            params = {}
            if filters:
                # Add filter parameters
                for key, value in filters.items():
                    if value is not None:
                        params[key] = value
            
            response = self.client.makeRequest('GET', url, params=params if params else None)
            response.raise_for_status()
            
            objects = response.json()
            # Handle paginated response - keep structure consistent
            if isinstance(objects, dict):
                if 'items' in objects:
                    # Keep the dict structure with 'items' key
                    objects = objects
                elif 'content' in objects:
                    objects = {'items': objects['content']}
                else:
                    # Convert to standard format
                    objects = {'items': []}
            elif isinstance(objects, list):
                # Convert list to standard format
                objects = {'items': objects}
            else:
                objects = {'items': []}
            
            items = objects.get('items', []) if isinstance(objects, dict) else []
            return {
                'success': True,
                'count': len(items),
                'objects': objects,  # Keep as dict with 'items' key for consistency
                'objectType': objectType,
                'domainId': domainId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                errorMsg = f'HTTP {e.response.status_code}: {e.response.text[:200]}'
            return {'success': False, 'error': f'Exception listing objects: {errorMsg}'}
    
    def getObject(self, objectType: str, domainId: str, objectId: str) -> Dict:
        """
        Get a specific object by ID - backend uses top-level /{plural}/{uuid} endpoint
        
        Args:
            objectType: Type of object (scope, asset, control, process, person, scenario, incident, document)
            domainId: Domain ID (not used for GET - kept for compatibility)
            objectId: Object ID
        
        Returns:
            Dict with success status and object data
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        plural = self.OBJECT_TYPES.get(objectType.lower())
        if not plural:
            return {
                'success': False, 
                'error': f'Unknown object type: {objectType}. Available types: {", ".join(self.OBJECT_TYPES.keys())}'
            }
        
        try:
            # Backend uses top-level endpoint: /{plural}/{uuid}
            url = f"{API_URL}/{plural}/{objectId}"
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            objectData = response.json()
            return {
                'success': True,
                'data': objectData,
                'objectId': objectId,
                'objectType': objectType,
                'domainId': domainId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    errorMsg = f'{objectType} not found'
                elif status_code == 403:
                    errorMsg = f'Access forbidden: You may not have permission to view this {objectType}'
                else:
                    error_text = e.response.text[:300] if hasattr(e.response, 'text') else str(e.response.content[:300])
                    errorMsg = f'HTTP {status_code}: {error_text}'
            return {'success': False, 'error': f'Failed to get {objectType}: {errorMsg}'}
    
    # ==================== UPDATE OPERATIONS ====================
    
    def updateObject(self, objectType: str, domainId: str, objectId: str, 
                    data: Dict) -> Dict:
        """
        Update an object - properly handles PUT by getting full object first
        
        Args:
            objectType: Type of object
            domainId: Domain ID
            objectId: Object ID
            data: Dictionary of fields to update
        
        Returns:
            Dict with success status and updated object data
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        plural = self.OBJECT_TYPES.get(objectType.lower())
        if not plural:
            return {'success': False, 'error': f'Unknown object type: {objectType}'}
        
        try:
            # Step 1: GET the current object (PUT requires full object)
            getResult = self.getObject(objectType, domainId, objectId)
            if not getResult.get('success'):
                return getResult  # Return the error
            
            # Step 2: Use full object from GET, update only specified fields
            # InDomain PUT requires complete object with all nested structures
            fullObject = getResult['data'].copy()
            
            # Merge user's updates
            fullObject.update(data)
            
            # Remove read-only fields backend rejects
            readOnlyFields = ['createdAt', 'createdBy', 'updatedAt', 'updatedBy', 'id', 'type', '_self', 'resourceId']
            for field in readOnlyFields:
                fullObject.pop(field, None)
            
            # Step 3: PUT the complete updated object
            # Backend InDomain controller requires ALL fields: /domains/{domainId}/{plural}/{uuid}
            url = f"{API_URL}/domains/{domainId}/{plural}/{objectId}"
            response = self.client.makeRequest('PUT', url, json=fullObject)
            response.raise_for_status()
            
            updatedData = response.json()
            return {
                'success': True,
                'data': updatedData,
                'objectId': objectId,
                'objectType': objectType
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    errorMsg = f'{objectType} not found'
                else:
                    errorMsg = f'HTTP {e.response.status_code}: {e.response.text[:200]}'
            return {'success': False, 'error': f'Failed to update {objectType}: {errorMsg}'}
    
    # ==================== DELETE OPERATIONS ====================
    
    def deleteObject(self, objectType: str, domainId: str, objectId: str) -> Dict:
        """
        Delete an object - backend uses top-level /{plural}/{uuid} endpoint for ALL objects
        
        Args:
            objectType: Type of object
            domainId: Domain ID (not used for DELETE - kept for compatibility)
            objectId: Object ID
        
        Returns:
            Dict with success status
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        plural = self.OBJECT_TYPES.get(objectType.lower())
        if not plural:
            return {'success': False, 'error': f'Unknown object type: {objectType}'}
        
        try:
            # Backend uses top-level endpoint for DELETE: /{plural}/{uuid}
            # This applies to ALL object types (scopes, assets, controls, etc.)
            url = f"{API_URL}/{plural}/{objectId}"
            response = self.client.makeRequest('DELETE', url)
            
            if response.status_code in [200, 204]:
                return {
                    'success': True,
                    'message': f'Deleted {objectType} successfully',
                    'objectId': objectId,
                    'objectType': objectType
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text[:200]}'
                }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    errorMsg = f'{objectType} not found'
                else:
                    errorMsg = f'HTTP {e.response.status_code}: {e.response.text[:200]}'
            return {'success': False, 'error': f'Failed to delete {objectType}: {errorMsg}'}
    
    # ==================== REPORT OPERATIONS ====================
    
    def listReports(self, domainId: Optional[str] = None) -> Dict:
        """
        List available reports for a domain (or all reports if domainId not provided)
        
        Args:
            domainId: Optional Domain ID (for filtering, but reports are global)
        
        Returns:
            Dict with success status and list of reports
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        try:
            # Use direct API call since reports endpoint is global
            url = f"{API_URL}/api/reporting/reports"
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            reports = response.json()
            # Handle both dict format (from our controller) and list format
            if isinstance(reports, dict):
                # Convert dict of reports to list format
                reports_list = []
                for report_id, report_data in reports.items():
                    report_entry = {
                        'id': report_id,
                        **report_data
                    }
                    reports_list.append(report_entry)
                reports = reports_list
            
            return {
                'success': True,
                'count': len(reports),
                'reports': reports,
                'domainId': domainId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                errorMsg = f'HTTP {e.response.status_code}: {e.response.text[:200]}'
            return {'success': False, 'error': f'Exception listing reports: {errorMsg}'}
    
    def generateReport(self, reportId: str, domainId: Optional[str] = None, params: Optional[Dict] = None) -> Dict:
        """
        Generate a report
        
        Args:
            reportId: Report ID (e.g., 'inventory-of-assets', 'risk-assessment', 'statement-of-applicability')
            domainId: Optional Domain ID (for context, but reports are generated globally)
            params: Optional report parameters (outputType, language, targets, timeZone)
        
        Returns:
            Dict with success status and report data/URL
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        try:
            # Report generation endpoint matches frontend expectation
            url = f"{API_URL}/api/reporting/reports/{reportId}"
            payload = params or {}
            payload['outputType'] = payload.get('outputType', 'application/pdf')
            payload['language'] = payload.get('language', 'en')
            payload['targets'] = payload.get('targets', [])
            payload['timeZone'] = payload.get('timeZone', 'UTC')
            
            # Make POST request - expect binary PDF response
            response = self.client.makeRequest('POST', url, json=payload)
            response.raise_for_status()
            
            # Check if response is PDF (binary)
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' in content_type or 'pdf' in content_type.lower() or response.content[:4] == b'%PDF':
                # Return PDF data as base64 for transmission
                import base64
                pdf_data = response.content
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                return {
                    'success': True,
                    'reportId': reportId,
                    'domainId': domainId,
                    'format': 'pdf',
                    'data': pdf_base64,
                    'size': len(pdf_data),
                    'message': f'Report "{reportId}" generated successfully ({len(pdf_data)} bytes). PDF data available in base64 format.'
                }
            else:
                # Try JSON response
                try:
                    result = response.json()
                    return {
                        'success': True,
                        'data': result,
                        'reportId': reportId,
                        'domainId': domainId
                    }
                except:
                    # Return raw response
                    return {
                        'success': True,
                        'data': response.text[:500] if hasattr(response, 'text') else str(response.content[:500]),
                        'reportId': reportId,
                        'domainId': domainId,
                        'message': 'Report generated but response format is not PDF or JSON'
                    }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                error_text = e.response.text[:300] if hasattr(e.response, 'text') else str(e.response.content[:300])
                errorMsg = f'HTTP {status_code}: {error_text}'
                if status_code == 404:
                    errorMsg += f'\n   Report ID "{reportId}" not found. Available reports: inventory-of-assets, risk-assessment, statement-of-applicability'
            return {'success': False, 'error': f'Failed to generate report: {errorMsg}'}
    
    # ==================== ANALYSIS OPERATIONS ====================
    
    def analyzeObject(self, domainId: str, objectId: str, objectType: str) -> Dict:
        """
        Analyze an object using LLM (requires LLM tool)
        
        Args:
            domainId: Domain ID
            objectId: Object ID
            objectType: Type of object
        
        Returns:
            Dict with success status and analysis result
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        try:
            # Get object data first
            objectResult = self.getObject(objectType, domainId, objectId)
            if not objectResult.get('success'):
                return objectResult
            
            objectData = objectResult.get('data', {})
            
            # Return object data for LLM analysis (LLM tool will handle actual analysis)
            return {
                'success': True,
                'data': objectData,
                'objectId': objectId,
                'objectType': objectType,
                'readyForAnalysis': True
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception analyzing object: {str(e)}'}
    
    # ==================== HELPER METHODS ====================
    
    def getValidSubTypes(self, domainId: str, objectType: str) -> Dict:
        """
        Get valid subTypes for an object type in a domain
        
        Args:
            domainId: Domain ID
            objectType: Type of object
        
        Returns:
            Dict with success status and list of valid subTypes
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.objectManager:
            return {'success': False, 'error': 'Object manager not initialized'}
        
        try:
            subTypes = self.objectManager.getValidSubTypes(domainId, objectType)
            return {
                'success': True,
                'subTypes': subTypes,
                'objectType': objectType,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception getting subTypes: {str(e)}'}
    
    def listDomains(self) -> Dict:
        """List all available domains"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        try:
            from sparksbmMgmt import SparksBMDomainManager
            domainManager = SparksBMDomainManager(self.client)
            domains = domainManager.listDomains()
            return {
                'success': True,
                'count': len(domains),
                'domains': domains
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception listing domains: {str(e)}'}
    
    def listUnits(self) -> Dict:
        """List all available units"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.unitManager:
            return {'success': False, 'error': 'Unit manager not initialized'}
        
        try:
            units = self.unitManager.listUnits()
            return {
                'success': True,
                'count': len(units),
                'units': units
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception listing units: {str(e)}'}
    
    # ==================== DOMAIN MANAGEMENT ====================
    
    def createDomain(self, templateId: str) -> Dict:
        """Create domain from template"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.domainManager:
            return {'success': False, 'error': 'Domain manager not initialized'}
        
        try:
            # createDomainFromTemplate returns bool, not domain object
            success = self.domainManager.createDomainFromTemplate(templateId)
            if success:
                # Fetch the newly created domain by listing all domains and finding the latest
                # or by template ID (domains created from same template might have similar names)
                domains = self.domainManager.listDomains()
                if domains:
                    # Find domain created from this template (most recent or matching template)
                    # For now, return success with template info
                    return {
                        'success': True,
                        'message': f'Domain created successfully from template {templateId}',
                        'templateId': templateId,
                        'totalDomains': len(domains)
                    }
                return {
                    'success': True,
                    'message': f'Domain created successfully from template {templateId}',
                    'templateId': templateId
                }
            return {'success': False, 'error': 'Failed to create domain (may already exist or template not found)'}
        except Exception as e:
            return {'success': False, 'error': f'Exception creating domain: {str(e)}'}
    
    def deleteDomain(self, domainId: str) -> Dict:
        """Delete a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.domainManager:
            return {'success': False, 'error': 'Domain manager not initialized'}
        
        try:
            result = self.domainManager.deleteDomain(domainId)
            return {
                'success': result,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception deleting domain: {str(e)}'}
    
    def getDomainTemplates(self) -> Dict:
        """Get available domain templates"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.domainManager:
            return {'success': False, 'error': 'Domain manager not initialized'}
        
        try:
            templates = self.domainManager.getDomainTemplates()
            return {
                'success': True,
                'count': len(templates),
                'templates': templates
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception getting templates: {str(e)}'}
    
    def getDomainSubTypes(self, domainId: str, objectType: str = None) -> Dict:
        """Get subtypes for a domain (all types or specific type)"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.objectManager:
            return {'success': False, 'error': 'Object manager not initialized'}
        
        try:
            if objectType:
                subtypes = self.objectManager.getValidSubTypes(domainId, objectType)
                return {
                    'success': True,
                    'objectType': objectType,
                    'subTypes': subtypes,
                    'count': len(subtypes)
                }
            else:
                # Get all subtypes for all object types
                object_types = ['scope', 'asset', 'control', 'process', 'person', 'scenario', 'incident', 'document']
                all_subtypes = {}
                for obj_type in object_types:
                    subtypes = self.objectManager.getValidSubTypes(domainId, obj_type)
                    if subtypes:
                        all_subtypes[obj_type] = subtypes
                return {
                    'success': True,
                    'subTypes': all_subtypes,
                    'totalCount': sum(len(v) for v in all_subtypes.values())
                }
        except Exception as e:
            return {'success': False, 'error': f'Exception getting subtypes: {str(e)}'}
    
    # ==================== UNIT MANAGEMENT ====================
    
    def createUnit(self, name: str, description: str = "", domainIds: List[str] = None) -> Dict:
        """Create a new unit"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.unitManager:
            return {'success': False, 'error': 'Unit manager not initialized'}
        
        try:
            result = self.unitManager.createUnit(name, description, domainIds)
            if result:
                return {
                    'success': True,
                    'unitId': result.get('id'),
                    'unit': result
                }
            return {'success': False, 'error': 'Failed to create unit'}
        except Exception as e:
            return {'success': False, 'error': f'Exception creating unit: {str(e)}'}
    
    # ==================== RISK DEFINITIONS ====================
    
    def listRiskDefinitions(self, domainId: str) -> Dict:
        """List risk definitions in a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.objectManager:
            return {'success': False, 'error': 'Object manager not initialized'}
        
        try:
            risk_defs = self.objectManager.listRiskDefinitions(domainId)
            return {
                'success': True,
                'count': len(risk_defs),
                'riskDefinitions': risk_defs,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception listing risk definitions: {str(e)}'}
    
    # ==================== PROFILE MANAGEMENT ====================
    
    def listProfiles(self, domainId: str) -> Dict:
        """List profiles in a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.domainManager:
            return {'success': False, 'error': 'Domain manager not initialized'}
        
        try:
            profiles = self.domainManager.listProfiles(domainId)
            return {
                'success': True,
                'count': len(profiles),
                'profiles': profiles,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception listing profiles: {str(e)}'}
    
    def getDomain(self, domainId: str) -> Dict:
        """Get detailed information about a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        try:
            response = self.client.makeRequest('GET', f"{API_URL}/domains/{domainId}")
            response.raise_for_status()
            domain = response.json()
            return {
                'success': True,
                'domain': domain,
                'domainId': domainId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    errorMsg = f'Domain {domainId} not found'
                else:
                    error_text = e.response.text[:300] if hasattr(e.response, 'text') else str(e.response.content[:300])
                    errorMsg = f'HTTP {status_code}: {error_text}'
            return {'success': False, 'error': f'Failed to get domain: {errorMsg}'}
    
    def getUnit(self, unitId: str) -> Dict:
        """Get detailed information about a unit"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.unitManager:
            return {'success': False, 'error': 'Unit manager not initialized'}
        
        try:
            response = self.client.makeRequest('GET', f"{API_URL}/units/{unitId}")
            response.raise_for_status()
            unit = response.json()
            return {
                'success': True,
                'unit': unit,
                'unitId': unitId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    errorMsg = f'Unit {unitId} not found'
                else:
                    error_text = e.response.text[:300] if hasattr(e.response, 'text') else str(e.response.content[:300])
                    errorMsg = f'HTTP {status_code}: {error_text}'
            return {'success': False, 'error': f'Failed to get unit: {errorMsg}'}
    
    def listCatalogItems(self, domainId: str) -> Dict:
        """List catalog items in a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.objectManager:
            return {'success': False, 'error': 'Object manager not initialized'}
        
        try:
            catalog_items = self.objectManager.listCatalogItems(domainId)
            return {
                'success': True,
                'count': len(catalog_items),
                'catalogItems': catalog_items,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception listing catalog items: {str(e)}'}
    
    def checkTemplateCompleteness(self, templateId: str) -> Dict:
        """Check if a domain template is complete (has all subTypes)"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': 'ISMS client not available. Please ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials in SparksbmISMS/scripts/sparksbmMgmt.py are correct'
            }
        
        if not self.domainManager:
            return {'success': False, 'error': 'Domain manager not initialized'}
        
        try:
            result = self.domainManager.checkTemplateCompleteness(templateId)
            return {
                'success': True,
                'templateId': templateId,
                'completeness': result
            }
        except Exception as e:
            return {'success': False, 'error': f'Exception checking template: {str(e)}'}
