"""
CLAW ARENA - Agent Authorization System

Uses EIP-712 typed signatures to allow users to authorize agents
to join arenas on their behalf WITHOUT sharing private keys.

Flow:
1. User creates an agent
2. User signs an EIP-712 authorization message (gasless)
3. Backend stores the signature
4. When agent wants to join an arena, backend verifies signature
5. Backend relayer submits the join transaction using operator wallet
6. User's funds are used (via approve/transfer or direct payment)

This is secure because:
- User NEVER shares private key
- Signature is domain-specific (can't be used elsewhere)
- Has spending limits and expiration
- Can be revoked anytime
"""

import os
import time
from datetime import datetime, timezone
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import to_checksum_address
import logging

logger = logging.getLogger('agent_authorization')

# EIP-712 Domain for Claw Arena Agent Authorization
DOMAIN_NAME = "Claw Arena Agent"
DOMAIN_VERSION = "1"

# EIP-712 Type definitions
AUTHORIZATION_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "AgentAuthorization": [
        {"name": "owner", "type": "address"},
        {"name": "agentId", "type": "string"},
        {"name": "maxEntryFeeWei", "type": "uint256"},
        {"name": "dailyLimitWei", "type": "uint256"},
        {"name": "validUntil", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "allowedGameTypes", "type": "string"},
    ],
}


@dataclass
class AgentAuthorization:
    """Authorization for an agent to act on behalf of a user"""
    owner: str                    # User's wallet address
    agent_id: str                 # Agent ID this authorization is for
    max_entry_fee_wei: str        # Maximum entry fee per arena
    daily_limit_wei: str          # Maximum total spending per day
    valid_until: int              # Unix timestamp when authorization expires
    nonce: int                    # Nonce to prevent replay attacks
    allowed_game_types: str       # Comma-separated game types (empty = all)
    signature: str                # EIP-712 signature
    chain_id: int                 # Chain ID this authorization is for

    # Tracking fields
    created_at: str = ""
    daily_spent_wei: str = "0"
    last_spend_date: str = ""
    is_revoked: bool = False


def get_domain(chain_id: int, verifying_contract: str) -> Dict:
    """Get EIP-712 domain for a specific chain"""
    return {
        "name": DOMAIN_NAME,
        "version": DOMAIN_VERSION,
        "chainId": chain_id,
        "verifyingContract": to_checksum_address(verifying_contract),
    }


def get_authorization_message(
    owner: str,
    agent_id: str,
    max_entry_fee_wei: str,
    daily_limit_wei: str,
    valid_until: int,
    nonce: int,
    allowed_game_types: str,
    chain_id: int,
    verifying_contract: str,
) -> Dict:
    """
    Generate the EIP-712 typed data for signing.
    This is what the frontend will ask the user to sign.
    """
    return {
        "types": AUTHORIZATION_TYPES,
        "primaryType": "AgentAuthorization",
        "domain": get_domain(chain_id, verifying_contract),
        "message": {
            "owner": to_checksum_address(owner),
            "agentId": agent_id,
            "maxEntryFeeWei": int(max_entry_fee_wei),
            "dailyLimitWei": int(daily_limit_wei),
            "validUntil": valid_until,
            "nonce": nonce,
            "allowedGameTypes": allowed_game_types,
        },
    }


def verify_authorization_signature(
    authorization: AgentAuthorization,
    verifying_contract: str,
) -> bool:
    """
    Verify that the authorization signature is valid and signed by the owner.
    """
    try:
        typed_data = get_authorization_message(
            owner=authorization.owner,
            agent_id=authorization.agent_id,
            max_entry_fee_wei=authorization.max_entry_fee_wei,
            daily_limit_wei=authorization.daily_limit_wei,
            valid_until=authorization.valid_until,
            nonce=authorization.nonce,
            allowed_game_types=authorization.allowed_game_types,
            chain_id=authorization.chain_id,
            verifying_contract=verifying_contract,
        )

        # Encode the typed data
        encoded = encode_typed_data(full_message=typed_data)

        # Recover the signer address
        recovered = Account.recover_message(encoded, signature=authorization.signature)

        # Check if recovered address matches owner
        return recovered.lower() == authorization.owner.lower()

    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False


def is_authorization_valid(authorization: AgentAuthorization) -> tuple[bool, str]:
    """
    Check if an authorization is currently valid.
    Returns (is_valid, reason)
    """
    # Check if revoked
    if authorization.is_revoked:
        return False, "Authorization has been revoked"

    # Check expiration
    now = int(time.time())
    if now > authorization.valid_until:
        return False, "Authorization has expired"

    # Check daily limit
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if authorization.last_spend_date == today:
        daily_spent = int(authorization.daily_spent_wei)
        daily_limit = int(authorization.daily_limit_wei)
        if daily_spent >= daily_limit:
            return False, "Daily spending limit reached"

    return True, "Valid"


def can_join_arena(
    authorization: AgentAuthorization,
    entry_fee_wei: str,
    game_type: str,
) -> tuple[bool, str]:
    """
    Check if an authorization allows joining a specific arena.
    Returns (can_join, reason)
    """
    # First check basic validity
    is_valid, reason = is_authorization_valid(authorization)
    if not is_valid:
        return False, reason

    # Check entry fee limit
    entry_fee = int(entry_fee_wei)
    max_fee = int(authorization.max_entry_fee_wei)
    if entry_fee > max_fee:
        return False, f"Entry fee {entry_fee} exceeds max allowed {max_fee}"

    # Check game type
    if authorization.allowed_game_types:
        allowed = [gt.strip().lower() for gt in authorization.allowed_game_types.split(",")]
        if game_type.lower() not in allowed:
            return False, f"Game type {game_type} not in allowed types"

    # Check if this would exceed daily limit
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if authorization.last_spend_date == today:
        daily_spent = int(authorization.daily_spent_wei)
    else:
        daily_spent = 0

    daily_limit = int(authorization.daily_limit_wei)
    if daily_limit > 0 and (daily_spent + entry_fee) > daily_limit:
        remaining = daily_limit - daily_spent
        return False, f"Would exceed daily limit. Remaining: {remaining} wei"

    return True, "Authorized"


def record_spending(authorization: AgentAuthorization, amount_wei: str) -> AgentAuthorization:
    """
    Record that the authorization was used for spending.
    Returns updated authorization.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if authorization.last_spend_date != today:
        # New day, reset counter
        authorization.daily_spent_wei = amount_wei
    else:
        # Same day, add to total
        current = int(authorization.daily_spent_wei)
        authorization.daily_spent_wei = str(current + int(amount_wei))

    authorization.last_spend_date = today
    return authorization


class AuthorizationManager:
    """Manages agent authorizations"""

    def __init__(self, db=None, verifying_contract: str = ""):
        self.db = db
        self.verifying_contract = verifying_contract or os.environ.get(
            'AUTHORIZATION_CONTRACT',
            '0x0000000000000000000000000000000000000001'
        )

    async def get_next_nonce(self, owner: str) -> int:
        """Get next nonce for an owner"""
        if not self.db:
            return 1

        # Find highest nonce used by this owner
        pipeline = [
            {"$match": {"owner": owner.lower()}},
            {"$group": {"_id": None, "maxNonce": {"$max": "$nonce"}}},
        ]
        result = await self.db.agent_authorizations.aggregate(pipeline).to_list(1)

        if result and result[0].get("maxNonce"):
            return result[0]["maxNonce"] + 1
        return 1

    async def store_authorization(self, authorization: AgentAuthorization) -> bool:
        """Store a new authorization after verifying signature"""
        # Verify signature
        if not verify_authorization_signature(authorization, self.verifying_contract):
            logger.error("Invalid signature for authorization")
            return False

        # Normalize owner address
        authorization.owner = authorization.owner.lower()
        authorization.created_at = datetime.now(timezone.utc).isoformat()

        # Store in database
        if self.db:
            await self.db.agent_authorizations.insert_one(asdict(authorization))

        logger.info(f"Stored authorization for agent {authorization.agent_id}")
        return True

    async def get_authorization(
        self,
        owner: str,
        agent_id: str,
        chain_id: int,
    ) -> Optional[AgentAuthorization]:
        """Get active authorization for an agent"""
        if not self.db:
            return None

        # Find latest non-revoked authorization
        data = await self.db.agent_authorizations.find_one(
            {
                "owner": owner.lower(),
                "agent_id": agent_id,
                "chain_id": chain_id,
                "is_revoked": False,
            },
            sort=[("nonce", -1)],
        )

        if data:
            data.pop('_id', None)
            return AgentAuthorization(**data)
        return None

    async def revoke_authorization(
        self,
        owner: str,
        agent_id: str,
        chain_id: int,
    ) -> bool:
        """Revoke all authorizations for an agent"""
        if not self.db:
            return False

        result = await self.db.agent_authorizations.update_many(
            {
                "owner": owner.lower(),
                "agent_id": agent_id,
                "chain_id": chain_id,
            },
            {"$set": {"is_revoked": True}},
        )

        logger.info(f"Revoked {result.modified_count} authorizations for agent {agent_id}")
        return result.modified_count > 0

    async def update_spending(
        self,
        owner: str,
        agent_id: str,
        chain_id: int,
        amount_wei: str,
    ) -> bool:
        """Update spending for an authorization"""
        auth = await self.get_authorization(owner, agent_id, chain_id)
        if not auth:
            return False

        updated = record_spending(auth, amount_wei)

        if self.db:
            await self.db.agent_authorizations.update_one(
                {
                    "owner": owner.lower(),
                    "agent_id": agent_id,
                    "chain_id": chain_id,
                    "nonce": auth.nonce,
                },
                {
                    "$set": {
                        "daily_spent_wei": updated.daily_spent_wei,
                        "last_spend_date": updated.last_spend_date,
                    }
                },
            )

        return True

    async def check_can_join(
        self,
        owner: str,
        agent_id: str,
        chain_id: int,
        entry_fee_wei: str,
        game_type: str,
    ) -> tuple[bool, str]:
        """Check if agent can join an arena"""
        auth = await self.get_authorization(owner, agent_id, chain_id)
        if not auth:
            return False, "No authorization found"

        return can_join_arena(auth, entry_fee_wei, game_type)


# Global instance
authorization_manager = AuthorizationManager()


def get_typed_data_for_frontend(
    owner: str,
    agent_id: str,
    max_entry_fee_wei: str,
    daily_limit_wei: str,
    valid_days: int,
    nonce: int,
    allowed_game_types: List[str],
    chain_id: int,
    verifying_contract: str,
) -> Dict:
    """
    Generate typed data in format suitable for frontend signTypedData.
    The frontend can pass this directly to wallet.signTypedData()
    """
    valid_until = int(time.time()) + (valid_days * 24 * 60 * 60)

    return {
        "domain": {
            "name": DOMAIN_NAME,
            "version": DOMAIN_VERSION,
            "chainId": chain_id,
            "verifyingContract": to_checksum_address(verifying_contract),
        },
        "types": {
            "AgentAuthorization": [
                {"name": "owner", "type": "address"},
                {"name": "agentId", "type": "string"},
                {"name": "maxEntryFeeWei", "type": "uint256"},
                {"name": "dailyLimitWei", "type": "uint256"},
                {"name": "validUntil", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
                {"name": "allowedGameTypes", "type": "string"},
            ],
        },
        "primaryType": "AgentAuthorization",
        "message": {
            "owner": to_checksum_address(owner),
            "agentId": agent_id,
            "maxEntryFeeWei": str(max_entry_fee_wei),
            "dailyLimitWei": str(daily_limit_wei),
            "validUntil": str(valid_until),
            "nonce": str(nonce),
            "allowedGameTypes": ",".join(allowed_game_types) if allowed_game_types else "",
        },
        # Include raw values for backend
        "_meta": {
            "validUntil": valid_until,
            "nonce": nonce,
        },
    }
