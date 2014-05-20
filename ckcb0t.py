from bs4 import BeautifulSoup
from threading import Thread
import inspect
import logging
import re
import requests
import sleekxmpp
import time
import wikipedia


# import config file
from config import *


def get_website_title(url):
    ''' getting website title '''
    r = requests.get(url)
    soup = BeautifulSoup(r.text)
    return soup.title.text


class LinkFile(object):

    ''' class to handle the link text file '''

    def __init__(self, logfile):
        self.logfile = logfile

    def _open_file(self):
        return open(self.logfile, 'a+')

    def write(self, url):
        logfile = self._open_file()
        lines_seen = set(logfile)
        if url not in lines_seen:
            logfile.write(url)
        logfile.close()

    def show(self, linenumbers):
        lines = self._open_file().readlines()
        linenumbers = int(linenumbers)
        return lines[-linenumbers:]


def botcmd(*args, **kwargs):
    ''' decorator for bot command functions '''

    def decorate(func):
        setattr(func, '_ckcb0t_command', True)
        setattr(func, '_ckcb0t_command_name', func.__name__)
        return func

    if len(args):
        return decorate(args[0], **kwargs)
    else:
        return lambda func: decorate(func, **kwargs)


def botregex(re):
    ''' decorator for regex listeners '''
    def decorate(func):
        setattr(func, '_ckcb0t_regex', True)
        setattr(func, '_ckcb0t_regex_re', re)
        setattr(func, '_ckcb0t_regex_name', func.__name__)
        return func
    return decorate


def botthread(*args, **kwargs):
    ''' decorator for bot command functions '''

    def decorate(func):
        setattr(func, '_ckcb0t_thread', True)
        setattr(func, '_ckcb0t_thread_name', func.__name__)
        return func

    if len(args):
        return decorate(args[0], **kwargs)
    else:
        return lambda func: decorate(func, **kwargs)


class MUCBot(sleekxmpp.ClientXMPP):

    def __init__(self, jid, password, room, nick):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        self.room = room
        self.nick = nick

        # The session_start event will be triggered when
        # the bot establishes its connection with the server
        # and the XML streams are ready for use. We want to
        # listen for this event so that we we can initialize
        # our roster.
        self.add_event_handler("session_start", self.start)

        # The groupchat_message event is triggered whenever a message
        # stanza is received from any chat room. If you also also
        # register a handler for the 'message' event, MUC messages
        # will be processed by both handlers.
        self.add_event_handler("groupchat_message", self.muc_message)

        # The groupchat_presence event is triggered whenever a
        # presence stanza is received from any chat room, including
        # any presences you send yourself. To limit event handling
        # to a single room, use the events muc::room@server::presence,
        # muc::room@server::got_online, or muc::room@server::got_offline.
        self.add_event_handler("muc::%s::got_online" % self.room,
                               self.muc_online)

        # collect commands and regex listeners out of function attributes.
        # it fills two dictionaries with the function as value
        self.commands = {}
        self.regex_listeners = {}
        self.docstrings = {}
        self.threads = []
        for name, value in inspect.getmembers(self):
            if inspect.ismethod(value) and getattr(
                    value, '_ckcb0t_command', False):
                name = getattr(value, '_ckcb0t_command_name')
                self.commands[name] = value
                self.docstrings[name] = inspect.getdoc(value)
            elif inspect.ismethod(value) and getattr(
                    value, '_ckcb0t_regex', False):
                regex = re.compile(getattr(value, '_ckcb0t_regex_re'))
                self.regex_listeners[regex] = value
            elif inspect.ismethod(value) and getattr(
                    value, '_ckcb0t_thread', False):
                self.threads.append(Thread(target=value))

    def start(self, event):
        """
        Process the session_start event.

        Typical actions for the session_start event are
        requesting the roster and broadcasting an initial
        presence stanza.

        Arguments:
            event -- An empty dictionary. The session_start
                     event does not provide any additional
                     data.
        """
        self.get_roster()
        self.send_presence()
        self.plugin['xep_0045'].joinMUC(self.room,
                                        self.nick,
                                        # If a room password is needed, use:
                                        # password=the_room_password,
                                        wait=True)

        for thread in self.threads:
            thread.start()

    def muc_message(self, msg):
        """
        Process incoming message stanzas from any chat room. Be aware
        that if you also have any handlers for the 'message' event,
        message stanzas may be processed by both handlers, so check
        the 'type' attribute when using a 'message' event handler.

        Whenever the bot's nickname is mentioned, respond to
        the message.

        IMPORTANT: Always check that a message is not from yourself,
                   otherwise you will create an infinite loop responding
                   to your own messages.

        This handler will reply to messages that mention
        the bot's nickname.

        Arguments:
            msg -- The received message stanza. See the documentation
                   for stanza objects and the Message stanza to see
                   how it may be used.
        """

        if msg['mucnick'] != self.nick:
            # checks for regex and fires function if matched
            for regex, function in self.regex_listeners.iteritems():
                if regex.match(msg['body']):
                    reply = function(msg['body'])
                    # sends the function return as message if there
                    if reply:
                        if isinstance(reply, list):
                            for item in reply:
                                self.send_message(mto=msg['from'].bare,
                                                  mbody=item,
                                                  mtype='groupchat')
                        else:
                            self.send_message(mto=msg['from'].bare,
                                              mbody=reply,
                                              mtype='groupchat')
            # checks for bot commands and fires function if needed
            if msg['body'].startswith('!'):
                cmd = msg['body'].split(' ', 1)[0].split('!')[1]
                args = msg['body'].split(cmd)[1].lstrip()
                if cmd in self.commands:
                    try:
                        if args:
                            reply = self.commands[cmd](args)
                        else:
                            reply = self.commands[cmd]()
                    except Exception:
                        reply = 'An error happend'
                    if isinstance(reply, list):
                        for item in reply:
                            self.send_message(mto=msg['from'].bare,
                                              mbody=item,
                                              mtype='groupchat')
                    else:
                        self.send_message(mto=msg['from'].bare,
                                          mbody=reply,
                                          mtype='groupchat')

    def muc_online(self, presence):
        """
        Process a presence stanza from a chat room. In this case,
        presences from users that have just come online are
        handled by sending a welcome message that includes
        the user's nickname and role in the room.

        Arguments:
            presence -- The received presence stanza. See the
                        documentation for the Presence stanza
                        to see how else it may be used.
        """
        if presence['muc']['nick'] != self.nick:
            self.send_message(mto=presence['from'].bare,
                              mbody="Moinsen %s" % (presence['muc']['nick']),
                              mtype='groupchat')


class ckcb0t(MUCBot):

    @botcmd
    def echo(self, message):
        ''' echoes message '''
        return message

    @botcmd
    def ping(self):
        ''' ping pong '''
        return 'pong'

    @botcmd
    def help(self):
        ''' show this help '''
        collected_docstrings = []
        for name, docstring in self.docstrings.iteritems():
            collected_docstrings.append(name + ': ' + docstring)
        return collected_docstrings

    @botcmd
    def fun(self, args):
        ''' show fun lines '''
        logfile = LinkFile('urls.log')
        return logfile.show(args)

    @botcmd
    def wiki(self, args):
        ''' wikipedia search '''
        wikipedia.set_lang('de')
        return wikipedia.summary(args, sentences=3)

    @botregex(
        'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    def urls(self, message):
        ''' matches urls and doing stuff '''
        logfile = LinkFile('urls.log')
        print 'write ' + message + ' to logfile'
        logfile.write(message + '\n')
        try:
            return get_website_title(message)
        except Exception:
            pass

    @botthread
    def thread_ping(self):
        ''' sends every hour a ping to the room '''
        while True:
            self.send_message(mto=self.room,
                              mbody='ping',
                              mtype='groupchat')
            time.sleep(3600)


if __name__ == '__main__':
    # Logging
    logging.basicConfig(level=30,
                        format='%(levelname)-8s %(message)s')

    # Setup Bot and register plugins.
    xmpp = ckcb0t(JID, PASSWORD, CHANNEL, CHANNEL_NICK)
    xmpp.register_plugin('xep_0030')  # Service Discovery
    xmpp.register_plugin('xep_0045')  # Multi-User Chat
    xmpp.register_plugin('xep_0199')  # XMPP Ping

    # Connect to the XMPP server and start processing XMPP stanzas.
    if xmpp.connect():
        # If you do not have the dnspython library installed, you will need
        # to manually specify the name of the server if it does not match
        # the one in the JID. For example, to use Google Talk you would
        # need to use:
        #
        # if xmpp.connect(('talk.google.com', 5222)):
        #     ...
        xmpp.process(block=True)
        print("Done")
    else:
        print("Unable to connect.")
