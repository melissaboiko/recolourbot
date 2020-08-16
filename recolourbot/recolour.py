#!/usr/bin/env python3
import json
import requests
import tempfile
from PIL import Image
from recolourbot import config

# via https://www.codedrome.com/more-image-manipulations-in-python-with-pillow/
def desaturate(openfilepath, savefilepath):
    """Converts image files to b&w using PIL."""

    image = Image.open(openfilepath)
    image = image.convert("L")
    image.save(savefilepath)

def deepai_recolour(imgfile):
    """imgfile: file-like; returns DeepAI URL to recoloured image."""

    r = requests.post(
        "https://api.deepai.org/api/colorizer",
        files={
            'image': imgfile,
        },
        headers={'api-key': config.deepai_api_key},
    )
    j = r.json()
    return j['output_url']

def recolour(imgfilepath, outfilepath):
    """
imgfilepath: filesystem path to image file (with extension!).
outfilepath: where to save the recoloured image.
    """

    extension = '.' + imgfilepath.split('.')[-1]
    with tempfile.NamedTemporaryFile(suffix=extension) as tmp:
        bw = desaturate(imgfilepath, tmp.name)
        tmp.seek(0)
        recoloured_url = deepai_recolour(tmp)

    with requests.get(recoloured_url) as response:
        # ct = response.headers['Content-type']
        with open(outfilepath, 'wb') as outf:
            outf.write(response.content)
