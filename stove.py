import httpx
import time
import yaml
from openai import OpenAI
import requests

# Add Telegram bot notification function
def send_telegram_notification(bot_token, chat_id, message):
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(telegram_url, json={
            "chat_id": chat_id,
            "text": message
        })
        return response.json()
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")
        return None

# Load configuration
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# HTTP/2 client with support for multiple requests
client = httpx.Client(http2=True)

url = 'https://api.onstove.com/blockchecker/v2.0/captcha/keys'

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-TW,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
}

# Use httpx for the request instead of requests
response = client.post(url, headers=headers)

# Extract key and image_url
captcha_key = response.json()['value']['captcha_key']
image_url = response.json()['value']['resource']['image_url']

print(f'Captcha Key: {captcha_key}')
print(f'Image URL: {image_url}')

# Initialize OpenAI client
openai_client = OpenAI(api_key=config['openai']['api_key'])

# Call OpenAI Vision API
response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What numbers do you see in this captcha image? Please only respond with the numbers without spaces, nothing else."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            ]
        }
    ],
    max_tokens=300
)

# Print the result
captcha_numbers = response.choices[0].message.content
print("Captcha numbers:", captcha_numbers)

# Login request
login_url = 'https://s-api.onstove.com/sign/v2.1/pc/signin'

login_headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-TW,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'captcha-key': captcha_key,
    'captcha-value': captcha_numbers,
    'content-type': 'application/json',
    'referer': 'https://accounts.onstove.com/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
}

login_data = {
    "client_id": config['stove']['client_id'],
    "service_id": "Portal_Web",
    "provider_cd": "SO",
    "provider_data": config['stove']['provider_data'],
    "inflow_path": "null",
    "game_no": "null",
    "gds_info": {
        "is_default": False,
        "nation": "TW",
        "regulation": "ETC",
        "timezone": "Asia/Taipei",
        "utc_offset": 480,
        "lang": "zh-tw",
        "ip": ""
    }
}

# Use httpx for the login request
login_response = client.post(login_url, headers=login_headers, json=login_data)
print("Login Response Status Code:", login_response.status_code)

if login_response.json()['code'] == 0:
    access_token = login_response.json()['value']['access_token']
    refresh_token = login_response.json()['value']['refresh_token']

    print("Access Token:", access_token)
    print("Refresh Token:", refresh_token)

    drawing_lot_url = 'https://api.onstove.com/emsbackapi/event/v2.0/drawingLot'

    drawing_lot_headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-TW,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'authorization': f'Bearer {access_token}',
        'content-type': 'application/json',
        'origin': 'https://reward.onstove.com',
        'referer': 'https://reward.onstove.com/',
    }

    drawing_lot_data = {
        "sub_event_no": config['drawing_lot']['sub_event_no'],
        "lang": config['drawing_lot']['lang']
    }

    for _ in range(30):
        try:
            drawing_lot_response = client.post(drawing_lot_url, headers=drawing_lot_headers, json=drawing_lot_data)
            drawing_lot_json = drawing_lot_response.json()

            if drawing_lot_json.get('value') and drawing_lot_json['value'].get('gift_info'):
                print("Drawing lot response:", drawing_lot_json['value']['gift_info']['gift_name'])
            else:
                print("No gift info found in the response")

            if config.get('telegram', {}).get('enabled', False):
                bot_token = config['telegram']['bot_token']
                chat_id = config['telegram']['chat_id']
                
                # Prepare notification message based on drawing result
                if drawing_lot_json['code'] == 0:
                    message = f"🎉 Lottery Drawing Successful!\n"
                    message += f"Details: {drawing_lot_json['value']['gift_info']['gift_name']}"
                else:
                    message = f"❌ Lottery Drawing Failed\n"
                    message += f"Error: {drawing_lot_json}"
                
                # Send Telegram notification
                send_telegram_notification(bot_token, chat_id, message)

        except Exception as e:
            print(f"Error in drawing lot request: {e}")
            print("Response content:", drawing_lot_response.text)
        
        time.sleep(6)

# Close the HTTP/2 client
client.close()
