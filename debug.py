#!/usr/bin/env python3
"""Debug script to see what's happening with the monitor."""

import requests
import sqlite3
import json

# Wallet to check
wallet = "0xdfe3fedc5c7679be42c3d393e99d4b55247b73c4"

# Fetch from API
print("=" * 60)
print("FETCHING FROM API...")
print("=" * 60)
response = requests.get(
    f"https://data-api.polymarket.com/activity?user={wallet}&limit=25&offset=0"
)
api_activities = response.json()

print(f"\nAPI returned {len(api_activities)} activities")
if api_activities:
    print("\nMost recent 3 from API:")
    for i, activity in enumerate(api_activities[:3]):
        print(f"\n{i+1}. Transaction: {activity.get('transactionHash', 'N/A')[:16]}...")
        print(f"   Timestamp: {activity.get('timestamp')}")
        print(f"   Side: {activity.get('side')}")
        print(f"   Market: {activity.get('title', 'N/A')[:50]}")
        print(f"   Value: ${activity.get('usdcSize', 0)}")

# Check database
print("\n" + "=" * 60)
print("CHECKING DATABASE...")
print("=" * 60)

conn = sqlite3.connect("polymarket.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT transaction_hash, timestamp, side, title, usdc_size
    FROM activities
    WHERE wallet_address = ?
    ORDER BY timestamp DESC
    LIMIT 3
""", (wallet,))

db_activities = cursor.fetchall()
print(f"\nDatabase has {cursor.execute('SELECT COUNT(*) FROM activities WHERE wallet_address = ?', (wallet,)).fetchone()[0]} activities")

if db_activities:
    print("\nMost recent 3 from Database:")
    for i, row in enumerate(db_activities):
        print(f"\n{i+1}. Transaction: {row[0][:16]}...")
        print(f"   Timestamp: {row[1]}")
        print(f"   Side: {row[2]}")
        print(f"   Market: {row[3][:50] if row[3] else 'N/A'}")
        print(f"   Value: ${row[4]}")

# Get last seen hash
cursor.execute("""
    SELECT transaction_hash
    FROM activities
    WHERE wallet_address = ?
    ORDER BY timestamp DESC
    LIMIT 1
""", (wallet,))

last_seen = cursor.fetchone()
last_seen_hash = last_seen[0] if last_seen else None

print("\n" + "=" * 60)
print("COMPARISON...")
print("=" * 60)
print(f"\nLast seen hash in DB: {last_seen_hash[:16] if last_seen_hash else 'None'}...")

if api_activities and last_seen_hash:
    latest_api_hash = api_activities[0].get('transactionHash')
    print(f"Latest hash from API: {latest_api_hash[:16]}...")

    if latest_api_hash == last_seen_hash:
        print("\n✅ Hashes MATCH - No new activity (correct)")
    else:
        print("\n🆕 Hashes DIFFERENT - New activity detected!")

        # Find where the last seen hash appears in API response
        found_index = None
        for i, activity in enumerate(api_activities):
            if activity.get('transactionHash') == last_seen_hash:
                found_index = i
                break

        if found_index is not None:
            print(f"\nLast seen transaction found at index {found_index} in API response")
            print(f"This means there are {found_index} NEW activities")

            print("\nNew activities:")
            for i in range(found_index):
                activity = api_activities[i]
                print(f"\n{i+1}. {activity.get('side')} - {activity.get('title', 'N/A')[:40]}")
                print(f"   Hash: {activity.get('transactionHash')[:16]}...")
                print(f"   Value: ${activity.get('usdcSize', 0)}")
        else:
            print(f"\n⚠️ Last seen transaction NOT FOUND in API response")
            print(f"   This means there are MORE than 25 new activities")
            print(f"   OR the transaction has fallen out of the recent 25")

conn.close()

print("\n" + "=" * 60)
