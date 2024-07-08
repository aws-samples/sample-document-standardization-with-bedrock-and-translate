import json
import os
import boto3

s3 = boto3.client('s3')

def handler(event, context):
    print(event)
    bucket_name = os.environ['BUCKET_NAME']
    subfolders = ['english/', 'spanish/', 'french/']  # List of subfolders to create

    try:
        for subfolder in subfolders:
            try:
                # Check if the folder already exists
                s3.head_object(Bucket=bucket_name, Key=subfolder)
                print(f'Folder {subfolder} already exists')
            except s3.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    s3.put_object(Bucket=bucket_name, Key=subfolder)
                    print(f'Folder {subfolder} created successfully')
                else:
                    raise

        return {
            'statusCode': 200,
            'body': json.dumps('Subfolders checked/created successfully')
        }
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error checking/creating subfolders: {str(e)}')
        }
