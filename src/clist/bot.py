import os
import asyncio
import discord
from discord.http import Route
from discord.ext import commands
from dotenv import load_dotenv
import datetime
import requests

from banner_scrap import *
from constants import *
from bot_utils import *

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CLIST_API_KEY = os.getenv('CLIST_API_KEY')
CLIST_USERNAME = os.getenv('CLIST_USERNAME')

bot = commands.Bot(command_prefix='^')

clist_events = {}
clist_tasks = {}
partcpt_info = {}

async def prepare_msg(event, partcpt_role, subscriber):
	start_time = datetime.datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5, minutes=30)
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	data = {}
	data['content'] = subscriber.mention + ' Next ' + notification_sites[event['resource']['id']] + ' contest about to start in ' + pretty_delta_big(start_time - now)

	embedVar = discord.Embed(color=0xf7cb0b)
	if notification_sites[event['resource']['id']] not in event['event']:
		embedVar.title = notification_sites[event['resource']['id']] + ' ' + event['event']
	else:
		embedVar.title = event['event']
	embedVar.url = event['href']
	embedVar.add_field(name='Time',value='{0:%b %d}, '.format(start_time) + pretty_time(start_time) + ' IST',inline=True)
	embedVar.add_field(name='Duration',value=pretty_delta_big(datetime.timedelta(seconds=event['duration'])),inline=True)
	embedVar.add_field(name='Role',value=partcpt_role.mention,inline=False)
	embedVar.add_field(name='Accepted',value="-",inline=True)
	embedVar.add_field(name='Declined',value="-‎",inline=True)
	embedVar.set_thumbnail(url = site_icon[event['resource']['id']])
	if event['resource']['id'] == 2 or event['resource']['id'] == 1001:
		try:
			embedVar.set_image(url=await get_banner_codechef(event['href']))
		except:
			None
	if event['resource']['id'] == 73 or event['resource']['id'] == 1002:
		try:
			embedVar.set_image(url=await get_banner_hackerearth(event['href']))
		except:
			None
	data['embed'] = embedVar.to_dict()
	data['components'] = [
		{
			'type': 1,
			'components': [
				{
					'type': 2,
					'label': 'Accept',
					'style': 3,
					'custom_id': 'accept'
				},
				{
					'type': 2,
					'label': 'Decline',
					'style': 4,
					'custom_id': 'decline'
				},
				{
					'type': 2,
					'label': 'Contest Page',
					'style': 5,
					'url': event['href']
				}
			]
		}
	]
	if event['resource']['id'] == 1:
		data['components'][0]['components'].append({
			'type': 2,
			'label': 'Register',
			'style': 5,
			'url': 'https://codeforces.com/contestRegistration/' + event['href'].split('/')[-1]
		})
	return data

async def clean_up(event, msg_id, partcpt_role):
	await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.competing, name=event['event']))
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	end_time = datetime.datetime.strptime(event['end'], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5, minutes=30)
	delta = end_time - now
	await asyncio.sleep(max(int(delta.total_seconds()), 0))
	msg = await bot.get_channel(notify_channel_id).fetch_message(msg_id)
	final_edit = {
		'content': msg.content,
		'embed': msg.embeds[0].to_dict(),
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 2,
						'label': 'Accept',
						'style': 3,
						'custom_id': 'accept',
						'disabled': True
					},
					{
						'type': 2,
						'label': 'Decline',
						'style': 4,
						'custom_id': 'decline',
						'disabled': True
					},
					{
						'type': 2,
						'label': 'Contest Link',
						'style': 5,
						'url': event['href']
					}
				]
			}
		]
	}
	edit_res = await bot.http.request(
		Route("PATCH", f"/channels/{notify_channel_id}/messages/{msg_id}"),
		json=final_edit
	)
	partcpt_info.pop(msg_id, None)
	await bot.change_presence(activity=discord.Game(name='clist.by notifications'))

	await asyncio.sleep(86400)
	await partcpt_role.delete()

async def remind_clist_event(event):
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	start_time = datetime.datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5, minutes=30)
	if start_time <= now:
		return
	delta = start_time - now
	await asyncio.sleep(max(int(delta.total_seconds()) - clist_remind_before, 0))
	guild = bot.get_guild(guild_id) # hardcoded guild id
	role_name = get_role_name(event)
	partcpt_role = await guild.create_role(name=role_name, colour= 0x43fa9a, mentionable=True, reason='Temporary role for people participating in '+role_name)
	subscriber = discord.utils.get(guild.roles, name=notify_role_name) # hardcoded notification role
	data = await prepare_msg(event, partcpt_role, subscriber)
	res = await bot.http.request(
		Route('POST', f'/channels/{notify_channel_id}/messages'),
		json=data
	)
	msg_id = int(res['id'])
	partcpt_info[msg_id] = {}
	partcpt_info[msg_id]['opt'] = {}
	partcpt_info[msg_id]['info'] = {'accept': [], 'decline': []}
	partcpt_info[msg_id]['role'] = partcpt_role

	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	delta = start_time - now
	await asyncio.sleep(max(int(delta.total_seconds()) - clist_remind_again_before, 0))
	now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
	next_reminder = {
		'content': partcpt_role.mention + ' About to start in ' + pretty_delta_big(start_time - now),
		'message_reference': {
			'channel_id': res['channel_id'],
			'message_id': res['id']
		},
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 2,
						'label': 'Open Contest Page',
						'style': 5,
						'url': event['href']
					}
				]
			}
		]
	}
	next_reminder_res = await bot.http.request(
		Route('POST', f'/channels/{notify_channel_id}/messages'),
		json=next_reminder
	)
	asyncio.create_task(clean_up(event, msg_id, partcpt_role))


async def refresh_clist_events():
	utcnow = datetime.datetime.utcnow()
	utcnext = utcnow + datetime.timedelta(days=7)
	url = 'https://clist.by/api/v1/json/contest/?username=sayanmedya&api_key=4b7854b5911aba11abe63cc8cf64a8fc928a55d3' + '&start__gt=' + utcnow.isoformat() + '&start__lt=' + utcnext.isoformat() + '&duration__lte=86401&filtered=true&order_by=start'
	loop = asyncio.get_event_loop()
	future = loop.run_in_executor(None, requests.get, url)
	res = await future
	events = res.json().get('objects', [])
	event_set = {}
	for k in clist_events:
		event_set[k] = False
	for raw_event in events:
		event = event_restruct(raw_event)
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
				print('Task Cancelltion Failed')
	
	
	
async def clist_notifiaction_service():
	while True:
		try:
			await refresh_clist_events()
		except:
			print('Refresh Event Failed')
		await asyncio.sleep(30)

@bot.event
async def on_ready():
	print(f'{bot.user} is connected to the following guild:\n')
	for guild in bot.guilds:
		print(f'{guild.name} (id: {guild.id})\n')
	asyncio.create_task(clist_notifiaction_service())
	await bot.change_presence(activity=discord.Game(name='clist.by notifications'))


@bot.event
async def on_socket_response(res):
	if res["t"] != "INTERACTION_CREATE":
		return
	if not res['d']['data'].get('component_type', None):
		return
	if not partcpt_info.get(int(res['d']['message']['id']), None):
		return
	interaction_id = res['d']['id']
	interaction_token = res['d']['token']
	user_id = int(res['d']['member']['user']['id'])
	msg = res['d']['message']
	msg_id = int(res['d']['message']['id'])
	new_opt = res['d']['data']['custom_id']
	old_opt = partcpt_info[msg_id]['opt'].get(user_id, None)
	guild = bot.get_guild(int(res['d']['guild_id']))
	member = guild.get_member(user_id)
	if not member:
		member = await guild.fetch_member(user_id)
	if old_opt:
		partcpt_info[msg_id]['info'][old_opt].remove(user_id)
	if old_opt == 'accept':
		try:
			await member.remove_roles(partcpt_info[msg_id]['role'], reason='User declined the contest')
		except:
			print('Role removal failed')
	
	partcpt_info[msg_id]['opt'][user_id] = new_opt
	partcpt_info[msg_id]['info'][new_opt].append(user_id)
	if new_opt == 'accept':
		try:
			await member.add_roles(partcpt_info[msg_id]['role'], reason='User accepted the contest')
		except:
			print('Role add failed')
	accepted = ''
	declined = ''
	if len(partcpt_info[msg_id]['info']['accept']) == 0:
		accepted += '-'
	for j in partcpt_info[msg_id]['info']['accept']:
		accepted += '<@' + str(j) + '>\n'
	if len(partcpt_info[msg_id]['info']['decline']) == 0:
		declined += '-'
	for j in partcpt_info[msg_id]['info']['decline']:
		declined += '<@' + str(j) + '>\n'
	data = {
		'content': msg['content'],
		'embed': msg['embeds'][0],
		'components': msg['components']
	}
	data['embed']['fields'][3]['value'] = accepted
	data['embed']['fields'][4]['value'] = declined
	interaction_res = await bot.http.request(
		Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
		json={'type': 6}
	)
	edit_res = await bot.http.request(
		Route("PATCH", f"/channels/{res['d']['channel_id']}/messages/{msg_id}"),
		json=data
	)


async def pager(ctx, pages, start_index):
	i = start_index
	data = {
		'embed': pages[i].to_dict(),
		'components': [
			{
				'type': 1,
				'components': [
					{
						'type': 2,
						'label': 'Prev Page',
						'style': 1,
						'custom_id': 'prev',
						'disabled': bool(start_index == 0)
					},
					{
						'type': 2,
						'label': 'Today',
						'style': 3,
						'custom_id': 'today'
					},
					{
						'type': 2,
						'label': 'Next Page',
						'style': 1,
						'custom_id': 'next',
						'disabled': bool(start_index == len(pages) - 1)
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

	while True:
		try:
			res = await bot.wait_for('socket_response', timeout=120, check=check)
			interaction_id = res['d']['id']
			interaction_token = res['d']['token']
			await bot.http.request(
				Route('POST', f'/interactions/{interaction_id}/{interaction_token}/callback'),
				json={'type': 6}
			)
			opt = res['d']['data']['custom_id']
			if opt == 'prev':
				i -= 1
			elif opt == 'next':
				i += 1
			else:
				i = start_index
			if i == 0:
				data['components'][0]['components'][0]['disabled'] = True
			else:
				data['components'][0]['components'][0]['disabled'] = False
			if i == len(pages) - 1:
				data['components'][0]['components'][2]['disabled'] = True
			else:
				data['components'][0]['components'][2]['disabled'] = False
			data['embed'] = pages[i].to_dict()
			await bot.http.request(
				Route("PATCH", f"/channels/{ctx.channel.id}/messages/{msg['id']}"),
				json=data
			)
		except asyncio.TimeoutError:
			data['components'] = None
			await bot.http.request(
				Route("PATCH", f"/channels/{ctx.channel.id}/messages/{msg['id']}"),
				json=data
			)
			break


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
	iststart = istnow + datetime.timedelta(days=-3)
	utcstart = iststart.replace(hour=0,minute=0,second=0) + datetime.timedelta(hours=-5,minutes=-30)
	
	url = 'https://clist.by/api/v1/json/contest/?username=' + CLIST_USERNAME + '&api_key=' + CLIST_API_KEY + '&end__gt=' + utcstart.isoformat() + '&duration__lte=864000&filtered=true&order_by=start'
	loop = asyncio.get_event_loop()
	future = loop.run_in_executor(None, requests.get, url)
	res = await future
	events = res.json().get('objects', [])
	last_date = None
	pages = []
	start_index = None
	for event in events:
		valid = False
		if event['resource']['id'] in sites:
			valid = True
		if event['resource']['id'] == 73 and 'competitive' not in event['href'].split('/'):
			valid = False
		if valid:
			start_dt = (datetime.datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=5,minutes=30))
			if start_dt.date() != last_date:
				if start_dt.date() >= istnow.date() and not start_index:
					start_index = len(pages)
				pages.append(discord.Embed(title = 'Live and Upcoming CP Contests'))
				pages[-1].description = pretty_date_heading(start_dt, istnow)
				last_date = start_dt.date()
			pages[-1].description += pretty_clist_desc(event, utcnow)
	for i in range(0, len(pages)):
		pages[i].set_footer(text=f'Requested by {ctx.author.display_name}  •  Page ' + str(i + 1) + ' / ' + str(len(pages)),icon_url=ctx.author.avatar_url)
	asyncio.create_task(pager(ctx, pages, start_index))

bot.run(TOKEN)
