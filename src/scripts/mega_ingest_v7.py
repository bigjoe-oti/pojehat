# ruff: noqa: E501
"""
Mega-Ingestion V7: Gemini Research Round 2 — Verified Direct PDFs.
Covers: Renault Logan ECU, Jatco CVT7, Mitsubishi CVT, Chery Tiggo 7,
Nissan Sunny, Toyota HV, MG ZS Hybrid, Launch Diagnostics, Hyundai A6LF1.
"""

import asyncio
import logging

from src.services.web_ingester import web_ingester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MEGA_DATA_V7 = [
    {
        "url": "https://logan-renault.narod.ru/dialogys_pdf/MR388LOGAN1.pdf",
        "context": "Renault Logan K7M Siemens EMS3132 ECU Wiring Engine Management Pinout",
    },
    {
        "url": "https://tps.kz/CVT-7-JF015E-RE0F11A-F1CJB-repair-manual.pdf",
        "context": "Jatco CVT7 JF015E RE0F11A Nissan Solenoid Resistance Pressure Specs Repair Manual",
    },
    {
        "url": "https://evoscan.com/manuals/ColtRalliart/065_WM_PDF/GR00004221-23A.pdf",
        "context": "Mitsubishi F1C1A INVECS-III Transmission Solenoid Resistance CVT Specs Lancer EX",
    },
    {
        "url": "https://www.chery-eg.com/media/maintenance_schedules/Tiggo-7-CKD-PM-Schedule.pdf",
        "context": "Chery Tiggo 7 Egypt Official Periodic Maintenance Schedule DCT Fluid Intervals CKD",
    },
    {
        "url": "https://chery-eg.com/media/maintenance_schedules/PM_Table_Tiggo_7.pdf",
        "context": "Chery Tiggo 7 Egypt PM Table Official Maintenance Intervals Mileage",
    },
    {
        "url": "https://autocatalogarchive.com/wp-content/uploads/2022/04/Chery-Tiggo-7-2022-UAE.pdf",
        "context": "Chery Tiggo 7 2022 UAE Specifications Powertrain Mechanical",
    },
    {
        "url": "https://cdn-cms.f-static.com/uploads/186686/normal_5885e5dbd20f1.pdf",
        "context": "Chery Warranty Safety Modification Constraints Electrical Braking",
    },
    {
        "url": "https://www.nissan.co.th/content/dam/Nissan/th/owners/sylphy-owner-manual-EN.pdf",
        "context": "Nissan Sunny B17 Sylphy Wheel Nut Torque 108Nm Owner Manual HR15DE",
    },
    {
        "url": "https://attachments.priuschat.com/attachment-files/2022/07/224479_Corolla_ZWE211_MZEH12_hvdm.pdf",
        "context": "Toyota Corolla E210 Hybrid HV Architecture 201.6V 207.2V 216V Safety",
    },
    {
        "url": "https://artsautomotive.com/wp-content/uploads/Diagnosing-Toyota-High-Voltage-Ground-Isolation-Faults.pdf",
        "context": "Toyota Hybrid P0AA6 HV Ground Isolation 500V Insulation Test MegaOhm",
    },
    {
        "url": "https://www.toyota.com/content/dam/toyota/brochures/pdf/2021/hybridbattery/T-MMS-21CorollaHV.pdf",
        "context": "Toyota Hybrid Battery Safety Boric Acid Neutralization Breach Protocol",
    },
    {
        "url": "https://www.mg.co.uk/sites/default/files/2025-05/MG_ZS_Hybrid_Rescue_Manual.pdf",
        "context": "MG ZS Hybrid Rescue Manual SRS Airbag HV Disconnection Safety 2025",
    },
    {
        "url": "https://launchtechusa.com/wp-content/uploads/2025/10/X-431-Torque-Link-User-Manual.pdf",
        "context": "Launch X431 Torque Link User Manual Actuation Test Data Stream Special Functions",
    },
    {
        "url": "https://launchtechusa.com/wp-content/uploads/2025/10/107013634-CRP-919-Max-User-Manual_EN.pdf",
        "context": "Launch CRP919 Max Diagnostic Logic VIN Special Functions Reset",
    },
    {
        "url": "https://launcheurope.de/launcheurope/wp-content/uploads/2020/10/X-431-EURO-PRO-5-User-Manual-EN.pdf",
        "context": "Launch X431 EuroPro5 Reset Functions Remote Diagnosis Special Functions",
    },
    {
        "url": "https://akpphelp.ru/assets/template/redesign/files/guidelines/a6lf1-rukodovstvo-manual-1.pdf",
        "context": "Hyundai A6LF1 Automatic Transmission Service Manual Solenoid Specs",
    },
]


async def run() -> None:
    total = len(MEGA_DATA_V7)
    success = 0
    failed: list[str] = []

    for i, item in enumerate(MEGA_DATA_V7, 1):
        url = item["url"]
        ctx = item["context"]
        logger.info("[%d/%d] Ingesting: %s", i, total, ctx)
        try:
            await web_ingester.process_url(url, vehicle_context=ctx)
            logger.info("  ✅ OK — %s", url)
            success += 1
        except Exception as e:  # noqa: BLE001
            logger.error("  ❌ FAILED: %s — %s", url, e)
            failed.append(url)

    logger.info("\n=== DONE: %d/%d succeeded ===", success, total)
    if failed:
        logger.warning("Failed URLs:")
        for u in failed:
            logger.warning("  - %s", u)


if __name__ == "__main__":
    asyncio.run(run())
