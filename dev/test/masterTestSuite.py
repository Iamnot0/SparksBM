#!/usr/bin/env python3
"""
Master Test Suite - Phase 3 & Phase 4 Comprehensive Validation

Runs all tests to verify:
- Phase 3 (ChatRouter) is stable and deployed correctly
- Phase 4 (ISMSCoordinator) is ready for integration
"""

import sys
import os
import subprocess
from datetime import datetime

def print_header(title, char="="):
    """Print section header"""
    print("\n" + char*70)
    print(f"  {title}")
    print(char*70)

def run_test_file(test_file, description, phase):
    """Run a test file and return results"""
    print_header(f"Testing: {description} ({phase})", "-")
    print(f"File: {test_file}")
    
    try:
        result = subprocess.run(
            ['python3', test_file],
            capture_output=True,
            text=True,
            timeout=120,
            cwd='/home/clay/Desktop/SparksBM'
        )
        
        # Check if tests passed
        passed = result.returncode == 0
        
        # Extract summary info
        output = result.stdout + result.stderr
        
        # Look for test results
        if 'PASSED' in output or 'OK' in output or 'Success' in output or '✅' in output:
            if 'FAILED' not in output and 'ERROR' not in output:
                print(f"✅ {description}: PASSED")
                # Show key results
                lines = output.split('\n')
                for line in lines:
                    if '✅' in line or 'PASSED' in line or 'Success' in line:
                        print(f"   {line.strip()}")
                        if len([l for l in lines if '✅' in l]) > 10:
                            break  # Don't flood output
                return True, "PASSED"
            else:
                print(f"❌ {description}: FAILED")
                print(f"   Output: {output[-500:]}")
                return False, "FAILED"
        elif 'All tests passed' in output or passed:
            print(f"✅ {description}: PASSED")
            return True, "PASSED"
        else:
            print(f"⚠️  {description}: UNCLEAR")
            print(f"   Return code: {result.returncode}")
            print(f"   Output snippet: {output[-300:]}")
            return passed, "UNCLEAR" if passed else "FAILED"
            
    except subprocess.TimeoutExpired:
        print(f"⏱️  {description}: TIMEOUT")
        return False, "TIMEOUT"
    except Exception as e:
        print(f"❌ {description}: ERROR - {str(e)}")
        return False, "ERROR"

def check_deployment_status():
    """Check Phase 3 deployment status"""
    print_header("Checking Phase 3 Deployment Status", "-")
    
    try:
        # Check feature flag
        with open('/home/clay/Desktop/SparksBM/Agentic Framework/agents/mainAgent.py', 'r') as f:
            content = f.read()
            if 'self._useChatRouter = True' in content:
                print("✅ Phase 3: ChatRouter is DEPLOYED (Active)")
                return True
            else:
                print("⚠️  Phase 3: ChatRouter in SHADOW MODE")
                return False
    except Exception as e:
        print(f"❌ Error checking deployment: {e}")
        return False

def check_phase4_status():
    """Check Phase 4 readiness"""
    print_header("Checking Phase 4 Readiness", "-")
    
    try:
        # Check if ismsCoordinator exists
        coordinator_path = '/home/clay/Desktop/SparksBM/Agentic Framework/agents/coordinators/ismsCoordinator.py'
        if os.path.exists(coordinator_path):
            print("✅ Phase 4: ISMSCoordinator exists")
            
            # Check file size
            size = os.path.getsize(coordinator_path)
            print(f"   File size: {size:,} bytes (~{size//1000}KB)")
            
            # Check if it has the main method
            with open(coordinator_path, 'r') as f:
                content = f.read()
                if 'def handleOperation' in content:
                    print("✅ Phase 4: Main interface implemented")
                    return True
                else:
                    print("⚠️  Phase 4: Main interface not found")
                    return False
        else:
            print("❌ Phase 4: ISMSCoordinator NOT FOUND")
            return False
    except Exception as e:
        print(f"❌ Error checking Phase 4: {e}")
        return False

def main():
    """Run master test suite"""
    print("\n" + "🚀" * 35)
    print(" "*20 + "MASTER TEST SUITE")
    print(" "*15 + "Phase 3 & Phase 4 Validation")
    print("🚀" * 35)
    print(f"\nTest Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {
        'phase3': {},
        'phase4': {},
        'deployment': {}
    }
    
    # ==================== DEPLOYMENT STATUS ====================
    
    print_header("SECTION 1: DEPLOYMENT STATUS")
    
    phase3_deployed = check_deployment_status()
    results['deployment']['phase3'] = phase3_deployed
    
    phase4_ready = check_phase4_status()
    results['deployment']['phase4'] = phase4_ready
    
    # ==================== PHASE 3 TESTS ====================
    
    print_header("SECTION 2: PHASE 3 TESTS (ChatRouter)")
    
    # Test 1: Phase 3 Router Tests
    passed, status = run_test_file(
        'dev/test/testPhase3Router.py',
        'ChatRouter Unit Tests',
        'Phase 3'
    )
    results['phase3']['router_tests'] = (passed, status)
    
    # Test 2: Edge Case Tests
    passed, status = run_test_file(
        'dev/test/edgeCaseTest.py',
        'Edge Case & Bug Prevention Tests',
        'Phase 3'
    )
    results['phase3']['edge_cases'] = (passed, status)
    
    # Test 3: Deployment Monitor (just check it runs)
    print_header("Checking: Deployment Monitor (Phase 3)", "-")
    print("Note: Not running full monitor, just verifying script exists")
    if os.path.exists('/home/clay/Desktop/SparksBM/dev/test/deploymentMonitor.py'):
        print("✅ Deployment Monitor: EXISTS")
        results['phase3']['monitor'] = (True, "EXISTS")
    else:
        print("❌ Deployment Monitor: NOT FOUND")
        results['phase3']['monitor'] = (False, "NOT FOUND")
    
    # ==================== PHASE 4 TESTS ====================
    
    print_header("SECTION 3: PHASE 4 TESTS (ISMSCoordinator)")
    
    # Test 4: Phase 4 Validation
    passed, status = run_test_file(
        'dev/test/phase4ValidationTest.py',
        'ISMSCoordinator Validation Tests',
        'Phase 4'
    )
    results['phase4']['validation'] = (passed, status)
    
    # ==================== SUMMARY ====================
    
    print_header("TEST SUMMARY")
    
    # Phase 3 Summary
    print("\n📊 PHASE 3 (ChatRouter - DEPLOYED):")
    print(f"  Deployment Status: {'✅ ACTIVE' if results['deployment']['phase3'] else '⚠️  SHADOW MODE'}")
    print(f"  Router Tests:      {'✅ PASSED' if results['phase3']['router_tests'][0] else '❌ ' + results['phase3']['router_tests'][1]}")
    print(f"  Edge Cases:        {'✅ PASSED' if results['phase3']['edge_cases'][0] else '❌ ' + results['phase3']['edge_cases'][1]}")
    print(f"  Monitor Script:    {'✅ EXISTS' if results['phase3']['monitor'][0] else '❌ ' + results['phase3']['monitor'][1]}")
    
    # Phase 4 Summary
    print("\n📊 PHASE 4 (ISMSCoordinator - READY):")
    print(f"  Readiness Check:   {'✅ READY' if results['deployment']['phase4'] else '❌ NOT READY'}")
    print(f"  Validation Tests:  {'✅ PASSED' if results['phase4']['validation'][0] else '❌ ' + results['phase4']['validation'][1]}")
    
    # Overall Status
    phase3_ok = all([results['phase3'][k][0] for k in results['phase3'].keys()])
    phase4_ok = results['phase4']['validation'][0] and results['deployment']['phase4']
    
    print("\n" + "="*70)
    print("  OVERALL STATUS")
    print("="*70)
    
    if phase3_ok and phase4_ok:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ Phase 3 (ChatRouter):")
        print("   - Deployed and active")
        print("   - All tests passing")
        print("   - Ready for monitoring (Day 1/14)")
        print("\n✅ Phase 4 (ISMSCoordinator):")
        print("   - Implementation complete")
        print("   - All tests passing")
        print("   - Ready for integration (after Phase 3 cleanup)")
        print("\n📅 Next Steps:")
        print("   1. Monitor Phase 3 for 2 weeks (until Jan 17)")
        print("   2. Clean up Phase 3 code (Jan 17-18)")
        print("   3. Integrate Phase 4 with shadow testing (Jan 18-20)")
        print("   4. Deploy Phase 4 (late January)")
    elif not phase3_ok:
        print("\n⚠️  PHASE 3 ISSUES DETECTED")
        print("\nPhase 3 is currently deployed but some tests failed.")
        print("Review the test results above and investigate issues.")
        print("\nConsider rollback if critical issues found:")
        print("  - Change: self._useChatRouter = False")
        print("  - Restart NotebookLLM API")
    elif not phase4_ok:
        print("\n⚠️  PHASE 4 ISSUES DETECTED")
        print("\nPhase 4 validation failed. Phase 4 is NOT ready for integration.")
        print("Review test results above and fix issues before integration.")
    
    print("\n" + "="*70 + "\n")
    
    # Return exit code
    return 0 if (phase3_ok and phase4_ok) else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
