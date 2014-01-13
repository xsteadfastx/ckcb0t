from jabberbot import JabberBot, botcmd
from datetime import datetime
from tatort_fundus import Episode
from google import search
import sys
import re
import wikipedia


class LinkFile(object):
    """ class to handle the link text file """

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


class MUCJabberBot(JabberBot):
    PING_FREQUENCY = 60
    PING_TIMEOUT = 10

    ''' Add features in JabberBot to allow it to handle specific
    caractheristics of multiple users chatroom (MUC). '''

    def __init__(self, *args, **kwargs):
        ''' Initialize variables. '''

        # answer only direct messages or not?
        self.only_direct = kwargs.get('only_direct', False)
        try:
            del kwargs['only_direct']
        except KeyError:
            pass

        # initialize jabberbot
        super(MUCJabberBot, self).__init__(*args, **kwargs)

        # create a regex to check if a message is a direct message
        user, domain = str(self.jid).split('@')
        self.direct_message_re = re.compile('^%s(@%s)?[^\w]? ' \
                % (user, domain))

    def callback_message(self, conn, mess):
        ''' Changes the behaviour of the JabberBot in order to allow
        it to answer direct messages. This is used often when it is
        connected in MUCs (multiple users chatroom). '''

        message = mess.getBody()
        if not message:
            return

        if self.direct_message_re.match(message):
            mess.setBody(' '.join(message.split(' ', 1)[1:]))
            return super(MUCJabberBot, self).callback_message(conn, mess)
        elif not self.only_direct:
            return super(MUCJabberBot, self).callback_message(conn, mess)

        urls = re.compile('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        if urls.match(message) and self.get_sender_username(mess) != 'ckcb0t':
            #reply = urls.findall(message)[0]
            #self.send_simple_reply(mess, reply)
            logfile = LinkFile('urls.log')
            logfile.write(urls.findall(message)[0]+'\n')


class ckcb0t(MUCJabberBot):

    @botcmd
    def date(self, mess, args):
        """Gibt das Datum aus"""
        reply = datetime.now().strftime('%Y-%m-%d')
        self.send_simple_reply(mess, reply)

    @botcmd
    def tatort_nummer(self, mess, args):
        """Gibt die Episodennummer aus"""
        episode = Episode(args)
        reply = episode.episode_number
        self.send_simple_reply(mess, reply)

    @botcmd
    def tatort_schauspieler(self, mess, args):
        """Gibt die Schauspieler der Episode aus"""
        episode = Episode(args)
        for i in episode.actors:
            self.send_simple_reply(mess, i)

    @botcmd
    def tatort_beschreibung(self, mess, args):
        """Gibt Episoden-Zusammenfassung aus"""
        episode = Episode(args)
        reply = episode.summary
        self.send_simple_reply(mess, reply)

    @botcmd
    def tatort_datum(self, mess, args):
        """Erstsendedatum"""
        episode = Episode(args)
        reply = episode.erstsendung
        self.send_simple_reply(mess, reply)

    @botcmd
    def wiki(self, mess, args):
        wikipedia.set_lang('de')
        reply = wikipedia.summary(args, sentences=1)
        self.send_simple_reply(mess, reply)

    @botcmd
    def google(self, mess, args):
        for i in search(args, stop=5):
            self.send_simple_reply(mess, i)

    @botcmd
    def fun(self, mess, args):
        """ show fun lines """
        logfile = LinkFile('urls.log')
        for i in logfile.show(args):
            self.send_simple_reply(mess, i)

if __name__ == '__main__':

    username = 'ckcb0t@xsteadfastx.org'
    password = sys.argv[1]
    nickname = 'ckcb0t'
    chatroom = 'ckc-chan@conference.jabber.ccc.de'

    mucbot = ckcb0t(username, password, only_direct=True, debug=True)
    mucbot.join_room(chatroom, nickname)
    mucbot.serve_forever()
