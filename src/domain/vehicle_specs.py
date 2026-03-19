"""
Hardcoded vehicle technical specs for the 10 Egyptian market priority vehicles.
Used for instant VIN decode enrichment without RAG latency.
Data validated against OEM sources — see Pojehat Diagnostic Bible v2.
"""

from dataclasses import dataclass, field

from src.app.api.schemas import VINDecodeResponse


@dataclass
class VehicleSpec:
    make: str
    model: str
    platform: str
    engine_code: str
    engine_name: str
    displacement_cc: int
    compression_ratio: str
    compression_std_bar: float
    compression_min_bar: float
    valve_type: str  # "hydraulic" | "shim" | "screw"
    oil_capacity_l: float
    oil_spec: str
    timing_drive: str  # "chain" | "belt"
    timing_interval_km: int  # 0 if chain (inspect only)
    ecu_brand: str
    ecu_model: str
    fuel_type: str  # "MPI" | "GDI" | "D-4S" | "common_rail"
    fuel_pressure_bar: str
    injector_resistance_ohm: str
    transmission_options: list[str]
    key_solenoid_specs: str
    egypt_faults: list[str]
    common_dtcs: list[str]
    x431_functions: list[str]
    safety_alerts: list[str] = field(default_factory=list)
    notes: str = ""


VEHICLE_SPECS: dict[str, VehicleSpec] = {
    "nissan_sunny_b17": VehicleSpec(
        make="Nissan",
        model="Sunny B17 (Sentra N17)",
        platform="V platform",
        engine_code="HR15DE",
        engine_name="1.5L DOHC 16V",
        displacement_cc=1498,
        compression_ratio="10.5:1 (pre-2010) or 11.0:1 (post-2010)",
        compression_std_bar=15.1,
        compression_min_bar=12.9,
        valve_type="shim",
        oil_capacity_l=3.0,
        oil_spec="5W-30 SN/GF-5",
        timing_drive="chain",
        timing_interval_km=0,
        ecu_brand="Hitachi",
        ecu_model="MEC37 (121-pin dual-plug)",
        fuel_type="MPI",
        fuel_pressure_bar="3.5 nominal",
        injector_resistance_ohm="12.0–14.0Ω cold",
        transmission_options=["5MT", "Jatco CVT7 JF015E (NS-3 fluid, 7.0L)"],
        key_solenoid_specs="CVT: Line press A/B 5.3Ω@20°C · TCC 6.1Ω@20°C",
        egypt_faults=[
            "CVT overheating in Cairo traffic → <span class=\"dtc-pill\">P0744</span> / <span class=\"dtc-pill\">P0843</span> — reduce fluid 0.7L, "
            "install dipstick p/n 2706A085",
            "MAF contamination from desert dust → <span class=\"dtc-pill\">P0171</span> — clean with MAF spray, "
            "verify OEM air filter",
            "Tumble Control Valve (TCV) carbon sooting → rough cold idle — clean TCV, "
            "idle relearn via X431",
            "Timing chain stretch after deferred oil changes → rattle on cold start — "
            "inspect at 150,000 km",
        ],
        common_dtcs=["P0171", "P0744", "P0843", "P0335", "P0340"],
        x431_functions=[
            "Idle Air Volume Learn: System > ECM > Special Function > "
            "Idle Air Vol Learn — engine warm, all accessories off, 20s hold",
            "CVT Pressure Test: System > TCM > Data Stream — "
            "secondary pressure 0.88–0.94V at idle N",
            "CVT Degradation Reset: System > TCM > Special Function > "
            "CVT Fluid Degradation Reset — after NS-3 fluid change only",
            "Injector Coding: System > ECM > Special Function > "
            "Injector Coding — enter IMA code from injector body label",
            "TPMS Reset: System > TPMS > Special Function > "
            "Tire Pressure Reset — trigger each sensor in sequence",
            "TCV Actuation Test: System > ECM > Actuation Test > "
            "Tumble Control Valve — verify position sensor voltage 0–5V",
            "CKP Variation Learn: System > ECM > Special Function > "
            "Crankshaft Position Variation Learn — road load required",
        ],
        safety_alerts=[],
        notes="Valve clearance spec at HOT condition: intake 0.304–0.416mm · "
        "exhaust 0.308–0.432mm",
    ),
    "chery_tiggo_7": VehicleSpec(
        make="Chery",
        model="Tiggo 7 / Tiggo 7 Pro (T19)",
        platform="T19 platform",
        engine_code="E4G15B",
        engine_name="1.5L DOHC DVVT",
        displacement_cc=1498,
        compression_ratio="9.5:1",
        compression_std_bar=13.0,
        compression_min_bar=8.5,
        valve_type="hydraulic",
        oil_capacity_l=4.5,
        oil_spec="5W-30 SN ACEA A3/B4",
        timing_drive="belt",
        timing_interval_km=100000,
        ecu_brand="Bosch",
        ecu_model="ME17.8.8 (121-pin / 94-pin)",
        fuel_type="MPI",
        fuel_pressure_bar="3.8–4.0",
        injector_resistance_ohm="11.5–12.5Ω",
        transmission_options=["6MT", "Dry DCT (6-speed)", "Wet DCT (7-speed)"],
        key_solenoid_specs=(
            "Dry DCT: replace every 100,000km / 5yr · Wet DCT: every 60,000km / 3yr"
        ),
        egypt_faults=[
            "Dry DCT judder from Cairo stop-go traffic → clutch glaze — "
            "X431 Gearbox Learning first, then clutch pack",
            "MAF contamination → <span class=\"dtc-pill\">P0171</span> — clean sensor, verify air filter brand",
            "Valve cover oil leak at E4G15B → tighten to 8–10 N·m crisscross pattern",
        ],
        common_dtcs=["P0171", "P0172", "P0201", "P0202", "P0203", "P0204"],
        x431_functions=[
            "DCT Gearbox Relearn: System > TCM > Special Functions > "
            "Gearbox Learning — mandatory after clutch pack replacement",
            "Throttle Adaptation: System > Engine > Special Functions > "
            "Electronic Throttle Reset — after cleaning or ECU replacement",
            "Injector Coding: System > ECM > Special Functions > "
            "Injector Coding — enter 16-digit IMA code per cylinder",
            "EGR Adaptation: System > Engine > Special Functions > "
            "EGR Valve Programming — Closed Position Learning",
            "Oil Service Reset: System > Body > Special Functions > "
            "Oil Life Reset — after oil change",
            "TPMS Reset: System > TPMS > Special Functions > "
            "Tire Reset — direct sensor ID registration",
        ],
        notes="Egypt official PM schedule: chery-eg.com · Valve cover torque: 8–10 N·m",
    ),
    "mg_zs": VehicleSpec(
        make="MG / SAIC",
        model="ZS (1.5L NSE / 1.3T)",
        platform="SAIC platform",
        engine_code="NSE 1.5L / 15S4G 1.3T",
        engine_name="1.5L NA or 1.3L Turbo",
        displacement_cc=1498,
        compression_ratio="11.5:1 (NA) · 10.0:1 (Turbo)",
        compression_std_bar=14.0,
        compression_min_bar=11.5,
        valve_type="hydraulic",
        oil_capacity_l=4.0,
        oil_spec="5W-30 SN/GF-5",
        timing_drive="chain",
        timing_interval_km=0,
        ecu_brand="SAIC",
        ecu_model="EMS10-SGE (112-pin Delphi/SAIC)",
        fuel_type="MPI",
        fuel_pressure_bar="3.5 nominal",
        injector_resistance_ohm="12.0Ω cold",
        transmission_options=["6MT", "CVT", "7-speed DCT (1.3T)"],
        key_solenoid_specs="Wheel bolt torque: 120–130 N·m sequence",
        egypt_faults=[
            "SRS warning after bump → check clock spring, read B-codes via X431",
            "MAF drift in high ambient temps → <span class=\"dtc-pill\">P0171</span> — common in summer",
            "CAN U-codes after battery disconnect → clear with X431, check BCM",
        ],
        common_dtcs=["P0171", "U0142", "P0420"],
        x431_functions=[
            "SAS Calibration: System > EPS > Special Functions > "
            "Steering Angle Reset — wheels straight, ignition on",
            "TPMS Relearn: System > TPMS > Special Functions > "
            "TPMS Reset — trigger sensors with TPMS tool at each wheel",
            "Throttle Adaptation: System > Engine > Special Functions > "
            "Throttle Body Adaptation — after cleaning",
            "AVM Camera Calibration: System > ADAS > Special Functions > "
            "Calibrating Camera Image — static target board required",
            "Battery Registration: System > BCM > Special Functions > "
            "Battery Matching — after 12V battery replacement",
            "EPB Reset: System > Brake > Special Functions > "
            "Brake Reset — retract rear calipers before pad replacement",
            "Window Initialization: System > Body > Special Functions > "
            "Power Window Reset — one-touch initialization per door",
        ],
        safety_alerts=[
            "SRS: Disconnect 12V + orange MSD clip. Wait 10 minutes.",
            "Squib resistance: 0.7–4.0Ω. Never measure directly with multimeter.",
        ],
    ),
    "toyota_corolla_e210": VehicleSpec(
        make="Toyota",
        model="Corolla E210 (2018–present)",
        platform="TNGA-C platform",
        engine_code="2ZR-FXE (Hybrid) / M20A-FKS (petrol)",
        engine_name="1.8L Hybrid or 2.0L Dynamic Force",
        displacement_cc=1798,
        compression_ratio="13.0:1 (Hybrid Atkinson) · 14.0:1 (2.0L)",
        compression_std_bar=14.7,
        compression_min_bar=11.8,
        valve_type="hydraulic",
        oil_capacity_l=4.2,
        oil_spec="0W-16 Toyota Genuine (hybrid) · 0W-20 (petrol)",
        timing_drive="chain",
        timing_interval_km=0,
        ecu_brand="Denso",
        ecu_model="Multi-ECU system (HV ECU + Engine ECU)",
        fuel_type="D-4S (Port + Direct injection combined)",
        fuel_pressure_bar="3.1–3.5 bar (low pressure side)",
        injector_resistance_ohm="Port: 12.0Ω · Direct: 1.0–2.0Ω",
        transmission_options=["CVT e-Drive", "6-speed iMT", "CVT-i (2.0L)"],
        key_solenoid_specs="HV Battery: NiMH 201.6V/216V or Li-ion 207.2V",
        egypt_faults=[
            "<span class=\"dtc-pill\">P0AA6</span> ground isolation fault → foam battery dam soaked by water",
            "Oil consumption on 2ZR-FXE — monitor every 5,000 km",
            "D-4S direct injector carbon buildup — port injection wash helps",
        ],
        common_dtcs=["P0AA6", "P3000", "P0300", "P0420"],
        x431_functions=[
            "HV Battery Status Update: System > Hybrid Control > "
            "Special Functions > Battery Status Info Update — after cell replacement",
            "Inverter Pump Actuation: System > Hybrid > Actuation Test > "
            "Electric Water Pump — verify 12V signal and flow",
            "SAS Calibration: System > EPS > Special Functions > "
            "Steering Angle Reset — after steering rack replacement",
            "Hybrid System Initialization: System > Hybrid Control > "
            "Special Functions > Hybrid System Initial Check",
            "TPMS Reset: System > TPMS > Special Functions > "
            "Tire Pressure Reset — direct system, trigger each sensor",
            "Injector Coding (D-4S): System > ECM > Special Functions > "
            "Injector Coding — direct injectors require QR code entry",
            "AVM Front Camera Calibration: System > ADAS > Special Functions > "
            "Calibrating Camera Image (Front Camera) — 3m target distance",
        ],
        safety_alerts=[
            "HV: Orange cables are HIGH VOLTAGE. Never probe without PPE.",
            "Insulation test: MUST use 500V megohmmeter (never higher/lower)",
            "Electrolyte: neutralize with 80g boric acid per 2L water.",
            "Wait 5 mins after 12V disconnect before HV work.",
        ],
    ),
    "renault_logan": VehicleSpec(
        make="Renault / Dacia",
        model="Logan / Sandero (2013–2022)",
        platform="B0 platform",
        engine_code="K7M / K9K",
        engine_name="1.6L 8V (K7M) or 1.5L dCi diesel (K9K)",
        displacement_cc=1598,
        compression_ratio="9.5:1 (K7M) · 15.5:1 (K9K diesel)",
        compression_std_bar=12.0,
        compression_min_bar=9.5,
        valve_type="shim",
        oil_capacity_l=3.3,
        oil_spec="5W-40 SL (K7M) · 5W-40 CF (K9K)",
        timing_drive="belt",
        timing_interval_km=60000,
        ecu_brand="Siemens",
        ecu_model="EMS3132 (90-pin black connector)",
        fuel_type="MPI",
        fuel_pressure_bar="3.3–3.7",
        injector_resistance_ohm="12.0Ω cold",
        transmission_options=["5MT", "DP0/AL4 auto (4-speed)"],
        key_solenoid_specs=(
            "DP0 shift valves EV1–EV6: 40Ω±2Ω · "
            "Modulation EVM/EVLU: 1.1Ω · Capacity: 4.8L"
        ),
        egypt_faults=[
            "IAC valve body sooting from dust → hunting idle, stalling — "
            "clean + X431 adaptation",
            "DP0 transmission cooler clogging → overheating, limp mode — "
            "install external cooler",
            "Timing belt failure → catastrophic engine damage — "
            "replace at 60,000 km in Egypt",
            "K7M valve seat wear from 92-octane fuel → compression loss cyl 3/4",
        ],
        common_dtcs=["P0171", "P0300", "P0700", "P0006"],
        x431_functions=[
            "Throttle Adaptation: System > Engine > Special Functions > "
            "Electronic Throttle Reset — required after cleaning or ECU swap",
            "DP0 Adaptation Reset: System > TCM > Special Functions > "
            "Adaptation Reset — mandatory after valve body or clutch service",
            "EGR Valve Programming: System > Engine > Special Functions > "
            "EGR Closed Position Learning — Low Pressure EGR",
            "Injector Coding (K9K diesel): System > ECM > Special Functions > "
            "Injector Coding — enter C2I correction code per injector",
            "Service Interval Reset: System > Cluster > Special Functions > "
            "Oil Service Reset — after oil change",
            "ABS Bleed: System > ABS > Special Functions > "
            "Brake Bleeding — electronic sequence for trapped air",
        ],
        notes="K7M timing belt: replace water pump and tensioner simultaneously.",
    ),
    "peugeot_301": VehicleSpec(
        make="Peugeot",
        model="301 (2012–2020)",
        platform="PF1 platform",
        engine_code="EC5 (1.6L VTi) / 9H05 (1.6L BlueHDi)",
        engine_name="1.6L VTi petrol or 1.6L BlueHDi diesel",
        displacement_cc=1587,
        compression_ratio="11.0:1 (petrol) · 16.0:1 (diesel)",
        compression_std_bar=13.0,
        compression_min_bar=10.0,
        valve_type="hydraulic",
        oil_capacity_l=4.25,
        oil_spec="5W-30 ACEA A5/B5",
        timing_drive="belt",
        timing_interval_km=140000,
        ecu_brand="Delphi",
        ecu_model="MT80 (X1/X2 dual plug)",
        fuel_type="MPI (petrol) / common rail (diesel)",
        fuel_pressure_bar="3.5 nominal",
        injector_resistance_ohm="12.0–14.5Ω (petrol MPI)",
        transmission_options=["5MT", "6MT (diesel)", "DP0/AL4 auto (4-speed)"],
        key_solenoid_specs=(
            "DP0: EV1–EV6: 40Ω±2Ω · EPC+lockup MUST be replaced together with TCM flash"
        ),
        egypt_faults=[
            "Cooling fan relay failure from constant A/C in 40°C+ heat → "
            "overheating, A/C cuts out",
            "DP0 overheating → heat exchanger clog — install external cooler",
            "Throttle body sooting → rough idle — clean + adaptation reset",
            "EC5 timing belt tensioner failure → replace belt + tensioner + pump",
        ],
        common_dtcs=["P0171", "P0006", "P0420", "P0300"],
        x431_functions=[
            "Throttle Adaptation: System > Engine > Special Functions > "
            "Electronic Throttle Sensor Reset — after body cleaning",
            "DP0 Adaptation Reset: System > TCM > Special Functions > "
            "Adaptation Reset — TCM flash required if solenoids replaced",
            "EGR Programming: System > Engine > Special Functions > "
            "EGR Valve Closed Position — Low Pressure EGR Learn",
            "Injector Coding (EC5 petrol): System > ECM > Special Functions > "
            "Injector Coding — QR code on injector label, per cylinder",
            "Service Reset: System > Cluster > Special Functions > "
            "Service Interval Reset",
            "ABS Bleed: System > ABS > Special Functions > "
            "Brake Bleeding — electronic sequence, PP2000/DiagBox compatible",
        ],
        notes="Citroën C-Elysée is mechanically identical (PF1, EC5, MT80, DP0).",
    ),
    "kia_cerato_bd": VehicleSpec(
        make="Kia",
        model="Cerato BD (2019–2023)",
        platform="BD platform",
        engine_code="G4FG / G4FJ (Turbo)",
        engine_name="1.6L MPI (G4FG) or 1.4L T-GDi (G4FJ)",
        displacement_cc=1591,
        compression_ratio="10.5:1",
        compression_std_bar=12.5,
        compression_min_bar=10.0,
        valve_type="hydraulic",
        oil_capacity_l=3.6,
        oil_spec="5W-30 SN/GF-5",
        timing_drive="chain",
        timing_interval_km=0,
        ecu_brand="Bosch",
        ecu_model="ME17.9.21 (94-pin module)",
        fuel_type="MPI (G4FG) / GDi (G4FJ turbo)",
        fuel_pressure_bar="3.5–3.8",
        injector_resistance_ohm="13.8–15.2Ω @ 20°C",
        transmission_options=["6MT", "6AT (A6MF2)", "7DCT (turbo)"],
        key_solenoid_specs="A6MF2 VFS: 5.1Ω · SSA/SSB: 10–11Ω · SP-IV 7.1L",
        egypt_faults=[
            "Catalytic converter destruction from 92-octane fuel → <span class=\"dtc-pill\">P0420</span> + <span class=\"dtc-pill\">P0300</span>",
            "Seatbelt pretensioner fault <span class=\"dtc-pill\">B1706</span> (resistance >5.8Ω) → SRS light",
            "G4FJ turbo: intercooler boost leak from speed bump vibration",
        ],
        common_dtcs=["P0420", "P0300", "P0325", "B1706"],
        x431_functions=[
            "TPMS Relearn: System > TPMS > Special Functions > "
            "TPMS Reset — trigger each sensor sequentially",
            "A6MF2 Adaptation Reset: System > TCM > Special Functions > "
            "Adaptation Reset — after valve body or clutch service",
            "Throttle Position Reset: System > ECM > Special Functions > "
            "TPS Adaptive Reset — after throttle body cleaning",
            "Injector Coding (G4FJ GDi): System > ECM > Special Functions > "
            "Injector Coding — alphanumeric flow-rate code on injector body",
            "ADAS Calibration: System > ADAS > Special Functions > "
            "Forward Camera Calibration — static target, 3m distance",
            "SAS Calibration: System > EPS > Special Functions > "
            "Steering Angle Sensor Reset — wheels straight",
            "ABS Bleed: System > ABS > Special Functions > "
            "Brake Bleeding — electronic caliper sequence",
        ],
        safety_alerts=[
            "SRS pretensioner: 1.8–2.5Ω. >5.8Ω = B1706. Never probe squib directly.",
        ],
    ),
    "hyundai_accent_rb": VehicleSpec(
        make="Hyundai",
        model="Accent RB (2011–2017)",
        platform="RB platform",
        engine_code="G4FA (1.4L) / G4FC (1.6L)",
        engine_name="1.4L or 1.6L Gamma DOHC",
        displacement_cc=1591,
        compression_ratio="10.5:1",
        compression_std_bar=12.5,
        compression_min_bar=10.0,
        valve_type="hydraulic",
        oil_capacity_l=3.3,
        oil_spec="5W-30 SN/GF-5",
        timing_drive="chain",
        timing_interval_km=0,
        ecu_brand="Bosch",
        ecu_model="ME17.9.11 (94-pin module)",
        fuel_type="MPI",
        fuel_pressure_bar="3.5–3.8",
        injector_resistance_ohm="13.8–15.2Ω @ 20°C",
        transmission_options=["6MT", "6AT (A6LF1)", "4AT (A4CF)"],
        key_solenoid_specs="A6LF1 VFS: 5.1Ω · SSA/SSB: 10–11Ω · ATF SP-IV 7.8L",
        egypt_faults=[
            "Catalyst destruction from 92-octane pre-ignition → <span class=\"dtc-pill\">P0420</span> + <span class=\"dtc-pill\">P0300</span>",
            "A6LF1: 3-5R and 2-6 brake VFS solenoid failure → harsh shift",
            "MAF sensor drift in summer heat → <span class=\"dtc-pill\">P0171</span> — clean sensor",
        ],
        common_dtcs=["P0420", "P0300", "P0171", "P0700"],
        x431_functions=[
            "Idle Relearn: System > ECM > Special Functions > "
            "TPS Adaptive Reset — after throttle body cleaning",
            "A6LF1 Adaptation Reset: System > TCM > Special Functions > "
            "Adaptation Reset — after solenoid or clutch pack service",
            "A6LF1 Pressure Check: System > TCM > Data Stream — "
            "monitor line pressure and VFS duty cycle",
            "TPMS Reset: System > TPMS > Special Functions > "
            "Tire Pressure Reset — direct system, trigger each sensor",
            "Injector Coding: System > ECM > Special Functions > "
            "Injector Coding — flow-rate correction code per cylinder",
            "SAS Calibration: System > EPS > Special Functions > "
            "Steering Angle Reset — required after rack replacement",
        ],
    ),
    "mitsubishi_lancer_ex": VehicleSpec(
        make="Mitsubishi",
        model="Lancer EX (2008–2017)",
        platform="CY/CZ platform",
        engine_code="4A91 (1.5L) / 4A92 (1.6L)",
        engine_name="1.5L or 1.6L MIVEC DOHC",
        displacement_cc=1499,
        compression_ratio="10.0:1",
        compression_std_bar=12.0,
        compression_min_bar=8.5,
        valve_type="shim",
        oil_capacity_l=4.2,
        oil_spec="5W-30 SN",
        timing_drive="chain",
        timing_interval_km=0,
        ecu_brand="Mitsubishi",
        ecu_model="MH8104F PCM (4-plug)",
        fuel_type="MPI",
        fuel_pressure_bar="3.2–3.4",
        injector_resistance_ohm="13.0–16.0Ω",
        transmission_options=["5MT", "CVT F1C1A (SP III, 8.1L)"],
        key_solenoid_specs="F1C1A all solenoids: 2.9–3.5Ω@20°C · Stall torque: 2.0",
        egypt_faults=[
            "CVT belt wear from high ambient heat — inspect at 150,000 km",
            "Valve clearance shim wear (4A91) — check at 80,000 km intervals",
            "MH8104F ECU connector corrosion from humidity — inspect C1-plug",
        ],
        common_dtcs=["P0171", "P0300", "P0335"],
        x431_functions=[
            "CVT Fluid Temp Monitor: System > TCM > Data Stream — "
            "monitor TFT sensor: >100°C = overheating threshold",
            "Idle Reset: System > ECM > Special Functions > "
            "Idle Adaptation — after MAF cleaning or IAC service",
            "INVECS-III Adaptation: System > TCM > Special Functions > "
            "Transmission Adapt Reset — after fluid or solenoid service",
            "Injector Coding: System > ECM > Special Functions > "
            "Injector Coding — 16-digit correction code per cylinder",
            "Throttle Adaptation: System > ECM > Special Functions > "
            "Throttle Position Sensor Relearn",
            "ABS Bleed: System > ABS > Special Functions > "
            "Brake Bleeding — electronic sequence required",
        ],
    ),
    "chevrolet_cruze": VehicleSpec(
        make="Chevrolet",
        model="Cruze J300 (2009–2016)",
        platform="Delta II platform",
        engine_code="Z18XER (1.8L)",
        engine_name="1.8L Ecotec DOHC 16V",
        displacement_cc=1796,
        compression_ratio="10.5:1",
        compression_std_bar=16.0,
        compression_min_bar=12.8,
        valve_type="hydraulic",
        oil_capacity_l=4.5,
        oil_spec="5W-30 dexos1 Gen2",
        timing_drive="belt",
        timing_interval_km=100000,
        ecu_brand="ACDelco",
        ecu_model="E39 (X1/X2: 73+53-pin)",
        fuel_type="MPI",
        fuel_pressure_bar="3.8 nominal",
        injector_resistance_ohm="11.0–14.0Ω",
        transmission_options=["5MT", "6MT", "6AT (AF33/TF-60SN)"],
        key_solenoid_specs="EVAP: 0.020 inch orifice small leak spec",
        egypt_faults=[
            "Timing belt + water pump failure — replace BOTH at 100,000 km",
            "Throttle body carbon → rough idle, hesitation — clean + reset",
            "AF33 transmission hesitation → adaptation reset via X431",
            "<span class=\"dtc-pill\">P0403</span>: EGR Circuit Malfunction — صمام EGR متسرب أو مسدود (شائع جداً في مصر).",
            "<span class=\"dtc-pill\">P0404</span>: EGR Valve Defective — عطل ميكانيكي في الـ**EGR valve**.",
            "<span class=\"dtc-pill\">U0101</span>: Lost Communication with TCM (6T40 only) — مشكلة شبكة CAN.",
        ],
        common_dtcs=["P0171", "P0300", "P0420", "P0442", "P0403", "P0404", "U0101"],
        x431_functions=[
            "EPB Reset: System > Brake Control > Special Functions > "
            "Brake Reset — mandatory before rear pad replacement",
            "Throttle Adaptation: System > Engine > Special Functions > "
            "Electronic Throttle Relearn — after cleaning or ECU swap",
            "Injector Coding: System > ECM > Special Functions > "
            "Injector Coding — QR/flow-rate code from injector label",
            "VVT Solenoid Test: System > ECM > Actuation Test > "
            "Camshaft OCV — verify duty cycle 0–100%",
            "6T40 Adapt Reset: System > TCM > Special Functions > "
            "Transmission Adaptation Reset — after valve body or fluid",
            "ABS Bleed: System > ABS > Special Functions > "
            "Brake Bleeding — electronic sequence, ACDelco scan compatible",
            "TPMS Reset: System > TPMS > Special Functions > "
            "Tire Pressure Reset — indirect system calibration",
        ],
        notes="Replace timing belt + water pump + tensioner simultaneously.",
    ),
}

# Aliases — VIN context suggestions map to these keys
VEHICLE_CONTEXT_MAP: dict[str, str] = {
    "nissan sunny b17": "nissan_sunny_b17",
    "nissan sentra b17": "nissan_sunny_b17",
    # Chery — entirely missing from map. Top Egyptian brand.
    "chery tiggo 7": "chery_tiggo_7",
    "chery tiggo 7 pro": "chery_tiggo_7",
    "chery arrizo": "chery_tiggo_7",
    "chery fulwin": "chery_tiggo_7",
    # MG / SAIC — entirely missing from map
    "mg zs": "mg_zs",
    "mg zs ev": "mg_zs",
    "mg zs hybrid": "mg_zs",
    # Nissan variant names auto.dev returns for B17 platform
    "nissan versa": "nissan_sunny_b17",
    "nissan almera": "nissan_sunny_b17",
    "nissan tiida": "nissan_sunny_b17",
    "nissan latio": "nissan_sunny_b17",
    # Hyundai variant names
    "hyundai verna": "hyundai_accent_rb",
    "hyundai elantra": "hyundai_accent_rb",
    # Renault variants
    "renault sandero": "renault_logan",
    "dacia sandero": "renault_logan",
    "toyota corolla e210": "toyota_corolla_e210",
    "toyota corolla": "toyota_corolla_e210",
    "renault logan": "renault_logan",
    "dacia logan": "renault_logan",
    "peugeot 301": "peugeot_301",
    "citroen c-elysee": "peugeot_301",
    "citroën c-elysée": "peugeot_301",
    "kia cerato bd": "kia_cerato_bd",
    "kia cerato": "kia_cerato_bd",
    "hyundai accent rb": "hyundai_accent_rb",
    "hyundai accent": "hyundai_accent_rb",
    "mitsubishi lancer ex": "mitsubishi_lancer_ex",
    "mitsubishi lancer": "mitsubishi_lancer_ex",
    "chevrolet cruze": "chevrolet_cruze",
}


def get_spec(vehicle_context_suggestion: str) -> VehicleSpec | None:
    """Look up spec by vehicle context string (case-insensitive)."""
    key = vehicle_context_suggestion.lower().strip()
    spec_key = VEHICLE_CONTEXT_MAP.get(key)
    if spec_key:
        return VEHICLE_SPECS.get(spec_key)
    # Fuzzy fallback — check if any key is contained in the suggestion
    for map_key, s_key in VEHICLE_CONTEXT_MAP.items():
        if map_key in key or key in map_key:
            return VEHICLE_SPECS.get(s_key)
    return None


def format_vehicle_brief(vin: str, spec: VehicleSpec, decode_data: dict) -> str:
    """
    Format the hardcoded spec as a rich markdown chat response.
    This is Bubble 1 — instant response from local data.
    """
    confidence_emoji = (
        "✅"
        if decode_data.get("confidence") == "high"
        else "🟡"
        if decode_data.get("confidence") == "medium"
        else "⚠️"
    )
    check_note = decode_data.get("message", "")
    safety_block = ""
    if spec.safety_alerts:
        safety_lines = "\n".join(f"  ⚡ {a}" for a in spec.safety_alerts)
        safety_block = f"\n\n🔴 **SAFETY ALERTS**\n{safety_lines}"

    faults_lines = "\n".join(f"  {i + 1}. {f}" for i, f in enumerate(spec.egypt_faults))
    dtc_line = " · ".join(
        f'<span class="dtc-pill">{d}</span>' for d in spec.common_dtcs
    )
    x431_lines = "\n".join(f"  → {x}" for x in spec.x431_functions)

    return f"""🔍 **VIN DECODED — `{vin}`**

{confidence_emoji} **{spec.make} {spec.model}** · {decode_data.get("model_year", "")}
🌍 Origin: {decode_data.get("country", "Unknown")} · WMI: `{decode_data.get("wmi", "")}`
_{check_note}_

---

⚙️ **ENGINE — {spec.engine_code}**
  Engine: {spec.engine_name} · {spec.displacement_cc}cc
  Compression ratio: {spec.compression_ratio}
  Compression: {spec.compression_std_bar} bar std · {spec.compression_min_bar} bar min
  Valve adjustment: {spec.valve_type}
  Oil: {spec.oil_capacity_l}L · {spec.oil_spec}
  Timing: {spec.timing_drive.upper()} · {
        "Replace at " + f"{spec.timing_interval_km:,}" + " km"
        if spec.timing_interval_km > 0
        else "Inspect only"
    }

⚡ **ECU / DIAGNOSTICS**
  ECU: {spec.ecu_brand} {spec.ecu_model}
  Fuel system: {spec.fuel_type} · {spec.fuel_pressure_bar} bar
  Injector resistance: {spec.injector_resistance_ohm}

🔧 **TRANSMISSION OPTIONS**
  {" | ".join(spec.transmission_options)}
  {spec.key_solenoid_specs}

🔴 **TOP EGYPTIAN MARKET FAULTS**
{faults_lines}

📟 **COMMON DTCS**
  {dtc_line}

🔧 **X431 SPECIAL FUNCTIONS**
{x431_lines}{safety_block}

---
_🤖 Retrieving additional technical data from knowledge base..._"""


# ---------------------------------------------------------------------------
# Pojehat Powertrain Intelligence Database (Legacy)
# Drawn from: ingested OEM manuals, regional diagnostic blueprint, A6LF1 /
# JF015E service manuals, Bosch ME17.9.11 / SID807 pinout data.
# ---------------------------------------------------------------------------

_PowertrainProfile = dict[str, str | list[str]]

_POWERTRAIN_PROFILES: list[tuple[str, list[str], int, int, _PowertrainProfile]] = [
    # ── Nissan Sunny (B17) ────────────────────────────────────────────────
    (
        "nissan",
        ["sunny", "b17"],
        2012,
        2026,
        {
            "ecu_family": "Hitachi MEC107 / Hitachi ECCS",
            "engine_code": "HR15DE 1.5L DOHC 16V MPFI",
            "transmission_code": "Jatco JF015E CVT7 (RE0F11A / F1CJB)",
            "known_issues": [
                "<span class=\"dtc-pill\">P0744</span>: Clutch performance — check CVT fluid level first",
                "<span class=\"dtc-pill\">P0841</span>: Fluid pressure sensor — verify solenoid A voltage",
                "CVT step-in vibration: clean speed sensors",
                "Throttle relearn: 5 pumps/5s, hold 20s until MI flashes",
            ],
            "special_functions_hint": (
                "Idle Air Volume Learning | CVT Pressure Test | CVT Degradation Reset"
            ),
        },
    ),
    # ── Nissan Qashqai (J11) ──────────────────────────────────────────────
    (
        "nissan",
        ["qashqai", "j11"],
        2014,
        2026,
        {
            "ecu_family": "Hitachi MEC141",
            "engine_code": "MR20DD 2.0L Direct Injection / HRA2DDT 1.2T",
            "transmission_code": "Jatco JF016E/JF017E (Xtronic CVT)",
            "known_issues": [
                "<span class=\"dtc-pill\">P0011</span>: Intake valve timing — check oil viscosity; 5W-30 req",
                "<span class=\"dtc-pill\">P2263</span>: Turbocharger boost performance (1.2T) — check bypass",
                "<span class=\"dtc-pill\">P17F0</span>: CVT judder — TCM software update mandatory",
                "Battery BMS: <span class=\"dtc-pill\">P0607</span> — reset current sensor after replacement",
            ],
            "special_functions_hint": (
                "CVT Judder Reset | Turbo Actuator Calibr | GDi Fuel Pressure"
            ),
        },
    ),
    # ── Toyota Corolla (E210) ──────────────────────────────────────────────
    (
        "toyota",
        ["corolla", "e210"],
        2019,
        2026,
        {
            "ecu_family": "Toyota Hybrid Control / Denso",
            "engine_code": "2ZR-FXE (Hybrid) / M15A-FKS",
            "transmission_code": "Toyota P410 eCVT",
            "known_issues": [
                "<span class=\"dtc-pill\">P0A93</span>: Inverter cooling failure — check water pump B1400",
                "<span class=\"dtc-pill\">P0421</span>: catalyst efficiency — check AFR sensor 1 drift",
                "Hybrid battery: monitor cell voltages (Delta < 0.3V)",
            ],
            "special_functions_hint": (
                "Hybrid Sys Initial | Inverter Pump Act | SAS Reset"
            ),
        },
    ),
    # ── Hyundai Tucson (TL/NX4) ───────────────────────────────────────────
    (
        "hyundai",
        ["tucson"],
        2015,
        2026,
        {
            "ecu_family": "Bosch ME17.9.64 / Bosch MG1CS008",
            "engine_code": "G4FD 1.6 GDi / G4FJ 1.6 T-GDi / G4KJ 2.4 GDi",
            "transmission_code": "Hyundai 6AT / 7-DCT / 8AT",
            "known_issues": [
                "<span class=\"dtc-pill\">P0014</span>: Exhaust CAM over-advanced — check OCV solenoid",
                "<span class=\"dtc-pill\">P1326</span>: Knock sensor detection (KSDS) — update ROM",
                "7-DCT: <span class=\"dtc-pill\">P073F</span> — sync error; perform clutch adaptation",
                "DPD/GPF: Forced regeneration if <span class=\"dtc-pill\">P2458</span> present",
            ],
            "special_functions_hint": (
                "Clutch Adaptation | GDi Injector Test | E-CVVT Calib"
            ),
        },
    ),
    # ── Hyundai Accent/Verna (RB/HC) ──────────────────────────────────────
    (
        "hyundai",
        ["accent", "verna"],
        2012,
        2026,
        {
            "ecu_family": "Bosch ME17.9.11 / ME17.9.21",
            "engine_code": "G4FC 1.6 CVVT / G4FG 1.6L Gamma",
            "transmission_code": "A4CF1 4AT / A6GF1 6AT",
            "known_issues": [
                "<span class=\"dtc-pill\">P0441</span>: Evap purge flow — check solenoid resistance (22-26Ω)",
                "A6GF1 failsafe (4th gear): <span class=\"dtc-pill\">P0707</span> range fault common",
                "Throttle jerk: clean carbon at 40k km; mandatory TPS reset",
            ],
            "special_functions_hint": (
                "TPS Adaptive Reset | Trans Pressure Check | ABS/ESP Bleeding"
            ),
        },
    ),
    # ── Chevrolet Cruze (J300) ───────────────────────────────────────────
    (
        "chevrolet",
        ["cruze"],
        2009,
        2026,
        {
            "ecu_family": "GM Delco E39 / E78 / E83",
            "engine_code": "Ecotec 1.6L / 1.8L (Z18XER)",
            "transmission_code": "GM 6T30 / 6T40 6-Speed AT",
            "known_issues": [
                "<span class=\"dtc-pill\">P0403</span>: EGR Circuit Malfunction — صمام EGR متسرب أو مسدود (شائع جداً في مصر).",
                "<span class=\"dtc-pill\">P0404</span>: EGR Valve Defective — عطل ميكانيكي في الـ**EGR valve**.",
                "<span class=\"dtc-pill\">P0420</span>: Catalyst System Efficiency Below Threshold — كاتالايزر ضعيف (من الكربون).",
                "<span class=\"dtc-pill\">P0016</span>: Crankshaft/Camshaft Position Correlation (Bank 1 Sensor A) — مشكلة توقيت (timing chain stretched).",
                "<span class=\"dtc-pill\">P0300</span>: Random Misfire — حقن غير متساوي أو شمعات.",
                "<span class=\"dtc-pill\">P0171</span>/<span class=\"dtc-pill\">P0172</span>: Fuel Trim Lean/Rich — تسرب هواء أو MAF متسخ.",
                "<span class=\"dtc-pill\">P0335</span>: CKP Sensor Circuit — حساس الكرنك مقطوع.",
                "<span class=\"dtc-pill\">U0101</span>: Lost Communication with TCM (6T40 only) — مشكلة شبكة CAN.",
            ],
            "special_functions_hint": (
                "VVT Solenoid Test | Trans Adapt Reset | Coolant Bleeding"
            ),
        },
    ),
    # ── Chevrolet Aveo (T200/T300) ────────────────────────────────────────
    (
        "chevrolet",
        ["aveo"],
        2008,
        2026,
        {
            "ecu_family": "Delphi MT80 / GM E83",
            "engine_code": "F14D4 / F16D4 1.4-1.6L DOHC 16V",
            "transmission_code": "Aisin 81-40LE / 6T30",
            "known_issues": [
                "<span class=\"dtc-pill\">P0300</span>: Random misfire — check ignition coil pack",
                "<span class=\"dtc-pill\">P0134</span>: O2 sensor 1 no activity — check harness proximity",
                "Throttle body: <span class=\"dtc-pill\">P0121</span> — clean carbon and perform learn",
            ],
            "special_functions_hint": (
                "Coil/Spark Test | Throttle Relearn | Fuel Trim Reset"
            ),
        },
    ),
    # ── Chevrolet Optra (J200) ───────────────────────────────────────────
    (
        "chevrolet",
        ["optra"],
        2005,
        2026,
        {
            "ecu_family": "Delphi HV240 / MR140",
            "engine_code": "F16D3 1.6L / F18D3 1.8L DOHC",
            "transmission_code": "ZF 4HP16 / AISIN AW81-40LE",
            "known_issues": [
                "<span class=\"dtc-pill\">P0404</span>: EGR range/performance — clean passage and valve",
                "Transmission: <span class=\"dtc-pill\">P0741</span> TCC jump — solenoids need cleaning",
                "Cam sensor leak: oil causes <span class=\"dtc-pill\">P0341</span> phantom codes",
            ],
            "special_functions_hint": "EGR Adaptation | TCC Test | IAC Valve Reset",
        },
    ),
    # ── Peugeot 5008 (T8/P87) ─────────────────────────────────────────────
    (
        "peugeot",
        ["5008"],
        2010,
        2026,
        {
            "ecu_family": "Bosch MEVD17.4.4 / Delphi DCM7.1",
            "engine_code": "1.6T EP6CDT / BlueHDi 1.6-2.0L",
            "transmission_code": "Aisin EAT6 / EAT8 AT",
            "known_issues": [
                "EP6 (THP): <span class=\"dtc-pill\">P0016</span> timing chain stretch — check tensioner",
                "<span class=\"dtc-pill\">P1336</span>/<span class=\"dtc-pill\">P1337</span>/<span class=\"dtc-pill\">P1338</span>: Misfires — HPFP pressure drift check",
                "AdBlue: <span class=\"dtc-pill\">P20E8</span> pressure low — crystalized tank/pump",
                "EAT6: <span class=\"dtc-pill\">P0700</span> shift lag — fluid interval crucial at 60k km",
            ],
            "special_functions_hint": (
                "Chain Stretch Test | HPFP Pressure Check | AdBlue Reset"
            ),
        },
    ),
    # ── Ford (Focus MENA/Global) ────────────────────────
    (
        "ford",
        ["focus"],
        2012,
        2026,
        {
            "ecu_family": "Bosch MED17.2 / Continental SID208",
            "engine_code": "Ecoboost 1.0T / 1.5T / 2.0L Duratec",
            "transmission_code": "6F35 / DPS6 Powershift",
            "known_issues": [
                "DPS6: <span class=\"dtc-pill\">P0902</span> clutch actuator circuit — grounding issue",
                "Ecoboost: <span class=\"dtc-pill\">P0234</span> turbo overboost — check wastegate solenoid",
                "SYNC: <span class=\"dtc-pill\">U0100</span> loss of comm — battery voltage drop",
            ],
            "special_functions_hint": (
                "Powershift Clutch Learn | Turbo VGT Reset | BMS Reset"
            ),
        },
    ),
    # ── Suzuki (Swift/Ciaz) ───────────────────────────────
    (
        "suzuki",
        ["swift", "ciaz"],
        2014,
        2026,
        {
            "ecu_family": "Bosch ME17.9.64 / Denso",
            "engine_code": "K14C Boosterjet / K15B / K12M",
            "transmission_code": "Aisin 4AT / 6AT / 5MT",
            "known_issues": [
                "<span class=\"dtc-pill\">P0121</span>: Throttle sensor fault — clean connector for poor contact",
                "Aisin 4AT: <span class=\"dtc-pill\">P0751</span> solenoid A — dirty fluid causes flair",
                "Steering: <span class=\"dtc-pill\">C1122</span> ESP signal fault — check battery health",
            ],
            "special_functions_hint": (
                "Throttle Learning | EPS Calibration | Trans-axle Reset"
            ),
        },
    ),
    # ── BYD (F3/L3) ──────────────────────────────────────────────
    (
        "byd",
        ["f3", "l3"],
        2010,
        2026,
        {
            "ecu_family": "Bosch M7.8 / Delphi MT22.1",
            "engine_code": "473QE / BYD476ZQA 1.5T",
            "transmission_code": "5MT / 6-DCT / 6AT",
            "known_issues": [
                "BYD 6-DCT: <span class=\"dtc-pill\">P0810</span> clutch position error — motor wear",
                "<span class=\"dtc-pill\">P0300</span>: Misfire on 473QE — check coil harness",
                "Can-bus: <span class=\"dtc-pill\">U0100</span> loss of engine comm — check grounding",
            ],
            "special_functions_hint": (
                "DCT Clutch Learn | EMS Reset | T-Box Diagnostics"
            ),
        },
    ),
]


def _enrich_vin_profile(make: str, model: str, year: str) -> _PowertrainProfile:
    """Cross-reference decoded data against the powertrain database."""
    make_lower = make.lower()
    model_lower = model.lower()
    try:
        year_int = int(year)
    except (ValueError, TypeError):
        year_int = 0

    best_match = None
    for p_make, p_keywords, p_start, p_end, profile in _POWERTRAIN_PROFILES:
        if p_make != make_lower:
            continue
        if year_int != 0 and (year_int < p_start or year_int > p_end):
            continue
        if any(kw in model_lower for kw in p_keywords):
            return profile
        if best_match is None:
            best_match = profile
    return best_match or {}


def apply_enrichment(
    response: VINDecodeResponse,
    make: str | None = None,
    model: str | None = None,
    year: str | None = None,
) -> VINDecodeResponse:
    """Mutate response in-place with powertrain intelligence and return it."""
    profile = _enrich_vin_profile(
        make or response.make,
        model or "",
        year or response.model_year,
    )
    if not profile:
        return response

    notes = []
    if e_code := profile.get("engine_code"):
        response.engine_code = str(e_code)
    if t_code := profile.get("transmission_code"):
        response.transmission_code = str(t_code)

    issues = profile.get("known_issues")
    if isinstance(issues, list) and issues:
        response.known_issues = issues
        notes.append("Kbase Faults: " + "; ".join(issues[:2]))
    if hints := profile.get("special_functions_hint"):
        response.special_functions_hint = str(hints)
        notes.append("X431: " + str(hints))

    if notes:
        # Avoid overwriting Bubble 1 (Technical Brief) if it was already set by Layer 2
        if not response.technical_brief:
            response.technical_brief = "\n".join(notes)

    return response
