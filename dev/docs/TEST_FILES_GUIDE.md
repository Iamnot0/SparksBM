# Test Files Guide

**Purpose:** Comprehensive overview of all test scripts  
**Location:** `/dev/test/`  
**Total Files:** 9 test scripts (active)

---

## Test File Categories

### 🎯 **PRODUCTION MONITORING** (Run Regularly)

#### 1. `masterTestSuite.py` ⭐ **PRIMARY TEST SUITE**
**Purpose:** Comprehensive test suite for Phase 3 & Phase 4 validation  
**When to Run:** Daily, before deployments, after changes  
**Tests:**
- Phase 3 (ChatRouter) stability
- Phase 4 (ISMSCoordinator) readiness
- All critical paths
- Integration points

**Status:** ✅ Active  
**Command:** `python3 dev/test/masterTestSuite.py`

---

#### 2. `deploymentMonitor.py` ⭐ **DEPLOYMENT MONITORING**
**Purpose:** First-hour monitoring after deployment  
**When to Run:** Immediately after deploying Phase 3 or Phase 4  
**Tests:**
- Automated checks every 15 minutes
- First hour critical monitoring
- Real-time issue detection

**Status:** ✅ Active  
**Command:** `python3 dev/test/deploymentMonitor.py`

---

#### 3. `integrationTest.py` ⭐ **LIVE SYSTEM VALIDATION**
**Purpose:** Test actual running system with all components  
**When to Run:** Daily, after changes  
**Tests:**
- Shadow testing validation
- Routing decision logging
- Bug #3 prevention
- All critical paths

**Prerequisites:** All servers running  
**Status:** ✅ Active  
**Command:** `python3 dev/test/integrationTest.py`

---

### 🔧 **PHASE 4 TESTING** (ISMSCoordinator)

#### 4. `phase4ValidationTest.py` ⭐
**Purpose:** Final validation before Phase 4 integration  
**Tests:**
- ISMS Coordinator functionality
- All ISMS operations
- Unit tests with mocks
- 12 comprehensive tests

**Status:** ✅ Complete (12/12 passing)  
**Command:** `python3 dev/test/phase4ValidationTest.py`

---

### 🧪 **FUNCTIONAL TESTING** (ISMS Operations)

#### 5. `comprehensiveISMSTest.py`
**Purpose:** Test all ISMS objects and operations  
**Tests:**
- All object types (scope, asset, person, process, control, document, incident)
- All operations (list, create, get)
- Document processing (Excel, Word, PDF)
- Bulk import

**Status:** ✅ Active  
**Command:** `python3 dev/test/comprehensiveISMSTest.py`

---

#### 6. `edgeCaseTest.py`
**Purpose:** Critical edge case scenarios  
**Tests:**
- Bulk import (Bug #13)
- File upload scenarios
- Follow-up scenarios
- Bug #3 poison pill test

**Status:** ✅ Active  
**Command:** `python3 dev/test/edgeCaseTest.py`

---

### 🔐 **AUTHENTICATION TESTING**

#### 7. `testKeycloakAuth.py`
**Purpose:** Test Keycloak authentication flow  
**Tests:**
- Complete authentication process
- Token acquisition
- Backend API access
- Frontend/Backend integration

**Status:** ✅ Active  
**Command:** `python3 dev/test/testKeycloakAuth.py`

---



## Test Execution Strategy

### Daily Monitoring (Automated)
```bash
# Run master test suite
python3 dev/test/masterTestSuite.py

# Check integration
python3 dev/test/integrationTest.py

# Validate ISMS operations
python3 dev/test/comprehensiveISMSTest.py
```

### Weekly Deep Testing
```bash
# Phase 3 validation
python3 dev/test/testPhase3Router.py

# Phase 4 validation
python3 dev/test/phase4ValidationTest.py

# Edge cases
python3 dev/test/edgeCaseTest.py
```

### Pre-Deployment
```bash
# Full test suite
python3 dev/test/masterTestSuite.py

# Integration test
python3 dev/test/integrationTest.py

# Authentication test
python3 dev/test/testKeycloakAuth.py
```

### Post-Deployment
```bash
# First hour monitoring
python3 dev/test/deploymentMonitor.py

# Live system validation
python3 dev/test/integrationTest.py
```

---

## Test Status Summary

| Category | Total | Status |
|----------|-------|--------|
| Production Monitoring | 3 | ✅ Active |
| Phase 4 Testing | 1 | ✅ Ready |
| Functional Testing | 2 | ✅ Active |
| Authentication | 1 | ✅ Active |
| **TOTAL** | **7** | **All Active** |

**Note:** Phase 3 shadow testing files (7 files) removed after successful deployment.  
**Note:** Debug tools and obsolete test plans removed after bugs fixed.

---

## Recommended Test Schedule

### **Daily** (Automated)
- `masterTestSuite.py` - 5 minutes
- `integrationTest.py` - 3 minutes

### **Weekly**
- `comprehensiveISMSTest.py` - 10 minutes
- `edgeCaseTest.py` - 5 minutes
- `testKeycloakAuth.py` - 2 minutes

### **After Code Changes**
- `masterTestSuite.py`
- `integrationTest.py`
- Relevant specific tests

### **Before Deployment**
- ALL tests
- Manual smoke testing

### **After Deployment**
- `deploymentMonitor.py` (first hour)
- `integrationTest.py` (ongoing)

---

## Test Dependencies

### Required Services
- **NotebookLLM API** (port 8000)
- **SparksbmISMS Backend** (port 8070)
- **Keycloak** (port 8080)
- **PostgreSQL** (Verinice database)

### Python Requirements
```bash
pip install requests
```

---

## Test Failure Response

### If Tests Fail

1. **Check services:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8070/actuator/health
   curl http://localhost:8080/health/ready
   ```

2. **Check logs:**
   ```bash
   tail -100 /tmp/notebookllm_api.log
   ```

3. **Run specific test:**
   ```bash
   python3 dev/test/[specific_test].py
   ```

4. **Check recent changes:**
   ```bash
   git log -10 --oneline
   ```

5. **Rollback if needed:**
   ```bash
   git revert HEAD
   ```

---

## Creating New Tests

### Template
```python
"""
Test Name - Purpose

Description of what this test validates.

Prerequisites:
- Service requirements
- Data requirements

Usage:
    python3 dev/test/myTest.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'Agentic Framework'
)))

def test_something():
    """Test specific functionality"""
    # Test implementation
    pass

if __name__ == "__main__":
    print("="*70)
    print("  MY TEST NAME")
    print("="*70)
    test_something()
```

---

**Last Updated:** 2026-01-05  
**Maintained By:** Development Team
