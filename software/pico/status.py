# Builds the one status dict that feeds the screen, the Pi and the simulator.


def build(cfg, st, r, energy, decision, outs, pi_on, safe_mode, now_tuple):
    motor_w = r["motor_v"] * r["motor_a"]
    solar_w = max(0.0, r["solar_v"] * r["solar_a"])
    loads_w = max(0.0, r["loads_v"] * r["loads_a"])
    net_w = r["battery_v"] * r["battery_a"]
    # Your legs are only measurable when the hub is generating (station or harvest);
    # while assisting or coasting this is 0 and the screen hides it.
    you_w = energy.pedal_watts(motor_w) if st["mode"] in ("station", "harvest") else 0.0
    return {
        "t": "status",
        "time": now_tuple,
        "mode": st["mode"],
        "level": st["level"],
        "speed_cap": int(cfg.SPEED_CAP_MPH),
        "speed_mph": r.get("speed_mph", 0.0),
        "pedal_w": you_w,
        "motor_w": motor_w,
        "solar_w": solar_w,
        "loads_w": loads_w,
        "net_w": net_w,
        "battery_v": r["battery_v"],
        "soc": energy.soc_pct,
        "reserve": int(cfg.RESERVE_PCT),
        "pack_full": energy.pack_full,
        "hours_to_full": energy.hours_to_full(net_w),
        "assist_miles": energy.assist_miles_left(),
        "made_today_wh": energy.made_today_wh(),
        "today": energy.today,
        "life": energy.life,
        "lights": outs["lights"],
        "usb": outs["usb"],
        "out_13v8": outs["out_13v8"],
        "pi_on": pi_on,
        "wings_locked": st.get("wings_locked", True),
        "braking": st.get("braking", False),
        "safe_mode": safe_mode,
        "warnings": decision.warnings,
    }
