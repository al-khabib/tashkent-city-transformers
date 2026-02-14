import requests
import time

# Your live Render URL
url = "https://tashkent-city-grip-api.onrender.com/ask"

# The message we want to send
payload = {
    "query": "Salom! Can you tell me what the law says about transformer safety in Tashkent?"
}

print(f"🚀 Sending request to: {url}...")
start_time = time.time()

try:
    # We use a 90-second timeout because Render's Free Tier 
    # might be "waking up" from sleep mode.
    response = requests.post(url, json=payload, timeout=90)
    
    end_time = time.time()
    duration = round(end_time - start_time, 2)

    if response.status_code == 200:
        print(f"✅ SUCCESS! (Response time: {duration}s)")
        print("-" * 30)
        print("AI RESPONSE:", response.json().get("answer", response.text))
        print("-" * 30)
    else:
        print(f"❌ ERROR: Received status code {response.status_code}")
        print("Details:", response.text)

except requests.exceptions.Timeout:
    print("⏳ TIMEOUT: The server took too long to wake up. Try running the script again!")
except Exception as e:
    print(f"🚨 FAILED: Could not connect to the server. Error: {e}")