import asyncio
from app.client.base import LaravelClient

async def main():
    client = LaravelClient()
    result = await client.login()
    print("Login successful!")
    print("Token:" , client._token[:40] + "...")

if __name__ == "__main__":
    asyncio.run(main())