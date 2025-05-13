#!/bin/bash

# install_complexity_tools.sh
# Description: Installs lightweight command-line tools for Python code complexity analysis on Ubuntu.
#              Prioritizes apt for system-wide installation and uses pip with --break-system-packages as a fallback.
#              Improved apt attempt logging and verification.
# Author: EssenceSentry

echo "Starting installation of Python code complexity analysis tools..."
echo "-----------------------------------------------------------------"
echo "[WARNING] This script will attempt system-wide installations."
echo "[WARNING] Using 'pip3 install --break-system-packages' can potentially conflict with system-managed packages."
echo "[WARNING] Proceed with caution and understand the risks."
echo "-----------------------------------------------------------------"
read -p "Do you wish to continue? (y/N): " confirmation
if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
    echo "Installation aborted by user."
    exit 0
fi
echo "-----------------------------------------------------------------"


# 0. Update package lists
echo "[INFO] Updating package lists..."
sudo apt-get update -y
echo "-----------------------------------------------------------------"

# 1. Install Python3 pip (if not already installed) - apt should handle this if python3 is present
echo "[INFO] Ensuring python3-pip is installed..."
sudo apt-get install -y python3-pip
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install python3-pip via apt. Please ensure Python 3 and pip are correctly set up."
    # Not exiting, to allow pip attempts for tools if user insists and apt fails for a tool
fi
echo "-----------------------------------------------------------------"

# Function to attempt apt install, then pip install as fallback
install_tool() {
    local tool_name="$1"
    local apt_package_name_py3="$2"  # e.g., python3-radon
    local apt_package_name_direct="$3" # e.g., flake8 (if no python3- prefix)
    local pip_package_name="$4"      # e.g., radon
    local tool_executable_name="$5"  # e.g., radon, flake8, pygmentize

    echo "[INFO] Installing $tool_name (expected executable: $tool_executable_name)..."

    # Try apt with python3- prefix
    if [ -n "$apt_package_name_py3" ]; then
        echo "[INFO] Attempting apt install with '$apt_package_name_py3'..."
        sudo apt-get install -y "$apt_package_name_py3"
        if [ $? -eq 0 ]; then
            echo "[INFO] 'apt-get install -y $apt_package_name_py3' reported success (exit code 0)."
            if command -v "$tool_executable_name" &> /dev/null; then
                echo "[SUCCESS] $tool_name installed and command '$tool_executable_name' verified via apt ($apt_package_name_py3)."
            else
                echo "[WARNING] $tool_name installed via apt ($apt_package_name_py3), but command '$tool_executable_name' not found immediately by 'command -v'. Trusting apt's success."
                echo "[INFO] This might be a PATH issue for the current script session or a slight delay. Assuming $tool_name is available."
            fi
            echo "-----------------------------------------------------------------"
            return
        else
             echo "[INFO] 'apt-get install -y $apt_package_name_py3' failed or package not found (exit code $?)."
        fi
    fi

    # Try apt with direct name
    if [ -n "$apt_package_name_direct" ]; then
        echo "[INFO] Attempting apt install with '$apt_package_name_direct'..."
        sudo apt-get install -y "$apt_package_name_direct"
        if [ $? -eq 0 ]; then
            echo "[INFO] 'apt-get install -y $apt_package_name_direct' reported success (exit code 0)."
            if command -v "$tool_executable_name" &> /dev/null; then
                echo "[SUCCESS] $tool_name installed and command '$tool_executable_name' verified via apt ($apt_package_name_direct)."
            else
                echo "[WARNING] $tool_name installed via apt ($apt_package_name_direct), but command '$tool_executable_name' not found immediately by 'command -v'. Trusting apt's success."
                echo "[INFO] This might be a PATH issue for the current script session or a slight delay. Assuming $tool_name is available."
            fi
            echo "-----------------------------------------------------------------"
            return
        else
            echo "[INFO] 'apt-get install -y $apt_package_name_direct' failed or package not found (exit code $?)."
        fi
    fi

    # Fallback to pip3 with --break-system-packages
    echo "[INFO] Could not install $tool_name via apt. Attempting with pip3..."
    echo "[WARNING] Using 'sudo pip3 install --break-system-packages $pip_package_name'. This may affect system Python packages."
    sudo pip3 install --break-system-packages "$pip_package_name"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install $tool_name via pip3 (command: $pip_package_name). Check permissions, network, or Python environment."
    else
        if command -v "$tool_executable_name" &> /dev/null; then
            echo "[SUCCESS] $tool_name installed and command '$tool_executable_name' verified via pip3 (with --break-system-packages)."
        else
            echo "[SUCCESS] $tool_name installed via pip3 (with --break-system-packages), but command '$tool_executable_name' not immediately found. Check PATH if issues persist."
        fi
    fi
    echo "-----------------------------------------------------------------"
}

# Install tools
# Tool Name | Apt Pkg (python3-) | Apt Pkg (direct) | Pip Pkg        | Executable Name
install_tool "Radon"      "python3-radon"      ""                 "radon"          "radon"
install_tool "McCabe"     "python3-mccabe"     ""                 "mccabe"         "mccabe"
install_tool "Flake8"     "python3-flake8"     "flake8"           "flake8"         "flake8"
install_tool "Pygments"   "python3-pygments"   ""                 "Pygments"       "pygmentize"
install_tool "complexipy" ""                   ""                 "complexipy"     "complexipy" # Less likely to be in apt

# Install cloc (Count Lines of Code)
echo "[INFO] Installing cloc..."
if command -v cloc &> /dev/null; then
    echo "[SUCCESS] cloc is already installed."
else
    echo "[INFO] cloc not found. Attempting apt install..."
    sudo apt-get install -y cloc
    if command -v cloc &> /dev/null; then
        echo "[SUCCESS] cloc installed via apt."
    else
        echo "[ERROR] Failed to install cloc via apt-get. Please install it manually if needed."
    fi
fi
echo "-----------------------------------------------------------------"

echo "All selected tools installation process finished."
echo "Please check for any warnings or errors above."
echo "If pip installed packages into a user-local directory (e.g. ~/.local/bin) and they are not found,"
echo "you might need to add it to your PATH: export PATH=\$PATH:~/.local/bin"
echo "Add this line to your ~/.bashrc or ~/.zshrc for persistence."

exit 0
