import asyncio
import logging
from pathlib import Path
from src.domain.pdf_parser import ingest_manual

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PDF_DIR = Path("/Users/OTI_1/Desktop/pojehat/pdfs/2")

MAPPING = {
    "Automotive_Mechatronics_Bosch_Profession.pdf": "Automotive ECU Brake System EPB Sensor Calibration Bosch",
    "Automotive_Mechatronics_Automotive_Netwo.pdf": "CAN Bus Electronic Transmission Control ABS EPS ADAS Bosch Networking",
    "Development_of_NOx_Estimator_ECU_Models.pdf": "NOx Sensor SCR AdBlue Reset Calibration Diesel ECU Aftertreatment",
    "VGT_and_EGR_Control_of_Common_Rail_Diese.pdf": "VGT Turbocharger EGR Adaptation Common Rail Diesel Engine Control",
    "Tire_Pressure_Checking_Framework_A_Revie.pdf": "TPMS Tire Pressure Monitoring Sensor Relearn Reset Direct Indirect",
    "Automobile_electrical_and_electronic_sys.pdf": "Automotive Electrical Electronic Systems EPS Brakes Diagnostics",
    "pdf_Automotive_Engines_Control_Estimati.pdf": "Engine Control EGR Adaptation Injector Turbo Boost Estimation",
    "Research_on_shifting_process_control_of.pdf": "Automatic Transmission Shift Control Gearbox Relearn Adaptation TCU",
    "Progress_in_Automotive_Transmission_Tech.pdf": "Automotive Transmission Technology DCT CVT Gearbox Adaptation Review",
    "MOTORIZED_BRAKE_CALIPER_PISTON_DEPRESSOR.pdf": "EPB Electronic Parking Brake Caliper Piston Retract Reset Service",
    "Vehicle_Safety_Management_System.pdf": "Vehicle Safety Management ADAS TPMS Brake System Integration",
    "Review_on_Lane_Detection_and_Tracking_Al.pdf": "ADAS Camera Calibration Lane Detection Forward Collision Warning",
    "Semi_Automatically_Parsing_Private_Prot.pdf": "CAN Bus UDS ECU Protocol Parsing In-Vehicle Communication",
    "Turbo_Low_Pressure_Warning_Light.pdf": "Turbocharger Boost Pressure Fault Diagnosis Warning Light",
    "HYDRAULIC_POWER_STEERING_IN_ROAD_VEHICLE.pdf": "Power Steering Motor Angle Sensor EPS Calibration",
    "Bilingual Dictionary of Technical Engineering.pdf": "Arabic Automotive Engineering Technical Dictionary Terminology"
}

async def main():
    if not PDF_DIR.exists():
        logger.error(f"Directory {PDF_DIR} does not exist.")
        return

    logger.info(f"Starting ingestion for folder: {PDF_DIR}")
    
    success = 0
    fail = 0

    for filename, context in MAPPING.items():
        pdf_path = PDF_DIR / filename
        if not pdf_path.exists():
            logger.warning(f"File not found: {filename}. Skipping.")
            continue

        logger.info(f"[*] Ingesting: {filename} -> Context: {context}")
        try:
            result = await ingest_manual(str(pdf_path), vehicle_context=context)
            if result.get("status") == "success":
                logger.info(f"  ✓ Success: {filename}")
                success += 1
            else:
                logger.error(f"  ✗ Failed: {filename} - {result.get('message')}")
                fail += 1
        except Exception as e:
            logger.error(f"  ✗ Error: {filename} - {str(e)}")
            fail += 1

    logger.info(f"Ingestion complete. Success: {success}, Failed: {fail}")

if __name__ == "__main__":
    asyncio.run(main())
