import requests
import sys
from tempfile import NamedTemporaryFile
from pprint import pprint, pformat
from textwrap import indent

from recolourbot import config, mastoapi
from recolourbot.recolour import recolour

log = config.log

def images_in(status):
    """Returns list of media dicts that are images, or empty list if none."""
    if 'media_attachments' not in status:
        return []
    else:
        return [attach for attach in status['media_attachments']
                if attach['type'] == 'image']

def fetch_image(url, suffix='jpeg'):
    """Returns NamedTemporaryFile."""
    log.info("Fetching image at <%s>…", url)
    with requests.get(url) as response:
        f = NamedTemporaryFile(suffix=suffix)
        f.write(response.content)
        f.seek(0)
        log.debug("Saved to %s .", f.name)
        return f

def upload_recolour_of(mastoapi, imagedict, authoracct):
    """Recolours image and uploads it.

    Fetches image locally, recolours it, uploads, and returns the imagedict of
    the uploaded recolour.

    Keeps the extension, description, focus from the original imagedict.

    authoracct: account to credit for image as string.

    """

    log.info('Will recolour image %s from %s and upload.', imagedict['id'], authoracct)
    log.debug('Image dict:\n%s', indent(pformat(imagedict), prefix='  '))

    if 'description' in imagedict and imagedict['description']:
        orig_desc = imagedict['description']
        log.debug('Setting description from original.')
    else:
        orig_desc = '(None provided).'
        log.debug('Couldn’t find description in original.')

    description = \
"""Automatically recoloured version of image originally posted by %s.
Original description:

%s

Recoloured by DeepAI Image Colorization PAI, via %s.""" \
    % (authoracct, orig_desc, config.acct)

    if 'meta' in imagedict and 'focus' in imagedict['meta']:
        focus = (imagedict['meta']['focus']['x'],
                 imagedict['meta']['focus']['y'])
        log.debug('Setting focus from original: %s', focus)
    else:
        focus=None
        log.debug('Couldn’t find focus.')

    origurl = imagedict['url'] or imagedict['remote_url']
    # content_type = ???
    # are Mastodon images always jpg?
    path_components = origurl.split('/')
    file_components = path_components[-1].split('.')
    if len(file_components) > 1:
        suffix = '.' + file_components[-1].split('?')[0]
        log.debug('Got suffix %s from url <%s>.', suffix, origurl)
    else:
        # Is this always the case?
        suffix = '.jpeg'
        log.debug('Got no suffix from url <%s>; forcing jpeg.', origurl)

    origf = fetch_image(origurl, suffix)

    with NamedTemporaryFile(suffix=suffix) as recolourf:
        log.debug('Recolouring image to file %s…', recolourf.name)
        recolour(origf.name, recolourf.name)
        recolourf.seek(0)

        log.info('Recoloured image OK, uploading to masto…')
        newimagedict = mastoapi.media_post(recolourf.name,
                                           description=description,
                                           focus=focus)
        log.info('Upload OK.')
        return newimagedict

def handle_mention(mastoapi, notidict):
    """notidict: a notification dict with type 'mention'.

    Returns new status on success, None if the mention was ignored."""

    log.info('Handling notification %s.', notidict['id'])
    log.debug('%s', indent(pformat(notidict), '  '))

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
        log.info('Found mention directly in image toot, proceeding.')
        target_status = status
    elif 'in_reply_to_id' in status and status['in_reply_to_id']:
        parent = mastoapi.status(status['in_reply_to_id'])
        images = images_in(parent)

        if images:
            if parent['account']['id'] == status['account']['id']:
                log.info('Found mention in parent toot, proceeding.')
                target_status = parent
            else:
                log.info('Parent toot from different user; refusing.')
                refusal_reason = "Sorry, I only recolour images when the original tooter asks for it!"

    if not(target_status):
        if refusal_reason:
            log.info('Will toot refusal reply…')
            mastoapi.status_reply(status, refusal_reason)
            log.info('OK.')

        log.info('Nothing to do, dimissing notification…')
        mastoapi.notifications_dismiss(notidict)
        return None

    new_imagedicts = []

    log.info('Will recolour %d images.', len(images))
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

    log.info('Will post reply with the new images…')
    log.debug('Args:\n%s', indent(pformat((status, new_imagedicts, visibility, extraargs)),
                                  '  '))
    newtoot = mastoapi.status_reply(status, "Recoloured :)",
                                    media_ids=new_imagedicts,
                                    untag=True,
                                    visibility=visibility,
                                    **extraargs
    )
    log.debug('All OK, will dismiss notification.')
    mastoapi.notifications_dismiss(notidict)
    return newtoot

def check_notifications():
    with mastoapi() as masto:
        log.info('Fetching notifications...')
        # not implemented: exclude_types=['follow','favourite','reblog','poll','follow_request']
        notifications = masto.notifications()
        log.debug('Found %d.', len(notifications))

        mentions = [n for n in notifications if n['type'] == 'mention']
        if not mentions:
            log.info('No mentions, nothing to do.')
        else:
            log.info('Mentions to process: %d', len(mentions))
            for mention in mentions:
                handle_mention(masto, mention)
