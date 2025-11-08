# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


# Copy the rest of your agent's code into the container
COPY . .

# --- Cloud Run Specific ---
# The ADK default port is 8080, which Cloud Run also expects.
ENV PORT=8080
EXPOSE 8080

# Command to run the uvicorn server with your main.py file
CMD ["uvicorn", "manager_agent.docker_main:app", "--host", "0.0.0.0", "--port", "8080"]