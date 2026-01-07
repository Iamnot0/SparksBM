"""
ISMS Coordinator - Phase 4 Refactoring

Coordinates all ISMS operations including CRUD, reports, and follow-ups.
Follows the DocumentCoordinator pattern established in Phase 2.

Status: ISOLATION BUILD - NOT CONNECTED TO PRODUCTION
Feature Flag: _useIsmsCoordinator = False (when integrated)
"""

from typing import Dict, Optional, List, Any
import re


class ISMSCoordinator:
    """
    Coordinates all ISMS operations with clean separation of concerns.
    
    Replaces ISMSHandler with a coordinator pattern matching DocumentCoordinator.
    Handles CRUD operations, report generation, and follow-ups.
    """
    
    def __init__(self, state: Dict, tools: Dict, contextManager=None):
        """
        Initialize ISMS Coordinator with explicit dependencies.
        
        Args:
            state: Agent state dictionary (passed by reference)
            tools: Dictionary of available tools
            contextManager: Optional context manager for session data
        
        Example:
            tools = {
                'veriniceTool': veriniceTool,
                'llmTool': llmTool  # optional
            }
            coordinator = ISMSCoordinator(agent.state, tools)
        """
        self.state = state
        self.veriniceTool = tools.get('veriniceTool')
        self.llmTool = tools.get('llmTool')
        self.contextManager = contextManager
        
        # Internal handler (lazy initialization)
        self._ismsHandler = None
        
        # Caches (from ISMSHandler)
        self._domainCache = None
        self._unitCache = None
    
    # ==================== PUBLIC INTERFACE ====================
    
    def handleOperation(self, operation: str, objectType: str, message: str) -> Dict:
        """
        Handle ISMS CRUD operations (main entry point).
        
        Replaces ISMSHandler.execute()
        
        Args:
            operation: Operation type (create, list, get, update, delete)
            objectType: ISMS object type (asset, scope, person, etc.)
            message: User's original message
        
        Returns:
            Dict with response data:
            {
                'type': 'success' | 'error',
                'text': str,  # Response message
                'data': dict  # Optional operation results
            }
        
        Examples:
            # Create operation
            result = coordinator.handleOperation('create', 'asset', 'create asset MyAsset')
            
            # List operation
            result = coordinator.handleOperation('list', 'scopes', 'list scopes')
            
            # Get operation
            result = coordinator.handleOperation('get', 'asset', 'get asset MyAsset')
        
        Raises:
            None - returns error dict instead
        """
        # Get domain/unit (cached)
        domainId, unitId = self._getDefaults()
        
        # Allow listing scopes without domain (scopes can be listed at unit level)
        # Allow listing domains without requiring a domain
        requiresDomain = operation != 'list_domains' and not (operation == 'list' and objectType == 'scope')
        
        if not domainId and requiresDomain:
            return self._error("No domains available. Please create a domain first.")
        
        # Dispatch to operation handler
        handlers = {
            'create': self._handleCreate,
            'list': self._handleList,
            'get': self._handleGet,
            'view': self._handleGet,  # view = get
            'update': self._handleUpdate,
            'delete': self._handleDelete,
            'analyze': self._handleAnalyze
        }
        
        handler = handlers.get(operation)
        if not handler:
            return self._error(f"Unknown operation: {operation}")
        
        return handler(objectType, message, domainId, unitId)
    
    def handleReportGeneration(self, command: Dict, message: str) -> Dict:
        """
        Handle report generation requests.
        
        Lists available scopes and stores pending state for user selection.
        
        Args:
            command: Dict with reportType (e.g., {'reportType': 'inventory-of-assets'})
            message: User's original message
        
        Returns:
            Dict with response:
            {
                'type': 'text',
                'text': str,  # List of scopes for selection
                'data': {
                    'pendingReportGeneration': {
                        'reportType': str,
                        'scopes': list
                    }
                }
            }
        
        Side Effects:
            Sets self.state['pendingReportGeneration']
        
        Example:
            command = {'reportType': 'inventory-of-assets'}
            result = coordinator.handleReportGeneration(command, message)
        """
        # TODO: Implement (port from MainAgent._handleReportGeneration)
        # For now, return placeholder
        return self._error("Report generation not yet implemented in coordinator (Phase 4 in progress)")
    
    def handleReportFollowUp(self, message: str) -> Dict:
        """
        Handle report generation follow-up (scope selection).
        
        Processes user's scope selection and generates the report.
        
        Args:
            message: User's scope selection (e.g., "1" or "MyScope")
        
        Returns:
            Dict with report data:
            {
                'type': 'report',
                'text': str,  # Success message
                'report': {
                    'format': 'pdf',
                    'data': str,  # Base64 encoded PDF
                    'reportType': str,
                    'scope': str
                }
            }
        
        Side Effects:
            Clears self.state['pendingReportGeneration']
        
        Prerequisites:
            Must have self.state['pendingReportGeneration'] set
        
        Raises:
            Returns error dict if:
            - No pending report generation
            - Invalid scope selection
            - Report generation fails
        """
        # TODO: Implement (port from MainAgent._handleReportGenerationFollowUp)
        # For now, return placeholder
        return self._error("Report follow-up not yet implemented in coordinator (Phase 4 in progress)")
    
    def handleSubtypeFollowUp(self, message: str) -> Optional[Dict]:
        """
        Handle subtype selection follow-up.
        
        Completes pending creation operations that require subtype selection.
        
        Args:
            message: User's subtype selection (e.g., "2" or "AST_IT-System")
        
        Returns:
            Dict with creation result if pending operation exists:
            {
                'type': 'success',
                'text': str,  # Success message
                'data': dict  # Created object data
            }
            
            None if no pending subtype selection
        
        Side Effects:
            Clears self.state['_pendingSubtypeSelection']
        
        Prerequisites:
            Must have self.state['_pendingSubtypeSelection'] set
        
        Example:
            # After create operation prompts for subtype
            result = coordinator.handleSubtypeFollowUp("2")
        """
        # TODO: Implement (port from MainAgent._handleSubtypeFollowUp)
        # For now, return None (no pending operation)
        return None
    
    def handleBulkAssetImportHelper(self, excelData: Dict) -> Dict:
        """
        Helper for bulk asset import (called by MainAgent).
        
        Creates multiple assets from Excel data.
        MainAgent orchestrates (reads Excel via DocumentCoordinator),
        this method handles the asset creation part.
        
        Args:
            excelData: Dict with parsed Excel data
            {
                'rows': list,  # List of asset data rows
                'columns': list  # Column names
            }
        
        Returns:
            Dict with import results:
            {
                'type': 'success',
                'text': str,  # Summary message
                'data': {
                    'created': int,  # Number of assets created
                    'failed': int,   # Number of failures
                    'errors': list   # Error details if any
                }
            }
        
        Notes:
            - This is a helper method, not a full coordinator method
            - MainAgent handles Excel reading and orchestration
            - This method only handles asset creation logic
        """
        # TODO: Implement bulk asset creation logic
        # For now, return placeholder
        return self._error("Bulk import not yet implemented in coordinator (Phase 4 in progress)")
    
    # ==================== INTERNAL METHODS ====================
    # These methods will be ported from ISMSHandler
    
    def _getHandler(self):
        """
        Lazy initialize ISMSHandler (internal).
        
        Returns existing handler or creates new one if needed.
        """
        # TODO: Implement lazy initialization
        pass
    
    def _getDefaults(self):
        """
        Get default domain and unit (with caching).
        
        Returns:
            Tuple[str, str]: (domainId, unitId)
        
        Note:
            Uses instance variable caching to avoid repeated API calls.
            Cache is cleared on initialization.
        """
        # Return cached values if available
        if self._domainCache and self._unitCache:
            return self._domainCache, self._unitCache
        
        # Get first unit
        unitsResult = self.veriniceTool.listUnits()
        if unitsResult.get('success'):
            units = unitsResult.get('units', [])
            if units and len(units) > 0:
                unit = units[0]
                self._unitCache = unit.get('id')
                
                # Get unit's domain
                domains = unit.get('domains', [])
                if domains:
                    self._domainCache = domains[0].get('id') if isinstance(domains[0], dict) else domains[0]
        
        # Fallback to first domain if no unit domain or no units
        if not self._domainCache:
            domainsResult = self.veriniceTool.listDomains()
            if domainsResult.get('success') and domainsResult.get('domains'):
                self._domainCache = domainsResult['domains'][0].get('id')
        
        # If still no unit but we have domains, try to get unit from domains
        if not self._unitCache and self._domainCache:
            # Try listing units again (might have been a transient error)
            unitsResult = self.veriniceTool.listUnits()
            if unitsResult.get('success') and unitsResult.get('units'):
                unit = unitsResult['units'][0]
                self._unitCache = unit.get('id')
        
        return self._domainCache, self._unitCache
    
    def _handleCreate(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Create operation handler (internal).
        
        Most complex handler - extracts parameters, handles subtypes, creates object.
        
        Args:
            objectType: Type of object to create
            message: User's message
            domainId: Domain ID
            unitId: Unit ID
        
        Returns:
            Dict with creation result
        """
        # Try simple format first
        simpleFormat = self._extractSimpleFormat(message, objectType)
        if simpleFormat:
            name = simpleFormat['name']
            abbreviation = simpleFormat.get('abbreviation')
            description = simpleFormat.get('description', '')
            subType = simpleFormat.get('subType')
        else:
            # Fallback to keyword extraction
            name = self._extractName(message, objectType)
            if not name:
                return self._error(f"What name for the {objectType}?\n\nExample: create {objectType} MyName\nOr: create {objectType} MyName ABBR My description")
            abbreviation = self._extractAbbreviation(message)
            description = self._extractDescription(message) or ""
            subType = self._extractSubType(message, objectType)
        
        # Validate and match subType if provided
        if subType:
            subTypesInfo = self._getSubTypesInfo(domainId, objectType)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            if availableSubTypes:
                if subType in availableSubTypes:
                    pass  # subType is correct
                else:
                    # Try intelligent matching
                    matched = self._matchSubType(subType, availableSubTypes)
                    if matched:
                        subType = matched
                    else:
                        return self._error(f"Invalid subType '{subType}'. Available: {', '.join(availableSubTypes[:5])}")
        
        # If subType not provided, try to infer or auto-select
        if not subType:
            subTypesInfo = self._getSubTypesInfo(domainId, objectType)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            
            if not availableSubTypes:
                pass  # No subtypes, proceed without
            elif len(availableSubTypes) == 1:
                subType = availableSubTypes[0]  # Only one option
            else:
                # Try pattern matching
                inferred = self._inferSubTypeFromPattern(objectType, name, abbreviation, description, availableSubTypes)
                if inferred:
                    subType = inferred
                else:
                    # Auto-select first subtype for consistency
                    subType = availableSubTypes[0]
        
        # Create object
        result = self.veriniceTool.createObject(
            objectType,
            domainId,
            unitId,
            name,
            subType=subType,
            description=description,
            abbreviation=abbreviation
        )
        
        if result.get('success'):
            info = f"Created {objectType} '{name}'"
            if abbreviation:
                info += f" (abbreviation: {abbreviation})"
            if subType:
                info += f" (subType: {subType})"
            return self._success(info)
        
        return self._error(f"Failed to create {objectType}: {result.get('error', 'Unknown error')}")
    
    def _handleList(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        List operation handler (internal).
        
        Args:
            objectType: Type of object to list
            message: User's message
            domainId: Domain ID
            unitId: Unit ID
        
        Returns:
            Dict with list results
        """
        # Special handling for scopes - can be listed without domain
        if objectType == 'scope' and not domainId:
            if unitId:
                result = self.veriniceTool.listObjects(objectType, None, unitId=unitId)
                if result.get('success'):
                    result['objectType'] = objectType
                    formatted = self._formatResult('listVeriniceObjects', result)
                    return self._success(formatted)
                return self._error(f"Could not list scopes: {result.get('error', 'Unknown error')}")
            else:
                # No unit - try to get units
                unitsResult = self.veriniceTool.listUnits()
                if not unitsResult.get('success'):
                    errorMsg = unitsResult.get('error', 'Unknown error')
                    if 'not available' in errorMsg.lower() or 'authentication' in errorMsg.lower() or 'connection' in errorMsg.lower():
                        return self._error(f"Could not connect to ISMS: {errorMsg}\n\nPlease ensure:\n1. Keycloak is running on http://localhost:8080\n2. ISMS backend is running on http://localhost:8070\n3. Credentials are correct")
                    # Fallback to domains
                    domainsResult = self.veriniceTool.listDomains()
                    if domainsResult.get('success') and domainsResult.get('domains'):
                        domainId = domainsResult['domains'][0].get('id')
                        result = self.veriniceTool.listObjects(objectType, domainId)
                        if result.get('success'):
                            result['objectType'] = objectType
                            formatted = self._formatResult('listVeriniceObjects', result)
                            return self._success(formatted)
                        return self._error(f"Could not list scopes: {result.get('error', 'Unknown error')}")
                    return self._error(f"Could not list units: {errorMsg}")
                
                units = unitsResult.get('units')
                if not units or (isinstance(units, list) and len(units) == 0):
                    # No units - try domains fallback
                    domainsResult = self.veriniceTool.listDomains()
                    if domainsResult.get('success') and domainsResult.get('domains'):
                        domainId = domainsResult['domains'][0].get('id')
                        result = self.veriniceTool.listObjects(objectType, domainId)
                        if result.get('success'):
                            result['objectType'] = objectType
                            formatted = self._formatResult('listVeriniceObjects', result)
                            return self._success(formatted)
                        return self._error(f"Could not list scopes: {result.get('error', 'Unknown error')}")
                    return self._error("No units found. Please create a unit first or create a domain from template.")
                
                # Use first unit
                firstUnit = units[0]
                unitId = firstUnit.get('id')
                if not unitId:
                    return self._error("Unit found but missing ID. Please try again.")
                
                result = self.veriniceTool.listObjects(objectType, None, unitId=unitId)
                if result.get('success'):
                    result['objectType'] = objectType
                    formatted = self._formatResult('listVeriniceObjects', result)
                    return self._success(formatted)
                return self._error(f"Could not list scopes: {result.get('error', 'Unknown error')}")
        
        # Standard list with domain
        if not domainId:
            return self._error(f"Could not list {objectType}s: No domain available. Please create a domain first.")
        
        result = self.veriniceTool.listObjects(objectType, domainId)
        if result.get('success'):
            result['objectType'] = objectType
            formatted = self._formatResult('listVeriniceObjects', result)
            return self._success(formatted)
        return self._error(f"Could not list {objectType}s: {result.get('error', 'Unknown error')}")
    
    def _handleGet(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Get operation handler (internal).
        
        Finds object by name or ID and retrieves details.
        
        Args:
            objectType: Type of object
            message: User's message
            domainId: Domain ID
            unitId: Unit ID (unused but kept for consistency)
        
        Returns:
            Dict with object details
        """
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(f"I need the {objectType} name or ID.\n\nExample: get {objectType} MyName")
        
        result = self.veriniceTool.getObject(objectType, domainId, objectId)
        if result.get('success'):
            formatted = self._formatResult('getVeriniceObject', result)
            return self._success(formatted)
        return self._error(f"Could not find {objectType}: {result.get('error', 'Unknown error')}")
    
    def _handleDelete(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Delete operation handler (internal).
        
        Args:
            objectType: Type of object
            message: User's message
            domainId: Domain ID
            unitId: Unit ID (unused but kept for consistency)
        
        Returns:
            Dict with deletion result
        """
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(f"I need the {objectType} name or ID to delete.\n\nExample: delete {objectType} MyName")
        
        result = self.veriniceTool.deleteObject(objectType, domainId, objectId)
        if result.get('success'):
            return self._success(f"Deleted {objectType} successfully")
        return self._error(f"Failed to delete {objectType}: {result.get('error', 'Unknown error')}")
    
    def _handleUpdate(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Update operation handler (internal).
        
        Args:
            objectType: Type of object
            message: User's message
            domainId: Domain ID
            unitId: Unit ID (unused but kept for consistency)
        
        Returns:
            Dict with update result
        """
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(f"I need the {objectType} name or ID.\n\nExample: update {objectType} MyName")
        
        # Extract field and value (simple pattern-based for now)
        field, value = self._extractFieldAndValuePattern(message, objectType)
        
        if not field or not value:
            return self._error("What do you want to update?\n\nExample: update scope BLUETEAM description New description")
        
        result = self.veriniceTool.updateObject(objectType, domainId, objectId, {field: value})
        if result.get('success'):
            return self._success(f"Updated {objectType} {field} to '{value}'")
        return self._error(f"Failed to update: {result.get('error', 'Unknown error')}")
    
    def _extractFieldAndValuePattern(self, message: str, objectType: str) -> tuple:
        """
        Pattern-based extraction of field and value for updates.
        
        Args:
            message: User's message
            objectType: Type of object
        
        Returns:
            Tuple of (field, value) or (None, None)
        """
        patterns = [
            r'(?:set|update|change)\s+(\w+)\s+(?:to|as|=)\s+(.+)',
            rf'{objectType}\s+\w+\s+(\w+)\s+(.+)',
            r'(\w+)\s*=\s*(.+)',
        ]
        
        for pattern in patterns:
            fieldMatch = re.search(pattern, message, re.IGNORECASE)
            if fieldMatch:
                field = fieldMatch.group(1)
                value = fieldMatch.group(2).strip()
                value = re.sub(r'\s+(in|for|with|using|to|the).*$', '', value, flags=re.IGNORECASE).strip()
                if field and value:
                    return (field, value)
        
        return (None, None)
    
    def _handleAnalyze(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Analyze operation handler (internal).
        
        Args:
            objectType: Type of object
            message: User's message
            domainId: Domain ID
            unitId: Unit ID (unused but kept for consistency)
        
        Returns:
            Dict with analysis result
        """
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(f"I need the {objectType} name or ID.\n\nExample: analyze {objectType} MyName")
        
        result = self.veriniceTool.analyzeObject(objectType, domainId, objectId)
        if result.get('success'):
            formatted = self._formatResult('analyzeVeriniceObject', result)
            return self._success(formatted)
        return self._error(f"Failed to analyze: {result.get('error', 'Unknown error')}")
    
    # ========== PARSING METHODS (from ISMSHandler) ==========
    
    def _extractName(self, message: str, objectType: str) -> Optional[str]:
        """
        Extract object name from message - enhanced patterns.
        
        Args:
            message: User's message
            objectType: Type of object (asset, scope, etc.)
        
        Returns:
            Extracted name or None
        """
        patterns = [
            rf'(?:create|creat|new|add)\s+{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+description|\s+abbreviation|\s+subType|\s+status|$)',
            rf'{objectType}\s+(?:called|named)\s+([A-Za-z0-9_\s-]+)',
            r'(?:name|called|named)\s+([A-Za-z0-9_\s-]+)',
            rf'{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+description|\s+abbreviation|\s+subType|\s+status|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Remove common trailing words
                name = re.sub(r'\s+(in|for|with|using|to|the|description|abbreviation|subType|status).*$', '', name, flags=re.IGNORECASE).strip()
                if name:
                    return name
        return None
    
    def _extractAbbreviation(self, message: str) -> Optional[str]:
        """
        Extract abbreviation from message.
        
        Args:
            message: User's message
        
        Returns:
            Extracted abbreviation or None
        """
        patterns = [
            r'abbreviation[:\s]+([A-Za-z0-9_-]{1,10})',
            r'abbrev[:\s]+([A-Za-z0-9_-]{1,10})',
            r'abbr[:\s]+([A-Za-z0-9_-]{1,10})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                abbrev = match.group(1).strip()
                if abbrev:
                    return abbrev
        return None
    
    def _extractDescription(self, message: str) -> Optional[str]:
        """
        Extract description from message.
        
        Args:
            message: User's message
        
        Returns:
            Extracted description or None
        """
        patterns = [
            r'description[:\s]+(.+?)(?:\s+subType|\s+status|$)',
            r'desc[:\s]+(.+?)(?:\s+subType|\s+status|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                desc = match.group(1).strip().strip('"').strip("'")
                if desc:
                    return desc
        return None
    
    def _extractSubType(self, message: str, objectType: str) -> Optional[str]:
        """
        Extract subtype from message.
        
        Args:
            message: User's message
            objectType: Type of object (for context, currently unused)
        
        Returns:
            Extracted subtype or None
        """
        patterns = [
            r'subType[:\s]+([A-Za-z0-9_-]+)',
            r'subtype[:\s]+([A-Za-z0-9_-]+)',
            r'type[:\s]+([A-Za-z0-9_-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                subType = match.group(1).strip()
                if subType:
                    return subType
        return None
    
    def _extractSimpleFormat(self, message: str, objectType: str) -> Optional[Dict]:
        """
        Parse 'create {type} {name} {abbr} {desc}' format.
        
        Supports multiple formats:
        - Quoted strings: create asset "name with spaces" "ABBR" "description"
        - Underscores: create asset name_with_underscores ABBR description
        - Mixed formats
        
        Args:
            message: User's message
            objectType: Type of object
        
        Returns:
            Dict with extracted fields or None
        """
        # Support "creat" typo
        createPattern = r'(?:create|creat|new|add)'
        
        # Pattern 1: All quoted with subtype
        quotedWithSubTypePattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"'
        quotedWithSubTypeMatch = re.search(quotedWithSubTypePattern, message, re.IGNORECASE)
        if quotedWithSubTypeMatch:
            return {
                'name': quotedWithSubTypeMatch.group(1).strip(),
                'abbreviation': quotedWithSubTypeMatch.group(2).strip(),
                'description': quotedWithSubTypeMatch.group(3).strip(),
                'subType': quotedWithSubTypeMatch.group(4).strip()
            }
        
        # Pattern 2: All quoted without subtype
        quotedPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"'
        quotedMatch = re.search(quotedPattern, message, re.IGNORECASE)
        if quotedMatch:
            return {
                'name': quotedMatch.group(1).strip(),
                'abbreviation': quotedMatch.group(2).strip(),
                'description': quotedMatch.group(3).strip()
            }
        
        # Pattern 3: Quoted name and description, unquoted abbreviation
        quotedNameDescPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+([A-Za-z0-9_-]+?)\s+"([^"]+)"'
        quotedNameDescMatch = re.search(quotedNameDescPattern, message, re.IGNORECASE)
        if quotedNameDescMatch:
            return {
                'name': quotedNameDescMatch.group(1).strip(),
                'abbreviation': quotedNameDescMatch.group(2).strip(),
                'description': quotedNameDescMatch.group(3).strip()
            }
        
        # Pattern 4: Quoted name and abbreviation, unquoted description
        quotedNamePattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+(.+?)(?:\s+subType|\s+status|$)'
        quotedNameMatch = re.search(quotedNamePattern, message, re.IGNORECASE)
        if quotedNameMatch:
            desc = quotedNameMatch.group(3).strip().strip('"').strip("'")
            return {
                'name': quotedNameMatch.group(1).strip(),
                'abbreviation': quotedNameMatch.group(2).strip(),
                'description': desc
            }
        
        # Pattern 5: Quoted name only, unquoted abbreviation and description
        quotedNameUnquotedPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+([A-Za-z0-9_-]+?)\s+(.+?)(?:\s+subType|\s+status|$)'
        quotedNameUnquotedMatch = re.search(quotedNameUnquotedPattern, message, re.IGNORECASE)
        if quotedNameUnquotedMatch:
            desc = quotedNameUnquotedMatch.group(3).strip().strip('"').strip("'")
            return {
                'name': quotedNameUnquotedMatch.group(1).strip(),
                'abbreviation': quotedNameUnquotedMatch.group(2).strip(),
                'description': desc
            }
        
        # Pattern 6: Standard format without quotes (underscores converted to spaces)
        pattern = rf'{createPattern}\s+{objectType}\s+([A-Za-z0-9_\s-]+?)\s+([A-Za-z0-9_-]{{1,20}})\s+(.+?)(?:\s+subType|\s+status|$)'
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            name = match.group(1).strip().replace('_', ' ')
            abbreviation = match.group(2).strip()
            description = match.group(3).strip()
            return {
                'name': name,
                'abbreviation': abbreviation,
                'description': description
            }
        
        # Pattern 7: Name and abbreviation only (no description)
        pattern2 = rf'{createPattern}\s+{objectType}\s+([A-Za-z0-9_\s-]+?)\s+([A-Za-z0-9_-]{{1,20}})(?:\s+subType|\s+status|$)'
        match2 = re.search(pattern2, message, re.IGNORECASE)
        if match2:
            name = match2.group(1).strip().replace('_', ' ')
            abbreviation = match2.group(2).strip()
            return {
                'name': name,
                'abbreviation': abbreviation,
                'description': ''
            }
        
        return None
    
    def _parseSubtypeSelection(self, message: str, availableSubTypes: List[str]) -> Optional[str]:
        """
        Parse user's subtype selection.
        
        Handles both number selection (e.g., "2") and name selection (e.g., "AST_IT-System").
        
        Args:
            message: User input
            availableSubTypes: List of valid subtype names
        
        Returns:
            Selected subtype name or None
        """
        # TODO: Port from MainAgent._parseSubtypeSelection
        pass
    
    # ========== RESOLUTION METHODS (from ISMSHandler) ==========
    
    def _resolveToId(self, objectType: str, nameOrId: str, domainId: str) -> Optional[str]:
        """
        Resolve object name to ID.
        
        Checks if message contains UUID, otherwise searches by name.
        
        Args:
            objectType: Type of object
            nameOrId: Message containing name or ID
            domainId: Domain ID to search in
        
        Returns:
            Object ID or None
        """
        # Check for UUID in message
        uuidMatch = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', nameOrId, re.IGNORECASE)
        if uuidMatch:
            return uuidMatch.group(1)
        
        # Extract name from message
        updateFieldKeywords = ['description', 'status', 'subtype', 'subType', 'name', 'abbreviation', 'abbr']
        
        patterns = [
            rf'(?:update|change|modify|edit|set)\s+{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+(?:{"|".join(updateFieldKeywords)}))',
            rf'(?:get|view|show|delete|remove|analyze)\s+{objectType}\s+(.+)',
            rf'{objectType}\s+([A-Za-z0-9_\s-]+)',
        ]
        
        name = None
        for pattern in patterns:
            match = re.search(pattern, nameOrId, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'\s+(description|status|subtype|subType|name|abbreviation|abbr|field|value|to|is|as).*$', '', name, flags=re.IGNORECASE).strip()
                if name:
                    break
        
        if not name:
            return None
        
        # Helper to search in a specific domain
        def searchInDomain(dId: str) -> Optional[str]:
            listResult = self.veriniceTool.listObjects(objectType, dId)
            if not listResult.get('success'):
                return None
            
            objects = listResult.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            
            for item in items:
                itemName = item.get('name', '').strip()
                if not itemName:
                    continue
                
                # Exact match (case-insensitive)
                if itemName.lower() == name.lower():
                    return item.get('id') or item.get('resourceId')
                
                # Fuzzy match (substring)
                if name.lower() in itemName.lower() or itemName.lower() in name.lower():
                    return item.get('id') or item.get('resourceId')
            
            return None
        
        # Try default domain first
        if domainId:
            result = searchInDomain(domainId)
            if result:
                return result
        
        # Search all domains if not found
        domainsResult = self.veriniceTool.listDomains()
        if domainsResult.get('success') and domainsResult.get('domains'):
            domains = domainsResult['domains']
            for domain in domains:
                dId = domain.get('id') if isinstance(domain, dict) else domain
                if dId and dId != domainId:
                    result = searchInDomain(dId)
                    if result:
                        return result
        
        return None
    
    def _getSubTypesInfo(self, domainId: str, objectType: str) -> Dict:
        """
        Get available subtypes for object type.
        
        Args:
            domainId: Domain ID
            objectType: Type of object
        
        Returns:
            Dict with subtypes and count
        """
        try:
            result = self.veriniceTool.getDomainSubTypes(domainId, objectType)
            if result.get('success'):
                return {
                    'subTypes': result.get('subTypes', []),
                    'count': result.get('count', 0)
                }
        except Exception:
            pass
        return {'subTypes': [], 'count': 0}
    
    def _matchSubType(self, providedSubType: str, availableSubTypes: List[str]) -> Optional[str]:
        """
        Intelligently match provided subtype to available options.
        
        Handles variations like "Data protection officer" → "PER_DataProtectionOfficer"
        
        Args:
            providedSubType: User-provided subtype string
            availableSubTypes: List of valid subtypes
        
        Returns:
            Matched subtype or None
        """
        if not availableSubTypes or not providedSubType:
            return None
        
        provided_lower = providedSubType.lower().strip()
        
        def normalize_subtype(st: str) -> str:
            """Remove common prefixes and normalize"""
            st_clean = st.lower().replace('ast_', '').replace('per_', '').replace('_', ' ').replace('-', ' ')
            return st_clean.strip()
        
        for subType in availableSubTypes:
            subType_lower = subType.lower()
            subType_normalized = normalize_subtype(subType)
            
            # Exact match
            if provided_lower == subType_lower or provided_lower == subType_normalized:
                return subType
            
            # Normalized match (remove spaces, underscores, hyphens)
            provided_normalized = provided_lower.replace(' ', '').replace('_', '').replace('-', '')
            subType_normalized_no_spaces = subType_normalized.replace(' ', '').replace('_', '').replace('-', '')
            if provided_normalized == subType_normalized_no_spaces:
                return subType
            
            # Word-by-word matching
            provided_words = provided_lower.split()
            subType_words = subType_normalized.split()
            
            if all(word in subType_normalized for word in provided_words):
                return subType
            
            if all(word in provided_lower for word in subType_words):
                return subType
            
            # Contains match
            if provided_lower in subType_normalized or subType_normalized in provided_lower:
                return subType
            
            # Pattern-based matching
            patterns = {
                'data protection officer': ['dpo', 'data protection', 'privacy officer', 'gdpr officer', 'dataprotectionofficer'],
                'dataprotectionofficer': ['dpo', 'data protection', 'privacy officer', 'gdpr officer', 'data protection officer'],
                'person': ['person', 'employee', 'staff', 'user'],
                'it-system': ['it system', 'server', 'infrastructure', 'network', 'system', 'it-systems'],
                'it-systems': ['it system', 'server', 'infrastructure', 'network', 'system', 'it-system'],
                'application': ['application', 'app', 'software', 'program'],
                'datatype': ['data type', 'data', 'information', 'dataset', 'datatypes'],
                'datatypes': ['data type', 'data', 'information', 'dataset', 'datatype']
            }
            
            if subType_normalized in patterns:
                keywords = patterns[subType_normalized]
                for keyword in keywords:
                    if keyword in provided_lower or provided_lower in keyword:
                        return subType
        
        return None
    
    def _inferSubTypeFromPattern(self, objectType: str, name: str, 
                                 abbreviation: str, description: str,
                                 availableSubTypes: List[str]) -> Optional[str]:
        """
        Infer subtype from patterns in name/abbreviation/description.
        
        Simple keyword matching - no LLM needed.
        
        Args:
            objectType: Type of object
            name: Object name
            abbreviation: Object abbreviation
            description: Object description
            availableSubTypes: List of valid subtypes
        
        Returns:
            Inferred subtype or None
        """
        if not availableSubTypes:
            return None
        
        # Normalize inputs
        name_lower = (name or '').lower().strip()
        abbr_lower = (abbreviation or '').lower().strip()
        desc_lower = (description or '').lower().strip()
        combined_text = f"{name_lower} {abbr_lower} {desc_lower}"
        
        def normalize_subtype(st: str) -> str:
            """Remove common prefixes"""
            st_clean = st.lower().replace('ast_', '').replace('per_', '').replace('_', ' ').replace('-', ' ')
            return st_clean.strip()
        
        for subType in availableSubTypes:
            subType_lower = subType.lower()
            subType_normalized = normalize_subtype(subType)
            
            # Exact match in description
            if desc_lower == subType_lower or desc_lower == subType_normalized:
                return subType
            
            # Check description words
            desc_words = desc_lower.split()
            for word in desc_words:
                if word == subType_lower or word == subType_normalized:
                    return subType
                if word.rstrip('s') == subType_normalized.rstrip('s') or subType_normalized.rstrip('s') == word.rstrip('s'):
                    return subType
                if word in subType_normalized or subType_normalized in word:
                    return subType
            
            # Direct match in combined text
            if subType_lower in combined_text or subType_normalized in combined_text:
                return subType
            
            # Pattern mappings
            patterns = {
                'person': {
                    'data protection officer': ['dpo', 'data protection', 'privacy officer', 'gdpr officer'],
                    'person': ['person', 'employee', 'staff', 'user']
                },
                'asset': {
                    'it-systems': ['it system', 'server', 'infrastructure', 'network', 'system'],
                    'it-system': ['it system', 'server', 'infrastructure', 'network', 'system'],
                    'applications': ['application', 'app', 'software', 'program'],
                    'application': ['application', 'app', 'software', 'program'],
                    'datatypes': ['data type', 'data', 'information', 'dataset', 'datatypes'],
                    'datatype': ['data type', 'data', 'information', 'dataset', 'datatypes']
                }
            }
            
            type_patterns = patterns.get(objectType.lower(), {})
            if subType_normalized in type_patterns:
                keywords = type_patterns[subType_normalized]
                for keyword in keywords:
                    if keyword in combined_text:
                        return subType
            
            # Partial match
            if abbr_lower and (abbr_lower in subType_lower or subType_lower in abbr_lower):
                return subType
        
        return None
    
    # ========== UTILITY METHODS (from ISMSHandler) ==========
    
    def _success(self, message: str, data: Any = None) -> Dict:
        """
        Format success response.
        
        Args:
            message: Success message text
            data: Optional additional data
        
        Returns:
            Dict with success response format
        """
        return {
            'type': 'success',
            'text': message,
            'data': data
        }
    
    def _error(self, message: str) -> Dict:
        """
        Format error response.
        
        Args:
            message: Error message text
        
        Returns:
            Dict with error response format
        """
        return {
            'type': 'error',
            'text': message
        }
    
    def _formatResult(self, operation: str, result: Any) -> str:
        """
        Format Verinice result for display.
        
        This is a simplified formatter. The full MainAgent formatter
        will be used when integrated, but this provides basic formatting
        for testing.
        
        Args:
            operation: Operation type (e.g., 'listVeriniceObjects')
            result: Raw result from Verinice tool
        
        Returns:
            Formatted string for display
        """
        # For now, return simple formatted result
        # This will be replaced with proper MainAgent formatter during integration
        if isinstance(result, dict):
            if operation == 'listVeriniceObjects':
                objects = result.get('objects', {})
                items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                objectType = result.get('objectType', 'objects')
                
                if not items:
                    return f"No {objectType}s found."
                
                formatted = f"Found {len(items)} {objectType}(s):\n\n"
                for i, item in enumerate(items[:20], 1):  # Limit to 20 items
                    name = item.get('name', 'N/A')
                    itemId = item.get('id') or item.get('resourceId', 'N/A')
                    formatted += f"{i}. {name} (ID: {itemId})\n"
                
                if len(items) > 20:
                    formatted += f"\n... and {len(items) - 20} more items"
                
                return formatted
            
            elif operation == 'getVeriniceObject':
                obj = result.get('object', result)
                name = obj.get('name', 'N/A')
                objId = obj.get('id') or obj.get('resourceId', 'N/A')
                objType = obj.get('type', 'object')
                
                formatted = f"**{objType.upper()}: {name}**\n\n"
                formatted += f"ID: {objId}\n"
                
                # Add other fields if available
                if 'description' in obj:
                    formatted += f"Description: {obj['description']}\n"
                if 'abbreviation' in obj:
                    formatted += f"Abbreviation: {obj['abbreviation']}\n"
                if 'status' in obj:
                    formatted += f"Status: {obj['status']}\n"
                if 'subType' in obj:
                    formatted += f"SubType: {obj['subType']}\n"
                
                return formatted
        
        # Fallback: convert to string
        return str(result)


# ==================== USAGE EXAMPLE ====================

def example_usage():
    """
    Example of how ISMSCoordinator will be used in MainAgent.
    
    This is for documentation only - not actual integration.
    """
    
    # In MainAgent.__init__:
    # self._ismsCoordinator = None
    # self._useIsmsCoordinator = False  # Feature flag
    
    # In MainAgent (when integrated):
    def _getIsmsCoordinator(agent):
        """Lazy initialize ISMS Coordinator"""
        if not agent._ismsCoordinator:
            tools = {
                'veriniceTool': agent._veriniceTool,
                'llmTool': agent._llmTool
            }
            agent._ismsCoordinator = ISMSCoordinator(
                agent.state,
                tools,
                agent.contextManager
            )
        return agent._ismsCoordinator
    
    # Example calls:
    # coordinator = agent._getIsmsCoordinator()
    
    # CRUD operation:
    # result = coordinator.handleOperation('create', 'asset', message)
    
    # Report generation:
    # result = coordinator.handleReportGeneration(command, message)
    
    # Follow-up handling:
    # result = coordinator.handleReportFollowUp(message)
    # result = coordinator.handleSubtypeFollowUp(message)


# ==================== TESTING NOTES ====================

"""
Shadow Testing Strategy (Phase 4):

1. Build this coordinator in isolation (CURRENT PHASE)
2. When Phase 3 monitoring ends (Jan 17):
   - Connect to MainAgent with feature flag False
   - Run old ISMSHandler AND new ISMSCoordinator in parallel
   - Log both results for comparison
   - Validate 100% match rate
3. Deploy when confident (flip flag to True)
4. Monitor for 2 weeks
5. Remove old ISMSHandler code

Feature Flag Location:
    mainAgent.py: self._useIsmsCoordinator = False

Shadow Testing Code:
    if self._useIsmsCoordinator:
        new_result = self._ismsCoordinator.handleOperation(...)
        return new_result
    else:
        old_result = self._ismsHandler.execute(...)
        return old_result

Validation:
    - All ISMS operations must work identically
    - State management must be preserved
    - Follow-ups must work correctly
    - Report generation must work end-to-end
"""
