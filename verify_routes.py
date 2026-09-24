"""
Route Contract Verification.

只驗證 FastAPI 最終註冊的 route path 與 HTTP method。
不啟動 application lifespan，也不呼叫 Laravel API。

用途：
- CI route regression detection
- Local API contract verification
"""

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
    expected = {
        "/customers/{customer_id}/points": {"GET"},
        "/customers/{customer_id}/point-transactions": {"GET", "POST"},
        "/customers/{customer_id}/point-transactions/expiring": {"GET"},
        "/customers/{customer_id}/point-transactions/{transaction_id}": {"GET"},
        "/points/earn": {"POST"},
        "/points/redeem": {"POST"},
        "/customers/{customer_id}/coupons": {"GET"},
        "/customers/{customer_id}/coupons/{user_coupon_id}": {"GET"},
        "/customers/{customer_id}/coupon-redemptions": {"GET"},
        "/coupons/redeem": {"POST"},
        "/payments/mixed": {"POST"},
        "/customers/{customer_id}/coupons/claim": {"POST"},
        "/coupons/claim": {"POST"},
        "/customers/{customer_id}/reward-grants": {"GET"},
        "/customers/{customer_id}/rewards/grant": {"POST"},
        "/workflows/pos-checkout": {"POST"},
        "/auth/login": {"POST"},
        "/auth/me": {"GET"},
        "/auth/refresh": {"POST"},
        "/auth/logout": {"POST"},
        "/health": {"GET"},
        "/": {"GET"},
    }

    print("\n=== 關鍵路由驗證 ===")
    actual: dict[str, set[str]] = {}
    for path, methods, _ in all_routes:
        actual.setdefault(path, set()).update(methods)
    failures = []
    for path, methods in expected.items():
        actual_methods = actual.get(path, set())
        status = "✓" if actual_methods == methods else "✗"
        print(f"  {status} {sorted(methods)} {path}")
        if actual_methods != methods:
            failures.append((path, methods, actual_methods))

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()