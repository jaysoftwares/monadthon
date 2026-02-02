#!/usr/bin/env python3
"""
CLAW ARENA Backend API Testing Suite
Tests all backend endpoints for the tournament management system
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, List, Any

class ClawArenaAPITester:
    def __init__(self, base_url="https://claw-arena.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_key = "claw-arena-admin-key"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_arenas = []

    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}: PASSED")
        else:
            print(f"❌ {name}: FAILED - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "response_data": response_data
        })

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Dict = None, headers: Dict = None, params: Dict = None) -> tuple:
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)

        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {method} {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, params=params, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            response_data = None
            
            try:
                response_data = response.json()
            except:
                response_data = response.text

            if success:
                self.log_test(name, True, f"Status: {response.status_code}", response_data)
            else:
                self.log_test(name, False, f"Expected {expected_status}, got {response.status_code}. Response: {response_data}")

            return success, response_data

        except Exception as e:
            self.log_test(name, False, f"Exception: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "health",
            200
        )
        
        if success and isinstance(response, dict):
            if response.get('status') == 'healthy':
                print(f"   ✓ Service is healthy")
                return True
            else:
                print(f"   ✗ Unexpected health status: {response.get('status')}")
                return False
        return success

    def test_get_arenas_empty(self):
        """Test getting arenas when empty"""
        success, response = self.run_test(
            "Get Arenas (Empty)",
            "GET", 
            "arenas",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   ✓ Found {len(response)} arenas")
            return True
        return success

    def test_create_arena(self):
        """Test creating a new arena"""
        arena_data = {
            "name": f"Test Arena {datetime.now().strftime('%H%M%S')}",
            "entry_fee": "100000000000000000",  # 0.1 MON in wei
            "max_players": 8,
            "protocol_fee_bps": 250,
            "treasury": "0x742d35Cc6634C0532925a3b844Bc9e7595f3F4D0"
        }
        
        success, response = self.run_test(
            "Create Arena",
            "POST",
            "admin/arena/create",
            200,
            data=arena_data,
            headers={"X-Admin-Key": self.admin_key}
        )
        
        if success and isinstance(response, dict):
            arena_address = response.get('address')
            if arena_address:
                self.created_arenas.append(arena_address)
                print(f"   ✓ Created arena at address: {arena_address}")
                return arena_address
            else:
                print(f"   ✗ No address in response")
                return None
        return None

    def test_create_arena_without_admin_key(self):
        """Test creating arena without admin key (should fail)"""
        arena_data = {
            "name": "Unauthorized Arena",
            "entry_fee": "100000000000000000",
            "max_players": 8,
            "protocol_fee_bps": 250
        }
        
        success, response = self.run_test(
            "Create Arena (No Admin Key)",
            "POST",
            "admin/arena/create", 
            401,
            data=arena_data
        )
        return success

    def test_get_arenas_with_data(self):
        """Test getting arenas after creating one"""
        success, response = self.run_test(
            "Get Arenas (With Data)",
            "GET",
            "arenas",
            200
        )
        
        if success and isinstance(response, list) and len(response) > 0:
            print(f"   ✓ Found {len(response)} arenas")
            arena = response[0]
            required_fields = ['address', 'name', 'entry_fee', 'max_players', 'players']
            for field in required_fields:
                if field not in arena:
                    print(f"   ✗ Missing field: {field}")
                    return False
            print(f"   ✓ Arena structure is valid")
            return True
        return success

    def test_get_specific_arena(self, arena_address: str):
        """Test getting a specific arena by address"""
        success, response = self.run_test(
            "Get Specific Arena",
            "GET",
            f"arenas/{arena_address}",
            200
        )
        
        if success and isinstance(response, dict):
            if response.get('address') == arena_address:
                print(f"   ✓ Retrieved correct arena")
                return True
            else:
                print(f"   ✗ Address mismatch")
                return False
        return success

    def test_join_arena(self, arena_address: str):
        """Test joining an arena"""
        join_data = {
            "arena_address": arena_address,
            "player_address": "0x1234567890123456789012345678901234567890",
            "tx_hash": "0x" + "a" * 64  # Mock transaction hash
        }
        
        success, response = self.run_test(
            "Join Arena",
            "POST",
            "arenas/join",
            200,
            data=join_data
        )
        
        if success and isinstance(response, dict):
            if response.get('success'):
                print(f"   ✓ Successfully joined arena")
                return True
            else:
                print(f"   ✗ Join was not successful")
                return False
        return success

    def test_join_arena_twice(self, arena_address: str):
        """Test joining arena twice (should fail)"""
        join_data = {
            "arena_address": arena_address,
            "player_address": "0x1234567890123456789012345678901234567890",
            "tx_hash": "0x" + "b" * 64
        }
        
        success, response = self.run_test(
            "Join Arena Twice (Should Fail)",
            "POST",
            "arenas/join",
            400,
            data=join_data
        )
        return success

    def test_close_arena(self, arena_address: str):
        """Test closing arena registration"""
        success, response = self.run_test(
            "Close Arena",
            "POST",
            f"admin/arena/{arena_address}/close",
            200,
            headers={"X-Admin-Key": self.admin_key}
        )
        
        if success and isinstance(response, dict):
            if response.get('success'):
                print(f"   ✓ Successfully closed arena")
                return True
            else:
                print(f"   ✗ Close was not successful")
                return False
        return success

    def test_request_finalize_signature(self, arena_address: str):
        """Test requesting finalize signature"""
        finalize_data = {
            "arena_address": arena_address,
            "winners": ["0x1234567890123456789012345678901234567890"],
            "amounts": ["90000000000000000"]  # 0.09 MON in wei
        }
        
        success, response = self.run_test(
            "Request Finalize Signature",
            "POST",
            "admin/arena/request-finalize-signature",
            200,
            data=finalize_data,
            headers={"X-Admin-Key": self.admin_key}
        )
        
        if success and isinstance(response, dict):
            required_fields = ['signature', 'nonce', 'operator_address', 'domain', 'types', 'message']
            for field in required_fields:
                if field not in response:
                    print(f"   ✗ Missing field in signature response: {field}")
                    return False
            print(f"   ✓ Signature response structure is valid")
            return True
        return success

    def test_get_leaderboard(self):
        """Test getting leaderboard"""
        success, response = self.run_test(
            "Get Leaderboard",
            "GET",
            "leaderboard",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   ✓ Retrieved leaderboard with {len(response)} entries")
            if len(response) > 0:
                entry = response[0]
                required_fields = ['address', 'total_wins', 'total_payouts', 'tournaments_played']
                for field in required_fields:
                    if field not in entry:
                        print(f"   ✗ Missing field in leaderboard entry: {field}")
                        return False
                print(f"   ✓ Leaderboard entry structure is valid")
            return True
        return success

    def test_get_arena_players(self, arena_address: str):
        """Test getting arena players"""
        success, response = self.run_test(
            "Get Arena Players",
            "GET",
            f"arenas/{arena_address}/players",
            200
        )
        
        if success and isinstance(response, dict):
            if 'players' in response and 'arena_address' in response:
                print(f"   ✓ Retrieved {len(response['players'])} players")
                return True
            else:
                print(f"   ✗ Invalid players response structure")
                return False
        return success

    def test_nonexistent_arena(self):
        """Test accessing non-existent arena"""
        fake_address = "0x0000000000000000000000000000000000000000"
        success, response = self.run_test(
            "Get Non-existent Arena",
            "GET",
            f"arenas/{fake_address}",
            404
        )
        return success

    def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 Starting CLAW ARENA Backend API Tests")
        print("=" * 60)
        
        # Basic health and empty state tests
        self.test_health_check()
        self.test_get_arenas_empty()
        self.test_get_leaderboard()
        
        # Admin authentication tests
        self.test_create_arena_without_admin_key()
        
        # Arena creation and management
        arena_address = self.test_create_arena()
        if arena_address:
            self.test_get_arenas_with_data()
            self.test_get_specific_arena(arena_address)
            self.test_get_arena_players(arena_address)
            
            # Player joining tests
            self.test_join_arena(arena_address)
            self.test_join_arena_twice(arena_address)
            
            # Admin operations
            self.test_close_arena(arena_address)
            self.test_request_finalize_signature(arena_address)
        
        # Error handling tests
        self.test_nonexistent_arena()
        
        # Final results
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print(f"❌ {self.tests_run - self.tests_passed} tests failed")
            return 1

    def get_test_summary(self):
        """Get summary of test results"""
        return {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "failed_tests": self.tests_run - self.tests_passed,
            "success_rate": (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0,
            "test_details": self.test_results,
            "created_arenas": self.created_arenas
        }

def main():
    """Main test execution"""
    tester = ClawArenaAPITester()
    exit_code = tester.run_all_tests()
    
    # Save detailed results
    summary = tester.get_test_summary()
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    return exit_code

if __name__ == "__main__":
    sys.exit(main())