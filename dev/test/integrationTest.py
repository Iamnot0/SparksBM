"""
Phase 3 Integration Test - Live System Validation

This script tests the actual running system with shadow mode enabled.
It validates that:
1. Shadow testing is working
2. Routing decisions are logged
3. Bug #3 is prevented
4. All critical paths work correctly

Prerequisites:
- All servers must be running (NotebookLLM API, SparksbmISMS backend)
- Shadow mode should be enabled (_useChatRouter = False)

Usage:
    python3 dev/test/integrationTest.py
"""

import sys
import os
import time
import json

# Add Agentic Framework to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Agentic Framework')))


def printSection(title):
    """Print a formatted section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def testShadowModeEnabled():
    """Test 1: Verify shadow mode is enabled"""
    printSection("TEST 1: Shadow Mode Configuration")
    
    try:
        from agents.mainAgent import MainAgent
        
        agent = MainAgent()
        
        shadowEnabled = not agent._useChatRouter
        routerInitialized = agent._chatRouter is None  # Should be lazy-loaded
        
        print(f"Shadow Mode Enabled: {shadowEnabled}")
        print(f"Feature Flag (_useChatRouter): {agent._useChatRouter}")
        print(f"Router Lazy Init: {routerInitialized} (will init on first message)")
        
        if shadowEnabled:
            print("\n✅ PASS: Shadow mode correctly enabled")
            print("   Old routing will execute, new router will watch")
            return True, agent
        else:
            print("\n❌ FAIL: Shadow mode NOT enabled")
            print("   Set _useChatRouter = False in mainAgent.py line ~80")
            return False, None
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False, None


def testBasicRouting(agent):
    """Test 2: Basic routing without file context"""
    printSection("TEST 2: Basic Routing (No File Context)")
    
    testCases = [
        ("hello", "Should route to greeting"),
        ("list scopes", "Should route to ISMS/Verinice operation"),
        ("generate report", "Should route to report generation"),
    ]
    
    results = []
    
    for message, description in testCases:
        print(f"📨 Testing: '{message}'")
        print(f"   Expected: {description}")
        
        try:
            # Process message
            result = agent.process(message)
            
            # Check if successful
            status = result.get('status')
            response = result.get('result', '')
            
            if status == 'success':
                print(f"   Response: {str(response)[:80]}...")
                print("   ✅ Message processed successfully")
                results.append(True)
            else:
                error = result.get('error', 'Unknown error')
                print(f"   ❌ Error: {error}")
                results.append(False)
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            results.append(False)
        
        print()
        time.sleep(0.5)  # Brief pause between tests
    
    passCount = sum(results)
    totalCount = len(results)
    
    print(f"\n📊 Results: {passCount}/{totalCount} tests passed")
    
    if passCount == totalCount:
        print("✅ PASS: All basic routing tests succeeded")
        return True
    else:
        print(f"⚠️  PARTIAL: {totalCount - passCount} test(s) failed")
        return False


def testPoisonPill(agent):
    """Test 3: Bug #3 Poison Pill - CRITICAL TEST"""
    printSection("TEST 3: Poison Pill Test (Bug #3 Prevention)")
    
    print("🧪 Setting up poison pill scenario...")
    print("   Simulating: File uploaded + 'create asset Test'")
    
    # Simulate file upload by setting state
    agent.state['lastProcessed'] = {
        'fileName': 'test.xlsx',
        'fileType': 'excel',
        'filePath': '/uploads/test.xlsx',
        'sheets': {
            'Sheet1': {
                'data': [
                    ['Name', 'Type', 'Description'],
                    ['Test Asset', 'Server', 'Test data']
                ]
            }
        }
    }
    
    agent.state['_sessionContext'] = {
        'hasProcessedDocument': True,
        'documentCount': 1,
        'excelFileCount': 1,
        'activeSources': ['test.xlsx']
    }
    
    print("✅ Simulated file context set")
    print()
    
    # Now send the poison pill command
    print("📨 Sending: 'create asset Test'")
    print("   This is the Bug #3 scenario!")
    print()
    
    try:
        result = agent.process("create asset Test")
        
        status = result.get('status')
        response = str(result.get('result', ''))
        
        print(f"Response: {response[:150]}...")
        print()
        
        # Check if routed to ISMS (correct) or document operations (Bug #3 regression)
        if status == 'success':
            # Check response for ISMS indicators
            isISMS = any(keyword in response.lower() for keyword in [
                'create', 'asset', 'subtype', 'select', 'isms'
            ])
            
            # Check response for document/bulk import indicators (bad)
            isBulkImport = any(keyword in response.lower() for keyword in [
                'bulk', 'import', 'excel', 'rows', 'processing file'
            ])
            
            if isISMS and not isBulkImport:
                print("✅ PASS: Correctly routed to ISMS operations")
                print("   Bug #3 regression PREVENTED!")
                return True
            elif isBulkImport:
                print("❌ CRITICAL FAIL: Routed to document/bulk import")
                print("   🚨 BUG #3 REGRESSION DETECTED!")
                print("   This is a BLOCKER - do NOT proceed to active mode")
                return False
            else:
                print("⚠️  WARNING: Response unclear, needs manual verification")
                print(f"   Full response: {response}")
                return False
        else:
            error = result.get('error', 'Unknown error')
            print(f"❌ Error occurred: {error}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def testShadowLogging(agent):
    """Test 4: Verify shadow logging is working"""
    printSection("TEST 4: Shadow Mode Logging")
    
    print("📊 Checking routing log...")
    
    try:
        routingLog = agent.getRoutingLog()
        
        totalMessages = len(routingLog)
        matches = sum(1 for entry in routingLog if entry.get('match', False))
        mismatches = [e for e in routingLog if not e.get('match', False)]
        
        matchRate = (matches / totalMessages * 100) if totalMessages > 0 else 0
        
        print(f"Total messages logged: {totalMessages}")
        print(f"Matches: {matches}")
        print(f"Mismatches: {len(mismatches)}")
        print(f"Match rate: {matchRate:.1f}%")
        print()
        
        if totalMessages == 0:
            print("⚠️  WARNING: No messages in log")
            print("   This might mean shadow testing isn't recording")
            return False
        
        if mismatches:
            print(f"❌ MISMATCHES DETECTED ({len(mismatches)}):")
            for idx, m in enumerate(mismatches[:3], 1):  # Show first 3
                print(f"\n   Mismatch #{idx}:")
                print(f"   Message: '{m.get('message', '')[:50]}...'")
                print(f"   Old Route: {m.get('oldRoute', 'unknown')}")
                print(f"   New Route: {m.get('newRoute', 'unknown')}")
            
            if len(mismatches) > 3:
                print(f"\n   ... and {len(mismatches) - 3} more mismatch(es)")
            
            print(f"\n⚠️  PARTIAL PASS: Logging works but {len(mismatches)} mismatch(es) found")
            print("   Investigate mismatches before switching to active mode")
            return False
        else:
            print("✅ PASS: Shadow logging working perfectly")
            print("   All routing decisions match between old and new router")
            return True
            
    except AttributeError:
        print("❌ FAIL: getRoutingLog() method not available")
        print("   Shadow testing infrastructure may not be properly installed")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def testStateValidator(agent):
    """Test 5: Verify state validator is working"""
    printSection("TEST 5: State Validator (Bug #3 Prevention)")
    
    print("🔍 Testing state validation...")
    
    try:
        from orchestrator.chatRouter import ChatRouter
        from agents.instructions import VERINICE_OBJECT_TYPES
        
        router = ChatRouter(VERINICE_OBJECT_TYPES)
        
        # Test 1: Valid state
        print("\nTest 5.1: Valid state (should accept)")
        try:
            validState = {}
            context = {'hasProcessedDocument': False}
            decision = router.route("hello", validState, context)
            print("   ✅ Valid state accepted")
            test1Pass = True
        except Exception as e:
            print(f"   ❌ Valid state rejected: {e}")
            test1Pass = False
        
        # Test 2: Invalid state (not a dict)
        print("\nTest 5.2: Invalid state (should reject)")
        try:
            invalidState = "not a dict"
            context = {'hasProcessedDocument': False}
            decision = router.route("hello", invalidState, context)
            print("   ❌ Invalid state NOT rejected (should have raised ValueError)")
            test2Pass = False
        except ValueError as e:
            print(f"   ✅ Invalid state correctly rejected: {e}")
            test2Pass = True
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            test2Pass = False
        
        print()
        if test1Pass and test2Pass:
            print("✅ PASS: State validator working correctly")
            print("   Bug #3 prevention mechanism active")
            return True
        else:
            print("❌ FAIL: State validator not working properly")
            return False
            
    except ImportError as e:
        print(f"❌ ERROR: Cannot import ChatRouter: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def displayFinalReport(results):
    """Display final test report"""
    printSection("FINAL TEST REPORT")
    
    testNames = [
        "Shadow Mode Configuration",
        "Basic Routing",
        "Poison Pill (Bug #3)",
        "Shadow Logging",
        "State Validator"
    ]
    
    print("Test Results:")
    print()
    
    for idx, (name, passed) in enumerate(zip(testNames, results), 1):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {idx}. {name:30} {status}")
    
    print()
    print("-" * 70)
    
    passCount = sum(results)
    totalCount = len(results)
    passRate = (passCount / totalCount * 100) if totalCount > 0 else 0
    
    print(f"Total: {totalCount} | Passed: {passCount} | Failed: {totalCount - passCount}")
    print(f"Pass Rate: {passRate:.0f}%")
    print()
    
    if passCount == totalCount:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("✅ Phase 3 is working correctly in shadow mode")
        print("✅ Ready for production deployment")
        print()
        print("📋 NEXT STEPS:")
        print("   1. Process 100+ real messages in your application")
        print("   2. Check routing log: agent.getRoutingLog()")
        print("   3. Verify 100% match rate")
        print("   4. Switch to active mode: agent.enableChatRouter()")
        print()
    elif results[2]:  # Poison pill test passed
        print("⚠️  SOME TESTS FAILED")
        print()
        print("✅ Critical: Poison Pill test PASSED (Bug #3 prevented)")
        print(f"❌ {totalCount - passCount} other test(s) failed")
        print()
        print("📋 NEXT STEPS:")
        print("   1. Investigate failed tests")
        print("   2. Fix issues before proceeding")
        print("   3. Re-run this test suite")
        print()
    else:
        print("🚨 CRITICAL FAILURE")
        print()
        print("❌ Poison Pill test FAILED or not run")
        print("   This means Bug #3 may have regressed")
        print()
        print("🛑 DO NOT PROCEED TO ACTIVE MODE")
        print()
        print("📋 IMMEDIATE ACTION:")
        print("   1. Review Poison Pill test failure")
        print("   2. Check state management in mainAgent.py")
        print("   3. Run unit tests: python3 dev/test/testPhase3Router.py")
        print("   4. Contact development team if issue persists")
        print()


def main():
    """Main test execution"""
    print("\n" + "#"*70)
    print("#" + " "*15 + "PHASE 3 INTEGRATION TEST" + " "*15 + "#")
    print("#" + " "*15 + "Live System Validation" + " "*18 + "#")
    print("#"*70)
    
    print("\n⚠️  Prerequisites:")
    print("   - NotebookLLM API must be running")
    print("   - SparksbmISMS backend must be running")
    print("   - Shadow mode should be enabled")
    print()
    print("🚀 Starting tests...\n")
    
    results = []
    agent = None
    
    # Test 1: Shadow mode configuration
    test1Pass, agent = testShadowModeEnabled()
    results.append(test1Pass)
    
    if not test1Pass or not agent:
        print("\n🛑 Cannot proceed: Shadow mode not properly configured")
        print("   Fix configuration and re-run this test")
        return 1
    
    # Test 2: Basic routing
    test2Pass = testBasicRouting(agent)
    results.append(test2Pass)
    
    # Test 3: Poison pill (CRITICAL)
    test3Pass = testPoisonPill(agent)
    results.append(test3Pass)
    
    # Test 4: Shadow logging
    test4Pass = testShadowLogging(agent)
    results.append(test4Pass)
    
    # Test 5: State validator
    test5Pass = testStateValidator(agent)
    results.append(test5Pass)
    
    # Final report
    displayFinalReport(results)
    
    # Return exit code
    if all(results):
        return 0  # Success
    elif results[2]:  # Poison pill passed
        return 2  # Warning (some tests failed but critical test passed)
    else:
        return 1  # Failure (critical test failed)


if __name__ == "__main__":
    try:
        exitCode = main()
        sys.exit(exitCode)
    except KeyboardInterrupt:
        print("\n\n🛑 Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
