#!/usr/bin/env python3
"""
Comprehensive System Audit - ISMS Operations & Document Processing

Tests:
1. All ISMS operations (CRUD for all object types)
2. Document uploads (docx, excel, pdf)
3. Document questions (intelligence testing)
4. Knowledge questions (Ollama integration)
5. Response quality (readability, user-friendliness)
6. Ollama implementation verification

Usage:
    python3 dev/test/comprehensiveAudit.py
"""

import sys
import os
import requests
import time
import json
from datetime import datetime
from pathlib import Path

# Configuration
API_URL = "http://localhost:8000"
TIMEOUT = 120  # Increased for Ollama responses

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(title, char="="):
    """Print formatted header"""
    print(f"\n{BOLD}{CYAN}{char*80}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{char*80}{RESET}\n")

def print_result(label, status, details="", response_preview=""):
    """Print test result"""
    if status == "PASS":
        icon = f"{GREEN}✅{RESET}"
    elif status == "FAIL":
        icon = f"{RED}❌{RESET}"
    elif status == "WARN":
        icon = f"{YELLOW}⚠️{RESET}"
    else:
        icon = "ℹ️"
    
    print(f"{icon} {BOLD}{label:50s}{RESET} {status:6s}")
    if details:
        print(f"   {details}")
    if response_preview:
        preview = response_preview[:200] + "..." if len(response_preview) > 200 else response_preview
        print(f"   {BLUE}Response:{RESET} {preview}")
    print()

def create_session():
    """Create a new session"""
    try:
        response = requests.post(f"{API_URL}/api/agent/session", timeout=10)
        if response.status_code == 200:
            return response.json().get("sessionId")
        return None
    except Exception as e:
        print(f"{RED}Failed to create session: {e}{RESET}")
        return None

def send_message(session_id, message, timeout=TIMEOUT):
    """Send message to API"""
    try:
        response = requests.post(
            f"{API_URL}/api/agent/chat",
            json={"message": message, "sessionId": session_id},
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "error": f"HTTP {response.status_code}"}
    except requests.exceptions.Timeout:
        return {"status": "error", "error": "Request timeout"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def upload_file(session_id, file_path):
    """Upload file to API"""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            data = {'sessionId': session_id}
            response = requests.post(
                f"{API_URL}/api/agent/upload",
                files=files,
                data=data,
                timeout=TIMEOUT
            )
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_isms_operations(session_id):
    """Test all ISMS operations"""
    print_header("PART 1: ISMS OPERATIONS AUDIT")
    
    object_types = ['scope', 'asset', 'person', 'process', 'control', 'document', 'incident']
    operations = ['list', 'create', 'get']
    
    results = {}
    test_objects = {}  # Store created objects for get operations
    
    for obj_type in object_types:
        print(f"\n{BOLD}📦 Testing {obj_type.upper()} Operations{RESET}")
        results[obj_type] = {}
        
        # LIST operation
        print(f"   {BLUE}1. LIST{RESET}: Testing 'list {obj_type}s'...")
        start_time = time.time()
        result = send_message(session_id, f"list {obj_type}s", timeout=60)
        elapsed = time.time() - start_time
        
        if result.get('status') == 'success':
            response_text = str(result.get('result', ''))
            if response_text and response_text != "None":
                print_result(
                    f"LIST {obj_type}s",
                    "PASS",
                    f"Response time: {elapsed:.2f}s, Length: {len(response_text)} chars",
                    response_text
                )
                results[obj_type]['list'] = True
            else:
                print_result(f"LIST {obj_type}s", "WARN", "Empty response")
                results[obj_type]['list'] = False
        else:
            print_result(f"LIST {obj_type}s", "FAIL", result.get('error', 'Unknown error'))
            results[obj_type]['list'] = False
        
        time.sleep(1)
        
        # CREATE operation
        test_name = f"AuditTest_{obj_type}_{int(time.time())}"
        print(f"   {BLUE}2. CREATE{RESET}: Testing 'create {obj_type} {test_name}'...")
        start_time = time.time()
        result = send_message(session_id, f"create {obj_type} {test_name} Test{obj_type.capitalize()} Test description for audit", timeout=60)
        elapsed = time.time() - start_time
        
        actual_created_name = None  # Will extract from response
        if result.get('status') == 'success':
            response_text = str(result.get('result', ''))
            # Check if created or asking for subtype (both are valid)
            if 'created' in response_text.lower() or 'subtype' in response_text.lower() or 'success' in response_text.lower():
                print_result(
                    f"CREATE {obj_type}",
                    "PASS",
                    f"Response time: {elapsed:.2f}s",
                    response_text
                )
                results[obj_type]['create'] = True
                
                # Extract actual created name from response
                # Format: "Created scope 'ActualName' (abbreviation: ...)"
                import re
                name_match = re.search(r"Created\s+\w+\s+'([^']+)'", response_text, re.IGNORECASE)
                if name_match:
                    actual_created_name = name_match.group(1)
                else:
                    # Fallback: try to extract from quotes
                    name_match = re.search(r"'([^']+)'", response_text)
                    if name_match:
                        actual_created_name = name_match.group(1)
                    else:
                        # Last resort: use test_name
                        actual_created_name = test_name
                
                test_objects[obj_type] = actual_created_name
            else:
                print_result(f"CREATE {obj_type}", "WARN", f"Unexpected response: {response_text[:100]}")
                results[obj_type]['create'] = False
        else:
            print_result(f"CREATE {obj_type}", "FAIL", result.get('error', 'Unknown error'))
            results[obj_type]['create'] = False
        
        time.sleep(1)
        
        # GET operation (if object was created)
        if obj_type in test_objects and actual_created_name:
            print(f"   {BLUE}3. GET{RESET}: Testing 'get {obj_type} {actual_created_name}'...")
            start_time = time.time()
            result = send_message(session_id, f"get {obj_type} {actual_created_name}", timeout=60)
            elapsed = time.time() - start_time
            
            if result.get('status') == 'success':
                response_text = str(result.get('result', ''))
                if response_text and response_text != "None":
                    print_result(
                        f"GET {obj_type}",
                        "PASS",
                        f"Response time: {elapsed:.2f}s",
                        response_text
                    )
                    results[obj_type]['get'] = True
                else:
                    print_result(f"GET {obj_type}", "WARN", "Empty response")
                    results[obj_type]['get'] = False
            else:
                print_result(f"GET {obj_type}", "WARN", result.get('error', 'Unknown error'))
                results[obj_type]['get'] = False
        else:
            print(f"   {YELLOW}3. GET{RESET}: Skipped (object not created or name not extracted)")
            results[obj_type]['get'] = None
        
        time.sleep(1)
        
        # DELETE operation (if object was created and GET worked)
        if obj_type in test_objects and actual_created_name and results[obj_type].get('get'):
            print(f"   {BLUE}4. DELETE{RESET}: Testing 'delete {obj_type} {actual_created_name}'...")
            start_time = time.time()
            result = send_message(session_id, f"delete {obj_type} {actual_created_name}", timeout=60)
            elapsed = time.time() - start_time
            
            if result.get('status') == 'success':
                response_text = str(result.get('result', ''))
                if 'deleted' in response_text.lower() or 'success' in response_text.lower():
                    print_result(
                        f"DELETE {obj_type}",
                        "PASS",
                        f"Response time: {elapsed:.2f}s",
                        response_text
                    )
                    results[obj_type]['delete'] = True
                else:
                    print_result(f"DELETE {obj_type}", "WARN", f"Unexpected response: {response_text[:100]}")
                    results[obj_type]['delete'] = False
            else:
                print_result(f"DELETE {obj_type}", "WARN", result.get('error', 'Unknown error'))
                results[obj_type]['delete'] = False
        else:
            print(f"   {YELLOW}4. DELETE{RESET}: Skipped (object not created or GET failed)")
            results[obj_type]['delete'] = None
        
        time.sleep(1)
    
    return results

def test_document_uploads(session_id):
    """Test document uploads (docx, excel, pdf)"""
    print_header("PART 2: DOCUMENT UPLOAD & PROCESSING AUDIT")
    
    # Find test files in uploads directory
    uploads_dir = Path("/home/clay/Desktop/SparksBM/NotebookLLM/api/uploads")
    test_files = {
        'excel': None,
        'docx': None,
        'pdf': None
    }
    
    # Find one of each type
    for file_path in uploads_dir.glob("*"):
        if file_path.suffix.lower() == '.xlsx' and not test_files['excel']:
            test_files['excel'] = file_path
        elif file_path.suffix.lower() == '.docx' and not test_files['docx']:
            test_files['docx'] = file_path
        elif file_path.suffix.lower() == '.pdf' and not test_files['pdf']:
            test_files['pdf'] = file_path
    
    results = {}
    
    for file_type, file_path in test_files.items():
        if not file_path:
            print_result(f"UPLOAD {file_type.upper()}", "WARN", f"No {file_type} test file found")
            results[file_type] = None
            continue
        
        print(f"\n{BOLD}📄 Testing {file_type.upper()} Upload{RESET}")
        print(f"   File: {file_path.name}")
        
        start_time = time.time()
        result = upload_file(session_id, str(file_path))
        elapsed = time.time() - start_time
        
        if result.get('status') == 'success':
            response_text = str(result.get('result', result.get('message', '')))
            print_result(
                f"UPLOAD {file_type.upper()}",
                "PASS",
                f"Response time: {elapsed:.2f}s, File: {file_path.name}",
                response_text
            )
            results[file_type] = {
                'uploaded': True,
                'file_path': str(file_path),
                'response': response_text
            }
        else:
            print_result(f"UPLOAD {file_type.upper()}", "FAIL", result.get('error', 'Unknown error'))
            results[file_type] = {'uploaded': False, 'error': result.get('error')}
        
        time.sleep(2)
    
    return results

def test_document_questions(session_id, uploaded_files):
    """Test intelligent questions about uploaded documents"""
    print_header("PART 3: DOCUMENT INTELLIGENCE TEST (Ollama Integration)")
    
    questions = [
        "What is in this file?",
        "Summarize the content",
        "What are the main points?",
        "Can you analyze this document?",
        "What information does this contain?",
    ]
    
    results = {}
    
    for file_type, file_info in uploaded_files.items():
        if not file_info or not file_info.get('uploaded'):
            continue
        
        print(f"\n{BOLD}🤖 Testing Questions About {file_type.upper()}{RESET}")
        results[file_type] = {}
        
        for i, question in enumerate(questions[:3], 1):  # Test first 3 questions
            print(f"   {BLUE}Q{i}:{RESET} {question}")
            start_time = time.time()
            result = send_message(session_id, question, timeout=TIMEOUT)
            elapsed = time.time() - start_time
            
            if result.get('status') == 'success':
                response_text = str(result.get('result', ''))
                
                # Check response quality
                quality_checks = {
                    'has_content': len(response_text) > 50,
                    'readable': not response_text.startswith('Error') and not response_text.startswith('Failed'),
                    'intelligent': any(word in response_text.lower() for word in ['content', 'document', 'file', 'information', 'data', 'summary', 'contains', 'shows', 'includes']),
                    'user_friendly': not any(word in response_text.lower() for word in ['exception', 'traceback', 'error code', 'failed to'])
                }
                
                quality_score = sum(quality_checks.values())
                
                if quality_score >= 3:
                    status = "PASS"
                elif quality_score >= 2:
                    status = "WARN"
                else:
                    status = "FAIL"
                
                print_result(
                    f"Question {i} ({file_type})",
                    status,
                    f"Response time: {elapsed:.2f}s, Quality: {quality_score}/4, Length: {len(response_text)} chars",
                    response_text
                )
                
                results[file_type][f'q{i}'] = {
                    'question': question,
                    'response': response_text,
                    'quality_score': quality_score,
                    'response_time': elapsed,
                    'status': status
                }
            else:
                print_result(f"Question {i} ({file_type})", "FAIL", result.get('error', 'Unknown error'))
                results[file_type][f'q{i}'] = {'status': 'FAIL', 'error': result.get('error')}
            
            time.sleep(2)  # Wait between questions
    
    return results

def test_knowledge_questions(session_id):
    """Test knowledge questions (Ollama integration)"""
    print_header("PART 4: KNOWLEDGE QUESTIONS TEST (Ollama Intelligence)")
    
    questions = [
        "What is a scope in ISMS?",
        "What is an asset?",
        "How do I create a scope?",
        "What is the difference between scope and asset?",
        "What is ISMS?",
        "How does risk assessment work?",
    ]
    
    results = {}
    
    for i, question in enumerate(questions, 1):
        print(f"\n{BOLD}🧠 Question {i}:{RESET} {question}")
        start_time = time.time()
        result = send_message(session_id, question, timeout=TIMEOUT)
        elapsed = time.time() - start_time
        
        if result.get('status') == 'success':
            response_text = str(result.get('result', ''))
            
            # Check response quality
            quality_checks = {
                'has_content': len(response_text) > 100,  # Knowledge answers should be detailed
                'readable': not response_text.startswith('Error'),
                'intelligent': any(word in response_text.lower() for word in ['is', 'are', 'means', 'refers', 'definition', 'purpose', 'used', 'create', 'step', 'process']),
                'user_friendly': len(response_text.split('.')) > 2  # Should have multiple sentences
            }
            
            quality_score = sum(quality_checks.values())
            
            if quality_score >= 3:
                status = "PASS"
            elif quality_score >= 2:
                status = "WARN"
            else:
                status = "FAIL"
            
            print_result(
                f"Knowledge Q{i}",
                status,
                f"Response time: {elapsed:.2f}s, Quality: {quality_score}/4, Length: {len(response_text)} chars",
                response_text
            )
            
            results[f'q{i}'] = {
                'question': question,
                'response': response_text,
                'quality_score': quality_score,
                'response_time': elapsed,
                'status': status
            }
        else:
            print_result(f"Knowledge Q{i}", "FAIL", result.get('error', 'Unknown error'))
            results[f'q{i}'] = {'status': 'FAIL', 'error': result.get('error')}
        
        time.sleep(2)
    
    return results

def verify_ollama_usage():
    """Verify Ollama is being used (check logs/config)"""
    print_header("PART 5: OLLAMA IMPLEMENTATION VERIFICATION")
    
    checks = {}
    
    # Check reasoningEngine.py exists
    reasoning_engine_path = Path("/home/clay/Desktop/SparksBM/Agentic Framework/orchestrator/reasoningEngine.py")
    if reasoning_engine_path.exists():
        print_result("ReasoningEngine exists", "PASS", f"Path: {reasoning_engine_path}")
        checks['reasoning_engine_exists'] = True
        
        # Check if Ollama is configured
        with open(reasoning_engine_path, 'r') as f:
            content = f.read()
            if 'OllamaReasoningEngine' in content:
                print_result("OllamaReasoningEngine class found", "PASS")
                checks['ollama_class'] = True
            else:
                print_result("OllamaReasoningEngine class found", "FAIL")
                checks['ollama_class'] = False
            
            if 'ollama.com' in content or 'OLLAMA_ENDPOINT' in content:
                print_result("Ollama Cloud API configured", "PASS")
                checks['ollama_cloud'] = True
            else:
                print_result("Ollama Cloud API configured", "WARN", "May be using local Ollama")
                checks['ollama_cloud'] = False
    else:
        print_result("ReasoningEngine exists", "FAIL", "File not found")
        checks['reasoning_engine_exists'] = False
    
    # Check agentBridge.py uses ReasoningEngine
    agent_bridge_path = Path("/home/clay/Desktop/SparksBM/NotebookLLM/integration/agentBridge.py")
    if agent_bridge_path.exists():
        with open(agent_bridge_path, 'r') as f:
            content = f.read()
            if 'ReasoningEngine' in content or 'createReasoningEngine' in content:
                print_result("AgentBridge uses ReasoningEngine", "PASS")
                checks['agent_bridge'] = True
            else:
                print_result("AgentBridge uses ReasoningEngine", "FAIL")
                checks['agent_bridge'] = False
    else:
        print_result("AgentBridge uses ReasoningEngine", "WARN", "File not found")
        checks['agent_bridge'] = False
    
    # Check .env for Ollama config
    env_path = Path("/home/clay/Desktop/SparksBM/Agentic Framework/.env")
    if env_path.exists():
        with open(env_path, 'r') as f:
            content = f.read()
            if 'OLLAMA_API_KEY' in content:
                print_result("OLLAMA_API_KEY configured", "PASS")
                checks['api_key'] = True
            else:
                print_result("OLLAMA_API_KEY configured", "WARN", "May not be set")
                checks['api_key'] = False
    else:
        print_result("OLLAMA_API_KEY configured", "WARN", ".env file not found")
        checks['api_key'] = False
    
    return checks

def generate_summary(isms_results, upload_results, doc_question_results, knowledge_results, ollama_checks):
    """Generate comprehensive summary"""
    print_header("COMPREHENSIVE AUDIT SUMMARY", "=")
    
    print(f"\n{BOLD}Date:{RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{BOLD}API:{RESET} {API_URL}\n")
    
    # ISMS Operations Summary
    print(f"{BOLD}📦 ISMS Operations:{RESET}")
    total_isms_tests = 0
    passed_isms_tests = 0
    ops_breakdown = {'list': 0, 'create': 0, 'get': 0, 'delete': 0}
    ops_passed = {'list': 0, 'create': 0, 'get': 0, 'delete': 0}
    for obj_type, ops in isms_results.items():
        for op, result in ops.items():
            if result is not None:
                total_isms_tests += 1
                ops_breakdown[op] = ops_breakdown.get(op, 0) + 1
                if result:
                    passed_isms_tests += 1
                    ops_passed[op] = ops_passed.get(op, 0) + 1
    print(f"   Passed: {passed_isms_tests}/{total_isms_tests} ({passed_isms_tests*100//total_isms_tests if total_isms_tests > 0 else 0}%)")
    print(f"   Breakdown: LIST {ops_passed.get('list', 0)}/{ops_breakdown.get('list', 0)}, CREATE {ops_passed.get('create', 0)}/{ops_breakdown.get('create', 0)}, GET {ops_passed.get('get', 0)}/{ops_breakdown.get('get', 0)}, DELETE {ops_passed.get('delete', 0)}/{ops_breakdown.get('delete', 0)}")
    
    # Document Upload Summary
    print(f"\n{BOLD}📄 Document Uploads:{RESET}")
    uploaded_count = sum(1 for r in upload_results.values() if r and r.get('uploaded'))
    total_files = len([r for r in upload_results.values() if r is not None])
    print(f"   Uploaded: {uploaded_count}/{total_files} file types")
    
    # Document Questions Summary
    print(f"\n{BOLD}🤖 Document Intelligence:{RESET}")
    if doc_question_results:
        total_doc_q = sum(len(v) for v in doc_question_results.values() if isinstance(v, dict))
        passed_doc_q = sum(1 for v in doc_question_results.values() if isinstance(v, dict) 
                          for q in v.values() if isinstance(q, dict) and q.get('status') == 'PASS')
        print(f"   Passed: {passed_doc_q}/{total_doc_q} questions")
    else:
        print(f"   No document questions tested")
    
    # Knowledge Questions Summary
    print(f"\n{BOLD}🧠 Knowledge Questions:{RESET}")
    if knowledge_results:
        total_knowledge = len(knowledge_results)
        passed_knowledge = sum(1 for v in knowledge_results.values() if isinstance(v, dict) and v.get('status') == 'PASS')
        avg_response_time = sum(v.get('response_time', 0) for v in knowledge_results.values() if isinstance(v, dict)) / total_knowledge if total_knowledge > 0 else 0
        print(f"   Passed: {passed_knowledge}/{total_knowledge} questions")
        print(f"   Average response time: {avg_response_time:.2f}s")
    else:
        print(f"   No knowledge questions tested")
    
    # Ollama Verification Summary
    print(f"\n{BOLD}🔧 Ollama Implementation:{RESET}")
    ollama_passed = sum(1 for v in ollama_checks.values() if v)
    ollama_total = len(ollama_checks)
    print(f"   Checks passed: {ollama_passed}/{ollama_total}")
    
    # Overall Assessment
    print(f"\n{BOLD}{'='*80}{RESET}")
    overall_score = (passed_isms_tests + uploaded_count + passed_doc_q + passed_knowledge + ollama_passed)
    overall_max = (total_isms_tests + total_files + total_doc_q + total_knowledge + ollama_total)
    overall_percentage = (overall_score * 100 // overall_max) if overall_max > 0 else 0
    
    if overall_percentage >= 80:
        status_color = GREEN
        status = "EXCELLENT"
    elif overall_percentage >= 60:
        status_color = YELLOW
        status = "GOOD"
    else:
        status_color = RED
        status = "NEEDS IMPROVEMENT"
    
    print(f"\n{status_color}{BOLD}Overall Score: {overall_score}/{overall_max} ({overall_percentage}%){RESET}")
    print(f"{status_color}{BOLD}Status: {status}{RESET}\n")

def main():
    """Main audit function"""
    print_header("COMPREHENSIVE SYSTEM AUDIT", "=")
    print(f"{BOLD}Testing:{RESET}")
    print(f"  • ISMS Operations (CRUD)")
    print(f"  • Document Processing (docx, excel, pdf)")
    print(f"  • Document Intelligence (Ollama)")
    print(f"  • Knowledge Questions (Ollama)")
    print(f"  • Response Quality & Readability")
    print(f"  • Ollama Implementation Verification")
    
    # Create session
    print(f"\n{BOLD}Creating session...{RESET}")
    session_id = create_session()
    if not session_id:
        print(f"{RED}Failed to create session. Aborting.{RESET}")
        return 1
    
    print(f"{GREEN}Session created: {session_id[:20]}...{RESET}\n")
    
    # Run all tests
    isms_results = test_isms_operations(session_id)
    upload_results = test_document_uploads(session_id)
    doc_question_results = test_document_questions(session_id, upload_results)
    knowledge_results = test_knowledge_questions(session_id)
    ollama_checks = verify_ollama_usage()
    
    # Generate summary
    generate_summary(isms_results, upload_results, doc_question_results, knowledge_results, ollama_checks)
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Audit interrupted by user{RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{RED}CRITICAL ERROR: {str(e)}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
