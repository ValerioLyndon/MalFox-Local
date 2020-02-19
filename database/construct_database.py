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
	print(f'Sent web request - waiting {delay} seconds to avoid spam protection...')
	sleep(delay)
	
	# Check for misc problems (504 errors, page load faults, etc)
	
	malHealth = parsed.find(id='myanimelist')
	
	if malHealth is None:
		data['name'] = '_error_'
		data['image'] = '_error_'
		data['error'] = 'unknown'
		return data
	
	# Check for 404
	
	badLink = parsed.find('img', src=re.compile('^https\://cdn\.myanimelist\.net/images/error/404_image\.png'))
	
	if badLink is not None:
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
		data['image'] = image.get('src')
	
	return data

# Build Database

def build(listType):
	log('BEGIN BUILDING')
	
	totalEntries = estimateEntries(listType)
	
	try:
		for id in range(totalEntries):
			id += 1
			checkTime = datetime.utcnow()
			logPrefix = f'{listType[:1]}{str(id).zfill(6)}'
			
			# Check DB for duplicates
			
			c.execute(f'''
				SELECT id, name
				FROM data
				WHERE type="{listType}"
				AND id={id}
			''')
			entry = c.fetchone()
			
			# If entry not exist
			
			if entry is None:
				newData = parseEntry(listType, id)
					
				#Add to DB
				c.execute(f'''
					INSERT INTO data
					(type, id, name, image, updated)
					VALUES("{newData['type']}", {newData['id']}, "{newData['name']}", "{newData['image']}", "{checkTime}")
				''')
				if not debug: conn.commit()
				
				log(f'{logPrefix} Entry added')
			else:
				log(f'{logPrefix} Already in DB')
	except Exception as e:
		log('ERROR: ' + str(e))

# Maintain Database

def maintainOld(listType):
	log('BEGIN MAINTAINING OLD')
	
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
			logPrefix = f'{listType[:1]}{str(currentData["id"]).zfill(6)}'
			
			#Skip blanks
			if currentData['name'] == '_404_':
				continue
			
			#Check Date
			c.execute(f'''
				SELECT id
				FROM data
				WHERE type="{listType}"
				ORDER BY id DESC
			''')
			totalEntries = c.fetchone()[0]
			
			if currentData['updated'] is not None:
				#Set minimum & maximum times before a check occurs
				minDays = 20
				maxDays = 90
				
				#Set weighted formula for priority purposes (older gets checked less, newer sooner)
				checkWeight = minDays * (totalEntries / currentData['id'])
				if checkWeight > maxDays:
					checkWeight = maxDays
				
				sinceLast = abs(datetime.strptime(currentData['updated'], timeFormat) - checkTime).days
				
				if sinceLast < checkWeight:
					continue
			
			newData = parseEntry(currentData['type'], currentData['id'])
			
			# Handle errors
			
			if 'error' in newData:
				# 404
				if newData['error'] == '404':
					c.execute(f'''
						UPDATE data
						SET updated="{checkTime}"
						WHERE type="{currentData['type']}"
						AND id={currentData['id']}
					''')
					
					log(f'{logPrefix} 404 entry')
					if not debug: conn.commit()
					continue
				
				# Generic
				elif newData['error'] is not None:
					log(f'{logPrefix} error: {newData["error"]}')
			
			# Update DB with new Data
			
			if newData['name'] == '_null_' and newData['image'] == '_null_':
				c.execute(f'''
					UPDATE data
					SET updated="{checkTime}"
					WHERE type="{currentData['type']}"
					AND id={currentData['id']}
				''')
				
				log(f'{logPrefix} null entry')
				
			elif newData['name'] == currentData['name'] and newData['image'] == currentData['image']:
				c.execute(f'''
					UPDATE data
					SET updated="{checkTime}"
					WHERE type="{currentData['type']}"
					AND id={currentData['id']}
				''')
				
				log(f'{logPrefix} nothing new')
			
			else:
				updated = []
				
				if newData['name'] != '_null_' and newData['name'] != currentData['name']:
					c.execute(f'''
						UPDATE data
						SET name="{newData['name']}", updated="{checkTime}"
						WHERE type="{currentData['type']}"
						AND id={currentData['id']}
					''')
					
					updated += ['name']
				
				if newData['image'] != '_null_' and newData['image'] != currentData['image']:
					c.execute(f'''
						UPDATE data
						SET image="{newData['image']}", updated="{checkTime}"
						WHERE type="{currentData['type']}"
						AND id={currentData['id']}
					''')
					
					updated += ['image']
					
				if len(updated) > 0:
					updatedStr = ' & '.join(updated)
					log(f'{logPrefix} {updatedStr} updated')
				else:
					log(f'{logPrefix} nothing updated')
			
			if not debug: conn.commit()
		
		log('MAINTENANCE COMPLETE')
	except Exception as e:
		log('ERROR: ' + str(e))

def maintainNew(listType):
	log('BEGIN MAINTAINING NEW')
	
	errorCount = 0
	newCount = 0
	
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
		while errorCount < 50:
			id += 1
			checkTime = datetime.utcnow()
			logPrefix = f'{listType[:1]}{str(id).zfill(6)}'
			
			newData = parseEntry(listType, str(id))
			
			# Handle errors
			
			if 'error' in newData:
				# 404
				if newData['error'] == '404':
					errorCount += 1
					logSuffix = f'- 404 [{errorCount} streak]'
				
				# Generic
				elif newData['error'] is not None:
					logSuffix = '- generic error [streak maintained]'
			
			else:
				errorCount = 0
				logSuffix = '[reset error streak]'
				
			# Error Check Passed, continuing
			
			newCount += 1
			
			if newData['name'] == '_null_' and newData['image'] == '_null_':
				errorCount = 0
				log(f'{logPrefix} skipped null entry [{errorCount} error streak]')
			
			#Check DB for exist
			c.execute(f'''
				SELECT id
				FROM data
				WHERE type="{newData['type']}"
				AND id={newData['id']}
			''')
			entry = c.fetchone()
			
			#Insert into DB - If entry not exist
			if entry is None:
				c.execute(f'''
					INSERT INTO data
					(type, id, name, image, updated)
					VALUES("{newData['type']}", {newData['id']}, "{newData['name']}", "{newData['image']}", "{checkTime}")
				''')
			
			#Insert into DB - If entry exist
			else:
				c.execute(f'''
					UPDATE data
					SET name="{newData['name']}", image="{newData['image']}", updated="{checkTime}"
					WHERE type="{newData['type']}"
					AND id={newData['id']}
				''')
			
			if not debug: conn.commit()
			log(f'{logPrefix} added new {logSuffix}')
		
		log(f'''Ending search...
{newCount} NEW {listType.upper()} ENTRIES ADDED''')
	except Exception as e:
		log('ERROR: ' + str(e))

# Commands

listTypes = ('anime', 'manga')

for listType in listTypes:
	build(listType)
	maintainOld(listType)
	maintainNew(listType)

# Save changes and close connection

if not debug: conn.commit()
conn.close()