# Result Models API

## Purpose

This module defines data models for managing workflow execution results in RDEToolKit. It provides structured result data including execution status, result information, and error details.

## Key Features

### Execution Result Management
- Tracking workflow execution status
- Structuring execution results
- Integrated management through result manager

### Data Structures
- Type-safe result data
- Recording execution time
- Managing processing statistics

---

::: src.rdetoolkit.models.result.WorkflowExecutionStatus

---

::: src.rdetoolkit.models.result.WorkflowExecutionResults

---

::: src.rdetoolkit.models.result.WorkflowResultManager

---

## 実践的な使い方

### 基本的な実行結果管理

```python title="basic_result_management.py"
from rdetoolkit.models.result import WorkflowExecutionStatus, WorkflowExecutionResults
from datetime import datetime

# 実行ステータスの作成
status = WorkflowExecutionStatus(
    status="success",
    message="ワークフローが正常に完了しました",
    timestamp=datetime.now(),
    execution_time=120.5
)

print(f"実行ステータス: {status.status}")
print(f"メッセージ: {status.message}")
print(f"実行時間: {status.execution_time}秒")

# 実行結果の作成
results = WorkflowExecutionResults(
    run_id="workflow_001",
    status=status,
    input_files_count=5,
    output_files_count=8,
    processed_data_size=1024000,
    metadata={"experiment_id": "EXP001", "researcher": "John Doe"}
)

print(f"Execution ID: {results.run_id}")
print(f"Input files count: {results.input_files_count}")
print(f"Output files count: {results.output_files_count}")
print(f"Processed data size: {results.processed_data_size} bytes")
```

### Workflow Result Manager

```python title="workflow_result_manager.py"
from rdetoolkit.models.result import WorkflowResultManager, WorkflowExecutionStatus
from datetime import datetime
import json

# Create result manager
manager = WorkflowResultManager()

# Add multiple execution results
for i in range(3):
    run_id = f"workflow_{i+1:03d}"
    
    if i == 2:  # Last execution is error
        status = WorkflowExecutionStatus(
            status="error",
            message="Error occurred during file processing",
            timestamp=datetime.now(),
            execution_time=45.2
        )
    else:
        status = WorkflowExecutionStatus(
            status="success",
            message="Completed successfully",
            timestamp=datetime.now(),
            execution_time=120.5 + i * 10
        )
    
    # Add result
    manager.add(run_id, status, input_files=5+i, output_files=8+i*2)
    print(f"Added execution result {run_id}")

# Add status only
manager.add_status("workflow_004", "running", "Running...")

# Output in JSON format
results_json = manager.to_json()
print(f"\nOutput results in JSON format:")
print(json.dumps(json.loads(results_json), indent=2, ensure_ascii=False))
```

### Error Result Management

```python title="error_result_management.py"
from rdetoolkit.models.result import WorkflowExecutionStatus, WorkflowExecutionResults
from datetime import datetime

# Create error status
error_status = WorkflowExecutionStatus(
    status="error",
    message="Error occurred during file processing",
    timestamp=datetime.now(),
    execution_time=45.2,
    error_code="FILE_PROCESSING_ERROR",
    error_details={
        "error_type": "FileNotFoundError",
        "missing_file": "data/input/missing.csv",
        "stack_trace": "Traceback (most recent call last)..."
    }
)

# Create error results
error_results = WorkflowExecutionResults(
    run_id="workflow_error_001",
    status=error_status,
    input_files_count=3,
    output_files_count=0,
    processed_data_size=0,
    metadata={"experiment_id": "EXP002", "error_occurred": True}
)

print(f"Error execution ID: {error_results.run_id}")
print(f"Error code: {error_results.status.error_code}")
print(f"Error details: {error_results.status.error_details}")
```

### Execution Result Statistical Analysis

```python title="result_statistics.py"
from rdetoolkit.models.result import WorkflowResultManager, WorkflowExecutionStatus
from datetime import datetime, timedelta
import json

def analyze_workflow_results(manager: WorkflowResultManager) -> dict:
    """Statistical analysis of workflow execution results"""
    
    # Get results in JSON format
    results_json = manager.to_json()
    results_data = json.loads(results_json)
    
    total_runs = len(results_data)
    successful_runs = sum(1 for r in results_data if r.get("status", {}).get("status") == "success")
    failed_runs = total_runs - successful_runs
    
    total_execution_time = sum(r.get("status", {}).get("execution_time", 0) for r in results_data)
    avg_execution_time = total_execution_time / total_runs if total_runs > 0 else 0
    
    total_input_files = sum(r.get("input_files_count", 0) for r in results_data)
    total_output_files = sum(r.get("output_files_count", 0) for r in results_data)
    total_data_size = sum(r.get("processed_data_size", 0) for r in results_data)
    
    return {
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "success_rate": successful_runs / total_runs if total_runs > 0 else 0,
        "total_execution_time": total_execution_time,
        "average_execution_time": avg_execution_time,
        "total_input_files": total_input_files,
        "total_output_files": total_output_files,
        "total_data_processed": total_data_size
    }

# Create sample execution results
manager = WorkflowResultManager()

# Success examples
for i in range(5):
    status = WorkflowExecutionStatus(
        status="success",
        message="Success",
        timestamp=datetime.now() - timedelta(hours=i),
        execution_time=120.5 + i * 10
    )
    manager.add(f"run_{i+1:03d}", status, input_files=3+i, output_files=6+i*2, processed_data_size=512000*(i+1))

# Error example
error_status = WorkflowExecutionStatus(
    status="error",
    message="Error",
    timestamp=datetime.now(),
    execution_time=30.1,
    error_code="VALIDATION_ERROR"
)
manager.add("run_006", error_status, input_files=2, output_files=0, processed_data_size=0)

# Execute statistical analysis
stats = analyze_workflow_results(manager)

print("=== Workflow Execution Statistics ===")
print(f"Total executions: {stats['total_runs']}")
print(f"Successful executions: {stats['successful_runs']}")
print(f"Failed executions: {stats['failed_runs']}")
print(f"Success rate: {stats['success_rate']:.2%}")
print(f"Average execution time: {stats['average_execution_time']:.1f} seconds")
print(f"Total processed data size: {stats['total_data_processed']:,} bytes")
```
