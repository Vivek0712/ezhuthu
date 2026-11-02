import * as cdk from 'aws-cdk-lib';
import * as budgets from 'aws-cdk-lib/aws-budgets';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

/**
 * One on-demand table for sessions, corrections and the review queue (single-table design):
 *   SESSION#<id> / META                 learner session (written by the proxy and the agent)
 *   QUEUE#<id>   / ITEM                 correction or abstention awaiting review
 *   GSI1: gsi1pk = STATUS#<status>, gsi1sk = created_at  -> oldest-first queue listing
 */
export class EzhuthuDataStack extends cdk.Stack {
  public readonly table: dynamodb.TableV2;

  constructor(scope: Construct, id: string, props?: cdk.StackProps & { budgetEmail?: string }) {
    super(scope, id, props);
    this.table = new dynamodb.TableV2(this, 'AppTable', {
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
      billing: dynamodb.Billing.onDemand(),
      timeToLiveAttribute: 'ttl',
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      deletionProtection: false,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      globalSecondaryIndexes: [
        {
          indexName: 'gsi1',
          partitionKey: { name: 'gsi1pk', type: dynamodb.AttributeType.STRING },
          sortKey: { name: 'gsi1sk', type: dynamodb.AttributeType.STRING },
        },
      ],
    });
    new cdk.CfnOutput(this, 'TableName', { value: this.table.tableName });

    // Monthly cost guardrail: USD 50 for resources tagged Project=ezhuthu, email at 80% of actual spend.
    // The address comes from `-c ezhuthu:budgetEmail=<address>` or EZHUTHU_BUDGET_EMAIL; without one the
    // budget is still created, with no email notification.
    const budgetEmail = props?.budgetEmail;
    new budgets.CfnBudget(this, 'MonthlyBudget', {
      budget: {
        budgetName: 'ezhuthu-monthly',
        budgetType: 'COST',
        timeUnit: 'MONTHLY',
        budgetLimit: { amount: 50, unit: 'USD' },
        costFilters: { TagKeyValue: ['user:Project$ezhuthu'] },
      },
      notificationsWithSubscribers: budgetEmail
        ? [
            {
              notification: { notificationType: 'ACTUAL', comparisonOperator: 'GREATER_THAN', threshold: 80, thresholdType: 'PERCENTAGE' },
              subscribers: [{ subscriptionType: 'EMAIL', address: budgetEmail }],
            },
          ]
        : undefined,
    });
  }
}
