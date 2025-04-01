import requests
import json

BASE_URL = "http://localhost:8080"

def test_dashboard():
    """Test accessing the dashboard page"""
    response = requests.get(f"{BASE_URL}/")
    print(f"Dashboard Status Code: {response.status_code}")
    print(f"Content Type: {response.headers.get('content-type')}")
    print("If status code is 200, the application is running successfully!")

def test_reports():
    """Test accessing the reports page"""
    response = requests.get(f"{BASE_URL}/reports")
    print(f"Reports Status Code: {response.status_code}")

if __name__ == "__main__":
    print("Testing the Legal Task System application...")
    try:
        test_dashboard()
        test_reports()
        print("\nYou can access the application in your browser at: http://localhost:8080")
    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to the application.")
        print("Make sure the Flask app is running on port 8080.") 