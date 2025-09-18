import scrapy
import json
from scrapy.crawler import CrawlerProcess

# This class is the spider from your linkedin_scraper.py file.
class LinkedInSpider(scrapy.Spider):
    name = "linkedin_scraper"
    
    def __init__(self, linkedin_url=None, *args, **kwargs):
        super(LinkedInSpider, self).__init__(*args, **kwargs)
        if linkedin_url:
            self.start_urls = [linkedin_url]
        else:
            self.start_urls = []
            
    def parse(self, response):
        """
        Parses the LinkedIn profile page to extract all available data
        and provides it as clean, readable text.
        """
        self.logger.info(f"Scraping LinkedIn profile: {response.url}")
        
        # Initialize a dictionary to store all page data
        page_data = {}
        
        try:
            # Extract all text from all elements within the page body
            full_page_text = response.css('body *::text').getall()
            
            # Clean up the text by joining and stripping whitespace
            cleaned_text = ' '.join(t.strip() for t in full_page_text if t.strip())

            # Yield the cleaned text
            yield {
                'full_page_text_clean': cleaned_text
            }

        except Exception as e:
            self.logger.error(f"Error during parsing: {e}")
            
        
def main():
    # Replace this with the LinkedIn URL you want to scrape
    linkedin_url = "https://www.linkedin.com/in/hariharan-r-1760701bb"
    
    # The URL is already a complete URL, no need to add https:// again.
    full_url = linkedin_url
    
    print(f"Starting Scrapy spider to scrape: {full_url}")
    
    # Configure the Scrapy crawler
    process = CrawlerProcess(settings={
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'FEEDS': {
            'output.json': {'format': 'json', 'overwrite': True}
        }
    })
    
    # Run the spider
    process.crawl(LinkedInSpider, linkedin_url=full_url)
    process.start()  # The script will block here until the crawling is finished
    
    print("\nScraping finished. Data saved to output.json.")

if __name__ == "__main__":
    main()
