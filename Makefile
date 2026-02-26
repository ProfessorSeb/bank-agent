IMAGE_REPO ?= ghcr.io/professorseb/bank-credit-limit-agent
IMAGE_TAG  ?= latest
IMAGE      := $(IMAGE_REPO):$(IMAGE_TAG)

.PHONY: build push run dev deploy argocd-apply

## ---------- Container ----------

build:
	docker build -t $(IMAGE) .

push: build
	docker push $(IMAGE)

run: build
	docker run --rm -it \
		-p 8080:8080 \
		-e OPENAI_API_KEY=$(OPENAI_API_KEY) \
		-e LLM_BASE_URL=https://api.openai.com/v1 \
		-e LLM_MODEL=gpt-4o-mini \
		$(IMAGE)

## ---------- Local dev ----------

dev:
	cd src && uvicorn app:app --host 0.0.0.0 --port 8080 --reload

## ---------- Kubernetes ----------

deploy:
	kubectl apply -k k8s/agents/

argocd-apply:
	kubectl apply -f k8s/argocd/bank-agents-application.yaml
