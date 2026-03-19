# ruff: noqa: E501

"""
Mega-Ingestion V5: Technical Standards & Tools.
Orchestrates ingestion of diagnostic protocols (OBD-II, UDS), Bosch ESI systems,
TPMS procedures, and advanced tool manuals (Autel, Launch, Xtool).
Split into two logical batches for systematic ingestion.
"""

import asyncio
import logging

from src.services.web_ingester import web_ingester

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# BATCH 5: Technical Diagnostic Standards & Protocols
MEGA_DATA_V5_BATCH_A = [
    {
        "url": "https://github.com/digitalbond/canbus-utils/blob/master/obdii-pids.json",
        "context": "OBD-II Telemetry JSON Schema - Standard PIDs",
    },
    {
        "url": "https://github.com/rnd-ash/OpenVehicleDiag/blob/main/README.md",
        "context": "UDS Protocol / OpenVehicleDiag Implementation",
    },
    {
        "url": "https://github.com/oxibus/automotive_diag/blob/main/README.md",
        "context": "UDS Rust Implementation (automotive_diag) documentation",
    },
    {
        "url": "https://www.mechanexpert.com/wp-content/uploads/2023/01/Diagnostics-Bosch-SIS-trouble-shooting.pdf",
        "context": "Bosch ESI[tronic] SIS Troubleshooting Guide",
    },
    {
        "url": "https://www.downloads.bosch-automotive.com/fileadmin/user_upload/Medialibrary/www.downloads.bosch-automotive.com/DDM_Assets/News/News_2022_3_en.pdf",
        "context": "Bosch ESI[tronic] 2.0 Updates 2022/3",
    },
    {
        "url": "https://help.boschdiagnostics.com/ESItronic/Content/PDF/en/ESItronic2_worksheet02_with_answers.pdf",
        "context": "Bosch ESI[tronic] worksheet — Diagnostics Training",
    },
    {
        "url": "https://static.nhtsa.gov/odi/tsbs/2023/MC-10244287-0001.pdf",
        "context": "TSB (Kia/Engine) - NHTSA Technical Bulletin",
    },
    {
        "url": "https://static.nhtsa.gov/odi/tsbs/2018/MC-10129797-9999.pdf",
        "context": "TSB (Honda/ATF) - NHTSA Technical Bulletin",
    },
    {
        "url": "https://static.oemdtc.com/NHTSA-PDFs/MC-11023521-0001.pdf",
        "context": "TSB (Subaru) - NHTSA Technical Bulletin",
    },
    {
        "url": "https://launchtechusa.com/wp-content/uploads/2025/10/HIGH-RES-Launch_ADAS_1025_v4_FLATTENED-with-spreads.pdf",
        "context": "Launch ADAS Target Guide - Calibration Equipment",
    },
    {
        "url": "https://cdn.vector.com/cms/content/application-areas/ecu-calibration/Docs/AUTOSAR_Calibration_UserManual_EN.pdf",
        "context": "AUTOSAR Calibration User Manual - Vector Informatik",
    },
    {
        "url": "https://hps.vi4io.org/_media/research/theses/ashcon_mohseninia_open_source_vehicle_ecu_diagnostics_and_testing_platform.pdf",
        "context": "ECU Coding & Open Source Diagnostics Research - Thesis DB",
    },
]

# BATCH 6: Service Tools, TPMS & OEM Manuals
MEGA_DATA_V5_BATCH_B = [
    {
        "url": "https://www.laspositascollege.edu/auto/assets/resources/import_tpms_relearns_1-4.pdf",
        "context": "TPMS Reset Guide - Import Vehicles",
    },
    {
        "url": "https://lib.americanmuscle.com/files/tpms-reset-instructions.pdf",
        "context": "TPMS Reset Instructions - Performance/Aftermarket",
    },
    {
        "url": "https://jameshalderman.com/wp-content/uploads/2021/08/TPMS_2009-2020_Relearn_Procedures.pdf",
        "context": "TPMS Relearn Procedures (2009-2020) - James Halderman",
    },
    {
        "url": "https://manuals.harborfreight.com/manuals/70000-70999/70836-193175515179.pdf",
        "context": "Harbor Freight Diagnostic Tool Manual",
    },
    {
        "url": "https://www.autel.com/u/cms/www/202402/26082614tk3o.pdf",
        "context": "Autel MaxiCOM User Manual (2024)",
    },
    {
        "url": "https://csr.innova.com/Content/Manual/Innova/INNOVA-SDS50-SDS-Tech-Manual-v22.06.04.pdf",
        "context": "Innova SDS50 SDS Tech Manual",
    },
    {
        "url": "https://www.xtooltech.com/official/product_document/1666685648685.pdf",
        "context": "Xtool Diagnosis User Manual",
    },
    {
        "url": "https://www.mycartech.no/wp-content/uploads/Otofix-D1-D1-Lite-brukermanual.pdf",
        "context": "Otofix D1 / D1 Lite User Manual",
    },
    {
        "url": "https://www.autel.com/u/cms/www/202007/03034716k726.pdf",
        "context": "Autel AP200C Bluetooth Dongle Manual",
    },
    {
        "url": "https://www.autel.com/u/cms/www/202306/23031138qcmq.pdf",
        "context": "Autel Battery / EPB Service Tool Manual",
    },
    {
        "url": "https://fcc.report/FCC-ID/XUJPROV4/4559107.pdf",
        "context": "Launch X431 FCC Documentation",
    },
    {
        "url": "https://www.launchtech.co.uk/documents/x431%20Software%20coverage.pdf",
        "context": "Launch X431 Software Coverage Matrix",
    },
    {
        "url": "https://launcheurope.de/wp-content/uploads/2018/09/X-431-PRO-User-Manual.pdf",
        "context": "Launch X-431 PRO User Manual",
    },
    {
        "url": "https://diagnation.com/wp-content/uploads/2024/01/X431_Throttle_III_UserManual-1.pdf",
        "context": "Launch X431 Throttle III User Manual",
    },
    {
        "url": "http://diagnostic-associates.co.uk/downloads/DA-ST512%20Injector%20coding.pdf",
        "context": "Injector Coding Technical Document - DA-ST512",
    },
    {
        "url": "https://ts.thrustmaster.com/faqs/eng/FAQ_Joysticks_Remove_Win_Calibration_All.pdf",
        "context": "Windows Calibration / Joystick Troubleshooting (Sensor Calibration)",
    },
    {
        "url": "https://web-file.topdon.com/topdon-web/information_download/Phoenix-Plus-2-User-Manual.pdf",
        "context": "Topdon Phoenix Plus 2 User Manual",
    },
    {
        "url": "https://www.nissanusa.com/content/dam/Nissan/us/manuals-and-guides/versasedan/2025/2025-nissan-versa-owner-manual.pdf",
        "context": "Nissan Versa (2025) Owner's Manual",
    },
    {
        "url": "https://www.nissanusa.com/content/dam/Nissan/us/manuals-and-guides/rogue/2023/2023-nissan-rogue-quick-reference-guide.pdf",
        "context": "Nissan Rogue (2023) Quick Reference Guide",
    },
    {
        "url": "https://www.nissanusa.com/content/dam/Nissan/us/manuals-and-guides/pathfinder/2024/2024-nissan-pathfinder-owner-manual.pdf",
        "context": "Nissan Pathfinder (2024) Owner's Manual",
    },
    {
        "url": "https://www.nissanusa.com/content/dam/Nissan/us/manuals-and-guides/nissan-z/2024/2024-nissan-z-owner-manual.pdf",
        "context": "Nissan Z Series (2024) Owner's Manual",
    },
    {
        "url": "https://www.byd.com/content/dam/byd-site/eu/support/service/manual/20250327/BYD%20DOLPHIN%20SURF%20Owner's%20Manual-Left-hand%20Drive-EN-General%20version%20for%20Europe-250310.pdf",
        "context": "BYD Dolphin (2025) Owner's Manual - Europe",
    },
]


async def run_mega_ingest_v5():
    """Execute the Technical Standards & Tools (V5) Ingestion."""
    all_data = MEGA_DATA_V5_BATCH_A + MEGA_DATA_V5_BATCH_B
    logger.info(
        f"🚀 Launching Mega-Ingestion (V5) for {len(all_data)} targets..."
    )

    for i, item in enumerate(all_data):
        url = item["url"]
        context = item["context"]

        # Clean URL if it's a google search wrapper (though none seem to be here)
        if "google.com/search?q=" in url:
            url = url.split("google.com/search?q=")[-1].split("&")[0]
            url = url.replace("%3A", ":").replace("%2F", "/")

        logger.info(f"⏳ [{i+1}/{len(all_data)}] Target: {context}")
        logger.info(f"🔗 URL: {url}")
        try:
            await web_ingester.process_url(url, context)
            logger.info(f"✅ Ingested: {context}")
        except Exception as e:
            logger.error(f"❌ Failed: {context} | Error: {str(e)}")
            continue

    logger.info("🏁 Mega-Ingestion V5 Complete.")


if __name__ == "__main__":
    asyncio.run(run_mega_ingest_v5())
