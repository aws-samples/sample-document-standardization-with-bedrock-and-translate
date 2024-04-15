import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as path from 'path';
import * as events from 'aws-cdk-lib/aws-events';
import * as cloudtrail from 'aws-cdk-lib/aws-cloudtrail';
import * as eventTargets from 'aws-cdk-lib/aws-events-targets';

export class DocProcessingStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 buckets
    const inputBucket = new s3.Bucket(this, 'InputBucket', {
      autoDeleteObjects: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    const outputBucket = new s3.Bucket(this, 'OutputBucket', {
      autoDeleteObjects: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Log S3 data events so EventBridge rule can be triggered
    const trail = new cloudtrail.Trail(this, 'MyS3Trail', {});
    trail.addS3EventSelector([{bucket: inputBucket}], {
      readWriteType: cloudtrail.ReadWriteType.WRITE_ONLY,
    });

    // SNS Topic
    const resultTopic = new sns.Topic(this, 'ResultTopic');
    
    // Define the Lambda layer
    const LambdaLayer = new lambda.LayerVersion(this, 'LambdaLayer', {
      code: lambda.Code.fromAsset('../DocProcessing/layer.zip'), 
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_9],
      description: 'A layer for python-docx',
    });
    
    // Define the AWS SDK layer containing Pandas
    const awsSdkPandasLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      'AWSSDKPandasLayer',
      'arn:aws:lambda:eu-west-1:336392948345:layer:AWSSDKPandas-Python39:19'
    );

    // Lambda function
    const processingLambda = new lambda.Function(this, 'ProcessingLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'processor.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda')),
      layers: [LambdaLayer, awsSdkPandasLayer],
      environment: {
        OUTPUT_BUCKET: outputBucket.bucketName,
      }
    });

    // Permission to read and write S3 buckets
    inputBucket.grantRead(processingLambda);
    outputBucket.grantWrite(processingLambda);
    
    // Create a policy statement that allows invoking the Bedrock service
    const bedrockPolicy = new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'], // Modify based on actual service actions
      resources: ['*'], // Specify more restrictive resource ARNs as needed
    });
    
    // Attach the policy to the Lambda function's role
    processingLambda.addToRolePolicy(bedrockPolicy);


    // Define the Step Functions state machine
    const lambdaTask = new tasks.LambdaInvoke(this, 'Invoke Processing Lambda', {
      lambdaFunction: processingLambda,
    });

    const publishSuccess = new tasks.SnsPublish(this, 'Publish Success', {
      topic: resultTopic,
      message: sfn.TaskInput.fromJsonPathAt('$.Payload.body'),
    });

    const publishFailure = new tasks.SnsPublish(this, 'Publish Failure', {
      topic: resultTopic,
      message: sfn.TaskInput.fromJsonPathAt('$.Payload.error'),  
    });


    const checkStatus = new sfn.Choice(this, 'Check Status')
      .when(sfn.Condition.numberEquals('$.Payload.statusCode', 200), publishSuccess)
      .otherwise(publishFailure);
      
    lambdaTask.addCatch(publishFailure);

    const stateMachine = new sfn.StateMachine(this, 'StateMachine', {
      definition: lambdaTask.next(checkStatus),
      timeout: cdk.Duration.minutes(5),
    });

    // EventBridge rule that triggers on S3 PutObject
    const s3EventRule = new events.Rule(this, 's3EventRule', {
      eventPattern: {
        source: ['aws.s3'],
        detailType: ['AWS API Call via CloudTrail'],
        detail: {
          eventName: ['PutObject'],
          requestParameters: {
            bucketName: [inputBucket.bucketName],
          },
        },
      },
    });

    // Target the state machine with details from the S3 event
    s3EventRule.addTarget(new eventTargets.SfnStateMachine(stateMachine, {
      input: events.RuleTargetInput.fromObject({
        "documentName": events.EventField.fromPath('$.detail.requestParameters.key'),
        "documentPath": events.EventField.fromPath('$.detail.requestParameters.bucketName')
      }),
    }));

    // Grant EventBridge permission to invoke the state machine
    stateMachine.grantStartExecution(new iam.ServicePrincipal('events.amazonaws.com'));

    // SNS notifications for state machine execution results
    resultTopic.grantPublish(stateMachine);

    // Grant permissions to the state machine to invoke the Lambda
    processingLambda.grantInvoke(new iam.ServicePrincipal('states.amazonaws.com'));
  }
}
