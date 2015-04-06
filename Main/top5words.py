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
CommonWords = ['and', 'or', 'for', 'of', 'by', 'is', 'a', 'with', 'using', 'in', 'from', 'the', '3d', 'on', 'via', 'to', 'an']

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
        self.response.write("<p>A very poor attempt to identify trends in graphics research.</p>")
        self.response.write("<p>Using data from Ke-Sen Huang's page. <a href=\"https://github.com/ap1/siggraph-wordcloud\">Source</a>.</p><br>\n")
        rawWords = "<ul>"
        for Year in Years:
          try:
            webhtml = urlfetch.fetch("http://kesen.realtimerendering.com/sig%s.html" % Year).content

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
              elif(freq > 0.6):   fontSizePc = 130
              elif(freq > 0.5):   fontSizePc = 110
              elif(freq > 0.4):   fontSizePc = 100
              elif(freq > 0.3):   fontSizePc = 90
              elif(freq > 0.2):   fontSizePc = 75
              elif(freq > 0.1):   fontSizePc = 60
              elif(freq > 0.05):  fontSizePc = 50
              else:               fontSizePc = 30
              self.response.write("<span style=\"font-size: %d%%;\">%s</span> (%d) &nbsp;&nbsp;" % (fontSizePc, word[0], word[1]))
            self.response.write("\n")

            rawWords = rawWords + "<li><span style=\"font-size: 250%%\">SIGGRAPH %s</span><br>" % Year + (", ").join(titleWords) + "\n\n"
          except urllib2.URLError, e:
            self.response.write(e)
        self.response.write("</td></tr></table>\n")
        self.response.write("<p><strong>Words ignored</strong>: %s</p>\n" % ((", ").join(sorted(CommonWords))))
        self.response.write("<hr><p><strong>Note</strong>: If you use this tool, please respect Ke-Sen's bandwidth limits and only run it a few times, offline.</p>\n")

        rawWords = rawWords + "</ul>\n"
        self.response.write("<p><strong>Raw Words:</strong> " + rawWords + "\n")

        self.response.write(HTML_POSTFIX)
