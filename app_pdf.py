#!/usr/bin/env python3
"""
Quick fix script for PDF library installation issues
Run this script to diagnose and fix PDF extraction library problems
"""

import sys
import subprocess
import os

def run_command(command):
    """Run a command and return success status"""
    try:
        print(f"Running: {command}")
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ Success: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {e.stderr.strip()}")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_import(module_name):
    """Test if a module can be imported"""
    try:
        __import__(module_name)
        print(f"✅ {module_name} imports successfully")
        return True
    except ImportError:
        print(f"❌ {module_name} import failed")
        return False

def main():
    print("🔍 PDF Library Quick Fix Tool")
    print("=" * 40)
    
    # Check Python and pip
    print(f"Python: {sys.version}")
    print(f"Executable: {sys.executable}")
    print()
    
    # Test current state
    print("Testing current library state...")
    libraries = {
        'fitz': 'PyMuPDF',
        'PyPDF2': 'PyPDF2', 
        'docling': 'Docling'
    }
    
    working_libs = []
    for module, name in libraries.items():
        if test_import(module):
            working_libs.append(name)
    
    if working_libs:
        print(f"\n✅ Working libraries: {', '.join(working_libs)}")
        print("You should be good to go!")
        return
    
    print("\n⚠️ No PDF libraries working. Installing...")
    
    # Upgrade pip first
    print("\n1. Upgrading pip...")
    run_command(f"{sys.executable} -m pip install --upgrade pip")
    
    # Install libraries in order of preference
    packages = [
        ("pymupdf", "PyMuPDF - Most reliable"),
        ("PyPDF2", "PyPDF2 - Basic but works"),
        ("docling", "Docling - Advanced features")
    ]
    
    for package, description in packages:
        print(f"\n2. Installing {description}...")
        
        # Try multiple installation methods
        methods = [
            f"{sys.executable} -m pip install {package}",
            f"{sys.executable} -m pip install --user {package}",
            f"{sys.executable} -m pip install --force-reinstall {package}"
        ]
        
        installed = False
        for method in methods:
            if run_command(method):
                # Test if it actually works
                test_module = "fitz" if package == "pymupdf" else package.split('.')[0]
                if test_import(test_module):
                    print(f"✅ {package} installed and working!")
                    installed = True
                    break
        
        if installed:
            break
        else:
            print(f"❌ Failed to install {package}")
    
    # Final test
    print("\n3. Final verification...")
    working_count = 0
    for module, name in libraries.items():
        if test_import(module):
            working_count += 1
    
    if working_count > 0:
        print(f"\n🎉 SUCCESS! {working_count} PDF library(ies) now working!")
        print("\nYou can now run your Streamlit app:")
        print("streamlit run your_app.py")
    else:
        print("\n❌ Installation failed. Try manual installation:")
        print("\nTry these commands manually:")
        print("pip install --upgrade pip")
        print("pip install pymupdf")
        print("pip install PyPDF2")
        print("\nIf that doesn't work, you might have environment issues.")
        print("Consider creating a fresh virtual environment:")
        print("python -m venv new_env")
        print("source new_env/bin/activate  # On Windows: new_env\\Scripts\\activate")
        print("pip install pymupdf pandas streamlit")

if __name__ == "__main__":
    main()
