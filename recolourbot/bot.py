import requests
import sys
from tempfile import NamedTemporaryFile
from pprint import pprint

from recolourbot import config, mastoapi
from recolourbot.recolour import recolour

def images_in(status):
    """Returns list of media dicts that are images, or empty list if none."""
    if 'media_attachments' not in status:
        return []
    else:
        return [attach for attach in status['media_attachments']
                if attach['type'] == 'image']

def fetch_image(url, suffix='jpeg'):
    """Returns NamedTemporaryFile."""
    with requests.get(url) as response:
        f = NamedTemporaryFile(suffix=suffix)
        f.write(response.content)
        f.seek(0)
        return f

def upload_recolour_of(mastoapi, imagedict, authoracct):
    """Recolours image and uploads it.

    Fetches image locally, recolours it, uploads, and returns the imagedict of
    the uploaded recolour.

    Keeps the extension, description, focus from the original imagedict.

    authoracct: account to credit for image as string.

    """
    global config

    if 'description' in imagedict:
        orig_desc = imagedict['description']
    else:
        orig_desc = '(None provided).'

    description = \
"""Automatically recoloured version of image originally posted by %s.
Original description:

%s

Recoloured by DeepAI Image Colorization PAI, via %s.""" \
    % (authoracct, orig_desc, config.acct)

    if 'meta' in imagedict and 'focus' in imagedict['meta']:
        focus = (imagedict['meta']['focus']['x'],
                 imagedict['meta']['focus']['y'])
    else:
        focus=None

    origurl = imagedict['url'] or imagedict['remote_url']
    # content_type = ???
    # are Mastodon images always jpg?
    path_components = origurl.split('/')
    file_components = path_components[-1].split('.')
    if len(file_components) > 1:
        suffix = '.' + file_components[-1].split('?')[0]

    else:
        # Is this always the case?
        suffix = '.jpeg'

    origf = fetch_image(origurl, suffix)
    with NamedTemporaryFile(suffix=suffix) as recolourf:
        recolour(origf.name, recolourf.name)
        recolourf.seek(0)

        newimagedict = mastoapi.media_post(recolourf.name,
                                           description=description,
                                           focus=focus)
        return newimagedict

def handle_mention(mastoapi, notidict):
    """notidict: a notification dict with type 'mention'.

    Returns new status on success, None if the mention was ignored."""

    status = notidict['status']

    me = [mention for mention in status['mentions']
          if mention['username'] == config.login
          or mention['acct'] in (config.login, config.acct)]
    if not me:
        raise(RuntimeError("Mention notification without mentions? %s" % notidict))

    target_status=None
    refusal_reason = None

    images = images_in(status)
    if images:
        target_status = status
    elif 'in_reply_to_id' in status and status['in_reply_to_id']:
        parent = mastoapi.status(status['in_reply_to_id'])
        images = images_in(parent)

        if images:
            if parent['account']['id'] == status['account']['id']:
                target_status = parent
            else:
                refusal_reason = "Sorry, I only recolour images when the original tooter asks for it!"

    if not(target_status):
        if refusal_reason:
            mastoapi.status_reply(status, refusal_reason)
        print('Dismissing noti...')
        mastoapi.notifications_dismiss(notidict)
        return None

    new_imagedicts = []

    for imagedict in images:
        recoloured = upload_recolour_of(mastoapi,
                                        imagedict,
                                        target_status['account']['acct'])
        new_imagedicts.append(recoloured.id)

    if not 'visibility' in target_status or target_status['visibility'] == 'public':
        visibility = 'unlisted'
    else:
        visibility = target_status['visibility']

    extraargs = {}
    for arg in ('sensitive', 'spoiler_text', 'language'):
        if arg in target_status:
            extraargs[arg] = target_status[arg]

    newtoot = mastoapi.status_reply(status, "Recoloured :)",
                                    media_ids=new_imagedicts,
                                    untag=True,
                                    visibility=visibility,
                                    **extraargs
    )
    mastoapi.notifications_dismiss(notidict)
    return newtoot

def check_notifications():
    with mastoapi() as masto:
        notifications = masto.notifications()
        # not implemented: exclude_types=['follow','favourite','reblog','poll','follow_request']
        for noti in [n for n in notifications if n['type'] == 'mention']:
            print('Handling noti...')
            handle_mention(masto, noti)
