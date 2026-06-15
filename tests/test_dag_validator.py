import pytest

from orchestration.dag_validator import DagValidationError, validate_dag
from orchestration.schemas import Dag, DagNode


def test_valid_dag_passes():
    dag = Dag(
        project="p",
        nodes=[DagNode(id="001"), DagNode(id="002", depends=["001"])],
    )
    validate_dag(dag)  # should not raise


def test_cycle_detected():
    dag = Dag(
        project="p",
        nodes=[
            DagNode(id="001", depends=["002"]),
            DagNode(id="002", depends=["001"]),
        ],
    )
    with pytest.raises(DagValidationError):
        validate_dag(dag)


def test_unknown_dependency():
    dag = Dag(project="p", nodes=[DagNode(id="001", depends=["999"])])
    with pytest.raises(DagValidationError):
        validate_dag(dag)


def test_duplicate_ids():
    dag = Dag(project="p", nodes=[DagNode(id="001"), DagNode(id="001")])
    with pytest.raises(DagValidationError):
        validate_dag(dag)
