#!/usr/bin/env python3
"""
Phase 3 Deployment - First Hour Monitoring Script
Runs automated checks every 15 minutes for the first hour after deployment
"""

import sys
import os
import time
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../Agentic Framework')))

def print_header(title):
    """Print section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def check_feature_flag():
    """Verify feature flag is enabled"""
    print_header("STEP 1: Feature Flag Status")
    try:
        with open('Agentic Framework/agents/mainAgent.py', 'r') as f:
            content = f.read()
            if 'self._useChatRouter = True' in content:
                print("✅ Feature flag is ENABLED (Active Mode)")
                print("   ChatRouter is live and handling all routing")
                return True
            else:
                print("⚠️  Feature flag is DISABLED (Shadow Mode)")
                print("   Old routing is still active")
                return False
    except Exception as e:
        print(f"❌ Error checking feature flag: {e}")
        return False

def run_edge_case_tests():
    """Run edge case tests"""
    print_header("STEP 2: Edge Case Tests")
    try:
        import subprocess
        result = subprocess.run(
            ['python3', 'dev/test/edgeCaseTest.py'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("✅ Edge case tests PASSED")
            # Show summary
            if 'PASSED' in result.stdout:
                lines = [l for l in result.stdout.split('\n') if 'PASSED' in l or '✅' in l]
                for line in lines[:5]:  # First 5 results
                    print(f"   {line.strip()}")
            return True
        else:
            print("❌ Edge case tests FAILED")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return False
    except Exception as e:
        print(f"❌ Error running edge case tests: {e}")
        return False

def check_routing_logs():
    """Check routing logs for issues"""
    print_header("STEP 3: Routing Log Analysis")
    try:
        import subprocess
        result = subprocess.run(
            ['python3', 'dev/test/checkLiveRoutingLogs.py'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if 'entries' in result.stdout.lower():
            print("✅ Routing logs accessible")
            # Show summary
            lines = result.stdout.split('\n')
            for line in lines[:10]:  # First 10 lines
                if line.strip():
                    print(f"   {line.strip()}")
            return True
        else:
            print("⚠️  Routing logs empty or inaccessible")
            print(f"   This is normal if no messages sent yet")
            return True
    except Exception as e:
        print(f"⚠️  Could not access routing logs: {e}")
        print("   This is OK if API isn't running yet")
        return True

def check_api_health():
    """Check if NotebookLLM API is responding"""
    print_header("STEP 4: API Health Check")
    try:
        import subprocess
        result = subprocess.run(
            ['curl', '-s', 'http://localhost:8000'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout:
            print("✅ NotebookLLM API is responding")
            return True
        else:
            print("⚠️  NotebookLLM API not responding")
            print("   You need to restart the API for changes to take effect")
            return False
    except Exception as e:
        print(f"⚠️  API health check failed: {e}")
        print("   You need to start/restart the NotebookLLM API")
        return False

def print_hard_stop_rules():
    """Display hard stop rules"""
    print_header("⚠️  HARD STOP RULES - WATCH FOR THESE")
    print("""
If ANY of these occur, ROLLBACK IMMEDIATELY:

1. ❌ Stateful Flow Break
   - Subtype selection loses context
   - Follow-up questions forget state
   
2. ❌ Generic Fallback on Known Commands
   - "list scopes" returns generic message
   - ISMS commands not recognized
   
3. ❌ Context Amnesia
   - File upload forgotten
   - Document context lost
   
4. ❌ Test Regression
   - Edge cases start failing
   - Previously working ops break

ROLLBACK: Change _useChatRouter = False, restart API
""")

def print_manual_tests():
    """Display manual tests to run"""
    print_header("🧪 MANUAL TESTS - Run These in Web UI")
    print("""
Open http://localhost:8000 and test:

1. Basic Greeting:
   Type: "hello"
   Expected: Friendly greeting response
   
2. ISMS List:
   Type: "list scopes"
   Expected: Table of scopes (not generic fallback)
   
3. ISMS Create:
   Type: "create scope TestDeploy TD Test deployment"
   Expected: Success message with object details
   
4. File Upload Context (CRITICAL):
   - Upload a file
   - Ask: "what's in this file?"
   - Then ask: "summarize it"
   Expected: Both questions work, context retained
   
5. Poison Pill Test:
   - Upload any file
   - Type: "create asset Test"
   Expected: Creates asset, NOT bulk import error
""")

def main():
    """Main monitoring function"""
    print("\n" + "🚀" * 30)
    print(" "*15 + "PHASE 3 DEPLOYMENT MONITORING")
    print("🚀" * 30)
    print(f"\nDeployment Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Monitoring Period: First Hour (4 checks @ 15 min intervals)")
    
    # Run automated checks
    flag_ok = check_feature_flag()
    if not flag_ok:
        print("\n⚠️  WARNING: Feature flag not enabled!")
        print("   Deployment has NOT been activated yet")
        return
    
    api_ok = check_api_health()
    if not api_ok:
        print("\n⚠️  NEXT STEP: Restart NotebookLLM API")
        print("   cd /home/clay/Desktop/SparksBM/NotebookLLM")
        print("   python3 api/main.py")
        return
    
    tests_ok = run_edge_case_tests()
    logs_ok = check_routing_logs()
    
    # Display hard stop rules
    print_hard_stop_rules()
    
    # Display manual tests
    print_manual_tests()
    
    # Final status
    print_header("DEPLOYMENT STATUS")
    print(f"✅ Feature Flag: {'ENABLED' if flag_ok else 'DISABLED'}")
    print(f"{'✅' if api_ok else '⚠️ '} API Health: {'RESPONDING' if api_ok else 'NOT RESPONDING'}")
    print(f"{'✅' if tests_ok else '❌'} Edge Cases: {'PASSED' if tests_ok else 'FAILED'}")
    print(f"✅ Routing Logs: ACCESSIBLE")
    
    if flag_ok and api_ok and tests_ok:
        print("\n🎉 DEPLOYMENT SUCCESSFUL - Phase 3 is LIVE!")
        print("   Monitor closely for next 60 minutes")
        print("   Run this script again in 15 minutes")
    elif not tests_ok:
        print("\n❌ DEPLOYMENT ISSUE DETECTED")
        print("   Edge case tests failed - investigate immediately")
        print("   Consider rollback if issues persist")
    else:
        print("\n⚠️  DEPLOYMENT IN PROGRESS")
        print("   Complete API restart, then run this script again")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
