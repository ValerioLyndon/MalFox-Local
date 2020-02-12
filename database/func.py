#VARIABLES



#FUNCTIONS - Generic

#Encoder/Decoder for safe storage of random strings into database.

import urllib.parse

def encodeString(s):
	return urllib.parse.quote(s)

def decodeString(s):
	return urllib.parse.unquote(s)
	
#FUNCTIONS - Database

#Update item

