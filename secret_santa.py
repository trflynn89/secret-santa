"""
Secret Santa made easy! Copy config.yml.template to config.yml and fill out the
options. Run this program to create random Secret Santa assignments and to
email participants their assignments.

Examples
--------
Create assignments, but don't send emails (useful for debugging configuration):

    python secret_santa.py

Create assignments and send emails:

    python secret_santa.py -s
"""
import argparse
import copy
import datetime
import getpass
import random
import re
import smtplib
import socket
import time
import yaml

def repeat_if_failed(tries, exceptions):
    """
    Decorator to repeat a function up to a maxiumum number of tries until it
    succeeds (i.e. does not throw an exception). If the maximum attempts are
    exceeded, re-raise the last exception.

    Paramaters
    ----------
    tries : int
        Maximum number of attempts to make the function call.
    exceptions : tuple of Exception
        Tuple of exception classes that are acceptable to be thrown.
    """
    def outer_wrapper(func):
        def inner_wrapper(*args, **kwargs):
            for _ in range(tries):
                try:
                    return func(*args, **kwargs)
                except exceptions as ex:
                    pass

            raise ex

        return inner_wrapper
    return outer_wrapper

class SecretSantaException(Exception):
    """
    Base exception class for this module.
    """
    pass

class SecretSanta(object):
    """
    Class to represent a kindly Secret Santa. Used to create a Secret Santa
    assignment for this Santa and to notify the Santa via email.

    Attributes
    ----------
    name : str
        Name of this Santa.
    email : str
        Email address for this Santa.
    invalid_matches : list of str
        List of names that should not be assigned to this Santa.
    santee : SecretSanta
        The luckly recipient of this Santa's gift.

    Parameters
    ----------
    name : str
        Name of this Santa.
    email : str
        Email address for this Santa.
    invalid_matches : list of str
        List of names that should not be assigned to this Santa.
    """
    def __init__(self, name, email, invalid_matches):
        self.name = name
        self.email = email
        self.invalid_matches = invalid_matches + [self.name]
        self.santee = None

    def __str__(self):
        return '%s ---> %s' % (self.name, self.santee.name if self.santee else str())

    def assign_santee(self, santees):
        """
        Create a random assignment for this Santa from the given list of people,
        excluding this Santa's invalid matches.

        Parameters
        ----------
        santees : list of Santa
            List of candidate assignments.
        """
        candidates = [s for s in santees if s.name not in self.invalid_matches]
        self.santee = random.choice(candidates) if candidates else None

    def send_email(self, session, config):
        """
        Send this Santa an email with their assignment.

        Parameters
        ----------
        session : smtplib.SMTP
            SMTP session to send the email over.
        config : Config
            Secret Santa configuration.
        """
        date = datetime.datetime.now().strftime('%a, %d %b %Y %I:%M%p')
        message_id = '<%f%f@%s>' % (time.time(), random.random(), socket.gethostname())

        sender = config['FROM']
        receiver = self.email
        subject = config['SUBJECT'].format(santa=self.name, santee=self.santee.name)

        body = (Config.EMAIL_HEADER + config['MESSAGE']).format(
            sender=sender,
            receiver=receiver,
            date=date,
            message_id=message_id,
            subject=subject,
            santa=self.name,
            santee=self.santee.name,
        )

        session.sendmail(sender, [receiver], body)

class Config(dict):
    """
    Dictionary-like configuration class to parse the Secret Santa YAML config
    file and store/parse its contents.

    Attributes
    ----------
    config : dict
        Dictionary of parsed configuration key/value mappings.

    Parameters
    ----------
    yaml_path : str
        Path to the YAML configuration file.

    Raises
    ------
    SecretSantaException
        - The YAML config file does not contain all required configs.
        - The YAML config file contains an invalid config.
    """
    REQUIRED_CONFIGS = [
        'SMTP_SERVER',
        'SMTP_PORT',
        'USERNAME',
        'PARTICIPANTS',
        'FROM',
        'SUBJECT',
        'MESSAGE'
    ]

    OPTIONAL_CONFIGS = {
        'PASSWORD' : getpass.getpass,
        'DONT_PAIR' : list
    }

    EMAIL_HEADER = (
        'Date: {date}\n'
        'Content-Type: text/plain; charset="utf-8"\n'
        'Message-Id: {message_id}\n'
        'From: {sender}\n'
        'To: {receiver}\n'
        'Subject: {subject}\n'
        '\n'
    )

    NAME_AND_EMAIL_REGEX = re.compile(r'([^<]*)<([^>]*)>')

    def __init__(self, yaml_path):
        with open(yaml_path, 'r') as yaml_file:
            self.config = yaml.safe_load(yaml_file)

        # Check config requirements
        if not all([r in self.config for r in Config.REQUIRED_CONFIGS]):
            raise SecretSantaException('Did not find all required configs')

        elif len(self.config['PARTICIPANTS']) < 2:
            raise SecretSantaException('Not enough participants specified')

        # Check config optionals
        for (key, default) in Config.OPTIONAL_CONFIGS.iteritems():
            if key not in self.config:
                self.config[key] = default()

    def __getitem__(self, key):
        return self.config[key]

    def __contains__(self, key):
        return key in self.config

    def parse_name_and_email(self, name_and_email):
        """
        Extract the name and email from a string of the form
        'name <email@server.com>'.

        Parameters
        ----------
        name_and_email : str
            String containing the name and email to extract.

        Returns
        -------
        tuple
            A tuple of the form (name : str, email : str).

        Raises
        ------
        SecretSantaException
            - If the input string could not be parsed.
        """
        match = Config.NAME_AND_EMAIL_REGEX.match(name_and_email)

        if match:
            return (match.group(1).strip(), match.group(2).strip())

        raise SecretSantaException('Could not parse name/email: %s' % (name_and_email))

@repeat_if_failed(tries=100, exceptions=(SecretSantaException, ))
def assign_santees(santas):
    """
    Iterate through each Santa and create random assignments for each Santa.

    Parameters
    ----------
    santas : list of Santa
        List of Santas to create assignments for.

    Raises
    ------
    SecretSantaException
        - Not all Santas could be given an assignment.
    """
    santees = copy.deepcopy(santas)

    for santa in santas:
        santa.assign_santee(santees)

        if not santa.santee:
            raise SecretSantaException('Could not find santee for %s' % (santa.name))

        santees.remove(santa.santee)

def create_santas(config):
    """
    Create a valid set of Santas and create their random assignments.

    Parameters
    ----------
    config : Config
        Secret Santa configuration.

    Returns
    ----------
    list of Santa
        List of created Santas.
    """
    santas = list()

    participants = config['PARTICIPANTS']
    dont_pair = config['DONT_PAIR']

    for person in participants:
        (name, email) = config.parse_name_and_email(person)
        invalid_matches = list()

        for pair in dont_pair:
            names = [n.strip() for n in pair.split(',')]
            invalid_matches.extend([p for p in names if name in names])

        santas.append(SecretSanta(name, email, invalid_matches))

    assign_santees(santas)
    return santas

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)

    parser.add_argument(
        '-s', '--send-emails', action='store_true',
        help='If set, send emails to all participants. Exclude for debugging.')
    parser.add_argument(
        '-c', '--config-path', default='config.yml',
        help='Path to the YAML configuration file.')

    args = parser.parse_args()
    config = Config(args.config_path)

    while True:
        santas = create_santas(config)

        print '\n%s\n' % ('\n'.join([str(s) for s in santas]))

        if raw_input('Is this okay? [y/n]: ') == 'y':
            break

    if args.send_emails:
        try:
            session = smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT'])
            session.starttls()
            session.login(config['USERNAME'], config['PASSWORD'])

            for santa in santas:
                print 'Emailing %s <%s>' % (santa.name, santa.email)
                santa.send_email(session, config)

        finally:
            session.quit()

if __name__ == '__main__':
    main()
