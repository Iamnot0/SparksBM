"""Simplified ISMS operation handler - clean, robust, maintainable"""
from typing import Dict, Optional, List, Any
import re
import json
from .instructions import get_error_message


class ISMSHandler:
    """Handles all ISMS operations with clean, simple logic"""
    
    def __init__(self, veriniceTool, formatFunc, llmTool=None):
        self.veriniceTool = veriniceTool
        self.formatResult = formatFunc
        self.llmTool = llmTool  # Optional LLM for intelligent parsing
        self._domainCache = None
        self._unitCache = None
        self.state = {}  # State for storing pending operations
    
    def execute(self, operation: str, objectType: str, message: str) -> Dict:
        """
        Execute Verinice operation with auto-detection
        
        Single entry point for all operations - simple dispatch
        """
        # Get domain/unit (cached)
        domainId, unitId = self._getDefaults()
        
        # Allow listing scopes without domain (scopes can be listed at unit level)
        # Allow listing domains without requiring a domain
        requiresDomain = operation != 'list_domains' and not (operation == 'list' and objectType == 'scope')
        
        if not domainId and requiresDomain:
            return self._error(get_error_message('not_found', 'domain'))
        
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
            return self._error(get_error_message('validation', 'unknown_operation', operation=operation))
        
        return handler(objectType, message, domainId, unitId)
    
    # ==================== OPERATION HANDLERS ====================
    
    def _handleCreate(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """Create operation - simple and efficient"""
        # Try simple format first: "create {objectType} {name} {abbreviation} {description}"
        simpleFormat = self._extractSimpleFormat(message, objectType)
        if simpleFormat:
            name = simpleFormat['name']
            abbreviation = simpleFormat.get('abbreviation')
            description = simpleFormat.get('description', '')
            subType = simpleFormat.get('subType')
        else:
            # Fallback to old format with keywords
            name = self._extractName(message, objectType)
            if not name:
                return self._error(get_error_message('validation', 'missing_name', objectType=objectType))
            abbreviation = self._extractAbbreviation(message)
            description = self._extractDescription(message) or ""
            subType = self._extractSubType(message, objectType)
        
        # Validate and match subType if provided
        if subType:
            subTypesInfo = self._getSubTypesInfo(domainId, objectType)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            if availableSubTypes:
                # If exact match, use it
                if subType in availableSubTypes:
                    pass  # subType is already correct
                else:
                    # Try intelligent matching
                    matched = self._matchSubType(subType, availableSubTypes)
                    if matched:
                        subType = matched  # Use the matched subtype
                    else:
                        return self._error(get_error_message('validation', 'invalid_subtype', subType=subType, available=', '.join(availableSubTypes[:5])))
        
        # If subType not provided, try to infer it or auto-select default
        if not subType:
            subTypesInfo = self._getSubTypesInfo(domainId, objectType)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            
            if not availableSubTypes:
                # No subtypes available, proceed without subtype (tool will handle)
                pass
            elif len(availableSubTypes) == 1:
                # Only one subtype, use it automatically
                subType = availableSubTypes[0]
            else:
                # Multiple subtypes - try pattern matching first
                inferred = self._inferSubTypeFromPattern(objectType, name, abbreviation, description, availableSubTypes)
                if inferred:
                    subType = inferred
                else:
                    # Pattern matching failed - auto-select first available subtype for consistency
                    # This ensures consistent behavior in automated flows
                    # If user wants specific subtype, they can specify it in the command
                    subType = availableSubTypes[0]
        
        # Create object (tool handles auto-selection of subType/status)
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
        
        return self._error(get_error_message('operation_failed', 'create', objectType=objectType, error=result.get('error', 'Unknown error')))
    
    def _handleList(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """List operation - simple and clean"""
        # For scopes, try to list without domain first (at unit level)
        if objectType == 'scope' and not domainId:
            # Try to list scopes at unit level
            if unitId:
                result = self.veriniceTool.listObjects(objectType, None, unitId=unitId)
                if result.get('success'):
                    result['objectType'] = objectType
                    formatted = self.formatResult('listVeriniceObjects', result)
                    return self._success(formatted)
                return self._error(get_error_message('operation_failed', 'list_scopes', error=result.get('error', 'Unknown error')))
            else:
                # Check if units exist - refresh cache if needed
                unitsResult = self.veriniceTool.listUnits()
                if not unitsResult.get('success'):
                    # listUnits() failed - check if it's an auth/connection issue
                    errorMsg = unitsResult.get('error', 'Unknown error')
                    if 'not available' in errorMsg.lower() or 'authentication' in errorMsg.lower() or 'connection' in errorMsg.lower():
                        return self._error(get_error_message('connection', 'isms_unavailable', error=errorMsg))
                    # Try domains as fallback
                    domainsResult = self.veriniceTool.listDomains()
                    if domainsResult.get('success') and domainsResult.get('domains'):
                        domainId = domainsResult['domains'][0].get('id')
                        result = self.veriniceTool.listObjects(objectType, domainId)
                        if result.get('success'):
                            result['objectType'] = objectType
                            formatted = self.formatResult('listVeriniceObjects', result)
                            return self._success(formatted)
                        return self._error(get_error_message('operation_failed', 'list_scopes', error=result.get('error', 'Unknown error')))
                    return self._error(get_error_message('operation_failed', 'list_units', error=errorMsg))
                
                # Check if units list is empty or None
                units = unitsResult.get('units')
                if not units or (isinstance(units, list) and len(units) == 0):
                    # No units found - try domains as fallback
                    domainsResult = self.veriniceTool.listDomains()
                    if domainsResult.get('success') and domainsResult.get('domains'):
                        domainId = domainsResult['domains'][0].get('id')
                        result = self.veriniceTool.listObjects(objectType, domainId)
                        if result.get('success'):
                            result['objectType'] = objectType
                            formatted = self.formatResult('listVeriniceObjects', result)
                            return self._success(formatted)
                        return self._error(get_error_message('operation_failed', 'list_scopes', error=result.get('error', 'Unknown error')))
                    return self._error(get_error_message('not_found', 'unit'))
                
                # Use first unit to list scopes
                firstUnit = units[0]
                unitId = firstUnit.get('id')
                if not unitId:
                    return self._error(get_error_message('not_found', 'unit_missing_id'))
                
                result = self.veriniceTool.listObjects(objectType, None, unitId=unitId)
                if result.get('success'):
                    result['objectType'] = objectType
                    formatted = self.formatResult('listVeriniceObjects', result)
                    return self._success(formatted)
                return self._error(get_error_message('operation_failed', 'list_scopes', error=result.get('error', 'Unknown error')))
        
        # Standard list operation with domain
        if not domainId:
            return self._error(get_error_message('operation_failed', 'list', objectType=objectType, error='No domain available. Please create a domain first.'))
        
        result = self.veriniceTool.listObjects(objectType, domainId)
        if result.get('success'):
            result['objectType'] = objectType
            formatted = self.formatResult('listVeriniceObjects', result)
            return self._success(formatted)
        return self._error(get_error_message('operation_failed', 'list', objectType=objectType, error=result.get('error', 'Unknown error')))
    
    def _handleGet(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """Get operation - find by name or ID"""
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params', objectType=objectType))
        
        result = self.veriniceTool.getObject(objectType, domainId, objectId)
        if result.get('success'):
            formatted = self.formatResult('getVeriniceObject', result)
            return self._success(formatted)
        return self._error(get_error_message('not_found', 'object', objectType=objectType, error=result.get('error', 'Unknown error')))
    
    def _handleDelete(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """Delete operation - find by name or ID and delete"""
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params_delete', objectType=objectType))
        
        result = self.veriniceTool.deleteObject(objectType, domainId, objectId)
        if result.get('success'):
            return self._success(f"Deleted {objectType} successfully")
        return self._error(get_error_message('operation_failed', 'delete', objectType=objectType, error=result.get('error', 'Unknown error')))
    
    def _handleUpdate(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Update operation - simple positional format like CREATE
        
        Format: update {object} {currentName} {newName} {newAbbr} {newDescription}
        Examples:
        - update scope MyScope NewName
        - update scope MyScope NewName NA
        - update scope MyScope NewName NA New description here
        """
        # Resolve current object ID
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params_update', objectType=objectType))
        
        # Extract current name for response
        currentName = self._extractName(message, objectType) or objectId
        
        # Parse update fields using same logic as CREATE
        parts = message.split()
        
        # Remove command words and object type
        filteredParts = []
        skipWords = ['update', 'edit', 'modify', 'change', objectType, objectType + 's']
        for part in parts:
            if part.lower() not in skipWords:
                filteredParts.append(part)
        
        if len(filteredParts) < 2:
            return self._error(get_error_message('validation', 'what_to_update', objectType=objectType, currentName=currentName))
        
        # First part is current name (already resolved), rest are updates
        updateParts = filteredParts[1:]  # Skip current name
        
        # Build update data based on number of arguments
        updateData = {}
        
        if len(updateParts) >= 1:
            # First arg: new name
            updateData['name'] = updateParts[0]
        
        if len(updateParts) >= 2:
            # Second arg: new abbreviation
            updateData['abbreviation'] = updateParts[1]
        
        if len(updateParts) >= 3:
            # Everything else: new description
            updateData['description'] = ' '.join(updateParts[2:])
        
        # Execute update
        result = self.veriniceTool.updateObject(objectType, domainId, objectId, updateData)
        if result.get('success'):
            updatedFields = ', '.join(updateData.keys())
            return self._success(f"Updated {objectType} '{currentName}' ({updatedFields})")
        return self._error(get_error_message('operation_failed', 'update', error=result.get('error', 'Unknown error')))
    
    def _extractFieldAndValue(self, message: str, objectType: str, objectId: str) -> tuple:
        """
        Intelligently extract field and value using LLM (with pattern fallback)
        
        Returns:
            (field, value) tuple or (None, None) if extraction fails
        """
        # Try LLM first if available
        if self.llmTool:
            try:
                prompt = f"""Extract the field name and new value from this update command:

User Message: "{message}"
Object Type: {objectType}
Object ID: {objectId}

Common fields for {objectType}:
- name: Object name
- description: Object description
- status: Object status (e.g., NEW, ACTIVE, INACTIVE)
- subType: Object subtype

Extract the field name and value. The user wants to update a specific field.

Examples:
- "update scope BLUETEAM description New description" → field: "description", value: "New description"
- "update asset MyAsset status ACTIVE" → field: "status", value: "ACTIVE"
- "change scope NAME to NewName" → field: "name", value: "NewName"
- "set description to Updated description" → field: "description", value: "Updated description"

Respond ONLY in JSON format:
{{
    "field": "field_name",
    "value": "new_value"
}}

If you cannot determine the field or value, return:
{{
    "field": null,
    "value": null
}}
"""
                response = self.llmTool.generate(prompt, maxTokens=200)
                
                # Extract JSON from response
                jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
                if jsonMatch:
                    result = json.loads(jsonMatch.group(0))
                    field = result.get('field')
                    value = result.get('value')
                    if field and value:
                        return (field.strip(), value.strip())
            except Exception:
                pass  # Fallback to pattern-based
        
        return (None, None)
    
    def _extractFieldAndValuePattern(self, message: str, objectType: str) -> tuple:
        """
        Pattern-based extraction (fallback)
        
        Returns:
            (field, value) tuple or (None, None) if extraction fails
        """
        patterns = [
            r'(?:set|update|change)\s+(\w+)\s+(?:to|as|=)\s+(.+)',  # "set description to value"
            rf'{objectType}\s+\w+\s+(\w+)\s+(.+)',                    # "scope NAME field value"
            r'(\w+)\s*=\s*(.+)',                                      # "field = value"
        ]
        
        for pattern in patterns:
            fieldMatch = re.search(pattern, message, re.IGNORECASE)
            if fieldMatch:
                field = fieldMatch.group(1)
                value = fieldMatch.group(2).strip()
                # Remove trailing words that might be part of the message
                value = re.sub(r'\s+(in|for|with|using|to|the).*$', '', value, flags=re.IGNORECASE).strip()
                if field and value:
                    return (field, value)
        
        return (None, None)
    
    def _handleAnalyze(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """Analyze operation - get object and analyze with LLM"""
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params_analyze', objectType=objectType))
        
        result = self.veriniceTool.analyzeObject(objectType, domainId, objectId)
        if result.get('success'):
            formatted = self.formatResult('analyzeVeriniceObject', result)
            return self._success(formatted)
        return self._error(get_error_message('operation_failed', 'analyze', error=result.get('error', 'Unknown error')))
    
    # ==================== HELPER METHODS ====================
    
    def _getDefaults(self) -> tuple:
        """Get default domain/unit with caching"""
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
    
    def _extractSimpleFormat(self, message: str, objectType: str) -> Optional[Dict]:
        """
        Extract from simple format with support for quoted strings:
        - "create {objectType} {name} {abbreviation} {description}"
        - "create {objectType} \"name with spaces\" \"abbr\" \"description with spaces\""
        - "create {objectType} name_with_underscores abbr description"
        
        Examples:
        - create scope "scope test" "scp2" "scope description"
        - create person "john doe" "DPO" "dpo officer"
        - create scope scope_test scp2 scope_description
        - creat scope "SCOPE TEST" "SA-1" "SCOPE TESTING"  (typo "creat" supported)
        """
        # Support "creat" typo
        createPattern = r'(?:create|creat|new|add)'
        
        # First try: All quoted format with subtype (supports spaces)
        # Pattern: create {objectType} "name" "abbreviation" "description" "subtype"
        quotedWithSubTypePattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"'
        quotedWithSubTypeMatch = re.search(quotedWithSubTypePattern, message, re.IGNORECASE)
        if quotedWithSubTypeMatch:
            return {
                'name': quotedWithSubTypeMatch.group(1).strip(),
                'abbreviation': quotedWithSubTypeMatch.group(2).strip(),
                'description': quotedWithSubTypeMatch.group(3).strip(),
                'subType': quotedWithSubTypeMatch.group(4).strip()
            }
        
        # Second try: All quoted format without subtype (supports spaces)
        # Pattern: create {objectType} "name" "abbreviation" "description"
        quotedPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"'
        quotedMatch = re.search(quotedPattern, message, re.IGNORECASE)
        if quotedMatch:
            return {
                'name': quotedMatch.group(1).strip(),
                'abbreviation': quotedMatch.group(2).strip(),
                'description': quotedMatch.group(3).strip()
            }
        
        # Third try: Quoted name and description, unquoted abbreviation (with hyphens)
        # Pattern: create {objectType} "name" ABBR-1 "description"
        quotedNameDescPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+([A-Za-z0-9_-]+?)\s+"([^"]+)"'
        quotedNameDescMatch = re.search(quotedNameDescPattern, message, re.IGNORECASE)
        if quotedNameDescMatch:
            return {
                'name': quotedNameDescMatch.group(1).strip(),
                'abbreviation': quotedNameDescMatch.group(2).strip(),
                'description': quotedNameDescMatch.group(3).strip()
            }
        
        # Fourth try: Quoted name and abbreviation, unquoted description
        quotedNamePattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+(.+?)(?:\s+subType|\s+status|$)'
        quotedNameMatch = re.search(quotedNamePattern, message, re.IGNORECASE)
        if quotedNameMatch:
            desc = quotedNameMatch.group(3).strip().strip('"').strip("'")
            return {
                'name': quotedNameMatch.group(1).strip(),
                'abbreviation': quotedNameMatch.group(2).strip(),
                'description': desc
            }
        
        # Fifth try: Quoted name only, unquoted abbreviation and description
        # Pattern: create {objectType} "name" ABBR description text
        quotedNameUnquotedPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+([A-Za-z0-9_-]+?)\s+(.+?)(?:\s+subType|\s+status|$)'
        quotedNameUnquotedMatch = re.search(quotedNameUnquotedPattern, message, re.IGNORECASE)
        if quotedNameUnquotedMatch:
            desc = quotedNameUnquotedMatch.group(3).strip().strip('"').strip("'")
            return {
                'name': quotedNameUnquotedMatch.group(1).strip(),
                'abbreviation': quotedNameUnquotedMatch.group(2).strip(),
                'description': desc
            }
        
        # Sixth try: Standard format without quotes (underscores converted to spaces)
        # Pattern: create {objectType} {name} {abbreviation} {description}
        # Name can have spaces/underscores, abbreviation is short (1-20 chars), description is rest
        # Use non-greedy matching and ensure abbreviation doesn't contain spaces
        pattern = rf'{createPattern}\s+{objectType}\s+([A-Za-z0-9_\s-]+?)\s+([A-Za-z0-9_-]{{1,20}})\s+(.+?)(?:\s+subType|\s+status|$)'
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            name = match.group(1).strip().replace('_', ' ')  # Convert underscores to spaces
            abbreviation = match.group(2).strip()
            description = match.group(3).strip()
            return {
                'name': name,
                'abbreviation': abbreviation,
                'description': description
            }
        
        # Seventh try: "create {objectType} {name} {abbreviation}" (no description)
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
    
    def _extractName(self, message: str, objectType: str) -> Optional[str]:
        """Extract object name from message - enhanced patterns"""
        patterns = [
            rf'(?:create|creat|new|add)\s+{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+description|\s+abbreviation|\s+subType|\s+status|$)',  # "create scope MyScope"
            rf'{objectType}\s+(?:called|named)\s+([A-Za-z0-9_\s-]+)',     # "scope called MyScope"
            r'(?:name|called|named)\s+([A-Za-z0-9_\s-]+)',               # "name MyScope"
            rf'{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+description|\s+abbreviation|\s+subType|\s+status|$)',  # "scope MyScope"
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
        """Extract abbreviation from message"""
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
        """Extract description from message"""
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
        """Extract subType from message"""
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
    
    def _getSubTypesInfo(self, domainId: str, objectType: str) -> Dict:
        """Get subTypes information for an object type in a domain"""
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
    
    def _determineSubType(self, objectType: str, name: str, abbreviation: str, description: str, domainId: str) -> Optional[str]:
        """
        Determine subtype using simple pattern matching and interactive selection.
        Simple approach: Pattern matching first, then ask user if needed.
        """
        # Get available subtypes
        subTypesInfo = self._getSubTypesInfo(domainId, objectType)
        availableSubTypes = subTypesInfo.get('subTypes', [])
        
        # If no subtypes available, return None
        if not availableSubTypes:
            return None
        
        # If only one subtype, use it
        if len(availableSubTypes) == 1:
            return availableSubTypes[0]
        
        # Try pattern matching
        inferred = self._inferSubTypeFromPattern(objectType, name, abbreviation, description, availableSubTypes)
        if inferred:
            return inferred
        
        # Pattern matching failed - return None to trigger user prompt in _handleCreate
        return None
    
    def _inferSubTypeFromPattern(self, objectType: str, name: str, abbreviation: str, description: str, availableSubTypes: List[str]) -> Optional[str]:
        """
        Infer subtype from patterns in name, abbreviation, or description.
        Simple keyword matching - no LLM needed.
        """
        if not availableSubTypes:
            return None
        
        # Normalize inputs for matching
        name_lower = (name or '').lower().strip()
        abbr_lower = (abbreviation or '').lower().strip()
        desc_lower = (description or '').lower().strip()
        combined_text = f"{name_lower} {abbr_lower} {desc_lower}"
        
        # Helper to normalize subtype names (remove prefixes like AST_, PER_, etc.)
        def normalize_subtype(st: str) -> str:
            # Remove common prefixes
            st_clean = st.lower().replace('ast_', '').replace('per_', '').replace('_', ' ').replace('-', ' ')
            return st_clean.strip()
        
        # Try to match each available subtype
        for subType in availableSubTypes:
            subType_lower = subType.lower()
            subType_normalized = normalize_subtype(subType)
            
            # 1. Check if description itself is exactly a subtype name (exact match)
            if desc_lower == subType_lower or desc_lower == subType_normalized:
                return subType
            
            # 2. Check if description contains subtype name (with plural/singular handling)
            # "Datatypes" should match "AST_Datatype" or "Datatype"
            desc_words = desc_lower.split()
            for word in desc_words:
                # Exact match
                if word == subType_lower or word == subType_normalized:
                    return subType
                # Singular/plural match (e.g., "datatypes" matches "datatype")
                if word.rstrip('s') == subType_normalized.rstrip('s') or subType_normalized.rstrip('s') == word.rstrip('s'):
                    return subType
                # Contains match (e.g., "datatypes" contains "datatype")
                if word in subType_normalized or subType_normalized in word:
                    return subType
            
            # 3. Direct match in combined text
            if subType_lower in combined_text or subType_normalized in combined_text:
                return subType
            
            # 4. Pattern mappings for common subtypes
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
            
            # Get patterns for this object type
            type_patterns = patterns.get(objectType.lower(), {})
            
            # Pattern match
            if subType_normalized in type_patterns:
                keywords = type_patterns[subType_normalized]
                for keyword in keywords:
                    if keyword in combined_text:
                        return subType
            
            # 5. Partial match (subtype name contains abbreviation or vice versa)
            if abbr_lower and (abbr_lower in subType_lower or subType_lower in abbr_lower):
                return subType
        
        return None
    
    def _matchSubType(self, providedSubType: str, availableSubTypes: List[str]) -> Optional[str]:
        """
        Match a user-provided subtype string against available subtypes.
        Handles variations like "Data protection officer" → "PER_DataProtectionOfficer"
        """
        if not availableSubTypes or not providedSubType:
            return None
        
        provided_lower = providedSubType.lower().strip()
        
        # Helper to normalize subtype names (remove prefixes like AST_, PER_, etc.)
        def normalize_subtype(st: str) -> str:
            # Remove common prefixes
            st_clean = st.lower().replace('ast_', '').replace('per_', '').replace('_', ' ').replace('-', ' ')
            return st_clean.strip()
        
        # Try to match each available subtype
        for subType in availableSubTypes:
            subType_lower = subType.lower()
            subType_normalized = normalize_subtype(subType)
            
            # 1. Exact match (case-insensitive)
            if provided_lower == subType_lower or provided_lower == subType_normalized:
                return subType
            
            # 2. Normalized match (remove spaces, underscores, hyphens)
            provided_normalized = provided_lower.replace(' ', '').replace('_', '').replace('-', '')
            subType_normalized_no_spaces = subType_normalized.replace(' ', '').replace('_', '').replace('-', '')
            if provided_normalized == subType_normalized_no_spaces:
                return subType
            
            # 3. Word-by-word matching (e.g., "data protection officer" matches "dataprotectionofficer")
            provided_words = provided_lower.split()
            subType_words = subType_normalized.split()
            
            # Check if all words in provided subtype are in the normalized subtype
            if all(word in subType_normalized for word in provided_words):
                return subType
            
            # Check if all words in normalized subtype are in the provided subtype
            if all(word in provided_lower for word in subType_words):
                return subType
            
            # 4. Contains match (e.g., "data protection officer" contains "dataprotectionofficer")
            if provided_lower in subType_normalized or subType_normalized in provided_lower:
                return subType
            
            # 5. Pattern-based matching for common variations
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
            
            # Check if provided subtype matches any pattern for this subtype
            if subType_normalized in patterns:
                keywords = patterns[subType_normalized]
                for keyword in keywords:
                    if keyword in provided_lower or provided_lower in keyword:
                        return subType
        
        return None
    
    def _resolveToId(self, objectType: str, message: str, domainId: str) -> Optional[str]:
        """
        Resolve name or ID to object ID - single, simple method
        
        1. Check if message has UUID
        2. If not, extract name
        3. List objects and find by name (try default domain first, then all domains)
        4. Return ID or None
        """
        # Check for UUID in message
        uuidMatch = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', message, re.IGNORECASE)
        if uuidMatch:
            return uuidMatch.group(1)
        
        # Extract name from message
        # For update commands, stop at field name (description, status, etc.)
        # For get/delete commands, capture everything after object type
        updateFieldKeywords = ['description', 'status', 'subtype', 'subType', 'name', 'abbreviation', 'abbr']
        
        patterns = [
            # Update command: "update asset Name description Value" - stop at field name
            rf'(?:update|change|modify|edit|set)\s+{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+(?:{"|".join(updateFieldKeywords)}))',
            # Get/delete command: "get asset Name" - capture everything
            rf'(?:get|view|show|delete|remove|analyze)\s+{objectType}\s+(.+)',
            # Generic: "asset Name"
            rf'{objectType}\s+([A-Za-z0-9_\s-]+)',
        ]
        
        name = None
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Clean up - remove common trailing words that indicate field names
                name = re.sub(r'\s+(description|status|subtype|subType|name|abbreviation|abbr|field|value|to|is|as).*$', '', name, flags=re.IGNORECASE).strip()
                if name:
                    break
        
        if not name:
            return None
        
        # Helper function to search in a specific domain
        def searchInDomain(dId: str) -> Optional[str]:
            listResult = self.veriniceTool.listObjects(objectType, dId)
            if not listResult.get('success'):
                return None
            
            objects = listResult.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            
            # Find by name (exact match first, then fuzzy)
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
        
        # Try default domain first (most common case)
        if domainId:
            result = searchInDomain(domainId)
            if result:
                return result
        
        # If not found in default domain, search all domains
        # This handles cases where objects are in different domains or domain cache is stale
        domainsResult = self.veriniceTool.listDomains()
        if domainsResult.get('success') and domainsResult.get('domains'):
            domains = domainsResult['domains']
            for domain in domains:
                dId = domain.get('id') if isinstance(domain, dict) else domain
                if dId and dId != domainId:  # Skip default domain (already searched)
                    result = searchInDomain(dId)
                    if result:
                        return result
        
        return None
    
    # ==================== RESPONSE HELPERS ====================
    
    def bulkCreateAssets(self, rows: List[Dict], columnMapping: Dict[str, str], domainId: str, unitId: str) -> Dict:
        """
        Bulk create assets from Excel rows
        
        Args:
            rows: List of row dictionaries from Excel
            columnMapping: Dict mapping Excel column names to Verinice field names
            domainId: Domain ID
            unitId: Unit ID
            
        Returns:
            Dict with success status and summary
        """
        if not rows:
            return self._error(get_error_message('data', 'no_rows'))
        
        if not columnMapping:
            return self._error(get_error_message('data', 'no_column_mapping'))
        
        # Get available subTypes for assets
        subTypesInfo = self._getSubTypesInfo(domainId, 'asset')
        availableSubTypes = subTypesInfo.get('subTypes', [])
        defaultSubType = availableSubTypes[0] if availableSubTypes else None
        
        created = []
        failed = []
        
        for i, row in enumerate(rows, 1):
            try:
                # Extract asset data from row using column mapping
                assetData = {}
                
                # Map each field
                for excelCol, veriniceField in columnMapping.items():
                    if excelCol in row:
                        value = row[excelCol]
                        if value is not None and str(value).strip():
                            assetData[veriniceField] = str(value).strip()
                
                # Ensure name exists
                if 'name' not in assetData:
                    # Try to use first column or generate name
                    firstCol = list(row.keys())[0] if row else None
                    if firstCol and firstCol in row:
                        assetData['name'] = str(row[firstCol]).strip()
                    else:
                        assetData['name'] = f"Asset_{i}"
                
                # Set default subType if not provided
                if 'subType' not in assetData and defaultSubType:
                    assetData['subType'] = defaultSubType
                
                # Extract fields
                name = assetData.get('name', f"Asset_{i}")
                description = assetData.get('description', '')
                subType = assetData.get('subType')
                abbreviation = assetData.get('abbreviation', '')
                
                # Create asset
                result = self.veriniceTool.createObject(
                    'asset', 
                    domainId, 
                    unitId, 
                    name, 
                    subType=subType, 
                    description=description
                )
                
                if result.get('success'):
                    objectId = result.get('objectId') or result.get('resourceId') or result.get('id')
                    
                    # Update abbreviation if provided
                    if abbreviation and objectId:
                        self.veriniceTool.updateObject(
                            'asset',
                            domainId,
                            objectId,
                            {'abbreviation': abbreviation}
                        )
                    
                    created.append({
                        'name': name,
                        'row': i,
                        'id': objectId
                    })
                else:
                    failed.append({
                        'name': name,
                        'row': i,
                        'error': result.get('error', 'Unknown error')
                    })
            except Exception as e:
                failed.append({
                    'name': f"Row_{i}",
                    'row': i,
                    'error': str(e)
                })
        
        # Build summary message
        total = len(rows)
        successCount = len(created)
        failedCount = len(failed)
        
        summary = "Bulk import completed:\n\n"
        summary += f"✅ Successfully created: {successCount}/{total} assets\n"
        
        if failedCount > 0:
            summary += f"❌ Failed: {failedCount}/{total} assets\n\n"
            summary += "Failed items:\n"
            for fail in failed[:10]:  # Show first 10 failures
                summary += f"  - Row {fail['row']} ({fail['name']}): {fail['error']}\n"
            if failedCount > 10:
                summary += f"  ... and {failedCount - 10} more failures\n"
        
        if successCount > 0:
            summary += "\n✅ Created assets:\n"
            for asset in created[:10]:  # Show first 10 created
                summary += f"  - {asset['name']}\n"
            if successCount > 10:
                summary += f"  ... and {successCount - 10} more assets\n"
        
        return self._success(summary)
    
    def _success(self, result: Any) -> Dict:
        """Success response"""
        return {
            'status': 'success',
            'result': result,
            'type': 'tool_result'
        }
    
    def _error(self, message: str) -> Dict:
        """Error response"""
        return {
            'status': 'error',
            'result': message,
            'type': 'error'
        }

