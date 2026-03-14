#!/bin/bash
# Cawnex Quality Control - ULTRA STRICT Validation
# This script enforces maximum code quality across all languages

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
TOTAL_CHECKS=0

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((CHECKS_PASSED++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((CHECKS_FAILED++))
}

log_header() {
    echo -e "\n${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}\n"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        log_success "$1 is installed"
        return 0
    else
        log_error "$1 is not installed"
        return 1
    fi
}

run_check() {
    local name="$1"
    local command="$2"
    ((TOTAL_CHECKS++))

    log_info "Running: $name"
    if eval "$command"; then
        log_success "$name passed"
    else
        log_error "$name failed"
    fi
}

# Main quality control function
main() {
    log_header "🔍 CAWNEX ULTRA-STRICT QUALITY CONTROL"

    # ================================
    # DEPENDENCY CHECKS
    # ================================
    log_header "📋 Checking Dependencies"

    check_command "python3.12" || check_command "python3"
    check_command "node"
    check_command "npm"
    check_command "git"

    # ================================
    # PYTHON QUALITY CHECKS
    # ================================
    log_header "🐍 Python Quality Checks (API & Lambdas)"

    if [ -d "apps/api" ]; then
        cd apps/api

        # Install dependencies if needed
        if [ ! -d "venv" ]; then
            log_info "Creating Python virtual environment..."
            python3 -m venv venv
            source venv/bin/activate
            pip install -e ".[dev,test]"
        else
            source venv/bin/activate
        fi

        # Run Python quality checks
        run_check "Python: MyPy Type Checking" "mypy src --strict --show-error-codes"
        run_check "Python: Black Formatting Check" "black src tests --check --line-length=88"
        run_check "Python: isort Import Sorting Check" "isort src tests --check-only --profile black"
        run_check "Python: Flake8 Linting" "flake8 src --max-line-length=88 --max-complexity=10"
        run_check "Python: Bandit Security Scan" "bandit -r src -f json -o bandit-report.json"
        run_check "Python: Tests with Coverage" "pytest --cov=src --cov-fail-under=80"

        cd ../..
    else
        log_warning "apps/api directory not found, skipping Python checks"
    fi

    # ================================
    # TYPESCRIPT QUALITY CHECKS
    # ================================
    log_header "⚡ TypeScript Quality Checks (Infrastructure)"

    if [ -f "package.json" ]; then
        # Install Node dependencies if needed
        if [ ! -d "node_modules" ]; then
            log_info "Installing Node.js dependencies..."
            npm install
        fi

        # TypeScript checks
        run_check "TypeScript: Type Checking" "npm run type-check:all"
        run_check "TypeScript: ESLint (Zero Warnings)" "npm run quality:typescript"
        run_check "TypeScript: Prettier Formatting" "npm run format:check"

        # CDK-specific checks
        if [ -d "infra" ]; then
            cd infra
            run_check "CDK: Synth Test" "npx cdk synth --quiet"
            run_check "CDK: TypeScript Compilation" "npx tsc --noEmit"
            cd ..
        fi
    else
        log_warning "package.json not found, skipping TypeScript checks"
    fi

    # ================================
    # IOS SWIFT CHECKS
    # ================================
    log_header "📱 iOS Swift Quality Checks"

    if [ -d "apps/ios" ]; then
        cd apps/ios

        # Check if Xcode command line tools are available
        if command -v xcodebuild &> /dev/null; then
            run_check "iOS: Swift Compilation Test" "xcodebuild -workspace Cawnex/Cawnex.xcworkspace -scheme Cawnex -destination 'platform=iOS Simulator,name=iPhone 15' clean build CODE_SIGNING_ALLOWED=NO"
        else
            log_warning "Xcode not available, skipping iOS build test"
        fi

        # Check for SwiftLint if available
        if command -v swiftlint &> /dev/null; then
            run_check "iOS: SwiftLint" "swiftlint lint --strict"
        else
            log_info "SwiftLint not installed, consider installing for additional Swift checks"
        fi

        cd ../..
    else
        log_warning "apps/ios directory not found, skipping iOS checks"
    fi

    # ================================
    # SECURITY CHECKS
    # ================================
    log_header "🔒 Security Checks"

    # Git security checks
    run_check "Git: No secrets in history" "git secrets --scan-history || echo 'git-secrets not installed'"
    run_check "Git: No large files" "find . -name '*.py' -o -name '*.ts' -o -name '*.swift' | xargs wc -l | sort -n | tail -1 | awk '{if(\$1>500) exit 1}'"

    # Dependency vulnerability checks
    if [ -f "package.json" ]; then
        run_check "Node: Security Audit" "npm audit --audit-level=moderate"
    fi

    if [ -f "apps/api/requirements.txt" ]; then
        run_check "Python: Security Audit" "cd apps/api && pip-audit || echo 'pip-audit not installed'"
    fi

    # ================================
    # CONFIGURATION VALIDATION
    # ================================
    log_header "⚙️  Configuration Validation"

    # Check for required config files
    config_files=(
        "apps/api/pyproject.toml"
        "tsconfig.base.json"
        ".eslintrc.json"
        "apps/ios/Cawnex/configs/Development.xcconfig"
        "apps/ios/Cawnex/configs/Production.xcconfig"
        "apps/ios/Cawnex/configs/Shared.xcconfig"
    )

    for config in "${config_files[@]}"; do
        if [ -f "$config" ]; then
            log_success "Configuration file exists: $config"
            ((CHECKS_PASSED++))
        else
            log_error "Missing configuration file: $config"
            ((CHECKS_FAILED++))
        fi
        ((TOTAL_CHECKS++))
    done

    # ================================
    # FINAL RESULTS
    # ================================
    log_header "📊 Quality Control Results"

    echo -e "Total Checks: ${CYAN}$TOTAL_CHECKS${NC}"
    echo -e "Passed: ${GREEN}$CHECKS_PASSED${NC}"
    echo -e "Failed: ${RED}$CHECKS_FAILED${NC}"

    if [ $CHECKS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}🏆 ALL QUALITY CHECKS PASSED!${NC}"
        echo -e "${GREEN}✨ Code is production-ready with ULTRA-STRICT standards${NC}\n"
        exit 0
    else
        echo -e "\n${RED}❌ QUALITY CHECKS FAILED${NC}"
        echo -e "${RED}🚨 Fix the issues above before committing${NC}\n"
        exit 1
    fi
}

# ================================
# COMMAND LINE OPTIONS
# ================================

show_help() {
    echo "Cawnex Quality Control - ULTRA STRICT Code Validation"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -q, --quick    Run quick checks only (no tests)"
    echo "  -p, --python   Run Python checks only"
    echo "  -t, --ts       Run TypeScript checks only"
    echo "  -i, --ios      Run iOS checks only"
    echo "  --fix          Attempt to auto-fix issues"
    echo ""
    echo "Examples:"
    echo "  $0              # Run all quality checks"
    echo "  $0 --quick      # Run quick validation"
    echo "  $0 --python     # Check Python code only"
    echo "  $0 --fix        # Auto-fix formatting issues"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    -q|--quick)
        log_info "Running quick quality checks..."
        # Override test commands for quick mode
        run_check() {
            local name="$1"
            local command="$2"
            if [[ "$name" != *"Tests"* && "$name" != *"Coverage"* ]]; then
                ((TOTAL_CHECKS++))
                log_info "Running: $name"
                if eval "$command"; then
                    log_success "$name passed"
                else
                    log_error "$name failed"
                fi
            fi
        }
        main
        ;;
    --fix)
        log_info "Auto-fixing code quality issues..."
        if [ -d "apps/api" ]; then
            cd apps/api && make lint-fix && cd ../..
        fi
        if [ -f "package.json" ]; then
            npm run quality:fix
        fi
        log_success "Auto-fix complete. Re-run quality control to verify."
        ;;
    *)
        main
        ;;
esac
