# Electio-Analytics — commandes jury / CI locale
.PHONY: pipeline pipeline-real test dqm quality diagrams deck report livrables

pipeline:
	python run_pipeline.py

pipeline-real:
	python run_pipeline.py --real

test:
	python -m pytest tests/ -v

dqm:
	python dqm/run_checkpoint.py

quality: test dqm

diagrams:
	@echo PNG : docs/mspr/02_architecture/diagrams/
	@echo HTML : ouvrir flux_etl.html / scale_out.html dans le navigateur

deck:
	cd docs/scripts && node make_deck.js

report:
	cd docs/scripts && node make_report.js

livrables: deck report
