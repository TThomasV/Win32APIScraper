import json
import os
from typing import Dict, List, Optional

import requests
import tqdm.contrib.concurrent
from bs4 import BeautifulSoup


class Win32APIScraper():
    BASE_ROOT_URL = 'https://learn.microsoft.com/en-us'
    BASE_API_URL =  os.path.join(BASE_ROOT_URL, 'windows/win32/api')

    def check_and_setup_output_path(self, path: Optional[str]) -> None:
        if path:
            self.output_path = path
        else:
            self.output_path = os.path.join(os.path.realpath(__file__), "..", "output.json")

        # Let the exception bubble up if we can't open the path to write to
        with open(self.output_path, 'w'):
            return

    def __init__(self, output_path: Optional[str] = None) -> None:
        self.headers_to_collect = 0
        self.session = requests.Session()
        self.check_and_setup_output_path(output_path)

    def get_function_signature(self, function_details: Dict[str, str]) -> None:
        url = os.path.join(self.BASE_ROOT_URL, function_details['href'][1:])
        resp = self.session.get(url)
        if resp.status_code != 200:
            raise Exception(f'Failed to retireve data from: {url}')

        soup = BeautifulSoup(resp.text, self.html_handler)

        try:
            code_tag = soup.find_all('code', class_="lang-cpp")[0]
            function_details['signature'] = ' '.join(code_tag.string.split())
            function_details['name'] = function_details['toc_title'][:-9]
            del function_details['href']
            del function_details['toc_title']
        # Thrown when can't find a <code> tag on the page
        except IndexError:
            print(f'Failed to extract signature from: {url}')

        return 

    def scrape_headers_for_functions(self, index:int, name: str, path: str) -> Dict[str, str]:
        resp = self.session.get(os.path.join(self.BASE_API_URL, path, 'toc.json'))
        if resp.status_code != 200:
            raise Exception(f'Unexpected response code {resp.status_code} when attempting to GET {name}')

        toc_json = resp.json()

        functions = []
        for func_entry in toc_json['items'][0]['children']:
            if title := func_entry.get('toc_title'):
                if title.endswith(' function'):
                    functions.append(func_entry)

        desc = f'({index+1}/{self.headers_to_collect}) {name}'
        unit=' functions'
        if functions:
            tqdm.contrib.concurrent.thread_map(self.get_function_signature, functions, unit=unit, desc=desc)
        else:
            print(f'{desc}: 0{unit} to collect')

        return functions # type: ignore
    
    def get_headers_list(self) -> List[Dict[str, str]]:
        resp = self.session.get(os.path.join(self.BASE_API_URL, 'toc.json'))
        if resp.status_code != 200:
            raise Exception("Invalid response when attempting to access toc.json")

        json_content = resp.json()
        return json_content['items'][0]['children'][1]['children'] # type: ignore

    def scrape(self) -> None:
        headers_list = self.get_headers_list()
        self.headers_to_collect = len(headers_list)
        content = {}
        try:
            import lxml
            self.html_handler = 'lxml'
        except ImportError:
            self.html_handler = 'html.parser'
        for index, header in enumerate(headers_list):
            content[header['toc_title']] = self.scrape_headers_for_functions(index, header['toc_title'], header['href'])
        
        with open(self.output_path, 'w') as fp:
            json.dump(content, fp, sort_keys=True, indent=4)


def main() -> None:
    scraper = Win32APIScraper()
    scraper.scrape()

if __name__ == '__main__':
    main()