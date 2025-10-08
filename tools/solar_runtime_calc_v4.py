#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kalkulator czasu pracy na 1S Li-Ion/LiPo + PV (Vsys=3.0 V).

- Najpierw zbiera wszystkie dane (ENTER = domyślne).
- Napięcie systemowe urządzenia stałe: 3.0 V.
- Raport: [OBIĄŻENIE], [BATT] (Wh/mWh + czas tylko na baterii), [PV] (profil sezonowy, średnie BEST/WORST),
  [PV → próg ‘na zero’], [Autonomia przy ujemnym bilansie] (na bazie średniego bilansu),
  [Dark-streak] (bufor na N ciemnych dni), [Sezonowy symulator] (roczny profil PSH PL, dzień po dniu).
"""

def safe_float_input(prompt, default=None):
    while True:
        raw = input(prompt)
        if raw.strip() == "" and default is not None:
            return float(default)
        try:
            val = raw.strip().replace(",", ".").replace(" ", "")
            return float(val)
        except ValueError:
            print("⚠️  Błąd: podaj liczbę (np. 1234.56 lub 1234,56).")

def safe_int_input(prompt, default=None, lo=None, hi=None):
    while True:
        raw = input(prompt)
        if raw.strip() == "" and default is not None:
            val = int(default)
            return val
        try:
            val = int(raw.strip())
            if lo is not None and val < lo: raise ValueError
            if hi is not None and val > hi: raise ValueError
            return val
        except ValueError:
            rng = f" ({lo}-{hi})" if lo is not None and hi is not None else ""
            print(f"⚠️  Błąd: podaj liczbę całkowitą{rng}.")

def format_time(hours_float):
    if hours_float == float('inf'):
        return "∞ (nieskończoność)"
    hours = int(hours_float)
    minutes = int(round((hours_float - hours) * 60))
    if minutes == 60:
        hours += 1
        minutes = 0
    days_info = f" (~{hours_float/24:.2f} dni)" if hours_float >= 24 else ""
    return f"{hours} h {minutes} min (~{hours_float:.2f} h){days_info}"

def rotate(lst, start_idx):
    # przesuwa listę tak, by element o indeksie start_idx stał się pierwszym
    return lst[start_idx:] + lst[:start_idx]

def main():
    print("=== Kalkulator 1S Li-Ion/LiPo + PV (Vsys=3.0 V) ===\n")
    print("Wciśnij ENTER, aby użyć wartości domyślnych.\n")

    # 1) Wejścia
    current_mA    = safe_float_input("Średni prąd urządzenia [mA] (ENTER=0.162): ", default=0.162)
    capacity_mAh  = safe_float_input("Pojemność ogniwa [mAh] (ENTER=500): ", default=500)
    p_panel_W     = safe_float_input("Moc panelu PV [W] (ENTER=0.15): ", default=0.15)
    eff_best_pct  = safe_float_input("Sprawność całkowita BEST [%] (ENTER=20): ", default=20)
    eff_worst_pct = safe_float_input("Sprawność całkowita WORST [%] (ENTER=5): ", default=5)
    start_month   = safe_int_input("Miesiąc startu (1=styczeń ... 12=grudzień, ENTER=7): ", default=7, lo=1, hi=12)
    # dodatki – wejścia dla dark-streak
    dark_days       = safe_float_input("Ile maksymalnie 'ciemnych' dni z rzędu? (ENTER=14): ", default=14)
    sun_hours_dark  = safe_float_input("PSH w 'ciemne' dni [h] (ENTER=0.0): ", default=0.0)
    eff_dark_pct    = safe_float_input("Sprawność w 'ciemne' dni [%] (ENTER=5): ", default=5)

    # 2) Stałe i założenia
    v_sys   = 3.0  # stałe
    U_full  = 4.2
    U_safe  = 3.3
    U_cutoff= 3.0

    # Frakcje pojemności (liniowy model energii 4.2→3.0 V)
    fraction_safe   = (U_full - U_safe) / (U_full - U_cutoff)
    cap_safe_mAh    = capacity_mAh * fraction_safe
    cap_cutoff_mAh  = capacity_mAh

    # 3) Obciążenie i bateria
    time_safe_h       = cap_safe_mAh   / current_mA
    time_cutoff_h     = cap_cutoff_mAh / current_mA
    consumption_mWh_d = current_mA * v_sys * 24.0  # mA*V*24 -> mWh/d
    batt_Wh  = capacity_mAh * v_sys / 1000.0
    batt_mWh = batt_Wh * 1000.0
    daily_pct = 100.0 * consumption_mWh_d / batt_mWh if batt_mWh > 0 else 0.0

    # 4) PV – profil sezonowy PL (PSH/dzień) i rotacja od start_month
    # PSH orientacyjne dla środka PL: Jan..Dec
    base_psh_month   = [0.5, 1.0, 2.5, 3.5, 4.5, 5.0, 5.0, 4.5, 3.0, 2.0, 1.0, 0.5]
    days_in_month    = [31,  28,  31,  30,  31,  30,  31,  31,  30,  31,  30,  31]
    month_names_pl   = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]

    # rotacja tak, by start_month był pierwszym (1->indeks 0)
    idx0 = (start_month - 1) % 12
    psh_month  = rotate(base_psh_month, idx0)
    days_month = rotate(days_in_month, idx0)
    names_rot  = rotate(month_names_pl, idx0)

    eff_best   = eff_best_pct  / 100.0
    eff_worst  = eff_worst_pct / 100.0

    # Symulacja dzień po dniu – zliczanie średnich (BEST i WORST)
    total_harvest_best = 0.0
    total_harvest_worst = 0.0
    total_days = sum(days_month)

    # SOC symulacji (BEST – bo to sensowniejsze do oceny „czy przeżyje”; możesz łatwo zmienić na WORST)
    soc_mWh = batt_mWh  # start pełny
    soc_min = soc_mWh

    for m in range(12):
        daily_harvest_best  = p_panel_W * 1000.0 * psh_month[m] * eff_best
        daily_harvest_worst = p_panel_W * 1000.0 * psh_month[m] * eff_worst
        total_harvest_best  += daily_harvest_best  * days_month[m]
        total_harvest_worst += daily_harvest_worst * days_month[m]

        for _ in range(days_month[m]):
            soc_mWh += daily_harvest_best - consumption_mWh_d
            if soc_mWh > batt_mWh: soc_mWh = batt_mWh
            if soc_mWh < soc_min:  soc_min = soc_mWh

    avg_harvest_best_mWh_d  = total_harvest_best  / total_days
    avg_harvest_worst_mWh_d = total_harvest_worst / total_days

    def coverage_and_balance(harvest_mWh_day):
        coverage    = 100.0 * harvest_mWh_day / consumption_mWh_d if consumption_mWh_d > 0 else 0.0
        balance_mWh = harvest_mWh_day - consumption_mWh_d
        return coverage, balance_mWh

    cov_best,  bal_best_mWh   = coverage_and_balance(avg_harvest_best_mWh_d)
    cov_worst, bal_worst_mWh  = coverage_and_balance(avg_harvest_worst_mWh_d)

    # Autonomia „przy ujemnym bilansie” – liczona z BILANSU ŚREDNIEGO (informacyjnie)
    def days_until_empty(cap_mAh, balance_mWh_per_day):
        if balance_mWh_per_day >= 0:
            return float('inf')
        energy_mWh = cap_mAh * v_sys
        days = energy_mWh / (-balance_mWh_per_day)
        return days * 24.0  # godziny

    days_best_safe_h    = days_until_empty(cap_safe_mAh,   bal_best_mWh)
    days_best_cutoff_h  = days_until_empty(cap_cutoff_mAh, bal_best_mWh)
    days_worst_safe_h   = days_until_empty(cap_safe_mAh,   bal_worst_mWh)
    days_worst_cutoff_h = days_until_empty(cap_cutoff_mAh, bal_worst_mWh)

    # 5) Raport (format jak wcześniej)
    print("\n--- PODSUMOWANIE ---")
    print(f"[OBIĄŻENIE] Iavg: {current_mA:.3f} mA @ {v_sys:.1f} V  => {consumption_mWh_d:.2f} mWh/d")
    #print(f"U_safe={U_safe:.1f} V:     {format_time(time_safe_h)} (≈ {cap_safe_mAh:.1f} mAh)")
    #print(f"U_cutoff={U_cutoff:.1f} V: {format_time(time_cutoff_h)} (≈ {cap_cutoff_mAh:.1f} mAh)")

    print("\n[BATT] {:.2f} Wh ≈ {:.0f} mWh".format(batt_Wh, batt_mWh))
    print(f"Dzienne zużycie: {consumption_mWh_d:.2f} mWh/d (~{daily_pct:.2f}% pojemności)")
    print("Czas pracy tylko na samej baterii:")
    print(f"  → do U_safe={U_safe:.1f} V:   {format_time(time_safe_h)}")
    print(f"  → do U_cutoff={U_cutoff:.1f} V: {format_time(time_cutoff_h)}")

    start_label = names_rot[0].upper()
    print("\n[PV] Panel: {:.3f} W, profil sezonowy PL (start: {}), BEST: {:.0f}%, WORST: {:.0f}%".format(
        p_panel_W, start_label, eff_best_pct, eff_worst_pct))
    print(f"BEST (średnio):  uzysk {avg_harvest_best_mWh_d:.2f} mWh/d, pokrycie {cov_best:.1f}%, bilans {bal_best_mWh:+.2f} mWh/d")
    print(f"WORST (średnio): uzysk {avg_harvest_worst_mWh_d:.2f} mWh/d, pokrycie {cov_worst:.1f}%, bilans {bal_worst_mWh:+.2f} mWh/d")

    # [PV → próg ‘na zero’] – minimalna moc panelu z rocznej średniej PSH (dla BEST i WORST)
    avg_psh_year = sum(base_psh_month[i] * days_in_month[i] for i in range(12)) / 365.0
    p_min_best_W  = (consumption_mWh_d / (1000.0 * avg_psh_year * eff_best))  if avg_psh_year>0 and eff_best>0  else float('inf')
    p_min_worst_W = (consumption_mWh_d / (1000.0 * avg_psh_year * eff_worst)) if avg_psh_year>0 and eff_worst>0 else float('inf')

    print("\n[PV → próg ‘na zero’]")
    print(f"Minimalna moc panelu (BEST, średnio-rocznie):  {p_min_best_W:.3f} W")
    print(f"Minimalna moc panelu (WORST, średnio-rocznie): {p_min_worst_W:.3f} W")

    #print("\n[Autonomia przy ujemnym bilansie]")
    #print(f"BEST  → U_safe: {format_time(days_best_safe_h)}\nBEST  → U_cutoff: {format_time(days_best_cutoff_h)}")
    #print(f"WORST → U_safe: {format_time(days_worst_safe_h)}\nWORST  → U_cutoff: {format_time(days_worst_cutoff_h)}")

    # --- DODATEK A: Dark-streak (N ciemnych dni) ---
    harvest_dark_mWh_d = p_panel_W * 1000.0 * sun_hours_dark * (eff_dark_pct/100.0)
    deficit_dark_mWh_d = max(0.0, consumption_mWh_d - harvest_dark_mWh_d)
    need_buffer_mWh    = deficit_dark_mWh_d * dark_days

    print("\n[Dark-streak]")
    print(f"Bilans w 'ciemny' dzień: {harvest_dark_mWh_d:.2f} mWh/d → deficyt {deficit_dark_mWh_d:.2f} mWh/d")
    print(f"Buffer wymagany na {int(dark_days)} dni: {need_buffer_mWh:.1f} mWh")
    print("Status: OK" if batt_mWh >= need_buffer_mWh else "Status: NIE WYSTARCZY (zwiększ aku lub panel)")

    # --- DODATEK B: Sezonowy symulator (dzień po dniu, BEST/WORST) ---
    print("\n[Sezonowy symulator]")

    def simulate_profile(eff, names, psh, days):
        soc = batt_mWh  # start: pełne naładowanie
        soc_min = soc
        soc_min_month = names[0]
        rows = []  # (name, psh, harvest_day, harvest_mon, cons_mon, balance_mon, soc_end_pct)
        for m in range(12):
            name = names[m]
            psh_m = psh[m]
            d_m   = days[m]
            harvest_day = p_panel_W * 1000.0 * psh_m * eff
            harvest_mon = harvest_day * d_m
            cons_mon    = consumption_mWh_d * d_m

            # dzień po dniu, z obcięciem SOC do [0, batt_mWh]
            for _ in range(d_m):
                soc += harvest_day - consumption_mWh_d
                if soc > batt_mWh: soc = batt_mWh
                if soc < soc_min:
                    soc_min = soc
                    soc_min_month = name

            balance_mon = harvest_mon - cons_mon
            soc_end_pct = 100.0 * soc / batt_mWh if batt_mWh > 0 else 0.0
            rows.append((name, psh_m, harvest_day, harvest_mon, cons_mon, balance_mon, soc_end_pct))
        return soc_min, soc_min_month, rows

    # Symulacje dla BEST i WORST
    soc_min_b, soc_min_month_b, rows_b = simulate_profile(eff_best,  names_rot, psh_month, days_month)
    soc_min_w, soc_min_month_w, rows_w = simulate_profile(eff_worst, names_rot, psh_month, days_month)

    perc_b = (100.0 * soc_min_b / batt_mWh) if batt_mWh > 0 else 0.0
    perc_w = (100.0 * soc_min_w / batt_mWh) if batt_mWh > 0 else 0.0

    print(f"BEST  → minimalny SOC w roku: {soc_min_b:.0f} mWh ({perc_b:.1f}% pojemności) — miesiąc: {soc_min_month_b}")
    print(f"WORST → minimalny SOC w roku: {soc_min_w:.0f} mWh ({perc_w:.1f}% pojemności) — miesiąc: {soc_min_month_w}")
    print("Wniosek (BEST):  "  + ("stabilne całoroczne działanie" if soc_min_b > 0 else "grozi rozładowanie w najgorszym miesiącu"))
    print("Wniosek (WORST): " + ("stabilne całoroczne działanie" if soc_min_w > 0 else "grozi rozładowanie w najgorszym miesiącu"))

    # Tabela miesięczna BEST
    print("\n[Bilans miesięczny (BEST)]")
    print("Mies  PSH[h/d]  Uzysk[d]  Uzysk[mies]  Zużycie    Saldo      SOC_koniec")
    for (name, psh, h_day, h_mon, c_mon, bal_mon, soc_end_pct) in rows_b:
        flag = " !" if bal_mon < 0 else "  "
        print("{:>3s} {:>8.2f} {:>9.2f} {:>11.0f} {:>9.0f} {:>9.0f}   {:>6.1f}%{}".format(
            name.upper(), psh, h_day, h_mon, c_mon, bal_mon, soc_end_pct, flag
        ))

    # Tabela miesięczna WORST
    print("\n[Bilans miesięczny (WORST)]")
    print("Mies  PSH[h/d]  Uzysk[d]  Uzysk[mies]  Zużycie    Saldo      SOC_koniec")
    for (name, psh, h_day, h_mon, c_mon, bal_mon, soc_end_pct) in rows_w:
        flag = " !" if bal_mon < 0 else "  "
        print("{:>3s} {:>8.2f} {:>9.2f} {:>11.0f} {:>9.0f} {:>9.0f}   {:>6.1f}%{}".format(
            name.upper(), psh, h_day, h_mon, c_mon, bal_mon, soc_end_pct, flag
        ))


    # Uwagi i disclaimer
    print("\nUwagi: sprawność BEST/WORST obejmuje MPPT/regulator, temperaturę, kąt, zabrudzenie i kable. \n"
          "Zimą w PL przyjmij PSH 0.2–1.0; latem 4.5–5.5; średnio-rocznie ≈ 3.")
    print("\n[Disclaimer]")
    print("Obliczenia przyjmują Vsys=3.0 V i brak strat poza sprawnością PV (LDO idealny).")
    print("Potencjalne źródła odchyłek względem rzeczywistości:")
    print(" - prąd własny LDO, dropout/BOD, ugięcie napięcia przy pikach RF")
    print(" - temperatura: spadek pojemności o 20–40% w 0…-10 °C")
    print(" - starzenie ogniwa: -10…20% pojemności rocznie/cykowo")
    print("Łączny typowy błąd szacowania czasu pracy: ±5…10% (bez ekstremalnego zimna/starzenia).")

if __name__ == "__main__":
    main()
