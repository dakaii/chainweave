import * as pulumi from "@pulumi/pulumi";
import * as gcp from "@pulumi/gcp";

// Configuration
const config = new pulumi.Config();
const gcpConfig = new pulumi.Config("gcp");
const projectId = gcpConfig.require("project");
const region = gcpConfig.get("region") || "us-central1";
const environment = config.get("environment") || "dev";

// Resource naming
const resourcePrefix = `chainweave-${environment}`;

// Enable required Google Cloud APIs
const bigqueryApi = new gcp.projects.Service("bigquery-api", {
    service: "bigquery.googleapis.com",
    project: projectId,
});

const pubsubApi = new gcp.projects.Service("pubsub-api", {
    service: "pubsub.googleapis.com",
    project: projectId,
});

const cloudRunApi = new gcp.projects.Service("cloudrun-api", {
    service: "run.googleapis.com",
    project: projectId,
});

const cloudbuildApi = new gcp.projects.Service("cloudbuild-api", {
    service: "cloudbuild.googleapis.com",
    project: projectId,
});

const loggingApi = new gcp.projects.Service("logging-api", {
    service: "logging.googleapis.com",
    project: projectId,
});

const monitoringApi = new gcp.projects.Service("monitoring-api", {
    service: "monitoring.googleapis.com",
    project: projectId,
});

// BigQuery Dataset
const dataset = new gcp.bigquery.Dataset("nft-analytics-dataset", {
    datasetId: `chainweave_${environment}`,
    project: projectId,
    location: region,
    description: "ChainWeave NFT analytics data",
    deleteContentsOnDestroy: environment === "dev",
    access: [
        {
            role: "OWNER",
            userByEmail: "dev@chainweave.io", // Replace with actual email
        },
        {
            role: "READER",
            specialGroup: "projectReaders",
        },
        {
            role: "WRITER",
            specialGroup: "projectWriters",
        },
    ],
}, { dependsOn: [bigqueryApi] });

// Pub/Sub Topics
const nftEventsTopic = new gcp.pubsub.Topic("nft-events-topic", {
    name: `${resourcePrefix}-nft-events`,
    project: projectId,
}, { dependsOn: [pubsubApi] });

const deadLetterTopic = new gcp.pubsub.Topic("nft-events-dlq-topic", {
    name: `${resourcePrefix}-nft-events-dlq`,
    project: projectId,
}, { dependsOn: [pubsubApi] });

// Pub/Sub Subscriptions
const nftEventsSubscription = new gcp.pubsub.Subscription("nft-events-subscription", {
    name: `${resourcePrefix}-nft-processor`,
    topic: nftEventsTopic.name,
    project: projectId,
    ackDeadlineSeconds: 300,
    messageRetentionDuration: "604800s", // 7 days
    retryPolicy: {
        minimumBackoff: "10s",
        maximumBackoff: "600s",
    },
    deadLetterPolicy: {
        deadLetterTopic: deadLetterTopic.id,
        maxDeliveryAttempts: 5,
    },
    enableMessageOrdering: false,
});

// Service Account for applications
const serviceAccount = new gcp.serviceaccount.Account("chainweave-service-account", {
    accountId: `${resourcePrefix}-sa`,
    displayName: `ChainWeave ${environment} Service Account`,
    description: `Service account for ChainWeave ${environment} environment`,
    project: projectId,
});

// IAM bindings for service account
const bigqueryAdminBinding = new gcp.projects.IAMBinding("bigquery-admin-binding", {
    project: projectId,
    role: "roles/bigquery.admin",
    members: [
        pulumi.interpolate`serviceAccount:${serviceAccount.email}`,
    ],
});

const pubsubAdminBinding = new gcp.projects.IAMBinding("pubsub-admin-binding", {
    project: projectId,
    role: "roles/pubsub.admin", 
    members: [
        pulumi.interpolate`serviceAccount:${serviceAccount.email}`,
    ],
});

const loggingWriterBinding = new gcp.projects.IAMBinding("logging-writer-binding", {
    project: projectId,
    role: "roles/logging.logWriter",
    members: [
        pulumi.interpolate`serviceAccount:${serviceAccount.email}`,
    ],
});

const monitoringWriterBinding = new gcp.projects.IAMBinding("monitoring-writer-binding", {
    project: projectId,
    role: "roles/monitoring.metricWriter",
    members: [
        pulumi.interpolate`serviceAccount:${serviceAccount.email}`,
    ],
});

// Cloud Storage bucket for artifacts
const artifactBucket = new gcp.storage.Bucket("chainweave-artifacts", {
    name: `${resourcePrefix}-artifacts`,
    project: projectId,
    location: region,
    storageClass: "STANDARD",
    uniformBucketLevelAccess: true,
    versioning: {
        enabled: true,
    },
    lifecycleRules: [
        {
            condition: {
                age: 30,
            },
            action: {
                type: "Delete",
            },
        },
    ],
});

// Outputs
export const datasetId = dataset.datasetId;
export const datasetLocation = dataset.location;
export const nftEventsTopicName = nftEventsTopic.name;
export const nftEventsSubscriptionName = nftEventsSubscription.name;
export const deadLetterTopicName = deadLetterTopic.name;
export const serviceAccountEmail = serviceAccount.email;
export const artifactBucketName = artifactBucket.name;
export const projectId = projectId;
export const region = region;