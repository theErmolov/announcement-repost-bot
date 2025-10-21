# Telegram Forwarder Bot for AWS Lambda (ZIP Deployment)

This project implements a simple Telegram bot that forwards all messages it receives to a designated chat.

The bot is designed to be deployed as an AWS Lambda function (packaged as a ZIP archive) via AWS SAM (Serverless Application Model) and uses GitHub Actions for CI/CD.

## Features

*   Forwards all incoming messages to a specified Telegram chat.
*   Serverless deployment on AWS Lambda using ZIP packaging.
*   Automated build and deployment using GitHub Actions.
*   Secure handling of secrets and webhook verification.

## Architecture Overview

1.  A user sends a message to the bot or a group where the bot is a member.
2.  Telegram sends an update to a configured webhook.
3.  The webhook URL points to an **AWS API Gateway** endpoint.
4.  API Gateway triggers the **AWS Lambda function**.
5.  The Lambda function (Python code in `src/`, packaged as a ZIP) processes the update and forwards the message.
6.  **GitHub Actions** are used for CI/CD. Pushing to the `main` branch automatically builds the ZIP package, uploads it to an S3 bucket, and deploys the application using AWS SAM.

## Prerequisites

*   **AWS Account:** To host the Lambda function, API Gateway, and an S3 bucket for deployments.
*   **Telegram Bot:** Create a bot using [BotFather](https://core.telegram.org/bots#botfather) on Telegram to get a `TELEGRAM_BOT_TOKEN`.
*   **AWS SAM CLI:** (Optional, for local development/manual deployment) [Install SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html).
*   **Docker:** (Optional, but recommended for local testing with SAM) [Install Docker](https://docs.docker.com/get-docker/).
*   **GitHub Account:** To host the repository and use GitHub Actions.

## Setup and Deployment

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd <repository-name>
```

### 2. Create S3 Bucket for SAM Deployments

AWS SAM needs an S3 bucket to store the packaged Lambda code (ZIP file) before deploying it with CloudFormation.
*   Create an S3 bucket in your AWS account, in the **same AWS region** where you intend to deploy the Lambda function (e.g., `us-east-1`).
*   Choose a globally unique name for your bucket (e.g., `your-name-sam-deployments`).
*   Ensure the IAM Role used by GitHub Actions (see step 4) has `s3:PutObject` and `s3:GetObject` permissions for this bucket.

### 3. Configure GitHub Repository Variables

Navigate to your GitHub repository's `Settings` > `Secrets and variables` > `Actions`. Under the "Variables" tab, add the following:

*   `AWS_REGION`: The AWS region where resources will be deployed (e.g., `us-east-1`).
*   `SAM_CLI_S3_BUCKET`: The name of the S3 bucket you created in the previous step.
*   `FORWARD_CHAT_ID`: The ID of the Telegram chat where messages should be forwarded (e.g., `-1001234567890` or `@channelusername`).

### 4. Configure GitHub Secrets

Navigate to your GitHub repository's `Settings` > `Secrets and variables` > `Actions`. Under the "Secrets" tab, add the following:

*   `AWS_IAM_ROLE_FOR_GITHUB_ACTIONS`: The ARN of the IAM Role that GitHub Actions will assume to deploy to AWS.
*   `TELEGRAM_BOT_TOKEN`: Your Telegram bot token obtained from BotFather.
*   `TELEGRAM_WEBHOOK_SECRET_TOKEN`: A strong, random string used to verify webhook requests.

### 5. IAM Role for GitHub Actions (OIDC)

Create an IAM role in your AWS account that GitHub Actions can assume.
*   **Trusted entity type**: Select "Web identity".
*   **Identity provider**: Choose "GitHub".
*   **Audience**: `sts.amazonaws.com`.
*   **GitHub organization/repository/username**: Specify your GitHub details to restrict which workflows can assume this role.
*   **Permissions**: Attach policies that grant necessary permissions for SAM deployments. This includes permissions for CloudFormation, Lambda, API Gateway, IAM (to pass roles), and S3.

Store the ARN of this role in the `AWS_IAM_ROLE_FOR_GITHUB_ACTIONS` GitHub secret.

### 6. Deployment via GitHub Actions

Once the S3 bucket, variables, secrets, and IAM role are configured, committing and pushing changes to the `main` branch will automatically trigger the GitHub Actions workflow.

### 7. Set the Webhook with Telegram

After the first successful deployment, use the `TelegramBotApiEndpoint` output from the SAM deployment to set your Telegram webhook:
`https_waf_url/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook?url=<API_GATEWAY_ENDPOINT>&secret_token=<WEBHOOK_SECRET_TOKEN>`

Replace placeholders accordingly.

Your bot is now live!

## Project Structure

```
.
├── .github/workflows/deploy.yml
├── src/
│   ├── lambda_function.py
│   ├── main.py
│   └── requirements.txt
├── template.yaml
├── README.md
└── .gitignore
```

## Security Notes

*   **Secrets:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET_TOKEN`, and `AWS_IAM_ROLE_FOR_GITHUB_ACTIONS` must be kept as GitHub Secrets.
*   **Variables:** `AWS_REGION`, `SAM_CLI_S3_BUCKET`, and `FORWARD_CHAT_ID` are configured as GitHub Repository Variables.
*   **Webhook Verification:** The bot uses a `TELEGRAM_WEBHOOK_SECRET_TOKEN` for security.
*   **IAM Permissions:** Follow the principle of least privilege.
