#!/bin/bash
# QUAN Recovery - Production Deployment Script

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-quan-recovery}"
REGION="${GCP_REGION:-us-central1}"
CLUSTER_NAME="${GKE_CLUSTER:-quan-production}"
NAMESPACE="quan-production"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "🚀 QUAN Recovery Production Deployment"
echo "======================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Cluster: $CLUSTER_NAME"
echo "Image Tag: $IMAGE_TAG"
echo ""

# Check prerequisites
command -v gcloud >/dev/null 2>&1 || { echo "gcloud required but not installed."; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl required but not installed."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "docker required but not installed."; exit 1; }

# Authenticate with GCP
echo "📦 Authenticating with GCP..."
gcloud auth configure-docker gcr.io --quiet

# Build and push Docker image
echo "🔨 Building Docker image..."
docker build -t gcr.io/$PROJECT_ID/api:$IMAGE_TAG .

echo "📤 Pushing image to GCR..."
docker push gcr.io/$PROJECT_ID/api:$IMAGE_TAG

# Get cluster credentials
echo "🔑 Getting cluster credentials..."
gcloud container clusters get-credentials $CLUSTER_NAME \
    --region $REGION \
    --project $PROJECT_ID

# Create namespace if not exists
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Apply Kubernetes configurations
echo "📋 Applying Kubernetes configurations..."
kubectl apply -f k8s/production/deployment.yaml
kubectl apply -f k8s/production/quantum-engine.yaml

# Wait for rollout
echo "⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/quan-api -n $NAMESPACE --timeout=300s

# Verify deployment
echo "✅ Verifying deployment..."
kubectl get pods -n $NAMESPACE -l app=quan-api

# Get service URL
echo ""
echo "🌐 Service Endpoints:"
kubectl get ingress -n $NAMESPACE

echo ""
echo "✨ Deployment complete!"
echo ""
echo "To check logs:"
echo "  kubectl logs -f deployment/quan-api -n $NAMESPACE"
echo ""
echo "To check metrics:"
echo "  kubectl port-forward svc/prometheus 9090:9090 -n $NAMESPACE"
