
from fastapi.testclient import TestClient
from app.main import create_app

def run_verification():
    try:
        app = create_app()
        print("create_app(): PASS")
    except Exception as e:
        print(f"create_app(): FAIL - {e}")
        return

    with TestClient(app) as client:
        print("TestClient initialization: PASS")

        # 1. Lifespan and Laravel Login
        # TestClient handles lifespan automatically. If login fails, it should raise an exception.
        # We can check the result by calling an endpoint that depends on the client.

        # 2. All expected routes exist
        response = client.get("/openapi.json")
        if response.status_code == 200:
            openapi_schema = response.json()
            paths = openapi_schema.get("paths", {}).keys()
            print(f"Routes from openapi.json: {len(paths)}")

            # Print all paths for verification
            for path in sorted(paths):
                print(f"  - {path}")

        else:
            print("Failed to get openapi.json")

        # 3. /health endpoint
        response = client.get("/health")
        if response.status_code == 200 and response.json() == {"status": "healthy"}:
            print("/health: PASS")
        else:
            print(f"/health: FAIL - Status: {response.status_code}, Body: {response.text}")

        # 4. Call an endpoint that requires auth
        response = client.get("/auth/me")
        if response.status_code == 200:
            print("/auth/me: PASS")
        else:
            print(f"/auth/me: FAIL - Status: {response.status_code}, Body: {response.text}")

if __name__ == "__main__":
    run_verification()