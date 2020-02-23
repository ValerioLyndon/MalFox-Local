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

# VARIABLES & SETUP

debug = False

# seconds to delay actions, preventing MAL spam protection from activating

delay = 6

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
		updated TEXT
	)
''')

# BASIC FUNCTIONS

# Encoder/Decoder for safe storage of random strings into database.

def encodeString(s):
	return urllib.parse.quote(s)

def decodeString(s):
	return urllib.parse.unquote(s)

def log(msg):
	output = f'{strftime("%H:%M:%S")} {msg}'
	
	if 'logs' not in os.listdir():
		os.mkdir('logs')
	with open(f'logs/log {runTime}.txt', 'a') as file:
		file.write(output + '\n')
	
	print(output)

# PROGRAM FUNCTIONS

if debug: log('DEBUG ENABLED')

# Estimate total database entries

def estimateEntries(type):
	url = 'https://myanimelist.net/' + type + '.php?o=9&c[0]=a&c[1]=d&cv=2'
	parsed = BeautifulSoup(requests.get(url).text, 'html.parser')
	
	# Add delay - uses print instead of log since time delays will only matter when viewing live
	print(f'Sent web request - waiting {delay} seconds to avoid spam protection...')
	sleep(delay)
	
	recent = parsed.find('a', class_='hoverinfo_trigger')
	recentId = recent['href'].split('/')[4]
	
	estimate = int(recentId) + 50
	return estimate

# Returns information from database entries in dictionary format.

def parseEntry(listType, id):
	data = {
		'type': listType,
		'id': id,
		'name': '_null_',
		'image': '_null_',
		'updated': str(datetime.utcnow())
	}
	
	# Fetch result
	
	url = 'https://myanimelist.net/' + listType + '/' + str(id)
	parsed = BeautifulSoup(requests.get(url).text, 'html.parser')
	
	# Add delay - uses print instead of log since time delays will only matter when viewing live
	#print(f'Sent web request - waiting {delay} seconds to avoid spam protection...')
	sleep(delay)
	
	# Check for misc problems (504 errors, page load faults, etc)
	
	malHealth = parsed.find(id='myanimelist')
	
	if malHealth is None:
		data['name'] = '_error_'
		data['image'] = '_error_'
		data['error'] = 'unknown'
		return data
	
	# Check for 404
	
	deadEntry = parsed.find('img', src=re.compile('^https\://cdn\.myanimelist\.net/images/error/404_image\.png'))
	
	if deadEntry is not None:
		data['name'] = '_404_'
		data['image'] = '_404_'
		data['error'] = '404'
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
	
	if debug: log(data)
	return data

# Commits changes for a single entry to database.

def updateById(listType, id):
	logPrefix = f'{listType[:1]}{str(id).zfill(6)}'
	
	newData = parseEntry(listType, id)
	
	# Check for existence in DB
	
	c.execute(f'''
		SELECT type, id, name, image, updated
		FROM data
		WHERE type="{listType}"
		AND id={id}
	''')
	entry = c.fetchone()
	
	if entry is None:
		# If entry does NOT exist
		
		sqlCommand = '''
			INSERT INTO data
			(type, id, name, image, updated)
			VALUES("{type}", {id}, "{name}", "{image}", "{updated}")
		'''
		
		logSuffix = 'Entry Added'	
	
	else:
		# If entry DOES exist
		
		sqlCommand = '''
			UPDATE data
			SET name="{name}",
				image="{image}",
				updated="{updated}"
			WHERE type="{type}"
			AND id={id}
		'''
		
		oldData = {
			'type': entry[0],
			'id': entry[1],
			'name': entry[2],
			'image': entry[3],
			'updated': entry[4]
		}
		
		# Handle data
		
		if 'error' in newData:
			# Retain old data if error - this may change in future but for now it prioritizes maintaining data in case it's a 404 caused by other issues
			newData['name'] = oldData['name']
			newData['image'] = oldData['image']
			
			if newData['error'] == '404':
				logSuffix = '404 entry'
				
			elif newData['error'] is not None:
				# Generic error handling
				logSuffix = f'error: {newData["error"]}'
		
		else:
			updated = []
			
			if newData['name'] == '_null_':
				newData['name'] = oldData['name']
			
			elif newData['name'] != oldData['name']:
				updated += ['name']
			
			if newData['image'] == '_null_':
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
	
	sqlCommand = sqlCommand.format(type=newData['type'], id=newData['id'], name=newData['name'], image=newData['image'], updated=newData['updated'])
	
	if debug: print(sqlCommand)
	c.execute(sqlCommand)
	if not debug: conn.commit()
	
	log(f'{logPrefix} {logSuffix}')
	
	return newData

# Build Database

def build(listType):
	log('BEGIN BUILDING')
	
	totalEntries = estimateEntries(listType)
	
	c.execute('''
		SELECT id
		FROM data
	''')
	entries = c.fetchall()
	ids = [id for tuple in entries for id in tuple]
	
	try:
		for id in range(totalEntries):
			id += 1
			checkTime = datetime.utcnow()
			logPrefix = f'{listType[:1]}{str(id).zfill(6)}'
			
			# Check DB for duplicates - does this outside of updateById function to avoid parsing every entry unnecessarily
			
			if id in ids:
				log(f'{logPrefix} Skipped (already in DB)')
				continue
			
			# If entry not exist
			
			updateById(listType, id)
		log('FINISHED BUILDING')
	except Exception as e:
		log('ERROR: ' + str(e))

# Maintain Database

def maintainOld(listType):
	log('BEGIN MAINTAINING OLD')
	
	# Find highest ID in DB
	
	c.execute(f'''
		SELECT id
		FROM data
		WHERE type="{listType}"
		ORDER BY id DESC
	''')
	localEntries = c.fetchone()[0]
	
	# Select entries to update
	
	c.execute(f'''
		SELECT type, id, name, image, updated
		FROM data
		WHERE type="{listType}"
		ORDER BY updated ASC
	''')
	
	entries = c.fetchall()
	
	try:
		for entry in entries:
			currentData = {
				'type': entry[0],
				'id': entry[1],
				'name': entry[2],
				'image': entry[3],
				'updated': entry[4]
			}
			
			checkTime = datetime.utcnow()
			
			# Skip blanks
			
			if currentData['name'] == '_404_':
				continue
			
			# Check Date
			
			if currentData['updated'] is not None:
				#Set minimum & maximum times before a check occurs
				minDays = 20
				maxDays = 90
				
				#Set weighted formula for priority purposes (older gets checked less, newer sooner)
				checkWeight = minDays * (localEntries / currentData['id'])
				if checkWeight > maxDays:
					checkWeight = maxDays
				
				sinceLast = abs(datetime.strptime(currentData['updated'], timeFormat) - checkTime).days
				
				if sinceLast < checkWeight:
					continue
			
			# Update entry
			
			updateById(currentData['type'], currentData['id'])
		
		log('MAINTENANCE COMPLETE')
	except Exception as e:
		log('ERROR: ' + str(e))

def maintainNew(listType):
	log('BEGIN MAINTAINING NEW')
	
	errorCount = 0
	
	c.execute(f'''
		SELECT id, name
		FROM data
		WHERE type="{listType}"
		ORDER BY id DESC
	''')
	
	entries = c.fetchall()
	
	# work down from newest 404 until find valid entry
	for row in entries:
		if row[1] == '_404_':
			continue
		else:
			id = row[0]
			break
	
	try:
		while True:
			if errorCount >= 50:
				log('Max 404 streak reached, stopping search.')
				break
			
			id += 1
			
			# Update entry and set variable containing data
			
			data = updateById(listType, id)
			
			# Count errors
			if data.get('error') == '404':
				errorCount += 1
			
			else:
				errorCount = 0
		
		log('MAINTENANCE COMPLETE')
	except Exception as e:
		log('ERROR: ' + str(e))

# Commands

if __name__ == '__main__':
	listTypes = ('anime', 'manga')
	
	for listType in listTypes:
		#build(listType)
		maintainNew(listType)
		maintainOld(listType)

# Close connection

conn.close()