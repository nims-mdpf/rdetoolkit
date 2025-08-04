# Report Generator API

## Purpose

This module defines report generation processing in RDEToolKit. It provides functionality for creating experimental result reports, data visualization, and security scanning.

## Key Features

### Report Generation
- Markdown template-based report generation
- Automatic report creation from experimental data
- Customizable report formats

### Security Scanning
- Code security scanning
- External connection scanning
- Security report generation

---

::: src.rdetoolkit.artifact.report.TemplateMarkdownReportGenerator

---

::: src.rdetoolkit.artifact.report.CodeSecurityScanner

---

::: src.rdetoolkit.artifact.report.ExternalConnScanner

---

::: src.rdetoolkit.artifact.report.get_scanner

---

## Practical Usage

### Basic Report Generation

```python title="basic_report_generation.py"
from rdetoolkit.artifact.report import TemplateMarkdownReportGenerator
from pathlib import Path

# Create report generator
generator = TemplateMarkdownReportGenerator()

# Prepare experimental data
experiment_data = {
    "experiment_id": "EXP001",
    "title": "Temperature Measurement Experiment",
    "researcher": "John Doe",
    "date": "2024-01-01",
    "measurements": [
        {"time": "09:00", "temperature": 25.0, "humidity": 60},
        {"time": "10:00", "temperature": 26.5, "humidity": 58},
        {"time": "11:00", "temperature": 28.0, "humidity": 55}
    ]
}

# Generate report
try:
    report_content = generator.generate(
        template_name="experiment_report",
        data=experiment_data
    )
    print(f"✓ Report generation completed")
    
    # Save report
    output_path = Path("reports/experiment_001_report.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    generator.save(report_content, str(output_path))
    print(f"✓ Report saved: {output_path}")
    
except Exception as e:
    print(f"✗ Report generation error: {e}")
```

### Security Scanning Execution

```python title="security_scanning.py"
from rdetoolkit.artifact.report import CodeSecurityScanner, ExternalConnScanner, get_scanner
from pathlib import Path

# Execute code security scan
code_scanner = CodeSecurityScanner()

# Single file scan
source_file = Path("src/rdetoolkit/workflows.py")
if source_file.exists():
    try:
        scan_result = code_scanner.scan_file(str(source_file))
        print(f"✓ File scan completed: {source_file}")
        print(f"Issues detected: {len(scan_result.get('issues', []))}")
        
    except Exception as e:
        print(f"✗ File scan error: {e}")

# Directory-wide scan
source_dir = Path("src/rdetoolkit")
if source_dir.exists():
    try:
        scan_results = code_scanner.scan(str(source_dir))
        print(f"✓ Directory scan completed: {source_dir}")
        
        # Get results
        results = code_scanner.get_results()
        print(f"Total scanned files: {results.get('total_files', 0)}")
        print(f"Total issues: {results.get('total_issues', 0)}")
        
    except Exception as e:
        print(f"✗ Directory scan error: {e}")

# Execute external connection scan
external_scanner = ExternalConnScanner()

try:
    external_results = external_scanner.scan(source_dir)
    print(f"✓ External connection scan completed")
    print(f"External connections detected: {len(external_results.get('connections', []))}")
    
except Exception as e:
    print(f"✗ External connection scan error: {e}")

# Get appropriate scanner
scanner = get_scanner("code_security")
if scanner:
    print(f"✓ Scanner acquisition successful: {type(scanner).__name__}")
else:
    print("✗ Scanner acquisition failed")
```

### Integrated Report System

```python title="integrated_report_system.py"
from rdetoolkit.artifact.report import (
    TemplateMarkdownReportGenerator, 
    CodeSecurityScanner, 
    ExternalConnScanner
)
from pathlib import Path
from datetime import datetime

class IntegratedReportSystem:
    """Integrated report system"""
    
    def __init__(self):
        self.report_generator = TemplateMarkdownReportGenerator()
        self.code_scanner = CodeSecurityScanner()
        self.external_scanner = ExternalConnScanner()
    
    def generate_comprehensive_report(self, project_dir: Path) -> dict:
        """Generate comprehensive project report"""
        
        report_data = {
            "project_name": project_dir.name,
            "scan_date": datetime.now().isoformat(),
            "code_security": {},
            "external_connections": {},
            "summary": {}
        }
        
        # Code security scan
        try:
            print("Executing code security scan...")
            self.code_scanner.scan(str(project_dir))
            security_results = self.code_scanner.get_results()
            
            report_data["code_security"] = {
                "total_files": security_results.get("total_files", 0),
                "total_issues": security_results.get("total_issues", 0),
                "high_severity": security_results.get("high_severity", 0),
                "medium_severity": security_results.get("medium_severity", 0),
                "low_severity": security_results.get("low_severity", 0)
            }
            
            print(f"✓ Security scan completed: {security_results.get('total_issues', 0)} issues detected")
            
        except Exception as e:
            print(f"✗ Security scan error: {e}")
            report_data["code_security"]["error"] = str(e)
        
        # External connection scan
        try:
            print("Executing external connection scan...")
            external_results = self.external_scanner.scan(project_dir)
            
            report_data["external_connections"] = {
                "total_connections": len(external_results.get("connections", [])),
                "unique_domains": len(set(conn.get("domain", "") for conn in external_results.get("connections", []))),
                "protocols": list(set(conn.get("protocol", "") for conn in external_results.get("connections", [])))
            }
            
            print(f"✓ External connection scan completed: {len(external_results.get('connections', []))} connections detected")
            
        except Exception as e:
            print(f"✗ External connection scan error: {e}")
            report_data["external_connections"]["error"] = str(e)
        
        # Generate summary
        report_data["summary"] = {
            "security_score": self._calculate_security_score(report_data["code_security"]),
            "external_risk_level": self._assess_external_risk(report_data["external_connections"]),
            "recommendations": self._generate_recommendations(report_data)
        }
        
        # Generate and save report
        try:
            report_content = self.report_generator.generate(
                template_name="security_report",
                data=report_data
            )
            
            report_file = project_dir / "reports" / f"security_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            report_file.parent.mkdir(parents=True, exist_ok=True)
            
            self.report_generator.save(report_content, str(report_file))
            
            report_data["report_file"] = str(report_file)
            print(f"✓ Integrated report saved: {report_file}")
            
        except Exception as e:
            print(f"✗ Report generation error: {e}")
            report_data["report_error"] = str(e)
        
        return report_data
    
    def _calculate_security_score(self, security_data: dict) -> int:
        """Calculate security score"""
        if "error" in security_data:
            return 0
        
        total_issues = security_data.get("total_issues", 0)
        high_severity = security_data.get("high_severity", 0)
        
        if total_issues == 0:
            return 100
        elif high_severity > 0:
            return max(0, 50 - high_severity * 10)
        else:
            return max(0, 80 - total_issues * 5)
    
    def _assess_external_risk(self, external_data: dict) -> str:
        """Assess external risk level"""
        if "error" in external_data:
            return "unknown"
        
        total_connections = external_data.get("total_connections", 0)
        
        if total_connections == 0:
            return "low"
        elif total_connections < 5:
            return "medium"
        else:
            return "high"
    
    def _generate_recommendations(self, report_data: dict) -> list:
        """Generate recommendations"""
        recommendations = []
        
        # Security-related recommendations
        security_score = report_data["summary"]["security_score"]
        if security_score < 70:
            recommendations.append("Prioritize fixing security issues")
        
        # External connection-related recommendations
        risk_level = report_data["summary"]["external_risk_level"]
        if risk_level == "high":
            recommendations.append("Consider reviewing external connections and strengthening security")
        
        if not recommendations:
            recommendations.append("Current security status is good")
        
        return recommendations

# Usage example
report_system = IntegratedReportSystem()
project_directory = Path(".")

print("=== Integrated Security Report Generation ===")
comprehensive_report = report_system.generate_comprehensive_report(project_directory)

print(f"\n=== Report Results ===")
print(f"Project: {comprehensive_report['project_name']}")
print(f"Security score: {comprehensive_report['summary']['security_score']}/100")
print(f"External risk level: {comprehensive_report['summary']['external_risk_level']}")
print(f"Recommendations: {', '.join(comprehensive_report['summary']['recommendations'])}")

if "report_file" in comprehensive_report:
    print(f"Detailed report: {comprehensive_report['report_file']}")
```
