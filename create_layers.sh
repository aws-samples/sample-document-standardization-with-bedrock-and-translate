#!/bin/bash

# Build the Docker image
docker build -t lambda-layer-builder .

# Create layers
create_layer() {
    layer_name=$1
    packages=$2

    echo "Creating layer for $layer_name..."
    
    # Create a temporary requirements file
    echo "$packages" > temp_requirements.txt
    
    # Run pip install in the container
    docker run --rm -v $(pwd):/asset lambda-layer-builder pip install -r /asset/temp_requirements.txt -t /asset/python/

    # Create the zip file
    zip -r ${layer_name}_layer.zip python

    # Clean up
    rm -rf python
    rm temp_requirements.txt

    echo "Layer created: ${layer_name}_layer.zip"
}

# Create individual layers
create_layer "beautifulsoup" "beautifulsoup4==4.12.3"
create_layer "mammoth" "mammoth==1.8.0"
create_layer "pythondocx" "python-docx==1.1.0 lxml==4.9.2"

# Move layers to the correct directory
mkdir -p lib/lambda-layers
mv *_layer.zip lib/lambda-layers/

echo "All layers created and moved to lib/lambda-layers/"
