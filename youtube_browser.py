#Requires: apiclient; oauth2client; httplib2
import httplib2
import os
import sys
import time
import datetime
import csv
import codecs
from operator import itemgetter
from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

#point to authentication info file
CLIENT_SECRETS_FILE = "client_secrets.json"

#youtube configuration
SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

MISSING_CLIENT_SECRET_MESSAGE = "Secret file not found"

CHANNEL_LIST_FILE_NAME = "channel_list.csv"

#Authenticate with youtube and get object to perform actions through
def get_authenticated_service(args):
	
	#Retrieve stored credentials object
	storage = Storage("%s-oauth2.json" % sys.argv[0])
	credentials = storage.get()
	
	#If necessary, flow credentials from secrets file
	if credentials is None or credentials.invalid:
		flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
			scope=SCOPE, message=MISSING_CLIENT_SECRET_MESSAGE)
		credentials = run_flow(flow, storage, args)
		
	return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))
	
def saveChannelList(channel_file, id):
	f = open(channel_file, "w")
	f.write(id)
	f.close()

def loadLastChannel(channel_file):
	with open(channel_file, 'rb') as file:
		channel_reader = csv.reader(file)
		return channel_reader.next()[0]
	
	
#Get first page, return list of channel ids, and recurse through additional pages
#@params:
#youtube: apiclient - youtube api object
#channel_id: string - id of channel to fetch subscriptions for
#sub_list: array - list of subscriptions fetched by prior function calls
#page: string - token of page to fetch on this call
#@retuns:
#array - list of subscriptions
def fetchSubscriptionPage(youtube, channel_id, sub_list, page=None):
	subscription_response = youtube.subscriptions().list(
		part='snippet',
		channelId = channel_id,
		maxResults = 50,
		pageToken = page
	).execute()
	for sub in subscription_response["items"]:
		sub_list.append({"channel_id":sub["snippet"]["resourceId"]["channelId"], "name":sub["snippet"]["title"]})
		
	#Recurse to the next token if there is one.
	if "nextPageToken" in subscription_response:
		sub_list = fetchSubscriptionPage(youtube, channel_id, sub_list, subscription_response["nextPageToken"])
	return sub_list

#Get videos on specified channel
#@params:
#youtube: apiclient - youtube api object
#channel: string - id of channel to fetch videos for
#@retuns:
#array - list of videos on the channel
def getVidsFromChannel(youtube, channel):
	#Find the channel's upload list
	channel_response = youtube.channels().list(
		part='contentDetails',
		id = channel["channel_id"]
	).execute()
	uploads = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
	
	#Get the videos on the upload list
	channel_vids = getVidsFromPlaylist(youtube, uploads, [], channel["name"])
	return channel_vids
	
#Get videos from a specified playlist
#@params:
#youtube: apiclient - youtube api object
#playlist: string - id of playlist to fetch vids from
#vid_list: array - list of videos fetched by prior function calls
#channel_name: name of channel video is on
#page: string - token of page to fetch on this call
#@retuns:
#array - list of videos in playlist
def getVidsFromPlaylist(youtube, playlist, vid_list, channel_name, page=None):
	#Retrieve the playlist
	playlist_response = youtube.playlistItems().list(
		part='snippet',
		playlistId=playlist,
		maxResults = 50,
		pageToken = page
	).execute()
	for vid in playlist_response["items"]:
		vid_list.append({"title":vid["snippet"]["title"], "link":vid["snippet"]["resourceId"]["videoId"], "time":vid["snippet"]["publishedAt"], "channel":channel_name})
		
	#Recurse to the next token if there is one.
	if "nextPageToken" in playlist_response:
		vid_list = getVidsFromPlaylist(youtube, playlist, vid_list, channel_name, playlist_response["nextPageToken"])
	return vid_list
	
#Write list of videos to HTML file
#@params:
#vid_list: List of videos
#@returns:
#null
def writeHTML(vid_list):
	curr_time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H-%M-%S')
	file = codecs.open("Subsciption List %s.html" % (curr_time), 'w', 'utf-8')
	file.write("""<html>
		<body>
		""")
		
	for video in vid_list:
		file.write(u"""<a href="https://www.youtube.com/watch?v=%s" target="_blank">%s - %s</a> %s<br/>""" % (video["link"], video["channel"], video["title"], video["time"]))
		
	file.write("""
		</body>
		</html>
		""")
	file.close

	
if __name__ == "__main__":
	print "Enter channel ID:"
	newname = raw_input()
	
	#Check for shortcut to last channel entered
	if newname == "":
		newname = loadLastChannel(CHANNEL_LIST_FILE_NAME)
	else:
		saveChannelList(CHANNEL_LIST_FILE_NAME, newname)
	
	argparser.add_argument("--channel-id", help="ID of the channel to subscribe to.",
		default=newname)
	args = argparser.parse_args()
	#Make API object
	youtube = get_authenticated_service(args)
	
	try:
		channels = fetchSubscriptionPage(youtube, newname, [])
		video_list = []
		for channel in channels:
			video_list = video_list + getVidsFromChannel(youtube, channel)
	except HttpError, e:
		print "Error %d: %s\n" % (e.resp.status, e.content)
	else:
		#Sort by time stamp
		sorted_list = sorted(video_list, key=itemgetter("time"), reverse=True)
		#Write list to HTML file
		writeHTML(sorted_list)