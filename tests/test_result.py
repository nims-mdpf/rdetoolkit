from rdetoolkit.models.result import WorkflowExecutionStatus, WorkflowResultManager


def test_workflow_execution_status_creation():
    status = WorkflowExecutionStatus(
        run_id="1",
        title="Test Workflow",
        status="success",
        mode="invoice",
        error_code=None,
        error_message=None,
        target="example_target",
        stacktrace=None,
    )

    assert status.run_id == "0001"
    assert status.title == "Test Workflow"
    assert status.status == "success"
    assert status.mode == "invoice"
    assert status.error_code is None
    assert status.error_message is None
    assert status.target == "example_target"
    assert status.stacktrace is None


def test_workflow_result_manager_add():
    manager = WorkflowResultManager()
    manager.add(run_id="1", title="Test Workflow", status="success", mode="invoice", target="example_target", stacktrace=None)

    assert len(manager) == 1
    status: WorkflowExecutionStatus = manager[0]
    assert status.run_id == "0001"
    assert status.title == "Test Workflow"
    assert status.status == "success"
    assert status.mode == "invoice"
    assert status.error_code is None
    assert status.error_message is None
    assert status.target == "example_target"
    assert status.stacktrace is None


def test_workflow_result_manager_iteration():
    manager = WorkflowResultManager()
    manager.add(run_id="1", title="Test Workflow 1", status="success", mode="invoice", target="example_target_1", stacktrace=None)
    manager.add(run_id="2", title="Test Workflow 2", status="failure", mode="invoice", error_code=404, error_message="Not Found", target="example_target_2", stacktrace="Example stacktrace")
    statuses = list(manager)
    assert len(statuses) == 2
    assert statuses[0].run_id == "0001"
    assert statuses[0].stacktrace is None
    assert statuses[1].run_id == "0002"
    assert statuses[1].stacktrace == "Example stacktrace"


def test_workflow_result_manager_add_status():
    manager = WorkflowResultManager()
    status = WorkflowExecutionStatus(
        run_id="1",
        title="Test Workflow",
        status="success",
        mode="invoice",
        error_code=None,
        error_message=None,
        target="example_target",
        stacktrace=None,
    )
    manager.add_status(status)
    assert len(manager) == 1
    assert manager[0] == status


def test_workflow_result_manager_repr():
    manager = WorkflowResultManager()
    manager.add(run_id="1", title="Test Workflow", status="success", mode="invoice", target='example_target', stacktrace=None)
    repr_str = repr(manager)
    expected_repr = "WorkflowResultManager(statuses=[WorkflowExecutionStatus(run_id='0001', title='Test Workflow', status='success', mode='invoice', error_code=None, error_message=None, target='example_target', stacktrace=None, exception_object=None)])"
    assert repr_str == expected_repr


def test_workflow_result_manager_to_json():
    manager = WorkflowResultManager()
    manager.add(run_id="1", title="Test Workflow", status="success", mode="invoice", target="example_target", stacktrace=None)
    json_str = manager.to_json()
    expected_json = '''{
  "statuses": [
    {
      "run_id": "0001",
      "title": "Test Workflow",
      "status": "success",
      "mode": "invoice",
      "error_code": null,
      "error_message": null,
      "target": "example_target",
      "stacktrace": null
    }
  ]
}'''
    assert json_str == expected_json


