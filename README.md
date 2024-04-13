# Welcome to your CDK TypeScript project

This is a blank project for CDK development with TypeScript.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `npx cdk deploy`  deploy this stack to your default AWS account/region
* `npx cdk diff`    compare deployed stack with current state
* `npx cdk synth`   emits the synthesized CloudFormation template


## Deploying the Solution
1. Create a new environment in Cloud9 with an m5.large instance.
2. Clone the repo
3. Go to the project's root folder and run ```cdk synth``` followed by ```cdk deploy```

## Subscribing to the SNS Topic
After the solution is deployed, an SNS topic will be created. Create a subscription to this topic using a protocol and endpoint of your choice (this can be done via the AWS Management console)
* When using an email endpoint, you will receive an email asking to confirm the subscription