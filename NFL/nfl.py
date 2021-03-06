#!/usr/bin/python

import unirest
from bs4 import BeautifulSoup
import re
import quarterback, runningback, widereceiver
import sys, os
from multiprocessing.dummy import Process, Queue
import time
from datetime import datetime
import csv
import json

RUNDAY = datetime.utcnow().date().isoformat()
BASE_URL = 'http://espn.go.com/nfl/team/roster/_/name/'
TEAM_CODES = {}
PLAYERS = []

def load_codes():
	global TEAM_CODES
	print 'Loading team names...'
	file = open('nfl_teams.txt', 'r+')
	for line in file:
		line = line.strip('\n').split('|')
		TEAM_CODES[line[0]] = line[1]
	file.close()

def get_rosters_from_file(rosters_outfile):
	global PLAYERS
	print 'Loading rosters from file...'
	json_data = open(rosters_outfile, 'r+')
	PLAYERS = json.loads(json_data.read())
	json_data.close()
	print 'Finished loading rosters from file...'

def get_rosters_from_url(rosters_outfile):
	global PLAYERS, TEAM_CODES
	for team, code in TEAM_CODES.iteritems():
		print 'Fetching roster for %s...' % team
		url = BASE_URL+code
		try:		
			result = unirest.get(url).body
		except Exception as e:
			print 'ERROR: could not access %s' % url
			continue
		soup = BeautifulSoup(result)
		results = soup.find_all('tr', {'class': 'evenrow'}) + soup.find_all('tr', {'class': 'oddrow'})
		for result in results:
			player = {}
			temp = result.contents
			player['SPORT'] = 'NFL'
			player['TEAM'] = team
			player['JERSEY'] = temp[0].contents[0].encode('utf-8')
			player['URL'] = temp[1].contents[0]['href']
			player['POSITION'] = temp[2].contents[0].encode('utf-8')
			player['SUCCESS'] = False
			player['COUNT'] = 0
			PLAYERS.append(player)
	print 'Finished fetching rosters.'
	print 'Saving rosters to file...'
	json_data = open(rosters_outfile, 'w+')
	json_data.write(json.dumps(PLAYERS))
	json_data.close()
	print 'Finished saving rosters to file.'

def get_rosters():
	rosters_outfile = RUNDAY+'_nfl_rosters.json'
	if os.path.isfile(rosters_outfile):
		get_rosters_from_file(rosters_outfile)
	else:
		get_rosters_from_url(rosters_outfile)

def queue_players(in_queue):
	global PLAYERS
	for player in PLAYERS:
		in_queue.put(player)	

def get_stats_helper(in_queue, out_queue):
	global PLAYERS
	if in_queue.empty():
		return
	player = in_queue.get()
	player['COUNT'] += 1
	if player['POSITION'] == 'QB' or player['POSITION'] == 'RB' or player['POSITION'] == 'WR':
		if player['POSITION'] == 'QB':
			player = quarterback.get_stats(player)
		elif player['POSITION'] == 'RB':
			player = runningback.get_stats(player)
		elif player['POSITION'] == 'WR':
			player = widereceiver.get_stats(player)

		if player['SUCCESS'] == True:
			out_queue.put(player)
		elif player['COUNT'] > 5:
			print 'ERROR: Made more than 5 attempts to get data for %s' % player['URL']
		else:
			in_queue.put(player)

def get_stats():
	print 'Fetching NFL player stats...'
	stats_outfile = RUNDAY+'_nfl_stats.csv'
	csvout = open(stats_outfile, 'wb')

	NUM_THREADS = 8

	in_queue = Queue()
	out_queue = Queue()
	queue_players(in_queue)

	while not in_queue.empty():	
		jobs = []

		for i in range(NUM_THREADS):
			if not in_queue.empty():
				thread = Process(target=get_stats_helper, args=(in_queue, out_queue))
				jobs.append(thread)
				thread.start()
		for thread in jobs:
			thread.join()	

		while not out_queue.empty():
			player = out_queue.get()
			del player['SUCCESS']
			del player['COUNT']
			try: 
				name = player['NAME']
			except KeyError as e:
				continue
			player['TIME'] = RUNDAY
			fieldnames = [
				'TIME',
				'NAME', 
				'JERSEY',
				'SPORT',
				'TEAM',
				'POSITION',
				'TD',
				'YDS',
				'URL'
			]
		
			csvwriter = csv.DictWriter(csvout, delimiter='|', fieldnames=fieldnames)
			csvwriter.writerow(player)
	csvout.close()

	print 'Finished fetching NFL player stats.'
	print 'Ouput saved in %s' % stats_outfile

def print_players():
	global PLAYERS
	for player in PLAYERS:
		print player
	
def main():
	load_codes()
	get_rosters()
	get_stats()
	#print_players()

if __name__=='__main__':
	main()
	
