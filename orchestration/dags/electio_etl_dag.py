"""
Stub DAG Airflow — Electio-Analytics (compétence C3).
Ne nécessite pas Airflow pour le POC local : illustratif + exécutable
via `make pipeline` (Makefile).
"""
from __future__ import annotations

# Si Airflow est installé, ce module est chargeable comme DAG.
try:
    from datetime import datetime
    from airflow import DAG
    from airflow.operators.bash import BashOperator

    with DAG(
        dag_id="electio_etl_medaillon",
        start_date=datetime(2024, 1, 1),
        schedule=None,
        catchup=False,
        tags=["electio", "medallion"],
    ) as dag:
        download = BashOperator(
            task_id="download_real",
            bash_command="cd {{ var.value.electio_root | default('.') }} && python run_pipeline.py --real",
        )
        # run_pipeline enchaine deja transform/ML/viz ; tâche unique volontaire
        # pour le POC. En prod : splitter en tasks paralleles download_*.
        download
except ImportError:
    dag = None
