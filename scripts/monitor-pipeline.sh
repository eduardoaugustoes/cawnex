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
    
    # Get the latest runs for each workflow
    QUALITY_GATE=$(gh run list --workflow="🔒 Ultra-Strict Quality Gate" --limit 1 --json status,conclusion --jq '.[0].conclusion // .[0].status')
    DEPLOY_DEV=$(gh run list --workflow="Deploy Dev Environment" --limit 1 --json status,conclusion --jq '.[0].conclusion // .[0].status')
    
    echo "  🔒 Quality Gate: $QUALITY_GATE"
    echo "  🚀 Deploy Dev: $DEPLOY_DEV"
    
    # Check if both workflows have completed successfully
    if [ "$QUALITY_GATE" = "success" ] && [ "$DEPLOY_DEV" = "success" ]; then
        echo "✅ ALL WORKFLOWS COMPLETED SUCCESSFULLY!"
        echo ""
        echo "🎉 Pipeline is fully operational:"
        echo "  ✅ Quality Gate: PASSED"
        echo "  ✅ Deploy Dev: PASSED"
        echo ""
        return 0
    fi
    
    # Check if any workflow failed
    if [ "$QUALITY_GATE" = "failure" ] || [ "$DEPLOY_DEV" = "failure" ]; then
        echo "❌ WORKFLOW FAILURE DETECTED!"
        echo ""
        echo "Failed workflows:"
        [ "$QUALITY_GATE" = "failure" ] && echo "  ❌ Quality Gate: FAILED"
        [ "$DEPLOY_DEV" = "failure" ] && echo "  ❌ Deploy Dev: FAILED"
        echo ""
        echo "🔍 Checking logs for details..."
        
        # Show recent failed runs
        gh run list --limit 5 --json status,conclusion,name,url
        return 1
    fi
    
    # Still in progress
    echo "⏳ Workflows still running..."
    if [ "$QUALITY_GATE" = "in_progress" ]; then
        echo "  🔄 Quality Gate: IN PROGRESS"
    fi
    if [ "$DEPLOY_DEV" = "in_progress" ]; then
        echo "  🔄 Deploy Dev: IN PROGRESS"
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