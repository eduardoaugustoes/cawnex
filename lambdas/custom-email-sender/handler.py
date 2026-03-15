"""
Custom Email Sender Lambda for Cawnex.

Replaces Cognito's default email templates with branded HTML emails.
Triggers on Cognito events and sends custom emails via SES.

Environment variables:
  DOMAIN_NAME     — Email domain (e.g., cawnex.ai)
  CONFIG_SET_NAME — SES configuration set name
  STAGE           — dev | staging | prod
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses_client = boto3.client('ses', region_name='us-east-1')


def load_template(template_name: str) -> str:
    """Load HTML email template from templates directory."""
    template_path = Path(__file__).parent / "templates" / f"{template_name}.html"
    try:
        return template_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"Template not found: {template_name}")
        raise


def replace_template_vars(template: str, variables: Dict[str, str]) -> str:
    """Replace template variables with actual values."""
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        template = template.replace(placeholder, str(value))
    return template


def send_email_via_ses(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    from_email: Optional[str] = None
) -> bool:
    """Send email via SES with error handling."""
    domain_name = os.environ.get('DOMAIN_NAME', 'cawnex.ai')
    config_set = os.environ.get('CONFIG_SET_NAME')

    if not from_email:
        from_email = f"Cawnex <noreply@{domain_name}>"

    try:
        kwargs = {
            'Source': from_email,
            'Destination': {'ToAddresses': [to_email]},
            'Message': {
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {'Html': {'Data': html_body, 'Charset': 'UTF-8'}}
            }
        }

        # Add text body if provided
        if text_body:
            kwargs['Message']['Body']['Text'] = {'Data': text_body, 'Charset': 'UTF-8'}

        # Add configuration set if specified
        if config_set:
            kwargs['ConfigurationSetName'] = config_set

        response = ses_client.send_email(**kwargs)
        logger.info(f"Email sent successfully to {to_email}, MessageId: {response['MessageId']}")
        return True

    except ClientError as e:
        logger.error(f"Failed to send email to {to_email}: {e.response['Error']['Message']}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email to {to_email}: {str(e)}")
        return False


def extract_user_attributes(event: Dict[str, Any]) -> Dict[str, str]:
    """Extract user attributes from Cognito event."""
    user_attrs = event.get('request', {}).get('userAttributes', {})

    # Handle both dict format and list format
    if isinstance(user_attrs, list):
        attrs = {}
        for attr in user_attrs:
            attrs[attr.get('Name', '')] = attr.get('Value', '')
        user_attrs = attrs

    return {
        'user_email': user_attrs.get('email', ''),
        'user_name': user_attrs.get('name') or user_attrs.get('given_name') or user_attrs.get('email', '').split('@')[0],
        'user_given_name': user_attrs.get('given_name', ''),
        'user_family_name': user_attrs.get('family_name', ''),
        'tenant_id': user_attrs.get('custom:tenant_id', ''),
    }


def handle_verification_email(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle email verification during signup."""
    logger.info("Processing verification email")

    user_attrs = extract_user_attributes(event)
    code = event['request'].get('codeParameter', '')

    if not user_attrs['user_email'] or not code:
        logger.error("Missing email or verification code")
        return event

    # Load and customize template
    template = load_template('verification')
    html_body = replace_template_vars(template, {
        'verification_code': code,
        'user_name': user_attrs['user_name'],
        'user_email': user_attrs['user_email']
    })

    # Send via SES
    success = send_email_via_ses(
        to_email=user_attrs['user_email'],
        subject="🔐 Verify your Cawnex account",
        html_body=html_body,
        text_body=f"Welcome to Cawnex! Your verification code is: {code}. This code expires in 24 hours."
    )

    if success:
        # Suppress Cognito's default email by clearing the response
        event['response']['emailSubject'] = ""
        event['response']['emailMessage'] = ""

    return event


def handle_password_reset_email(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle password reset email."""
    logger.info("Processing password reset email")

    user_attrs = extract_user_attributes(event)
    code = event['request'].get('codeParameter', '')

    if not user_attrs['user_email'] or not code:
        logger.error("Missing email or reset code")
        return event

    # Load and customize template
    template = load_template('password-reset')
    html_body = replace_template_vars(template, {
        'reset_code': code,
        'user_name': user_attrs['user_name'],
        'user_email': user_attrs['user_email']
    })

    # Send via SES
    success = send_email_via_ses(
        to_email=user_attrs['user_email'],
        subject="🔐 Reset your Cawnex password",
        html_body=html_body,
        text_body=f"Reset your Cawnex password. Your temporary code is: {code}. This code expires in 1 hour."
    )

    if success:
        # Suppress Cognito's default email
        event['response']['emailSubject'] = ""
        event['response']['emailMessage'] = ""

    return event


def handle_welcome_email(event: Dict[str, Any]) -> None:
    """Send welcome email after user confirms signup (called from post-confirmation)."""
    logger.info("Processing welcome email")

    user_attrs = extract_user_attributes(event)

    if not user_attrs['user_email']:
        logger.error("Missing email for welcome message")
        return

    # Load and customize template
    template = load_template('welcome')
    html_body = replace_template_vars(template, {
        'user_name': user_attrs['user_name'],
        'user_email': user_attrs['user_email']
    })

    # Send via SES
    send_email_via_ses(
        to_email=user_attrs['user_email'],
        subject="🎉 Welcome to Cawnex - Start Building Autonomous Software",
        html_body=html_body,
        text_body=f"Welcome to Cawnex, {user_attrs['user_name']}! Your autonomous development platform is ready. Create your first project at https://app.cawnex.ai/projects/new"
    )


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for custom email sending."""
    logger.info(f"Received event: {json.dumps(event, default=str)}")

    trigger_source = event.get('triggerSource', '')

    try:
        if trigger_source == 'CustomMessage_SignUp':
            # Email verification during signup
            return handle_verification_email(event)

        elif trigger_source == 'CustomMessage_ForgotPassword':
            # Password reset email
            return handle_password_reset_email(event)

        elif trigger_source == 'CustomMessage_ResendCode':
            # Resend verification code
            return handle_verification_email(event)

        elif trigger_source == 'CustomMessage_UpdateUserAttribute':
            # Email verification for attribute updates
            return handle_verification_email(event)

        elif trigger_source == 'CustomMessage_AdminCreateUser':
            # Admin created user - send invitation email
            return handle_verification_email(event)

        else:
            logger.info(f"Unhandled trigger source: {trigger_source}")
            return event

    except Exception as e:
        logger.error(f"Error processing email trigger {trigger_source}: {str(e)}")
        # Return original event to allow Cognito fallback
        return event


def send_welcome_email_direct(user_email: str, user_name: str, tenant_id: str) -> bool:
    """
    Direct function to send welcome email (for post-confirmation trigger).
    This is called from the post-confirmation Lambda.
    """
    try:
        template = load_template('welcome')
        html_body = replace_template_vars(template, {
            'user_name': user_name,
            'user_email': user_email
        })

        return send_email_via_ses(
            to_email=user_email,
            subject="🎉 Welcome to Cawnex - Start Building Autonomous Software",
            html_body=html_body,
            text_body=f"Welcome to Cawnex, {user_name}! Your autonomous development platform is ready. Create your first project at https://app.cawnex.ai/projects/new"
        )
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        return False


# For testing purposes
if __name__ == "__main__":
    # Test template loading
    test_template = load_template('verification')
    print(f"Template loaded: {len(test_template)} characters")

    # Test variable replacement
    test_vars = {
        'verification_code': '123456',
        'user_name': 'John Doe',
        'user_email': 'john@example.com'
    }
    result = replace_template_vars(test_template, test_vars)
    print(f"Variables replaced: {len(result)} characters")
