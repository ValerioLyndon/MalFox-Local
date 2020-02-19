import sqlite3
import os

# Begin Connection

conn = sqlite3.connect('../database/covers.db')
c = conn.cursor()

# Create directory if not exist

subdir = 'reference_lists'

if subdir not in os.listdir():
	os.mkdir(subdir)

# Write to file

def createLocal(listType):
	presets = {
		'dataimagelink': '.data.image a[href^="/{type}/{id}/"]{{background-image:url({image})}}\n',
		
		'dataimagelinkbefore': '.data.image a[href^="/{type}/{id}/"]:before{{background-image:url({image})}}\n',
		
		'dataimagelinkafter': '.data.image a[href^="/{type}/{id}/"]:after{{background-image:url({image})}}\n',
		
		'datatitlelink': '.data.title>a[href^="/{type}/{id}/"]{{background-image:url({image})}}\n',
		
		'datatitlelinkbefore': '.data.title>a[href^="/{type}/{id}/"]:before{{background-image:url({image})}}\n',
		
		'datatitlelinkafter': '.data.title>a[href^="/{type}/{id}/"]:after{{background-image:url({image})}}\n',
		
		'animetitle': '.animetitle[href^="/{type}/{id}/"]{{background-image:url({image})}}\n',
		
		'animetitlebefore': '.animetitle[href^="/{type}/{id}/"]:before{{background-image:url({image})}}\n',
		
		'animetitleafter': '.animetitle[href^="/{type}/{id}/"]:after{{background-image:url({image})}}\n',
		
		'more': '#more{id}{{background-image:url({image})}}\n'
	}
	
	c.execute('''
		SELECT id, name, image
		FROM data
		WHERE type="%s"
		ORDER BY id ASC
	''' % listType)
	database = c.fetchall()
	
	for preset in presets:
		fileName = subdir + '/%slist_%s.css' % (listType, preset)
		file = open(fileName,"w+")
		
		for item in database:
			id = item[0]
			name = item[1]
			image = item[2]
			
			#Skip 404
			if name == '_404_' or image == '_404_':
				continue
			
			#Set Image to placeholder if not valid URL
			if 'cdn.myanimelist.net' not in image:
				image = 'https://cdn.myanimelist.net/r/96x136/images/qm_50.gif?s=3f32c5b34005de86599954f2656b9482'
			
			#Begin Writing
			cssLine = presets[preset].format(type = listType, id = id, image = image)
			file.write(cssLine)
		
		#End
		file.close()
		print('Created %s' % preset)

createLocal('anime')
createLocal('manga')

#Close Connection
conn.close()