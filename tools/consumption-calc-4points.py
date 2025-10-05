def safe_float_input(prompt):
    """Pobiera input i zamienia przecinek na kropkę, usuwa spacje, zwraca float."""
    while True:
        try:
            val = input(prompt).strip().replace(",", ".").replace(" ", "")
            return float(val)
        except ValueError:
            print("⚠️  Błąd: podaj liczbę (np. 1234.56 lub 1234,56).")


def segment_time(capacity_mAh, U_points, I_points, U_cutoff=3.3):
    """
    capacity_mAh - pojemność ogniwa [mAh]
    U_points - lista napięć [V] (malejąca, np. [4.2, 3.7, 3.5, 3.3])
    I_points - lista prądów [mA] odpowiadających napięciom
    U_cutoff - napięcie końcowe [V]
    """
    U_full, U_end = U_points[0], U_cutoff
    usable_voltage_range = U_full - 3.0  # pełny zakres użyteczny

    total_time_h = 0.0

    for i in range(len(U_points) - 1):
        U_high, U_low = U_points[i], U_points[i + 1]
        I_high, I_low = I_points[i], I_points[i + 1]

        if U_low < U_cutoff:
            U_low = U_cutoff
        if U_high <= U_cutoff:
            break

        # pojemność przypisana do tego segmentu
        segment_capacity = capacity_mAh * ((U_high - U_low) / usable_voltage_range)

        # średni prąd w segmencie
        avg_current = (I_high + I_low) / 2.0

        # czas pracy w tym segmencie [h]
        time_h = segment_capacity / avg_current
        total_time_h += time_h

    return total_time_h


def main():
    print("=== Kalkulator czasu pracy LiPo 1S (model z krzywą prądu) ===")

    capacity_mAh = safe_float_input("Podaj pojemność ogniwa [mAh]: ")

    print("\nPodaj średni prąd urządzenia [mA] przy różnych napięciach:")
    I_42 = safe_float_input("  przy 4.2 V: ")
    I_37 = safe_float_input("  przy 3.7 V: ")
    I_35 = safe_float_input("  przy 3.5 V: ")
    I_33 = safe_float_input("  przy 3.3 V: ")

    U_points = [4.2, 3.7, 3.5, 3.3]
    I_points = [I_42, I_37, I_35, I_33]

    time_h = segment_time(capacity_mAh, U_points, I_points, U_cutoff=3.3)

    # formatowanie
    hours = int(time_h)
    minutes = int(round((time_h - hours) * 60))
    if minutes == 60:
        hours += 1
        minutes = 0

    days_info = ""
    if time_h >= 24:
        days = time_h / 24
        days_info = f" ({days:.2f} dni)"

    print(f"\nUżyteczna pojemność: {capacity_mAh:.2f} mAh")
    print(f"Maksymalny czas pracy: {hours} h {minutes} min (~{time_h:.2f} h){days_info}")


if __name__ == "__main__":
    main()
