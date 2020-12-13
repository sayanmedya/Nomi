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
CLIST_API_KEY = os.getenv('CLIST_API_KEY')

EMBED_COLOR = 0x7e76dc
NO_EVENT_MESSAGE = 'No Class Found'

bot = commands.Bot(command_prefix='^')

weekday_list=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
week_day_lower = {
	'sunday':0,'sun':0,'monday':1,'mon':1,'tuesday':2,'tue':2,'wednesday':3,'wed':3,'thursday':4,'thu':4,'friday':5,'fri':5,'saturday':6,'sat':6
}

class_id = {'CLASS_CODE' : 'CLASS_CODE'
	}
			
subject = {
	'CLASSROOM_ID' : {
		'title' : 'CLASS_NAME',
		'short' : 'CLASS_CODE',
		'link' : 'MEET_LINK',
		'mention' : 'ROLE_NAME_TO_BE_MENTIONED',
		'tags' : []
	}
}

teacher = { 'CLASSROOM_ID': {'name': 'TEACHER_NAME', 'icon_url': 'PROFILE_PHOTO_URL'}
		}

no_photourl = 'http://www.clker.com/cliparts/f/a/0/c/1434020125875430376profile.png'

remind_before = 599

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly', 
		'https://www.googleapis.com/auth/classroom.courses.readonly',
		'https://www.googleapis.com/auth/classroom.rosters.readonly',
		'https://www.googleapis.com/auth/classroom.student-submissions.me.readonly',
		'https://www.googleapis.com/auth/classroom.announcements.readonly']

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
classroom_service = build('classroom', 'v1', credentials=creds)

start_time_map = {}
task_map = {}

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
		desc += '🟢 ` '
	elif now >= sdt:
		desc += '🔴 ` '
	else:
		desc += '🟡 ` '
	link = subject[class_id[event['summary'][0:6]]]['link']
	desc += pretty_time(sdt) + ' - ' + pretty_time(edt) + ' | ' + event['summary'] + ' ` [GMeet🔗](' + link + ')\n\n'
	return desc
	
def pretty_date_heading(dt, now):
	return '**{0:%A | %b %d}'.format(dt) + (' | 👈 Today**' if dt.date() == now.date() else '**') + '\n'

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
	#'🟢 (Past)  |  🔴 (Live)  |  🟡 (Upcoming)\n'
	embedVar.set_footer(text=f'Requested by {author.display_name} • ' + pretty_time(now),icon_url=author.avatar_url)
	return embedVar


def pretty_notice_embed(notice):
	name = teacher[notice['creatorUserId']]['name']
	photoUrl = teacher[notice['creatorUserId']]['icon_url']
	# else:
		# creator = classroom_service.courses().students().list(courseId=notice['courseId']).execute() #,userId=notice['creatorUserId']
		# print(creator)
		# name = creator['name']['fullName']

	embedVar = discord.Embed(color=EMBED_COLOR)
	embedVar.set_author(name=name, icon_url=photoUrl)
	embedVar.title = '📢 Announcement | ' + subject[notice['courseId']]['title']
	embedVar.description = '\n[Open in Classroom ↗️](' + notice['alternateLink'] + ')\n\n'
	embedVar.description += notice['text'] +'\n\n'
	materials=notice.get('materials', [])
	if materials:
		for material in materials:
			if 'driveFile' in material:
				embedVar.description += '[📄' + material['driveFile']['driveFile']['title'] + '](' + material['driveFile']['driveFile']['alternateLink'] + ')\n'
			if 'link' in materials:
				embedVar.description += '[🔗' + material['link']['title'] + '](' + material['link']['url'] + ')\n'
			if 'form' in materials:
				embedVar.description += '[📑' + material['form']['title'] + '](' + material['form']['formUrl'] + ')\n'
	create_time = datetime.datetime.strptime(notice['creationTime'][0:19], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5,minutes=30)
	update_time = datetime.datetime.strptime(notice['updateTime'][0:19], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5,minutes=30)
	# if 'scheduledTime' in notice:
		# post_time = datetime.datetime.strptime(notice['creationTime'][0:19], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5,minutes=30)
	footer ='Created ' + '{0:%a • %b %d • %I:%M%p}'.format(create_time)
	if (update_time - create_time).total_seconds() > 600:
		footer += '\nUpdated ' + '{0:%a • %b %d • %I:%M%p}'.format(update_time)
	embedVar.set_footer(text=footer)
	return embedVar


def pretty_assign_embed(notice):
	name = teacher[notice['creatorUserId']]['name']
	photoUrl = teacher[notice['creatorUserId']]['icon_url']
	# else:
		# creator = classroom_service.userProfiles().get(userId=notice['creatorUserId']).execute()
		# name = creator['name']['fullName']

	post_time = datetime.datetime.strptime(notice['creationTime'][0:19], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5,minutes=30)
	embedVar = discord.Embed(color=EMBED_COLOR)
	embedVar.set_author(name=name, icon_url=photoUrl)
	if notice['workType'] == 'ASSIGNMENT':
		embedVar.title = '📋 Assignment | ' + subject[notice['courseId']]['title']
	elif notice['workType'] == 'SHORT_ANSWER_QUESTION':
		embedVar.title = '❓ Question | ' + subject[notice['courseId']]['title']
	else:
		embedVar.title = '📑 Quiz | ' + subject[notice['courseId']]['title']
	embedVar.description = '**' + notice['title'] + '**'
	embedVar.description += '\n[Open in Classroom ↗️](' + notice['alternateLink'] + ')\n'
	if 'dueDate' in notice:
		due = datetime.datetime(notice['dueDate']['year'], notice['dueDate']['month'], notice['dueDate']['day'])
		hr = 0
		mn = 0
		if 'hours' in notice['dueTime']:
			hr=notice['dueTime']['hours']
		if 'minutes' in notice['dueTime']:
			mn = notice['dueTime']['minutes']
		due += datetime.timedelta(hours=hr+5, minutes=mn+30)
		now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
		if due <= now:
			embedVar.description += '🟢 `'
		else:
			embedVar.description += '🔴 `'
		embedVar.description += 'Due ' + '{0:%a • %b %d • %I:%M %p}'.format(due)
		if due > now:
			embedVar.description += ' | ' + pretty_delta(due - now) + ' remaining'
		embedVar.description += '`\n\n'
	else:
		embedVar.description += '🟡 `No due date specified`\n\n'
	if 'description' in notice:
		embedVar.description += notice['description'] + '\n\n'
	materials=notice.get('materials', [])
	if materials:
		for material in materials:
			if 'driveFile' in material:
				embedVar.description += '[📄' + material['driveFile']['driveFile']['title'] + '](' + material['driveFile']['driveFile']['alternateLink'] + ')\n'
			if 'link' in material:
				embedVar.description += '[🔗' + material['link']['title'] + '](' + material['link']['url'] + ')\n'
			if 'form' in material:
				embedVar.description += '[📑' + material['form']['title'] + '](' + material['form']['formUrl'] + ')\n'
	create_time = datetime.datetime.strptime(notice['creationTime'][0:19], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5,minutes=30)
	update_time = datetime.datetime.strptime(notice['updateTime'][0:19], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5,minutes=30)
	# if 'scheduledTime' in notice:
		# post_time = datetime.datetime.strptime(notice['creationTime'][0:19], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5,minutes=30)
	footer ='Created ' + '{0:%a • %b %d • %I:%M%p}'.format(create_time)
	if (update_time - create_time).total_seconds() > 600:
		footer += '\nUpdated ' + '{0:%a • %b %d • %I:%M%p}'.format(update_time)
	embedVar.set_footer(text=footer)
	return embedVar


async def status_task():
	while True:
		await bot.change_presence(activity=discord.Game(name='3rd year class routine'))
		await asyncio.sleep(10)
		await bot.change_presence(activity=discord.Game(name='type ^help for help'))
		await asyncio.sleep(10)
		
		now = datetime.datetime.utcnow() + datetime.timedelta(hours=5,minutes=30)
		now_iso = now.isoformat() + '+05:30'
		stm_copy = start_time_map.copy()
		for key in stm_copy:
			class_name = stm_copy[key]['summary'][0:6]
			sdt_iso = stm_copy[key]['start']['dateTime']
			sdt = datetime.datetime.strptime(sdt_iso[0:19], '%Y-%m-%dT%H:%M:%S')
			edt_iso = stm_copy[key]['end']['dateTime']
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
			await asyncio.sleep(10)

async def remind_event(event):
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	start_time = datetime.datetime.strptime(event['start']['dateTime'][0:19], '%Y-%m-%dT%H:%M:%S')
	if start_time <= now:
		return
	delta = start_time - now
	await asyncio.sleep(max(int(delta.total_seconds()) - remind_before, 0))
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	embedVar = discord.Embed(color=0xf7cb0b)
	embedVar.description = pretty_class_desc(event, now)
	delay =  (min(int((start_time - now).total_seconds()), remind_before) + 2) // 60
	embedVar.title = 'Next class is about to start in ' + str(delay) + ' min'
	guild=bot.get_guild(718886828891176997)
	notify_channel = discord.utils.get(guild.text_channels, id=755718650111066163)
	subscriber = discord.utils.get(guild.roles, name=subject[class_id[event['summary'][0:6]]]['mention'])
	await notify_channel.send(f'{subscriber.mention}',embed=embedVar)
	
async def refresh_events():
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	start_iso = now.isoformat() + '+05:30'
	end_iso = (now + datetime.timedelta(days=1)).isoformat() + '+05:30'
	while True:
		try:
			events_result = service.events().list(calendarId=C_ID, timeMin=start_iso, timeMax=end_iso, singleEvents=True, orderBy='startTime').execute()
			break
		except:
			await asyncio.sleep(10)
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


async def notifiaction_service():
	while True:
		await refresh_events()
		await asyncio.sleep(60)
	

clist_events = {}
clist_tasks = {}

notification_sites = {
			1  : 'Codeforces',
			# 2  : 'CodeChef',
			# 12 : 'Topcoder',
			29 : 'Facebook HackerCup',
			35 : 'Google',
			# 63 : 'HackerRank'
			# 65 : 'Project Euler'
			# 73 : 'HackerEarth'
			93 : 'AtCoder',
			102: 'LeetCode'
		}

clist_remind_before = 1799

async def remind_clist_event(event):
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	start_time = datetime.datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5, minutes=30)
	if start_time <= now:
		return
	delta = start_time - now
	await asyncio.sleep(max(int(delta.total_seconds()) - clist_remind_before, 0))
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	embedVar = discord.Embed(color=0xf7cb0b)
	delay =  (int((start_time - now).total_seconds()) + 2) // 60
	embedVar.title = 'About to start in ' + str(delay) + ' min'
	desc = ''
	if notification_sites[event['resource']['id']] not in event['event'].split():
		desc += '🟡  __[' + sites[event['resource']['id']] + ' ' + event['event'] + '](' + event['href'] + ')__\n'
	else:
		desc += '🟡  __[' + event['event'] + '](' + event['href'] + ')__\n'
	desc += '` {0:%a | %b %d} | '.format(start_time) + pretty_time(start_time) + ' | '
	desc += pretty_delta(datetime.timedelta(seconds=event['duration'])) + ' `'
	embedVar.description = desc
	embedVar.set_thumbnail(url = 'https://clist.by' + event['resource']['icon'])
	guild=bot.get_guild(718886828891176997)
	notify_channel = discord.utils.get(guild.text_channels, id=769509892843110450)
	subscriber = discord.utils.get(guild.roles, name='CP')
	msg = await notify_channel.send(f'{subscriber.mention}',embed=embedVar)
	await msg.publish()


async def refresh_clist_events():
	utcnow = datetime.datetime.utcnow()
	utcnext = utcnow + datetime.timedelta(days=1)
	url = 'https://clist.by/api/v1/json/contest/?username=sayanmedya&api_key=' + CLIST_API_KEY + '&start__gt=' + utcnow.isoformat() + '&start__lt=' + utcnext.isoformat() + '&duration__lte=864000&filtered=true&order_by=start'
	loop = asyncio.get_event_loop()
	future = loop.run_in_executor(None, requests.get, url)
	res = await future
	events = res.json().get('objects', [])
	event_set = {}
	for k in clist_events:
		event_set[k] = False
	for event in events:
		if event['resource']['id'] in notification_sites:
			if event['id'] in clist_events:
				if event != clist_events[event['id']]:
					try:
						clist_tasks[event['id']].cancel()
					except:
						print(event)
					clist_events[event['id']] = event
					tsk = asyncio.create_task(remind_clist_event(event))
					clist_tasks[event['id']] = tsk
				event_set[event['id']] = True
			else:
				clist_events[event['id']] = event
				tsk = asyncio.create_task(remind_clist_event(event))
				clist_tasks[event['id']] = tsk
	for k in event_set:
		if event_set[k] == False:
			try:
				clist_tasks[k].cancel()
				clist_events.pop(k, None)
				clist_tasks.pop(k, None)
			except:
				print(k)
	
	
	
async def clist_notifiaction_service():
	while True:
		await refresh_clist_events()
		await asyncio.sleep(600)



@bot.event
async def on_ready():
	for guild in bot.guilds:
		if guild.name == GUILD:
			break
	# subscriber = discord.utils.get(guild.roles, id=755692949052063764)
	# notify_channel = discord.utils.get(guild.text_channels, id=755718650111066163)
	print(
		f'{bot.user} is connected to the following guild:\n'
		f'{guild.name}(id: {guild.id})\n'
	)
	asyncio.create_task(status_task())
	asyncio.create_task(notifiaction_service())
	asyncio.create_task(clist_notifiaction_service())
'''
@bot.command(help='Say hello')
async def hello(ctx):
	embedVar = discord.Embed(title="Hello World", description=f'hi {ctx.author.mention}', color=EMBED_COLOR)
	await ctx.send(embed=embedVar)
'''
@bot.command(help='Shows the avatar of the mentioned user')
async def avatar(ctx, vctm: User):
	await ctx.send(str(vctm.avatar_url))

@bot.command(help='Slaps the mentioned user')
async def slap(ctx, vctm: User):
	req = requests.get(str(vctm.avatar_url_as(format='jpg',size=256)), stream=True).raw
	arr = np.asarray(bytearray(req.read()), dtype="uint8")
	top = cv2.imdecode(arr, cv2.IMREAD_COLOR)
	btm = cv2.imread('e.jpg')
	btm[240:240+top.shape[0], 520:520+top.shape[1]] = top
	cv2.imwrite("a.jpg", btm)
	await ctx.message.channel.send(file=discord.File('a.jpg'))
'''
@bot.command(help='Choose 1 - 200 random words for skribble. Pass the number of words as argument')
async def words(ctx, cnt : int):
	await ctx.trigger_typing()
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

@bot.command(help='Solve simple mathematical expression')
async def math(ctx, *, arg):
	try:
		await ctx.send("```" + str(eval(arg)) + "```")
	except:
		await ctx.send("Ooops! wrong expression")
'''
last_spam = {}
spam_cooldown = 900
spam_message = 25
auto_delete_time = 300

@bot.command(name='spam', help='25x Spam, Cooldown = 15 min, Auto delete after 5 min')
async def spm(ctx, *, arg):
	#arg = discord.utils.escape_mentions(arg)
	now = datetime.datetime.utcnow()
	if ctx.author.id in last_spam:
		delta = (now - last_spam[ctx.author.id])
		if delta.total_seconds() < spam_cooldown:
			dlt = last_spam[ctx.author.id] - now + datetime.timedelta(seconds=spam_cooldown)
			m = int(dlt.total_seconds()) // 60
			s = int(dlt.total_seconds()) % 60
			delay = ''
			if m != 0:
				delay += str(m) + 'min '
			if s != 0 or (m == 0 and s == 0):
				delay += str(s) + 'sec'
			await ctx.send(f'{ctx.author.mention}, You will be able to spam again in ' + delay)
			return
	
	last_spam[ctx.author.id] = now
	for i in range(0, spam_message):
		await ctx.send(arg, delete_after=auto_delete_time, allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False))
		await asyncio.sleep(1)


@bot.command(name='class', help='Shows the class routine')
async def clss(ctx, *, arg):
	await ctx.trigger_typing()
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


@bot.command(help='Shows recent classroom announcements')
async def annc(ctx, arg):
	await ctx.trigger_typing()
	if arg not in class_id:
		return
	await ctx.trigger_typing()
	result = classroom_service.courses().announcements().list(courseId = class_id[arg]).execute()
	notices = result.get('announcements', [])
	pages = []
	for i in range(len(notices) - 1, -1, -1):
		if notices[i]['creatorUserId'] in teacher:
			pages.append(pretty_notice_embed(notices[i]))
	for i in range(0, len(pages)):
		pages[i].set_footer(text = pages[i].footer.text + '\nPage ' + str(i + 1) + ' / ' + str(len(pages)))
	asyncio.create_task(pager(ctx, pages, len(pages) - 1))



emojis = ['⏪', '◀️', '▶️', '⏩']

async def pager(ctx, pages, i):
	msg = await ctx.send(embed = pages[i])
	asyncio.gather(msg.add_reaction('⏪'), msg.add_reaction('◀️'), msg.add_reaction('▶️'), msg.add_reaction('⏩'),)
	

	def check(reaction, user):
		return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in emojis

	while True:
		try:
			reaction, user = await bot.wait_for('reaction_add', timeout=120, check=check)
			await reaction.remove(user)
			if str(reaction.emoji) == '⏪':
				if i > 0:
					i = 0
					await msg.edit(embed=pages[i])
			elif str(reaction.emoji) == '◀️':
				if i > 0:
					i -= 1
					await msg.edit(embed=pages[i])
			elif str(reaction.emoji) == '▶️':
				if i < len(pages) - 1:
					i += 1
					await msg.edit(embed=pages[i])
			else:
				if i < len(pages) - 1:
					i = len(pages) - 1
					await msg.edit(embed=pages[i])
		except asyncio.TimeoutError:
			await msg.clear_reactions()




@bot.command(help='Shows recent classroom assignments')
async def assgn(ctx, arg):
	await ctx.trigger_typing()
	if arg not in class_id:
		return
	result = classroom_service.courses().courseWork().list(courseId = class_id[arg]).execute()
	notices = result.get('courseWork', [])
	pages = []
	for i in range(len(notices) - 1, -1, -1):
		if notices[i]['creatorUserId'] in teacher:
			pages.append(pretty_assign_embed(notices[i]))
	for i in range(0, len(pages)):
		pages[i].set_footer(text = pages[i].footer.text + '\nPage ' + str(i + 1) + ' / ' + str(len(pages)))
	asyncio.create_task(pager(ctx, pages, len(pages) - 1))
			
@bot.command(help='Lists all members in the server')
async def members(ctx):
	await ctx.trigger_typing()
	guild = ctx.guild
	embedVar = discord.Embed(color=EMBED_COLOR)
	embedVar.title = f'Members of {guild.name}'
	desc = '```css\n'
	desc += ' #   Joined   Name\n'
	desc += '--   ------   ------------------\n'
	i = 0
	members = sorted(guild.members, key=lambda x: x.joined_at)
	for member in members:
		if not member.bot:
			i += 1
			desc += ' ' * (2 - len(str(i))) + str(i)
			desc += '   {0:%b %d}'.format(member.joined_at)
			desc += '   ' + member.name + ('👑' if member == guild.owner else '') + '\n'
	desc += '```'
	embedVar.description = desc
	await ctx.send(embed=embedVar)
	
	
sites = {	1  : 'Codeforces',
			2  : 'CodeChef',
			12 : 'Topcoder',
			29 : 'Facebook HackerCup',
			35 : 'Google',
			# 63 : 'HackerRank'
			# 65 : 'Project Euler'
			73 : 'HackerEarth',
			93 : 'AtCoder',
			102: 'LeetCode'
		}

def pretty_clist_desc(event, now):
	desc = ''
	sdt = datetime.datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S')
	edt = datetime.datetime.strptime(event['end'], '%Y-%m-%dT%H:%M:%S')
	if edt < now:
		desc += '🟢'
	elif now >= sdt:
		desc += '🔴'
	else:
		desc += '🟡'
	if sites[event['resource']['id']] not in event['event'].split():
		desc += '  __[' + sites[event['resource']['id']] + ' ' + event['event'] + '](' + event['href'] + ')__\n'
	else:
		desc += '  __[' + event['event'] + '](' + event['href'] + ')__\n'
	desc += '` ' + pretty_time(sdt + datetime.timedelta(hours=5, minutes=30)) + ' | '
	desc += pretty_delta(datetime.timedelta(seconds=event['duration'])) + ' | '
	if edt < now:
		desc += 'ended ' + pretty_delta(now-edt).split()[0] + ' ago'
	elif now >= sdt:
		desc += 'ends in ' + pretty_delta(edt-now).split()[0]
	else:
		desc += 'starts in ' + pretty_delta(sdt-now).split()[0]
	desc += ' `\n\n'
	return desc



@bot.command(help='Shows upcoming Competitive Programming contests')
async def clist(ctx):
	await ctx.trigger_typing()
	utcnow = datetime.datetime.utcnow()
	istnow = utcnow + datetime.timedelta(hours=5,minutes=30)
	utcstart = istnow.replace(hour=0,minute=0,second=0) + datetime.timedelta(hours=-5,minutes=-30)
	#end = start + datetime.timedelta(days=7)
	
	url = 'https://clist.by/api/v1/json/contest/?username=CLIST_USERNAME&api_key=' + CLIST_API_KEY + '&end__gt=' + utcstart.isoformat() + '&duration__lte=864000&filtered=true&order_by=start'
	loop = asyncio.get_event_loop()
	future = loop.run_in_executor(None, requests.get, url)
	res = await future
	events = res.json().get('objects', [])
	
	last_date = None
	pages = []
	for event in events:
		valid = False
		if event['resource']['id'] in sites:
			valid = True
		if event['resource']['id'] == 73 and 'competitive' not in event['href'].split('/'):
			valid = False
		if valid:
			start_dt = (datetime.datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5,minutes=30))
			if start_dt.date() != last_date:
				pages.append(discord.Embed(color=EMBED_COLOR, title = 'Live and Upcoming CP Contests'))
				pages[-1].description = pretty_date_heading(start_dt, istnow)
				last_date = start_dt.date()
			pages[-1].description += pretty_clist_desc(event, utcnow)
	for i in range(0, len(pages)):
		pages[i].set_footer(text=f'Requested by {ctx.author.display_name}  •  Page ' + str(i + 1) + ' / ' + str(len(pages)),icon_url=ctx.author.avatar_url)
	asyncio.create_task(pager(ctx, pages, 0))

@bot.command(help = 'Shows bot latency')
async def ping(ctx):
	png = int(bot.latency * 1000)
	if png < 100:
		clr = '🟢'
	elif png < 1000:
		clr = '🟡'
	else:
		clr = '🔴'
	embedVar = discord.Embed(color=EMBED_COLOR, description=f' {clr} ` {png} ms `')
	await ctx.send(embed=embedVar)

bot.run(TOKEN)
