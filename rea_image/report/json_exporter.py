"""JSON report exporter conforming strictly to Section 7 schema."""

import json
from pathlib import Path
from rea_image.schemas import ReportSchema


def export_report_json(report_data: ReportSchema, output_file: Path) -> Path:
    """Validate and write report.json with proper alias serialization ('global')."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Use by_alias=True to serialize 'global_analysis' as 'global'
    data_dict = report_data.model_dump(by_alias=True, mode="json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2, ensure_ascii=False)
        
    return output_file

