#!/usr/bin/env python3
"""
Integration and end-to-end testing script for Voice AI Agent
Tests all major components and workflows
"""

import asyncio
import requests
import json
from datetime import datetime, timedelta
import time

BASE_URL = "http://localhost:8000"


class VoiceAgentTester:
    def __init__(self):
        self.session_id = None
        self.user_id = None
        self.appointment_id = None
        self.test_results = []
    
    def test(self, name: str, condition: bool, message: str = ""):
        """Record test result"""
        status = "✓ PASS" if condition else "✗ FAIL"
        self.test_results.append({
            "name": name,
            "passed": condition,
            "message": message
        })
        print(f"{status} {name}")
        if message and not condition:
            print(f"  → {message}")
    
    def print_summary(self):
        """Print test summary"""
        passed = sum(1 for t in self.test_results if t["passed"])
        total = len(self.test_results)
        print(f"\n{'='*50}")
        print(f"Test Summary: {passed}/{total} passed")
        print(f"{'='*50}\n")
        return passed == total
    
    # ===== HEALTH CHECK TESTS =====
    def test_health_check(self):
        """Test API health check"""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            self.test(
                "Health Check",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.test(
                "Health Check - Database Status",
                data.get("database") == "connected",
                f"Database: {data.get('database')}"
            )
            
            self.test(
                "Health Check - Redis Status",
                data.get("redis") in ["connected", "disconnected"],
                f"Redis: {data.get('redis')}"
            )
        except Exception as e:
            self.test("Health Check", False, str(e))
    
    # ===== SESSION TESTS =====
    def test_session_start(self):
        """Test starting a new session"""
        try:
            payload = {
                "name": "Test User",
                "language": "en"
            }
            response = requests.post(
                f"{BASE_URL}/api/sessions/start",
                json=payload,
                timeout=10
            )
            
            self.test(
                "Session Start",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.session_id = data.get("session_id")
            self.user_id = data.get("user_id")
            
            self.test(
                "Session Start - Session ID Generated",
                self.session_id is not None and len(self.session_id) > 0,
                f"Session ID: {self.session_id}"
            )
            
            self.test(
                "Session Start - User ID Generated",
                self.user_id is not None and isinstance(self.user_id, int),
                f"User ID: {self.user_id}"
            )
            
            self.test(
                "Session Start - Language Set",
                data.get("language") == "en",
                f"Language: {data.get('language')}"
            )
            
            self.test(
                "Session Start - Welcome Message",
                "message" in data and len(data.get("message", "")) > 0,
                f"Message: {data.get('message')}"
            )
        except Exception as e:
            self.test("Session Start", False, str(e))
    
    def test_session_get(self):
        """Test retrieving session info"""
        if not self.session_id:
            print("⊘ SKIP Session Get (no session)")
            return
        
        try:
            response = requests.get(
                f"{BASE_URL}/api/sessions/{self.session_id}",
                timeout=10
            )
            
            self.test(
                "Session Get",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.test(
                "Session Get - Session Data",
                data.get("session_id") is not None,
                f"Session ID: {data.get('session_id')}"
            )
        except Exception as e:
            self.test("Session Get", False, str(e))
    
    # ===== VOICE PROCESSING TESTS =====
    def test_voice_process_text(self):
        """Test text message processing"""
        if not self.session_id or not self.user_id:
            print("⊘ SKIP Voice Process (no session)")
            return
        
        try:
            payload = {
                "session_id": self.session_id,
                "user_message": "I need to book an appointment for a consultation next Monday",
                "language": "en"
            }
            response = requests.post(
                f"{BASE_URL}/api/voice/process",
                json=payload,
                timeout=15
            )
            
            self.test(
                "Voice Process - Text",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            
            self.test(
                "Voice Process - Response Message",
                "message" in data and len(data.get("message", "")) > 0,
                f"Message length: {len(data.get('message', ''))}"
            )
            
            self.test(
                "Voice Process - Intent Detected",
                data.get("intent") in ["book", "reschedule", "cancel", "query", "confirm"],
                f"Intent: {data.get('intent')}"
            )
            
            self.test(
                "Voice Process - Confidence Score",
                isinstance(data.get("confidence"), int) and 0 <= data.get("confidence", 0) <= 100,
                f"Confidence: {data.get('confidence')}"
            )
            
            # Store appointment if booked
            if "appointment_id" in data:
                self.appointment_id = data["appointment_id"]
        except Exception as e:
            self.test("Voice Process - Text", False, str(e))
    
    # ===== APPOINTMENT TESTS =====
    def test_create_appointment(self):
        """Test creating an appointment"""
        if not self.user_id:
            print("⊘ SKIP Create Appointment (no user)")
            return
        
        try:
            payload = {
                "appointment_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "appointment_type": "consultation",
                "doctor_name": "Dr. John Smith",
                "clinic_name": "City Medical Clinic",
                "notes": "Test appointment from integration test"
            }
            response = requests.post(
                f"{BASE_URL}/api/appointments/",
                json={"user_id": self.user_id, **payload},
                params={"user_id": self.user_id},
                timeout=10
            )
            
            self.test(
                "Create Appointment",
                response.status_code in [200, 201],
                f"Status: {response.status_code}"
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.appointment_id = data.get("id")
                
                self.test(
                    "Create Appointment - Appointment ID",
                    self.appointment_id is not None,
                    f"ID: {self.appointment_id}"
                )
                
                self.test(
                    "Create Appointment - Status",
                    data.get("status") == "booked",
                    f"Status: {data.get('status')}"
                )
        except Exception as e:
            self.test("Create Appointment", False, str(e))
    
    def test_get_appointment(self):
        """Test retrieving appointment"""
        if not self.appointment_id:
            print("⊘ SKIP Get Appointment (no appointment)")
            return
        
        try:
            response = requests.get(
                f"{BASE_URL}/api/appointments/{self.appointment_id}",
                timeout=10
            )
            
            self.test(
                "Get Appointment",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.test(
                "Get Appointment - Appointment Data",
                data.get("id") == self.appointment_id,
                f"ID: {data.get('id')}"
            )
        except Exception as e:
            self.test("Get Appointment", False, str(e))
    
    def test_get_user_appointments(self):
        """Test retrieving user's appointments"""
        if not self.user_id:
            print("⊘ SKIP Get User Appointments (no user)")
            return
        
        try:
            response = requests.get(
                f"{BASE_URL}/api/appointments/user/{self.user_id}",
                timeout=10
            )
            
            self.test(
                "Get User Appointments",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.test(
                "Get User Appointments - Is List",
                isinstance(data, list),
                f"Type: {type(data)}"
            )
            
            self.test(
                "Get User Appointments - Count",
                len(data) > 0,
                f"Count: {len(data)}"
            )
        except Exception as e:
            self.test("Get User Appointments", False, str(e))
    
    # ===== USER TESTS =====
    def test_get_user(self):
        """Test retrieving user"""
        if not self.user_id:
            print("⊘ SKIP Get User (no user)")
            return
        
        try:
            response = requests.get(
                f"{BASE_URL}/api/users/{self.user_id}",
                timeout=10
            )
            
            self.test(
                "Get User",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.test(
                "Get User - User Data",
                data.get("id") == self.user_id,
                f"ID: {data.get('id')}"
            )
        except Exception as e:
            self.test("Get User", False, str(e))
    
    # ===== LANGUAGE TESTS =====
    def test_hindi_session(self):
        """Test Hindi language session"""
        try:
            payload = {
                "name": "हिंदी यूजर",
                "language": "hi"
            }
            response = requests.post(
                f"{BASE_URL}/api/sessions/start",
                json=payload,
                timeout=10
            )
            
            self.test(
                "Hindi Session Start",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.test(
                "Hindi Session - Language",
                data.get("language") == "hi",
                f"Language: {data.get('language')}"
            )
        except Exception as e:
            self.test("Hindi Session Start", False, str(e))
    
    def test_tamil_session(self):
        """Test Tamil language session"""
        try:
            payload = {
                "name": "தமிழ் பயனர்",
                "language": "ta"
            }
            response = requests.post(
                f"{BASE_URL}/api/sessions/start",
                json=payload,
                timeout=10
            )
            
            self.test(
                "Tamil Session Start",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.test(
                "Tamil Session - Language",
                data.get("language") == "ta",
                f"Language: {data.get('language')}"
            )
        except Exception as e:
            self.test("Tamil Session Start", False, str(e))
    
    def run_all_tests(self):
        """Run all tests"""
        print(f"\n{'='*50}")
        print("Voice AI Agent - Integration Test Suite")
        print(f"{'='*50}\n")
        
        print("Testing Health & Connectivity...")
        self.test_health_check()
        
        print("\nTesting Session Management...")
        self.test_session_start()
        self.test_session_get()
        
        print("\nTesting Voice Processing...")
        self.test_voice_process_text()
        
        print("\nTesting Appointment Management...")
        self.test_create_appointment()
        self.test_get_appointment()
        self.test_get_user_appointments()
        
        print("\nTesting User Management...")
        self.test_get_user()
        
        print("\nTesting Language Support...")
        self.test_hindi_session()
        self.test_tamil_session()
        
        return self.print_summary()


def main():
    """Main test execution"""
    print("\n[v0] Starting Voice AI Agent Integration Tests")
    print(f"[v0] Target: {BASE_URL}\n")
    
    # Wait for server to be ready
    max_retries = 5
    for attempt in range(max_retries):
        try:
            requests.get(f"{BASE_URL}/health", timeout=2)
            break
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                print(f"[v0] Waiting for server... ({attempt + 1}/{max_retries})")
                time.sleep(2)
            else:
                print(f"[v0] ERROR: Could not connect to server at {BASE_URL}")
                print("[v0] Make sure FastAPI server is running: uvicorn app.main:app --reload")
                return False
    
    tester = VoiceAgentTester()
    success = tester.run_all_tests()
    
    if success:
        print("[v0] All tests passed! System is ready for use.\n")
    else:
        print("[v0] Some tests failed. Check the output above for details.\n")
    
    return success


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
