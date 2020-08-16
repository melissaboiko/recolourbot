import yaml
import logging
import logging.handlers
from os import path, makedirs
from contextlib import contextmanager
from mastodon import Mastodon

class Config:
    """Populated from config.yaml.  Methods work as dictionary keys (like ruby openstruct).

    >>> config = Config()
    >>> '@' in config.email
    True
    # config.login is always the first component of config.account
    >>> config.acct.index(config.login + '@')
    0
    """

    def __init__(self):
        # parent of this script
        self.basedir = path.abspath(
            path.join(path.abspath(path.dirname(__file__)),
                      '..')
        )

        with open(path.join(self.basedir, 'config.yaml'), 'rt') as configfile:
            y = yaml.safe_load(configfile)
            for key, val in y.items():
                setattr(self, key, val)

        self.log = logging.getLogger('recolourbot')
        self.log.setLevel(getattr(logging, self.loglevel.upper()))
        # Linux-specific
        handler = logging.handlers.SysLogHandler(address = '/dev/log')
        handler.setFormatter(logging.Formatter(
            fmt="%(name)s: %(levelname)s: %(message)s"
        ))
        self.log.addHandler(handler)
        self.log.debug('Read conffile and set up logging.')

        self.login = self.acct.split('@')[0]

        self.client_cred = path.abspath(path.join(self.basedir, self.client_cred))
        self.login_cred = path.abspath(path.join(self.basedir, self.login_cred))

        for d in (path.dirname(self.client_cred), path.dirname(self.login_cred)):
            if d and not path.isdir(d):
                self.log.info('mkdir %s for credentials', d)
                makedirs(d)

        if not path.isfile(self.client_cred):
            self.log.info('Registering app…')
            self.__createapp()
        if not path.isfile(self.login_cred):
            self.log.info('Logging in…')
            self.__login()

    def __createapp(self):
        '''Needed once, then persist in client_cred.'''
        Mastodon.create_app(
            self.appname,
            api_base_url = self.base_url,
            to_file = self.client_cred,
        )

    def __login(self):
        '''Needed once, then persist in login_cred.'''
        masto = Mastodon(
            client_id = self.client_cred,
            api_base_url = self.base_url,
        )
        masto.log_in(
            username=self.email,
            password=self.password,
            to_file=self.login_cred,
        )

config = Config()

@contextmanager
def mastoapi(*args, **kwds):
    """Wrapper over Mastodon() for with-statements:

    >>> with mastoapi() as masto:
    ...     me = masto.account_verify_credentials()
    ...     me['username'] == config.login
    True
    """

    if 'access_token' not in kwds:
        kwds['access_token'] = config.login_cred
    if 'api_base_url' not in kwds:
        kwds['api_base_url'] = config.base_url

    config.log.info("Opening Mastodon API session…")
    config.log.debug("login args are: %s; %s", str(args), str(kwds))
    masto = Mastodon(*args, **kwds)
    try:
        yield masto
    finally:
        pass
