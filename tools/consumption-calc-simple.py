#!/usr/bin/env python3
# -*- coding: utf-8 -*-0

def safe_float_input(prompt):
    """Pobiera input i zamienia przecinek na kropkę, usuwa spacje, zwraca float."""
    while True:
        try:
            val = input(prompt).strip().replace(",", ".").replace(" ", "")
            return float(val)
        except ValueError:
            print("⚠️  Błąd: podaj liczbę (np. 1234.56 lub 1234,56).")


def format_time(hours_float):
    """Zamienia godziny float na 'X h Y min' i ew. dodaje dni."""
    hours = int(hours_float)
    minutes = int(round((hours_float - hours) * 60))
    if minutes == 60:
        hours += 1
        minutes = 0
    days_info = f" (~{hours_float/24:.2f} dni)" if hours_float >= 24 else ""
    return f"{hours} h {minutes} min (~{hours_float:.2f} h){days_info}"


def main():
    print("=== Kalkulator czasu pracy na 1S LiPo ===")

    current_mA = safe_float_input("Podaj średni prąd urządzenia [mA]: ")
    capacity_mAh = safe_float_input("Podaj pojemność ogniwa [mAh]: ")

    # Założenia napięciowe
    U_full = 4.2
    U_cutoff = 3.0
    U_safe = 3.3

    # Frakcje pojemności do danego napięcia
    fraction_safe = (U_full - U_safe) / (U_full - U_cutoff)
    fraction_cutoff = (U_full - U_cutoff) / (U_full - U_cutoff)  # = 1.0

    cap_safe_mAh = capacity_mAh * fraction_safe
    cap_cutoff_mAh = capacity_mAh * fraction_cutoff

    time_safe_h = cap_safe_mAh / current_mA
    time_cutoff_h = cap_cutoff_mAh / current_mA

    print(f"\nPrzy średnim prądzie {current_mA:.2f} mA i ogniwie {capacity_mAh:.2f} mAh")
    print(f"Użyteczna pojemność (do {U_safe} V): ~{cap_safe_mAh:.2f} mAh")
    print(f"Czas pracy do {U_safe} V:   {format_time(time_safe_h)}")
    print(f"Czas pracy do {U_cutoff} V: {format_time(time_cutoff_h)}")


if __name__ == "__main__":
    main()
