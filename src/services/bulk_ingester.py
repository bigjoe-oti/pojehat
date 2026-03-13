import httpx
from bs4 import BeautifulSoup
from src.services.web_ingester import WebIngester
from src.domain.pdf_parser import ingest_manual

class BulkIngester:
    def __init__(self):
        self.web_ingester = WebIngester()

    async def scout_fcc_id(self, fcc_id: str):
        """
        Scrapes fccid.io for internal photos of automotive modules.
        """
        print(f"[*] Scouring FCC ID: {fcc_id} for hardware internals...")
        url = f"https://fccid.io/{fcc_id}/internal-photos"
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url, timeout=30.0)
                if response.status_code != 200:
                    print(f"[!] FCC ID {fcc_id} not found or blocked.")
                    return
                
                soup = BeautifulSoup(response.text, "html.parser")
                # Look for direct links to internal photo PDFs or high-res images
                links = soup.find_all("a", href=True)
                target_links = [
                    link_tag["href"] for link_tag in links 
                    if "internal" in link_tag["href"].lower() 
                    and link_tag["href"].endswith(".pdf")
                ]
                
                if not target_links:
                    print(f"[!] No internal photo PDFs found for {fcc_id}.")
                    return

                for link in target_links:
                    absolute_link = (
                        link if link.startswith("http") 
                        else f"https://fccid.io{link}"
                    )
                    print(f"[+] Found Hardware Internal: {absolute_link}")
                    # Download and ingest
                    download_path = await self.web_ingester.download_pdf(absolute_link)
                    if download_path:
                        await ingest_manual(
                            download_path, 
                            vehicle_context=f"Hardware Hardware: {fcc_id}"
                        )
            except Exception as e:
                print(f"[!] Error scouting FCC ID {fcc_id}: {e}")

    async def ingest_targeted_manuals(self, manual_list: list[dict]):
        """
        manual_list: list of {"url": str, "context": str}
        """
        for item in manual_list:
            print(f"[*] Processing Target: {item['context']} -> {item['url']}")
            try:
                if item['url'].endswith(".pdf"):
                    # Direct PDF download and ingest
                    d_path = await self.web_ingester.download_pdf(item['url'])
                    if d_path:
                        await ingest_manual(d_path, vehicle_context=item['context'])
                elif item['url'].endswith((".png", ".jpg", ".jpeg")):
                    # Direct Image download and ingest
                    d_path = await self.web_ingester.download_pdf(item['url'])
                    if d_path:
                        await ingest_manual(d_path, vehicle_context=item['context'])
                else:
                    # Web crawling via WebIngester
                    await self.web_ingester.process_url(item['url'], item['context'])
            except Exception as e:
                print(f"[!] Error ingesting {item['context']}: {e}")

    async def ingest_chipset_datasheets(self, chipsets: list[dict]):
        """
        chipsets: list of {"name": str, "url": str}
        """
        for chip in chipsets:
            print(f"[*] Ingesting Chipset Datasheet: {chip['name']}")
            try:
                download_path = await self.web_ingester.download_pdf(chip['url'])
                if download_path:
                    await ingest_manual(download_path, vehicle_context=f"Chipset Datasheet: {chip['name']}")
            except Exception as e:
                print(f"[!] Error ingesting chipset {chip['name']}: {str(e)}")
