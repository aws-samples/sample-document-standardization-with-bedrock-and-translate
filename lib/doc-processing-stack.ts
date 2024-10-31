// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

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
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatch_actions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as sns_subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import { DefinitionBody } from 'aws-cdk-lib/aws-stepfunctions';
import * as logs from 'aws-cdk-lib/aws-logs';




export class DocProcessingStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Bucket for S3 service logs
    const logBucket = new s3.Bucket(this, 'S3LogsBucket', {
      autoDeleteObjects: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY, 
      enforceSSL: true,
    });

    // S3 buckets
    const inputBucket = new s3.Bucket(this, 'InputBucket', {
      autoDeleteObjects: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY, 
      serverAccessLogsBucket: logBucket,
      serverAccessLogsPrefix: 'InputBucketLogs',
      enforceSSL: true,
    });

    const outputBucket = new s3.Bucket(this, 'OutputBucket', {
      autoDeleteObjects: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY, 
      serverAccessLogsBucket: logBucket,
      serverAccessLogsPrefix: 'OutputBucketLogs',
      enforceSSL: true,
    });

    // Log S3 data events so EventBridge rule can be triggered
    const trail = new cloudtrail.Trail(this, 'MyS3Trail', {});
    trail.addS3EventSelector([{bucket: inputBucket}], {
      readWriteType: cloudtrail.ReadWriteType.WRITE_ONLY,
    });

    // SNS Topic for workflow results 
    const resultTopic = new sns.Topic(this, 'ResultTopic', {
      topicName: 'DocStandardizationStack-ResultTopic',
    });

    // Enable server-side encryption with AWS-managed key
    const cfnResultTopic = resultTopic.node.defaultChild as sns.CfnTopic;
    cfnResultTopic.kmsMasterKeyId = 'alias/aws/sns';

    // Add a policy to enforce SSL
    const topicPolicy = new iam.PolicyStatement({
      effect: iam.Effect.DENY,
      principals: [new iam.AnyPrincipal()],
      actions: ['SNS:Publish'],
      resources: [resultTopic.topicArn],
      conditions: {
        'Bool': {
          'aws:SecureTransport': 'false'
        }
      }
    });

    resultTopic.addToResourcePolicy(topicPolicy);
    
    
    // Define the python-docx Lambda layer
    const package_layer = new lambda.LayerVersion(this, 'PackageLayer', {
      code: lambda.Code.fromAsset('lib/lambda-layers/layer.zip'), 
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_9],
      description: 'A layer containing python-docx, mammoth and beautiful soup',
    });

    // Translate Lambda function
    const translateLambda = new lambda.Function(this, 'translateLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'translate.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda/translate')),
      layers: [package_layer],
      environment: {
        INPUT_BUCKET: inputBucket.bucketName,
      },
      timeout: cdk.Duration.minutes(3),
      reservedConcurrentExecutions: 1,
    });

    // Bedrock Lambda function
    const bedrockLambda = new lambda.Function(this, 'bedrockLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'bedrock_processor.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda/bedrock')),
      layers: [package_layer],
      environment: {
        OUTPUT_BUCKET: outputBucket.bucketName,
        INPUT_BUCKET: inputBucket.bucketName,
      },
      timeout: cdk.Duration.minutes(3),
    });

    // Aggregate Lambda function
    const aggregationLambda = new lambda.Function(this, 'aggregationLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'aggregate_results.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda/aggregation')),
      timeout: cdk.Duration.minutes(1),
    });

    // Create S3 folders lambda
    const createS3foldersLambda = new lambda.Function(this, 'createS3foldersLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'createS3folders.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda/createS3folders')),
      environment: {
        BUCKET_NAME: inputBucket.bucketName,
      }
    });
    
    // Permission to read and write S3 buckets
    inputBucket.grantReadWrite(createS3foldersLambda);
    inputBucket.grantReadWrite(translateLambda);
    inputBucket.grantRead(bedrockLambda);
    outputBucket.grantReadWrite(bedrockLambda);

    // Create a policy statement that allows invoking the Amazon Translate service
    const translatePolicy = new iam.PolicyStatement({
      actions: ['translate:TranslateText'],
      resources: ['*'],
    })
     // Attach the policy to the  bedrockLambda role
     translateLambda.addToRolePolicy(translatePolicy);
    
    // Create a policy statement that allows invoking the Bedrock service
    const bedrockPolicy = new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'], 
      resources: ['*'], 
    });
    
    // Attach the policy to the  bedrockLambda role
    bedrockLambda.addToRolePolicy(bedrockPolicy);

    // Define the Step Functions state machine
    const translateTask = new tasks.LambdaInvoke(this, 'Translate Task', {
      lambdaFunction: translateLambda,
      outputPath: '$.Payload',
    });

    const bedrockLambdaTask = new tasks.LambdaInvoke(this, 'Invoke Bedrock Processing Lambda', {
      lambdaFunction: bedrockLambda,
    });

    const aggregateResultsTask = new tasks.LambdaInvoke(this, 'Aggregate Results', {
      lambdaFunction: aggregationLambda,
      payload: sfn.TaskInput.fromObject({
        mapResults: sfn.JsonPath.stringAt('$.mapResults')
      }),
      outputPath: '$.Payload',
    });

    const publishResultsTask = new tasks.SnsPublish(this, 'Publish Results', {
      topic: resultTopic,
      message: sfn.TaskInput.fromJsonPathAt('$.message'),
    });

    const wordTemplateTask = new tasks.LambdaInvoke(this, 'Template uploaded, creating S3 folders', {
      lambdaFunction: createS3foldersLambda,
      outputPath: '$.Payload'
    });

    const parseBody = new sfn.Pass(this, 'Parse Body', {
      parameters: {
        'body.$': 'States.StringToJson($.body)',
      },
      resultPath: '$.parsedBody',
    });

    const mapState = new sfn.Map(this, 'Process Docs', {
      maxConcurrency: 1,
      itemsPath: sfn.JsonPath.stringAt('$.parsedBody.body.filePaths'),
      resultPath: '$.mapResults',
    }).itemProcessor(
      bedrockLambdaTask.next(
        new sfn.Choice(this, 'Did Lambda Succeed?')
          .when(sfn.Condition.numberEquals('$.Payload.statusCode', 200), new sfn.Pass(this, 'Lambda Success'))
          .otherwise(new sfn.Pass(this, 'Lambda Failure'))
      )
    );

    // Update when adding / changing languages
    const exitPaths = ['english/', 'spanish/','french/'];
    const exitCondition = sfn.Condition.or(...exitPaths.map(path => sfn.Condition.stringEquals('$.documentName', path)));
    const succeedState = new sfn.Succeed(this, 'S3 folder created');

    
    const definition = new sfn.Choice(this, 'Was template uploaded?')
    .when(sfn.Condition.stringEquals('$.documentName', 'word_template.docx'), wordTemplateTask)
    .when(exitCondition, succeedState)
    .otherwise(
      translateTask.next(
        new sfn.Choice(this, 'Did Translate Succeed?')
          .when(sfn.Condition.numberEquals('$.statusCode', 200), 
            parseBody.next(
              mapState.next(
                aggregateResultsTask.next(
                  publishResultsTask
                )
              )
            )
          )
          .otherwise(publishResultsTask)
      )
    );

    // Create logGroup for state machine
    const sfnLogGroup = new logs.LogGroup(this, 'DocProcessingStateMachineLogs', {
      logGroupName: '/aws/vendedlogs/states/DocProcessingStateMachine',
    });

    const stateMachine = new sfn.StateMachine(this, 'DocProcessingStateMachine', {
      definitionBody: DefinitionBody.fromChainable(definition),
      timeout: cdk.Duration.minutes(5),
      logs: {
        destination: sfnLogGroup,
        level: sfn.LogLevel.ALL,
        includeExecutionData: true,
      },
    });

    // S3 event rule - ignoring the "_translated.docx" suffix  created by the translate lambda
    const s3EventRule = new events.Rule(this, 's3EventRule', {
      eventPattern: {
        source: ['aws.s3'],
        detailType: ['AWS API Call via CloudTrail'],
        detail: {
          eventSource: ['s3.amazonaws.com'],
          eventName: ['PutObject'],
          requestParameters: {
            bucketName: [inputBucket.bucketName],
            key: [{ "anything-but": {
              "suffix": "_translated.docx"
            }}]
          }
        }
      }
    });

    // Target the state machine from the S3 event
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

    // Grant permissions to the state machine to invoke the Lambdas
    translateLambda.grantInvoke(new iam.ServicePrincipal('states.amazonaws.com'));
    bedrockLambda.grantInvoke(new iam.ServicePrincipal('states.amazonaws.com'));
    aggregationLambda.grantInvoke(new iam.ServicePrincipal('states.amazonaws.com'));
    createS3foldersLambda.grantInvoke(new iam.ServicePrincipal('states.amazonaws.com'));

    // SNS Topic for publishing alarm notifications
    const alarmTopic = new sns.Topic(this, 'AlarmTopic', {
      topicName: 'DocStandardizationStack-AlarmTopic',
    });

    // Add a policy to enforce SSL
    const alarmtopicPolicy = new iam.PolicyStatement({
      effect: iam.Effect.DENY,
      principals: [new iam.AnyPrincipal()],
      actions: ['SNS:Publish'],
      resources: [alarmTopic.topicArn],
      conditions: {
        'Bool': {
          'aws:SecureTransport': 'false'
        }
      }
    });
    alarmTopic.addToResourcePolicy(alarmtopicPolicy);


    // CloudWatch Alarm to monitor Lambda invocations
    const alarm = new cloudwatch.Alarm(this, 'LoopInvocationAlarm', {
      metric: stateMachine.metric('ExecutionsStarted'),
      threshold: 5, // Alarm if more than 5 invocations
      evaluationPeriods: 1, // within 1 evaluation period (5 mins by default)
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      alarmDescription: 'Triggers if state machine is invoked more than 10 times in 5 minutes',
    });

    // Set SNS Topic as the action for the alarm
    alarm.addAlarmAction(new cloudwatch_actions.SnsAction(alarmTopic));

    // Create a Lambda function that deletes the S3 event rule
    const deleteS3EventRuleLambda = new lambda.Function(this, 'DeleteS3EventRuleLambda', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'delete_rule.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda/delete_rule')),
      environment: {
        RESULTS_TOPIC_ARN: resultTopic.topicArn,
        EVENT_RULE_NAME: s3EventRule.ruleName,
      },
      timeout: cdk.Duration.minutes(3),
    });

    deleteS3EventRuleLambda.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'events:DeleteRule', 
        'events:DisableRule',     
        'events:RemoveTargets',   
        'events:ListTargetsByRule' 
      ],
      resources: [
        `arn:aws:events:${this.region}:${this.account}:rule/${s3EventRule.ruleName}`, 
      ],
    }));
    
    // Grant permission to publish messages to the SNS topic
    deleteS3EventRuleLambda.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'sns:Publish' 
      ],
      resources: [
        resultTopic.topicArn,
      ],
    }));
    
    // Subscribe the deletion Lambda to the SNS Topic
    alarmTopic.addSubscription(new sns_subscriptions.LambdaSubscription(deleteS3EventRuleLambda));

    // Stack Outputs
    new cdk.CfnOutput(this, 'ResultTopicName', {
      value: resultTopic.topicName,
      description: 'The name of the result SNS topic you subscribe to',
    });
    
    new cdk.CfnOutput(this, 'InputBucketName', {
      value: inputBucket.bucketName,
      description: 'The name of the S3 bucket you upload documents to',
    });
    
    new cdk.CfnOutput(this, 'OutputBucketName', {
      value: outputBucket.bucketName,
      description: 'The name of the S3 bucket where the processed documents are stored',
    });
    

  }
}
