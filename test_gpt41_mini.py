import os
import json
import base64
from openai import OpenAI

# Initialize the client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def encode_image_to_base64(image_path):
    """Convert an image file to base64 encoding"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

try:
    # Test simple text completion
    print("Testing GPT-4.1-mini text completion...")
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "user", "content": "Hello, this is a test message without images"}
        ],
        max_tokens=100
    )
    print("Text completion successful!")
    print(f"Response: {response.choices[0].message.content}")
    print("-" * 50)
    
    # List all models 
    models = client.models.list()
    print("Models that support vision:")
    # List known vision models
    known_vision_models = ["gpt-4o", "gpt-4-vision-preview"]
    print(f"Known vision models: {', '.join(known_vision_models)}")
    
    # Print details about gpt-4.1-mini
    print("\nGPT-4.1-mini variants:")
    mini_models = [m for m in models.data if "gpt-4.1-mini" in m.id]
    for model in mini_models:
        print(f"- {model.id}")
    
    # Now try with an image to see if GPT-4.1-mini supports vision
    print("\nAttempting to use GPT-4.1-mini with an image...")
    try:
        # Find a sample image from the attached_assets folder
        sample_image_path = "./generated-icon.png"
        if os.path.exists(sample_image_path):
            base64_image = encode_image_to_base64(sample_image_path)
            print(f"Image encoded successfully from {sample_image_path}")
            
            vision_response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "What's in this image? Describe it briefly."
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=100
            )
            print("Vision capability test successful with GPT-4.1-mini!")
            print(f"Response: {vision_response.choices[0].message.content}")
        else:
            print(f"Sample image not found at {sample_image_path}")
    except Exception as vision_error:
        print(f"Vision capability test failed: {type(vision_error).__name__}: {vision_error}")
        print("\nTrying with GPT-4o as a fallback...")
        try:
            if os.path.exists(sample_image_path):
                vision_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": "What's in this image? Describe it briefly."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=100
                )
                print("Vision capability test successful with GPT-4o!")
                print(f"Response: {vision_response.choices[0].message.content}")
            else:
                print(f"Sample image not found at {sample_image_path}")
        except Exception as fallback_error:
            print(f"Fallback to GPT-4o also failed: {type(fallback_error).__name__}: {fallback_error}")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")