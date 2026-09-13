#!/usr/bin/env python3
"""
Build script to create a standalone macOS application for Claude MCP Launcher
"""

import os
import sys
import subprocess
import shutil


def create_app():
    """Create the app bundle using PyInstaller"""
    print("Creating Claude MCP Launcher application...")

    # Ensure PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "PyInstaller"], check=True)

    # Create a temporary spec file
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Claude MCP Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/claude_launcher.icns',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Claude MCP Launcher',
)
app = BUNDLE(
    coll,
    name='Claude MCP Launcher.app',
    icon='icons/claude_launcher.icns',
    bundle_identifier='com.claudemcplauncher',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleDocumentTypes': [],
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': 'MIT License',
        'CFBundleGetInfoString': 'Claude MCP Launcher, a simple tool to configure and launch Claude with MCP servers',
    },
)
    """

    with open("claude_launcher.spec", "w") as f:
        f.write(spec_content)

    # Create icons directory if it doesn't exist
    if not os.path.exists("icons"):
        os.makedirs("icons")

    # Run PyInstaller
    subprocess.run(["pyinstaller", "claude_launcher.spec"], check=True)

    print("Application created successfully!")


def create_dmg():
    """Create a DMG installer for the app"""
    print("Creating DMG installer...")

    # Ensure create-dmg is installed
    try:
        subprocess.run(["create-dmg", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("create-dmg tool not found. Installing via Homebrew...")
        try:
            subprocess.run(["brew", "install", "create-dmg"], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Homebrew not found. Please install Homebrew first:")
            print("  /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
            print("Then run this script again.")
            return False

    # Create a directory for the DMG contents
    if os.path.exists("dmg_temp"):
        shutil.rmtree("dmg_temp")
    os.makedirs("dmg_temp")

    # Copy the app to the DMG directory
    shutil.copytree(
        "dist/Claude MCP Launcher.app",
        "dmg_temp/Claude MCP Launcher.app"
    )

    # Create a symlink to /Applications
    os.symlink("/Applications", "dmg_temp/Applications")

    # Create the DMG
    subprocess.run([
        "create-dmg",
        "--volname", "Claude MCP Launcher",
        "--volicon", "icons/claude_launcher.icns",
        "--window-pos", "200", "120",
        "--window-size", "800", "400",
        "--icon-size", "100",
        "--icon", "Claude MCP Launcher.app", "200", "190",
        "--hide-extension", "Claude MCP Launcher.app",
        "--app-drop-link", "600", "190",
        "Claude_MCP_Launcher.dmg",
        "dmg_temp"
    ], check=True)

    # Clean up
    shutil.rmtree("dmg_temp")

    print("DMG installer created successfully!")
    return True


if __name__ == "__main__":
    create_app()
    success = create_dmg()

    if success:
        print("\nBuild completed successfully!")
        print("You can distribute 'Claude_MCP_Launcher.dmg' to users.")
    else:
        print(
            "\nBuild completed with warnings. The application was created but the DMG installer could not be created.")
        print("You can manually create a DMG or distribute the 'dist/Claude MCP Launcher.app' folder.")