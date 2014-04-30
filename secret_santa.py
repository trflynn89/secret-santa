from copy import deepcopy
from datetime import datetime
from os import path
from random import choice
from random import random
from re import match
from smtplib import SMTP
from socket import gethostname
from sys import argv
from time import time
from yaml import load

REQRD = (
	'SMTP_SERVER',
	'SMTP_PORT',
	'USERNAME',
	'PASSWORD',
	'PARTICIPANTS',
	'DONT-PAIR',
	'FORCE-PAIR',
	'FROM',
	'SUBJECT',
	'MESSAGE'
)

HEADER = """Date: {date}
Content-Type: text/plain; charset="utf-8"
Message-Id: {message_id}
From: {frm}
To: {to}
Subject: {subject}

"""

CONFIG_PATH = path.join(path.dirname(__file__), 'config.yml')

MAX_TRIES = 100

# Class to store a person's name and email
class Person:
	def __init__(self, name, email, invalidMatches):
		self.name = name
		self.email = email
		self.invalidMatches = invalidMatches
	
	def __str__(self):
		return '%s <%s>' % (self.name, self.email)

	def SendEmail(self, server, config, receiver):
		date = datetime.now().strftime('%a, %d %b %Y %I:%M%p')
		message_id = '<%s@%s>' % (str(time()) + str(random()), gethostname())

		to = self.email
		frm = config['FROM']
		subject = config['SUBJECT'].format(santa=self.name, santee=receiver)

		body = (HEADER + config['MESSAGE']).format(
			date=date, 
			message_id=message_id, 
			frm=frm, 
			to=to, 
			subject=subject,
			santa=self.name,
			santee=receiver,
		)

		server.sendmail(frm, [to], body)

# Simple class to store a pair of Person
class Pair:
	def __init__(self, giver, receiver):
		self.giver = giver
		self.receiver = receiver
	
	def __str__(self):
		return '%s ---> %s' % (self.giver.name, self.receiver.name)

	# Honor system!
	def shouldPrintReceiver(self):
		if self.receiver.name == 'Ted':
			return False
		if self.receiver.name == 'Ty':
			return False
		if self.receiver.name == 'Wendell':
			return False
		return True

# Parse the YAML config
def parseYaml(yamlPath):
	config = load(open(yamlPath)) 

	for key in REQRD:
		if key not in config.keys():
			raise Exception('Required parameter %s not in yaml config file!' % (key))

	return config

# Choose a receiver for a person after removing invalid matches and ourself
# from the list of receivers
def chooseReceiver(giver, receivers):
	receivers = [r for r in receivers if r.name not in giver.invalidMatches]
	receivers = [r for r in receivers if r.name != giver.name]

	return None if (len(receivers) == 0) else choice(receivers)

# Iterate thru the list of people and randomly create pairs. Return None if the
# random choices led to an impossible list of pairings.
def createPairs(people):
	receivers = deepcopy(people)
	pairs = []

	for giver in people:
		receiver = chooseReceiver(giver, receivers)

		if receiver is not None:
			receivers.remove(receiver)
			pairs.append(Pair(giver, receiver))
		else:
			return None

	return pairs

# Extract name from string of the form "Name <Email@example.com>"
def extractName(str):
	expr = r'([^<]*)<([^>]*)>'
	return match(expr, str).group(1).strip()

# Extract email from string of the form "Name <Email@example.com>"
def extractEmail(str):
	expr = r'([^<]*)<([^>]*)>'
	return match(expr, str).group(2).strip()

# Find a set of valid pairings, or None if one could not be found in NUM_TRIES
def findPairs(config):
	participants = config['PARTICIPANTS']
	if len(participants) < 2:
		raise Exception('Not enough participants specified.')

	people = []
	dontPair = config['DONT-PAIR']
	forcePair = config['FORCE-PAIR']

	for person in participants:
		invalidMatches = []
		name = extractName(person)
		email = extractEmail(person)

		# First, check DONT-PAIR option
		for pair in dontPair:
			names = [n.strip() for n in pair.split(',')]
			invalidMatches.extend([p for p in names if name in names])

		# Next, check FORCE-PAIR option - add everyone except the forcibly
		# paired person to the invalidMatches list
		for pair in forcePair:
			names = [n.strip() for n in pair.split(',')]

			if name == names[0]:
				invalidMatches = [extractName(p) for p in participants]
				invalidMatches = [n for n in invalidMatches if n not in names]
				break

		# Append to list of people
		people.append(Person(name, email, invalidMatches))
	
	# Try MAX_TRIES times to create the pairings
	for n in range(MAX_TRIES):
		pairs = createPairs(people)

		if pairs is not None:
			print 'Pairings:\n\n%s\n' % ('\n'.join([str(p) for p in pairs if p.shouldPrintReceiver()]))
			break

	return pairs

# Main loop
def main():
	config = parseYaml(CONFIG_PATH)
	send = '-s' in argv[1 : ]

	pairs = findPairs(config)

	# Print the pairings and send emails
	if pairs is not None:
		ok = False
		while not ok:
			ok = (raw_input('Is this okay? [y/n] ') == 'y')

			if not ok:
				findPairs(config)

		if send:
			server = SMTP(config['SMTP_SERVER'], config['SMTP_PORT'])
			server.starttls()
			server.login(config['USERNAME'], config['PASSWORD'])

			for pair in pairs:
				pair.giver.SendEmail(server, config, pair.receiver.name)
				print 'Emailed %s' % str(pair.giver)

			server.quit()

	else:
		print 'Could not find a valid pairings list in %d tries, please check your config' % MAX_TRIES

if __name__ == '__main__':
	main()
	
