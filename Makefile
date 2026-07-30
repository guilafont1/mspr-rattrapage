# Electio-Analytics — commandes jury / CI locale
.PHONY: pipeline pipeline-real test gx quality diagrams

pipeline:
	python run_pipeline.py

pipeline-real:
	python run_pipeline.py --real

test:
	python -m pytest tests/ -v

gx:
	python -m great_expectations checkpoint run electio_silver_gold || python gx/run_checkpoint.py

quality: test gx

diagrams:
	@echo Voir docs/mspr/02_architecture/DIAGRAMMES_FLUX.md et docs/README.md
