import os
import subprocess
import sys

def build_exe():
    """
    Script to build the executable using PyInstaller.
    """
    print("Starting build process...")

    # Name of the main script
    main_script = "main.py"
    
    # Name of the output executable
    exe_name = "NetworkMonitor"

    # PyInstaller arguments
    args = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # Run without console window
        "--onefile",   # Bundle into a single file
        f"--name={exe_name}",
        # Add necessary hidden imports if PyInstaller misses them
        "--hidden-import=PyQt5",
        "--hidden-import=openpyxl",
        "--hidden-import=sqlite3",
        "--hidden-import=plyer.platforms.win.notification",
        # Bundle data files if needed (e.g., config.json if it's static, but usually it's created at runtime)
        # "--add-data=config.json;." 
        main_script
    ]

    print(f"Running command: {' '.join(args)}")

    try:
        subprocess.check_call(args)
        print("\nBuild completed successfully!")
        print(f"Executable can be found in the 'dist/{exe_name}' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\nError during build: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\nError: 'pyinstaller' not found. Please ensure it is installed (pip install pyinstaller).")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
