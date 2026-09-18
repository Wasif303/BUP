# 🐳 Docker Fallback Image — Build & Push Guide

According to Section 03 & Section 07 of the Hackathon Evaluation Rubric:
> *"The judges require a working pullable Docker fallback image that reaches /health using the documented command (4 points)."*

---

## 📋 Quick Steps for Your Team

### Step 1: Log in to Docker Hub
In your terminal (on any machine with Docker installed):
```bash
docker login
```
*(Enter your Docker Hub username and password/access token)*

---

### Step 2: Build the Docker Image
Inside the project root directory (where `Dockerfile` is located):
```bash
docker build -t wasif303/gridwise:latest .
```
*(Replace `wasif303` with your actual Docker Hub username if different, e.g. `yourusername/gridwise:latest`)*

---

### Step 3: Test the Image Locally Before Pushing
```bash
# Run container with API key
docker run -d -p 8000:8000 -e GEMINI_API_KEY="your-gemini-api-key" --name gridwise-test wasif303/gridwise:latest

# Check health endpoint
curl http://localhost:8000/health
# Expected output: {"status":"ok"}

# Stop and remove test container
docker stop gridwise-test && docker rm gridwise-test
```

---

### Step 4: Push to Docker Hub
```bash
docker push wasif303/gridwise:latest
```

Once pushed, verify on [hub.docker.com](https://hub.docker.com) that the repository is set to **Public** so the judges can pull it without credentials.

---

## 🔍 Exact Judge Execution Command
Make sure this exact command is in the README and submission form:
```bash
docker pull wasif303/gridwise:latest
docker run -d -p 8000:8000 -e GEMINI_API_KEY="your-gemini-api-key" wasif303/gridwise:latest
```
And verify health:
```bash
curl http://localhost:8000/health
```
