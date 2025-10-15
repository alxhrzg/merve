#!/usr/bin/env python3
"""Test script for complex response handling."""

import requests
import json
import sys


def test_standard_format():
    """Test standard response format."""
    print("\n=== Testing Standard Format ===")

    # This would use default config with response_format: "standard"
    payload = {
        "payload": {
            "records": [
                {"feature1": 1.5, "feature2": 2.3},
                {"feature1": 2.1, "feature2": 1.7}
            ]
        }
    }

    response = requests.post("http://localhost:8000/predict", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    # Check that predictions field exists
    data = response.json()
    assert "predictions" in data, "Missing predictions field"
    assert "time_ms" in data, "Missing time_ms field"
    print("✓ Standard format test passed")


def test_custom_format():
    """Test custom response format with complex dictionary."""
    print("\n=== Testing Custom Format ===")

    # This assumes server is running with mlserver_complex.yaml
    payload = {
        "payload": {
            "records": [
                {"feature1": 1.5, "feature2": 2.3},
                {"feature1": 2.1, "feature2": 1.7}
            ]
        }
    }

    response = requests.post("http://localhost:8000/predict", json=payload)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")

        # Check for custom format structure
        if "result" in data:
            result = data["result"]
            print("\n✓ Custom format detected")
            print(f"  - Result type: {type(result)}")

            if isinstance(result, dict):
                print(f"  - Result keys: {list(result.keys())}")

                # Check for our custom fields
                if "custom_fields" in result:
                    custom = result["custom_fields"]
                    print(f"  - Custom fields: {custom}")

                    # Verify the complex structure is preserved
                    if "a" in custom and "b" in custom:
                        assert isinstance(custom["a"], list), "Field 'a' should be a list"
                        assert isinstance(custom["b"], dict), "Field 'b' should be a dict"
                        assert "c" in custom["b"], "Missing nested field 'c'"
                        assert "d" in custom["b"], "Missing nested field 'd'"
                        print("  ✓ Complex structure preserved correctly!")
        else:
            print("! Response doesn't have 'result' field - might be in standard format")
            print("  Ensure server is running with response_format: 'custom'")
    else:
        print(f"Error: {response.text}")


def test_passthrough_format():
    """Test passthrough response format."""
    print("\n=== Testing Passthrough Format ===")

    # This assumes server is running with mlserver_legacy.yaml on port 8001
    payload = {
        "payload": {
            "records": [
                {"feature1": 1.5, "feature2": 2.3}
            ]
        }
    }

    try:
        response = requests.post("http://localhost:8001/predict", json=payload)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")

            # Check for legacy format structure
            if "status" in data and "code" in data and "data" in data:
                print("✓ Passthrough format working - legacy structure preserved")
                assert data["status"] == "success", "Expected success status"
                assert "results" in data["data"], "Missing results in data"
            else:
                print("! Response doesn't match expected legacy format")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("! Could not connect to port 8001")
        print("  To test passthrough format, start server with:")
        print("  mlserver serve examples/mlserver_legacy.yaml")


def main():
    """Run all tests."""
    print("Testing Complex Response Handling")
    print("==================================")

    try:
        # Test whatever server is running on port 8000
        test_custom_format()

        # Optionally test other formats
        # test_standard_format()
        # test_passthrough_format()

    except requests.exceptions.ConnectionError:
        print("\n! Error: Could not connect to server")
        print("  Make sure the server is running:")
        print("  mlserver serve examples/mlserver_complex.yaml")
        sys.exit(1)
    except Exception as e:
        print(f"\n! Test failed: {e}")
        sys.exit(1)

    print("\n✓ All tests completed successfully!")


if __name__ == "__main__":
    main()