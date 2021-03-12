# import urllib.request
import re
import os
import collections
import math
import sys
# import lxml
# from lxml import html
import requests
import time
from datetime import datetime

HTML_PREFIX = """\
    <html>
      <head>
        <title>SIGGRAPH Word Clouds</title>
        <meta name="author" content="Anjul Patney">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
        <link href="https://fonts.googleapis.com/css?family=Source+Sans+Pro" rel="stylesheet">
        <link href="static/main.css" rel="stylesheet" type="text/css">
      </head>
      <body>
"""

HTML_POSTFIX = """\
      <!-- Start of StatCounter Code for Default Guide -->
      <script type="text/javascript">
      var sc_project=10471620; 
      var sc_invisible=1; 
      var sc_security="81ba45aa"; 
      var scJsHost = (("https:" == document.location.protocol) ?
      "https://secure." : "http://www.");
      document.write("<sc"+"ript type='text/javascript' src='" +
      scJsHost+
      "statcounter.com/counter/counter.js'></"+"script>");
      </script>
      <noscript><div class="statcounter"><a title="shopify traffic
      stats" href="http://statcounter.com/shopify/"
      target="_blank"><img class="statcounter"
      src="http://c.statcounter.com/10471620/0/81ba45aa/1/"
      alt="shopify traffic stats"></a></div></noscript>
      <!-- End of StatCounter Code for Default Guide -->
      </body>
    </html>
"""


# lower case only
CommonWords = ['and', 'or', 'for', 'of', 'by', 'is', 
                'a', 'with', 'using', 'in', 'from', 'the', 
                '3d', 'on', 'via', 'to', 'an', 'graphics', 'design', ]

def RemoveHTMLComments(str):
  return re.sub('<!--.*?-->', '', str, flags=re.DOTALL)

# fetch a list of paper titles from ke-sen's page
def GetPaperTitles(str, confname):
  if confname == "CVPR":
    return re.findall('<dt class=\"ptitle\"><br><a href=\"[^\"]+\">[^<]+</a></dt>', str, flags=re.IGNORECASE)
  else:
    return re.findall('<dt><B>[^<]+</B>', str, flags=re.IGNORECASE)

# fetch words from paper titles, convert to lower case, remove special characters
def GetPaperTitleWords(titles):
  return (re.sub('(<[^<]+?>)|:|\(|\)|,|!|\+', '', (" ").join(titles))).lower().split(' ')

def RemoveCommonWords(words):
  return [w for w in words if w not in CommonWords]

def GetTopWords(words, N):
  counter=collections.Counter(words)
  return counter.most_common(N)

def isqrt(x):
  fsqrt = math.sqrt(float(x))
  return int(fsqrt)


# ---------- #
# -- main -- #
# ---------- #

def findTop5Words(prefix, postfix, title, Years, outFilename):
    allWords = []
    outFile = open(outFilename, 'w')
    outFile.write(HTML_PREFIX)
    outFile.write("<table class=\"ex\"><tr><td>")
    outFile.write("<br><p class=\"page_title\">%s Paper Title Word Clouds</p>\n" % title)
    outFile.write("<p>A very poor attempt to identify trends in graphics/ML research.</p>\n")
    outFile.write("<strong>Notes</strong><ul>\n")
    if prefix == "CVPR":
      outFile.write("<li>Using data from <a href=\"http://openaccess.thecvf.com\">CVPR Open Access Page</a>. For source of this script, <a href=\"https://github.com/ap1/siggraph-wordcloud\">click here</a>.</li>\n")
    else:
      outFile.write("<li>Using data from <a href=\"http://kesen.realtimerendering.com\">Ke-Sen Huang's page</a>. For source of this script, <a href=\"https://github.com/ap1/siggraph-wordcloud\">click here</a>.</li>\n")
    outFile.write("<li>Words ignored: %s</li>\n" % ((", ").join(sorted(CommonWords))))
    outFile.write("<li>If you use this tool, please respect the host's bandwidth limits and only run it a few times, offline.</li>\n")
    outFile.write("<li>Feedback: anjul dot patney at gmail dot com</li>\n")
    outFile.write("</ul>\n")
    rawWords = "<ul>"
    for Year in Years:
        # try:
        if prefix == "CVPR":
          fetchURL = "http://openaccess.thecvf.com/%s%s%s" % (prefix, Year, postfix)
        else:
          fetchURL = "http://kesen.realtimerendering.com/%s%s%s" % (prefix, Year, postfix)
        print (fetchURL)

        try:
            # req = urllib.request.Request(fetchURL, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36'})
            time.sleep(0.5)
            with requests.get(fetchURL) as page:
                #print (response.content)
                webhtml     = RemoveHTMLComments(page.text)

                titles      = GetPaperTitles(webhtml, prefix)
                titleWords  = GetPaperTitleWords(titles)
                titleWords  = RemoveCommonWords(titleWords)
                allWords    = allWords + titleWords
                topWords    = GetTopWords(titleWords, 10)
                nWords      = len(titleWords)

                print("Found %d potentially useful words" % (nWords))

                if nWords > 10:
                  outFile.write("<p class=\"topic_header\"><a href = %s>%s %s (%d)</a></p>" % (fetchURL, title, Year, nWords))

                  outFile.write("\n<div class=\"topic_content\">\n")

                  for word in topWords:
                      fontSizePc = 100
                      textdarkness = 250
                      freq = 100.0 * float(word[1])/float(nWords)
                      if  (freq > 1.0):   fontSizePc, textdarkness = 250, 250
                      elif(freq > 0.9):   fontSizePc, textdarkness = 200, 225
                      elif(freq > 0.8):   fontSizePc, textdarkness = 180, 200
                      elif(freq > 0.7):   fontSizePc, textdarkness = 150, 150
                      elif(freq > 0.6):   fontSizePc, textdarkness = 125, 100
                      elif(freq > 0.5):   fontSizePc, textdarkness = 100, 50
                      elif(freq > 0.4):   fontSizePc, textdarkness = 70, 40
                      elif(freq > 0.3):   fontSizePc, textdarkness = 50, 40
                      elif(freq > 0.2):   fontSizePc, textdarkness = 30, 40
                      elif(freq > 0.1):   fontSizePc, textdarkness = 20, 40
                      elif(freq > 0.05):  fontSizePc, textdarkness = 10, 40
                      else:               fontSizePc, textdarkness = 5, 40

                      textintensity = 255 - textdarkness
                      outFile.write("<span style=\"font-size: %d%%; color: rgb(%d,%d,%d)\">%s</span> (%d) &nbsp;&nbsp;" % (fontSizePc, textintensity, textintensity, textintensity, word[0], word[1]))

                  outFile.write("\n</div>\n")

                  rawWords = rawWords + "<li><span style=\"font-size: 250%%\">%s %s</span><br>" % (title, Year) + (", ").join(titleWords) + "\n\n"
                else:
                  print ("error")
        except: #urllib.request.URLError as e:
            print ("Error: " + str(sys.exc_info()))
    outFile.write("</td></tr></table>\n")
    rawWords = rawWords + "</ul>\n"
    #outFile.write("<p><strong>Raw Words:</strong> " + rawWords + "\n")

    outFile.write(HTML_POSTFIX)
    outFile.close()

    return allWords

def revYearRange(beg, end):
    return reversed([str(y) for y in range(beg, end+1)])


allWords = {}

allWords["cvpr"] = findTop5Words("CVPR",   ".py",        "CVPR",           revYearRange(2013, datetime.today().year+1), "cvpr.html")
allWords["sig"]  = findTop5Words("sig",    ".html",      "SIGGRAPH",       revYearRange(2008, datetime.today().year+1), "sig.html")
allWords["siga"] = findTop5Words("siga",   "Papers.htm", "SIGGRAPH Asia",  revYearRange(2008, datetime.today().year+1), "siga.html")
allWords["hpg"]  = findTop5Words("hpg",    "Papers.htm", "HPG",            revYearRange(2009, datetime.today().year+1), "hpg.html")
allWords["egsr"] = findTop5Words("egsr",   "Papers.htm", "EGSR",           revYearRange(2009, datetime.today().year+1), "egsr.html")

for awk in allWords.keys():
  aw = allWords[awk]
  aw = list(GetTopWords(aw, 500))
  wordlist = ",".join([a[0] for a in aw])

  f = open(awk + "_words.txt", "w")
  f.write(wordlist)
  f.close()


