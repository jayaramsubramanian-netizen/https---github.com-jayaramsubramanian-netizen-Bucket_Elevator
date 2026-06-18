"""
Task 13 — main.py patch instructions
=====================================
Apply these 3 changes to YOUR main.py (the v1.1.0+ version you pasted).
Do NOT replace the entire file — your version has far more features.

CHANGE 1: Add after the existing ReportRequest class definition
───────────────────────────────────────────────────────────────
Find this block:
    class ReportRequest(BaseModel):
        results: dict
        inputs:  dict
        project: str | None = ""
        ref:     str | None = ""

Replace with:

    class SignOffPerson(BaseModel):
        name:        str = ""
        designation: str = ""
        date:        str = ""

    class SignOff(BaseModel):
        designed_by: SignOffPerson = SignOffPerson()
        reviewed_by: SignOffPerson = SignOffPerson()
        approved_by: SignOffPerson = SignOffPerson()

    class ReportRequest(BaseModel):
        results:  dict
        inputs:   dict
        project:  str | None = ""
        ref:      str | None = ""
        sign_off: Optional[SignOff] = None   # Task 13 — engineering sign-off


CHANGE 2: Update the generate_report endpoint function body
────────────────────────────────────────────────────────────
Find:
    @v1.post("/bucket-elevator/report")
    def generate_report(data: ReportRequest):
        \"\"\"Generate A4 portrait PDF engineering report.\"\"\"
        try:
            pdf = build_report(
                data.results, data.inputs,
                project=data.project or "",
                doc_ref=data.ref or "",
            )
        except Exception as e:
            _err("REPORT_ERROR", str(e), status=500)

Replace with:
    @v1.post("/bucket-elevator/report")
    def generate_report(data: ReportRequest):
        \"\"\"
        A4 PDF engineering report with optional engineering sign-off block.

        sign_off body field (optional):
            {
                "designed_by":  {"name": "...", "designation": "...", "date": "YYYY-MM-DD"},
                "reviewed_by":  {"name": "...", "designation": "...", "date": "YYYY-MM-DD"},
                "approved_by":  {"name": "...", "designation": "...", "date": "YYYY-MM-DD"}
            }
        \"\"\"
        try:
            sign_off_dict = None
            if data.sign_off:
                sign_off_dict = {
                    "designed_by": data.sign_off.designed_by.model_dump(),
                    "reviewed_by": data.sign_off.reviewed_by.model_dump(),
                    "approved_by": data.sign_off.approved_by.model_dump(),
                }
            pdf = build_report(
                data.results, data.inputs,
                project=data.project or "",
                doc_ref=data.ref or "",
                sign_off=sign_off_dict,
            )
        except Exception as e:
            _err("REPORT_ERROR", str(e), status=500)


CHANGE 3: No other changes needed — your main.py is complete.
"""
