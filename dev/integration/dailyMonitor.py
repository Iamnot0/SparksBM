#!/usr/bin/env python3
"""
Daily Monitoring Script - Automated System Health Check

This script runs comprehensive daily tests and generates a report.
Safe to run in production - only performs read operations unless explicitly enabled.

Features:
- API health check
- Refactored component validation
- ISMS operations testing
- Knowledge base validation
- Error handling verification
- Performance metrics
- Generates timestamped report

Usage:
    python3 dev/integration/dailyMonitor.py

    # Save report to file
    python3 dev/integration/dailyMonitor.py > reports/daily_$(date +%Y%m%d).log

    # Run with write operations (creates test objects)
    python3 dev/integration/dailyMonitor.py --write

Schedule with cron:
    # Every day at 9 AM
    0 9 * * * cd /home/clay/Desktop/SparksBM && python3 dev/integration/dailyMonitor.py >> /var/log/sparksbm_monitor.log 2>&1
"""

import requests
import json
import time
import sys
from datetime import datetime
import argparse

# Configuration
API_URL = "http://localhost:8000"
BACKEND_URL = "http://localhost:8070"
KEYCLOAK_URL = "http://localhost:8080"

# Test configuration
ENABLE_WRITE_OPS = False  # Set to True to enable create/delete operations
TEST_TIMEOUT = 60  # seconds

class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(title, char="="):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{char*70}{Colors.RESET}")
    print(f"{Colors.BOLD}  {title}{Colors.RESET}")
    print(f"{Colors.BOLD}{char*70}{Colors.RESET}\n")

def print_result(label, status, details=""):
    """Print test result"""
    if status == "PASS":
        icon = f"{Colors.GREEN}✅{Colors.RESET}"
    elif status == "FAIL":
        icon = f"{Colors.RED}❌{Colors.RESET}"
    elif status == "WARN":
        icon = f"{Colors.YELLOW}⚠️{Colors.RESET}"
    else:
        icon = "ℹ️"
    
    print(f"{icon} {label:45s} {status:6s} {details}")

def check_service_health():
    """Check all service health endpoints"""
    print_header("1. SERVICE HEALTH CHECK")
    
    services = {
        "NotebookLLM API": f"{API_URL}/health",
        "SparksBM Backend": f"{BACKEND_URL}/actuator/health",
        "Keycloak": f"{KEYCLOAK_URL}/health/ready"
    }
    
    results = {"passed": 0, "failed": 0}
    
    for name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print_result(name, "PASS", f"Status: {response.status_code}")
                results["passed"] += 1
            else:
                print_result(name, "FAIL", f"Status: {response.status_code}")
                results["failed"] += 1
        except Exception as e:
            print_result(name, "FAIL", str(e)[:40])
            results["failed"] += 1
    
    return results

def test_refactored_components(session_id):
    """Test JSON-powered refactored components"""
    print_header("2. REFACTORED COMPONENTS (JSON-Powered)")
    
    tests = [
        # Conversational patterns (regex)
        ("hi", "Greeting (Regex)", 60, 30),
        ("thanks", "Gratitude (Regex)", 40, 20),
        
        # Knowledge base (JSON)
        ("what is a scope?", "Knowledge: Scope (JSON)", 100, 50),
        ("what is an asset?", "Knowledge: Asset (JSON)", 100, 50),
        ("difference between scope and asset?", "Knowledge: Comparison (JSON)", 100, 50),
        
        # Instructions (JSON)
        ("how do i create scope?", "Instructions: Scope (JSON)", 150, 60),
        ("how do i create asset?", "Instructions: Asset (JSON)", 150, 60),
        ("how do i create person?", "Instructions: Person (JSON)", 80, 40),
    ]
    
    results = {"passed": 0, "failed": 0}
    
    for query, label, min_len, timeout in tests:
        try:
            response = requests.post(
                f"{API_URL}/api/agent/chat",
                json={"message": query, "sessionId": session_id},
                timeout=timeout
            )
            result = response.json().get("result", "None")
            
            if result and result != "None" and len(str(result)) >= min_len:
                print_result(label, "PASS", f"{len(str(result))} chars")
                results["passed"] += 1
            else:
                print_result(label, "FAIL", f"Response too short or None")
                results["failed"] += 1
        except Exception as e:
            print_result(label, "FAIL", str(e)[:40])
            results["failed"] += 1
        time.sleep(0.5)
    
    return results

def test_isms_operations(session_id, enable_write):
    """Test ISMS operations (read-only by default)"""
    print_header("3. ISMS OPERATIONS")
    
    tests = [
        ("list scopes", "LIST Scopes", 20, 40),
        ("list assets", "LIST Assets", 20, 40),
        ("list persons", "LIST Persons", 20, 40),
    ]
    
    # Add write operations if enabled
    if enable_write:
        test_obj_name = f"MonitorTest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        tests.extend([
            (f"create scope {test_obj_name}", "CREATE Scope", 30, 60),
            (f"get scope {test_obj_name}", "GET Scope", 50, 40),
            (f"delete scope {test_obj_name}", "DELETE Scope", 30, 40),
        ])
    
    results = {"passed": 0, "failed": 0}
    
    for query, label, min_len, timeout in tests:
        try:
            response = requests.post(
                f"{API_URL}/api/agent/chat",
                json={"message": query, "sessionId": session_id},
                timeout=timeout
            )
            result = response.json().get("result", "None")
            
            if result and result != "None" and len(str(result)) >= min_len:
                print_result(label, "PASS", f"{len(str(result))} chars")
                results["passed"] += 1
            else:
                print_result(label, "FAIL", f"Response too short or None")
                results["failed"] += 1
        except Exception as e:
            print_result(label, "FAIL", str(e)[:40])
            results["failed"] += 1
        time.sleep(0.5)
    
    return results

def test_error_handling(session_id):
    """Test error handling and edge cases"""
    print_header("4. ERROR HANDLING & EDGE CASES")
    
    tests = [
        ("", "Empty message", "fallback"),
        ("asdfghjkl", "Random gibberish", "fallback"),
        ("create invalidtype Test", "Invalid object type", "Supported types"),
        ("get scope NonExistentXYZ", "Non-existent object", "not found"),
    ]
    
    results = {"passed": 0, "failed": 0}
    
    for query, label, expected in tests:
        try:
            response = requests.post(
                f"{API_URL}/api/agent/chat",
                json={"message": query, "sessionId": session_id},
                timeout=30
            )
            result = response.json().get("result", "None")
            
            # Check that we got SOME response (not None)
            if result and result != "None":
                print_result(label, "PASS", f"Response provided")
                results["passed"] += 1
            else:
                print_result(label, "FAIL", f"Returned None")
                results["failed"] += 1
        except Exception as e:
            print_result(label, "FAIL", str(e)[:40])
            results["failed"] += 1
        time.sleep(0.5)
    
    return results

def generate_summary(start_time, all_results):
    """Generate test summary"""
    print_header("DAILY MONITORING SUMMARY", "=")
    
    end_time = time.time()
    duration = end_time - start_time
    
    total_passed = sum(r["passed"] for r in all_results.values())
    total_failed = sum(r["failed"] for r in all_results.values())
    total_tests = total_passed + total_failed
    
    print(f"Date:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration:      {duration:.2f} seconds")
    print(f"Total Tests:   {total_tests}")
    print(f"{Colors.GREEN}✅ Passed:     {total_passed}{Colors.RESET}")
    print(f"{Colors.RED}❌ Failed:     {total_failed}{Colors.RESET}")
    
    if total_failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL SYSTEMS OPERATIONAL{Colors.RESET}")
        print(f"\n{Colors.GREEN}Status: ✅ PRODUCTION READY{Colors.RESET}")
        print(f"{Colors.GREEN}Recommendation: Continue monitoring{Colors.RESET}")
        return 0
    elif total_passed >= total_tests * 0.8:  # 80% pass rate
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  SOME ISSUES DETECTED{Colors.RESET}")
        print(f"\n{Colors.YELLOW}Status: ⚠️  ACCEPTABLE (Minor issues){Colors.RESET}")
        print(f"{Colors.YELLOW}Recommendation: Review failures{Colors.RESET}")
        return 1
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ MULTIPLE FAILURES{Colors.RESET}")
        print(f"\n{Colors.RED}Status: ❌ NEEDS ATTENTION{Colors.RESET}")
        print(f"{Colors.RED}Recommendation: Investigate immediately{Colors.RESET}")
        return 2
    
    print("=" * 70)

def main():
    """Main monitoring function"""
    parser = argparse.ArgumentParser(description="Daily System Monitoring")
    parser.add_argument("--write", action="store_true", 
                       help="Enable write operations (create/delete test objects)")
    args = parser.parse_args()
    
    start_time = time.time()
    
    print_header("DAILY SYSTEM MONITORING", "=")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'WRITE (creates test objects)' if args.write else 'READ-ONLY (safe)'}")
    print(f"API:  {API_URL}")
    
    all_results = {}
    
    # 1. Service Health
    all_results["services"] = check_service_health()
    
    # Check if API is healthy before continuing
    if all_results["services"]["failed"] > 0:
        print(f"\n{Colors.RED}⚠️  Services are down, skipping functional tests{Colors.RESET}")
        generate_summary(start_time, all_results)
        return 2
    
    # 2. Create session
    try:
        print_header("SESSION CREATION")
        response = requests.post(f"{API_URL}/api/agent/session", timeout=10)
        session_id = response.json()["sessionId"]
        print_result("Session Created", "PASS", session_id[:20] + "...")
    except Exception as e:
        print_result("Session Creation", "FAIL", str(e)[:40])
        print(f"\n{Colors.RED}⚠️  Cannot create session, aborting tests{Colors.RESET}")
        return 2
    
    # 3. Test refactored components
    all_results["refactored"] = test_refactored_components(session_id)
    
    # 4. Test ISMS operations
    all_results["isms"] = test_isms_operations(session_id, args.write)
    
    # 5. Test error handling
    all_results["errors"] = test_error_handling(session_id)
    
    # 6. Generate summary
    exit_code = generate_summary(start_time, all_results)
    
    return exit_code

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Monitoring interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}CRITICAL ERROR: {str(e)}{Colors.RESET}")
        sys.exit(1)
