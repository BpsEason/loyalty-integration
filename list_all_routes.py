import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.routing import APIRoute, APIRouter
from fastapi.testclient import TestClient
from app.main import app

# Load environment variables from .env file
load_dotenv()


def get_all_routes(app: FastAPI):
    return app.router.routes

def main():
    # 使用 TestClient 會完整觸發 FastAPI 的啟動流程，包含 include_router
    with TestClient(app) as client:
        print("=== 所有已註冊的路由（透過 TestClient 觸發） ===")
        # 從 client.app 獲取路由，確保拿到的是 TestClient 內部完整初始化的 app
        openapi_paths = client.app.openapi()["paths"]
        all_routes = []

        for i, (path, operations) in enumerate(sorted(openapi_paths.items())):
            methods = sorted(method.upper() for method in operations)
            name = ", ".join(
                operations[method].get("operationId", method)
                for method in sorted(operations)
            )
            all_routes.append((path, methods, name))
            print(f"{i:3} | {path:55} | {str(methods):20} | {name}")

        print(f"\n總共路由數量: {len(all_routes)}")

        # 比對 Points/Coupons/Rewards 是否全部存在
        print("\n=== Points 路由驗證 ===")
        points_expected = [
            "/customers/{customer_id}/points",
            "/customers/{customer_id}/point-transactions",
            "/customers/{customer_id}/point-transactions/expiring",
            "/customers/{customer_id}/point-transactions/{transaction_id}",
            "/points/earn",
            "/points/redeem",
        ]
        points_found = []
        for p in points_expected:
            found = any(p == path for path, _, _ in all_routes)
            points_found.append((p, found))
            print(f"  {p:55} {'✓' if found else '✗'}")
        points_ok = all(found for _, found in points_found)
        print(f"Points routes overall: {'PASS' if points_ok else 'FAIL'}")

        print("\n=== Coupons 路由驗證 ===")
        coupons_expected = [
            "/customers/{customer_id}/coupons",
            "/customers/{customer_id}/coupons/{user_coupon_id}",
            "/customers/{customer_id}/coupon-redemptions",
            "/coupons/redeem",
            "/payments/mixed",
            "/customers/{customer_id}/coupons/claim",
            "/coupons/claim",
        ]
        coupons_found = []
        for p in coupons_expected:
            found = any(p == path for path, _, _ in all_routes)
            coupons_found.append((p, found))
            print(f"  {p:55} {'✓' if found else '✗'}")
        coupons_ok = all(found for _, found in coupons_found)
        print(f"Coupons routes overall: {'PASS' if coupons_ok else 'FAIL'}")

        print("\n=== Rewards 路由驗證 ===")
        rewards_expected = [
            "/customers/{customer_id}/reward-grants",
            "/customers/{customer_id}/rewards/grant",
        ]
        rewards_found = []
        for p in rewards_expected:
            found = any(p == path for path, _, _ in all_routes)
            rewards_found.append((p, found))
            print(f"  {p:55} {'✓' if found else '✗'}")
        rewards_ok = all(found for _, found in rewards_found)
        print(f"Rewards routes overall: {'PASS' if rewards_ok else 'FAIL'}")

        # 列出所有匯入的 router 是否有自己的路由
        print("\n=== 各Router內部路由檢查 ===")
        from app.routers import auth_router, customers_router, points_router, coupons_router, rewards_router, workflows_router
        routers = [
            ("auth_router", auth_router),
            ("customers_router", customers_router),
            ("points_router", points_router),
            ("coupons_router", coupons_router),
            ("rewards_router", rewards_router),
            ("workflows_router", workflows_router),
        ]
        for name, router in routers:
            print(f"\n{name}:")
            if hasattr(router, 'routes'):
                for r in router.routes:
                    if hasattr(r, 'path') and hasattr(r, 'methods'):
                        methods = sorted(r.methods) if r.methods else []
                        print(f"  {r.path:50} {methods}")
            else:
                print("  沒有routes屬性")

if __name__ == "__main__":
    main()