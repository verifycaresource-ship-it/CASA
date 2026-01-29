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

def parse_structured_file(file_obj, hospital: Hospital):
    """
    Parses an uploaded structured file (CSV or Excel)
    containing clinical events and risk scores.
    
    Expected columns:
      - client_id
      - visit_type
      - notes
      - maternal_risk_score
      - neonatal_risk_score
      - event_datetime (optional, default now)
    
    Returns: list of created ClinicalEvent objects
    """
    # Determine file type
    if file_obj.name.endswith('.csv'):
        df = pd.read_csv(file_obj)
    elif file_obj.name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file_obj)
    else:
        raise ValueError("Unsupported file type. Use CSV or Excel.")

    created_events = []

    for _, row in df.iterrows():
        client = Client.objects.filter(id=row.get("client_id")).first()
        if not client:
            continue  # skip invalid client

        event_datetime = row.get("event_datetime") or pd.Timestamp.now()
        visit_type = row.get("visit_type", "OTHER")
        notes = row.get("notes", "")

        # Create ClinicalEvent
        event = ClinicalEvent.objects.create(
            client=client,
            hospital=hospital,
            visit_type=visit_type,
            notes=notes,
            source="upload",
            event_datetime=event_datetime
        )

        # Create RiskScores
        maternal_score = row.get("maternal_risk_score", 0.0)
        neonatal_score = row.get("neonatal_risk_score", 0.0)

        RiskScore.objects.bulk_create([
            RiskScore(event=event, type="maternal", score=maternal_score, level="LOW" if maternal_score < 5 else "HIGH"),
            RiskScore(event=event, type="neonatal", score=neonatal_score, level="LOW" if neonatal_score < 5 else "HIGH"),
        ])

        created_events.append(event)

    return created_events

# -------------------------------
# Utility functions
# -------------------------------
def parse_date(date_str):
    """
    Convert a string to a datetime.date object.
    Accepts: 'YYYY-MM-DD', 'DD/MM/YYYY', or Excel dates.
    """
    if isinstance(date_str, datetime):
        return date_str.date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(date_str), fmt).date()
        except ValueError:
            continue
    raise ValidationError(f"Invalid date format: {date_str}")


def determine_risk_level(score):
    """
    Determine risk level automatically based on numeric score.
    Customize thresholds if needed.
    """
    try:
        score = float(score)
    except ValueError:
        return "LOW"
    if score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    else:
        return "LOW"


# -------------------------------
# CSV Parser
# -------------------------------
def parse_clinical_csv(file, hospital: Hospital):
    """
    Parse uploaded CSV file and create ClinicalEvent + RiskScore entries.
    Expects columns:
      - client_id, visit_date, visit_type, doctor_name, department, notes
      - risk_type, score
    """
    decoded = file.read().decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    results = {"created_events": 0, "created_risks": 0, "errors": []}

    for idx, row in enumerate(reader, start=2):  # Start at 2 to account for header row
        client_id = row.get("client_id")
        visit_date = row.get("visit_date")
        visit_type = row.get("visit_type", "OTHER")
        doctor_name = row.get("doctor_name", "")
        department = row.get("department", "")
        notes = row.get("notes", "")
        risk_type = row.get("risk_type", "").lower()
        score = row.get("score", 0)

        # Validate client
        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            results["errors"].append(f"Row {idx}: Client ID {client_id} not found.")
            continue

        # Validate date
        try:
            visit_date_parsed = parse_date(visit_date)
        except ValidationError as e:
            results["errors"].append(f"Row {idx}: {e}")
            continue

        # Create ClinicalEvent
        event = ClinicalEvent.objects.create(
            client=client,
            hospital=hospital,
            visit_type=visit_type.upper(),
            notes=notes,
            doctor_name=doctor_name,
            department=department,
            event_datetime=visit_date_parsed,
            source="upload",
        )
        results["created_events"] += 1

        # Create RiskScore if provided
        if risk_type and score != "":
            RiskScore.objects.create(
                event=event,
                type=risk_type,
                score=float(score),
                level=determine_risk_level(score),
            )
            results["created_risks"] += 1

    return results


# -------------------------------
# XLSX Parser
# -------------------------------
def parse_clinical_xlsx(file, hospital: Hospital):
    """
    Parse Excel file and create ClinicalEvent + RiskScore entries.
    """
    wb = openpyxl.load_workbook(file)
    sheet = wb.active

    results = {"created_events": 0, "created_risks": 0, "errors": []}

    headers = [cell.value for cell in sheet[1]]
    header_map = {h.lower(): i for i, h in enumerate(headers)}

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
            doctor_name = row[header_map.get("doctor_name", 3)].value or ""
            department = row[header_map.get("department", 4)].value or ""
            notes = row[header_map.get("notes", 5)].value or ""
            risk_type = row[header_map.get("risk_type", 6)].value
            score = row[header_map.get("score", 7)].value or 0

            # Validate client
            try:
                client = Client.objects.get(id=client_id)
            except Client.DoesNotExist:
                results["errors"].append(f"Row {idx}: Client ID {client_id} not found.")
                continue

            # Validate date
            try:
                visit_date_parsed = parse_date(visit_date)
            except ValidationError as e:
                results["errors"].append(f"Row {idx}: {e}")
                continue

            # Create ClinicalEvent
            event = ClinicalEvent.objects.create(
                client=client,
                hospital=hospital,
                visit_type=visit_type.upper(),
                notes=notes,
                doctor_name=doctor_name,
                department=department,
                event_datetime=visit_date_parsed,
                source="upload",
            )
            results["created_events"] += 1

            # Create RiskScore if provided
            if risk_type and score != "":
                RiskScore.objects.create(
                    event=event,
                    type=risk_type.lower(),
                    score=float(score),
                    level=determine_risk_level(score),
                )
                results["created_risks"] += 1

        except Exception as e:
            results["errors"].append(f"Row {idx}: {e}")

    return results


# -------------------------------
# Unified Parser
# -------------------------------
def parse_clinical_file(file, hospital: Hospital):
    """
    Detect file type (CSV or XLSX) and parse accordingly.
    """
    name = file.name.lower()
    if name.endswith(".csv"):
        return parse_clinical_csv(file, hospital)
    elif name.endswith((".xlsx", ".xls")):
        return parse_clinical_xlsx(file, hospital)
    else:
        return {"created_events": 0, "created_risks": 0, "errors": ["Unsupported file type. Use CSV or XLSX."]}
