import requests
import json
import time
from datetime import datetime, date
import uuid
import random
import io

# Get the backend URL from the frontend .env file
BACKEND_URL = "https://a4559290-93cc-445f-81b0-a357c0d691a9.preview.emergentagent.com"
API_URL = f"{BACKEND_URL}/api"

# Test data
test_user = {
    "name": f"Test User {uuid.uuid4()}",
    "email": f"test.user.{uuid.uuid4()}@example.com",
    "password": "SecurePassword123!"
}

test_habits = [
    {
        "name": "Morning Meditation",
        "description": "10 minutes of mindfulness meditation",
        "habit_type": "yes_no",
        "category": "Wellness",
        "color": "#4F46E5",
        "reminder_enabled": True,
        "reminder_time": "08:00",
        "slack_notifications": True
    },
    {
        "name": "Drink Water",
        "description": "Track daily water intake",
        "habit_type": "quantifiable",
        "target_value": 8,
        "target_unit": "glasses",
        "category": "Health",
        "color": "#0EA5E9",
        "reminder_enabled": True,
        "reminder_time": "10:00",
        "slack_notifications": False
    },
    {
        "name": "Exercise",
        "description": "Daily workout routine",
        "habit_type": "time_based",
        "target_value": 30,
        "target_unit": "minutes",
        "category": "Fitness",
        "color": "#10B981",
        "reminder_enabled": False,
        "reminder_time": None,
        "slack_notifications": False
    }
]

# Test results
test_results = {
    "auth": {"success": False, "details": ""},
    "habit_crud": {"success": False, "details": ""},
    "habit_tracking": {"success": False, "details": ""},
    "dashboard": {"success": False, "details": ""},
    "analytics": {"success": False, "details": ""},
    "export_import": {"success": False, "details": ""},
    "notifications": {"success": False, "details": ""},
    "social_sharing": {"success": False, "details": ""},
    "slack_integration": {"success": False, "details": ""}
}

# Global variables
access_token = None
user_id = None
habit_ids = []

def print_separator():
    print("\n" + "="*80 + "\n")

def print_test_header(title):
    print_separator()
    print(f"TESTING: {title}")
    print_separator()

def print_test_result(test_name, success, details=""):
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"{status} - {test_name}")
    if details:
        print(f"  Details: {details}")

def print_response(response):
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")

def test_user_registration():
    print_test_header("User Registration")
    
    url = f"{API_URL}/auth/register"
    response = requests.post(url, json=test_user)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        global access_token, user_id
        access_token = data.get("access_token")
        user_id = data.get("user", {}).get("id")
        
        success = access_token is not None and user_id is not None
        test_results["auth"]["success"] = success
        test_results["auth"]["details"] = "Successfully registered user and got access token"
        
        print_test_result("User Registration", success)
        return success
    else:
        test_results["auth"]["success"] = False
        test_results["auth"]["details"] = f"Failed to register user: {response.text}"
        print_test_result("User Registration", False, response.text)
        return False

def test_user_login():
    print_test_header("User Login")
    
    url = f"{API_URL}/auth/login"
    login_data = {
        "email": test_user["email"],
        "password": test_user["password"]
    }
    
    response = requests.post(url, json=login_data)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        global access_token
        access_token = data.get("access_token")
        
        success = access_token is not None
        print_test_result("User Login", success)
        return success
    else:
        print_test_result("User Login", False, response.text)
        return False

def test_get_current_user():
    print_test_header("Get Current User")
    
    url = f"{API_URL}/auth/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        success = data.get("email") == test_user["email"]
        print_test_result("Get Current User", success)
        return success
    else:
        print_test_result("Get Current User", False, response.text)
        return False

def test_create_habits():
    print_test_header("Create Habits")
    
    url = f"{API_URL}/habits"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    all_success = True
    global habit_ids
    
    for habit in test_habits:
        response = requests.post(url, json=habit, headers=headers)
        print(f"Creating habit: {habit['name']}")
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            habit_id = data.get("id")
            if habit_id:
                habit_ids.append(habit_id)
            else:
                all_success = False
        else:
            all_success = False
    
    test_results["habit_crud"]["success"] = all_success and len(habit_ids) == len(test_habits)
    test_results["habit_crud"]["details"] = f"Created {len(habit_ids)} out of {len(test_habits)} habits"
    
    print_test_result("Create Habits", all_success, f"Created {len(habit_ids)} out of {len(test_habits)} habits")
    return all_success

def test_get_habits():
    print_test_header("Get All Habits")
    
    url = f"{API_URL}/habits"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        success = len(data) >= len(habit_ids)
        print_test_result("Get All Habits", success, f"Retrieved {len(data)} habits")
        return success
    else:
        print_test_result("Get All Habits", False, response.text)
        return False

def test_get_single_habit():
    print_test_header("Get Single Habit")
    
    if not habit_ids:
        print_test_result("Get Single Habit", False, "No habits created to retrieve")
        return False
    
    url = f"{API_URL}/habits/{habit_ids[0]}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        success = data.get("id") == habit_ids[0]
        print_test_result("Get Single Habit", success)
        return success
    else:
        print_test_result("Get Single Habit", False, response.text)
        return False

def test_update_habit():
    print_test_header("Update Habit")
    
    if not habit_ids:
        print_test_result("Update Habit", False, "No habits created to update")
        return False
    
    url = f"{API_URL}/habits/{habit_ids[0]}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    update_data = {
        "name": f"Updated Habit {uuid.uuid4()}",
        "description": "This habit has been updated"
    }
    
    response = requests.put(url, json=update_data, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        success = data.get("name") == update_data["name"]
        print_test_result("Update Habit", success)
        return success
    else:
        print_test_result("Update Habit", False, response.text)
        return False

def test_track_habits():
    print_test_header("Track Habits")
    
    if not habit_ids:
        print_test_result("Track Habits", False, "No habits created to track")
        return False
    
    all_success = True
    
    # Track yes_no habit
    yes_no_url = f"{API_URL}/habits/{habit_ids[0]}/track"
    headers = {"Authorization": f"Bearer {access_token}"}
    yes_no_data = {
        "completed": True,
        "notes": "Completed yes/no habit"
    }
    
    yes_no_response = requests.post(yes_no_url, json=yes_no_data, headers=headers)
    print("Tracking yes_no habit:")
    print_response(yes_no_response)
    
    if yes_no_response.status_code != 200:
        all_success = False
    
    # Track quantifiable habit
    if len(habit_ids) > 1:
        quant_url = f"{API_URL}/habits/{habit_ids[1]}/track"
        quant_data = {
            "completed": True,
            "value": 6,
            "notes": "Tracked quantifiable habit"
        }
        
        quant_response = requests.post(quant_url, json=quant_data, headers=headers)
        print("Tracking quantifiable habit:")
        print_response(quant_response)
        
        if quant_response.status_code != 200:
            all_success = False
    
    # Track time_based habit
    if len(habit_ids) > 2:
        time_url = f"{API_URL}/habits/{habit_ids[2]}/track"
        time_data = {
            "completed": True,
            "value": 25,
            "notes": "Tracked time-based habit"
        }
        
        time_response = requests.post(time_url, json=time_data, headers=headers)
        print("Tracking time_based habit:")
        print_response(time_response)
        
        if time_response.status_code != 200:
            all_success = False
    
    test_results["habit_tracking"]["success"] = all_success
    test_results["habit_tracking"]["details"] = "Successfully tracked all habit types" if all_success else "Failed to track some habits"
    
    print_test_result("Track Habits", all_success)
    return all_success

def test_get_habit_records():
    print_test_header("Get Habit Records")
    
    if not habit_ids:
        print_test_result("Get Habit Records", False, "No habits created to get records for")
        return False
    
    url = f"{API_URL}/habits/{habit_ids[0]}/records"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        success = isinstance(data, list)
        print_test_result("Get Habit Records", success, f"Retrieved {len(data)} records")
        return success
    else:
        print_test_result("Get Habit Records", False, response.text)
        return False

def test_get_dashboard():
    print_test_header("Get Dashboard")
    
    url = f"{API_URL}/dashboard"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        success = "habits" in data and "stats" in data
        
        test_results["dashboard"]["success"] = success
        test_results["dashboard"]["details"] = "Successfully retrieved dashboard data" if success else "Dashboard data incomplete"
        
        print_test_result("Get Dashboard", success)
        return success
    else:
        test_results["dashboard"]["success"] = False
        test_results["dashboard"]["details"] = f"Failed to retrieve dashboard: {response.text}"
        
        print_test_result("Get Dashboard", False, response.text)
        return False

def test_get_streaks():
    print_test_header("Get Streaks")
    
    url = f"{API_URL}/stats/streaks"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        success = isinstance(data, list)
        print_test_result("Get Streaks", success, f"Retrieved streak data for {len(data)} habits")
        return success
    else:
        print_test_result("Get Streaks", False, response.text)
        return False

def test_delete_habit():
    print_test_header("Delete Habit")
    
    if not habit_ids:
        print_test_result("Delete Habit", False, "No habits created to delete")
        return False
    
    url = f"{API_URL}/habits/{habit_ids[0]}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.delete(url, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        # Verify deletion by trying to get the habit
        get_response = requests.get(url, headers=headers)
        success = get_response.status_code == 404 or (get_response.status_code == 200 and not get_response.json().get("is_active", True))
        print_test_result("Delete Habit", success)
        return success
    else:
        print_test_result("Delete Habit", False, response.text)
        return False

# Enhanced Feature Tests

def test_analytics_overview():
    print_test_header("Analytics Overview")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    all_success = True
    
    # Test with different time periods
    time_periods = [7, 14, 30]
    
    for days in time_periods:
        url = f"{API_URL}/analytics/overview?days={days}"
        response = requests.get(url, headers=headers)
        
        print(f"Testing analytics for {days} days:")
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["period", "chart_data", "category_stats", "habit_stats", "summary"]
            success = all(field in data for field in required_fields)
            
            if success:
                # Verify chart data structure
                chart_data = data.get("chart_data", [])
                if chart_data:
                    chart_success = all("date" in item and "completion_rate" in item for item in chart_data)
                    success = success and chart_success
                
                # Verify summary structure
                summary = data.get("summary", {})
                summary_fields = ["total_habits", "total_completions", "average_completion_rate"]
                summary_success = all(field in summary for field in summary_fields)
                success = success and summary_success
            
            print_test_result(f"Analytics Overview ({days} days)", success)
            if not success:
                all_success = False
        else:
            print_test_result(f"Analytics Overview ({days} days)", False, response.text)
            all_success = False
    
    test_results["analytics"]["success"] = all_success
    test_results["analytics"]["details"] = "Successfully tested analytics overview with different time periods" if all_success else "Failed analytics overview tests"
    
    return all_success

def test_export_habits():
    print_test_header("Export Habits")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    all_success = True
    
    # Test JSON export
    json_url = f"{API_URL}/export/habits?format=json"
    json_response = requests.get(json_url, headers=headers)
    
    print("Testing JSON export:")
    print(f"Status Code: {json_response.status_code}")
    print(f"Content-Type: {json_response.headers.get('Content-Type', 'Not set')}")
    
    if json_response.status_code == 200:
        try:
            # Try to parse as JSON
            json_data = json_response.json() if json_response.headers.get('Content-Type') == 'application/json' else json.loads(json_response.text)
            json_success = "habits" in json_data and "records" in json_data
            print_test_result("JSON Export", json_success)
        except:
            json_success = False
            print_test_result("JSON Export", False, "Invalid JSON response")
    else:
        json_success = False
        print_test_result("JSON Export", False, json_response.text)
    
    # Test CSV export
    csv_url = f"{API_URL}/export/habits?format=csv"
    csv_response = requests.get(csv_url, headers=headers)
    
    print("Testing CSV export:")
    print(f"Status Code: {csv_response.status_code}")
    print(f"Content-Type: {csv_response.headers.get('Content-Type', 'Not set')}")
    
    if csv_response.status_code == 200:
        csv_success = "text/csv" in csv_response.headers.get('Content-Type', '') or len(csv_response.text) > 0
        print_test_result("CSV Export", csv_success)
    else:
        csv_success = False
        print_test_result("CSV Export", False, csv_response.text)
    
    all_success = json_success and csv_success
    
    test_results["export_import"]["success"] = all_success
    test_results["export_import"]["details"] = "Successfully tested habit export in both formats" if all_success else "Failed export tests"
    
    return all_success

def test_import_habits():
    print_test_header("Import Habits")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Create sample import data
    import_data = {
        "habits": [
            {
                "name": "Imported Reading Habit",
                "description": "Daily reading for 30 minutes",
                "habit_type": "time_based",
                "target_value": 30,
                "target_unit": "minutes",
                "category": "Learning",
                "color": "#F59E0B",
                "reminder_enabled": True,
                "reminder_time": "20:00"
            }
        ],
        "records": []
    }
    
    url = f"{API_URL}/import/habits"
    response = requests.post(url, json=import_data, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        success = data.get("success", False) and data.get("imported_habits", 0) > 0
        print_test_result("Import Habits", success, f"Imported {data.get('imported_habits', 0)} habits")
        return success
    else:
        print_test_result("Import Habits", False, response.text)
        return False

def test_notifications_reminders():
    print_test_header("Notifications and Reminders")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    url = f"{API_URL}/notifications/reminders"
    response = requests.get(url, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        success = isinstance(data, list)
        
        # Check structure of reminder data
        if data and len(data) > 0:
            reminder = data[0]
            required_fields = ["habit_id", "name"]
            structure_success = all(field in reminder for field in required_fields)
            success = success and structure_success
        
        test_results["notifications"]["success"] = success
        test_results["notifications"]["details"] = f"Successfully retrieved {len(data)} pending reminders" if success else "Failed to retrieve reminders"
        
        print_test_result("Get Reminders", success, f"Retrieved {len(data)} pending reminders")
        return success
    else:
        test_results["notifications"]["success"] = False
        test_results["notifications"]["details"] = f"Failed to retrieve reminders: {response.text}"
        
        print_test_result("Get Reminders", False, response.text)
        return False

def test_social_sharing():
    print_test_header("Social Sharing")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test get share data
    url = f"{API_URL}/share/progress"
    response = requests.get(url, headers=headers)
    
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        required_fields = ["user_name", "period", "completion_rate", "total_habits", "share_text"]
        success = all(field in data for field in required_fields)
        
        test_results["social_sharing"]["success"] = success
        test_results["social_sharing"]["details"] = "Successfully generated shareable progress data" if success else "Failed to generate share data"
        
        print_test_result("Get Share Data", success)
        return success
    else:
        test_results["social_sharing"]["success"] = False
        test_results["social_sharing"]["details"] = f"Failed to get share data: {response.text}"
        
        print_test_result("Get Share Data", False, response.text)
        return False

def test_slack_integration():
    print_test_header("Slack Integration")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    all_success = True
    
    # Test Slack status
    status_url = f"{API_URL}/slack/status"
    status_response = requests.get(status_url, headers=headers)
    
    print("Testing Slack status:")
    print_response(status_response)
    
    if status_response.status_code == 200:
        data = status_response.json()
        status_success = "configured" in data and "webhook_url" in data
        print_test_result("Slack Status", status_success)
    else:
        status_success = False
        print_test_result("Slack Status", False, status_response.text)
    
    # Test Slack install info
    install_url = f"{API_URL}/slack/install"
    install_response = requests.get(install_url, headers=headers)
    
    print("Testing Slack install info:")
    print_response(install_response)
    
    if install_response.status_code == 200:
        data = install_response.json()
        install_success = "webhook_url" in data and "setup_instructions" in data
        print_test_result("Slack Install Info", install_success)
    else:
        install_success = False
        print_test_result("Slack Install Info", False, install_response.text)
    
    # Test Slack user connection
    connect_url = f"{API_URL}/auth/slack/connect"
    connect_data = {
        "slack_user_id": "U1234567890",
        "slack_team_id": "T1234567890"
    }
    connect_response = requests.post(connect_url, json=connect_data, headers=headers)
    
    print("Testing Slack user connection:")
    print_response(connect_response)
    
    if connect_response.status_code == 200:
        connect_success = True
        print_test_result("Slack User Connection", True)
    else:
        connect_success = False
        print_test_result("Slack User Connection", False, connect_response.text)
    
    all_success = status_success and install_success and connect_success
    
    test_results["slack_integration"]["success"] = all_success
    test_results["slack_integration"]["details"] = "Successfully tested all Slack integration endpoints" if all_success else "Failed some Slack integration tests"
    
    return all_success

def run_all_tests():
    print("\n\n")
    print("="*80)
    print("STARTING BACKEND API TESTS")
    print("="*80)
    print(f"Backend URL: {API_URL}")
    print("\n")
    
    # Authentication tests
    auth_success = test_user_registration()
    if not auth_success:
        # Try login if registration fails (user might already exist)
        auth_success = test_user_login()
    
    if auth_success:
        test_get_current_user()
        
        # Habit CRUD tests
        crud_success = test_create_habits()
        if crud_success:
            test_get_habits()
            test_get_single_habit()
            test_update_habit()
            
            # Habit tracking tests
            test_track_habits()
            test_get_habit_records()
            
            # Dashboard and stats tests
            test_get_dashboard()
            test_get_streaks()
            
            # Enhanced feature tests
            test_analytics_overview()
            test_export_habits()
            test_import_habits()
            test_notifications_reminders()
            test_social_sharing()
            test_slack_integration()
            
            # Finally, test deletion
            test_delete_habit()
    
    # Print summary
    print_separator()
    print("TEST SUMMARY")
    print_separator()
    
    for category, result in test_results.items():
        status = "✅ PASSED" if result["success"] else "❌ FAILED"
        print(f"{status} - {category.upper()}")
        if result["details"]:
            print(f"  Details: {result['details']}")
    
    print_separator()
    
    # Overall result
    all_passed = all(result["success"] for result in test_results.values())
    print(f"OVERALL RESULT: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    print_separator()

if __name__ == "__main__":
    run_all_tests()