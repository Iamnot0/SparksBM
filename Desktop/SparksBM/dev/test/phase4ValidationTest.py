"""
Phase 4 - ISMS Coordinator Validation Test

Tests all ISMS operations to verify the coordinator is working correctly.
This is the FINAL validation before integration.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../Agentic Framework')))

from agents.coordinators.ismsCoordinator import ISMSCoordinator
from unittest.mock import Mock

def create_mock_verinice():
    """Create a comprehensive mock VeriniceTool"""
    mock = Mock()
    
    # Mock listUnits
    mock.listUnits.return_value = {
        'success': True,
        'units': [{'id': 'unit-1', 'name': 'TestUnit', 'domains': ['domain-1']}]
    }
    
    # Mock listDomains
    mock.listDomains.return_value = {
        'success': True,
        'domains': [{'id': 'domain-1', 'name': 'TestDomain'}]
    }
    
    # Mock getDomainSubTypes
    def mock_subtypes(domainId, objectType):
        subtypes = {
            'asset': ['AST_Datatype', 'AST_IT-System', 'AST_Application'],
            'person': ['PER_Person', 'PER_DataProtectionOfficer'],
            'scope': ['SCO_Scope'],
            'process': ['PRO_Process'],
            'control': ['CTL_Control'],
            'document': ['DOC_Document'],
            'incident': ['INC_Incident']
        }
        return {
            'success': True,
            'subTypes': subtypes.get(objectType, []),
            'count': len(subtypes.get(objectType, []))
        }
    
    mock.getDomainSubTypes.side_effect = mock_subtypes
    
    # Mock createObject
    mock.createObject.return_value = {
        'success': True,
        'objectId': 'obj-123',
        'id': 'obj-123'
    }
    
    # Mock listObjects
    mock.listObjects.return_value = {
        'success': True,
        'objects': {
            'items': [
                {'id': 'obj-1', 'name': 'TestAsset', 'type': 'asset'},
                {'id': 'obj-2', 'name': 'TestScope', 'type': 'scope'}
            ]
        }
    }
    
    # Mock getObject
    mock.getObject.return_value = {
        'success': True,
        'object': {
            'id': 'obj-123',
            'name': 'TestAsset',
            'type': 'asset',
            'description': 'Test description',
            'abbreviation': 'TA'
        }
    }
    
    # Mock updateObject
    mock.updateObject.return_value = {
        'success': True
    }
    
    # Mock deleteObject
    mock.deleteObject.return_value = {
        'success': True
    }
    
    # Mock analyzeObject
    mock.analyzeObject.return_value = {
        'success': True,
        'analysis': 'Test analysis'
    }
    
    return mock


def test_all_operations():
    """Test all ISMS coordinator operations"""
    
    print("\n" + "="*70)
    print("  PHASE 4 - ISMS COORDINATOR VALIDATION TEST")
    print("="*70 + "\n")
    
    # Initialize coordinator
    mock_verinice = create_mock_verinice()
    tools = {'veriniceTool': mock_verinice}
    state = {}
    
    coordinator = ISMSCoordinator(state, tools)
    
    print("✅ Coordinator initialized\n")
    
    # Test results
    results = {
        'passed': 0,
        'failed': 0,
        'tests': []
    }
    
    # ==================== CREATE OPERATIONS ====================
    
    print("📝 TESTING CREATE OPERATIONS:")
    print("-" * 70)
    
    # Test 1: Create Asset (simple format)
    test_name = "Create Asset (simple format)"
    try:
        result = coordinator.handleOperation('create', 'asset', 'create asset TestAsset TA Test description')
        assert result['type'] == 'success', f"Expected success, got {result['type']}"
        assert 'TestAsset' in result['text'], "Asset name not in response"
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    # Test 2: Create Scope
    test_name = "Create Scope"
    try:
        result = coordinator.handleOperation('create', 'scope', 'create scope MyScope MS Scope description')
        assert result['type'] == 'success'
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    # Test 3: Create Person
    test_name = "Create Person"
    try:
        result = coordinator.handleOperation('create', 'person', 'create person "John Doe" JD Data protection officer')
        assert result['type'] == 'success'
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    print()
    
    # ==================== LIST OPERATIONS ====================
    
    print("📋 TESTING LIST OPERATIONS:")
    print("-" * 70)
    
    # Test 4: List Assets
    test_name = "List Assets"
    try:
        result = coordinator.handleOperation('list', 'assets', 'list assets')
        assert result['type'] == 'success'
        assert 'Found' in result['text'] or 'asset' in result['text'].lower()
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    # Test 5: List Scopes
    test_name = "List Scopes"
    try:
        result = coordinator.handleOperation('list', 'scopes', 'list scopes')
        assert result['type'] == 'success'
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    print()
    
    # ==================== GET OPERATIONS ====================
    
    print("🔍 TESTING GET OPERATIONS:")
    print("-" * 70)
    
    # Test 6: Get Asset by name
    test_name = "Get Asset by name"
    try:
        result = coordinator.handleOperation('get', 'asset', 'get asset TestAsset')
        assert result['type'] == 'success'
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    # Test 7: Get Scope
    test_name = "Get Scope"
    try:
        result = coordinator.handleOperation('get', 'scope', 'get scope TestScope')
        assert result['type'] == 'success'
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    print()
    
    # ==================== UPDATE OPERATIONS ====================
    
    print("✏️  TESTING UPDATE OPERATIONS:")
    print("-" * 70)
    
    # Test 8: Update Asset description
    test_name = "Update Asset description"
    try:
        result = coordinator.handleOperation('update', 'asset', 'update asset TestAsset description Updated description')
        assert result['type'] == 'success'
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    # Test 9: Update Scope status
    test_name = "Update Scope status"
    try:
        result = coordinator.handleOperation('update', 'scope', 'update scope TestScope status ACTIVE')
        assert result['type'] == 'success'
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    print()
    
    # ==================== DELETE OPERATIONS ====================
    
    print("🗑️  TESTING DELETE OPERATIONS:")
    print("-" * 70)
    
    # Test 10: Delete Asset
    test_name = "Delete Asset"
    try:
        result = coordinator.handleOperation('delete', 'asset', 'delete asset TestAsset')
        assert result['type'] == 'success'
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    print()
    
    # ==================== ERROR HANDLING ====================
    
    print("⚠️  TESTING ERROR HANDLING:")
    print("-" * 70)
    
    # Test 11: Invalid operation
    test_name = "Invalid operation"
    try:
        result = coordinator.handleOperation('invalid', 'asset', 'invalid operation')
        assert result['type'] == 'error', "Should return error for invalid operation"
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    # Test 12: Create without name
    test_name = "Create without name (error handling)"
    try:
        result = coordinator.handleOperation('create', 'asset', 'create asset')
        assert result['type'] == 'error', "Should return error when name missing"
        print(f"  ✅ {test_name}")
        results['passed'] += 1
        results['tests'].append({'name': test_name, 'status': 'PASS'})
    except Exception as e:
        print(f"  ❌ {test_name}: {str(e)}")
        results['failed'] += 1
        results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
    
    print()
    
    # ==================== SUMMARY ====================
    
    print("="*70)
    print("  TEST SUMMARY")
    print("="*70)
    print(f"Total Tests: {results['passed'] + results['failed']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Success Rate: {(results['passed'] / (results['passed'] + results['failed']) * 100):.1f}%")
    print("="*70)
    
    if results['failed'] == 0:
        print("\n🎉 ALL TESTS PASSED! Phase 4 ISMS Coordinator is READY!")
    else:
        print(f"\n⚠️  {results['failed']} test(s) failed. Review errors above.")
        print("\nFailed tests:")
        for test in results['tests']:
            if test['status'] == 'FAIL':
                print(f"  - {test['name']}: {test.get('error', 'Unknown error')}")
    
    print()
    return results


if __name__ == "__main__":
    results = test_all_operations()
    exit(0 if results['failed'] == 0 else 1)
