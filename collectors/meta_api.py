import requests
import os
from .base import BaseCollector

class MetaAPICollector(BaseCollector):
    def __init__(self, access_token=None):
        self.access_token = access_token or os.getenv("META_ACCESS_TOKEN")
        self.base_url = "https://graph.facebook.com/v17.0/ads_archive"

    async def collect(self, search_terms: str, ad_type='ALL', ad_reached_countries=['NP']):
        if not self.access_token:
            print("Meta Access Token not provided.")
            return []

        params = {
            'access_token': self.access_token,
            'search_terms': search_terms,
            'ad_type': ad_type,
            'ad_reached_countries': str(ad_reached_countries),
            'fields': 'id,ad_creation_time,ad_creative_bodies,ad_creative_link_captions,ad_creative_link_descriptions,ad_creative_link_titles,ad_delivery_start_time,ad_delivery_stop_time,delivery_by_region,demographic_distribution,impressions,publisher_platforms,spend'
        }

        response = requests.get(self.base_url, params=params)
        if response.status_code == 200:
            return response.json().get('data', [])
        else:
            print(f"Error from Meta API: {response.text}")
            return []

    def save(self, data):
        # Implementation for saving to DB will go here
        pass
