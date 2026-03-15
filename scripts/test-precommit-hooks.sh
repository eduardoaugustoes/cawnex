#!/bin/bash
set -e

# Test Pre-commit Hooks - Verify They Match CI Exactly
echo "🧪 Testing Pre-commit Hooks"
echo "==========================="
echo "This tests that pre-commit hooks run the same commands as CI"
echo ""

cd "$(dirname "$0")/.." || exit 1

echo "📍 Project root: $(pwd)"

# Check if virtual environment exists
if [ ! -d "apps/api/venv" ]; then
    echo "❌ Python virtual environment not found!"
    echo "🛠️ Run ./scripts/setup-local-dev.sh first"
    exit 1
fi

echo ""
echo "🔍 **Testing individual CI commands locally:**"
echo "============================================="

cd apps/api
source venv/bin/activate

echo ""
echo "🐍 1. MyPy (strict type checking)..."
if mypy src --strict --show-error-codes; then
    echo "✅ MyPy passed"
else
    echo "❌ MyPy failed"
    exit 1
fi

echo ""
echo "🎨 2. Black (formatting check)..."
if black src tests --check --line-length=88; then
    echo "✅ Black passed"
else
    echo "❌ Black formatting needed"
    echo "🔧 Run: black src tests --line-length=88"
    exit 1
fi

echo ""
echo "📏 3. Flake8 (style guide)..."
if flake8 src --max-line-length=88 --max-complexity=10; then
    echo "✅ Flake8 passed"
else
    echo "❌ Flake8 failed"
    exit 1
fi

echo ""
echo "🧪 4. Pytest (tests + coverage)..."
if pytest --cov=src --cov-report=term-missing --cov-fail-under=80; then
    echo "✅ Pytest passed"
else
    echo "❌ Pytest failed"
    exit 1
fi

cd ../..

echo ""
echo "⚡ 5. Prettier (TypeScript/docs formatting)..."
if npm run format:check; then
    echo "✅ Prettier passed"
else
    echo "❌ Prettier formatting needed"
    echo "🔧 Run: npm run format:write"
    exit 1
fi

echo ""
echo "🪝 **Testing pre-commit hooks:**"
echo "==============================="

echo ""
echo "🔍 Checking pre-commit configuration..."
if pre-commit --version > /dev/null 2>&1; then
    echo "✅ Pre-commit installed"
else
    echo "❌ Pre-commit not installed"
    echo "🛠️ Run: ./scripts/setup-local-dev.sh"
    exit 1
fi

echo ""
echo "🧪 Running pre-commit on all files..."
if pre-commit run --all-files; then
    echo "✅ All pre-commit hooks passed!"
else
    echo "⚠️  Some pre-commit hooks failed"
    echo "🔧 This is expected if there are formatting issues"
    echo "💡 Pre-commit hooks should fix formatting automatically"
fi

echo ""
echo "==============================================="
echo "🎉 **Pre-commit Hook Test Complete!**"
echo ""
echo "💡 **How to use:**"
echo "  git add ."
echo "  git commit  # Pre-commit hooks run automatically"
echo ""
echo "🔧 **Manual fixes if needed:**"
echo "  cd apps/api && source venv/bin/activate"
echo "  black src tests --line-length=88    # Fix Python formatting"
echo "  cd ../.. && npm run format:write     # Fix TypeScript/docs"
echo ""
echo "🎯 **Expected workflow:**"
echo "  1. Make changes"
echo "  2. git commit (hooks run automatically)"
echo "  3. Fix any issues locally"
echo "  4. git commit again (should pass)"
echo "  5. git push (CI should pass first try!)"
echo "==============================================="
