#!/bin/bash
# Update iOS configuration from deployed AWS stack

set -e

STAGE=${1:-dev}
FROM_ENV=${2}
CONFIG_FILE="apps/ios/Cawnex/Cawnex/Core/Config/AppConfiguration.swift"

echo "📱 Updating iOS configuration for $STAGE environment..."

# Check if the config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Get configuration values - either from environment or AWS CLI
if [ "$FROM_ENV" = "--from-env" ]; then
    echo "🔍 Using configuration from environment variables..."
    USER_POOL_ID="$CAWNEX_USER_POOL_ID"
    IOS_CLIENT_ID="$CAWNEX_IOS_CLIENT_ID"
    API_URL="$CAWNEX_API_URL"
else
    echo "🔍 Getting stack outputs from AWS..."

    # Check if AWS CLI is available
    if ! command -v aws &> /dev/null; then
        echo "❌ AWS CLI is required but not installed"
        exit 1
    fi

    # Get outputs from deployed stacks
    AUTH_STACK_NAME="CawnexAuthStack-$STAGE"
    MAIN_STACK_NAME="Cawnex-$STAGE"

    USER_POOL_ID=$(aws cloudformation describe-stacks \
        --stack-name "$AUTH_STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
        --output text)

    IOS_CLIENT_ID=$(aws cloudformation describe-stacks \
        --stack-name "$AUTH_STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`iOSClientId`].OutputValue' \
        --output text)

    API_URL=$(aws cloudformation describe-stacks \
        --stack-name "$MAIN_STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
        --output text)
fi

# Validate outputs
if [ -z "$USER_POOL_ID" ] || [ -z "$IOS_CLIENT_ID" ] || [ -z "$API_URL" ]; then
    echo "❌ Failed to get stack outputs. Is the stack deployed?"
    echo "   UserPoolId: $USER_POOL_ID"
    echo "   iOSClientId: $IOS_CLIENT_ID"
    echo "   ApiUrl: $API_URL"
    exit 1
fi

echo "✅ Retrieved configuration:"
echo "   UserPoolId: $USER_POOL_ID"
echo "   iOSClientId: $IOS_CLIENT_ID"
echo "   ApiUrl: $API_URL"

# Backup the original file
cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
echo "📋 Backed up original to ${CONFIG_FILE}.backup"

# Map stage to environment case
case $STAGE in
    dev|development)
        echo "🔄 Updating development environment configuration..."

        # Update development userPoolId
        sed -i 's|return ".*"  // Development User Pool|return "'"$USER_POOL_ID"'"  // Development User Pool|g' "$CONFIG_FILE"

        # Update development clientId
        sed -i 's|return ".*"  // Development iOS Client|return "'"$IOS_CLIENT_ID"'"  // Development iOS Client|g' "$CONFIG_FILE"

        # Update development apiBaseURL
        sed -i 's|return ".*"  // Development API|return "'"$API_URL"'"  // Development API|g' "$CONFIG_FILE"
        ;;
    staging)
        echo "🔄 Updating staging environment configuration..."

        # Update staging userPoolId (uses dev for now)
        sed -i 's|return ".*"  // Staging uses dev for now|return "'"$USER_POOL_ID"'"  // Staging uses dev for now|g' "$CONFIG_FILE"

        # Update staging clientId (uses dev for now)
        sed -i 's|return ".*"  // Staging uses dev for now|return "'"$IOS_CLIENT_ID"'"  // Staging uses dev for now|g' "$CONFIG_FILE"

        # Update staging apiBaseURL
        sed -i 's|return ".*"  // Staging API|return "'"$API_URL"'"  // Staging API|g' "$CONFIG_FILE"
        ;;
    prod|production)
        echo "🔄 Updating production environment configuration..."

        # Update production userPoolId
        sed -i 's|return ".*"  // Production User Pool|return "'"$USER_POOL_ID"'"  // Production User Pool|g' "$CONFIG_FILE"

        # Update production clientId
        sed -i 's|return ".*"  // Production iOS Client|return "'"$IOS_CLIENT_ID"'"  // Production iOS Client|g' "$CONFIG_FILE"

        # Update production apiBaseURL
        sed -i 's|return ".*"  // Production API|return "'"$API_URL"'"  // Production API|g' "$CONFIG_FILE"
        ;;
    *)
        echo "❌ Unknown stage: $STAGE"
        exit 1
        ;;
esac

# Validate that the updates were applied
if ! grep -q "$USER_POOL_ID" "$CONFIG_FILE"; then
    echo "❌ Failed to update User Pool ID"
    cp "${CONFIG_FILE}.backup" "$CONFIG_FILE"
    exit 1
fi

if ! grep -q "$IOS_CLIENT_ID" "$CONFIG_FILE"; then
    echo "❌ Failed to update iOS Client ID"
    cp "${CONFIG_FILE}.backup" "$CONFIG_FILE"
    exit 1
fi

if ! grep -q "$API_URL" "$CONFIG_FILE"; then
    echo "❌ Failed to update API URL"
    cp "${CONFIG_FILE}.backup" "$CONFIG_FILE"
    exit 1
fi

echo "✅ Updated $CONFIG_FILE for $STAGE environment"
echo ""
echo "🎉 iOS app is now configured for $STAGE environment!"

# Additional verification for GitHub Actions
if [ "$FROM_ENV" = "--from-env" ]; then
    echo ""
    echo "✅ Configuration updated from environment variables:"
    echo "   UserPoolId: $USER_POOL_ID"
    echo "   iOSClientId: $IOS_CLIENT_ID"
    echo "   ApiUrl: $API_URL"
fi
