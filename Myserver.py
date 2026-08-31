import requests

# Paste your active ngrok URL from Colab here (include /generate at the end)
SERVER_URL = "https://fidgety-reword-backdrop.ngrok-free.dev/generate"

def request_image(prompt: str, output_path: str = "colab_realvis_output.png"):
    payload = {
        "prompt": prompt,
        "negative_prompt": "cartoon, drawing, painting, blurry, deformed hands, bad quality, oversaturated, CGI",
        "width": 1024,
        "height": 768,
        "steps": 25,
        "guidance_scale": 6.0
    }
    
    print(f"Sending prompt to Colab GPU: '{prompt}'...")
    
    # Header bypasses the ngrok free warning landing page
    headers = {"ngrok-skip-browser-warning": "69420"}
    
    try:
        response = requests.post(SERVER_URL, json=payload, headers=headers, timeout=180)
        
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            print(f"Success! High-resolution image saved to: {output_path}")
        else:
            print(f"Server returned error {response.status_code}: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_prompt = (
        "A hyper-realistic, wide-angle cinematic 35mm documentary photo of a massive traffic jam "
        "on a multi-layered concrete flyover in Karachi during blinding sunny midday weather. "
        "Intricate Pakistani trucks (jingle trucks) adorned with vibrant artwork, yellow-and-black taxis, "
        "auto-rickshaws, motorbikes weaving through gridlocked sedans. "
        "Harsh tropical sunlight, sharp shadows, realistic heat haze shimmer in the air, "
        "dust particles, concrete textures, billboards, 8k resolution."
    )
    
    request_image(test_prompt, "karachi_traffic_hq.png")