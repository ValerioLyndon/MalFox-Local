# IMPORTS

#Database
import sqlite3

#Time and Functions
from time import sleep
from time import strftime
from datetime import datetime, timezone
import re
import urllib.parse
import os

#Scraper
import requests
import urllib.request
from bs4 import BeautifulSoup

#Misc
import traceback

# VARIABLES & SETUP

debug = False

# seconds to delay actions, preventing MAL spam protection from activating
delay = 6

# amount of 404 entries over the estimated total entries to scan before giving up
scanBuffer = 50

timeFormat = '%Y-%m-%d %H:%M:%S.%f'
runTime = strftime('%Y-%m-%d %H;%M;%S')

conn = sqlite3.connect('covers.db')
c = conn.cursor()

# Create Database if Needed

c.execute('''
	CREATE TABLE if not exists data (
		type TEXT,
		id INT,
		name TEXT,
		image TEXT,
		updated TEXT,
		error TEXT
	)
''')

# BASIC FUNCTIONS

# Encoder/Decoder for safe storage of random strings into database.

def encodeString(s):
	return urllib.parse.quote(s)

def decodeString(s):
	return urllib.parse.unquote(s)

# Formats string-formatted dates into datetime objects

def formatDate(d):
	return datetime.strptime(d, timeFormat)

# Logs string to console and file simultaneously.

def log(msg):
	output = f'{strftime("%H:%M:%S")} {msg}'
	
	if 'logs' not in os.listdir():
		os.mkdir('logs')
	with open(f'logs/log {runTime}.txt', 'a') as file:
		file.write(output + '\n')
	
	print(output)

# PROGRAM FUNCTIONS

if debug: log('DEBUG ENABLED')

# Estimate total MAL database entries

def estimateTotalEntries(listType):
	print(f'Sending web request - waiting {delay} seconds to avoid spam protection...')
	sleep(delay)
	url = 'https://myanimelist.net/_' + listType + '.php?o=9&c[0]=a&c[1]=d&cv=2'
	parsed = BeautifulSoup(requests.get(url).text, 'html.parser')
	
	recent = parsed.find('a', class_='hoverinfo_trigger')
	if recent is not None:
		recentId = recent['href'].split('/')[4]
		estimate = int(recentId)
	elif listType == 'anime':
		estimate = 40000
	elif listType == 'manga':
		estimate = 125000
	else:
		estimate = 0
	
	return estimate
	
# Return total local database entries.
# Scans down from top until it finds a valid entry. This is to account for any scan buffer entries.

def checkLocalEntries(listType):
	c.execute(f'''
		SELECT id, name
		FROM data
		WHERE type="{listType}"
		ORDER BY id DESC
	''')
	
	entries = c.fetchall()
	
	for entry in entries:
		if entry[1] == '_404_':
			continue
		else:
			return entry[0]

# Returns information from database entries in dictionary format.

def parseEntry(listType, id):
	data = {
		'type': listType,
		'id': id,
		'name': '_null_',
		'image': '_null_',
		'updated': str(datetime.utcnow()),
		'error': ['None']
	}
	
	# Fetch result
	
	sleep(delay)
	url = 'https://myanimelist.net/' + listType + '/' + str(id)
	parsed = BeautifulSoup(requests.get(url).text, 'html.parser')
	
	# Check for misc problems (504 errors, page load faults, etc)
	
	malHealth = parsed.find(id='myanimelist')
	
	if malHealth is None:
		data['name'] = '_error_'
		data['image'] = '_error_'
		data['error'] = ['unknown', 1]
		return data
	
	# Check for 404
	
	deadEntry = parsed.find('img', src=re.compile('^https\://cdn\.myanimelist\.net/images/error/404_image\.png'))
	
	if deadEntry is not None:
		data['name'] = '_404_'
		data['image'] = '_404_'
		data['error'] = ['404', 1]
		return data
		
	# Fetch new data
	
	name = parsed.find('span', itemprop='name')
	if name is not None:
		data['name'] = encodeString(name.text)
	
	image = parsed.find('img', itemprop='image')
	if image is not None:
		if image.get('data-src') is not None:
			data['image'] = image.get('data-src')
		elif image.get('src') is not None:
			data['image'] = image.get('src')
	
	if debug: print('[DEBUG] Unfiltered new:', data)
	return data

# Commits changes for a single entry to database.

def updateById(listType, id):
	logPrefix = f'{listType[:1]}{str(id).zfill(6)}'
	
	newData = parseEntry(listType, id)
	
	# Check for existence in DB
	
	c.execute(f'''
		SELECT type, id, name, image, updated, error
		FROM data
		WHERE type="{listType}"
		AND id={id}
	''')
	entry = c.fetchone()
	
	if entry is None:
		# If entry does NOT exist
		
		sqlCommand = '''
			INSERT INTO data
			(type, id, name, image, updated, error)
			VALUES("{type}", {id}, "{name}", "{image}", "{updated}", "{error}")
		'''
		
		# Log Changes
		if newData['error'][0] == '404':
			logSuffix = 'Added new (404)'
		elif newData['error'][0] != 'None':
			logSuffix = f'Added new ({newData["error"][0]} error)'
		else:
			logSuffix = 'Added new'
	
	else:
		# If entry DOES exist
		
		sqlCommand = '''
			UPDATE data
			SET name="{name}",
				image="{image}",
				updated="{updated}",
				error="{error}"
			WHERE type="{type}"
			AND id={id}
		'''
		
		oldData = {
			'type': entry[0],
			'id': entry[1],
			'name': entry[2],
			'image': entry[3],
			'updated': entry[4],
			'error': entry[5].split(', ')
		}
		
		# Handle data
		
		if newData['error'][0] != 'None':
			# Check for previous errors and add their counts together
			daysSinceLast = abs(formatDate(oldData['updated']) - formatDate(newData['updated'])).days
			
			if daysSinceLast > 7 and newData['error'][0] == oldData['error'][0]:
				newData['error'][1] = int(newData['error'][1]) + int(oldData['error'][1])
			
			# Sets data as 404 if entry has 404'd 5 times
			# if below threshold or generic error it retains old data
			if newData['error'][0] == '404' and int(newData['error'][1]) > 4:
				logSuffix = 'entry set as 404 - reached max 404s'
			else:
				newData['name'] = oldData['name']
				newData['image'] = oldData['image']
				
				if newData['error'][0] == '404':
					logSuffix = 'nothing updated (404)'
				
				else:
					# Generic error handling
					logSuffix = f'error: {newData["error"][0]}'
		
		else:
			updated = []
			
			if newData['name'] == '_null_' and oldData['name'] != '_404_' and oldData['name'] != '_error_':
				newData['name'] = oldData['name']
			elif newData['name'] != oldData['name']:
				updated += ['name']
			
			if newData['image'] == '_null_' and oldData['image'] != '_404_' and oldData['image'] != '_error_':
				newData['image'] = oldData['image']
			elif newData['image'] != oldData['image']:
				updated += ['image']
			
			# Log changes
			if len(updated) > 0:
				logSuffix = f'{" & ".join(updated)} updated'
			elif newData['name'] == '_null_' and newData['image'] == '_null_':
				logSuffix = 'nothing updated (null entry)'
			else:
				logSuffix = 'nothing updated'
	
	# Commit Changes
	
	if debug: print('[DEBUG] Filtered new:', newData)
	
	formattedError = ', '.join(str(x) for x in newData['error'])
	
	sqlCommand = sqlCommand.format(type=newData['type'], id=newData['id'], name=newData['name'], image=newData['image'], updated=newData['updated'], error=formattedError)
	
	if debug: print(sqlCommand)
	c.execute(sqlCommand)
	if not debug: conn.commit()
	
	log(f'{logPrefix} {logSuffix}')
	return newData

# Build Database

def build(listType):
	log('BEGIN BUILDING')
	
	# Set total entry counts.
	
	localEntryCount = checkLocalEntries(listType)
	totalEntryCount = estimateTotalEntries(listType)
	
	# Set existing IDs in DB
	
	c.execute(f'''
		SELECT id
		FROM data
		WHERE type="{listType}"
	''')
	entries = c.fetchall()
	ids = [id for tuple in entries for id in tuple]
	
	# Begin building
	
	try:
		errorStreak = 0
		id = 0
		
		while True:
			id += 1
			
			if id < totalEntryCount:
				errorStreak = 0
			
			if errorStreak >= scanBuffer:
				log('Max 404 streak reached, stopping search.')
				break
			
			logPrefix = f'{listType[:1]}{str(id).zfill(6)}'
			
			# Check DB for duplicates and skip if found
			# Does this outside of updateById function to avoid parsing every entry unnecessarily
			# Only skips if below the scanBuffer.
			
			if id in ids and id < localEntryCount:
				log(f'{logPrefix} Skipped (already in DB)')
				continue
			
			# Update entry and set variable containing data
			
			data = updateById(listType, id)
			
			# Count errors
			if data['error'][0] == '404':
				errorStreak += 1
			else:
				errorStreak = 0
		
		log('FINISHED BUILDING')
	except:
		log('ERROR: ' + traceback.format_exc())

# Maintain Database

def maintain():
	log('BEGIN MAINTAINING OLD')
	
	# Set total entry count
	
	localAnimeCount = checkLocalEntries('anime')
	localMangaCount = checkLocalEntries('manga')
	
	# Select entries to update
	
	c.execute(f'''
		SELECT type, id, name, image, updated, error
		FROM data
		ORDER BY updated ASC
	''')
	
	entries = []
	for row in c.fetchall():
		entries.append([col for col in row])
	
	# Sort entries by priority
	
	print('Sorting database, this may take a second...')
	
	checkTime = datetime.utcnow()
	
	for entry in entries:
		currentData = {
			'type': entry[0],
			'id': entry[1],
			'name': entry[2],
			'image': entry[3],
			'updated': entry[4],
			'error': entry[5].split(', ')
		}
		
		if currentData['type'] == 'anime':
			localEntryCount = localAnimeCount
		elif currentData['type'] == 'manga':
			localEntryCount = localMangaCount
		
		# Calculate check weight - lower weight = checks sooner
		
		# Set formula based on database entries
		weightId = (localEntryCount / currentData['id'])
		
		# Set formula based on time since last check - try except is to catch entries with no updated value
		try:
			daysSinceLast = abs(datetime.strptime(currentData['updated'], timeFormat) - checkTime).days
			if daysSinceLast < 0.5:
				daysSinceLast = 0.5
		except:
			daysSinceLast = 365
		
		# Uses 120 days as a benchmark for priority
		weightTime = 120 / (daysSinceLast / 120)
		
		# Set caps on values to avoid extreme outliers.
		if weightId > 3:
			weightId = 3
		
		if daysSinceLast < 0.1:
			daysSinceLast = 0.1
		
		# Combine formulas to find total weight
		
		weight = weightTime * weightId
		
		# Lower weight if 404
		
		if currentData['name'] == '_404_':
			weight = weight * 2
		
		# Adjust weight data
		if debug: print('[DEBUG] Weight:', weight)
		entry.append(weight)
	
	entries.sort(key = lambda col: col[6])
	
	# Begin updating
	
	try:
		for entry in entries:
			if debug: print('[DEBUG] Current:', entry)
			
			currentData = {
				'type': entry[0],
				'id': entry[1],
				'name': entry[2],
				'image': entry[3],
				'updated': entry[4],
				'error': entry[5].split(', ')
			}
			
			# Skip 404s
			
			if len(currentData['error']) > 1 and int(currentData['error'][1]) > 4:
				continue
			
			# Update entry
			
			updateById(currentData['type'], currentData['id'])
		
		log('MAINTENANCE COMPLETE')
	except:
		log('ERROR: ' + traceback.format_exc())

# Commands

if __name__ == '__main__':
	build('anime')
	build('manga')
	maintain()