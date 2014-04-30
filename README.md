Intro
=====

**secret-santa** can help you manage a list of secret santa participants by
randomly assigning pairings and sending emails. It can avoid pairing 
couples to their significant other, and allows custom email messages to be 
specified.

Dependencies
------------

pyyaml

Usage
-----

Copy config.yml.template to config.yml and enter in the connection details 
for your outgoing mail server. Modify the participants and couples lists and 
the email message if you wish.

    cd secret-santa/
    cp config.yml.template config.yml

Once configured, call secret-santa:

    python secret_santa.py

To send the emails, call using the `-s` argument

    python secret_santa.py -s
