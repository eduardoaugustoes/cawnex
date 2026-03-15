#!/bin/bash
set -e

# Script to switch to the fixed pipeline once validated
echo "🔧 Pipeline Fix and Validation Script"
echo "====================================="

cd "$(dirname "$0")/../.github/workflows/" || exit 1

echo "📊 Current workflows:"
ls -la *.yml

echo ""
echo "🧪 Testing approach:"
echo "1. The debug-pipeline.yml will test basic change detection"
echo "2. The main-pipeline-fixed.yml has simplified logic to avoid failures"
echo "3. Once confirmed working, we'll replace main-pipeline.yml"

echo ""
read -p "🔄 Switch to fixed pipeline now? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 Switching to fixed pipeline..."

    # Backup current pipeline
    echo "📁 Backing up current pipeline..."
    cp main-pipeline.yml "disabled/main-pipeline-broken-$(date +%Y%m%d-%H%M%S).yml"

    # Replace with fixed version
    echo "✅ Installing fixed pipeline..."
    cp main-pipeline-fixed.yml main-pipeline.yml

    # Clean up
    echo "🧹 Cleaning up..."
    rm main-pipeline-fixed.yml

    echo ""
    echo "✅ Fixed pipeline is now active!"
    echo "🧪 Test with a small change to verify it works"
    echo "📁 Broken version backed up to disabled/"

    echo ""
    echo "🚀 Next steps:"
    echo "1. git add . && git commit -m 'fix: activate working pipeline'"
    echo "2. git push"
    echo "3. Test with a small change"
    echo "4. Remove debug-pipeline.yml when confirmed working"
else
    echo "❌ Keeping current pipeline for now"
    echo "💡 Run this script again when ready to switch"
fi

echo ""
echo "🔍 Manual testing:"
echo "# Test docs change (should trigger debug workflow):"
echo 'echo "# Pipeline test" >> ../../README.md'
echo 'git add . && git commit -m "test: trigger debug workflow" && git push'
