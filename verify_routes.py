from fastapi.routing import APIRoute
from app.main import create_app


def get_all_routes(app):
    routes = []
    for path, operations in app.openapi()["paths"].items():
        for method, operation in operations.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                routes.append((path, [method.upper()], operation["operationId"]))
    return routes


def main():
    app = create_app()
    all_routes = get_all_routes(app)

    print("=== 所有已註冊的路由 ===")
    for path, methods, name in sorted(all_routes):
        print(f"{path:<60} {str(methods):<20} {name}")

    print(f"\n總共路由數量: {len(all_routes)}")

    # 驗證關鍵路徑是否存在（與原本設計一致）
    expected = [
        "/customers/{customer_id}/points",
        "/customers/{customer_id}/point-transactions",
        "/customers/{customer_id}/point-transactions/expiring",
        "/customers/{customer_id}/point-transactions/{transaction_id}",
        "/points/earn",
        "/points/redeem",
        "/customers/{customer_id}/coupons",
        "/customers/{customer_id}/coupons/{user_coupon_id}",
        "/customers/{customer_id}/coupon-redemptions",
        "/coupons/redeem",
        "/payments/mixed",
        "/customers/{customer_id}/coupons/claim",
        "/customers/{customer_id}/reward-grants",
        "/customers/{customer_id}/rewards/grant",
        "/workflows/pos-checkout",
        "/auth/login",
        "/health",
        "/",
    ]

    print("\n=== 關鍵路由驗證 ===")
    paths = {p for p, _, _ in all_routes}
    for p in expected:
        status = "✓" if p in paths else "✗"
        print(f"  {status} {p}")


if __name__ == "__main__":
    main()