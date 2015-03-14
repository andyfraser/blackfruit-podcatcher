# The BlackFruit Podcatcher

# Imports
import os, sys, string, feedparser, urllib, smtplib

# Global configuration object.
class Config(object):

    def __init__(self, config):
        self.test = self.parseLine(config, '-t')
        self.cron = self.parseLine(config, '--cron')
        self.latest = self.parseLine(config, '-l')
        self.allentries = self.parseLine(config, '-a')
        self.subscribe = self.parseStringLine(config, '-s')
        self.logsize = 1000
        self.poddir = os.getenv("HOME") + "/podcasts/"
        self.cachedir = self.poddir + "cache/"
        self.runfile = self.poddir + 'podcatcher.run'
        self.logfile = self.poddir + "downloaded.log"
        self.feedsfile = self.poddir + "feeds.conf"
        self.fromaddr = 'andyfraser@gmail.com'
        self.toaddr = 'andy@blackfruit.co.uk'
        # Massive security hole right here!
        self.username = 'username'
        self.password = 'password'
        if self.subscribe:
            self.latest = 1

    # Parser for command line switches.
    def parseLine(self, config, value):
        try:
            if config.index(value):
                return 1
        except ValueError:
            return 0

    # PArser for string arguments.
    def parseStringLine(self, config, value):
        for i in range(1, len(config)):
            if config[i] == '-s':
                return config[i + 1]
        return 0

# Base class for handling files.
class BaseFile(object):

    # Initialise and read the file.
    def __init__(self, filename, config):
        self.config = config
        self.changed = False
        self.sortonsave = False
        self._list = []
        contents = open(filename, "r")
        for c in contents:
            self._list.append(c.rstrip("\n"))
        contents.close()
        self._file = filename

    # Return the filename.
    def GetFilename(self):
        return self._file

    # Return the contents of the file.
    def GetList(self):
        return self._list

    # Save the file but only if it's been changed.
    def save(self):
        if self.changed:
            if self.sortonsave:
                self._list.sort()
            f = open(self._file, "w")
            for line in self._list:
                f.write(line + "\n")
            f.close()


# Class specific to the feeds file. Derived from BaseFile.
class Feeds(BaseFile):
    def __init__(self, filename, config):
        super(Feeds, self).__init__(filename, config)
        self.sortonsave = True

    def add(self, url):
        if not url in self._list:
            self._list.append(url)
            self.changed = True

    feeds = property(BaseFile.GetList)

# Class specific to the log file. Derived from BaseFile.
class Log(BaseFile):
    def add(self, logentry):
        self._list.insert(0, logentry)
        if len(self._list) > self.config.logsize:
            self._list.pop()
        self.changed = True

    log = property(BaseFile.GetList)

# The Mailer class. Sends an email if anything was downloaded.
class Mailer(object):
    def __init__(self, config):
        self.config = config
        self.downloaded = []
        self._msg =  "From: andyfraser@gmail.com\nSubject: Videos Downloaded\n\nThe following videos have been downloaded:\n\n"

    def send(self):
        if len(self.downloaded) > 0:
            for i in self.downloaded:
                self._msg = self._msg + i + '\n'
            server = smtplib.SMTP('smtp.gmail.com:587')
            server.starttls()
            server.login(self.config.username, self.config.password)
            server.sendmail(self.config.fromaddr, self.config.toaddr, self._msg)
            server.quit()

    def add(self, value):
        self.downloaded.append(value)

# The main podcatcher class.
class Podcatcher(object):

    def __init__(self):
        self.config = Config(sys.argv)
        self.feeds = Feeds(self.config.feedsfile, self.config)
        self.log = Log(self.config.logfile, self.config)
        self.mailer = Mailer(self.config)

    # A print mechanism that only prints if --cron isn't specified.
    def podPrint(self, value):
        if not self.config.cron:
            print value

    # Remove bad characters from potential filenames.
    def sanitiseString(self, filename):
        valid_chars = "-_,.()'# %s%s" % (string.ascii_letters, string.digits)
        return ''.join(c for c in filename if c in valid_chars)

    # Process a feed.
    def processFeed(self, feedurl):
        self.podPrint("  Processing URL " + feedurl)
        feed = feedparser.parse(feedurl)
        self.podPrint("  Feed name: " + feed.feed.title)
        for entry in feed.entries:
            self.podPrint("    Checking " + entry.title)
            feeddir = self.config.poddir + 'cache/' + feed.feed.title
            if not os.path.exists(feeddir):
                self.podPrint("    Creating directory " + feeddir)
                if not self.config.test:
                    os.makedirs(feeddir)
            url = entry.enclosures[0].href
            filename = os.path.basename(url)
            fileext = os.path.splitext(filename)
            logentry = feed.feed.title + '/' + filename
            if logentry in self.log.log:
                self.podPrint("      " + logentry + " already downloaded.")
                if not self.config.allentries:
                    break
            else:
                self.podPrint("      Downloading " + logentry)
                if not self.config.test:
                    urllib.urlretrieve(url, feeddir + '/' + self.sanitiseString(entry.title) + fileext[1])
                    self.log.add(logentry)
                    self.mailer.add(entry.title)
            if self.config.latest:
                break

    # Run the podcatcher but only if it's not already running.
    def run(self):
        if os.path.exists(self.config.runfile):
            self.podPrint("Already running.")
            return
        else:
            f = open(self.config.runfile, "w")
            f.close()

        self.podPrint("Podcatcher running.")
        if self.config.subscribe:
            self.podPrint("Subscribing to " + self.config.subscribe)
            if not self.config.test:
                self.feeds.add(self.config.subscribe)
            self.processFeed(self.config.subscribe)
        else:
            for url in self.feeds.feeds:
                self.processFeed(url)

        if os.path.exists(self.config.runfile):
            os.remove(self.config.runfile)

    # When we've finished save the files and send the email.
    def __del__(self):
        self.feeds.save()
        self.log.save()
        self.mailer.send()
