#VARIABLES

timeFormat = '%Y-%m-%d %H:%M:%S.%f'

#IMPORTS

#Database
import sqlite3

#Time and Functions
from time import sleep
from time import strftime
from datetime import datetime, timezone
import re
import urllib.parse

#Scraper
import requests
import urllib.request
from bs4 import BeautifulSoup

# Functions

#Encoder/Decoder for safe storage of random strings into database.

def encodeString(s):
	return urllib.parse.quote(s)

def decodeString(s):
	return urllib.parse.unquote(s)

# Begin connection

conn = sqlite3.connect('covers.db')
c = conn.cursor()

c.execute('''
	CREATE TABLE if not exists data (
		type TEXT,
		id INT,
		name TEXT,
		image TEXT,
		updated TEXT
	)
''')

# Build Database

def build(listType):
	errorCount = 0
	
	if listType == 'anime':
		#15700
		totalIds = 40000
	elif listType == 'manga':
		#46650
		totalIds = 120000
	else:
		print('Invalid list type, please try again using either "anime" or "manga".')
	
	for id in range(totalIds):
		id += 1
		checkTime = datetime.utcnow()
		
		#Check DB for duplicates
		c.execute(f'''
			SELECT id, name
			FROM data
			WHERE type="{listType}"
			AND id={id}
		''')
		entry = c.fetchone()
		
		#If entry non exist
		if entry is None:
			#Begin Parsing
			url = 'https://myanimelist.net/' + listType + '/' + str(id)
			parsed = BeautifulSoup(requests.get(url).text, 'html.parser')
			
			#404 Check
			errorCheck = parsed.find('img', src=re.compile('^https\://cdn\.myanimelist\.net/images/error/404_image\.png'))
			
			if errorCheck is not None:
				name = '_404_'
				image = '_null_'
				errorCount += 1
			else:
				errorCount = 0
				
				try:
					name = parsed.find('span', itemprop='name').string;
					if name is None:
						name = '_null_'
					else:
						name = encodeString(name)
				except Exception as e:
					name = '_null_'
					print(f'({id}) Error encountered on name: {e}')
				try:
					image = parsed.find('img', itemprop='image').get('src');
					if image is None:
						image = '_null_'
				except Exception as e:
					image = '_null_'
					print(f'({id}) Error encountered on image: {e}')
					
				
				
			#Add to DB
			c.execute(f'''
				INSERT INTO data
				(type, id, name, image, updated)
				VALUES("{listType}", {id}, "{name}", "{image}", "{checkTime}")
			''')
			#conn.commit()
			
			print(f'{strftime("%H:%M:%S")} New entry added ({id}) [404 streak of {errorCount}]')
			
			#Delay checks to prevent spam
			if id != 0 and id != totalIds:
				sleep(6)
		
		#If entry exist
		else:
			if entry[1] == '_404_':
				errorCount += 1
			else:
				errorCount = 0
			
			print(f'{strftime("%H:%M:%S")} Entry found ({id}) [404 streak of {errorCount}]')
# Maintain Database

def maintainOld(listType):
	c.execute(f'''
		SELECT id, name, image, updated
		FROM data
		WHERE type="{listType}"
		AND image!="_null_"
		AND name!="_null_"
		ORDER BY updated ASC
	''')
	
	entries = c.fetchall()
	
	try:
		for entry in entries:
			id = entry[0]
			currentName = entry[1]
			currentImage = entry[2]
			lastUpdated = entry[3]
			checkTime = datetime.utcnow()
			logPrefix = f'{strftime("%H:%M:%S")} {listType[:1]}{str(id).zfill(6)}'
			
			#Skip blanks
			if currentName == '_404_' and currentImage == '_404_':
				continue
			
			#Check Date
			c.execute(f'''
				SELECT id
				FROM data
				WHERE type="{listType}"
				ORDER BY id DESC
			''')
			totalIDs = c.fetchone()[0]
			
			if lastUpdated is not None:
				#Set minimum & maximum times before a check occurs
				minDays = 20
				maxDays = 90
				
				#Set weighted formula for priority purposes (older gets checked less, newer sooner)
				checkWeight = minDays * (totalIDs / id)
				if checkWeight > maxDays:
					checkWeight = maxDays
				
				sinceLast = abs(datetime.strptime(lastUpdated, timeFormat) - checkTime).days
				
				if sinceLast < checkWeight:
					continue
			
			#Begin Parsing
			url = 'https://myanimelist.net/' + listType + '/' + str(id)
			parsed = BeautifulSoup(requests.get(url).text, 'html.parser')
			
			#Check Exist
			miscErrorCheck = parsed.find(id='myanimelist')
			
			if miscErrorCheck is None:
				print(f'{logPrefix} error encountered: Page did not load.')
				sleep(6)
				continue
			
			existCheck = parsed.find('img', src=re.compile('^https\://cdn\.myanimelist\.net/images/error/404_image\.png'))
			
			if existCheck is not None:
				if currentName == '_null_' and currentImage == '_null_':
					c.execute(f'''
						UPDATE data
						SET name="_404_", image="_404_", updated="{checkTime}"
						WHERE type="{listType}"
						AND id={id}
					''')
					
					print(f'{logPrefix} both set as 404')
				elif currentName == '_null_' and currentImage == '_404_':
					c.execute(f'''
						UPDATE data
						SET name="_404_", updated="{checkTime}"
						WHERE type="{listType}"
						AND id={id}
					''')
					
					print(f'{logPrefix} name set as 404')
				elif currentName == '_404_' and currentImage == '_null_':
					c.execute(f'''
						UPDATE data
						SET image="_404_", updated="{checkTime}"
						WHERE type="{listType}"
						AND id={id}
					''')
					
					print(f'{logPrefix} image set as 404')
				else:
					c.execute(f'''
						UPDATE data
						SET updated="{checkTime}"
						WHERE type="{listType}"
						AND id={id}
					''')
					
					print(f'{logPrefix} nothing new')
				#conn.commit()
				sleep(6)
				continue
			
			#Check for New
			try:
				newName = parsed.find('span', itemprop='name').string
				newName = encodeString(newName)
			except Exception as e:
				newName = '_null_'
			
			try:
				newImage = parsed.find('img', itemprop='image').get('data-src')
			except Exception as e:
				newImage = '_null_'
			
			#Update DB if not New
			if newName == '_null_' and newImage == '_null_':
				c.execute(f'''
					UPDATE data
					SET updated="{checkTime}"
					WHERE type="{listType}"
					AND id={id}
				''')
				
				print(f'{logPrefix} null entry')
				
			elif newName == currentName and newImage == currentImage:
				c.execute(f'''
					UPDATE data
					SET updated="{checkTime}"
					WHERE type="{listType}"
					AND id={id}
				''')
				
				print(f'{logPrefix} nothing new')
				
			#Update DB if New
			else:
				updated = []
				
				if newName != '_null_' and newName != currentName:
					c.execute(f'''
						UPDATE data
						SET name="{newName}", updated="{checkTime}"
						WHERE type="{listType}"
						AND id={id}
					''')
					
					updated += ['name']
				
				if newImage != '_null_' and newImage != currentImage:
					c.execute(f'''
						UPDATE data
						SET image="{newImage}", updated="{checkTime}"
						WHERE type="{listType}"
						AND id={id}
					''')
					
					updated += ['image']
					
				updatedStr = ' & '.join([i for i in updated])
				print(f'{logPrefix} {updatedStr} updated')
			
			#conn.commit()
			sleep(6)
		
		print('MAINTENENACE COMPLETE')
	except Exception as e:
		f = open('logs/log.txt', 'w+')
		f.write(e)
		f.close()

def maintainNew(listType):
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
	
	while errorCount < 50:
		id += 1
		checkTime = datetime.utcnow()
		logPrefix = f'{strftime("%H:%M:%S")} {listType[:1]}{str(id).zfill(6)}'
		
		#Begin Parsing
		url = 'https://myanimelist.net/' + listType + '/' + str(id)
		parsed = BeautifulSoup(requests.get(url).text, 'html.parser')
		
		#404 Check
		miscErrorCheck = parsed.find(id='myanimelist')
			
		if miscErrorCheck is None:
			print(f'{logPrefix} error encountered: Page did not load.')
			sleep(6)
			continue
		
		errorCheck = parsed.find('img', src=re.compile('^https\://cdn\.myanimelist\.net/images/error/404_image\.png'))
		
		if errorCheck is not None:
			errorCount += 1
			print(f'{logPrefix} skipped 404 [{errorCount} error streak]')
			sleep(6)
			continue
		else:
			errorCount = 0
			
		#404 Check Passed, continuing
		newCount += 1
		
		try:
			name = parsed.find('span', itemprop='name').string
			name = encodeString(name)
		except Exception as e:
			name = '_null_'
			#print("%s name error: %s" % (logPrefix, e))
		try:
			image = parsed.find('img', itemprop='image').get('data-src')
		except Exception as e:
			image = '_null_'
			#print("%s image error: %s" % (logPrefix, e))
		
		if name == '_null_' and image == '_null_':
			errorCount += 1
			print(f'{logPrefix} skipped null entry [{errorCount} error streak]')
			sleep(6)
			continue
		
		#Check DB for exist
		c.execute(f'''
			SELECT id
			FROM data
			WHERE type="{listType}"
			AND id={id}
		''')
		entry = c.fetchone()
		
		#Insert into DB - If entry not exist
		if entry is None:
			c.execute(f'''
				INSERT INTO data
				(type, id, name, image, updated)
				VALUES("{listType}", {id}, "{name}", "{image}", "{checkTime}")
		''')
		
		#Insert into DB - If entry exist
		else:
			c.execute(f'''
				UPDATE data
				SET name="{name}", image="{image}", updated="{checkTime}"
				WHERE type="{listType}"
				AND id={id}
			''')
		
		#conn.commit()
		print(f'{logPrefix} added new [reset error streak]')
		sleep(6)
	
	print(f'''Ending search...
{newCount} NEW {listType.upper()} ENTRIES ADDED''')

# Commands

#build('anime')
#build('manga')
#maintainNew('anime')
#maintainNew('manga')
maintainOld('anime')
maintainOld('manga')

# Save changes and close connection

#conn.commit()
conn.close()