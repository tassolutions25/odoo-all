import xmlrpc.client
import pandas as pd
import datetime
import math

# ==========================================
# 1. CONFIGURATION
# ==========================================
URL = "http://localhost:8069"
DB = "your_database"
USERNAME = "admin"
PASSWORD = "admin_password"

CSV_FILE = "employee_history.csv"  # Save your excel as CSV

# Odoo "Activity Type" Mapping
# Keys are strings found in your CSV "Reason Name" or "Action Name"
# Values are the selection keys in Odoo's hr.employee.activity model
ACTIVITY_TYPE_MAP = {
    "promotion": "promotion",
    "demotion": "demotion",
    "transfer": "transfer",
    "disciplinary": "disciplinary",
    "termination": "termination",
    "resignation": "termination",
    "death": "termination",
    "ctc": "ctc",
    "acting": "acting",
    "temporary": "temporary",
    # Note: If 'data_change' is not in your Odoo selection list,
    # you must add it to the python code or map it to an existing one like 'disciplinary' or 'transfer'
    "data change": "data_change",  # Will use the Orange Pencil Icon
    "confirmation": "confirmation",  # Will use the Green Check Icon
    "reassign": "reassign_reportees",  # Will use the Blue Users Icon
    "reinitiate": "employee_reinitiate",
}

# ==========================================
# 2. CONNECTION
# ==========================================
print(f"Connecting to {URL}...")
common = xmlrpc.client.ServerProxy("{}/xmlrpc/2/common".format(URL))
uid = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy("{}/xmlrpc/2/object".format(URL))

if not uid:
    print("Authentication Failed.")
    exit()
print("Connected!")

# ==========================================
# 3. CACHING MASTER DATA
# ==========================================
# To avoid thousands of search calls, we cache master data names to IDs.
print("Caching Master Data (Jobs, Departments, Branches, Grades)...")


def get_map(model, name_field="name"):
    records = models.execute_kw(
        DB, uid, PASSWORD, model, "search_read", [[], ["id", name_field]]
    )
    # create dict: { "manager": 12, "officer": 14 }
    return {
        rec[name_field].strip().lower(): rec["id"] for rec in records if rec[name_field]
    }


JOB_MAP = get_map("hr.job")
DEPT_MAP = get_map("hr.department")
BRANCH_MAP = get_map(
    "hr.branch"
)  # Ensure this model exists in your Odoo, else use 'hr.work.location'
GRADE_MAP = get_map("hr.grade")
EMPLOYEE_MAP = {}  # Cache for employees { 'AHB001': Odoo_ID }

# Load Employees
emps = models.execute_kw(
    DB, uid, PASSWORD, "hr.employee", "search_read", [[], ["id", "employee_id"]]
)
for e in emps:
    if e["employee_id"]:
        EMPLOYEE_MAP[str(e["employee_id"]).strip()] = e["id"]

print(f"Cached {len(EMPLOYEE_MAP)} employees.")

# ==========================================
# 4. HELPER FUNCTIONS
# ==========================================


def get_id(map_dict, value, model_name=None):
    if not value or pd.isna(value):
        return False
    val_clean = str(value).strip().lower()

    if val_clean in map_dict:
        return map_dict[val_clean]

    # Optional: Create on the fly if missing (Risky for production)
    # if model_name:
    #     new_id = models.execute_kw(DB, uid, PASSWORD, model_name, 'create', [{'name': str(value).strip()}])
    #     map_dict[val_clean] = new_id
    #     return new_id

    return False


def parse_date(date_val):
    if pd.isna(date_val):
        return datetime.date.today().strftime("%Y-%m-%d")
    try:
        return pd.to_datetime(date_val).strftime("%Y-%m-%d")
    except:
        return datetime.date.today().strftime("%Y-%m-%d")


def create_generic_activity(emp_odoo_id, date, type_key, description):
    """
    Creates an activity card for Data Change, Confirmation, etc.
    where there isn't a specific model like hr.employee.promotion.
    """
    vals = {
        "employee_id": emp_odoo_id,
        "activity_type": type_key,  # Must exist in selection list
        "date": date,
        "state": "approved",
        "description": description,
    }
    try:
        models.execute_kw(DB, uid, PASSWORD, "hr.employee.activity", "create", [vals])
        print(f"   -> Created Generic Activity: {description}")
    except Exception as e:
        print(f"   !! Error creating activity: {e}")


# ==========================================
# 5. MIGRATION LOGIC
# ==========================================


def process_history():
    df = pd.read_csv(CSV_FILE)

    # 1. Sort: Group by Employee, then chronologically by Effective Date
    df["Effective Date"] = pd.to_datetime(df["Effective Date"])
    df = df.sort_values(by=["Employee", "Effective Date"])

    grouped = df.groupby("Employee")

    for emp_code, history in grouped:
        emp_code = str(emp_code).strip()

        if emp_code not in EMPLOYEE_MAP:
            print(f"Skipping {emp_code}: Employee not found in Odoo.")
            continue

        emp_odoo_id = EMPLOYEE_MAP[emp_code]
        print(f"\nProcessing {emp_code} (ID: {emp_odoo_id})...")

        # Initialize previous state
        prev_row = None

        for index, row in history.iterrows():
            reason = str(row.get("Reason Name", "")).lower()
            action = str(row.get("Action Name", "")).lower()
            eff_date = parse_date(row["Effective Date"])

            # Current Row Data Mapped to Odoo IDs
            curr_data = {
                "job_id": get_id(JOB_MAP, row.get("Designation")),
                "dept_id": get_id(DEPT_MAP, row.get("OU Name")),
                "branch_id": get_id(BRANCH_MAP, row.get("Location Name")),
                "grade_id": get_id(GRADE_MAP, row.get("Grade Name")),
                "salary": 0.0,  # CSV doesn't seem to have salary, defaults to 0
            }

            # Comparison Logic (Need a previous row to compare against)
            prev_data = {
                "job_id": False,
                "dept_id": False,
                "branch_id": False,
                "grade_id": False,
                "salary": 0.0,
            }

            if prev_row is not None:
                prev_data = {
                    "job_id": get_id(JOB_MAP, prev_row.get("Designation")),
                    "dept_id": get_id(DEPT_MAP, prev_row.get("OU Name")),
                    "branch_id": get_id(BRANCH_MAP, prev_row.get("Location Name")),
                    "grade_id": get_id(GRADE_MAP, prev_row.get("Grade Name")),
                    "salary": 0.0,
                }

            # -----------------------------------------------
            # LOGIC HANDLERS
            # -----------------------------------------------

            # 1. EMPLOYEE CREATION (Usually the first row)
            if "employee cre" in reason or "employee cre" in action:
                # Just update the master data to ensure the base is correct
                update_vals = {}
                if curr_data["job_id"]:
                    update_vals["job_id"] = curr_data["job_id"]
                if curr_data["dept_id"]:
                    update_vals["department_id"] = curr_data["dept_id"]
                if curr_data["branch_id"]:
                    update_vals["branch_id"] = curr_data["branch_id"]
                if curr_data["grade_id"]:
                    update_vals["grade_id"] = curr_data["grade_id"]

                if update_vals:
                    models.execute_kw(
                        DB,
                        uid,
                        PASSWORD,
                        "hr.employee",
                        "write",
                        [[emp_odoo_id], update_vals],
                    )
                    print(f"   -> Initialized Master Data")
                prev_row = row
                continue

            # 2. PROMOTION
            if "promotion" in reason:
                vals = {
                    "employee_id": emp_odoo_id,
                    "promotion_date": eff_date,
                    "state": "approved",  # Force approved state
                    # Current (Previous state)
                    # Note: Odoo compute fields usually pull 'current' from the employee master.
                    # If this is historical, the employee master might already be ahead.
                    # We usually don't write to 'current_*' fields if they are computed/readonly.
                    # We focus on the 'new_*' fields.
                    "new_job_id": curr_data["job_id"],
                    "new_grade_id": curr_data["grade_id"],
                    "new_department_id": curr_data["dept_id"],
                    "new_branch_id": curr_data["branch_id"],
                    "reason": reason,
                }

                # Check for changes to build description
                desc = []
                if curr_data["job_id"] != prev_data["job_id"]:
                    desc.append(f"Job changed")
                if curr_data["grade_id"] != prev_data["grade_id"]:
                    desc.append(f"Grade changed")

                try:
                    # Creating this record should trigger the override create() which makes the Activity
                    res_id = models.execute_kw(
                        DB, uid, PASSWORD, "hr.employee.promotion", "create", [vals]
                    )
                    # Force the final approval logic to update Master
                    models.execute_kw(
                        DB,
                        uid,
                        PASSWORD,
                        "hr.employee.promotion",
                        "_perform_final_approval",
                        [[res_id]],
                    )
                    print(f"   -> Processed Promotion")
                except Exception as e:
                    print(f"   !! Error Promotion: {e}")

            # 3. DEMOTION
            elif "demotion" in reason:
                vals = {
                    "employee_id": emp_odoo_id,
                    "demotion_date": eff_date,
                    "state": "approved",
                    "new_job_id": curr_data["job_id"],
                    "new_grade_id": curr_data["grade_id"],
                    "new_department_id": curr_data["dept_id"],
                    "new_branch_id": curr_data["branch_id"],
                    "reason": reason,
                }
                try:
                    res_id = models.execute_kw(
                        DB, uid, PASSWORD, "hr.employee.demotion", "create", [vals]
                    )
                    models.execute_kw(
                        DB,
                        uid,
                        PASSWORD,
                        "hr.employee.demotion",
                        "_perform_final_approval",
                        [[res_id]],
                    )
                    print(f"   -> Processed Demotion")
                except Exception as e:
                    print(f"   !! Error Demotion: {e}")

            # 4. TRANSFER
            elif "transfer" in reason:
                vals = {
                    "employee_id": emp_odoo_id,
                    "transfer_date": eff_date,
                    "state": "approved",
                    "new_branch_id": curr_data["branch_id"],
                    "new_department_id": curr_data["dept_id"],
                    # Optional: Transfer might change job too
                    "new_job_id": (
                        curr_data["job_id"]
                        if curr_data["job_id"] != prev_data["job_id"]
                        else False
                    ),
                    "reason": reason,
                }
                try:
                    res_id = models.execute_kw(
                        DB, uid, PASSWORD, "hr.employee.transfer", "create", [vals]
                    )
                    models.execute_kw(
                        DB,
                        uid,
                        PASSWORD,
                        "hr.employee.transfer",
                        "_perform_final_approval",
                        [[res_id]],
                    )
                    print(f"   -> Processed Transfer")
                except Exception as e:
                    print(f"   !! Error Transfer: {e}")

            # 5. CTC CHANGE
            elif "ctc" in reason:
                vals = {
                    "employee_id": emp_odoo_id,
                    "date": eff_date,
                    "state": "approved",
                    "new_wage": 0.0,  # CSV Missing Wage? Or use current master wage if not provided
                    "new_grade_id": curr_data["grade_id"],
                    "new_job_id": curr_data["job_id"],
                    "new_department_id": curr_data["dept_id"],
                    "reason": reason,
                }
                try:
                    res_id = models.execute_kw(
                        DB, uid, PASSWORD, "hr.employee.ctc", "create", [vals]
                    )
                    models.execute_kw(
                        DB,
                        uid,
                        PASSWORD,
                        "hr.employee.ctc",
                        "_perform_final_approval",
                        [[res_id]],
                    )
                    print(f"   -> Processed CTC Change")
                except Exception as e:
                    print(f"   !! Error CTC: {e}")

            # 6. RETIREMENT
            elif "retirement" in reason:
                vals = {
                    "employee_id": emp_odoo_id,
                    "retirement_date": eff_date,
                    "retirement_type": "normal",  # Default
                    "state": "approved",
                    "reason": reason,
                }
                try:
                    res_id = models.execute_kw(
                        DB, uid, PASSWORD, "hr.employee.retirement", "create", [vals]
                    )
                    models.execute_kw(
                        DB,
                        uid,
                        PASSWORD,
                        "hr.employee.retirement",
                        "_perform_final_approval",
                        [[res_id]],
                    )
                    print(f"   -> Processed Retirement")
                except Exception as e:
                    print(f"   !! Error Retirement: {e}")

            # 7. TERMINATION / RESIGNATION / DEATH
            elif (
                "resignation" in reason or "termination" in reason or "death" in reason
            ):
                vals = {
                    "employee_id": emp_odoo_id,
                    "termination_date": eff_date,
                    "state": "approved",
                    "reason": reason,
                }
                try:
                    res_id = models.execute_kw(
                        DB, uid, PASSWORD, "hr.employee.termination", "create", [vals]
                    )
                    # Careful with final approval here, it archives the employee.
                    # If there are subsequent rows (e.g. data correction after term), this might block updates.
                    # Since we sorted by date, this should be the end.
                    models.execute_kw(
                        DB,
                        uid,
                        PASSWORD,
                        "hr.employee.termination",
                        "_perform_final_approval",
                        [[res_id]],
                    )
                    print(f"   -> Processed Termination/Resignation")
                except Exception as e:
                    print(f"   !! Error Termination: {e}")

            # 8. DATA CHANGE / REASSIGN / CONFIRMATION / REINITIATE
            # "create new cards in the employee activity named data change... and insert what data is changed"
            else:
                # Calculate Delta
                changes = []
                if curr_data["job_id"] != prev_data["job_id"]:
                    changes.append(
                        f"Designation: {row.get('Designation')} (was {prev_row.get('Designation')})"
                    )
                if curr_data["dept_id"] != prev_data["dept_id"]:
                    changes.append(
                        f"OU: {row.get('OU Name')} (was {prev_row.get('OU Name')})"
                    )
                if curr_data["branch_id"] != prev_data["branch_id"]:
                    changes.append(
                        f"Location: {row.get('Location Name')} (was {prev_row.get('Location Name')})"
                    )
                if curr_data["grade_id"] != prev_data["grade_id"]:
                    changes.append(
                        f"Grade: {row.get('Grade Name')} (was {prev_row.get('Grade Name')})"
                    )

                # Master Data Update (Always keep master in sync)
                master_update = {}
                if curr_data["job_id"]:
                    master_update["job_id"] = curr_data["job_id"]
                if curr_data["dept_id"]:
                    master_update["department_id"] = curr_data["dept_id"]
                if curr_data["branch_id"]:
                    master_update["branch_id"] = curr_data["branch_id"]
                if curr_data["grade_id"]:
                    master_update["grade_id"] = curr_data["grade_id"]

                if master_update:
                    models.execute_kw(
                        DB,
                        uid,
                        PASSWORD,
                        "hr.employee",
                        "write",
                        [[emp_odoo_id], master_update],
                    )

                # Determine Model to Write To
                reason_lower = reason.lower()
                desc_text = (
                    f"{reason.title()}: " + ", ".join(changes)
                    if changes
                    else reason.title()
                )

                try:
                    if "confirm" in reason_lower:
                        # Insert into hr.employee.confirmation
                        models.execute_kw(
                            DB,
                            uid,
                            PASSWORD,
                            "hr.employee.confirmation",
                            "create",
                            [
                                {
                                    "employee_id": emp_odoo_id,
                                    "date": eff_date,
                                    "reason": desc_text,
                                    "state": "approved",
                                }
                            ],
                        )
                        print("   -> Created Confirmation Record")

                    elif "reassign" in reason_lower:
                        # Insert into hr.employee.reassign
                        models.execute_kw(
                            DB,
                            uid,
                            PASSWORD,
                            "hr.employee.reassign",
                            "create",
                            [
                                {
                                    "employee_id": emp_odoo_id,
                                    "date": eff_date,
                                    "reason": desc_text,
                                    "state": "approved",
                                }
                            ],
                        )
                        print("   -> Created Reassignment Record")

                    elif "reinitiate" in reason_lower:
                        # Insert into hr.employee.reinitiate
                        models.execute_kw(
                            DB,
                            uid,
                            PASSWORD,
                            "hr.employee.reinitiate",
                            "create",
                            [
                                {
                                    "employee_id": emp_odoo_id,
                                    "date": eff_date,
                                    "reason": desc_text,
                                    "state": "approved",
                                }
                            ],
                        )
                        print("   -> Created Reinitiate Record")

                    else:
                        # Fallback: Data Change Model
                        models.execute_kw(
                            DB,
                            uid,
                            PASSWORD,
                            "hr.employee.data.change",
                            "create",
                            [
                                {
                                    "employee_id": emp_odoo_id,
                                    "date": eff_date,
                                    "change_summary": desc_text,
                                    "state": "approved",
                                }
                            ],
                        )
                        print("   -> Created Data Change Record")

                except Exception as e:
                    print(f"   !! Error creating history record: {e}")

            # Update prev_row for next iteration
            prev_row = row


if __name__ == "__main__":
    try:
        process_history()
    except KeyboardInterrupt:
        print("\nStopped by user.")
