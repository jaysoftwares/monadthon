"""
Interactive Blackjack Player for Claw Arena Testing
Lets you play against the bot!
"""
import asyncio
import aiohttp
import sys

ARENA = "0xc0eb093b0e26c5a1a0db75a8361413b4d1e12b7b"
API = "http://localhost:8000"


def card_value(cards):
    """Calculate hand value"""
    total = 0
    aces = 0
    for c in cards:
        r = c["rank"]
        if r in ["J", "Q", "K"]:
            total += 10
        elif r == "A":
            aces += 1
            total += 11
        else:
            total += int(r)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def format_cards(cards):
    """Format cards for display"""
    sym = {"hearts": "H", "diamonds": "D", "clubs": "C", "spades": "S"}
    return " ".join(f"[{c['rank']}{sym.get(c['suit'], '?')}]" for c in cards)


async def bot_play(session, player_addr, my_hand):
    """Bot plays its hand"""
    hand_val = card_value(my_hand["cards"])
    
    while my_hand.get("status") == "playing" and hand_val < 17:
        print(f"  Bot hand: {format_cards(my_hand['cards'])} = {hand_val}")
        print(f"  Bot decides to HIT...")
        
        payload = {
            "arena_address": ARENA,
            "player_address": player_addr,
            "move_data": {"action": "hit"}
        }
        async with session.post(f"{API}/api/arenas/{ARENA}/game/move", json=payload) as resp:
            result = await resp.json()
            if result.get("game_state"):
                my_hand["cards"] = result["game_state"]["hand"]["cards"]
                my_hand["status"] = result["game_state"]["hand"]["status"]
                hand_val = result["game_state"].get("total", card_value(my_hand["cards"]))
                print(f"  {result.get('message', '')}")
    
    if my_hand.get("status") == "playing":
        print(f"  Bot hand: {format_cards(my_hand['cards'])} = {hand_val}")
        print(f"  Bot decides to STAND")
        payload = {
            "arena_address": ARENA,
            "player_address": player_addr,
            "move_data": {"action": "stand"}
        }
        async with session.post(f"{API}/api/arenas/{ARENA}/game/move", json=payload) as resp:
            result = await resp.json()
            print(f"  {result.get('message', '')}")


async def play():
    print("\n=== CLAW ARENA BLACKJACK ===\n")
    
    async with aiohttp.ClientSession() as session:
        # Get game state
        async with session.get(f"{API}/api/arenas/{ARENA}/game") as resp:
            game = await resp.json()
        
        if game.get("status") != "active":
            print(f"Game is not active. Status: {game.get('status')}")
            return
        
        challenge = game.get("current_challenge", {})
        player_hands = challenge.get("player_hands", {})
        dealer_hand = challenge.get("dealer_hand", {})
        
        print("Players in this round:")
        for addr, hand in player_hands.items():
            cards = hand.get("cards", [])
            val = card_value(cards)
            status = hand.get("status", "?")
            is_bot = "B0T" in addr
            label = "BOT" if is_bot else "YOU"
            print(f"  [{label}] {addr[:10]}... : {format_cards(cards)} = {val} ({status})")
        
        if dealer_hand:
            # Only show first card (hidden)
            dealer_cards = dealer_hand.get("cards", [])
            if dealer_cards:
                print(f"  [DEALER] : [{dealer_cards[0]['rank']}?] [??]")
        
        print("\n--- BOT PLAYS ---")
        
        # Find bot players and play them
        for addr, hand in player_hands.items():
            if "B0T" in addr and hand.get("status") == "playing":
                await bot_play(session, addr, hand)
        
        print("\n--- UPDATED STATE ---")
        
        # Get updated state
        async with session.get(f"{API}/api/arenas/{ARENA}/game") as resp:
            game = await resp.json()
        
        challenge = game.get("current_challenge", {})
        player_hands = challenge.get("player_hands", {})
        
        print("\nFinal hands this round:")
        for addr, hand in player_hands.items():
            cards = hand.get("cards", [])
            val = card_value(cards)
            status = hand.get("status", "?")
            is_bot = "B0T" in addr
            label = "BOT" if is_bot else "YOU"
            print(f"  [{label}] : {format_cards(cards)} = {val} ({status})")
        
        # Get leaderboard
        async with session.get(f"{API}/api/arenas/{ARENA}/game/leaderboard") as resp:
            leaderboard = await resp.json()
        
        print("\nLeaderboard:")
        for i, entry in enumerate(leaderboard):
            addr = entry.get("address", "?")
            score = entry.get("score", 0)
            is_bot = "B0T" in addr
            label = "BOT" if is_bot else "YOU"
            print(f"  #{i+1} [{label}] Score: {score}")


if __name__ == "__main__":
    asyncio.run(play())
