import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as path from 'path';

export class DocProcessingStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 buckets
    const inputBucket = new s3.Bucket(this, 'InputBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    const outputBucket = new s3.Bucket(this, 'OutputBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // SNS Topic
    const resultTopic = new sns.Topic(this, 'ResultTopic');

    // Lambda function
    const processingLambda = new lambda.Function(this, 'ProcessingLambda', {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: 'processor.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda')),
      environment: {
        OUTPUT_BUCKET: outputBucket.bucketName
      }
    });

    // Permission to read and write S3 buckets
    inputBucket.grantRead(processingLambda);
    outputBucket.grantWrite(processingLambda);

    // Set up the Lambda trigger
    inputBucket.addEventNotification(s3.EventType.OBJECT_CREATED_PUT, new s3.notifications.LambdaDestination(processingLambda));

    // Define the Step Functions state machine
    const lambdaTask = new tasks.LambdaInvoke(this, 'Invoke Processing Lambda', {
      lambdaFunction: processingLambda,
      outputPath: '$.Payload',
    });

    const successState = new sfn.Pass(this, 'Success', {
      result: sfn.Result.fromObject({ message: 'Processing successful!' }),
    });

    const failureState = new sfn.Pass(this, 'Failure', {
      result: sfn.Result.fromObject({ message: 'Processing failed!' }),
    });

    const definition = lambdaTask
      .addCatch(failureState, { resultPath: '$.errorInfo' })
      .next(successState);

    const stateMachine = new sfn.StateMachine(this, 'StateMachine', {
      definition,
      timeout: cdk.Duration.minutes(5)
    });

    // Grant permissions to the state machine to invoke the Lambda
    processingLambda.grantInvoke(new iam.ServicePrincipal('states.amazonaws.com'));

    // SNS notifications for state machine execution results
    successState.next(new tasks.SnsPublish(this, 'Publish Success', {
      topic: resultTopic,
      message: sfn.TaskInput.fromJsonPathAt('$.result'),
    }));

    failureState.next(new tasks.SnsPublish(this, 'Publish Failure', {
      topic: resultTopic,
      message: sfn.TaskInput.fromJsonPathAt('$.errorInfo'),
    }));
  }
}
