"""
Mega-Ingestion Orchestration Script for Pojehat (V4 - Corpus Expansion).
Triaged from research results — 3 batches by reliability and content type.

Batch 1: Direct PDFs — highest reliability, no scraping needed
Batch 2: Structured HTML pages — Jina-processable, ecu.design, at-manuals, etc.
Batch 3: Viewer pages — manualslib, cardiagn (requires viewer fallback)

EXCLUDED (do not add back without verification):
- scribd.com URLs — login-walled, Jina returns login page not content
- slideshare.net URLs — session-based, content not accessible to scrapers
- Section 8 homepage URLs — not content pages, ingestion produces nothing
- Chery A21/A5/A1 manualslib entries — wrong models, not Tiggo 7
"""

import asyncio
import logging
import os

import httpx

from src.services.web_ingester import web_ingester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BATCH 1 — Direct PDFs
# Highest reliability. web_ingester routes .pdf URLs directly to ingest_manual.
# Run this first — it fills the most critical gaps with the least risk.
# ---------------------------------------------------------------------------

BATCH_1_DIRECT_PDFS = [
    # --- OEM Manuals ---
    {
        "url": "https://en.chery-club.eu/manual_download.php?id=250",
        "context": "Chery Tiggo 7 Electrical Wiring Diagram",
    },
    {
        "url": "https://fixmycarinfo.com/wp-content/uploads/2025/08/KIA-Cerato-4-BD-2023-Wiring-Diagrams.pdf",
        "context": "Kia Cerato BD 2023 Wiring Diagrams",
    },
    {
        "url": "https://www.hyundai.com/content/dam/hyundai/template_en/en/data/marketing/manual/accent/2017accent-full-version.pdf",
        "context": "Hyundai Accent RB 2017 Owner Manual",
    },
    {
        "url": "https://s3cf792cad773e861.jimcontent.com/download/version/1529652344/module/12693091422/name/Mitsubishi%20Lancer%20Evolution%208%20Electrical.pdf",
        "context": "Mitsubishi Lancer EX Electrical Wiring Diagrams",
    },
    # --- ECU Pinouts (Direct PDFs) ---
    {
        "url": "https://ecutools.vn/wp-content/uploads/2024/10/ECUTools-Vietnam-Pinout-Dimsport-Bench-Mode-Bosch-ME17.9.11-ME17.9.11.1-MEG17.9.13-Hyundai-Kia.pdf",
        "context": "Bosch ME17.9.11 ECU Pinout Hyundai Kia Nissan",
    },
    {
        "url": "https://ecu.design/files/ecu_pinout/delphi_mt86_irom_tc1766_kia_hyundai.pdf",
        "context": "Delphi MT86 ECU Pinout Kia Hyundai Renault Logan Peugeot 301",
    },
    {
        "url": "https://www.ecuhelpshop.com/uploads/item/168188854966658468.pdf",
        "context": "Bosch ME17.9.11 ME17.9.21 ECU Pinout Nissan Hyundai Kia",
    },
    # --- DTC Code Databases (Direct PDFs) ---
    {
        "url": "https://nic-tec.com/wp-content/uploads/2019/02/Nissan.pdf",
        "context": "Nissan OBD DTC Fault Codes All Modes",
    },
    {
        "url": "https://sc35ef6025435ca24.jimcontent.com/download/version/1677867886/module/9646756682/name/Kia%20OBD_OBD2%20Codes%20%E2%80%93%20Trouble%20Codes.pdf",
        "context": "Kia OBD OBD2 Trouble Codes P0 P1 Complete List",
    },
    {
        "url": "https://s3cf792cad773e861.jimcontent.com/download/version/1742838309/module/15688750122/name/Toyota%20Engine%20Fault%20Codes%20DTC.pdf",
        "context": "Toyota Engine Fault Codes DTC P0 P1 Complete List",
    },
    {
        "url": "https://toyotamanuals.gitlab.io/pz471-z0020-ca/htmlweb/rm/rm731e/m_di_0015.pdf",
        "context": "Toyota ABS DTC Codes Diagnostic Trouble Codes",
    },
    {
        "url": "https://www.dmv.de.gov/VehicleServices/inspections/pdfs/dtc_list.pdf",
        "context": "Standard OBD-II DTC Codes Complete List All Manufacturers",
    },
    {
        "url": "https://cim.mcgill.ca/~cprahacs/gtcs/DTC_Codes.pdf",
        "context": "OBD DTC Diagnostic Trouble Code Charts Reference",
    },
    # --- Sensor Specifications (Direct PDFs — MENA-specific where available) ---
    {
        "url": "https://carmanit.co/wp-content/uploads/2020/12/6.-Signal-Analysis_Oxygen-sensor-MENA.pdf",
        "context": "Oxygen Sensor Signal Analysis Waveforms MENA Region",
    },
    {
        "url": "https://carmanit.co/wp-content/uploads/2020/11/2.-Signal-Analysis_Crank-position-sensor-MENA.pdf",
        "context": "Crankshaft Position Sensor Signal Analysis MENA Region",
    },
    {
        "url": "https://thegrouptrainingacademy.com/wp-content/uploads/sites/2/2019/06/LBT-212-Waveform-web.pdf",
        "context": "Oxygen Sensor Waveform Analysis Testing Procedures",
    },
    {
        "url": "https://www.walkerproducts.com/wp-content/uploads/2020/04/O2-Sensor-101-WF37-137A.pdf",
        "context": "Oxygen Sensor O2 Specifications Testing Values",
    },
    {
        "url": "https://www.walkerproducts.com/wp-content/uploads/2020/06/Camshaft-Crankshaft_April-2019.pdf",
        "context": "Camshaft Crankshaft Position Sensor Specifications Testing",
    },
    {
        "url": "https://autoditex.com/cms/user/files/mafwaveforms/mafsensorwaveformsen.pdf",
        "context": "MAF Sensor Waveforms Signal Analysis Specifications",
    },
    {
        "url": "https://smogtechinstitute.com/smogtech/media/attachments/2024/03/12/ch-4-sensors-and-actuators.pdf",
        "context": "Automotive Sensors Actuators Specifications Testing Procedures",
    },
    {
        "url": "https://www.walkerproducts.com/wp-content/uploads/2020/06/Camshaft-Crankshaft_April-2019.pdf",
        "context": "Camshaft Crankshaft Position Sensor Resistance Waveform Values",
    },
    {
        "url": "https://jameshalderman.com/wp-content/uploads/2019/04/aepd_page_59.pdf",
        "context": "Throttle Position Sensor Crankshaft Position Sensor Specifications",
    },
    {
        "url": "https://exxotest.com/content/uploads/2018/03/GU_DT-M006_EN.pdf",
        "context": "Wheel Speed Sensor Crankshaft Sensor Testing Oscilloscope",
    },
    {
        "url": "https://delcoline.com/wp-content/uploads/2017/02/Oxygen-Sensors.pdf",
        "context": "Oxygen Sensor Types Wiring Resistance Voltage Specifications",
    },
    # --- CAN Bus & Network Protocols (Direct PDFs) ---
    {
        "url": "https://raw.githubusercontent.com/Microrain-zh/uds_protocol/master/ISO_14229-1_2013.en.PDF.pdf",
        "context": "UDS ISO 14229 Unified Diagnostic Services Protocol Technical",
    },
    {
        "url": "https://www.can-cia.org/fileadmin/cia/documents/publications/cnlm/june_2022/cnlm_22-2_p24_iso_14229_uds_protocol-_automotive_diagnostics_pooja_todakar_iwave_systems.pdf",
        "context": "UDS ISO 14229 Automotive Diagnostics Protocol Guide",
    },
    {
        "url": "https://cdn.standards.iteh.ai/samples/72439/d6db7450800d4ccf859284e1a57bb23d/ISO-14229-1-2020.pdf",
        "context": "ISO 14229-1 2020 UDS Unified Diagnostic Services Standard",
    },
    {
        "url": "https://cdn.vector.com/cms/content/know-how/_application-notes/AN-IND-1-026_DoIP_in_CANoe.pdf",
        "context": "DoIP Diagnostic over IP CAN Bus Automotive Protocol",
    },
    {
        "url": "https://www.autosar.org/fileadmin/standards/R20-11/CP/AUTOSAR_SWS_DiagnosticOverIP.pdf",
        "context": "DoIP AUTOSAR Diagnostic over IP Specification",
    },
    {
        "url": "https://automotive.softing.com/fileadmin/sof-files/pdf/de/ae/poster/DoIP_faltblatt_softing.pdf",
        "context": "DoIP Diagnostic over IP Overview Architecture",
    },
    {
        "url": "https://lascarelectronics.com/wp-content/uploads/ppadesignstudio_can-bus-element-user-guide_iss1_04-19.pdf",
        "context": "CAN Bus Protocol Guide Wiring Architecture",
    },
    {
        "url": "https://www.fwmurphy.com/wp-content/uploads/2022/08/2215415.pdf",
        "context": "CAN Bus Wiring Diagrams Connections Automotive",
    },
    {
        "url": "https://incartec.blob.core.windows.net/instructions/29-UC-050%20CONNECTIONS%20diagrams.pdf",
        "context": "CAN Bus Connections Wiring Diagrams Automotive",
    },
    # --- Transmission (Direct PDFs) ---
    {
        "url": "https://atracom.blob.core.windows.net/webinars/import/nissan_cvt_internal.pdf",
        "context": "Jatco CVT Nissan Internal Technical Training Manual",
    },
    {
        "url": "https://www.wittrans.com/catalogs/2018-WIT-CVT.pdf",
        "context": "Jatco CVT7 CVT8 Reference Manual Specifications Nissan",
    },
    {
        "url": "https://tdreman.com/wp-content/uploads/CVT-8-TD-REMAN-Installation-Guide.pdf",
        "context": "Jatco CVT8 Installation Guide Nissan",
    },
    {
        "url": "https://atoc.ru/uploads/manual/5fb52ae227458.pdf",
        "context": "Jatco CVT Technical Manual Nissan Transmission",
    },
    {
        "url": "https://atracom.blob.core.windows.net/webinars/import%2Fa6mf1_rebuild.pdf",
        "context": "Hyundai A6MF1 Automatic Transmission Rebuild Guide",
    },
    {
        "url": "https://akpphelp.ru/assets/template/redesign/files/guidelines/a6lf1-rukodovstvo-manual-1.pdf",
        "context": "Hyundai A6LF1 Automatic Transmission Service Manual",
    },
    # --- MG ZS EV & HV Systems (Direct PDFs) ---
    {
        "url": "https://www.mg.co.uk/sites/default/files/2021-11/New%20MG%20ZS%20EV%20Owner%20Manual.pdf",
        "context": "MG ZS EV Owner Manual High Voltage HV Safety",
    },
    {
        "url": "https://www.mg.co.uk/sites/default/files/2021-11/MG%20ZS%20EV%20MY19%20Owner%20Manual.pdf",
        "context": "MG ZS EV MY19 Owner Manual Charging HV Battery",
    },
    {
        "url": "https://www.mg.co.uk/sites/default/files/2025-04/MG-ZS-Owner-Manual.pdf",
        "context": "MG ZS Owner Manual 2025 HV Safety Procedures",
    },
    {
        "url": "https://s3-ap-southeast-2.amazonaws.com/files.digitaldealer.com.au/mgmotor/files/ZS-EV-Owners-Manual.pdf",
        "context": "MG ZS EV Owner Manual Australia Charging Diagnostics",
    },
    {
        "url": "https://www.globalsuzuki.com/xev_battery/download/pdf/idis_common_hv_en.pdf",
        "context": "HV Battery High Voltage Safety Diagnostics EV Hybrid",
    },
    {
        "url": "https://b964d3e6d165a571306324c2c0e36a50.cdn.bubble.io/f1755023197204x661358951381841900/MG%20%28SAIC%29%28DTC%29_989350004585_20250812010801.pdf",
        "context": "MG SAIC DTC Diagnostic Trouble Codes All Systems",
    },
]

# ---------------------------------------------------------------------------
# BATCH 2 — Structured HTML Pages
# Jina-processable or structured HTML with technical tables.
# ecu.design pages are clean HTML with pinout tables — high value.
# ---------------------------------------------------------------------------

BATCH_2_HTML_PAGES = [
    # --- ECU Pinouts (HTML) ---
    {
        "url": "https://ecu.design/ecu-pinout/pinout-bosch-me17-9-11-irom-tc1762-egpt-kia-hyundai/",
        "context": "Bosch ME17.9.11 ECU Pinout Kia Hyundai Nissan",
    },
    {
        "url": "https://ecu.design/ecu-pinout/pinout-bosch-me17-9-21-irom-tc1724-egpt-ducati/",
        "context": "Bosch ME17.9.21 ECU Pinout Nissan Kia",
    },
    {
        "url": "https://ecu.design/ecu-pinout/pinout-delphi-mt86-irom-tc1766-kia-hyundai/",
        "context": "Delphi MT86 ECU Pinout Kia Hyundai Renault Peugeot",
    },
    {
        "url": "https://ecu.design/ecu-pinout/pinout-siemens-sid807-xrom-tc1796-psa/",
        "context": "Siemens SID807 ECU Pinout Peugeot 301 PSA",
    },
    {
        "url": "https://www.ecuhelp.org/kt200ii-read-write-kia-bosch-me17-9-21-on-bench/",
        "context": "Bosch ME17.9.21 Bench Mode Pinout Kia Nissan",
    },
    {
        "url": "http://blog.obdii365.com/2023/07/13/delphi-mt80-boot-pinout-to-foxflash-ktag-flex/",
        "context": "Delphi MT80 Boot Pinout Renault Logan Peugeot 301",
    },
    {
        "url": "http://blog.vvdishop.com/vvdi-prog-delphi-mt86-3500-gearbox-pinout/",
        "context": "Delphi MT86 Pinout Gearbox Connector Kia Hyundai",
    },
    # --- DTC Codes (HTML) ---
    {
        "url": "https://www.autonationhyundaitempe.com/service/obd-ii-trouble-codes.htm",
        "context": "Hyundai OBD-II Trouble Codes P1xxx Manufacturer Specific",
    },
    # --- Network Protocols (HTML) ---
    {
        "url": "https://www.csselectronics.com/pages/uds-protocol-tutorial-unified-diagnostic-services",
        "context": "UDS Protocol Tutorial Unified Diagnostic Services Automotive",
    },
    # --- Transmission (HTML) ---
    {
        "url": "https://at-manuals.com/manuals/jf016e-cvt8/",
        "context": "Jatco CVT8 JF016E Repair Manual Nissan",
    },
    {
        "url": "https://at-manuals.com/manuals/a6lf123-a6gf1-a6mf12-2/",
        "context": "Hyundai A6LF1 A6GF1 A6MF1 Automatic Transmission Repair Manual",
    },
    # --- MG ZS EV OBD PIDs (HTML) ---
    {
        "url": "https://sidecar.clutch.engineering/cars/mg/zs-ev/",
        "context": "MG ZS EV OBD-II PIDs Live Data Parameters EV",
    },
]

# ---------------------------------------------------------------------------
# BATCH 3 — Viewer Pages (manualslib, cardiagn)
# These require the viewer fallback in web_ingester.
# Run last — highest failure risk, but potentially highest volume content.
# NOTE: cardiagn.com URLs are category pages, not direct manuals.
#       web_ingester will attempt Jina scrape → viewer fallback chain.
# ---------------------------------------------------------------------------

BATCH_3_VIEWER_PAGES = [
    # --- OEM Manuals via manualslib ---
    {
        "url": "https://www.manualslib.com/manual/827375/Chery-Automobile.html",
        "context": "Chery Automobile Service Manual",
    },
    {
        "url": "https://www.manualslib.com/manual/1950379/Skoda-Octavia.html",
        "context": "Skoda Octavia A7 Workshop Manual",
    },
    {
        "url": "https://www.manualslib.com/manual/1226408/Skoda-A7-Octavia.html",
        "context": "Skoda Octavia A7 Owner Manual",
    },
    # --- OEM Manuals via cardiagn (category pages — Jina will extract listings) ---
    {
        "url": "https://cardiagn.com/nissan/sentra/",
        "context": "Nissan Sunny B17 Sentra Service Repair Manual",
    },
    {
        "url": "https://cardiagn.com/toyota-corolla-e210-2019-2022-service-and-repair-manual/",
        "context": "Toyota Corolla E210 2019 2022 Service Repair Manual",
    },
    {
        "url": "https://cardiagn.com/chery/chery-tiggo/",
        "context": "Chery Tiggo 7 Service Repair Wiring Manual",
    },
    {
        "url": "https://cardiagn.com/mg/mg-zs-zs-ev/",
        "context": "MG ZS ZS EV Service Repair Wiring Manual",
    },
    {
        "url": "https://cardiagn.com/peugeot/",
        "context": "Peugeot 301 Service Repair Wiring Manual",
    },
    {
        "url": "https://cardiagn.com/renault/renault-logan-sandero/",
        "context": "Renault Logan Sandero Service Repair Wiring Manual",
    },
    {
        "url": "https://cardiagn.com/kia/kia-cerato-forte/",
        "context": "Kia Cerato Forte BD Service Repair Wiring Manual",
    },
    {
        "url": "https://cardiagn.com/mitsubishi/lancer/",
        "context": "Mitsubishi Lancer EX Service Repair Wiring Manual",
    },
    {
        "url": "https://cardiagn.com/dacia/dacia-logan/",
        "context": "Renault Logan Dacia Service Repair Manual",
    },
    # --- MG ZS EV Additional ---
    {
        "url": "https://s7ap1.scene7.com/is/content/mgmotor/mgmotor/documents/MG%20ZSEV%20-%20Brochure.pdf",
        "context": "MG ZS EV Technical Specifications Brochure",
    },
]

# ---------------------------------------------------------------------------
# EXPLICITLY EXCLUDED — DO NOT REINSTATE WITHOUT VERIFICATION
# ---------------------------------------------------------------------------
# scribd.com — login-walled, Jina returns auth page not content
# slideshare.net — session-based URLs, content not scrapable
# Section 8 homepage URLs — not content pages
# manualslib.com/manual/1437675 (Chery A21) — wrong model, not Tiggo 7
# manualslib.com/manual/1799739 (Chery A5 2007) — wrong model
# manualslib.com/manual/2901580 (Chery A1 2009) — wrong model
# manualslib.com/manual/4033554 (Skoda Kamiq) — wrong model
# manualslib.com/manual/853247 (Skoda Citigo) — wrong model
# manualslib.com/manual/951382 (Skoda Fabia) — wrong model
# manualslib.com/manual/1260581 (Skoda Kodiaq) — wrong model
# manualslib.com/manual/1287317 (Skoda Octavia 1999) — wrong generation
# manualslib.com/manual/375264 (Skoda Octavia Tour) — wrong generation
# gsitlc.ext.gm.com — GM internal portal, access restricted
# uds.readthedocs.io — dynamic URL, session-based PDF generation
# diyservicemanuals.com — paywall
# alldata.com MAF sensor — redirects to login
# ueitest.com — product manual, not diagnostic content
# Mitsubishi Lancer Evolution 8 — Evolution model, not Lancer EX Egypt market
# ---------------------------------------------------------------------------


async def _is_processable_url(url: str) -> bool:
    """HEAD request to verify URL returns accessible content."""
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
        ) as client:
            resp = await client.head(url)
            ct = resp.headers.get("content-type", "")
            return resp.status_code == 200 and any(
                x in ct
                for x in [
                    "pdf",
                    "html",
                    "text",
                    "image/png",
                    "image/jpeg",
                    "image/webp",
                ]
            )
    except Exception:
        return False


async def run_batch(
    batch: list[dict], batch_name: str, semaphore_limit: int = 2
) -> None:
    """Run a batch of ingestion tasks with concurrency control."""
    logger.info(
        "Starting %s — %d assets, %d concurrent workers",
        batch_name,
        len(batch),
        semaphore_limit,
    )
    semaphore = asyncio.Semaphore(semaphore_limit)
    success_count = 0
    skip_count = 0
    fail_count = 0

    async def _process_one(item: dict) -> None:
        nonlocal success_count, skip_count, fail_count
        async with semaphore:
            url, context = item["url"], item["context"]
            if not await _is_processable_url(url):
                logger.warning("Skipping non-accessible URL: %s", url)
                skip_count += 1
                return
            try:
                await web_ingester.process_url(url, context)
                success_count += 1
                logger.info("Ingested: %s", context)
            except Exception as e:
                fail_count += 1
                logger.error("Failed: %s | %s", context, str(e))

    await asyncio.gather(*[_process_one(item) for item in batch])
    logger.info(
        "%s complete — success=%d skip=%d fail=%d",
        batch_name,
        success_count,
        skip_count,
        fail_count,
    )


async def run_mega_ingest(batch: str = "all") -> None:
    """
    Run corpus ingestion by batch.

    Usage:
        python mega_ingest.py              # runs all batches
        BATCH=1 python mega_ingest.py      # direct PDFs only
        BATCH=2 python mega_ingest.py      # HTML pages only
        BATCH=3 python mega_ingest.py      # viewer pages only

    Recommended order for first run: 1 → audit → 2 → audit → 3 → audit
    Run the audit query after each batch to measure coverage improvement:
        "analyze your knowledge base and rate your confidence by domain"
    """
    batch_target = os.environ.get("BATCH", batch)

    if batch_target in ("1", "all"):
        await run_batch(BATCH_1_DIRECT_PDFS, "BATCH 1 — Direct PDFs", semaphore_limit=2)

    if batch_target in ("2", "all"):
        await run_batch(BATCH_2_HTML_PAGES, "BATCH 2 — HTML Pages", semaphore_limit=2)

    if batch_target in ("3", "all"):
        await run_batch(
            BATCH_3_VIEWER_PAGES, "BATCH 3 — Viewer Pages", semaphore_limit=1
        )

    logger.info("Mega-Ingestion V4 complete.")


if __name__ == "__main__":
    asyncio.run(run_mega_ingest())
