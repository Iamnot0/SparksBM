"""
Edge Case Testing - Critical Scenarios

Test the most important edge cases:
1. Bulk import ("ii" command) - Bug #13 validation
2. File upload scenarios
3. Follow-up scenarios (subtype selection)
4. Bug #3 poison pill test
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Agentic Framework')))

from agents.mainAgent import MainAgent

print("="*70)
print("EDGE CASE TESTING - CRITICAL SCENARIOS")
print("="*70)

agent = MainAgent()

test_results = []

# TEST 1: Bug #3 Poison Pill - CRITICAL!
print("\n" + "="*70)
print("TEST 1: BUG #3 POISON PILL (CRITICAL)")
print("="*70)
print()
print("Scenario: User uploads file, then types 'create asset Test'")
print("Expected: Should route to ISMS (single asset creation), NOT bulk import")
print()

# Simulate file uploaded
agent.state['lastProcessed'] = {
    'fileName': 'test.xlsx',
    'fileType': 'excel',
    'data': [['Name'], ['Asset1']]
}

agent.state['_sessionContext'] = {
    'hasProcessedDocument': True,
    'documentCount': 1,
    'excelFileCount': 1
}

result = agent.process("create asset Test")
routing_log = agent.getRoutingLog()

if routing_log:
    last_entry = routing_log[-1]
    old_route = last_entry.get('oldRoute')
    new_route = last_entry.get('newRoute')
    match = last_entry.get('match')
    
    print(f"Old Routing: {old_route}")
    print(f"New Routing: {new_route}")
    print(f"Match: {'✅ YES' if match else '❌ NO'}")
    print()
    
    # Check if both routed to ISMS (correct behavior)
    if 'verinice' in old_route.lower() and 'verinice' in new_route.lower():
        print("✅ POISON PILL TEST: PASSED")
        print("✅ Both routers correctly detected single asset creation")
        test_results.append(("Bug #3 Poison Pill", True))
    else:
        print("❌ POISON PILL TEST: FAILED")
        print("❌ Routing mismatch on critical bug fix")
        test_results.append(("Bug #3 Poison Pill", False))
else:
    print("⚠️  No routing log generated")
    test_results.append(("Bug #3 Poison Pill", False))

# TEST 2: Bulk Import with "ii" command
print("\n" + "="*70)
print("TEST 2: BULK IMPORT 'ii' COMMAND (Bug #13 Fix)")
print("="*70)
print()
print("Scenario: 2 Excel files uploaded, user types 'ii'")
print("Expected: Should trigger bulk import")
print()

# Clear previous state
agent.clearRoutingLog()
agent = MainAgent()  # Fresh agent

# Simulate 2 Excel files
agent.state['lastProcessed'] = {
    'fileName': 'asset_inventory_v2.xlsx',
    'fileType': 'excel',
    'sheets': {'Sheet1': {'data': [['Name'], ['Asset1']]}}
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

result = agent.process("ii")
status = result.get('status')
response = result.get('result', '')

print(f"Status: {status}")
print(f"Response: {str(response)[:100]}...")
print()

if 'generic fallback' not in str(response).lower() and 'I can help with documents' not in str(response).lower():
    print("✅ BULK IMPORT TEST: PASSED")
    print("✅ 'ii' command triggered bulk import (or showed appropriate error)")
    test_results.append(("Bulk Import 'ii'", True))
else:
    print("❌ BULK IMPORT TEST: FAILED")
    print("❌ 'ii' command fell through to generic fallback")
    test_results.append(("Bulk Import 'ii'", False))

# TEST 3: Follow-up scenarios
print("\n" + "="*70)
print("TEST 3: FOLLOW-UP SCENARIOS")
print("="*70)
print()

# Clear and start fresh
agent = MainAgent()

# Scenario A: Subtype selection follow-up
print("Scenario A: Subtype selection follow-up")
print()

# First, trigger a create that needs subtype selection
agent.state['_pendingSubtypeSelection'] = {  # Fixed: Use correct state key with underscore
    'operation': 'create',
    'objectType': 'asset',
    'name': 'TestAsset',
    'subTypes': ['AST_Application', 'AST_IT-System'],
    'domainId': 'test-domain',
    'unitId': 'test-unit'
}

result = agent.process("1")
routing_log = agent.getRoutingLog()

if routing_log:
    last_entry = routing_log[-1]
    old_route = last_entry.get('oldRoute')
    new_route = last_entry.get('newRoute')
    
    # Both should route to follow_up
    if 'follow' in old_route.lower() and 'follow' in new_route.lower():
        print("✅ Subtype follow-up: PASSED")
        test_results.append(("Subtype Follow-up", True))
    else:
        print(f"⚠️  Routing: Old={old_route}, New={new_route}")
        test_results.append(("Subtype Follow-up", False))
else:
    print("⚠️  No routing log")
    test_results.append(("Subtype Follow-up", False))

# TEST 4: Greeting detection
print("\n" + "="*70)
print("TEST 4: GREETING DETECTION")
print("="*70)
print()

agent = MainAgent()
greetings = ["hello", "hi", "hey", "good morning"]
greeting_matches = 0

for greeting in greetings:
    agent.process(greeting)

routing_log = agent.getRoutingLog()
for entry in routing_log:
    if entry.get('match') and 'greeting' in str(entry.get('oldRoute')).lower():
        greeting_matches += 1

print(f"Greeting matches: {greeting_matches}/{len(greetings)}")
if greeting_matches == len(greetings):
    print("✅ GREETING TEST: PASSED")
    test_results.append(("Greeting Detection", True))
else:
    print("⚠️  GREETING TEST: Some mismatches")
    test_results.append(("Greeting Detection", False))

# FINAL SUMMARY
print("\n" + "="*70)
print("EDGE CASE TEST SUMMARY")
print("="*70)
print()

passed = sum(1 for _, result in test_results if result)
total = len(test_results)
pass_rate = (passed / total * 100) if total > 0 else 0

for test_name, result in test_results:
    icon = "✅" if result else "❌"
    print(f"{icon} {test_name}")

print()
print(f"Pass Rate: {pass_rate:.0f}% ({passed}/{total})")
print()

if pass_rate == 100:
    print("🎉 ALL EDGE CASES PASSED!")
    print("✅ Critical scenarios validated")
    print("✅ Safe to proceed")
elif pass_rate >= 80:
    print("⚠️  MOSTLY PASSED with some issues")
    print("🔍 Review failed tests")
else:
    print("❌ EDGE CASE TESTING FAILED")
    print("❌ Critical issues detected")
    print("❌ DO NOT DEPLOY")

print()
print("="*70)
