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

# Create the new configuration block
NEW_CONFIG="    static let $STAGE = AppConfiguration(
        cognitoRegion: \"us-east-1\",
        cognitoUserPoolId: \"$USER_POOL_ID\",
        cognitoClientId: \"$IOS_CLIENT_ID\",
        apiBaseUrl: \"$API_URL\"
    )"

# Determine the start marker for the stage
START_MARKER="static let $STAGE = AppConfiguration("

# Create a temporary file for the updated configuration
TEMP_FILE=$(mktemp)

# Process the file
awk -v stage="$STAGE" -v new_config="$NEW_CONFIG" '
BEGIN { in_block = 0; found = 0 }
/static let '"$STAGE"' = AppConfiguration\(/ {
    print new_config
    in_block = 1
    found = 1
    next
}
in_block && /^    \)/ {
    in_block = 0
    next
}
!in_block {
    print
}
END {
    if (!found) {
        print "❌ Could not find " stage " configuration block to update" > "/dev/stderr"
        exit 1
    }
}
' "$CONFIG_FILE" > "$TEMP_FILE"

# Check if awk succeeded
if [ $? -ne 0 ]; then
    echo "❌ Failed to update configuration"
    rm "$TEMP_FILE"
    exit 1
fi

# Replace the original file
mv "$TEMP_FILE" "$CONFIG_FILE"

echo "✅ Updated $CONFIG_FILE"
echo ""
echo "🎉 iOS app is now configured for $STAGE environment!"
echo ""
echo "Next steps:"
echo "1. Open the iOS project in Xcode"
echo "2. Build and run the app"
echo "3. The app will now connect to the deployed $STAGE infrastructure"
echo ""
echo "To restore the original configuration:"
echo "   cp ${CONFIG_FILE}.backup $CONFIG_FILE"

# Additional verification for GitHub Actions
if [ "$FROM_ENV" = "--from-env" ]; then
    echo ""
    echo "✅ Configuration updated from environment variables:"
    echo "   UserPoolId: $USER_POOL_ID"
    echo "   iOSClientId: $IOS_CLIENT_ID" 
    echo "   ApiUrl: $API_URL"
fi