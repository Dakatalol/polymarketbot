#!/usr/bin/env python3
"""
Polymarket Wallet Activity Monitor

Fetches wallet activity from Polymarket API and detects new transactions.
Stores state in SQLite to track what's already been seen.
"""

import requests
import sqlite3
import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Optional

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


class PolymarketMonitor:
    def __init__(self, db_path: str = "polymarket.db"):
        """Initialize the monitor with database connection."""
        self.db_path = db_path
        self.api_base = "https://data-api.polymarket.com"
        self._init_database()

    def _init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table to store all activities
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                transaction_hash TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                side TEXT,
                title TEXT,
                outcome TEXT,
                size REAL,
                price REAL,
                usdc_size REAL,
                raw_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for faster wallet lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_wallet_timestamp
            ON activities(wallet_address, timestamp DESC)
        """)

        conn.commit()
        conn.close()

    def fetch_activity(self, wallet_address: str, limit: int = 25) -> List[Dict]:
        """Fetch recent activity for a wallet from Polymarket API."""
        url = f"{self.api_base}/activity"
        params = {
            "user": wallet_address,
            "limit": limit,
            "offset": 0
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching activity: {e}", file=sys.stderr)
            return []

    def get_last_seen_hash(self, wallet_address: str) -> Optional[str]:
        """Get the most recent transaction hash for a wallet from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT transaction_hash
            FROM activities
            WHERE wallet_address = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (wallet_address,))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def store_activities(self, wallet_address: str, activities: List[Dict]):
        """Store new activities in the database."""
        if not activities:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for activity in activities:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO activities
                    (transaction_hash, wallet_address, timestamp, side, title,
                     outcome, size, price, usdc_size, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    activity.get("transactionHash"),
                    wallet_address,
                    activity.get("timestamp"),
                    activity.get("side"),
                    activity.get("title"),
                    activity.get("outcome"),
                    activity.get("size"),
                    activity.get("price"),
                    activity.get("usdcSize"),
                    json.dumps(activity)
                ))
            except Exception as e:
                print(f"Error storing activity: {e}", file=sys.stderr)
                continue

        conn.commit()
        conn.close()

    def get_new_activities(self, wallet_address: str) -> List[Dict]:
        """
        Fetch latest activity and return only new transactions.
        Filters out REWARD type activities.

        Returns:
            List of new activities (empty list if none)
        """
        # Fetch latest from API
        latest_activities = self.fetch_activity(wallet_address)

        if not latest_activities:
            return []

        # Get last seen transaction
        last_seen_hash = self.get_last_seen_hash(wallet_address)

        # If this is the first run, store everything but return empty
        # (don't notify on initial setup)
        if last_seen_hash is None:
            self.store_activities(wallet_address, latest_activities)
            print(f"First run: stored {len(latest_activities)} activities (no notifications)")
            return []

        # Find new activities (everything before we hit the last seen hash)
        new_activities = []
        for activity in latest_activities:
            if activity.get("transactionHash") == last_seen_hash:
                break  # Stop when we hit the last seen transaction
            new_activities.append(activity)

        # Store the new activities
        if new_activities:
            self.store_activities(wallet_address, new_activities)

        # Filter out REWARD type activities before returning
        filtered_activities = [
            activity for activity in new_activities
            if activity.get("type") != "REWARD"
        ]

        # Return in chronological order (oldest first)
        return list(reversed(filtered_activities))

    def format_activity(self, activity: Dict) -> str:
        """Format activity for human-readable output."""
        emoji = "🟢" if activity.get("side") == "BUY" else "🔴"
        action = activity.get("side", "UNKNOWN")

        timestamp = activity.get("timestamp", 0)
        dt = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

        title = activity.get("title", "Unknown Market")
        outcome = activity.get("outcome", "Unknown")
        size = float(activity.get("size", 0))
        price = float(activity.get("price", 0))
        usdc_size = float(activity.get("usdcSize", 0))

        user = activity.get("pseudonym") or activity.get("name") or "Anonymous"
        wallet = activity.get("proxyWallet", "Unknown")
        wallet_short = f"{wallet[:6]}...{wallet[-4:]}" if len(wallet) > 10 else wallet

        return f"""
{emoji} {action}
Market: {title}
Outcome: {outcome}
Size: {size:,.0f} shares @ ${price:.4f}
Value: ${usdc_size:,.2f} USDC
User: {user}
Wallet: {wallet_short}
Time: {dt} UTC
Transaction: {activity.get("transactionHash", "N/A")}
        """.strip()


def main():
    """Main entry point for CLI usage."""
    if len(sys.argv) < 2:
        print("Usage: python monitor.py <wallet_address>")
        print("Example: python monitor.py 0xdfe3fedc5c7679be42c3d393e99d4b55247b73c4")
        sys.exit(1)

    wallet_address = sys.argv[1]

    # Initialize monitor
    monitor = PolymarketMonitor()

    # Get new activities
    new_activities = monitor.get_new_activities(wallet_address)

    if new_activities:
        print(f"Found {len(new_activities)} new activities:\n")
        for activity in new_activities:
            print(monitor.format_activity(activity))
            print("-" * 60)

        # Output JSON for n8n integration
        print("\nJSON output for n8n:")
        print(json.dumps({
            "hasNewActivity": True,
            "count": len(new_activities),
            "activities": new_activities
        }, indent=2))
    else:
        print("No new activity detected")
        print(json.dumps({
            "hasNewActivity": False,
            "count": 0,
            "activities": []
        }, indent=2))


if __name__ == "__main__":
    main()
