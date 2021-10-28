def pretty_date(dt):
	return (str(dt.day) if dt.day > 9 else '0' + str(dt.day)) + '-' + (str(dt.month) if dt.month > 9 else '0' + str(dt.month)) + '-' + str(dt.year)
	
def pretty_time(dt):
	h = 12
	if dt.hour > 12:
		h = dt.hour - 12
	elif dt.hour > 0:
		h = dt.hour
	ampm = ' AM'
	if dt.hour >= 12:
		ampm = ' PM'
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
	
def pretty_delta_big(delta):
	string = ''
	s = int(delta.total_seconds()) + 30
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
	
def pretty_date_heading(dt, now):
	return '**{0:%A | %b %d}'.format(dt) + (' | 👈 Today**' if dt.date() == now.date() else '**') + '\n'

def get_role_name(event):
	if event['resource']['id'] == 1:
		try:
			return 'Codeforces#' + event['event'].split('#')[1].split()[0]
		except:
			try:
				return 'CodeforcesID#' + event['href'].split('/')[-1]
			except:
				return 'Codeforces'
	elif event['resource']['id'] == 2 or event['resource']['id'] == 1001:
		try:
			return 'CodeChef#' + event['href'].split('/')[-1]
		except:
			return 'CodeChef'	
	elif event['resource']['id'] == 93:
		try:
			return 'Atcoder#' + event['href'].split('/')[-1]
		except:
			return 'Atcoder'
	elif event['resource']['id'] == 102:
		try:
			return 'LeetCode#' + event['href'].split('/')[-1]
		except:
			return 'LeetCode'
	elif event['resource']['id'] == 35:
		try:
			return 'Google#' + event['href'].split('/')[-3]
		except:
			return 'Google'
	elif event['resource']['id'] == 90:
		try:
			return 'CSAcademy#' + event['href'].split('/')[-1]
		except:
			return 'CSAcademy'
	elif event['resource']['id'] == 73 or event['resource']['id'] == 1002:
		try:
			return 'HackerEarth#' + event['href'].split('/')[-2].split('-')[-3] + '-' + event['href'].split('/')[-2].split('-')[-2]
		except:
			return 'HackerEarth'
	elif event['resource']['id'] == 12 or event['resource']['id'] == 1003:
		try:
			return 'Topcoder#' + event['event'].split()[-2] + event['event'].split()[-1]
		except:
			return 'Topcoder#SRM'
	elif event['resource']['id'] == 29:
		return 'HackerCup'
	return 'DefaultRole'


def event_restruct(event):
	if event['resource']['id'] == 2:
		if 'Lunchtime' in event['event'] or 'Cook-Off' in event['event']:
			event['resource']['id'] = 1001
	elif event['resource']['id'] == 73:
		if 'competitive' not in event['href'].split('/'):
			event['resource']['id'] = -1
		elif 'Easy' in event['event'] or 'Data Structures and Algorithms Coding Contest' in event['event']:
			event['resource']['id'] = 1002
	elif event['resource']['id'] == 12:
		event['href'] = 'https://arena.topcoder.com'
		if 'SRM' in event['event']:
			event['resource']['id'] = 1003
	return event
