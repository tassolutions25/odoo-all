
import math

def test_transport_calculation():
    # Simulation of current logic
    liters = 100.0
    rate = 70.0725
    
    # 1. Intermediate rounding as it was before my fix
    weighted_liters_rounded = round(liters, 2)
    weighted_rate_rounded = round(rate, 2)
    
    base_amount_rounded = weighted_liters_rounded * weighted_rate_rounded
    
    # 2. Proration (Assume 1 day absence in 30 days)
    ratio = 29 / 30
    final_amount_with_rounding = round(base_amount_rounded * ratio, 2)
    
    # 3. Logic AFTER my fix (no intermediate rounding)
    base_amount_precise = liters * rate
    final_amount_precise = round(base_amount_precise * ratio, 2)
    
    # 4. What user likely expects (Liters * Rate)
    expected = round(liters * rate, 2)
    
    print(f"Liters: {liters}")
    print(f"Rate: {rate}")
    print(f"Product (Expected): {expected}")
    print(f"Current Logic (with 1 day absence): {final_amount_with_rounding}")
    print(f"Fixed Logic (no intermediate rounding, but still with 1 day absence): {final_amount_precise}")
    print(f"Discrepancy due to intermediate rounding: {abs(final_amount_with_rounding - final_amount_precise)}")
    print(f"Discrepancy due to absence proration: {abs(expected - final_amount_precise)}")

if __name__ == "__main__":
    test_transport_calculation()
