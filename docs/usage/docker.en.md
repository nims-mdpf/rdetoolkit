# Using RDEToolKit with Docker

## Overview

This guide explains how to run RDE structured processing using RDEToolKit on Docker. Using Docker ensures environment consistency and simplifies deployment.

## Prerequisites

- Docker Desktop or Docker Engine installed
- Basic knowledge of Docker commands
- Understanding of RDEToolKit project structure

## Directory Structure

Recommended directory structure for structured processing projects:

```shell
(Structured Processing Project Directory)
├── container
│   ├── data/
│   ├── modules/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── inputdata
│   ├── input1
│   └── input2
├── README.md
└── template
    ├── batch.yaml
    ├── catalog.schema.json
    ├── invoice.schema.json
    ├── jobs.template.yaml
    ├── metadata-def.json
    └── tasksupport
```

## Creating Dockerfile

Create `container/Dockerfile`. Here's a basic Dockerfile example:

```dockerfile title="container/Dockerfile"
FROM python:3.11.9

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY main.py /app
COPY modules/ /app/modules/
```

!!! tip "Customization"
    Feel free to modify the Docker image and execution statements according to your project requirements.

!!! note "Reference"
    You can find base images at [Docker Hub Container Image Library](https://hub.docker.com/).

## Building Images

### Basic Build

Navigate to the directory containing the `Dockerfile` and run the docker build command:

```bash title="Image Build"
# Basic command
docker build -t image_name:tag path

# Example
docker build -t sample_tif:v1 .
```

### Option Descriptions

- `-t` option: Specifies image name and tag. Image name can be arbitrary but should be unique.
- Path: Specifies the path to the directory containing the `Dockerfile`. Use `.` for current directory.

### Proxy Environment Support

When building in a proxy environment, add the following options:

```bash title="Build in Proxy Environment"
docker build -t sample_tif:v1 \
  --build-arg http_proxy=http://proxy.example.com:8080 \
  --build-arg https_proxy=http://proxy.example.com:8080 \
  .
```

## Handling pip Command Errors

Solution for SSL certificate errors with pip commands:

### Creating pip.conf File

Create a `pip.conf` file in the same directory as the Dockerfile:

```ini title="pip.conf"
[install]
trusted-host =
    pypi.python.org
    files.pythonhosted.org
    pypi.org
```

### Modifying Dockerfile

Modify the Dockerfile to use pip.conf:

```dockerfile title="Modified Dockerfile"
FROM python:3.11

WORKDIR /app

COPY requirements.txt .
COPY pip.conf /etc/pip.conf

RUN pip install -r requirements.txt

COPY main.py /app
COPY modules/ /app/modules/
```

## Running Docker Containers

### Basic Execution

To run the built image, use the `docker run` command:

```bash title="Container Execution"
# Basic command
docker run [options] image_name [command]

# Example
docker run -it -v ${HOME}/sample_tif/container/data:/app2/data --name "sample_tifv1" sample_tif:v1 "/bin/bash"
```

### Option Details

| Option | Description |
|--------|-------------|
| `-it` | Run container in interactive mode. Enables terminal and command-line interface |
| `-v host_path:container_path` | Mount directory between host and container |
| `--name "container_name"` | Assign a name to the container |
| `image_name:tag` | Name and version of Docker image to run |
| `"/bin/bash"` | Command to execute inside the container |

### Mounting Data Volumes

Mount input file directories to test structured processing:

```bash title="Data Mount Example"
docker run -it \
  -v ${HOME}/sample_tif/container/data:/app2/data \
  -v ${HOME}/sample_tif/inputdata:/app2/inputdata \
  --name "sample_tifv1" \
  sample_tif:v1 \
  "/bin/bash"
```

## Running Programs Inside Container

Once the container starts, execute your developed program:

```bash title="Program Execution"
# Navigate to working directory
cd /app2

# Execute structured processing program
python3 /app/main.py
```

!!! tip "Terminal Change"
    When executed, the terminal will change to something like `root@(container_id):`.

## Container Management

### Exiting Container

```bash title="Exit Container"
exit
```

### Restarting Container

```bash title="Restart Stopped Container"
docker start sample_tifv1
docker exec -it sample_tifv1 /bin/bash
```

### Removing Container

```bash title="Remove Container"
docker rm sample_tifv1
```

## Best Practices

### Multi-stage Build

For production environments, use multi-stage builds to optimize image size:

```dockerfile title="Multi-stage Dockerfile"
# Build stage
FROM python:3.11 as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY main.py /app
COPY modules/ /app/modules/
ENV PATH=/root/.local/bin:$PATH
```

### .dockerignore File

Exclude unnecessary files from build context:

```text title=".dockerignore"
.git
.gitignore
README.md
Dockerfile
.dockerignore
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.venv
```

## Troubleshooting

### Common Issues and Solutions

1. **Port Conflict Error**
   - Avoid ports already in use
   - Check running containers with `docker ps`

2. **Volume Mount Error**
   - Verify paths are correct
   - Check permission settings

3. **Out of Memory Error**
   - Check Docker memory limits
   - Stop unnecessary containers

## Next Steps

- Understand [Structured Processing Concepts](../user-guide/structured-processing.en.md)
- Learn Docker environment configuration in [Configuration Files](../user-guide/config.en.md)
- Check archive creation using artifact command in [Command Line Interface](cli.en.md)
