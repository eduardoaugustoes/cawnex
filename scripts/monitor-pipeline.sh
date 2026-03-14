#!/bin/bash
# Monitor GitHub Actions pipeline with exponential backoff

set -e

echo "🔍 Monitoring GitHub Actions pipeline with exponential backoff..."

INITIAL_DELAY=10
MAX_DELAY=120
DELAY=$INITIAL_DELAY
MAX_ATTEMPTS=30
ATTEMPT=1

check_latest_runs() {
    echo "📊 Checking latest workflow runs (attempt $ATTEMPT/$MAX_ATTEMPTS)..."

    # Get the latest runs for the consolidated workflow
    MAIN_PIPELINE=$(gh run list --workflow="🚀 Main CI/CD Pipeline" --limit 1 --json status,conclusion --jq '.[0].conclusion // .[0].status')
    UTILITIES=$(gh run list --workflow="🔧 Utilities & Manual Operations" --limit 1 --json status,conclusion --jq '.[0].conclusion // .[0].status' 2>/dev/null || echo "none")

    echo "  🚀 Main Pipeline: $MAIN_PIPELINE"
    echo "  🔧 Utilities: $UTILITIES"

    # Check if main pipeline completed successfully
    if [ "$MAIN_PIPELINE" = "success" ]; then
        echo "✅ MAIN PIPELINE COMPLETED SUCCESSFULLY!"
        echo ""
        echo "🎉 Pipeline is fully operational:"
        echo "  ✅ Quality Gate: PASSED"
        echo "  ✅ Deploy Dev: PASSED"
        echo ""
        return 0
    fi

    # Check if main pipeline failed
    if [ "$MAIN_PIPELINE" = "failure" ]; then
        echo "❌ MAIN PIPELINE FAILURE DETECTED!"
        echo ""
        echo "Failed workflow:"
        echo "  ❌ Main Pipeline: FAILED"
        echo ""
        echo "🔍 Checking logs for details..."

        # Show recent failed runs
        gh run list --limit 3 --json status,conclusion,name,url
        return 1
    fi

    # Still in progress
    echo "⏳ Main pipeline still running..."
    if [ "$MAIN_PIPELINE" = "in_progress" ] || [ "$MAIN_PIPELINE" = "queued" ] || [ -z "$MAIN_PIPELINE" ]; then
        echo "  🔄 Main Pipeline: IN PROGRESS"
    fi

    return 2  # Still waiting
}

# Monitor with exponential backoff
while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    check_latest_runs
    STATUS=$?

    if [ $STATUS -eq 0 ]; then
        # Success - exit with success
        echo "🚀 Pipeline monitoring completed successfully!"
        exit 0
    elif [ $STATUS -eq 1 ]; then
        # Failure - exit with error
        echo "💥 Pipeline failed - manual intervention required"
        exit 1
    else
        # Still waiting - continue with backoff
        if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
            echo "⏰ Maximum attempts reached - pipeline may still be running"
            echo "Check manually: https://github.com/eduardoaugustoes/cawnex/actions"
            exit 2
        fi

        echo "⏳ Waiting ${DELAY}s before next check..."
        sleep $DELAY

        # Exponential backoff with jitter
        DELAY=$((DELAY * 2))
        if [ $DELAY -gt $MAX_DELAY ]; then
            DELAY=$MAX_DELAY
        fi

        ATTEMPT=$((ATTEMPT + 1))
        echo ""
    fi
done
