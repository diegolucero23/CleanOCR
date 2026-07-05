# 1. Use an official lightweight Python runtime
FROM python:3.11-slim

# 2. Install System Dependencies (The "Linux" version of Poppler)
# We also clean up the apt cache to keep the image small
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Copy requirements first (to cache dependencies)
COPY requirements.txt constraints.txt ./

# 5. Install Python libraries (constraints.txt locks all transitive versions)
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

# 6. Copy the rest of the application code
COPY . .

# 7. Default command: Run the interactive menu
CMD ["python", "-m", "app.main"]