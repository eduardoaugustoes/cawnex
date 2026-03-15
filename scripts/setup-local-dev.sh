#!/bin/bash
set -e

# Setup Local Development Environment with Quality Checks
echo "🛠️  Setting up Local Development Environment"
echo "============================================"
echo "This will set up pre-commit hooks and local quality checks"
echo "so you catch issues BEFORE pushing to CI."
echo ""

cd "$(dirname "$0")/.." || exit 1

echo "📍 Current directory: $(pwd)"

# Check if we're in the right place
if [ ! -f "apps/api/pyproject.toml" ]; then
    echo "❌ Error: Could not find apps/api/pyproject.toml"
    echo "Make sure you're running this from the cawnex root directory"
    exit 1
fi

echo ""
echo "🐍 Setting up Python environment..."
cd apps/api

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "⚡ Activating virtual environment..."
source venv/bin/activate

# Install development dependencies
echo "📚 Installing Python dependencies..."
pip install -e .[dev]

echo ""
echo "🟢 Installing Node.js dependencies..."
cd ../..
npm ci

echo ""
echo "🪝 Setting up pre-commit hooks..."
# Install pre-commit from the project root (where .git is)
pre-commit install
# Update pre-commit hooks to latest versions
pre-commit autoupdate

echo ""
echo "✅ Local Development Environment Setup Complete!"
echo ""

echo "🧪 **Local Quality Check Commands:**"
echo ""
echo "📁 Python (run from apps/api/):"
echo "  source venv/bin/activate"
echo "  mypy src --strict --show-error-codes"
echo "  black src tests --check --line-length=88"
echo "  flake8 src --max-line-length=88 --max-complexity=10"
echo "  pytest --cov=src --cov-report=term-missing --cov-fail-under=80"
echo ""

echo "📁 TypeScript/Prettier (run from root):"
echo "  npm run type-check:all"
echo "  npm run quality:typescript"
echo "  npm run format:check"
echo "  npm run format:write  # to fix formatting issues"
echo ""

echo "🚀 **Quick Quality Check (All):**"
echo "  ./scripts/check-quality-local.sh"
echo ""

echo "⚙️  **Pre-commit hooks are now active:**"
echo "  - Quality checks run automatically on git commit"
echo "  - Prevents commits with quality issues"
echo "  - Matches exactly what CI checks"
echo ""

echo "🎯 **Workflow:**"
echo "1. Make your changes"
echo "2. Run quality checks locally (or let pre-commit handle it)"
echo "3. Fix any issues before committing"
echo "4. Push clean, working code to CI"
echo "5. CI should pass on first try! 🎉"
echo ""

echo "💡 **Why This Matters:**"
echo "✅ Catch issues locally before wasting CI minutes"
echo "✅ Faster development feedback loop"
echo "✅ Clean git history without 'fix formatting' commits"
echo "✅ Consistent code quality across team"
echo "✅ No more CI failures from silly formatting issues"
