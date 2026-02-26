AGENT_IMAGE ?= sebbycorp/bank-credit-limit-agent
WEB_IMAGE   ?= sebbycorp/solo-bank-web
TAG         ?= latest

.PHONY: build push build-web push-web build-all push-all run-web dev-web deploy

## ---------- Agent container ----------

build:
	docker build --platform linux/amd64 -t $(AGENT_IMAGE):$(TAG) .

push: build
	docker push $(AGENT_IMAGE):$(TAG)

## ---------- Web container ----------

build-web:
	docker build --platform linux/amd64 -t $(WEB_IMAGE):$(TAG) -f Dockerfile.web .

push-web: build-web
	docker push $(WEB_IMAGE):$(TAG)

## ---------- All ----------

build-all: build build-web

push-all: push push-web

## ---------- Local dev ----------

run-web:
	cd web && uvicorn app:app --host 0.0.0.0 --port 8080 --reload

dev-agent:
	cd src && BANK_API_URL=http://localhost:8080 uvicorn app:app --host 0.0.0.0 --port 8081 --reload

## ---------- Kubernetes ----------

deploy:
	kubectl apply -k k8s/agents/
	kubectl apply -k k8s/web/
