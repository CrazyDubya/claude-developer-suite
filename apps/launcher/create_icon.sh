#!/bin/bash
# Script to create macOS .icns file from SVG icon

# Ensure we have the required tools
if ! command -v inkscape &> /dev/null; then
    echo "Inkscape is required but not found. Installing via Homebrew..."
    brew install --cask inkscape
fi

if ! command -v iconutil &> /dev/null; then
    echo "iconutil not found. This should be included with macOS."
    echo "Please check your macOS installation."
    exit 1
fi

# Create the icons directory if it doesn't exist
mkdir -p icons

# Convert SVG to PNG at various sizes
echo "Converting SVG to PNG at various sizes..."

# Create a temporary iconset directory
mkdir -p icons/claude_launcher.iconset

# Use Inkscape to convert to various sizes
SIZES=(16 32 128 256 512)
for size in "${SIZES[@]}"; do
    # Regular size
    inkscape -w $size -h $size icons/claude_launcher.svg -o icons/claude_launcher.iconset/icon_${size}x${size}.png

    # Retina size (2x)
    if [ $size -lt 512 ]; then
        double_size=$((size * 2))
        inkscape -w $double_size -h $double_size icons/claude_launcher.svg -o icons/claude_launcher.iconset/icon_${size}x${size}@2x.png
    fi
done

# Create the .icns file
echo "Creating .icns file..."
iconutil -c icns icons/claude_launcher.iconset

# Move the resulting .icns file to the icons directory
mv claude_launcher.icns icons/

# Clean up
rm -rf icons/claude_launcher.iconset

echo "Icon created successfully at icons/claude_launcher.icns"