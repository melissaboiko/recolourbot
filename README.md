A recolourbot
=============

Mastodon bot that fetches images from a toot, converts them to black-and-white,
recolours them using DeepAI colorising service, and replies to the toot with the
recoloured version.  Sometimes you get a new outfit, though often it’s “same but
in neutral colours”.

Interacting
===========

Just @ the bot, either in the same toot when uploading the photos, or in a reply
immediately below (recolourbot will only listen to requests from the same owner
as the parent toot.)

Running
=======

 - Install dependencies:

    sudo apt install python3-pil
    sudo pip3 install Mastodon.py

 - Create an account for the bot in a bot-friendly instance (or your own). Make
   sure to fill in a nice description and your contact account.
 - Create an account in DeepAI and get your API key.
 - Copy config.yaml.example to config.yaml and edit the fields.
 - Run bin/check to test. If it works, run it on cron.

Caveats
=======

This is very raw, beta, untested etc.
