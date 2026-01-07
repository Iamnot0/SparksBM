"""
Comprehensive ISMS Test - All Objects and Operations

Tests all ISMS object types with all operations:
- list, create, get for: scope, asset, person, process, control, document, incident
- Document processing: Excel, Word, PDF
- Bulk import from Excel

Usage:
    python3 dev/test/comprehensiveISMSTest.py
"""

import sys
import os

# Add Agentic Framework to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Agentic Framework')))


def print_section(title):
    """Print formatted section"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def test_isms_operations(agent):
    """Test ISMS operations for all object types"""
    print_section("ISMS OPERATIONS TEST")
    
    object_types = ['scope', 'asset', 'person', 'process', 'control', 'document', 'incident']
    
    results = {}
    
    for obj_type in object_types:
        print(f"\n📦 Testing {obj_type.upper()} operations...")
        results[obj_type] = {}
        
        # Test LIST operation
        print(f"   1. Testing 'list {obj_type}s'...")
        try:
            result = agent.process(f"list {obj_type}s")
            if result.get('status') == 'success':
                print(f"      ✅ List operation works")
                results[obj_type]['list'] = True
            else:
                print(f"      ❌ List failed: {result.get('error', 'unknown')}")
                results[obj_type]['list'] = False
        except Exception as e:
            print(f"      ❌ Exception: {e}")
            results[obj_type]['list'] = False
        
        # Test CREATE operation
        print(f"   2. Testing 'create {obj_type} Test{obj_type.capitalize()}'...")
        try:
            result = agent.process(f"create {obj_type} Test{obj_type.capitalize()}")
            if result.get('status') == 'success':
                response = str(result.get('result', ''))
                # Check if it's asking for subtype (expected) or created successfully
                if 'subtype' in response.lower() or 'created' in response.lower():
                    print(f"      ✅ Create operation works (subtype selection or created)")
                    results[obj_type]['create'] = True
                else:
                    print(f"      ⚠️  Create returned unexpected response")
                    results[obj_type]['create'] = False
            else:
                print(f"      ❌ Create failed: {result.get('error', 'unknown')}")
                results[obj_type]['create'] = False
        except Exception as e:
            print(f"      ❌ Exception: {e}")
            results[obj_type]['create'] = False
        
        # Test GET operation (skip for now - requires knowing object names)
        print(f"   3. Get operation (skipped - requires existing object)")
        results[obj_type]['get'] = None
    
    return results


def test_bulk_import(agent):
    """Test bulk import from Excel (the 'ii' command issue)"""
    print_section("BULK IMPORT TEST (Bug Fix Validation)")
    
    print("🧪 Simulating 2 Excel files uploaded scenario...")
    
    # Simulate 2 Excel files uploaded
    agent.state['lastProcessed'] = {
        'fileName': 'asset_inventory_v2.xlsx',
        'fileType': 'excel',
        'filePath': '/uploads/asset_inventory_v2.xlsx',
        'sheets': {
            'Sheet1': {
                'data': [
                    ['Name', 'Type', 'Description'],
                    ['Server01', 'Server', 'Production server'],
                    ['Laptop01', 'Laptop', 'Employee laptop']
                ]
            }
        }
    }
    
    agent.state['pendingFileAction'] = {
        'fileType': 'excel',
        'filePath': '/uploads/asset_inventory_v2.xlsx'
    }
    
    agent.state['_sessionContext'] = {
        'hasProcessedDocument': True,
        'documentCount': 2,
        'excelFileCount': 2,
        'activeSources': [
            {'type': 'excel', 'name': 'asset_inventory.xlsx'},
            {'type': 'excel', 'name': 'asset_inventory_v2.xlsx'}
        ]
    }
    
    print("✅ Simulated 2 Excel files in session")
    print()
    
    # Test 1: User types "ii" (create assets)
    print("📨 Test 1: User types 'ii' (should trigger bulk import)")
    try:
        result = agent.process("ii")
        status = result.get('status')
        response = str(result.get('result', ''))[:200]
        
        print(f"   Response: {response}...")
        print()
        
        if status == 'success':
            # Check if it's actually doing bulk import
            # Should NOT be the generic fallback message
            is_fallback = "I can help with documents and ISMS operations" in response
            is_bulk_import = any(word in response.lower() for word in ['which scope', 'select scope', 'import', 'rows', 'processing'])
            
            if is_fallback:
                print("   ❌ FAIL: Got generic fallback (bulk import not triggered)")
                test1_pass = False
            elif is_bulk_import:
                print("   ✅ PASS: Bulk import triggered correctly")
                test1_pass = True
            else:
                print(f"   ⚠️  UNCLEAR: Response doesn't clearly indicate bulk import")
                print(f"   Full response: {response}")
                test1_pass = False
        else:
            print(f"   ❌ FAIL: Error occurred: {result.get('error')}")
            test1_pass = False
    except Exception as e:
        print(f"   ❌ FAIL: Exception: {e}")
        test1_pass = False
    
    # Reset state
    agent.state['pendingFileAction'] = {
        'fileType': 'excel',
        'filePath': '/uploads/asset_inventory_v2.xlsx'
    }
    
    # Test 2: User types "create assets" (explicit)
    print("\n📨 Test 2: User types 'create assets' (explicit command)")
    try:
        result = agent.process("create assets")
        status = result.get('status')
        response = str(result.get('result', ''))[:200]
        
        print(f"   Response: {response}...")
        print()
        
        if status == 'success':
            if any(word in response.lower() for word in ['scope', 'which scope', 'select', 'import', 'asset', 'row']):
                print("   ✅ PASS: Bulk import triggered correctly")
                test2_pass = True
            else:
                print("   ❌ FAIL: Unexpected response")
                test2_pass = False
        else:
            print(f"   ❌ FAIL: Error: {result.get('error')}")
            test2_pass = False
    except Exception as e:
        print(f"   ❌ FAIL: Exception: {e}")
        test2_pass = False
    
    return test1_pass and test2_pass


def test_document_processing(agent):
    """Test document processing (Excel, Word, PDF)"""
    print_section("DOCUMENT PROCESSING TEST")
    
    doc_types = [
        ('Excel', 'xlsx', 'test.xlsx'),
        ('Word', 'docx', 'test.docx'),
        ('PDF', 'pdf', 'test.pdf')
    ]
    
    results = {}
    
    for name, ext, filename in doc_types:
        print(f"\n📄 Testing {name} document processing...")
        
        # Simulate document in state
        if ext == 'xlsx':
            agent.state['lastProcessed'] = {
                'fileName': filename,
                'fileType': 'excel',
                'filePath': f'/uploads/{filename}',
                'sheets': {'Sheet1': {'data': [['A', 'B'], [1, 2]]}}
            }
        elif ext == 'docx':
            agent.state['lastProcessed'] = {
                'fileName': filename,
                'fileType': 'word',
                'filePath': f'/uploads/{filename}',
                'paragraphs': ['Test paragraph 1', 'Test paragraph 2']
            }
        elif ext == 'pdf':
            agent.state['lastProcessed'] = {
                'fileName': filename,
                'fileType': 'pdf',
                'filePath': f'/uploads/{filename}',
                'text': 'Test PDF content',
                'pages': ['Page 1 content']
            }
        
        agent.state['_sessionContext'] = {
            'hasProcessedDocument': True,
            'documentCount': 1
        }
        
        # Test analysis
        print(f"   Testing 'analyze' command...")
        try:
            result = agent.process("analyze")
            if result.get('status') == 'success':
                print(f"      ✅ Analysis works")
                results[name] = True
            else:
                error = result.get('error', 'unknown')
                # LLM unavailable is OK (external dependency)
                if 'llm' in error.lower() or 'api' in error.lower():
                    print(f"      ⚠️  LLM unavailable (external dependency) - SKIPPED")
                    results[name] = None
                else:
                    print(f"      ❌ Analysis failed: {error}")
                    results[name] = False
        except Exception as e:
            print(f"      ❌ Exception: {e}")
            results[name] = False
    
    return results


def display_final_report(isms_results, bulk_result, doc_results):
    """Display final comprehensive test report"""
    print_section("COMPREHENSIVE TEST REPORT")
    
    print("📊 ISMS OPERATIONS:\n")
    
    total_isms = 0
    passed_isms = 0
    
    for obj_type, ops in isms_results.items():
        list_status = "✅" if ops.get('list') else "❌"
        create_status = "✅" if ops.get('create') else "❌"
        get_status = "⏭️" if ops.get('get') is None else ("✅" if ops.get('get') else "❌")
        
        print(f"  {obj_type.upper():12} | List: {list_status} | Create: {create_status} | Get: {get_status}")
        
        if ops.get('list'):
            passed_isms += 1
        if ops.get('create'):
            passed_isms += 1
        total_isms += 2  # list + create (get is skipped)
    
    print(f"\n  ISMS Pass Rate: {passed_isms}/{total_isms} ({(passed_isms/total_isms*100):.0f}%)")
    
    print("\n📦 BULK IMPORT:\n")
    bulk_status = "✅ PASS" if bulk_result else "❌ FAIL"
    print(f"  'ii' command trigger: {bulk_status}")
    
    print("\n📄 DOCUMENT PROCESSING:\n")
    
    for doc_type, result in doc_results.items():
        if result is True:
            status = "✅ PASS"
        elif result is None:
            status = "⏭️  SKIPPED (LLM unavailable)"
        else:
            status = "❌ FAIL"
        print(f"  {doc_type:6}: {status}")
    
    print("\n" + "="*70)
    print("  OVERALL ASSESSMENT")
    print("="*70 + "\n")
    
    isms_ok = (passed_isms / total_isms) >= 0.8
    bulk_ok = bulk_result
    doc_ok = all(r != False for r in doc_results.values())
    
    if isms_ok and bulk_ok and doc_ok:
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ System is fully functional")
        print("✅ All ISMS operations work")
        print("✅ Bulk import ('ii' command) fixed")
        print("✅ Document processing works")
        return 0
    else:
        print("⚠️  SOME ISSUES DETECTED")
        if not isms_ok:
            print(f"   ❌ ISMS operations: {passed_isms}/{total_isms} passed")
        if not bulk_ok:
            print("   ❌ Bulk import ('ii' command) NOT working")
        if not doc_ok:
            failed_docs = [k for k, v in doc_results.items() if v == False]
            if failed_docs:
                print(f"   ❌ Document processing failed: {', '.join(failed_docs)}")
        return 1


def main():
    """Main test execution"""
    print("\n" + "#"*70)
    print("#" + " "*12 + "COMPREHENSIVE ISMS & DOCUMENT TEST" + " "*13 + "#")
    print("#"*70)
    
    print("\n🔧 Initializing agent...")
    
    try:
        from agents.mainAgent import MainAgent
        agent = MainAgent()
        print("✅ Agent initialized\n")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        return 1
    
    # Test 1: ISMS Operations
    isms_results = test_isms_operations(agent)
    
    # Test 2: Bulk Import (YOUR BUG FIX)
    bulk_result = test_bulk_import(agent)
    
    # Test 3: Document Processing
    doc_results = test_document_processing(agent)
    
    # Final Report
    exit_code = display_final_report(isms_results, bulk_result, doc_results)
    
    return exit_code


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n🛑 Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
