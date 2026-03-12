# GitHub Actions Deployment Guide

This document outlines the necessary configurations, secrets, and permissions required to successfully deploy the SupportPilot Admin panel and Agent Runner to Google Cloud Run using the provided `.github/workflows/deploy.yml` pipeline.

## 1. Required GitHub Secrets

You must add the following secrets to your GitHub repository by navigating to **Settings > Secrets and variables > Actions > New repository secret**.

| Secret Name | Description | Example Value |
| :--- | :--- | :--- |
| `GCP_CREDENTIALS` | The JSON key file of the Google Service Account used for deployment. | `{ "type": "service_account", "project_id": "...", ... }` |
| `GOOGLE_CLOUD_PROJECT` | Your Google Cloud Project ID. | `my-awesome-project-123456` |
| `GOOGLE_CLOUD_LOCATION` | The Google Cloud region to deploy the Cloud Run service and Firestore database. Must be a single region. | `us-central1` |
| `ADMIN_SERVICE_NAME` | The name for the Cloud Run service running the Django Admin Panel. | `supportpilot-admin` |
| `AGENT_IMAGE_NAME` | The name of the Docker image for the agent runner. (This is appended to `gcr.io/PROJECT_ID/...`) | `supportpilot-agent` |
| `DJANGO_SECRET_KEY` | A long, cryptographically secure random string used by Django for sessions and signing. | `django-insecure-your-long-random-string-here` |
| `FIRESTORE_DATABASE` | *(Optional)* The specific ID of the Firestore database to use. | `(default)` |

---

## 2. Google Cloud Service Account Permissions

The GitHub Action uses a Google Cloud Service Account (via the `GCP_CREDENTIALS` secret) to authenticate and perform deployments. This Service Account must have the exact IAM roles listed below to function correctly.

### Required IAM Roles

Navigate to the Google Cloud Console [IAM & Admin page](https://console.cloud.google.com/iam-admin/iam), select your service account, and grant the following roles:

1. **Cloud Run Admin** (`roles/run.admin`)
   - *Why:* Required to deploy and manage Cloud Run services.
2. **Storage Admin** (`roles/storage.admin`)
   - *Why:* Required by Cloud Build to upload source code and store built images in the Google Container Registry (`gcr.io`).
3. **Cloud Build Service Account** (`roles/cloudbuild.builds.editor`)
   - *Why:* Required to submit and execute Docker image builds for the Agent Runner.
4. **Service Account User** (`roles/iam.serviceAccountUser`)
   - *Why:* Required so the GitHub Action can instruct Cloud Run to run using a specific runtime service account securely.
5. **Viewer** (`roles/viewer`)
   - *Why:* Provides basic read access to project metadata required during deployment.
6. **Logs Viewer** (`roles/logging.viewer`)
   - *Why:* Required for Cloud Build to stream logs back to the GitHub Actions console during the build process.
7. **Artifact Registry Administrator** (`roles/artifactregistry.admin`)
   - *Why:* Required to create the repository and push the container image when deploying from source using `gcloud run deploy --source`.
8. **Service Usage Consumer** (`roles/serviceusage.serviceUsageConsumer`)
   - *Why:* Required by Cloud Build to build from source during `gcloud run deploy`.

### Service Account Creation Instructions

1. Go to the [Google Cloud Console Service Accounts page](https://console.cloud.google.com/iam-admin/serviceaccounts).
2. Click **Create Service Account**, name it (e.g., `github-actions-deployer`), and click Create.
3. In the "Grant this service account access to project" step, add the 8 roles listed above.
4. Click **Done**.
5. Click on the newly created Service Account, navigate to the **Keys** tab.
6. Click **Add Key > Create new key**, select **JSON**, and click Create.
7. Open the downloaded JSON file, copy its entire contents, and paste it into the `GCP_CREDENTIALS` secret in GitHub.

---

## 3. Manual Database Creation

Instead of auto-creating the database, you must manually create the Firestore Database before deploying:

1. Go to the [Firestore Console](https://console.cloud.google.com/firestore/).
2. Click **Create Database**.
3. Set the Database ID to exactly what you specified in `FIRESTORE_DATABASE` (or leave it as `(default)` if you didn't set a custom name).
4. Select the location matching your `GOOGLE_CLOUD_LOCATION`.
5. Choose **Native mode** and click Create.

Make sure your Compute Engine default service account retains the **Cloud Datastore User** role so the application can read/write data to this database.

---

## 4. Compute Engine Default Service Account Permissions

When the Admin Panel runs on Cloud Run, it executes under the **Compute Engine default service account** (usually formatted as `[YOUR_PROJECT_NUMBER]-compute@developer.gserviceaccount.com`). 

For the Admin Panel to function correctly (connect to the database and deploy new agents), you must grant this service account the following roles in the [Google Cloud IAM Console](https://console.cloud.google.com/iam-admin/iam):

1. **Cloud Datastore User** (`roles/datastore.user`)
   - *Why:* Required so the Admin Panel can read and write to your Firestore database (to save agents and user accounts).
2. **Cloud Run Admin** (`roles/run.admin`)
   - *Why:* Required so the Admin Panel can programmatically create and deploy new Cloud Run services when you click "Deploy to Cloud Run" for an agent, and to set those agents to allow unauthenticated invocations (`allUsers`).
3. **Service Account User** (`roles/iam.serviceAccountUser`)
   - *Why:* Required alongside Cloud Run Admin so the Admin Panel has permission to attach a service account to the newly deployed agent services.
