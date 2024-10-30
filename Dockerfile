FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.9

# Install necessary build tools
RUN yum install -y gcc libxml2 libxslt libxml2-devel libxslt-devel zip


# Prepare the target directory for the Lambda Layer
WORKDIR /python

# Upgrade pip and install packages using the requirements file
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt -t /python/python/lib/python3.9/site-packages/

# Package everything into a zip file
RUN mkdir -p /output && cd /python && zip -r /output/layer.zip .


# Ensure the command does nothing as the zip is already created
CMD echo "Layer packaged"
