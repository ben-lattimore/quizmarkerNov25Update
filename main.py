from dotenv import load_dotenv
import sys
import importlib.util

# Load environment variables from .env file
load_dotenv()

# Load app.py as a module (not the app package)
spec = importlib.util.spec_from_file_location("app_module", "app.py")
app_module = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app_module
spec.loader.exec_module(app_module)

if __name__ == "__main__":
    app_module.app.run(host="0.0.0.0", port=5001, debug=True)
