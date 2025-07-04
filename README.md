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
        *   Details of this announcement (message ID, text content, and timestamp) are temporarily stored associated with the user (using `context.user_data`). This is intended for a short-term memory to potentially link a subsequent poll.

2.  **Poll Objects from Users:**
    *   If an authorized user sends a poll object to the bot:
        *   **Age Check:** The bot first checks if the user's original poll message is older than 1 hour. If so, it's ignored.
        *   **Retrieve Last Announcement:** The bot attempts to retrieve the details of the last text announcement it posted (triggered by the same user) from its temporary memory (`context.user_data`).
        *   **Conditions for Editing:**
            *   If a last announcement is found and its stored timestamp is recent (e.g., within the last 10 minutes, configurable in code), the bot proceeds to edit that announcement.
            *   If no recent announcement is found in memory for this user, the bot will currently do nothing further with the poll (as per the requirement not to post a new, unlinked poll prompt).
        *   **Editing Process (if conditions met):**
            *   A link to the user's current poll object is generated.
            *   A "Проголосуй..." prompt string is chosen based on keywords (`#анонс` or `#опрос`) found in the caption of the user's current poll. It defaults to the `#анонс` style.
            *   The bot takes the text of its previously posted announcement message.
            *   It attempts to remove any older "Проголосуй..." string that might already be appended to that announcement.
            *   The new "Проголосуй..." prompt (with the link to the current user's poll) is then appended to the announcement text.
            *   The original announcement message in the `TARGET_CHANNEL_ID` is edited with this updated text.
            *   The temporarily stored announcement details are then cleared.
    *   **Note on `user_data` Persistence:** The reliability of remembering the "last announcement" in a stateless environment like AWS Lambda (without explicit persistence configured for `user_data`) means this editing feature for polls might only work if the poll message is processed by the same warm Lambda instance very shortly after the text announcement.

3.  **Other Messages:** Messages from unauthorized users, or messages from authorized users that do not meet the above criteria (e.g., no keyword, not a poll when poll logic is active), are generally ignored.

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
*   Ensure the IAM Role used by GitHub Actions (see step 5) has `s3:PutObject` and `s3:GetObject` permissions for this bucket (e.g., for `arn:aws:s3:::your-bucket-name/*`).

### 3. Configure GitHub Repository Variables

Navigate to your GitHub repository's `Settings` > `Secrets and variables` > `Actions`. Under the "Variables" tab (or "Configuration variables"), add the following:

*   `AWS_REGION`: The AWS region where resources will be deployed (e.g., `us-east-1`). This must match the region of your S3 bucket.
*   `SAM_CLI_S3_BUCKET`: The name of the S3 bucket you created in the previous step for SAM deployments.
*   `AUTHORIZED_USER_IDS`: A comma-separated list of Telegram user IDs who are authorized to trigger announcements (e.g., `123456789,987654321`).
*   `TARGET_CHANNEL_ID`: The ID of the Telegram channel where announcements should be reposted (e.g., `-1001234567890` for a public/private channel, or `@channelusername`).

### 4. Configure GitHub Secrets

Navigate to your GitHub repository's `Settings` > `Secrets and variables` > `Actions`. Under the "Secrets" tab, add the following:

*   `AWS_IAM_ROLE_FOR_GITHUB_ACTIONS`: The ARN of the IAM Role that GitHub Actions will assume to deploy to AWS.
*   `TELEGRAM_BOT_TOKEN`: Your Telegram bot token obtained from BotFather.
*   `TELEGRAM_WEBHOOK_SECRET_TOKEN`: A strong, random string used to verify webhook requests.

### 5. IAM Role for GitHub Actions (OIDC)

Create an IAM role in your AWS account that GitHub Actions can assume.
*   **Trusted entity type**: Select "Web identity".
*   **Identity provider**: Choose "GitHub" (or add it manually if not listed: Provider URL `https://token.actions.githubusercontent.com`, Audience `sts.amazonaws.com`).
*   **Audience**: `sts.amazonaws.com`.
*   **GitHub organization/repository/username**: Specify your GitHub details to restrict which workflows can assume this role.
*   **Permissions**: Attach policies that grant necessary permissions for SAM deployments. This includes permissions for CloudFormation, Lambda, API Gateway, IAM (to pass roles), and **S3 (PutObject, GetObject for the SAM deployment bucket)**. Apply the principle of least privilege.

    *Note: The SAM template creates an IAM role for the Lambda function, which is why `CAPABILITY_IAM` is used during deployment.*

Store the ARN of this role in the `AWS_IAM_ROLE_FOR_GITHUB_ACTIONS` GitHub secret.

### 6. Deployment via GitHub Actions

Once the S3 bucket, variables, secrets, and IAM role are configured, committing and pushing changes to the `main` branch will automatically trigger the GitHub Actions workflow. This workflow will:
1.  Build the Lambda deployment package (ZIP file).
2.  Upload the package to your configured S3 bucket.
3.  Deploy the application stack using AWS SAM.

Check the "Actions" tab in your GitHub repository for deployment progress.

### 7. Set the Webhook with Telegram

After the first successful deployment, use the `TelegramBotApiEndpoint` output from the SAM deployment (found in GitHub Actions logs) to set your Telegram webhook:
`https_waf_url/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook?url=<API_GATEWAY_ENDPOINT>&secret_token=<WEBHOOK_SECRET_TOKEN>`

Replace placeholders:
*   `<YOUR_TELEGRAM_BOT_TOKEN>`: Your actual bot token (from GitHub Secrets).
*   `<API_GATEWAY_ENDPOINT>`: The `TelegramBotApiEndpoint` value.
*   `<WEBHOOK_SECRET_TOKEN>`: The same secret token you configured in GitHub Secrets.

Open this constructed URL in a web browser or use a tool like `curl`. Telegram should respond with `{"ok":true,"result":true,"description":"Webhook was set"}`.

Your bot is now live!

## Project Structure

```
.
├── .github/workflows/deploy.yml  # GitHub Actions CI/CD workflow
├── src/
│   ├── lambda_function.py        # AWS Lambda handler
│   ├── main.py                   # Core bot logic (message handling)
│   └── requirements.txt          # Python dependencies
├── template.yaml                 # AWS SAM template for infrastructure
├── README.md                     # This file
└── .gitignore
```

## Local Development & Testing (Optional)

1.  **Install AWS SAM CLI.**
2.  **Install Docker (Recommended for `sam local` commands).**
3.  **Configure AWS Credentials locally.**
4.  **Build (for ZIP package):**
    ```bash
    sam build
    ```
5.  **Deploy (guided, for ZIP package):**
    ```bash
    sam deploy --guided
    ```
    (This will prompt you for parameters, including the S3 bucket for deployment. For local testing, you can enter values directly. Note: if the stack creates IAM resources, you might need to add `--capabilities CAPABILITY_IAM` if deploying manually without `--guided` which handles this.)
6.  **Local Invocation (for `lambda_function.py`):**
    You can test the Lambda function locally using `sam local invoke`.

## Security Notes

*   **Secrets:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET_TOKEN`, and `AWS_IAM_ROLE_FOR_GITHUB_ACTIONS` must be kept as GitHub Secrets.
*   **Variables:** `AWS_REGION`, `SAM_CLI_S3_BUCKET`, `AUTHORIZED_USER_IDS`, and `TARGET_CHANNEL_ID` are configured as GitHub Repository/Organization Variables.
*   **Webhook Verification:** The bot uses a `TELEGRAM_WEBHOOK_SECRET_TOKEN` for security.
*   **IAM Permissions:** Follow the principle of least privilege.

## Code Style and Documentation

The codebase aims for clarity and readability, minimizing inline comments that merely restate what the code does.
- **Minimal Comments:** Comments are generally avoided unless they clarify non-obvious logic that cannot be made clear by the code itself.
- **README for Complexity:** More complex behaviors, architectural decisions, or known limitations (such as placeholder functions) are documented in this README file.
- **Commit Messages:** Detailed history of changes and the rationale behind them should be captured in commit messages.

## Known Limitations and Important Notes

*   **`find_bot_last_message_in_channel` Function (in `src/main.py`):**
    *   The current implementation of `find_bot_last_message_in_channel` is a **placeholder**. It logs a warning and returns `None`.
    *   This function is intended to find the last message posted by the bot in the target channel, which is crucial for the poll-linking feature (editing the bot's last announcement to add a poll link).
    *   **Action Required:** To enable the poll-linking functionality as described, this function needs to be replaced with a working implementation that can fetch recent messages from the target channel. This might involve:
        *   Using a specific method from the `python-telegram-bot` library if available and if the bot has sufficient permissions (e.g., admin rights in the channel).
        *   Making direct Telegram Bot API calls if the library does not directly support the required message fetching capability.
        *   Considering alternative strategies if direct fetching is not feasible (e.g., the bot remembering its own message IDs if it's guaranteed to be the only one posting or has a way to identify its messages).
    *   The current behavior means that when a user sends a poll, the bot will likely log that it couldn't find its last message and will not proceed to link the poll to any previous announcement.
