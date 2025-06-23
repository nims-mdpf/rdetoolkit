# Result Module

The `rdetoolkit.models.result` module provides comprehensive models and utilities for managing workflow execution results and status tracking in RDE systems. This module implements structured handling of workflow execution data, error tracking, and result aggregation with JSON serialization support.

## Overview

The result module implements a complete workflow execution tracking system with the following capabilities:

- **Status Tracking**: Comprehensive tracking of workflow execution states and progress
- **Error Management**: Detailed error code, message, and stack trace capture
- **Result Aggregation**: Collection and management of multiple workflow execution results
- **JSON Serialization**: Built-in support for JSON export and import of execution data
- **Iteration Support**: Pythonic iteration and indexing over workflow results

## Core Classes

### WorkflowExecutionStatus

Model representing the execution status of a single workflow run.

#### WorkflowExecutionStatus Constructor

```python
WorkflowExecutionStatus(
    run_id: str,
    title: str,
    status: str,
    mode: str,
    error_code: int | None = None,
    error_message: str | None = None,
    target: str | None = None,
    stacktrace: str | None = None
)
```

**Parameters:**

- `run_id` (str): Unique identifier for the workflow run (automatically formatted to 4 digits)
- `title` (str): Descriptive title of the workflow execution
- `status` (str): Current execution status (e.g., "success", "failed", "running")
- `mode` (str): Processing mode used for the workflow
- `error_code` (int | None): Optional error code for failed executions
- `error_message` (str | None): Optional error message describing failures
- `target` (str | None): Optional target directory or resource path
- `stacktrace` (str | None): Optional detailed stack trace for debugging

#### Validation

- `run_id` is automatically formatted to a 4-digit zero-padded string (e.g., "1" becomes "0001")

#### Usage Example

```python
from rdetoolkit.models.result import WorkflowExecutionStatus

# Successful workflow execution
success_status = WorkflowExecutionStatus(
    run_id="1",
    title="Data Processing Pipeline",
    status="success",
    mode="batch",
    target="/output/data/processed"
)

# Failed workflow execution with error details
failed_status = WorkflowExecutionStatus(
    run_id="2",
    title="Image Analysis Workflow",
    status="failed",
    mode="interactive",
    error_code=500,
    error_message="Failed to process image data",
    target="/output/images",
    stacktrace="Traceback (most recent call last):\n  File 'image_processor.py', line 45..."
)

# Running workflow
running_status = WorkflowExecutionStatus(
    run_id="3",
    title="Large Dataset Analysis",
    status="running",
    mode="background"
)

print(success_status.run_id)  # "0001"
print(failed_status.error_code)  # 500
print(running_status.status)  # "running"
```

### WorkflowExecutionResults

Container model for managing collections of workflow execution statuses.

#### WorkflowExecutionResults Constructor

```python
WorkflowExecutionResults(statuses: list[WorkflowExecutionStatus])
```

**Parameters:**

- `statuses` (list[WorkflowExecutionStatus]): List of workflow execution status objects

#### Example

```python
from rdetoolkit.models.result import WorkflowExecutionResults, WorkflowExecutionStatus

# Create multiple statuses
statuses = [
    WorkflowExecutionStatus(
        run_id="1",
        title="First Workflow",
        status="success",
        mode="batch"
    ),
    WorkflowExecutionStatus(
        run_id="2",
        title="Second Workflow",
        status="failed",
        mode="interactive",
        error_code=404,
        error_message="Resource not found"
    )
]

# Create results container
results = WorkflowExecutionResults(statuses=statuses)

print(len(results.statuses))  # 2
print(results.statuses[0].title)  # "First Workflow"
```

### WorkflowResultManager

High-level manager class for workflow execution result tracking and manipulation.

#### Constructor

```python
WorkflowResultManager()
```

Initializes an empty workflow result manager with no execution statuses.

#### Methods

##### add(run_id, title, status, mode, error_code=None, error_message=None, target=None, stacktrace=None)

Add a new workflow execution status with individual parameters.

```python
def add(
    run_id: str,
    title: str,
    status: str,
    mode: str,
    error_code: int | None = None,
    error_message: str | None = None,
    target: str | None = None,
    stacktrace: str | None = None
) -> None
```

**Parameters:**

- `run_id` (str): Unique identifier for the workflow run
- `title` (str): Descriptive title of the workflow
- `status` (str): Execution status
- `mode` (str): Processing mode
- `error_code` (int | None): Optional error code
- `error_message` (str | None): Optional error message
- `target` (str | None): Optional target path
- `stacktrace` (str | None): Optional stack trace

**Example:**

```python
from rdetoolkit.models.result import WorkflowResultManager

manager = WorkflowResultManager()

# Add successful execution
manager.add(
    run_id="1",
    title="Data Validation",
    status="success",
    mode="validation",
    target="/data/validated"
)

# Add failed execution
manager.add(
    run_id="2",
    title="File Processing",
    status="failed",
    mode="processing",
    error_code=500,
    error_message="File not found: input.csv",
    stacktrace="FileNotFoundError: [Errno 2] No such file or directory: 'input.csv'"
)

print(len(manager))  # 2
```

##### add_status(status)

Add an existing WorkflowExecutionStatus object.

```python
def add_status(status: WorkflowExecutionStatus) -> None
```

**Parameters:**

- `status` (WorkflowExecutionStatus): Pre-created status object to add

**Example:**

```python
manager = WorkflowResultManager()

# Create status separately
status = WorkflowExecutionStatus(
    run_id="5",
    title="Custom Workflow",
    status="completed",
    mode="custom"
)

# Add the status object
manager.add_status(status)

print(manager[0].title)  # "Custom Workflow"
```

##### to_json()

Export the workflow execution results as JSON string.

```python
def to_json() -> str
```

**Returns:**

- `str`: JSON representation of all workflow execution results

**Example:**

```python
manager = WorkflowResultManager()
manager.add("1", "Test Workflow", "success", "test")

json_output = manager.to_json()
print(json_output)
# {
#   "statuses": [
#     {
#       "run_id": "0001",
#       "title": "Test Workflow",
#       "status": "success",
#       "mode": "test",
#       "error_code": null,
#       "error_message": null,
#       "target": null,
#       "stacktrace": null
#     }
#   ]
# }
```

#### Magic Methods

The WorkflowResultManager supports standard Python container operations:

##### \_\_iter\_\_()

```python
def __iter__() -> Iterator[WorkflowExecutionStatus]
```

**Returns:**

- `Iterator[WorkflowExecutionStatus]`: Iterator over workflow execution statuses

##### \_\_len\_\_()

```python
def __len__() -> int
```

**Returns:**

- `int`: Number of workflow execution statuses

##### \_\_getitem\_\_(index)

```python
def __getitem__(index: int) -> WorkflowExecutionStatus
```

**Parameters:**

- `index` (int): Index of the status to retrieve

**Returns:**

- `WorkflowExecutionStatus`: Status at the specified index

##### \_\_repr\_\_()

```python
def __repr__() -> str
```

**Returns:**

- `str`: String representation of the manager

#### Example of Magic Methods

```python
manager = WorkflowResultManager()
manager.add("1", "First", "success", "mode1")
manager.add("2", "Second", "failed", "mode2", error_code=404)

# Iteration
for status in manager:
    print(f"{status.run_id}: {status.status}")
# Output:
# 0001: success
# 0002: failed

# Length
print(len(manager))  # 2

# Indexing
first_status = manager[0]
print(first_status.title)  # "First"

# String representation
print(repr(manager))  # WorkflowResultManager(WorkflowExecutionResults(...))
```

## Complete Usage Examples

### Basic Workflow Tracking

```python
from rdetoolkit.models.result import WorkflowResultManager
import traceback

def run_data_processing_pipeline():
    """Example of comprehensive workflow tracking."""

    manager = WorkflowResultManager()

    # Track data validation step
    try:
        # Simulate data validation
        print("Validating input data...")
        # validation_logic()

        manager.add(
            run_id="1",
            title="Data Validation",
            status="success",
            mode="validation",
            target="/data/validated"
        )

    except Exception as e:
        manager.add(
            run_id="1",
            title="Data Validation",
            status="failed",
            mode="validation",
            error_code=400,
            error_message=str(e),
            stacktrace=traceback.format_exc()
        )

    # Track data transformation step
    try:
        print("Transforming data...")
        # transformation_logic()

        manager.add(
            run_id="2",
            title="Data Transformation",
            status="success",
            mode="transformation",
            target="/data/transformed"
        )

    except Exception as e:
        manager.add(
            run_id="2",
            title="Data Transformation",
            status="failed",
            mode="transformation",
            error_code=500,
            error_message=str(e),
            stacktrace=traceback.format_exc()
        )

    # Track analysis step
    try:
        print("Running analysis...")
        # analysis_logic()

        manager.add(
            run_id="3",
            title="Data Analysis",
            status="success",
            mode="analysis",
            target="/data/results"
        )

    except Exception as e:
        manager.add(
            run_id="3",
            title="Data Analysis",
            status="failed",
            mode="analysis",
            error_code=500,
            error_message=str(e),
            stacktrace=traceback.format_exc()
        )

    return manager

# Execute pipeline and get results
results = run_data_processing_pipeline()

# Display summary
print(f"\nPipeline completed with {len(results)} steps:")
for status in results:
    print(f"  {status.run_id}: {status.title} - {status.status}")

# Save results
with open("pipeline_results.json", "w") as f:
    f.write(results.to_json())
```

### Advanced Error Tracking and Recovery

```python
from rdetoolkit.models.result import WorkflowResultManager, WorkflowExecutionStatus
import time
from datetime import datetime
from pathlib import Path

class AdvancedWorkflowTracker:
    """Advanced workflow tracker with error recovery and retries."""

    def __init__(self, workflow_name: str):
        self.workflow_name = workflow_name
        self.manager = WorkflowResultManager()
        self.start_time = datetime.now()

    def execute_step(self, step_id: str, step_name: str, step_function, mode: str = "default", max_retries: int = 3):
        """Execute a workflow step with retry logic and comprehensive tracking."""

        for attempt in range(max_retries + 1):
            try:
                print(f"Executing {step_name} (attempt {attempt + 1}/{max_retries + 1})")

                # Execute the step function
                result = step_function()

                # Success - record and return
                self.manager.add(
                    run_id=step_id,
                    title=step_name,
                    status="success",
                    mode=mode,
                    target=str(result) if result else None
                )

                print(f"✅ {step_name} completed successfully")
                return result

            except Exception as e:
                error_msg = f"Attempt {attempt + 1} failed: {str(e)}"
                print(f"❌ {error_msg}")

                if attempt == max_retries:
                    # Final failure - record and raise
                    self.manager.add(
                        run_id=step_id,
                        title=step_name,
                        status="failed",
                        mode=mode,
                        error_code=getattr(e, 'errno', 500),
                        error_message=str(e),
                        stacktrace=traceback.format_exc()
                    )
                    raise
                else:
                    # Retry - record attempt
                    self.manager.add(
                        run_id=f"{step_id}_retry_{attempt}",
                        title=f"{step_name} (Retry {attempt + 1})",
                        status="retry",
                        mode=mode,
                        error_code=getattr(e, 'errno', 500),
                        error_message=error_msg
                    )
                    time.sleep(2 ** attempt)  # Exponential backoff

    def get_summary(self) -> dict:
        """Get comprehensive workflow execution summary."""

        total_steps = len(self.manager)
        successful_steps = sum(1 for status in self.manager if status.status == "success")
        failed_steps = sum(1 for status in self.manager if status.status == "failed")
        retry_attempts = sum(1 for status in self.manager if status.status == "retry")

        return {
            "workflow_name": self.workflow_name,
            "start_time": self.start_time.isoformat(),
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "retry_attempts": retry_attempts,
            "success_rate": (successful_steps / max(successful_steps + failed_steps, 1)) * 100,
            "execution_details": [
                {
                    "run_id": status.run_id,
                    "title": status.title,
                    "status": status.status,
                    "mode": status.mode,
                    "has_errors": status.error_code is not None
                }
                for status in self.manager
            ]
        }

    def save_detailed_report(self, output_path: Path):
        """Save detailed execution report."""

        summary = self.get_summary()

        report = {
            "summary": summary,
            "detailed_results": self.manager.to_json()
        }

        with open(output_path, "w") as f:
            import json
            json.dump(report, f, indent=2, default=str)

# Example usage with retry logic
def unreliable_data_processing():
    """Simulate unreliable data processing that might fail."""
    import random

    if random.random() < 0.3:  # 30% chance of failure
        raise ValueError("Random processing error")

    return "/data/processed/output.json"

def reliable_validation():
    """Simulate reliable validation step."""
    return "/data/validated/schema.json"

# Execute advanced workflow
tracker = AdvancedWorkflowTracker("Data Processing Pipeline v2")

try:
    # Execute steps with different retry policies
    tracker.execute_step("001", "Data Validation", reliable_validation, "validation", max_retries=1)
    tracker.execute_step("002", "Data Processing", unreliable_data_processing, "processing", max_retries=3)

    print("\n✅ Workflow completed successfully!")

except Exception as e:
    print(f"\n❌ Workflow failed: {e}")

finally:
    # Generate and save report
    summary = tracker.get_summary()
    print(f"\nWorkflow Summary:")
    print(f"  Total steps: {summary['total_steps']}")
    print(f"  Successful: {summary['successful_steps']}")
    print(f"  Failed: {summary['failed_steps']}")
    print(f"  Retries: {summary['retry_attempts']}")
    print(f"  Success rate: {summary['success_rate']:.1f}%")

    tracker.save_detailed_report(Path("detailed_workflow_report.json"))
```

### Workflow Result Analysis and Reporting

```python
from rdetoolkit.models.result import WorkflowResultManager, WorkflowExecutionStatus
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

class WorkflowAnalyzer:
    """Analyzer for workflow execution results and patterns."""

    def __init__(self):
        self.results_cache = {}

    def load_results_from_json(self, file_path: Path) -> WorkflowResultManager:
        """Load workflow results from JSON file."""

        with open(file_path, 'r') as f:
            data = json.load(f)

        # Handle both direct WorkflowExecutionResults and nested structures
        if "statuses" in data:
            statuses_data = data["statuses"]
        elif "detailed_results" in data:
            detailed_data = json.loads(data["detailed_results"])
            statuses_data = detailed_data["statuses"]
        else:
            statuses_data = data

        manager = WorkflowResultManager()

        for status_data in statuses_data:
            status = WorkflowExecutionStatus(**status_data)
            manager.add_status(status)

        return manager

    def analyze_failure_patterns(self, manager: WorkflowResultManager) -> dict:
        """Analyze common failure patterns in workflow results."""

        analysis = {
            "total_executions": len(manager),
            "failure_count": 0,
            "success_count": 0,
            "error_codes": defaultdict(int),
            "failure_by_mode": defaultdict(int),
            "failure_by_title": defaultdict(int),
            "common_error_messages": defaultdict(int),
            "steps_with_stacktraces": []
        }

        for status in manager:
            if status.status == "failed":
                analysis["failure_count"] += 1

                if status.error_code:
                    analysis["error_codes"][status.error_code] += 1

                analysis["failure_by_mode"][status.mode] += 1
                analysis["failure_by_title"][status.title] += 1

                if status.error_message:
                    # Simplify error message for pattern matching
                    simplified_msg = status.error_message.split(':')[0] if ':' in status.error_message else status.error_message
                    analysis["common_error_messages"][simplified_msg] += 1

                if status.stacktrace:
                    analysis["steps_with_stacktraces"].append({
                        "run_id": status.run_id,
                        "title": status.title,
                        "error": status.error_message
                    })

            elif status.status == "success":
                analysis["success_count"] += 1

        # Calculate success rate
        total_completed = analysis["failure_count"] + analysis["success_count"]
        analysis["success_rate"] = (analysis["success_count"] / max(total_completed, 1)) * 100

        return analysis

    def generate_failure_report(self, analysis: dict) -> str:
        """Generate human-readable failure analysis report."""

        report = f"""
WORKFLOW FAILURE ANALYSIS REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERVIEW:
- Total executions: {analysis['total_executions']}
- Successful executions: {analysis['success_count']}
- Failed executions: {analysis['failure_count']}
- Success rate: {analysis['success_rate']:.1f}%

ERROR CODE DISTRIBUTION:
"""

        for error_code, count in sorted(analysis['error_codes'].items()):
            report += f"- Error {error_code}: {count} occurrences\n"

        report += "\nFAILURES BY MODE:\n"
        for mode, count in sorted(analysis['failure_by_mode'].items(), key=lambda x: x[1], reverse=True):
            report += f"- {mode}: {count} failures\n"

        report += "\nFAILURES BY STEP:\n"
        for title, count in sorted(analysis['failure_by_title'].items(), key=lambda x: x[1], reverse=True):
            report += f"- {title}: {count} failures\n"

        report += "\nCOMMON ERROR PATTERNS:\n"
        for error_msg, count in sorted(analysis['common_error_messages'].items(), key=lambda x: x[1], reverse=True)[:5]:
            report += f"- {error_msg}: {count} occurrences\n"

        if analysis['steps_with_stacktraces']:
            report += f"\nSTEPS WITH DETAILED STACKTRACES: {len(analysis['steps_with_stacktraces'])}\n"
            for step in analysis['steps_with_stacktraces'][:3]:  # Show first 3
                report += f"- {step['run_id']}: {step['title']} - {step['error']}\n"

        return report

    def compare_workflow_runs(self, managers: list[WorkflowResultManager]) -> dict:
        """Compare multiple workflow runs to identify trends."""

        comparison = {
            "run_count": len(managers),
            "average_steps": sum(len(m) for m in managers) / len(managers),
            "success_rates": [],
            "most_reliable_steps": defaultdict(int),
            "least_reliable_steps": defaultdict(int),
            "improvement_trend": None
        }

        for manager in managers:
            analysis = self.analyze_failure_patterns(manager)
            comparison["success_rates"].append(analysis["success_rate"])

            # Track step reliability
            for status in manager:
                if status.status == "success":
                    comparison["most_reliable_steps"][status.title] += 1
                elif status.status == "failed":
                    comparison["least_reliable_steps"][status.title] += 1

        # Calculate improvement trend
        if len(comparison["success_rates"]) >= 2:
            recent_rate = sum(comparison["success_rates"][-3:]) / min(3, len(comparison["success_rates"]))
            earlier_rate = sum(comparison["success_rates"][:-3]) / max(1, len(comparison["success_rates"]) - 3)
            comparison["improvement_trend"] = recent_rate - earlier_rate

        return comparison

# Example usage
analyzer = WorkflowAnalyzer()

# Create sample workflow results for analysis
def create_sample_results():
    """Create sample workflow results for testing."""

    managers = []

    for run in range(3):
        manager = WorkflowResultManager()

        # Add various execution results
        manager.add(f"{run*10 + 1}", "Data Validation", "success", "validation")
        manager.add(f"{run*10 + 2}", "Data Processing", "failed" if run == 1 else "success", "processing",
                   error_code=500 if run == 1 else None,
                   error_message="Memory allocation failed" if run == 1 else None)
        manager.add(f"{run*10 + 3}", "Result Generation", "success", "output")

        managers.append(manager)

    return managers

# Analyze sample results
sample_managers = create_sample_results()

# Individual analysis
for i, manager in enumerate(sample_managers):
    analysis = analyzer.analyze_failure_patterns(manager)
    print(f"Run {i+1} Analysis:")
    print(f"  Success rate: {analysis['success_rate']:.1f}%")
    print(f"  Failures: {analysis['failure_count']}")

# Comparative analysis
comparison = analyzer.compare_workflow_runs(sample_managers)
print(f"\nComparative Analysis:")
print(f"  Average steps per run: {comparison['average_steps']:.1f}")
print(f"  Success rates: {[f'{rate:.1f}%' for rate in comparison['success_rates']]}")

if comparison["improvement_trend"]:
    trend_word = "improving" if comparison["improvement_trend"] > 0 else "declining"
    print(f"  Trend: {trend_word} ({comparison['improvement_trend']:+.1f}%)")
```

### Integration with Monitoring Systems

```python
from rdetoolkit.models.result import WorkflowResultManager, WorkflowExecutionStatus
import requests
import json
from datetime import datetime

class WorkflowMonitoringIntegration:
    """Integration with external monitoring and alerting systems."""

    def __init__(self, webhook_url: str = None, slack_webhook: str = None):
        self.webhook_url = webhook_url
        self.slack_webhook = slack_webhook
        self.manager = WorkflowResultManager()

    def add_with_monitoring(self, run_id: str, title: str, status: str, mode: str, **kwargs):
        """Add workflow status with automatic monitoring notifications."""

        # Add to manager
        self.manager.add(run_id, title, status, mode, **kwargs)

        # Send notifications based on status
        if status == "failed":
            self._send_failure_alert(run_id, title, kwargs.get('error_message'))
        elif status == "success":
            self._send_success_notification(run_id, title)

    def _send_failure_alert(self, run_id: str, title: str, error_message: str = None):
        """Send failure alert to monitoring systems."""

        alert_data = {
            "timestamp": datetime.now().isoformat(),
            "severity": "error",
            "service": "workflow_execution",
            "run_id": run_id,
            "title": title,
            "message": error_message or "Workflow execution failed",
            "alert_type": "workflow_failure"
        }

        # Send to generic webhook
        if self.webhook_url:
            try:
                requests.post(self.webhook_url, json=alert_data, timeout=5)
            except Exception as e:
                print(f"Failed to send webhook alert: {e}")

        # Send to Slack
        if self.slack_webhook:
            slack_message = {
                "text": f"🚨 Workflow Failure Alert",
                "attachments": [
                    {
                        "color": "danger",
                        "fields": [
                            {"title": "Run ID", "value": run_id, "short": True},
                            {"title": "Title", "value": title, "short": True},
                            {"title": "Error", "value": error_message or "Unknown error", "short": False}
                        ]
                    }
                ]
            }

            try:
                requests.post(self.slack_webhook, json=slack_message, timeout=5)
            except Exception as e:
                print(f"Failed to send Slack alert: {e}")

    def _send_success_notification(self, run_id: str, title: str):
        """Send success notification (if configured for verbose monitoring)."""

        # Typically only send success notifications for important workflows
        if "critical" in title.lower() or "production" in title.lower():
            success_data = {
                "timestamp": datetime.now().isoformat(),
                "severity": "info",
                "service": "workflow_execution",
                "run_id": run_id,
                "title": title,
                "message": "Critical workflow completed successfully",
                "alert_type": "workflow_success"
            }

            if self.webhook_url:
                try:
                    requests.post(self.webhook_url, json=success_data, timeout=5)
                except Exception as e:
                    print(f"Failed to send success notification: {e}")

    def generate_health_check_report(self) -> dict:
        """Generate health check report for monitoring systems."""

        now = datetime.now()
        recent_failures = sum(1 for status in self.manager
                            if status.status == "failed")

        total_executions = len(self.manager)
        success_rate = 0 if total_executions == 0 else \
                      (total_executions - recent_failures) / total_executions * 100

        health_status = "healthy"
        if success_rate < 50:
            health_status = "critical"
        elif success_rate < 80:
            health_status = "warning"

        return {
            "timestamp": now.isoformat(),
            "service": "workflow_execution",
            "status": health_status,
            "metrics": {
                "total_executions": total_executions,
                "recent_failures": recent_failures,
                "success_rate": success_rate
            },
            "recent_executions": [
                {
                    "run_id": status.run_id,
                    "title": status.title,
                    "status": status.status,
                    "mode": status.mode
                }
                for status in list(self.manager)[-5:]  # Last 5 executions
            ]
        }

# Example usage with monitoring
monitor = WorkflowMonitoringIntegration(
    webhook_url="https://monitoring.example.com/webhook",
    slack_webhook="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
)

# Simulate workflow executions with monitoring
monitor.add_with_monitoring("001", "Critical Data Backup", "success", "backup")
monitor.add_with_monitoring("002", "User Data Processing", "failed", "processing",
                          error_code=500, error_message="Database connection timeout")
monitor.add_with_monitoring("003", "Report Generation", "success", "reporting")

# Generate health check
health_report = monitor.generate_health_check_report()
print("Health Check Report:")
print(json.dumps(health_report, indent=2))
```

## Best Practices

1. **Use Meaningful Run IDs**: Create systematic run ID schemes:

   ```python
   # Good - includes date and sequence
   run_id = f"{datetime.now().strftime('%Y%m%d')}_{sequence:03d}"

   # Good - includes workflow type
   run_id = f"validation_{run_number}"
   ```

2. **Provide Descriptive Titles**: Include context in workflow titles:

   ```python
   # Good
   title = "Customer Data ETL Pipeline - Weekly Batch"

   # Avoid
   title = "Pipeline"
   ```

3. **Standardize Status Values**: Use consistent status terminology:

   ```python
   VALID_STATUSES = ["success", "failed", "running", "queued", "cancelled"]
   ```

4. **Include Relevant Target Information**: Store output paths and resources:

   ```python
   manager.add(
       run_id="001",
       title="Data Export",
       status="success",
       mode="export",
       target="/exports/customer_data_2025_01_15.csv"
   )
   ```

5. **Capture Complete Error Information**: Include both error messages and stack traces:

   ```python
   try:
       risky_operation()
   except Exception as e:
       manager.add(
           run_id="002",
           title="Risky Operation",
           status="failed",
           mode="processing",
           error_code=getattr(e, 'errno', 500),
           error_message=str(e),
           stacktrace=traceback.format_exc()
       )
   ```

## Error Handling

### Validation Errors

```python
from rdetoolkit.models.result import WorkflowExecutionStatus
from pydantic import ValidationError

def safe_create_status(run_id, title, status, mode, **kwargs):
    """Safely create workflow status with validation."""

    try:
        return WorkflowExecutionStatus(
            run_id=run_id,
            title=title,
            status=status,
            mode=mode,
            **kwargs
        )
    except ValidationError as e:
        print(f"Validation error creating status: {e}")
        return None

# Example with validation
valid_status = safe_create_status("1", "Test", "success", "test")
invalid_status = safe_create_status(None, "Test", "success", "test")  # Invalid run_id

print(f"Valid status created: {valid_status is not None}")    # True
print(f"Invalid status created: {invalid_status is not None}") # False
```

## See Also

- [Pydantic Documentation](https://docs.pydantic.dev/) - For model validation and serialization
- [Workflow Management](https://airflow.apache.org/) - For workflow orchestration systems
- [Monitoring Integration](https://prometheus.io/) - For metrics and monitoring systems
- [JSON Schema](https://json-schema.org/) - For result format validation
