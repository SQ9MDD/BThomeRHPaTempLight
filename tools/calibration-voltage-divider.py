# calibrate_vbat_cli.py
# Kalibracja: V_true = K * raw_mV + BmV
# Punkty odniesienia domyślnie: 4.2 V (4200 mV) i 3.6 V (3600 mV) – można zmienić w promptach.

DEFAULT_V1_mV = 4200.0
DEFAULT_V2_mV = 3600.0

def _parse_number(s: str) -> float:
    """Akceptuje kropkę/przecinek. Zwraca float."""
    s = s.strip().lower().replace(',', '.')
    import re
    m = re.search(r'[-+]?\d+(?:\.\d+)?', s)
    if not m:
        raise ValueError("Nie podano liczby.")
    return float(m.group(0))

def _read_any_voltage(prompt: str, allow_empty_default: float | None = None) -> float:
    """
    Czyta napięcie (mV lub V). Jeśli < 20 → traktuje jak wolty i konwertuje na mV.
    Gdy allow_empty_default ustawione, puste wejście przyjmuje wartość domyślną.
    """
    raw = input(prompt).strip()
    if raw == "" and allow_empty_default is not None:
        return allow_empty_default
    v = _parse_number(raw)
    if v < 20.0:  # wygląda na wolty
        v *= 1000.0
        print(f"(Wykryto jednostkę w V → przeliczone na {v:.1f} mV)")
    return v

def compute_calibration(raw1_mV: float, raw2_mV: float,
                        v1_mV: float, v2_mV: float):
    if abs(raw2_mV - raw1_mV) < 1e-9:
        raise ValueError("Surowe odczyty są identyczne — nie da się policzyć K.")
    K = (v2_mV - v1_mV) / (raw2_mV - raw1_mV)
    BmV = v1_mV - K * raw1_mV
    return K, BmV

def apply_calibration(raw_mV: float, K: float, BmV: float) -> float:
    return K * raw_mV + BmV

if __name__ == "__main__":
    try:
        # Referencje (domyślnie 4.2 V i 3.6 V)
        # Surowe odczyty z urządzenia dla tych referencji
        V1_mV = _read_any_voltage(
            f"Podaj napięcie referencyjne #1 (mV/V) [Enter={DEFAULT_V1_mV:.0f} mV]: ",
            allow_empty_default=DEFAULT_V1_mV
        )
        r1 = _read_any_voltage("Podaj surowy odczyt urządzenia (mV/V) przy ref #1: ")
        V2_mV = _read_any_voltage(
            f"Podaj napięcie referencyjne #2 (mV/V) [Enter={DEFAULT_V2_mV:.0f} mV]: ",
            allow_empty_default=DEFAULT_V2_mV
        )
        r2 = _read_any_voltage("Podaj surowy odczyt urządzenia (mV/V) przy ref #2: ")
        

        

        K, BmV = compute_calibration(r1, r2, V1_mV, V2_mV)
        print("\nWYNIK KALIBRACJI:")
        print(f"  CAL_K   = {K:.8f}")
        print(f"  CAL_BmV = {BmV:.2f}  # mV")

        # Szybki self-check
        c1 = apply_calibration(r1, K, BmV)
        c2 = apply_calibration(r2, K, BmV)
        print("\nSelf-check (błąd względem ideału):")
        print(f"  przy ref #1 ({V1_mV:.0f} mV) → {c1:.2f} mV  (Δ={c1 - V1_mV:+.2f} mV)")
        print(f"  przy ref #2 ({V2_mV:.0f} mV) → {c2:.2f} mV  (Δ={c2 - V2_mV:+.2f} mV)")
    except Exception as e:
        print("Błąd:", e)
