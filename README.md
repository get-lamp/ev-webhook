# Prerequisites (one-time)
gcloud auth login
gcloud config set project ai-workshop-500214
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
gcloud artifacts repositories create gfunc --location=us-central1 --repository-format=docker

> **NOTE**
> Instructions for creating pubsub subscriptions and topics are in workshop readme file

# Deploy
./deploy.sh

# Or with overrides
REGION=europe-west1 ./deploy.sh

After deploying, register the webhook URL (https://<service>-<hash>-<region>.a.run.app/drive/webhook) with the Drive API push notifications endpoint.

### PubSub push endpoints

The service exposes ``/pubsub/push`` to receive PubSub push subscription messages
for topics ``blueprint-drive-snapshot`` and ``blueprint-drive-snapshot-push``.

Create push subscriptions pointing at the deployed service URL:

```bash
# Create topics
gcloud pubsub topics create blueprint-routes-snapshot
gcloud pubsub topics create blueprint-routes-snapshot-push

# Create push subscriptions
gcloud pubsub subscriptions create blueprint-routes-snapshot-sub \
    --topic=blueprint-routes-snapshot \
    --push-endpoint=https://<service>-<hash>-<region>.a.run.app/pubsub/push

gcloud pubsub subscriptions create blueprint-routes-snapshot-push-sub \
    --topic=blueprint-routes-snapshot-push \
    --push-endpoint=https://<service>-<hash>-<region>.a.run.app/pubsub/push
```

```bash
gcloud projects add-iam-policy-binding ai-workshop-500214 \
    --member="serviceAccount:workshop@ai-workshop-500214.iam.gserviceaccount.com" \
    --role="roles/pubsub.publisher"
```