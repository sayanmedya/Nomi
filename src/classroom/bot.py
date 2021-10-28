import os
import asyncio
import discord
from discord.http import Route
from discord.ext import commands
from dotenv import load_dotenv
import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from requests.api import options

from db import *

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
C_ID = os.getenv('CALENDER_ID')

bot = commands.Bot(command_prefix='^')

start_time_map = {}
task_map = {}
remind_before = 599
notify_channel_id = 807315756709707806
log_channel_id = 867143489334542336

subject = get_subject()

creds = None
SCOPES = ['https://www.googleapis.com/auth/calendar']

if os.path.exists('token.pickle'):
	with open('token.pickle', 'rb') as token:
		creds = pickle.load(token)
if not creds or not creds.valid:
	if creds and creds.expired and creds.refresh_token:
		creds.refresh(Request())
	else:
		flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
		creds = flow.run_local_server(port=0)
	with open('token.pickle', 'wb') as token:
		pickle.dump(creds, token)

service = build('calendar', 'v3', credentials=creds)

	
def pretty_delta_big(delta):
	string = ''
	s = int(delta.total_seconds())
	d = s // (24 * 60 * 60)
	s %= (24 * 60 * 60)
	if d != 0:
		string += str(d) + ' day '
	h = s // 3600
	s %= 3600
	if h != 0:
		string += str(h) + ' hour '
	m = s // 60
	if m != 0 or len(string) == 0:
		string += str(m) + ' min '
	return string[:-1]

def pretty_class_desc(event, now):
	sdt = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	edt = datetime.datetime.strptime(event['end']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	desc = ''

	if edt < now:
		desc += '<:BotGray:865284549730369558> '
	elif now >= sdt:
		desc += '<:BotRed:865284549810061332> '
	else:
		desc += '<:BotYellow:865284549377261599> '
	id = event['summary']
	# desc += '**' + subject[id].get('name', '') + ' (' + id + ')**\n'
	# desc += ' `' + sdt.strftime('%I:%M %p') + ' - ' + edt.strftime('%I:%M %p') + '`   •   '
	# desc += subject[id].get('tcode', '') + '   •   '
	# desc += '[Meet Link](' + subject[id].get('meet', '') + ')   •   '
	# desc += '[Classroom Link](' + subject[id].get('classroom', '') + ')\n'
	
	desc += '**' + id + ' • ' + subject[id].get('name', '')
	if 'tcode' in subject[id]:
		desc += ' (' + subject[id]['tcode'] + ')'
	desc += '**\n `' + sdt.strftime('%I:%M %p') + ' - ' + edt.strftime('%I:%M %p') + '`'
	if 'classroom' in subject[id]:
		desc += ' • [Classroom](' + subject[id]['classroom'] + ')'
	if 'meet' in subject[id]:
		desc += ' • [Meet](' + subject[id]['meet'] + ')'
	if 'attendance' in subject[id]:
		desc += ' • [Attendance](' + subject[id]['attendance'] + ')'
	desc += '\n'
	return desc


def get_events(iststart, istend):
	events_result = service.events().list(calendarId=C_ID,
											timeMin=iststart.isoformat() + 'T00:00:00+05:30',
											timeMax=istend.isoformat() + 'T23:59:59+05:30',
											singleEvents=True,
											orderBy='startTime').execute()
	event_dict = {}
	for event in events_result.get('items', []):
		if event_dict.get(event['start']['dateTime'][0:10], None):
			event_dict[event['start']['dateTime'][0:10]].append(event)
		else:
			event_dict[event['start']['dateTime'][0:10]] = [event]
	return event_dict

def pretty_msg_embed(events, author, event_date, now):
	embedVar = discord.Embed()
	embedVar.set_footer(text=f'Requested by {author.display_name}',icon_url=author.avatar_url)
	if len(events) == 0:
		embedVar.set_author(name = 'Found No Class')
	elif len(events) == 1:
		embedVar.set_author(name = 'Found 1 Class')
	else:
		embedVar.set_author(name = 'Found ' + str(len(events)) + ' Classes')
	embedVar.title = '{0:%A %B %d}'.format(event_date)
	embedVar.description = ''
	for event in events:
		embedVar.description += pretty_class_desc(event, now) + '\n'
	return embedVar


def pretty_event_embed(event):
	start_time = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	end_time = datetime.datetime.strptime(event['end']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	embedVar = discord.Embed(color=0xf7cb0b)
	id = event['summary']
	embedVar.title = subject[id].get('name', '') + ' (' + id + ')'
	embedVar.url = event['htmlLink']
	embedVar.description = subject[id].get('teacher', '')
	embedVar.add_field(name='Time',value=start_time.strftime('%a %b %d, %I:%M %p'),inline=True)
	embedVar.add_field(name='Duration',value=pretty_delta_big(end_time - start_time),inline=True)
	data = {}
	data['embed'] = embedVar.to_dict()
	data['components'] = [
		{
			'type': 1,
			'components': []
		}
	]
	if 'classroom' in subject[id]:
		data['components'][0]['components'].append({
			'type': 2,
			'label': 'Classroom',
			'style': 5,
			'emoji': {
				'name': 'classroom',
				'id': '889612955828752405'
			},
			'url': subject[id]['classroom']
		})
	if 'meet' in subject[id]:
		data['components'][0]['components'].append({
			'type': 2,
			'label': 'Meet',
			'style': 5,
			'emoji': {
				'name': 'meet',
				'id': '889612955568701450'
			},
			'url': subject[id]['meet']
		})
	if 'attendance' in subject[id]:
		btn = {
			'type': 2,
			'label': 'Attendance Form',
			'style': 5,
			'emoji': {
				'name': 'form',
				'id': '867146196439138314'
			},
			'url': subject[id]['attendance']
		}
		if len(data['components'][0]['components']) < 2:
			data['components'][0]['components'].append(btn)
		else:
			data['components'].append({
				'type': 1,
				'components': [btn]
			})

	return data

async def remind_event(event):
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	start_time = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	end_time = datetime.datetime.strptime(event['end']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	if start_time <= now:
		return
	delta = start_time - now
	await asyncio.sleep(max(int(delta.total_seconds()) - remind_before, 0))
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	id = event['summary']
	delay =  (min(int((start_time - now).total_seconds()), remind_before) + 2) // 60
	data = pretty_event_embed(event)
	data['content'] = '<@&' + subject[id].get('role', '') + '> Next class is about to start in ' + str(delay) + ' min'
	res = await bot.http.request(
		Route('POST', f'/channels/{notify_channel_id}/messages'),
		json=data
	)
	
async def refresh_events():
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	start_iso = now.isoformat() + '+05:30'
	end_iso = (now + datetime.timedelta(days=1)).isoformat() + '+05:30'
	while True:
		try:
			events_result = service.events().list(calendarId=C_ID, timeMin=start_iso, timeMax=end_iso, singleEvents=True, orderBy='startTime').execute()
			break
		except:
			await asyncio.sleep(60)
	events = events_result.get('items', [])
	event_set = {}
	for k in start_time_map:
		event_set[k] = False
	for event in events:
		if (event['start']['dateTime'], event['id']) in start_time_map:
			if event != start_time_map[(event['start']['dateTime'], event['id'])]:
				try:
					task_map[(event['start']['dateTime'], event['id'])].cancel()
				except:
					print(event)
				start_time_map[(event['start']['dateTime'], event['id'])] = event
				tsk = asyncio.create_task(remind_event(event))
				task_map[(event['start']['dateTime'], event['id'])] = tsk
			event_set[(event['start']['dateTime'], event['id'])] = True
		else:
			start_time_map[(event['start']['dateTime'], event['id'])] = event
			tsk = asyncio.create_task(remind_event(event))
			task_map[(event['start']['dateTime'], event['id'])] = tsk
	for k in event_set:
		if event_set[k] == False:
			try:
				task_map[k].cancel()
				start_time_map.pop(k, None)
				task_map.pop(k, None)
			except:
				print(k)


async def notification_service():
	while True:
		await refresh_events()
		await asyncio.sleep(300)

@bot.event
async def on_ready():
	print(f'{bot.user} is connected to the following guild:\n')
	for guild in bot.guilds:
		print(f'{guild.name} (id: {guild.id})\n')
	asyncio.create_task(notification_service())
	await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='for ^class'))

async def pager(ctx, pages, menus, i):
	data = {
		'embed': pages[i].to_dict(),
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'select_date',
						'options': menus,
						'placeholder': 'Select date',
						'max_values': 1
					}
				]
			}
		]
	}
	msg = await bot.http.request(
		Route('POST', f'/channels/{ctx.channel.id}/messages'),
		json=data
	)
	data['components'][0]['components'][0]['options'][i]['default'] = False
	

	def check(res):
		if res["t"] != "INTERACTION_CREATE":
			return 0
		if not res['d']['data'].get('component_type', None):
			return 0
		return int(res['d']['member']['user']['id']) == ctx.author.id and res['d']['message']['id'] == msg['id']

	while True:
		try:
			res = await bot.wait_for('socket_response', timeout=120, check=check)
			interaction_id = res['d']['id']
			interaction_token = res['d']['token']
			await bot.http.request(
				Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
				json={'type': 6}
			)
			i = int(res['d']['data']['values'][0])
			data['embed'] = pages[i].to_dict()
			data['components'][0]['components'][0]['options'][i]['default'] = True
			await bot.http.request(
				Route("PATCH", f"/channels/{ctx.channel.id}/messages/{msg['id']}"),
				json=data
			)
			data['components'][0]['components'][0]['options'][i]['default'] = False
		except asyncio.TimeoutError:
			data['components'] = None
			await bot.http.request(
				Route("PATCH", f"/channels/{ctx.channel.id}/messages/{msg['id']}"),
				json=data
			)
			break

@bot.command(name = 'class', help= 'Shows the classes of any date (default: current date)')
async def classfn(ctx):
	utcnow = datetime.datetime.utcnow()
	istnow = utcnow + datetime.timedelta(hours=5,minutes=30)
	iststart = istnow.date()
	w = istnow.date().weekday()
	istend = istnow.date() + datetime.timedelta(days=18-w)
	if w < 5:
		iststart = istnow.date() + datetime.timedelta(days=-w)
	events = get_events(iststart, istend)
	pages = []
	menus = []
	cur = iststart
	start_index = 0
	i = 0
	while cur <= istend:
		event_array = events.get(cur.isoformat(), [])
		menus.append({
			'label': cur.strftime('%A %B %d'),
			'value': str(i),
		})
		if len(event_array) == 0:
			menus[-1]['description'] = 'No class'
		elif len(event_array) == 1:
			menus[-1]['description'] = str(len(event_array)) + ' class'
		else:
			menus[-1]['description'] = str(len(event_array)) + ' classes'
		if cur < istnow.date():
			menus[-1]['emoji'] = {
				'name': 'BotGray',
				'id': '865284549730369558',
			}
		elif cur == istnow.date():
			start_index = len(pages)
			menus[-1]['default'] = True
			menus[-1]['emoji'] = {
				'name': 'BotRed',
				'id': '865284549810061332'
			}
		else:
			menus[-1]['emoji'] = {
				'name': 'BotYellow',
				'id': '865284549377261599'
			}
		pages.append(pretty_msg_embed(event_array, ctx.author, cur, istnow))
		cur = cur + datetime.timedelta(days=1)
		i += 1
	asyncio.create_task(pager(ctx, pages, menus, start_index))


async def choose_sub(ctx, content):
	global subject
	menus = []
	for s in subject:
		menus.append({
			'label': s,
			'value': s,
			'description': subject[s]['name']
		})
	data = {
		'content': content,
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'select_class',
						'options': menus,
						'placeholder': 'Select a class',
						'max_values': 1
					}
				]
			}
		]
	}
	
	msg = await bot.http.request(
		Route('POST', f'/channels/{ctx.channel.id}/messages'),
		json=data
	)
	

	def check(res):
		if res["t"] != "INTERACTION_CREATE":
			return 0
		if not res['d']['data'].get('component_type', None):
			return 0
		return int(res['d']['member']['user']['id']) == ctx.author.id and res['d']['message']['id'] == msg['id']
	
	try:
		res = await bot.wait_for('socket_response', timeout=120, check=check)
		interaction_id = res['d']['id']
		interaction_token = res['d']['token']
		await bot.http.request(
			Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
			json={'type': 6}
		)
		return res['d']['data']['values'][0]

	except asyncio.TimeoutError:
		await ctx.send('⏳ Timed out. Please start again.')
		return None
	

async def choose_date(ctx, old_date):
	cur_date = datetime.date.today()
	years = []
	months = []
	day1 = []
	day2 = []
	year = None
	month = None
	d1 = None
	d2 = None

	for i in range(0, 5):
		years.append({
			'label': str(cur_date.year + i),
			'value': str(cur_date.year + i)
		})
	if not old_date:
		years[0]['default'] = True
		year = cur_date.year
	else:
		years[old_date.year - cur_date.year]['default'] = True
		year = old_date.year

	for i in range(1, 13):
		months.append({
			'label': cur_date.replace(month=i).strftime('%B'),
			'value': str(i),
			'description': str(i)
		})
	if not old_date:
		months[cur_date.month - 1]['default'] = True
		month = cur_date.month
	else:
		months[old_date.month - 1]['default'] = True
		month = old_date.month


	for i in range(0, 4):
		day1.append({
			'label': str(i),
			'value': str(i),
		})
	if old_date:
		d1 = old_date.day // 10
		day1[d1]['default'] = True

	for i in range(0, 10):
		day2.append({
			'label': str(i),
			'value': str(i),
		})
	if old_date:
		d2 = old_date.day % 10
		day2[d2]['default'] = True

	data = {
		'content': 'Choose the start date of the event',
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'year',
						'options': years,
						'placeholder': 'Choose Year',
						'max_values': 1
					}
				]
			},
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'month',
						'options': months,
						'placeholder': 'Choose Month',
						'max_values': 1
					}
				]
			},
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'day1',
						'options': day1,
						'placeholder': 'Choose Day (First Digit)',
						'max_values': 1
					}
				]
			},
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'day2',
						'options': day2,
						'placeholder': 'Choose Day (Second Digit)',
						'max_values': 1
					}
				]
			},
			{
				'type': 1,
				'components': [
					{
						'type': 2,
						'label': 'Enter',
						'style': 3,
						'custom_id': 'enter'
					},
					{
						'type': 2,
						'label': 'Cancel',
						'style': 4,
						'custom_id': 'cancel'
					},
				]
			}
		]
	}
	msg = await bot.http.request(
		Route('POST', f'/channels/{ctx.channel.id}/messages'),
		json=data
	)

	def check(res):
		if res["t"] != "INTERACTION_CREATE":
			return 0
		if not res['d']['data'].get('component_type', None):
			return 0
		return int(res['d']['member']['user']['id']) == ctx.author.id and res['d']['message']['id'] == msg['id']

	while True:
		try:
			res = await bot.wait_for('socket_response', timeout=120, check=check)
			interaction_id = res['d']['id']
			interaction_token = res['d']['token']
			if res['d']['data']['component_type'] == 3:
				await bot.http.request(
					Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
					json={'type': 6}
				)
			opt = res['d']['data']['custom_id']
			if opt == 'enter':
				try:
					event_date = datetime.date(year, month, d1 * 10 + d2)
					await bot.http.request(
						Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
						json={'type': 6}
					)
					return event_date
				except:
					continue
			elif opt == 'cancel':
				await bot.http.request(
					Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
					json={'type': 4,'data':{'content': '✅ Cancelled'}}
				)
				return None
			else:
				val = int(res['d']['data']['values'][0])
				if opt == 'year':
					year=val
				elif opt == 'month':
					month=val
				elif opt == 'day1':
					d1=val
				else:
					d2=val
		except asyncio.TimeoutError:
			await ctx.send('⏳ Timed out. Please start again.')
			return None
		

async def choose_time(ctx, old_date):
	hours = []
	mins = []
	ampms =[
		{
			'label': 'AM',
			'value': '0'
		},
		{
			'label': 'PM',
			'value': '1'
		}
	]
	for i in range(1, 12):
		hours.append({
			'label': str(i),
			'value': str(i)
		})
	hours.append({
		'label': '12',
		'value': '0'
	})
	for i in range(0, 12):
		mins.append({
			'label': str(i * 5),
			'value': str(i)
		})
	hour = None
	min = None
	ampm = None

	if old_date:
		hour = old_date.hour % 12
		min = old_date.minute // 5
		ampm = old_date.hour // 12
		ampms[ampm]['default'] = True
		mins[min]['default'] = True
		if hour == 0:
			hours[11]['default'] = True
		else:
			hours[hour - 1]['default'] = True

	data = {
		'content': 'Choose the start time of the event',
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'hour',
						'options': hours,
						'placeholder': 'Choose Hour',
						'max_values': 1
					}
				]
			},
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'min',
						'options': mins,
						'placeholder': 'Choose Minute',
						'max_values': 1
					}
				]
			},
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'ampm',
						'options': ampms,
						'placeholder': 'AM / PM',
						'max_values': 1
					}
				]
			},
			{
				'type': 1,
				'components': [
					{
						'type': 2,
						'label': 'Enter',
						'style': 3,
						'custom_id': 'enter'
					},
					{
						'type': 2,
						'label': 'Cancel',
						'style': 4,
						'custom_id': 'cancel'
					},
				]
			}
		]
	}
	msg = await bot.http.request(
		Route('POST', f'/channels/{ctx.channel.id}/messages'),
		json=data
	)

	def check(res):
		if res["t"] != "INTERACTION_CREATE":
			return 0
		if not res['d']['data'].get('component_type', None):
			return 0
		return int(res['d']['member']['user']['id']) == ctx.author.id and res['d']['message']['id'] == msg['id']

	while True:
		try:
			res = await bot.wait_for('socket_response', timeout=120, check=check)
			interaction_id = res['d']['id']
			interaction_token = res['d']['token']
			if res['d']['data']['component_type'] == 3:
				await bot.http.request(
					Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
					json={'type': 6}
				)
			opt = res['d']['data']['custom_id']
			if opt == 'enter':
				try:
					event_time = datetime.time(hour + 12 * ampm, min * 5, 0)
					await bot.http.request(
						Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
						json={'type': 6}
					)
					return event_time
				except:
					continue
			elif opt == 'cancel':
				await bot.http.request(
					Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
					json={'type': 4,'data':{'content': '✅ Cancelled'}}
				)
				return None
			else:
				val = int(res['d']['data']['values'][0])
				if opt == 'hour':
					hour=val
				elif opt == 'min':
					min=val
					if min == 12:
						min = 0
				else:
					ampm=val
		except asyncio.TimeoutError:
			await ctx.send('⏳ Timed out. Please start again.')
			return None


async def choose_duration(ctx, txt, old_dur):
	duration = None
	durations = [
		{
			'label': 1,
			'description': '50 min',
			'value': '50'
		},
		{
			'label': 2,
			'description': '1 hour 50 min',
			'value': '110'
		},
		{
			'label': 3,
			'description': '2 hour 50 min',
			'value': '170'
		},
	]
	if old_dur:
		duration = (old_dur - 1) * 60 + 50
		durations[old_dur - 1]['default'] = True
	data = {
		'content': 'Choose the duration of the event',
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'duration',
						'options': durations,
						'placeholder': 'Choose no. of periods',
						'max_values': 1
					}
				]
			},
			{
				'type': 1,
				'components': [
					{
						'type': 2,
						'label': txt,
						'style': 3,
						'custom_id': 'enter'
					},
					{
						'type': 2,
						'label': 'Cancel',
						'style': 4,
						'custom_id': 'cancel'
					},
				]
			}
		]
	}
	msg = await bot.http.request(
		Route('POST', f'/channels/{ctx.channel.id}/messages'),
		json=data
	)

	def check(res):
		if res["t"] != "INTERACTION_CREATE":
			return 0
		if not res['d']['data'].get('component_type', None):
			return 0
		return int(res['d']['member']['user']['id']) == ctx.author.id and res['d']['message']['id'] == msg['id']

	while True:
		try:
			res = await bot.wait_for('socket_response', timeout=120, check=check)
			interaction_id = res['d']['id']
			interaction_token = res['d']['token']
			if res['d']['data']['component_type'] == 3:
				await bot.http.request(
					Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
					json={'type': 6}
				)
			opt = res['d']['data']['custom_id']
			if opt == 'enter':
				if duration:
					await bot.http.request(
						Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
						json={'type': 6}
					)
					return duration
				else:
					continue
			elif opt == 'cancel':
				await bot.http.request(
					Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
					json={'type': 4,'data':{'content': '✅ Cancelled'}}
				)
				return None
			else:
				duration = int(res['d']['data']['values'][0])
		except asyncio.TimeoutError:
			await ctx.send('⏳ Timed out. Please start again.')
			return None


async def choose_event(ctx, sub_id, content, btn_txt):
	utcnow = datetime.datetime.utcnow()
	istnow = utcnow + datetime.timedelta(hours=5,minutes=30)
	iststart = istnow.date()

	events_result = service.events().list(
		calendarId=C_ID,
		timeMin=iststart.isoformat() + 'T00:00:00+05:30',
		singleEvents=True,
		maxResults=25,
		orderBy='startTime',
		q=sub_id
	).execute()

	events = events_result.get('items', [])
	menus = []
	for event in events:
		sdt = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
		edt = datetime.datetime.strptime(event['end']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
		menus.append({
			'label': sdt.strftime('%A, %B %d'),
			'value': event['id'],
			'description': sdt.strftime('%I:%M %p') + ' (' + pretty_delta_big(edt - sdt) + ')'
		})
		if sdt > istnow:
			menus[-1]['emoji'] = {
				'name': 'BotYellow',
				'id': '865284549377261599'
			}
		elif edt > istnow:
			menus[-1]['emoji'] = {
				'name': 'BotRed',
				'id': '865284549810061332'
			}
		else:
			menus[-1]['emoji'] = {
				'name': 'BotGray',
				'id': '865284549730369558',
			}

	data = {
		'content': content,
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'select_event',
						'options': menus,
						'placeholder': 'Select an event',
						'max_values': 1
					}
				]
			},
			{
				'type': 1,
				'components': [
					{
						'type': 2,
						'label': btn_txt,
						'style': 3,
						'custom_id': 'enter'
					},
					{
						'type': 2,
						'label': 'Cancel',
						'style': 4,
						'custom_id': 'cancel'
					},
				]
			}
		]
	}
	
	msg = await bot.http.request(
		Route('POST', f'/channels/{ctx.channel.id}/messages'),
		json=data
	)
	

	def check(res):
		if res["t"] != "INTERACTION_CREATE":
			return 0
		if not res['d']['data'].get('component_type', None):
			return 0
		return int(res['d']['member']['user']['id']) == ctx.author.id and res['d']['message']['id'] == msg['id']

	event_id = None
	while True:
		try:
			res = await bot.wait_for('socket_response', timeout=120, check=check)
			interaction_id = res['d']['id']
			interaction_token = res['d']['token']
			if res['d']['data']['component_type'] == 3:
				await bot.http.request(
					Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
					json={'type': 6}
				)
			opt = res['d']['data']['custom_id']
			if opt == 'enter':
				if not event_id:
					continue
				await bot.http.request(
					Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
					json={'type': 6}
				)
				break
			elif opt == 'cancel':
				await bot.http.request(
					Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
					json={'type': 4,'data':{'content': '✅ Cancelled'}}
				)
				return None
			else:
				event_id = res['d']['data']['values'][0]

		except asyncio.TimeoutError:
			await ctx.send('⏳ Timed out. Please start again.')
			return None
	for event in events:
		if event['id'] == event_id:
			return event
	return None

@bot.command(help= 'Configure class details')
@commands.has_any_role(807213412433657887, 807213412425662534, 854452988457910322)
async def config(ctx):
	sub_id = await choose_sub(ctx, 'Choose which class to edit')
	if not sub_id:
		return
	
	data = {
		'content': 'Choose which field to update.\n```json\n{\n',
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 3,
						'custom_id': 'select_opt',
						'options': [
							{
								'label': 'name',
								'value': 'name',
								'description': 'Change the name of the class'
							},
							{
								'label': 'role',
								'value': 'role',
								'description': 'Update the role id to mention'
							},
							{
								'label': 'teacher',
								'value': 'teacher',
								'description': 'Update the full name of the instructor'
							},
							{
								'label': 'tcode',
								'value': 'tcode',
								'description': 'Update the instructor code'
							},
							{
								'label': 'meet',
								'value': 'meet',
								'description': 'Update the google meet link'
							},
							{
								'label': 'classroom',
								'value': 'classroom',
								'description': 'Update the google classroom link'
							},
							{
								'label': 'attendance',
								'value': 'attendance',
								'description': 'Update the attendance link'
							},
						],
						'placeholder': 'Select a option',
						'max_values': 1
					}
				]
			}
		]
	}
	
	global subject
	for f in subject[sub_id]:
		data['content'] += f'\t\"{f}\": \"{subject[sub_id][f]}\"\n'
	data['content'] += '}\n```'
	msg = await bot.http.request(
		Route('POST', f'/channels/{ctx.channel.id}/messages'),
		json=data
	)

	def check(res):
		if res["t"] != "INTERACTION_CREATE":
			return 0
		if not res['d']['data'].get('component_type', None):
			return 0
		return int(res['d']['member']['user']['id']) == ctx.author.id and res['d']['message']['id'] == msg['id']
	
	try:
		res = await bot.wait_for('socket_response', timeout=120, check=check)
		interaction_id = res['d']['id']
		interaction_token = res['d']['token']
		await bot.http.request(
			Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
			json={'type': 6}
		)
		field = res['d']['data']['values'][0]

	except asyncio.TimeoutError:
		data['components'] = None
		await bot.http.request(
			Route("PATCH", f"/channels/{ctx.channel.id}/messages/{msg['id']}"),
			json=data
		)
		await ctx.send('⏳ Timed out. Please try again.')
		return
	await ctx.send(f"Type the new `{field}`. Type `cancel` to cancel")
	
	def check_res(msg):
		return msg.channel == ctx.channel and msg.author == ctx.author

	try:
		msg = await bot.wait_for('message', timeout=120, check=check_res)
		if msg.content == 'cancel':
			await ctx.send(f'✅ Cancelled.')
			return
		try:
			old_val = subject[sub_id].get(field, '-')
			subject = set_subject(sub_id, field, msg.content)
		except:
			await ctx.send('❌ Update failed. Please try again later.')
			return
		await ctx.send(f'✅ Update successful. `{field}` set to `{msg.content}`.')
		log_channel = discord.utils.get(ctx.guild.text_channels, id=log_channel_id)
		res = f'Config updated by {ctx.author.mention} in {ctx.channel.mention}.\n'
		embedVar = discord.Embed(color=0x00a9ff)
		embedVar.title = sub_id
		embedVar.description = field
		embedVar.add_field(name='Old Value',value= old_val,inline=True)
		embedVar.add_field(name='New Value',value= msg.content,inline=True)
		await log_channel.send(res, embed=embedVar)
	except asyncio.TimeoutError:
		await ctx.send('⏳ Timed out. Please try again.')

@bot.command(help= 'Create a new event')
@commands.has_any_role(807213412433657887, 807213412425662534, 854452988457910322)
async def create(ctx):
	sub_id = await choose_sub(ctx, 'Choose which class to create')
	if not sub_id:
		return
	
	event_date = await choose_date(ctx, None)
	if not event_date:
		return
	
	event_time = await choose_time(ctx, None)
	if not event_time:
		return
	
	duration = await choose_duration(ctx, 'Create', None)
	if not duration:
		return

	event_start = datetime.datetime.combine(event_date, event_time)
	event_end = event_start + datetime.timedelta(minutes=duration)

	new_event = {
		'summary': sub_id,
		'start': {
			'dateTime': event_start.isoformat() + '+05:30',
			'timeZone': 'Asia/Kolkata'
		},
		'end': {
			'dateTime': event_end.isoformat() + '+05:30',
			'timeZone': 'Asia/Kolkata'
		}
	}
	try:
		event = service.events().insert(calendarId=C_ID, body=new_event).execute()
		start_time = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
		end_time = datetime.datetime.strptime(event['end']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
		embedVar = discord.Embed(color=0x24f30f)
		id = event['summary']
		embedVar.title = subject[id].get('name', '') + ' (' + id + ')'
		embedVar.description = subject[id].get('teacher', '')
		embedVar.add_field(name='Time',value=start_time.strftime('%a %b %d, %I:%M %p'), inline=True)
		embedVar.add_field(name='Duration',value=pretty_delta_big(end_time - start_time),inline=True)
		await ctx.send('✅ Event created successfully.', embed=embedVar)
		log_channel = discord.utils.get(ctx.guild.text_channels, id=log_channel_id)
		await log_channel.send(f'Event created by {ctx.author.mention} in {ctx.channel.mention}', embed=embedVar)
		await refresh_events()
	except:
	 	await ctx.send('❌ Failed. Try again')


@bot.command(help= 'Update an existing event')
@commands.has_any_role(807213412433657887, 807213412425662534, 854452988457910322)
async def update(ctx):
	sub_id = await choose_sub(ctx, 'Choose which class to edit')
	if not sub_id:
		return
	
	old_event = await choose_event(ctx, sub_id, 'Choose which event to update', 'Enter')
	if not old_event:
		return

	old_start = datetime.datetime.strptime(old_event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	old_end = datetime.datetime.strptime(old_event['end']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')

	event_date = await choose_date(ctx, old_start)
	if not event_date:
		return
	
	event_time = await choose_time(ctx, old_start)
	if not event_time:
		return
	

	old_duration = (int((old_end - old_start).total_seconds()) // 60 + 10) // 60
	duration = await choose_duration(ctx, 'Update', old_duration)
	if not duration:
		return

	event_start = datetime.datetime.combine(event_date, event_time)
	event_end = event_start + datetime.timedelta(minutes=duration)

	changes = {
		'start': {
			'dateTime': event_start.isoformat() + '+05:30',
			'timeZone': 'Asia/Kolkata'
		},
		'end': {
			'dateTime': event_end.isoformat() + '+05:30',
			'timeZone': 'Asia/Kolkata'
		}
	}
	try:
		event = service.events().patch(calendarId=C_ID, eventId=old_event['id'], body=changes).execute()
		start_time = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
		end_time = datetime.datetime.strptime(event['end']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
		embedVar = discord.Embed(color=0xe5ff1f)
		id = event['summary']
		embedVar.title = subject[id].get('name', '') + ' (' + id + ')'
		embedVar.description = subject[id].get('teacher', '')
		time_val = '~~' + old_start.strftime('%a %b %d, %I:%M %p') + '~~\n' + start_time.strftime('%a %b %d, %I:%M %p')
		duration_val = '~~' + pretty_delta_big(old_end - old_start) + '~~\n' + pretty_delta_big(end_time - start_time)
		embedVar.add_field(name='Time',value=time_val, inline=True)
		embedVar.add_field(name='Duration',value=duration_val,inline=True)
		await ctx.send('✅ Event updated successfully', embed=embedVar)
		log_channel = discord.utils.get(ctx.guild.text_channels, id=log_channel_id)
		await log_channel.send(f'Event updated by {ctx.author.mention} in {ctx.channel.mention}', embed=embedVar)
		await refresh_events()
	except:
	 	await ctx.send('❌ Failed. Try again')


@bot.command(help= 'Delete an event')
@commands.has_any_role(807213412433657887, 807213412425662534, 854452988457910322)
async def delete(ctx):
	sub_id = await choose_sub(ctx, 'Choose which class to delete')
	if not sub_id:
		return
	
	event = await choose_event(ctx, sub_id, 'Choose which event to delete', 'Delete')
	if not event:
		return
	
	try:
		service.events().delete(calendarId=C_ID, eventId=event['id']).execute()
		start_time = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
		end_time = datetime.datetime.strptime(event['end']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
		embedVar = discord.Embed(color=0xff0000)
		id = event['summary']
		embedVar.title = subject[id].get('name', '') + ' (' + id + ')'
		embedVar.description = subject[id].get('teacher', '')
		embedVar.add_field(name='Time',value=start_time.strftime('%a %b %d, %I:%M %p'), inline=True)
		embedVar.add_field(name='Duration',value=pretty_delta_big(end_time - start_time),inline=True)
		await ctx.send('✅ Event deleted successfully.', embed=embedVar)
		log_channel = discord.utils.get(ctx.guild.text_channels, id=log_channel_id)
		await log_channel.send(f'Event deleted by {ctx.author.mention} in {ctx.channel.mention}', embed=embedVar)
		await refresh_events()
	except:
		await ctx.send('❌ Failed. Try again')
	
bot.run(TOKEN)
