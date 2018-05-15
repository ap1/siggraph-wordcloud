import urllib.request
import re
import os
import collections

HTML_PREFIX = """\
    <html>
      <head>
        <title>SIGGRAPH Word Clouds</title>
        <link href='http://fonts.googleapis.com/css?family=Roboto+Slab' rel='stylesheet' type='text/css'>
        <link href="static/main.css" type="text/css" rel="stylesheet">
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



# ---------- #
# -- main -- #
# ---------- #

def findTop5Words(prefix, postfix, title, Years, outFilename):
    outFile = open(outFilename, 'w')
    outFile.write(HTML_PREFIX)
    outFile.write("<table class=\"ex\"><tr><td>")
    outFile.write("<br><p class=\"page_title\">%s Paper Title Word Clouds</p>\n" % title)
    outFile.write("<p>A very poor attempt to identify trends in graphics research.</p>\n")
    outFile.write("<strong>Notes</strong><ul>\n")
    outFile.write("<li>Using data from <a href=\"http://kesen.realtimerendering.com\">Ke-Sen Huang's page</a>. For source of this script, <a href=\"https://github.com/ap1/siggraph-wordcloud\">click here</a>.</li>\n")
    outFile.write("<li>Words ignored: %s</li>\n" % ((", ").join(sorted(CommonWords))))
    outFile.write("<li>If you use this tool, please respect Ke-Sen's bandwidth limits and only run it a few times, offline.</li>\n")
    outFile.write("<li>Feedback: anjul dot patney at gmail dot com</li>\n")
    outFile.write("</ul>\n")
    rawWords = "<ul>"
    for Year in Years:
        # try:
        fetchURL    = "http://kesen.realtimerendering.com/%s%s%s" % (prefix, Year, postfix)
        print (fetchURL)

        try:
            req = urllib.request.Request(fetchURL, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36'})
            with urllib.request.urlopen(req) as response:
                #print (response.content)
                webhtml     = RemoveHTMLComments(str(response.read()))

                titles      = GetPaperTitles(webhtml)
                titleWords  = GetPaperTitleWords(titles)
                titleWords  = RemoveCommonWords(titleWords)
                topWords    = GetTopWords(titleWords, 10)
                nWords      = len(titleWords)

                if nWords > 10:
                  outFile.write("<p class=\"topic_header\">%s %s (%d)</p>" % (title, Year, nWords))

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
                      outFile.write("<span style=\"font-size: %d%%;\">%s</span> (%d) &nbsp;&nbsp;" % (fontSizePc, word[0], word[1]))

                  outFile.write("\n")

                  rawWords = rawWords + "<li><span style=\"font-size: 250%%\">%s %s</span><br>" % (title, Year) + (", ").join(titleWords) + "\n\n"
                else:
                  print ("error")
        except urllib.request.URLError as e:
            print (e)
    outFile.write("</td></tr></table>\n")
    rawWords = rawWords + "</ul>\n"
    #outFile.write("<p><strong>Raw Words:</strong> " + rawWords + "\n")

    outFile.write(HTML_POSTFIX)
    outFile.close()

def revYearRange(beg, end):
    return reversed([str(y) for y in range(beg, end+1)])

findTop5Words("sig",    ".html",      "SIGGRAPH",       revYearRange(2008, 2025), "sig.html")
findTop5Words("siga",   "Papers.htm", "SIGGRAPH Asia",  revYearRange(2008, 2025), "siga.html")
findTop5Words("hpg",    "Papers.htm", "HPG",            revYearRange(2009, 2025), "hpg.html")
