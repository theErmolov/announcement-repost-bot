# Telegram Announcer Bot for AWS Lambda (ZIP Deployment)

This project implements a Telegram bot that listens to messages in a group chat. When a message from an authorized user contains the hashtag "#анонс", the bot reposts that message to a specified Telegram channel.

The bot is designed to be deployed as an AWS Lambda function (packaged as a ZIP archive) via AWS SAM (Serverless Application Model) and uses GitHub Actions for CI/CD.

## Features

*   Reposts messages containing a specific keyword (`#анонс`) from authorized users.
*   Forwards messages to a designated Telegram channel.
*   Serverless deployment on AWS Lambda using ZIP packaging.
*   Automated build and deployment using GitHub Actions.
*   Secure handling of secrets and webhook verification.

## Bot Behavior

The bot processes messages based on their content and type:

1.  **Text Messages with Keywords:**
    *   If an authorized user sends a text message (that is not a poll) containing a recognized keyword (e.g., `#анонс`, `#опрос`):
        *   The bot will copy the full text of the user's message and post it as a new message to the configured `TARGET_CHANNEL_ID`.
        *   Details of this announcement (message ID, text content, and timestamp) are temporarily stored in memory, associated with the user. This is intended for a short-term memory to potentially link a subsequent poll.

2.  **Poll Objects from Users:**
    *   If an authorized user sends a poll object to the bot:
        *   **Age Check:** The bot first checks if the user's original poll message is older than 1 hour. If so, it's ignored.
        *   **Retrieve Last Announcement:** The bot attempts to retrieve the details of the last text announcement it posted (triggered by the same user) from its in-memory storage.
        *   **Conditions for Editing:**
            *   If a last announcement is found and its stored timestamp is recent (e.g., within the last hour), the bot proceeds to edit that announcement.
            *   If no recent announcement is found in memory for this user, the bot will do nothing further with the poll.
        *   **Editing Process (if conditions met):**
            *   A link to the user's current poll object is generated.
            *   A "Проголосуй..." prompt string is chosen based on keywords (`#анонс` or `#опрос`) found in the caption of the user's current poll. It defaults to the `#анонс` style.
            *   The bot takes the text of its previously posted announcement message.
            *   It attempts to remove any older "Проголосуй..." string that might already be appended to that announcement.
            *   The new "Проголосуй..." prompt (with the link to the current user's poll) is then appended to the announcement text.
            *   The original announcement message in the `TARGET_CHANNEL_ID` is edited with this updated text.
            *   The temporarily stored announcement details are then cleared from memory.
    *   **Note on In-Memory Storage:** The reliability of remembering the "last announcement" in a stateless environment like AWS Lambda is not guaranteed. This editing feature for polls will only work if the poll message is processed by the same warm Lambda instance very shortly after the text announcement.

3.  **Other Messages:** Messages from unauthorized users, or messages from authorized users that do not meet the above criteria, are generally ignored.

## Architecture Overview

1.  A user posts a message in the source Telegram chat.
2.  If the bot is added to the chat, Telegram sends an update to a configured webhook.
3.  The webhook URL points to an **AWS API Gateway** endpoint.
4.  API Gateway triggers the **AWS Lambda function**.
5.  The Lambda function (Python code in `src/`, packaged as a ZIP) processes the update.
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
*   `AUTHORIZED_USER_IDS`: A comma-separated list of Telegram user IDs who are authorized to trigger announcements (e.g., `123456789,987654321`).
*   `TARGET_CHANNEL_ID`: The ID of the Telegram channel where announcements should be reposted (e.g., `-1001234567890` or `@channelusername`).

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
*   **Variables:** `AWS_REGION`, `SAM_CLI_S3_BUCKET`, `AUTHORIZED_USER_IDS`, and `TARGET_CHANNEL_ID` are configured as GitHub Repository Variables.
*   **Webhook Verification:** The bot uses a `TELEGRAM_WEBHOOK_SECRET_TOKEN` for security.
*   **IAM Permissions:** Follow the principle of least privilege.
