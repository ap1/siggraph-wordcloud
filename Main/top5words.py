from google.appengine.ext import webapp
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api import mail
from google.appengine.ext import ndb
from datetime import datetime
import cgi

import urllib2

import re
import os

import logging

import webapp2

import collections

HTML_PREFIX = """\
    <html>
      <head>
        <title>SIGGRAPH Word Clouds</title>
        <link href='http://fonts.googleapis.com/css?family=Roboto+Slab' rel='stylesheet' type='text/css'>
        <link href="/static/main.css" type="text/css" rel="stylesheet">
      </head>
      <body>
"""

HTML_POSTFIX = """\
      </body>
    </html>
"""

Years = ['2015', '2014', '2013', '2012', '2011', '2010', '2009', '2008']

# lower case only
CommonWords = ['and', 'or', 'for', 'of', 'by', 'is', 
                'a', 'with', 'using', 'in', 'from', 'the', 
                '3d', 'on', 'via', 'to', 'an', 'graphics']

def RemoveHTMLComments(str):
  return re.sub('<!--.*?-->', '', str, flags=re.DOTALL)

# fetch a list of paper titles from ke-sen's page
def GetPaperTitles(str):
  return re.findall('<dt><B>[^<]+</B>', str, flags=re.IGNORECASE)

# fetch words from paper titles, convert to lower case, remove special characters
def GetPaperTitleWords(titles):
  return (re.sub('(<[^<]+?>)|:|\(|\)|,|!|\+', '', (" ").join(titles))).lower().split(' ')

def RemoveCommonWords(words):
  return [w for w in words if w not in CommonWords]

def GetTopWords(words, N):
  counter=collections.Counter(words)
  return counter.most_common(N)

class FindTop5Words(webapp2.RequestHandler):
    def get(self):
        self.response.write(HTML_PREFIX)
        self.response.write("<table class=\"ex\"><tr><td>")
        self.response.write("<br><p class=\"page_title\">SIGGRAPH Paper Title Word Clouds</p>\n")
        self.response.write("<p>A very poor attempt to identify trends in graphics research.</p>\n")
        self.response.write("<strong>Notes</strong><ul>\n")
        self.response.write("<li>Using data from <a href=\"http://kesen.realtimerendering.com\">Ke-Sen Huang's page</a>. For source of this script, <a href=\"https://github.com/ap1/siggraph-wordcloud\">click here</a>.</li>\n")
        self.response.write("<li>Words ignored: %s</li>\n" % ((", ").join(sorted(CommonWords))))
        self.response.write("<li>If you use this tool, please respect Ke-Sen's bandwidth limits and only run it a few times, offline.</li>\n")
        self.response.write("</ul>\n")
        rawWords = "<ul>"
        for Year in Years:
          try:
            webhtml = RemoveHTMLComments(urlfetch.fetch("http://kesen.realtimerendering.com/sig%s.html" % Year).content)

            titles = GetPaperTitles(webhtml)

            titleWords = GetPaperTitleWords(titles)

            titleWords = RemoveCommonWords(titleWords)

            topWords = GetTopWords(titleWords, 20)

            nWords = len(titleWords)

            self.response.write("<p class=\"topic_header\">SIGGRAPH %s (%d)</p>" % (Year,nWords))
            for word in topWords:
              fontSizePc = 100
              freq = 100.0 * float(word[1])/float(nWords)
              if  (freq > 1.0):   fontSizePc = 250
              elif(freq > 0.9):   fontSizePc = 200
              elif(freq > 0.8):   fontSizePc = 180
              elif(freq > 0.7):   fontSizePc = 150
              elif(freq > 0.6):   fontSizePc = 125
              elif(freq > 0.5):   fontSizePc = 100
              elif(freq > 0.4):   fontSizePc = 70
              elif(freq > 0.3):   fontSizePc = 50
              elif(freq > 0.2):   fontSizePc = 30
              elif(freq > 0.1):   fontSizePc = 20
              elif(freq > 0.05):  fontSizePc = 10
              else:               fontSizePc = 5
              self.response.write("<span style=\"font-size: %d%%;\">%s</span> (%d) &nbsp;&nbsp;" % (fontSizePc, word[0], word[1]))
            self.response.write("\n")

            rawWords = rawWords + "<li><span style=\"font-size: 250%%\">SIGGRAPH %s</span><br>" % Year + (", ").join(titleWords) + "\n\n"
          except urllib2.URLError, e:
            self.response.write(e)
        self.response.write("</td></tr></table>\n")
        rawWords = rawWords + "</ul>\n"
        self.response.write("<p><strong>Raw Words:</strong> " + rawWords + "\n")

        self.response.write(HTML_POSTFIX)
