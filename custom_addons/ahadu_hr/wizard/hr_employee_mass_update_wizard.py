import base64
import csv
import io
import datetime
import logging
from dateutil import parser as date_parser

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Try importing Excel libraries
try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import xlrd
except ImportError:
    xlrd = None


class HrEmployeeMassUpdateWizard(models.TransientModel):
    _name = "hr.employee.mass.update.wizard"
    _description = "Mass Update Employee Fields"

    file_data = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def _extract_data_from_file(self):
        """Reads the uploaded CSV or Excel file and returns headers and raw rows."""
        file_name = (self.file_name or "").lower()
        file_content = base64.b64decode(self.file_data)

        headers = []
        data_rows = []

        try:
            # ---------------------------
            # PROCESS CSV FILE
            # ---------------------------
            if file_name.endswith(".csv"):
                csv_data = file_content.decode("utf-8-sig")
                input_file = io.StringIO(csv_data)
                reader = csv.DictReader(input_file)
                headers = [h.strip() for h in reader.fieldnames if h]
                for row in reader:
                    data_rows.append(
                        {
                            k.strip(): v.strip() if isinstance(v, str) else v
                            for k, v in row.items()
                            if k
                        }
                    )

            # ---------------------------
            # PROCESS EXCEL (.xlsx) FILE
            # ---------------------------
            elif file_name.endswith(".xlsx"):
                if not openpyxl:
                    raise UserError(
                        _(
                            "Python library 'openpyxl' is missing. Please ask your admin to install it or use CSV."
                        )
                    )

                wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
                sheet = wb.active
                rows = sheet.iter_rows(values_only=True)

                raw_headers = next(rows, None)
                if not raw_headers:
                    raise UserError(_("The Excel file appears to be empty."))

                headers = [str(h).strip() for h in raw_headers if h is not None]

                for row in rows:
                    row_dict = {}
                    for idx, header in enumerate(headers):
                        val = row[idx] if idx < len(row) else ""
                        if val is None:
                            val = ""
                        elif isinstance(val, str):
                            val = val.strip()
                        row_dict[header] = val
                    data_rows.append(row_dict)

            # ---------------------------
            # PROCESS OLD EXCEL (.xls) FILE
            # ---------------------------
            elif file_name.endswith(".xls"):
                if not xlrd:
                    raise UserError(
                        _(
                            "Python library 'xlrd' is missing. Please ask your admin to install it or use CSV/XLSX."
                        )
                    )

                wb = xlrd.open_workbook(file_contents=file_content)
                sheet = wb.sheet_by_index(0)
                if sheet.nrows == 0:
                    raise UserError(_("The Excel file appears to be empty."))

                raw_headers = sheet.row_values(0)
                headers = [str(h).strip() for h in raw_headers if h]

                for row_idx in range(1, sheet.nrows):
                    row_values = sheet.row_values(row_idx)
                    row_dict = {}
                    for col_idx, header in enumerate(headers):
                        val = row_values[col_idx] if col_idx < len(row_values) else ""

                        if isinstance(val, float) and val.is_integer():
                            val = int(val)
                        elif isinstance(val, str):
                            val = val.strip()

                        row_dict[header] = val if val is not None else ""
                    data_rows.append(row_dict)
            else:
                raise UserError(
                    _(
                        "Unsupported file format. Please upload a .csv, .xlsx, or .xls file."
                    )
                )

        except Exception as e:
            raise UserError(_("Error reading file: %s") % str(e))

        return headers, data_rows

    def action_update_employees(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Please upload a file."))

        headers, data_rows = self._extract_data_from_file()

        if not headers:
            raise UserError(_("The file appears to be empty or has no headers."))

        # 1. Identify the Employee ID column (allows standard names or Odoo export relational names)
        valid_id_cols = ["employee id", "employee_id", "biotime emp id"]
        id_col = None
        for h in headers:
            h_clean = h.split("/")[0].strip().lower() if "/" in h else h.strip().lower()
            if h_clean in valid_id_cols:
                id_col = h
                break

        if not id_col:
            raise UserError(
                _(
                    "The file MUST contain a column named 'employee_id', 'Employee ID', or 'BioTime Emp ID'."
                )
            )

        employee_model = self.env["hr.employee"]

        # 2. Build mapping of both Technical Names & View Labels -> Field Definitions
        field_mapping = {}
        for tech_name, field_def in employee_model._fields.items():
            field_mapping[tech_name.lower()] = (tech_name, field_def)
            if field_def.string:
                field_mapping[field_def.string.lower()] = (tech_name, field_def)

        # 3. Dynamically map column headers to actual Odoo fields
        valid_fields = {}
        for h in headers:
            if h == id_col:
                continue

            h_lower = h.lower()

            # Match exact technical name or exact label
            if h_lower in field_mapping:
                valid_fields[h] = field_mapping[h_lower]
            # Match Odoo export formats (e.g., "Branch/Branch Name" -> extract "Branch")
            elif "/" in h:
                base_h = h.split("/", 1)[0].strip().lower()
                if base_h in field_mapping:
                    valid_fields[h] = field_mapping[base_h]

        if not valid_fields:
            raise UserError(
                _(
                    "No valid Odoo field names or labels found in the headers. Ensure your headers match Odoo fields (e.g., 'Branch/Branch Name', 'Work Email')."
                )
            )

        updated_count = 0
        not_found_emps = []

        for row in data_rows:
            emp_id_val = str(row.get(id_col, "")).strip()
            if not emp_id_val:
                continue

            employee = employee_model.search(
                [("employee_id", "=ilike", emp_id_val)], limit=1
            )
            if not employee:
                not_found_emps.append(emp_id_val)
                continue

            update_vals = {}

            # 4. Process each dynamic field based on Odoo field type
            for col, (tech_name, field_def) in valid_fields.items():
                val = row.get(col, "")
                if val == "" or val is None:
                    continue

                try:
                    if field_def.type == "many2one":
                        comodel = field_def.comodel_name
                        if comodel == "hr.grade":
                            try:
                                g_int = int(float(val))
                                rel_record = self.env[comodel].search(
                                    [("name", "=", g_int)], limit=1
                                )
                                if rel_record:
                                    update_vals[tech_name] = rel_record.id
                            except ValueError:
                                # Fallback if they write 'Grade 8'
                                rel_records = self.env[comodel].name_search(
                                    str(val), operator="=", limit=1
                                )
                                if not rel_records:
                                    rel_records = self.env[comodel].name_search(
                                        str(val), operator="ilike", limit=1
                                    )
                                if rel_records:
                                    update_vals[tech_name] = rel_records[0][0]
                        else:
                            # 1. First try an exact match (operator="=") to avoid "Manager I" matching "Manager III"
                            rel_records = self.env[comodel].name_search(
                                str(val), operator="=", limit=1
                            )

                            # 2. If no exact match is found, fallback to ILIKE
                            if not rel_records:
                                rel_records = self.env[comodel].name_search(
                                    str(val), operator="ilike", limit=1
                                )

                            if rel_records:
                                update_vals[tech_name] = rel_records[0][0]

                    elif field_def.type == "selection":
                        val_str = str(val).strip()
                        val_lower = val_str.lower()

                        # Fetch Odoo selection options
                        selection = field_def.selection
                        if callable(selection):
                            selection = selection(employee)

                        matched_key = None
                        # Check both the internal technical key ('male') and UI Label ('Male')
                        for k, label in selection:
                            if (
                                str(k).lower() == val_lower
                                or str(label).lower() == val_lower
                            ):
                                matched_key = k
                                break

                        if matched_key is not None:
                            update_vals[tech_name] = matched_key
                        else:
                            update_vals[tech_name] = val_str  # Fallback

                    elif field_def.type in ["integer"]:
                        update_vals[tech_name] = int(float(val))

                    elif field_def.type in ["float", "monetary"]:
                        update_vals[tech_name] = float(val)

                    elif field_def.type == "boolean":
                        update_vals[tech_name] = str(val).lower() in [
                            "true",
                            "1",
                            "yes",
                            "y",
                        ]

                    elif field_def.type in ["date", "datetime"]:
                        if isinstance(val, (datetime.date, datetime.datetime)):
                            update_vals[tech_name] = val
                        else:
                            parsed_date = date_parser.parse(str(val), dayfirst=True)
                            if field_def.type == "date":
                                update_vals[tech_name] = parsed_date.date()
                            else:
                                update_vals[tech_name] = parsed_date

                    else:
                        update_vals[tech_name] = str(val)

                except Exception as e:
                    _logger.warning(
                        f"Failed to cast value '{val}' for field '{col}' on employee {emp_id_val}: {e}"
                    )
                    continue

            # Apply the updates
            if update_vals:
                employee.write(update_vals)
                employee.message_post(
                    body=_("Mass updated via Upload: %s")
                    % ", ".join(update_vals.keys())
                )
                updated_count += 1

        # Prepare success/warning message
        message = _("Successfully updated %d employees.") % updated_count
        if not_found_emps:
            message += _(
                "\n\nCould not find the following Employee IDs (Skipped): %s"
            ) % ", ".join(not_found_emps)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Mass Update Complete"),
                "message": message,
                "sticky": True,
                "type": "warning" if not_found_emps else "success",
            },
        }
