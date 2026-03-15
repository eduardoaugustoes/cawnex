#!/bin/bash
set -e

# Local Quality Check Script - Mirror of CI Pipeline
echo "🔍 Running Local Quality Checks (mirrors CI pipeline)"
echo "===================================================="
echo ""

cd "$(dirname "$0")/.." || exit 1

echo "📍 Project root: $(pwd)"
echo ""

# Track overall success
OVERALL_SUCCESS=true

echo "🐍 **Python Quality Checks**"
echo "----------------------------"
cd apps/api

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./scripts/setup-local-dev.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

echo "🔍 MyPy (strict type checking)..."
if mypy src --strict --show-error-codes; then
    echo "✅ MyPy passed"
else
    echo "❌ MyPy failed"
    OVERALL_SUCCESS=false
fi

echo ""
echo "🎨 Black (code formatting)..."
if black src tests --check --line-length=88; then
    echo "✅ Black passed"
else
    echo "❌ Black failed - run 'black src tests --line-length=88' to fix"
    OVERALL_SUCCESS=false
fi

echo ""
echo "📏 Flake8 (style guide)..."
if flake8 src --max-line-length=88 --max-complexity=10; then
    echo "✅ Flake8 passed"
else
    echo "❌ Flake8 failed"
    OVERALL_SUCCESS=false
fi

echo ""
echo "🧪 Pytest (tests + coverage)..."
if pytest --cov=src --cov-report=term-missing --cov-fail-under=80; then
    echo "✅ Pytest passed"
else
    echo "❌ Pytest failed"
    OVERALL_SUCCESS=false
fi

cd ../..

echo ""
echo "⚡ **TypeScript Quality Checks**"
echo "-------------------------------"

echo "📝 TypeScript compilation..."
if npm run type-check:all; then
    echo "✅ TypeScript compilation passed"
else
    echo "❌ TypeScript compilation failed"
    OVERALL_SUCCESS=false
fi

echo ""
echo "📏 TypeScript linting..."
if npm run quality:typescript; then
    echo "✅ TypeScript quality passed"
else
    echo "❌ TypeScript quality failed"
    OVERALL_SUCCESS=false
fi

echo ""
echo "🎨 Prettier (formatting)..."
if npm run format:check; then
    echo "✅ Prettier passed"
else
    echo "❌ Prettier failed - run 'npm run format:write' to fix"
    OVERALL_SUCCESS=false
fi

echo ""
echo "==============================================="
if [ "$OVERALL_SUCCESS" = true ]; then
    echo "🎉 **ALL QUALITY CHECKS PASSED!**"
    echo "✅ Your code is ready to push to CI"
    echo "✅ Pipeline should pass on first try"
else
    echo "❌ **QUALITY CHECKS FAILED**"
    echo "🔧 Fix the issues above before committing"
    echo "💡 This is exactly what CI would catch"
fi
echo "==============================================="

# Exit with appropriate code
if [ "$OVERALL_SUCCESS" = true ]; then
    exit 0
else
    exit 1
fi
