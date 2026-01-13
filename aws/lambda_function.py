"""
AWS Lambda Function: EC2 Wake-Up Switch
========================================
This Lambda function starts a stopped EC2 instance when accessed via Function URL.

Environment Variables Required:
- EC2_INSTANCE_ID: The ID of the EC2 instance to control (e.g., i-0abc123def456789)
- MAIN_SITE_URL: The URL of your main Flask app (e.g., http://your-elastic-ip:5000)

IAM Permissions Required:
- ec2:StartInstances
- ec2:DescribeInstances
"""

import boto3
import os
import json

# Initialize EC2 client
ec2 = boto3.client('ec2')

# Get environment variables
INSTANCE_ID = os.environ.get('EC2_INSTANCE_ID')
MAIN_SITE_URL = os.environ.get('MAIN_SITE_URL', 'http://your-site-url.com')


def get_instance_state():
    """Get the current state of the EC2 instance."""
    try:
        response = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        return state
    except Exception as e:
        return f"error: {str(e)}"


def start_instance():
    """Start the EC2 instance."""
    try:
        ec2.start_instances(InstanceIds=[INSTANCE_ID])
        return True
    except Exception as e:
        return str(e)


def generate_html_response(title, message, status_class, show_refresh=False):
    """Generate a styled HTML response page."""
    
    refresh_button = ""
    if show_refresh:
        refresh_button = f'''
            <a href="{MAIN_SITE_URL}" class="btn">🚀 Go to Main Site</a>
            <p class="hint">Please wait ~2 minutes for the server to fully boot up.</p>
        '''
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
        }}
        
        .container {{
            text-align: center;
            padding: 3rem;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            max-width: 500px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }}
        
        .icon {{
            font-size: 4rem;
            margin-bottom: 1.5rem;
        }}
        
        .status-waking {{ color: #fbbf24; }}
        .status-running {{ color: #34d399; }}
        .status-error {{ color: #f87171; }}
        .status-stopped {{ color: #94a3b8; }}
        
        h1 {{
            font-size: 1.8rem;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .message {{
            color: #a5b4fc;
            line-height: 1.6;
            margin-bottom: 2rem;
        }}
        
        .btn {{
            display: inline-block;
            padding: 1rem 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 50px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }}
        
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.6);
        }}
        
        .hint {{
            margin-top: 1.5rem;
            font-size: 0.9rem;
            color: #6b7280;
        }}
        
        .loader {{
            width: 50px;
            height: 50px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 1.5rem auto;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon {status_class}">
            {"⏳" if status_class == "status-waking" else "✅" if status_class == "status-running" else "❌" if status_class == "status-error" else "💤"}
        </div>
        <h1>{title}</h1>
        <p class="message">{message}</p>
        {"<div class='loader'></div>" if status_class == "status-waking" else ""}
        {refresh_button}
    </div>
</body>
</html>'''
    
    return html


def lambda_handler(event, context):
    """
    Main Lambda handler for the Function URL.
    
    Checks EC2 instance status and starts it if stopped.
    Returns a user-friendly HTML page with status information.
    """
    
    # Validate environment variables
    if not INSTANCE_ID:
        html = generate_html_response(
            "Configuration Error",
            "EC2_INSTANCE_ID environment variable is not set. Please configure the Lambda function.",
            "status-error"
        )
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html'},
            'body': html
        }
    
    # Get current instance state
    state = get_instance_state()
    
    if state.startswith("error"):
        html = generate_html_response(
            "Error",
            f"Failed to check instance status: {state}",
            "status-error"
        )
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html'},
            'body': html
        }
    
    # Handle different instance states
    if state == 'stopped':
        # Start the instance
        result = start_instance()
        if result == True:
            html = generate_html_response(
                "🌅 Server is Waking Up!",
                "The transcription server was sleeping and is now starting up. This typically takes about 2 minutes.",
                "status-waking",
                show_refresh=True
            )
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'text/html'},
                'body': html
            }
        else:
            html = generate_html_response(
                "Failed to Start",
                f"Could not start the server: {result}",
                "status-error"
            )
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'text/html'},
                'body': html
            }
    
    elif state == 'running':
        html = generate_html_response(
            "✨ Server is Already Running!",
            "Great news! The transcription server is already up and running.",
            "status-running",
            show_refresh=True
        )
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/html'},
            'body': html
        }
    
    elif state == 'pending':
        html = generate_html_response(
            "⏳ Server is Starting...",
            "The server is currently starting up. Please wait a moment and refresh this page.",
            "status-waking",
            show_refresh=True
        )
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/html'},
            'body': html
        }
    
    elif state == 'stopping':
        html = generate_html_response(
            "🔄 Server is Shutting Down",
            "The server is currently stopping. Please wait a few minutes and try again.",
            "status-stopped",
            show_refresh=True
        )
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/html'},
            'body': html
        }
    
    else:
        html = generate_html_response(
            "Unknown State",
            f"The server is in an unexpected state: {state}",
            "status-error"
        )
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/html'},
            'body': html
        }
