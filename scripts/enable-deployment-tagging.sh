#!/bin/bash
set -e

# Enable Deployment Tagging System - Caioo Pattern Implementation
echo "🏷️  Enabling Deployment Tagging System"
echo "======================================"
echo "This will implement the caioo pattern of tagging deployments"
echo "and comparing changes against the last deployed commit."
echo ""

cd "$(dirname "$0")/../.github/workflows/" || exit 1

echo "📊 Current workflows:"
ls -la *.yml

echo ""
echo "🎯 Benefits of Deployment Tagging:"
echo "  ✅ Compare changes against last DEPLOYED commit (not just previous commit)"
echo "  ✅ Accumulate changes from multiple commits between deployments"
echo "  ✅ Never miss changes from skipped doc-only deployments"
echo "  ✅ Full deployment history tracking with git tags"
echo "  ✅ Accurate time savings measurement"
echo "  ✅ Matches proven caioo pipeline pattern"

echo ""
echo "📝 How it works:"
echo "  1. After successful deployment, create tag: deploy-YYYYMMDD-HHMMSS"
echo "  2. Next pipeline run compares against that tag (not HEAD~1)"
echo "  3. Deploys all accumulated changes since last actual deployment"
echo "  4. Creates new tag after successful deployment"

echo ""
echo "📋 Current files:"
echo "  main-pipeline.yml              - Fixed but uses HEAD~1 comparison"
echo "  main-pipeline-with-tagging.yml - NEW: Uses deployment tags (caioo pattern)"
echo "  debug-pipeline.yml             - Debug/testing only"

echo ""
read -p "🔄 Switch to deployment tagging system? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 Switching to deployment tagging system..."

    # Backup current pipeline
    echo "📁 Backing up current pipeline..."
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    cp main-pipeline.yml "disabled/main-pipeline-pre-tagging-${TIMESTAMP}.yml"

    # Install the tagging pipeline
    echo "⚡ Installing deployment tagging pipeline..."
    cp main-pipeline-with-tagging.yml main-pipeline.yml

    # Clean up
    echo "🧹 Cleaning up..."
    rm main-pipeline-with-tagging.yml

    echo ""
    echo "✅ Deployment tagging system enabled!"
    echo ""
    echo "📊 What changed:"
    echo "  🔍 Change detection: HEAD~1 → last deployment tag"
    echo "  📈 Full git history: fetch-depth: 2 → fetch-depth: 0"
    echo "  🏷️ Tagging: Added tag-deployment job"
    echo "  📚 History: Deployment metadata in annotated tags"

    echo ""
    echo "🧪 Testing approach:"
    echo "  1. First deployment will create initial tag (no previous tag to compare)"
    echo "  2. Subsequent deploys will compare against the tag"
    echo "  3. Doc-only commits will accumulate until next code change"
    echo "  4. All accumulated changes will deploy together"

    echo ""
    echo "📁 Backup available at:"
    echo "  disabled/main-pipeline-pre-tagging-${TIMESTAMP}.yml"

    echo ""
    echo "🚀 Next steps:"
    echo "  1. git add . && git commit -m 'feat: enable deployment tagging system'"
    echo "  2. git push"
    echo "  3. Watch first deployment create initial tag"
    echo "  4. Test with docs + code changes to see accumulation"

    echo ""
    echo "🎯 Expected improvement:"
    echo "  - More robust change detection"
    echo "  - Better deployment history"
    echo "  - Matches caioo efficient pattern"
    echo "  - No missed changes between deployments"

else
    echo "❌ Keeping current pipeline"
    echo ""
    echo "💡 The tagging system is ready when you want to enable it:"
    echo "  ./scripts/enable-deployment-tagging.sh"
    echo ""
    echo "📚 Read more about the benefits:"
    echo "  docs/deployment-tagging-system.md"
fi

echo ""
echo "🔍 Deployment tag format:"
echo "  deploy-YYYYMMDD-HHMMSS (e.g. deploy-20260315-213045)"
echo "  Contains: deployment type, duration, changes included"

echo ""
echo "🏷️ View deployment history (after first tagged deployment):"
echo "  git tag --list 'deploy-*' --sort=-version:refname"
echo "  git show deploy-YYYYMMDD-HHMMSS  # Show deployment details"
