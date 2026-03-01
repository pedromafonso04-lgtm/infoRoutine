import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Get the API key from environment variables
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key or api_key == "your_gemini_api_key_here":
    print("Error: Please set a valid GEMINI_API_KEY in the .env file.")
    exit(1)

print(f"✅ Found API key starting with: {api_key[:10]}...")

try:
    # Initialize the client
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    # We will use gemini-2.5-flash as the test model
    model_name = 'gemini-2.5-flash'
    prompt = "Hello! Say hi back in Portuguese."
    
    print(f"\nSending '{prompt}' to model: {model_name}...")
    
    # Call the API
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    
    # Print the response
    print("\n--- Response from Gemini ---")
    print(response.text)
    print("----------------------------\n")
    print("🎉 Success! The API key and model are working correctly.")

except Exception as e:
    print(f"\n❌ Error connecting to Gemini API:")
    print(f"{type(e).__name__}: {str(e)}")
