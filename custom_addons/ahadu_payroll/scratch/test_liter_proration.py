
import math

def test_prorated_liters():
    # Scenario: 100 liters, March (31 days), 5 days absent
    total_liters = 100.0
    total_days = 31
    absent_days = 5
    paid_days = total_days - absent_days # 26
    
    ratio = paid_days / total_days
    prorated_liters = round(total_liters * ratio, 2)
    
    expected = round(100.0 / 31 * 26, 2) # 83.87
    
    print(f"Total Liters: {total_liters}")
    print(f"Total Days: {total_days}")
    print(f"Absent Days: {absent_days}")
    print(f"Paid Days: {paid_days}")
    print(f"Calculated Prorated Liters: {prorated_liters}")
    print(f"Expected Liters: {expected}")
    
    if prorated_liters == expected:
        print("SUCCESS: Liter proration matches expected formula.")
    else:
        print("FAILURE: Calculation mismatch.")

if __name__ == "__main__":
    test_prorated_liters()
