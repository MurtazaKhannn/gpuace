import requests
import pyperclip
import json

def main():
    # Define the API endpoint and payload
    url = "http://127.0.0.1:5000/api/start-container"
    payload = {
        "image": "mongo:latest",  # Replace with the desired image
        "command": None,          # Optional: Add a command if needed
        "environment": {},        # Optional: Add environment variables if needed
        "ports": {"27017/tcp": 27017},  # Optional: Map ports if needed
        "volumes": {},            # Optional: Add volume mappings if needed
        "name": "my-mongo-container"  # Optional: Specify a container name
    }

    try:
        # Send a POST request to the API
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an error for HTTP errors

        # Parse the response JSON
        response_data = response.json()

        # Convert the response to a formatted JSON string
        formatted_response = json.dumps(response_data, indent=4)

        # Copy the response to the clipboard
        pyperclip.copy(formatted_response)
        print("Response copied to clipboard successfully!")
        print("Response:")
        print(formatted_response)

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()