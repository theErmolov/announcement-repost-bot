# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /var/task

# Copy the requirements file into the container at /var/task
COPY src/requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir ensures that pip doesn't store downloaded packages, reducing image size.
# --user installs packages into the user's home directory, which is good practice
#        for security and to avoid conflicts with system packages.
# However, for Lambda, it's often simpler to install into the system site-packages,
# as the image is ephemeral. Let's stick to a standard global install for Lambda.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code from the src directory into the container at /var/task
COPY src/ .

# Set the CMD to your handler function
# Format: <lambda_function_module>.<handler_function>
# This tells Lambda how to invoke the function.
CMD [ "lambda_function.lambda_handler" ]
