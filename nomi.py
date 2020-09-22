# imon.py
import os
import asyncio
import random
import discord
from discord.ext import commands
from discord import User
from dotenv import load_dotenv
import cv2
import requests
import numpy as np

import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
C_ID = os.getenv('CALENDER_ID')

EMBED_COLOR = 0x9B59B6
NO_EVENT_MESSAGE = 'No Class Found'

bot = commands.Bot(command_prefix='^')

weekday_list=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
week_day_lower = {
	'sunday':0,'sun':0,'monday':1,'mon':1,'tuesday':2,'tue':2,'wednesday':3,'wed':3,'thursday':4,'thu':4,'friday':5,'fri':5,'saturday':6,'sat':6
}

notification_channel = None
remind_before = 599


SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

creds = None

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

start_time_map = {}


def RepresentsInt(s):
	try: 
		int(s)
		return True
	except ValueError:
		return False

def pretty_date(dt):
	return (str(dt.day) if dt.day > 9 else '0' + str(dt.day)) + '-' + (str(dt.month) if dt.month > 9 else '0' + str(dt.month)) + '-' + str(dt.year)
	
def pretty_time(dt):
	h = 12
	if dt.hour > 12:
		h = dt.hour - 12
	elif dt.hour > 0:
		h = dt.hour
	ampm = 'am'
	if dt.hour >= 12:
		ampm = 'pm'
	return (str(h) if h > 9 else '0' + str(h)) + ':' + (str(dt.minute) if dt.minute > 9 else '0' + str(dt.minute)) + ampm

def pretty_delta(delta):
	string = ''
	s = int(delta.total_seconds())
	d = s // (24 * 60 * 60)
	s %= (24 * 60 * 60)
	if d != 0:
		string += str(d) + 'd '
	h = s // 3600
	s %= 3600
	if h != 0:
		string += str(h) + 'h '
	m = s // 60
	if m != 0 or len(string) == 0:
		string += str(m) + 'm '
	return string[:-1]

def pretty_class_desc(event, now):
	sdt = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	edt = datetime.datetime.strptime(event['end']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	desc = ''

	if edt < now:
		desc += '`🟢 '
	elif now >= sdt:
		desc += '`🔴 '
	else:
		desc += '`🟡 '

	desc += pretty_time(sdt) + ' - ' + pretty_time(edt) + ' | ' + event['summary'] + ' | `[`GMeet🔗`](' + event['location'] + ')\n\n'
	return desc
	
def pretty_date_heading(dt, now):
	return '**' + weekday_list[dt.weekday()] + '**  |  ' + pretty_date(dt) + (' | 👈 Today' if dt.date() == now.date() else '') + '\n'

def pretty_events_desc(events, now):
	if len(events) == 0:
		return ''
	min_date = datetime.datetime.strptime(events[0]['start']['dateTime'][0:10], '%Y-%m-%d')
	max_date = datetime.datetime.strptime(events[-1]['start']['dateTime'][0:10], '%Y-%m-%d')
	cur_date = min_date
	desc=''
	while cur_date <= max_date:
		desc += pretty_date_heading(cur_date, now)
		for event in events:
			start_date = datetime.datetime.strptime(event['start']['dateTime'][0:10], '%Y-%m-%d')
			if start_date != cur_date:
				continue
			desc += pretty_class_desc(event, now)
		desc += '\n'
		cur_date += datetime.timedelta(days=1)
	return desc
	
def get_events(kwargs):
	now=kwargs.get('now', None)
	query_arg = {}
	if 'start' in kwargs and kwargs['start'] != None:
		if 'start_now' in kwargs:
			query_arg['timeMin'] = kwargs['start'].isoformat() + '+05:30'
		else:
			query_arg['timeMin'] = kwargs['start'].isoformat()[0:11] + '00:00:00+05:30'
	if 'end' in kwargs and kwargs['end'] != None:
		if 'end_now' in kwargs:
			query_arg['timeMax'] = kwargs['end'].isoformat() + '+05:30'
		else:
			query_arg['timeMax'] = kwargs['end'].isoformat()[0:11] + '23:59:59+05:30'
	if 'cnt' in kwargs:
		query_arg['maxResults'] = kwargs['cnt']
		if 'strict_upper' in kwargs:
			query_arg['maxResults'] += 1
	if 'q' in kwargs:
		query_arg['q'] = kwargs['q']
	events_result = service.events().list(calendarId=C_ID,
											timeMin=query_arg.get('timeMin', None),
											timeMax=query_arg.get('timeMax', None),
											maxResults=query_arg.get('maxResults', None),
											q=query_arg.get('q', None),
											singleEvents=True, orderBy='startTime').execute()
	events = events_result.get('items', [])
	if 'cnt' in kwargs and 'strict_upper' in kwargs and len(events) > 0:
		if events[0]['start']['dateTime'] <= now.isoformat():
			events = events[1:]
		else:
			events = events[:-1]
	return events

def pretty_msg_embed(**kwargs):
	events = get_events(kwargs)
	now=kwargs.get('now', None)
	author=kwargs.get('author', None)
	embedVar = discord.Embed(color=EMBED_COLOR)
	if len(events) == 0:
		embedVar.title = 'Found No Class'
	elif len(events) == 1:
		embedVar.title = 'Found 1 Class'
	else:
		embedVar.title = 'Found ' + str(len(events)) + ' Classes'
	embedVar.description = pretty_events_desc(events, now)
	embedVar.set_footer(text='🟢 (Past)  |  🔴 (Live)  |  🟡 (Upcoming)\n' + f'Requested by {author} • ' + pretty_time(now),icon_url=author.avatar_url)
	return embedVar

async def status_task():
	while True:
		await bot.change_presence(activity=discord.Game(name='3rd year class routine'))
		await asyncio.sleep(10)
		await bot.change_presence(activity=discord.Game(name='type ^help for help'))
		await asyncio.sleep(15)
		
		now = datetime.datetime.utcnow() + datetime.timedelta(hours=5,minutes=30)
		now_iso = now.isoformat() + '+05:30'
		try:
			events_result = service.events().list(calendarId=C_ID, timeMin=now_iso, maxResults=1, singleEvents=True, orderBy='startTime').execute()
			events = events_result.get('items', [])
		except:
			continue

		if len(events) == 0:
			await bot.change_presence(activity=discord.Game(name=NO_EVENT_MESSAGE))
			await asyncio.sleep(35)
			continue

		class_name = events[0]['summary'][0:6]
		sdt_iso = events[0]['start']['dateTime']
		sdt = datetime.datetime.strptime(sdt_iso[0:19], '%Y-%m-%dT%H:%M:%S')
		edt_iso = events[0]['end']['dateTime']
		edt = datetime.datetime.strptime(edt_iso[0:19], '%Y-%m-%dT%H:%M:%S')
		
		if sdt_iso <= now_iso:
			if (now - sdt).total_seconds() < 300:
				await bot.change_presence(activity=discord.Game(name=class_name+' has just started'))
			elif (now - sdt).total_seconds() < (edt - now).total_seconds():
				await bot.change_presence(activity=discord.Game(name=class_name+' started '+pretty_delta(now-sdt)+' ago'))
			else:
				await bot.change_presence(activity=discord.Game(name=class_name+' ends in '+pretty_delta(edt-now)))
		else:
			await bot.change_presence(activity=discord.Game(name=class_name+' starts in '+pretty_delta(sdt-now)))
		await asyncio.sleep(35)

async def remind_event(event, notify_channel, subscriber):
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	start_time = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	if start_time <= now:
		return
	delta = start_time - now
	await asyncio.sleep(max(int(delta.total_seconds()) - remind_before, 0))
	if (event['start']['dateTime'], event['id']) in start_time_map:
		now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
		embedVar = discord.Embed(color=0xf7cb0b)
		embedVar.description = pretty_class_desc(event, now)
		delay =  (min(int((start_time - now).total_seconds()), remind_before) + 30) // 60
		embedVar.title = '📢 Next class is about to start in ' + str(delay) + ' min'
		await notify_channel.send(f'{subscriber.mention}',embed=embedVar)
	
async def refresh_events(notify_channel, subscriber):
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
	for event in events:
		if event['start']['dateTime'] <= start_iso:
			continue
		if (event['start']['dateTime'], event['id']) in start_time_map:
			if event != start_time_map[(event['start']['dateTime'], event['id'])]:
				start_time_map[(event['start']['dateTime'], event['id'])] = event
				asyncio.create_task(remind_event(event, notify_channel, subscriber))
		else:
			start_time_map[(event['start']['dateTime'], event['id'])] = event
			asyncio.create_task(remind_event(event, notify_channel, subscriber))

async def notifiaction_service(notify_channel, subscriber):
	while True:
		await refresh_events(notify_channel, subscriber)
		await asyncio.sleep(300)
	

@bot.event
async def on_ready():
	for guild in bot.guilds:
		if guild.name == GUILD:
			break
	subscriber = discord.utils.get(guild.roles, id=755692949052063764)
	notify_channel = discord.utils.get(guild.text_channels, name="class-notification")
	print(
		f'{bot.user} is connected to the following guild:\n'
		f'{guild.name}(id: {guild.id})\n'
	)
	asyncio.create_task(status_task())
	asyncio.create_task(notifiaction_service(notify_channel, subscriber))

@bot.command(name='hello', help='Say hello')
async def stts(ctx):
	embedVar = discord.Embed(title="Hello World", description=f'hi {ctx.author.mention}', color=EMBED_COLOR)
	await ctx.send(embed=embedVar)

@bot.command(name='avatar', help='Shows the avatar of the mentioned user')
async def avtr(ctx, vctm: User):
	await ctx.send(str(vctm.avatar_url))

@bot.command(name='slap', help='Slaps the mentioned user')
async def slp(ctx, vctm: User):
	req = requests.get(str(vctm.avatar_url_as(format='jpg',size=256)), stream=True).raw
	arr = np.asarray(bytearray(req.read()), dtype="uint8")
	top = cv2.imdecode(arr, cv2.IMREAD_COLOR)
	btm = cv2.imread('e.jpg')
	btm[240:240+top.shape[0], 520:520+top.shape[1]] = top
	cv2.imwrite("a.jpg", btm)
	await ctx.message.channel.send(file=discord.File('a.jpg'))

@bot.command(name='words', help='Choose 1 - 200 random words for skribble. Pass the number of words as argument')
async def rndwrd(ctx, cnt : int):
	wordfile = open('words.txt', 'r')
	wordlist = wordfile.read().split(', ')
	if cnt > 200 or cnt < 1:
		await ctx.send("The number is invalid or too big")
	else:
		taken = set([])
		response = '```\n'
		for i in range(0, cnt):
			while True:
				guess=random.randint(0, len(wordlist) - 1)
				if guess not in taken:
					taken.add(guess)
					response += wordlist[guess].lower()
					if i != cnt - 1:
						response += ', '
					break
		response += '```'
		await ctx.send(response)

@bot.command(name='math', help='Solve simple mathematical expression')
async def slv(ctx, *, arg):
	try:
		await ctx.send("```" + str(eval(arg)) + "```")
	except:
		await ctx.send("Ooops! wrong expression")

@bot.command(name='class', help='Shows the class routine')
async def clss(ctx, *, arg):
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	arg_list = arg.split('+')[0].split()
	tag = None
	if len(arg.split('+')) > 1:
		tag = arg.split('+')[1]
	if arg_list[0] == 'now':
		await ctx.send(embed=pretty_msg_embed(now=now, start=now,start_now=True,end=now+datetime.timedelta(seconds=1),end_now=True,q=tag,author=ctx.author))
	elif arg_list[0] == 'next':
		if len(arg_list) == 1 or RepresentsInt(arg_list[1]):
			c = 1
			if len(arg_list) > 1:
				c = int(arg_list[1])
			await ctx.send(embed=pretty_msg_embed(now=now, start=now,start_now=True, strict_upper=True,cnt=c,q=tag,author=ctx.author))
		elif arg_list[1] == 'day':
			await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=1),end=now+datetime.timedelta(days=1),q=tag))
		elif arg_list[1] == 'week':
			week_day=(now.weekday()+1) % 7
			await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=7-week_day),end=now+datetime.timedelta(days=14-week_day),q=tag))
		elif arg_list[1] in week_day_lower.keys():
			dlt = 7 + week_day_lower[arg_list[1]] - (now.weekday()+1) % 7
			await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=dlt),end=now+datetime.timedelta(days=dlt),q=tag))
	elif arg_list[0] == 'last':
		if arg_list[1] == 'day':
			await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=-1),end=now+datetime.timedelta(days=-1),q=tag))
		elif arg_list[1] == 'week':
			week_day=(now.weekday()+1) % 7
			await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=-7-week_day),end=now+datetime.timedelta(days=-week_day),q=tag))
		elif arg_list[1] in week_day_lower.keys():
			dlt = -7 + week_day_lower[arg_list[1]] - (now.weekday()+1) % 7
			await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=dlt),end=now+datetime.timedelta(days=dlt),q=tag))
	elif arg_list[0] == 'this':
		if len(arg_list) == 1:
			await ctx.send(embed=pretty_msg_embed(now=now, start=now,start_now=True,end=now+datetime.timedelta(seconds=1),end_now=True,q=tag,author=ctx.author))
		elif arg_list[1] == 'day':
			await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now,end=now,q=tag))
		elif arg_list[1] == 'week':
			week_day=(now.weekday()+1) % 7
			await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=-week_day),end=now+datetime.timedelta(days=7-week_day),q=tag))
		elif arg_list[1] in week_day_lower.keys():
			dlt = week_day_lower[arg_list[1]] - (now.weekday()+1) % 7
			await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=dlt),end=now+datetime.timedelta(days=dlt),q=tag))
	elif arg_list[0] == 'today':
		await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now,end=now,q=tag))
	elif arg_list[0] == 'tomorrow':
		await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=1),end=now+datetime.timedelta(days=1),q=tag))
	elif arg_list[0] == 'yesterday':
		await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=-1),end=now+datetime.timedelta(days=-1),q=tag))
	elif arg_list[0] in week_day_lower.keys():
		dlt = week_day_lower[arg_list[0]] - (now.weekday()+1) % 7
		await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=dlt),end=now+datetime.timedelta(days=dlt),q=tag))
	elif arg_list[0] == 'week':
		week_day=(now.weekday()+1) % 7
		await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=-week_day),end=now+datetime.timedelta(days=7-week_day),q=tag))
	elif arg_list[0][0:2] == 'd[' and arg_list[0][-1] == ']':
		dt = arg_list[0][2:-1].split(':')
		if len(dt) == 1:
			if dt[0] == '':
				await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now,end=now,q=tag))
			elif RepresentsInt(dt[0]):
				dlt = int(dt[0])
				await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=now+datetime.timedelta(days=dlt),end=now+datetime.timedelta(days=dlt),q=tag))
			else:
				req_date = datetime.datetime.strptime(dt[0], '%d-%m-%Y')
				await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=req_date,end=req_date,q=tag))
		else:
			req_start_date = None
			req_end_date = None
			c = None
			if dt[0] == '':
				req_start_date = now
			elif RepresentsInt(dt[0]):
				req_start_date = now+datetime.timedelta(days=int(dt[0]))
			else:
				req_start_date = datetime.datetime.strptime(dt[0], '%d-%m-%Y')
			if dt[1] == '':
				req_end_date = None
			elif RepresentsInt(dt[1]):
				if RepresentsInt(dt[0]):
					req_end_date = now+datetime.timedelta(days=int(dt[1]))
				else:
					req_end_date = req_start_date+datetime.timedelta(days=int(dt[1]))
			else:
				req_end_date = datetime.datetime.strptime(dt[1], '%d-%m-%Y')
			if len(dt) == 3 and RepresentsInt(dt[2]):
				c = int(dt[2])
			if c != None or req_end_date != None:
				await ctx.send(embed=pretty_msg_embed(now=now,author=ctx.author,start=req_start_date,end=req_end_date,cnt=c,q=tag))

bot.run(TOKEN)

