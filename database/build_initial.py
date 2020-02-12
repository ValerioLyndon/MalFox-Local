#Generic
import func

import sqlite3

from time import sleep
from time import strftime
import re

import requests
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup


# Begin connection

conn = sqlite3.connect('covers.db')
c = conn.cursor()

c.execute('CREATE TABLE if not exists anime (id, name, image, updated)')
c.execute('CREATE TABLE if not exists manga (id, name, image, updated)')

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
		c.execute('SELECT id, name from %s WHERE id=%s' % (listType, id))
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
					name = func.encodeString(name)
				except Exception as e:
					name = '_null_'
					print("(%s) Error encountered on name: %s" % (id, e))
				try:
					image = parsed.find('img', itemprop='image').get('src');
				except Exception as e:
					image = '_null_'
					print("(%s) Error encountered on image: %s" % (id, e))
				
			#Add to DB
			c.execute('''INSERT INTO %s VALUES(%s, "%s", "%s", "%s"''' % (listType, id, name, image, checkTime))
			conn.commit()
			
			print('%s New entry added (%s) [404 streak of %s]' % (strftime('%H:%M:%S'), id, errorCount))
			
			#Delay checks to prevent spam
			if id != 0 and id != totalIds:
				sleep(6)
		
		#If entry exist
		else:
			if entry[1] == '_404_':
				errorCount += 1
			else:
				errorCount = 0
			
			print('%s Entry found (%s) [404 streak of %s]' % (strftime('%H:%M:%S'), id, errorCount))

build('anime')
build('manga')

# Tests

#for row in c.execute('SELECT * FROM %s' % listType):
#	print(row)

# Save changes and close connection

conn.commit()
conn.close()