import os
import hopsworks
from dotenv import load_dotenv

# Check the connection to Hopsworks through the saved API key in .env.
def main():
    # 1. Load environment variables from .env
    load_dotenv()
    api_key = os.environ.get("HOPSWORKS_API_KEY")
    if not api_key:
        raise ValueError("HOPSWORKS_API_KEY not found in .env")

    # 2. Login to Hopsworks using the API key
    project = hopsworks.login(api_key_value=api_key)
    print(f"Project name: {project.name}, with ID {project.id}")

if __name__ == "__main__":
    main()
