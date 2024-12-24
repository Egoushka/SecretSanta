# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any dependencies
RUN pip install -r requirements.txt

# Copy the project code into the container
COPY . .

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define the command to run your bot
CMD ["python", "bot.py"]