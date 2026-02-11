#!/bin/bash
#
# WebP Conversion Script für d4sw4r.github.io
# Konvertiert alle PNG und JPG Bilder zu WebP Format
#
# Voraussetzung: webp installiert
# Ubuntu/Debian: sudo apt-get install webp
# macOS: brew install webp
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IMG_DIR="$PROJECT_ROOT/assets/img"

echo "🖼️  WebP Conversion Script"
echo "=========================="
echo ""
echo "Image Directory: $IMG_DIR"
echo ""

# Check if cwebp is installed
if ! command -v cwebp &> /dev/null; then
    echo "❌ Error: cwebp is not installed!"
    echo ""
    echo "Please install webp:"
    echo "  Ubuntu/Debian: sudo apt-get install webp"
    echo "  macOS: brew install webp"
    echo "  Arch: sudo pacman -S libwebp"
    exit 1
fi

# Create backup directory
BACKUP_DIR="$PROJECT_ROOT/assets/img-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "📦 Backup created: $BACKUP_DIR"
echo ""

# Counter
total=0
converted=0
skipped=0

# Process PNG files
echo "🔄 Converting PNG files..."
while IFS= read -r -d '' img; do
    total=$((total + 1))
    filename=$(basename "$img")
    webp_path="${img%.png}.webp"
    
    # Skip if WebP already exists and is newer
    if [[ -f "$webp_path" ]] && [[ "$webp_path" -nt "$img" ]]; then
        echo "  ⏭️  Skipped: $filename (WebP already exists)"
        skipped=$((skipped + 1))
        continue
    fi
    
    # Backup original
    cp "$img" "$BACKUP_DIR/"
    
    # Convert to WebP
    if cwebp -q 85 -m 6 "$img" -o "$webp_path" &> /dev/null; then
        original_size=$(stat -f%z "$img" 2>/dev/null || stat -c%s "$img")
        webp_size=$(stat -f%z "$webp_path" 2>/dev/null || stat -c%s "$webp_path")
        savings=$(( (original_size - webp_size) * 100 / original_size ))
        
        echo "  ✅ $filename → ${filename%.png}.webp (-${savings}%)"
        converted=$((converted + 1))
    else
        echo "  ❌ Failed: $filename"
    fi
done < <(find "$IMG_DIR" -maxdepth 1 -name "*.png" -print0)

# Process JPG/JPEG files
echo ""
echo "🔄 Converting JPG/JPEG files..."
while IFS= read -r -d '' img; do
    total=$((total + 1))
    filename=$(basename "$img")
    base="${img%.*}"
    webp_path="${base}.webp"
    
    # Skip if WebP already exists and is newer
    if [[ -f "$webp_path" ]] && [[ "$webp_path" -nt "$img" ]]; then
        echo "  ⏭️  Skipped: $filename (WebP already exists)"
        skipped=$((skipped + 1))
        continue
    fi
    
    # Backup original
    cp "$img" "$BACKUP_DIR/"
    
    # Convert to WebP
    if cwebp -q 85 -m 6 "$img" -o "$webp_path" &> /dev/null; then
        original_size=$(stat -f%z "$img" 2>/dev/null || stat -c%s "$img")
        webp_size=$(stat -f%z "$webp_path" 2>/dev/null || stat -c%s "$webp_path")
        savings=$(( (original_size - webp_size) * 100 / original_size ))
        
        extension="${filename##*.}"
        echo "  ✅ $filename → ${filename%.$extension}.webp (-${savings}%)"
        converted=$((converted + 1))
    else
        echo "  ❌ Failed: $filename"
    fi
done < <(find "$IMG_DIR" -maxdepth 1 \( -name "*.jpg" -o -name "*.jpeg" \) -print0)

# Summary
echo ""
echo "================================"
echo "📊 Conversion Summary"
echo "================================"
echo "Total images found:  $total"
echo "Converted:           $converted"
echo "Skipped:             $skipped"
echo ""
echo "✨ Done! Original files backed up to:"
echo "   $BACKUP_DIR"
echo ""
echo "💡 Next steps:"
echo "   1. Test the site locally"
echo "   2. Update image references to use WebP"
echo "   3. Implement <picture> tags for fallback"
echo "   4. Commit changes to git"
echo ""
