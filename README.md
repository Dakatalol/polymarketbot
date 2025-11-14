# Polymarket Wallet Activity Monitor

Monitor Polymarket wallet activity and get notified via Telegram when there are new trades.

## How It Works

1. **Python script** fetches wallet activity from Polymarket API
2. **SQLite database** stores transaction history to track what's been seen
3. **Comparison logic** detects new activity since last check
4. **n8n workflow** schedules the script and sends Telegram notifications

## Quick Setup

### 1. Install Python Dependencies

```bash
pip install requests
```

That's it! SQLite is built into Python.

### 2. Test the Monitor Script

```bash
python monitor.py 0x21504551452f4c4b67a1fbee6ba743a611cdba16
```

**First run output:**
```
First run: stored 25 activities (no notifications)
No new activity detected
{
  "hasNewActivity": false,
  "count": 0,
  "activities": []
}
```

This is expected - it's storing the initial state.

**Second run (if there's new activity):**
```
Found 1 new activities:

🟢 BUY
Market: Will Bitcoin reach $100,000 by end of 2025?
Outcome: YES
Size: 5,000 shares @ $0.6700
Value: $3,350.00 USDC
User: Crypto-Whale
Wallet: 0xdfe3...73c4
Time: 2025-11-14 15:32:18 UTC
Transaction: 0xabc123...

JSON output for n8n:
{
  "hasNewActivity": true,
  "count": 1,
  "activities": [...]
}
```

### 3. Set Up Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Save your **bot token** (looks like: `123456:ABC-DEF1234...`)
4. Send a message to your bot (e.g., "hello")
5. Get your **chat ID**:
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Look for `"chat":{"id":123456789}`
   - Save this number

### 4. Set Up n8n Workflow

#### Option A: n8n Cloud (Easiest)

1. Sign up at [n8n.cloud](https://n8n.cloud) (free tier available)
2. Create a new workflow

#### Option B: Self-Hosted n8n (Docker)

```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

Access at: `http://localhost:5678`

### 5. Import the Workflow

1. In n8n, go to **Workflows** → **Import from File**
2. Select `workflows/polymarket-monitor.json`
3. The workflow will be imported with all nodes configured

### 6. Configure the Workflow

The workflow has 4 main nodes:

```
Schedule Trigger (every 5 min)
  ↓
Execute Python Script
  ↓
Check if New Activity (IF node)
  ↓ (yes)
Send Telegram Notification
```

#### Configure Python Script Execution

1. Click on the **"Execute Python Script"** node
2. Set the **Command** to:
   ```bash
   python C:\Users\Yordan\Desktop\polymarketbot\monitor.py 0xdfe3fedc5c7679be42c3d393e99d4b55247b73c4
   ```
   *(Update the path to match your actual location)*

#### Configure Telegram

1. Click on the **"Send Telegram"** node
2. Add credentials:
   - **Access Token**: Your bot token from Step 3
3. Set **Chat ID**: Your chat ID from Step 3

### 7. Test & Activate

1. Click **Execute Workflow** to test
2. First run should complete without sending notification (expected)
3. Run again - if there's new activity, you'll get a Telegram message
4. Toggle **Active** to enable automatic monitoring

## How the Monitor Works

### Database Schema

SQLite database (`polymarket.db`) stores:

- `transaction_hash` - Unique identifier for each trade
- `wallet_address` - Wallet being monitored
- `timestamp` - When the trade happened
- `side` - BUY or SELL
- `title` - Market title
- `outcome` - YES or NO
- `size`, `price`, `usdc_size` - Trade details
- `raw_data` - Full JSON response

### Detection Logic

1. **First run**: Stores all current activities, returns no new activity (prevents spam)
2. **Subsequent runs**:
   - Fetches latest 25 activities from API
   - Compares with last seen transaction hash in database
   - Returns only transactions newer than last seen
   - Stores new transactions in database

### Example Flow

```
Run 1 (12:00 PM):
  - API returns 25 activities
  - Last seen: None
  - Action: Store all 25, return empty
  - Notification: No

Run 2 (12:05 PM):
  - API returns 25 activities (23 old, 2 new)
  - Last seen: tx_hash_from_12:00
  - Action: Store 2 new, return 2 new
  - Notification: Yes (2 new trades)

Run 3 (12:10 PM):
  - API returns 25 activities (all old)
  - Last seen: tx_hash_from_12:05
  - Action: Nothing new
  - Notification: No
```

## Monitoring Multiple Wallets

### Option 1: Run Script Multiple Times

In n8n, duplicate the workflow for each wallet:

```bash
python monitor.py 0xwallet1
python monitor.py 0xwallet2
python monitor.py 0xwallet3
```

Each wallet has its own row in the database, tracked independently.

### Option 2: Loop in n8n

Use n8n's **Loop** nodes to iterate over multiple wallets:

1. Create a **Code** node with wallet array
2. Use **Split In Batches** node
3. Execute script for each wallet
4. Aggregate results

## Advanced Usage

### Query the Database Directly

```bash
sqlite3 polymarket.db
```

```sql
-- See all activities for a wallet
SELECT timestamp, side, title, usdc_size
FROM activities
WHERE wallet_address = '0xdfe3fedc5c7679be42c3d393e99d4b55247b73c4'
ORDER BY timestamp DESC
LIMIT 10;

-- Total volume traded
SELECT wallet_address, COUNT(*) as trades, SUM(usdc_size) as total_volume
FROM activities
GROUP BY wallet_address;

-- Recent buys vs sells
SELECT side, COUNT(*) as count, SUM(usdc_size) as volume
FROM activities
WHERE wallet_address = '0xdfe3fedc5c7679be42c3d393e99d4b55247b73c4'
GROUP BY side;
```

### Customize the Script

The `monitor.py` script is easy to extend:

**Filter by trade size:**
```python
# In get_new_activities method, after finding new_activities:
new_activities = [a for a in new_activities if float(a.get("usdcSize", 0)) > 500]
```

**Filter by market:**
```python
# Only crypto markets
new_activities = [a for a in new_activities if "bitcoin" in a.get("title", "").lower()]
```

**Different output format:**
```python
# Modify the format_activity method to change notification style
```

## Troubleshooting

### "No module named 'requests'"
```bash
pip install requests
```

### Database locked error
- Make sure only one instance of the script runs at a time
- n8n's schedule should have enough gap between runs (5+ minutes recommended)

### API returns empty
- Check if wallet address is valid (starts with 0x, 42 characters)
- Test the API directly: `https://data-api.polymarket.com/activity?user=0xdfe3...&limit=25`

### Telegram not sending
- Verify bot token is correct
- Ensure you've sent `/start` to your bot
- Check chat ID is a number, not a string

## Project Structure

```
polymarketbot/
├── monitor.py              # Main Python script
├── polymarket.db          # SQLite database (auto-created)
├── workflows/
│   └── polymarket-monitor.json   # n8n workflow to import
└── README.md              # This file
```

## Requirements

- Python 3.7+
- `requests` library
- n8n (cloud or self-hosted)
- Telegram account

## Why This Architecture?

- **Python handles logic**: Easier to debug, test, and extend than n8n nodes
- **SQLite for state**: Simple, reliable, no external dependencies
- **n8n for scheduling**: Visual workflow, easy to monitor
- **Separation of concerns**: Script can run standalone or via n8n

## License

MIT - Use freely
