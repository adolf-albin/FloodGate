import time
import urllib.request

TARGET = "http://127.0.0.1:5000/"
REQUESTS = 20
DELAY = 0.2

print(f"Sending {REQUESTS} controlled requests to {TARGET}")

for i in range(REQUESTS):
    try:
        with urllib.request.urlopen(TARGET, timeout=3) as response:
            print(f"{i + 1}/{REQUESTS} -> HTTP {response.status}")
    except Exception as e:
        print(f"{i + 1}/{REQUESTS} -> ERROR: {e}")

    time.sleep(DELAY)

print("Simulation finished.")
