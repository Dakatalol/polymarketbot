#!/usr/bin/env python3
"""
Test script to simulate new activity detection.
This will manually reset the database to an older transaction to test.
"""

import sqlite3
import sys

wallet = "0xdfe3fedc5c7679be42c3d393e99d4b55247b73c4"

print("This script will simulate new activity by 'forgetting' the most recent transactions.")
print("This lets you test that the monitor correctly detects new activity.\n")

# Connect to database
conn = sqlite3.connect("polymarket.db")
cursor = conn.cursor()

# Get all transactions for this wallet
cursor.execute("""
    SELECT transaction_hash, timestamp, side, title, usdc_size
    FROM activities
    WHERE wallet_address = ?
    ORDER BY timestamp DESC
""", (wallet,))

all_activities = cursor.fetchall()

if len(all_activities) < 2:
    print("Not enough activities in database to test. Need at least 2.")
    sys.exit(1)

print(f"Found {len(all_activities)} activities in database.\n")
print("Current most recent 5:")
for i, row in enumerate(all_activities[:5]):
    print(f"{i+1}. [{row[2]:4s}] {row[3][:40]:40s} ${row[4]:.2f}")
    print(f"   Hash: {row[0][:20]}... Time: {row[1]}")

# Ask how many to "forget"
print("\n" + "=" * 60)
print("How many recent activities should we 'forget' to simulate new activity?")
print("(This will delete them from the database, then you can re-run monitor.py)")
print("=" * 60)

try:
    num_to_forget = int(input("\nEnter number (1-5): "))
    if num_to_forget < 1 or num_to_forget > min(5, len(all_activities)):
        print("Invalid number")
        sys.exit(1)
except:
    print("Invalid input")
    sys.exit(1)

# Delete the most recent N activities
hashes_to_delete = [row[0] for row in all_activities[:num_to_forget]]

print(f"\nDeleting {num_to_forget} activities:")
for hash in hashes_to_delete:
    cursor.execute("DELETE FROM activities WHERE transaction_hash = ?", (hash,))
    print(f"  Deleted: {hash[:20]}...")

conn.commit()

# Show new state
cursor.execute("""
    SELECT transaction_hash, timestamp
    FROM activities
    WHERE wallet_address = ?
    ORDER BY timestamp DESC
    LIMIT 1
""", (wallet,))

result = cursor.fetchone()
if result:
    print(f"\nNew 'last seen' transaction: {result[0][:20]}...")
    print(f"Timestamp: {result[1]}")
else:
    print("\nDatabase is now empty for this wallet")

conn.close()

print("\n" + "=" * 60)
print("✅ Done! Now run:")
print(f"   python monitor.py {wallet}")
print(f"\nIt should detect {num_to_forget} new activities!")
print("=" * 60)
