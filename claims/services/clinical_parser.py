import csv
import openpyxl
from datetime import datetime
from django.core.exceptions import ValidationError
from claims.models import ClinicalEvent, RiskScore
from clients.models import Client
from hospitals.models import Hospital


# claims/services/clinical_parser.py
import pandas as pd
from claims.models import ClinicalEvent, RiskScore
from clients.models import Client
from hospitals.models import Hospital
# claims/services/clinical_parser.py
import csv
import openpyxl
import pandas as pd
from datetime import datetime
from django.core.exceptions import ValidationError
from openpyxl.utils.datetime import from_excel

from claims.models import ClinicalEvent, RiskScore
from clients.models import Client
from hospitals.models import Hospital


# -------------------------------
# Utility Functions
# -------------------------------
def parse_date(date_input):
    """Convert CSV/Excel string/float/datetime to Python date."""
    if isinstance(date_input, datetime):
        return date_input.date()
    if isinstance(date_input, float):  # Excel date float
        return from_excel(date_input).date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(date_input), fmt).date()
        except ValueError:
            continue
    raise ValidationError(f"Invalid date format: {date_input}")


def determine_risk_level(score):
    """Convert numeric score to LOW/MEDIUM/HIGH."""
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "LOW"
    if score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    else:
        return "LOW"


def get_risk_types(visit_type: str, notes: str = ""):
    """
    Auto-detect risk types based on visit type or notes.
    Returns list: ['maternal', 'neonatal']
    """
    visit_type = (visit_type or "").upper()
    notes = (notes or "").upper()
    risk_types = []

    if visit_type in ["ANC", "DELIVERY", "PNC"]:
        risk_types.append("maternal")
    if "CHILD" in notes or visit_type == "PNC":
        risk_types.append("neonatal")
    if not risk_types:
        risk_types.append("maternal")  # default
    return risk_types


# -------------------------------
# CSV Parser
# -------------------------------
def parse_clinical_csv(file, hospital: Hospital):
    """
    Parse uploaded CSV and create ClinicalEvent + RiskScore.
    Expects columns:
      - client_id, visit_date, visit_type, notes, risk_type, score
    """
    decoded = file.read().decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    results = {"created_events": 0, "created_risks": 0, "errors": [], "skipped_rows": []}

    for idx, row in enumerate(reader, start=2):
        client_id = row.get("client_id")
        visit_date = row.get("visit_date")
        visit_type = row.get("visit_type", "OTHER")
        notes = row.get("notes", "")
        score = row.get("score", 0)

        # Validate client
        client = Client.objects.filter(id=client_id).first()
        if not client:
            results["errors"].append(f"Row {idx}: Client ID {client_id} not found.")
            results["skipped_rows"].append(idx)
            continue

        # Parse date
        try:
            visit_date_parsed = parse_date(visit_date)
        except ValidationError as e:
            results["errors"].append(f"Row {idx}: {e}")
            results["skipped_rows"].append(idx)
            continue

        # Create ClinicalEvent
        event = ClinicalEvent.objects.create(
            client=client,
            hospital=hospital,
            visit_type=visit_type.upper(),
            notes=notes,
            source="upload",
            event_datetime=visit_date_parsed,
        )
        results["created_events"] += 1

        # Determine risk types automatically
        risk_types = get_risk_types(visit_type, notes)
        risk_objects = [
            RiskScore(
                event=event,
                type=rtype,
                score=float(score) if score else 0.0,
                level=determine_risk_level(score)
            ) for rtype in risk_types
        ]
        RiskScore.objects.bulk_create(risk_objects)
        results["created_risks"] += len(risk_objects)

    return results


# -------------------------------
# XLSX Parser
# -------------------------------
def parse_clinical_xlsx(file, hospital: Hospital):
    """
    Parse Excel file and create ClinicalEvent + RiskScore.
    """
    wb = openpyxl.load_workbook(file)
    sheet = wb.active
    results = {"created_events": 0, "created_risks": 0, "errors": [], "skipped_rows": []}

    headers = [str(cell.value).strip().lower() for cell in sheet[1]]
    header_map = {h: i for i, h in enumerate(headers)}

    required_columns = ["client_id", "visit_date"]
    for col in required_columns:
        if col not in header_map:
            results["errors"].append(f"Missing required column: {col}")
            return results

    for idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
        try:
            client_id = row[header_map["client_id"]].value
            visit_date = row[header_map["visit_date"]].value
            visit_type = row[header_map.get("visit_type", 2)].value or "OTHER"
            notes = row[header_map.get("notes", 3)].value or ""
            score = row[header_map.get("score", 4)].value or 0

            # Validate client
            client = Client.objects.filter(id=client_id).first()
            if not client:
                results["errors"].append(f"Row {idx}: Client ID {client_id} not found.")
                results["skipped_rows"].append(idx)
                continue

            # Parse date
            try:
                visit_date_parsed = parse_date(visit_date)
            except ValidationError as e:
                results["errors"].append(f"Row {idx}: {e}")
                results["skipped_rows"].append(idx)
                continue

            # Create ClinicalEvent
            event = ClinicalEvent.objects.create(
                client=client,
                hospital=hospital,
                visit_type=visit_type.upper(),
                notes=notes,
                source="upload",
                event_datetime=visit_date_parsed,
            )
            results["created_events"] += 1

            # Determine risk types
            risk_types = get_risk_types(visit_type, notes)
            risk_objects = [
                RiskScore(
                    event=event,
                    type=rtype,
                    score=float(score) if score else 0.0,
                    level=determine_risk_level(score)
                ) for rtype in risk_types
            ]
            RiskScore.objects.bulk_create(risk_objects)
            results["created_risks"] += len(risk_objects)

        except Exception as e:
            results["errors"].append(f"Row {idx}: {e}")
            results["skipped_rows"].append(idx)

    return results


# -------------------------------
# Unified Parser
# -------------------------------
def parse_clinical_file(file, hospital: Hospital):
    """
    Auto-detect CSV/XLSX and parse accordingly.
    Returns a dictionary of results.
    """
    name = file.name.lower()
    if name.endswith(".csv"):
        return parse_clinical_csv(file, hospital)
    elif name.endswith((".xlsx", ".xls")):
        return parse_clinical_xlsx(file, hospital)
    else:
        return {"created_events": 0, "created_risks": 0, "errors": ["Unsupported file type. Use CSV or XLSX."], "skipped_rows": []}
