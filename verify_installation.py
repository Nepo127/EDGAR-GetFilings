"""
Verification script to test package installation and imports
"""

# verify_installation.py

def check_package(package_name):
    """Try to import a package and print its location if successful."""
    try:
        module = __import__(package_name)
        print(f"✅ Successfully imported {package_name} from {module.__file__}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import {package_name}: {e}")
        return False

def check_function(package_name, function_name):
    """Try to import a specific function from a package."""
    try:
        module = __import__(package_name, fromlist=[function_name])
        function = getattr(module, function_name)
        print(f"✅ Successfully imported {function_name} from {package_name}")
        return True
    except (ImportError, AttributeError) as e:
        print(f"❌ Failed to import {function_name} from {package_name}: {e}")
        return False

def main():
    """Run verification checks."""
    print("\n=== Package Import Verification ===\n")
    
    # Check if the packages can be imported
    packages = ["edgar_parser", "app_utils"]
    for package in packages:
        check_package(package)
    
    print("\n=== Function Import Verification ===\n")
    
    # Check if specific functions can be imported
    functions = [
        ("edgar_parser", "main"),
        ("app_utils", "ConfigManager"),
        ("app_utils", "LoggingManager")
    ]
    for package, function in functions:
        check_function(package, function)
    
    print("\n=== Path Verification ===\n")
    
    # Print Python path
    import sys
    print("Python path:")
    for path in sys.path:
        print(f"  - {path}")
    
    print("\n=== Entry Point Verification ===\n")
    
    # Check for entry point scripts
    import os
    import subprocess
    
    def check_command(command):
        try:
            result = subprocess.run(["which", command], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip()
                print(f"✅ Command '{command}' found at: {path}")
                # Print the first few lines of the script
                if os.path.exists(path):
                    with open(path, "r") as f:
                        content = f.read(500)  # Read first 500 chars
                    print(f"Script content preview:\n{content[:200]}...")
            else:
                print(f"❌ Command '{command}' not found in PATH")
        except Exception as e:
            print(f"❌ Error checking command '{command}': {e}")
    
    check_command("edgar_parser")
    check_command("edgar-parser")

if __name__ == "__main__":
    main()
