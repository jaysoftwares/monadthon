import asyncio
import aiohttp
import sys
sys.stdout.reconfigure(encoding='utf-8')

ARENA = "0xc0eb093b0e26c5a1a0db75a8361413b4d1e12b7b"
BOT_ADDR = "0xB0T0000000000000000000000000000000000002"

async def test():
    print("Testing bot...", flush=True)
    async with aiohttp.ClientSession() as session:
        # Check arena state
        async with session.get(f"http://localhost:8000/api/arenas/{ARENA}") as resp:
            arena = await resp.json()
            print(f"Arena: {arena['name']}", flush=True)
            print(f"Players: {arena['players']}", flush=True)
            print(f"Game status: {arena['game_status']}", flush=True)
        
        # Try joining
        payload = {
            "arena_address": ARENA,
            "player_address": BOT_ADDR,
            "tx_hash": "0x" + "b" * 64
        }
        async with session.post("http://localhost:8000/api/arenas/join", json=payload) as resp:
            print(f"Join status: {resp.status}", flush=True)
            text = await resp.text()
            print(f"Response: {text}", flush=True)

if __name__ == "__main__":
    asyncio.run(test())
