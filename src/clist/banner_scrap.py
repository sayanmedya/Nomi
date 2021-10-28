from bs4 import BeautifulSoup
import asyncio
import requests
import re

# sample_cc_contest_url = 'https://www.codechef.com/api/contests/LTIME96'

# sample_he_contest_url = 'https://www.hackerearth.com/challenges/competitive/hackerearth-june-easy-21/'

async def get_banner_codechef(url):
	api_url = 'https://www.codechef.com/api/contests/' + url.split('/')[-1]
	loop = asyncio.get_event_loop()
	future = loop.run_in_executor(None, requests.get, api_url)
	res = await future
	if res.json()['banner'][0] == '/':
		return 'https://codechef.com' + res.json()['banner']
	else:
		return res.json()['banner']

async def get_banner_hackerearth(url):
	loop = asyncio.get_event_loop()
	future = loop.run_in_executor(None, requests.get, url)
	res = await future
	soup = BeautifulSoup(res.content , features='lxml')
	banner = soup.find(class_='banner-image')['style']
	x = re.search(r'url\(.*\'\);', banner)
	return x.group()[5:-3]