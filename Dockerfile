# Use a linux base image
FROM amazonlinux:2

# Install dependencies
RUN yum install -y curl tar gzip zip

# Set the working directory
WORKDIR /workspace

# Download the specified release of Pandoc
RUN curl -LO https://github.com/jgm/pandoc/releases/download/3.1.13/pandoc-3.1.13-linux-amd64.tar.gz

# Extract the downloaded tar.gz file
RUN tar -xzf pandoc-3.1.13-linux-amd64.tar.gz

# Create the necessary Lambda layer directory structure and move pandoc binary
RUN mkdir -p pandoc-layer/bin && mv pandoc-3.1.13/bin/pandoc pandoc-layer/bin/

# Zip the layer contents into /workspace
RUN cd pandoc-layer && zip -r /workspace/pandoc_layer.zip .

# Don't move to /lib/lambda-layers during build to avoid volume conflicts

# Final runtime command to move zip to the volume-mapped folder
CMD ["bash", "-c", "mv /workspace/pandoc_layer.zip /lib/lambda-layers/ && echo 'Pandoc layer has been packaged and moved to /lib/lambda-layers'"]
