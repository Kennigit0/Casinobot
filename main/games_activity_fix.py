# Run this once to patch activities.py
with open("/root/casino_bot/activities.py" if __import__("os").path.exists("/root/casino_bot/activities.py") else "/data/data/com.termux/files/home/casino_bot/activities.py", "r") as f:
    content = f.read()
print("Found file")
