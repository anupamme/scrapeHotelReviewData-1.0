"""Python Module for scraping hotel reviews.

This module scrapes review data from hotels (date, rating and review text) from Tridadvisor/Orbitz for all hotels in (and close to) the given list of cities in an US state.
Note that no Personal Information of the reviewers such as their account name or address is scraped.

Does this in 5 steps:
Step 1: Get the list of cities and the URLs listing hotels for that. (Only needed for TA - Tripadvisor)
Step 2: Get the list of URLs for each hotel in a city.
Step 3: Get the list of review pages for each hotel.
Step 4: From each hotel get the review information needed.
Step 5: Get the stats for each hotel

It also has the ability to be interrupted and (effectively) resume from where it stopped without having to redownload all the previous files. It does this by performs optimizations such as storing the webpages it has downloaded and compacting the downloaded pages into a format that is easy to process.

NOTE: This becomes essential since Tridadvisor starts dropping if you download too many pages too fast and hence it may need to be restarted after pausing for a few seconds.

Usage:
  scrapeHotelReviewData.py [-h] -state STATE -cities CITIES [-delay DELAY] -site SITE -o OUTPUT -path PATH

Inputs:
  -h, --help      show this help message and exit
  -state STATE    State for which the city data is required.
  -cities CITIES  Filename containing list of cities for which data is
                  required
  -delay DELAY    Amount of time to pause after downloading a website
  -site SITE      Either tripadvisor or orbitz
  -o OUTPUT       Path to output file for reviews
  -path PATH      Directory where the webpages should be downloaded

Key Outputs:
  - TSV File containing the review information
  - Condensed set of information downloaded
  - List of cities not found on website.
"""

import argparse
import urllib2
import sys
import time
import os
import bisect
import logging
import traceback
from pyquery import PyQuery as pq
import pdb
import os
import re

#Set the global variables
path = '/home/karthik/Desktop/Scraping/Hotels/WebPages'
state = ""
numReviewsPerPage = 10
numHotelsPerPage = 30
delayTime = 1

baseUrl = ""
outFile = None

totReviews = 0
trueNumH = 0

allHotelsSoFar = []
response = None

def getCities(cityF):
    """Reads the file and returns the list of cities
    
    Inputs:
    - cityF : File containing the list of cities (one per line)
    
    Returns:
    - List of cities in list
    
    """
    cityList = []
    for line in file(cityF):
        cityList.append(line.strip())
    return cityList

def getFileContentFromWeb(url):
        time.sleep(delayTime)
        #response = urllib2.urlopen(url)
        print("url to open: ", url)
        try:
           response = urllib2.urlopen(url)
           print("after response1")
        except urllib2.HTTPError, e:
           logging.error('HTTPError = ' + str(e.code))
           return None
        except urllib2.URLError, e:
           logging.error('URLError = ' + str(e.reason))
           return None
        except httplib.HTTPException, e:
           logging.error('HTTPException')
           return None
        except Exception:
           logging.error('generic exception: ' + traceback.format_exc())
           return None

        return response.read()

def downloadToFile(url, fileName, force = True):
    """Downloads url to file
    
    Inputs:
    - url : Url to be downloaded
    - fileName : Name of the file to write to
    - force : Optional boolean argument which if true will overwrite the file even it it exists
    
    Returns:
    - Pair indicating if the file was downloaded and a list of the contents of the file split up line-by-line
    
    """
    print("path: ", path)
    print("Filename: ", fileName)
    fullFileName = path+'/'+ fileName.replace("/","\\/")
    downloaded = False
    print(fullFileName)
    if not force and os.path.exists(fullFileName):
        print "Reading file: ", fileName
        thisFile = open(fullFileName)
        fileContents = thisFile.read()
        thisFile.close()
    else:
        print "Downloading URL : ", url, " to file: ", fullFileName
        fileContents = getFileContentFromWeb(url)
        output = None
        #print "file contents: ", fileContents, "\n"
        if fileContents == None:
           return ([], False)
        output = open(fullFileName, 'w')
        output.write(fileContents)
        output.close()
        downloaded = True
        return (fileContents.split("\n"), downloaded)

def getNumberOfReviews(content):
    """Tripadvisor only: Gets the number of reviews for this hotel
    
    Inputs:
    - content : Website content
    
    Returns:
    - Number of reviews
    
    """  
    if len(content) < 3:
        return 0
    line = content[1].strip()
    revStr = "TotReviews:"
    return int( line[ len(revStr) :] )

def getNumberOfHotels(content):
    if len(content) == 0:
       return 0
    preS2 = "of <b>"
    sufS2 = "</b>"
    line = content[0]
    pInd = line.rfind(preS2) + len(preS2)
    sInd = line.rfind(sufS2)
    print("line: ", line)
    return int(line[pInd: sInd].replace(",",""))

def isCharInt(c):
    """Checks to see if the character is an integer or not."""
    try:
        x = int(c)
        return True
    except:
        return False
    return False

def getHotelListInsertIndex(s):
    """Tripadvisor only: Gets where the hotel index should be inserted"""  
    numD = 0
    index = s.find('-')+1
    index = s.find('-',index)+1
    if isCharInt(s[index+1]):
        index = s.find('-',index)+1
    return index

def getAddress(s):
    """Gets the city
    
    Inputs:
    - url : Content string
    
    Returns:
    - City
    
    """
    str1 = "property=\"v:locality\">"
    ind1 = s.find(str1) + len(str1)
    if ind1 < len(str1):
        str2 = "<span class=\"locality\">"
        ind1 = s.find(str2) + len(str2)
    ind2 = s.find("</span>",ind1)
    return    s[ind1:ind2]

def getFullAddress(s):
    """Gets the complete address
    
    Inputs:
    - url : Content string
    
    """
    str1 = "<"
    str2 = ">"
    lastInd = len("Address:")
    addStr = ""
    while True:
        ind1 = s.find(str2, lastInd)
        if ind1 < lastInd:
            break
        ind1 += len(str2)

        ind2 = s.find(str1,ind1)
        if ind2 < ind1:
            break
        addr = s[ind1:ind2]
        if len(addr) > 0:
            addStr += addr + " "
        lastInd  = len(str1) + ind2
        
    return addStr.strip()

def pruneCitySearchPage(content):
    inside = False
    preStr = "<div class=\"srGeoLinks\">"
    pruneContent = []
    for line in content:
      if True:
        if line.find("Hotel_Review") != -1:
          #print("line contains hote_review: ", line)
          line = line.strip()
          pruneContent.append(line)
        else:
          continue
  #    fInd = line.find(preStr)
  #    if fInd != -1:    #Process this line
   #     inside = True
    return pruneContent

def pruneSearchFile(searchContents, fileName, city):
    
    print "Finished downloading search page"
    prunedSearchContents = pruneCitySearchPage(searchContents)
    #prunedSearchContents = searchContents
    with open(path+'/'+ fileName.replace("/","\\/"),'w') as outF:
        for line in prunedSearchContents:
            outF.write(line+'\n')
    print city,"search page pruned to ", len(prunedSearchContents)," lines from ", len(searchContents)," lines"
    return prunedSearchContents

def getCityHotelListPage(content):
    pages = []
    preStr = "href="
    sufStr = ".html"
    for line in content:
        print("our line: ", line)
        if len(line) > 2:
            sufInd = line.find(sufStr) + len(sufStr)
            line = line[:sufInd]
            preInd = line.find(preStr) + len(preStr) + 2        
            url = line[preInd:]
            print("line: ", line)
            print("parsed-url: ", url)
            pages.append( url )
    print("Total Hotels in this page: ", len(pages))
    return pages

def pruneTAHotelListPage(content):
    """Prunes the page returned by trip advisor listing all hotels in a city.
        
    Inputs:
    - content : Content list of the original hotel list page
    
    """
    numPreS = "<div id=\"INLINE_COUNT\""
    hotelSufS = "\" class=\"property_title\""
    pruneContent = []
    foundNum = False

    i = 0
    while i < len(content):
        line = content[i]

        if not foundNum and line.find(numPreS) != -1:    #Add the line containing the number
            i += 1
            pruneContent.append( content[i] )
            foundNum = True

        if line.find(hotelSufS) != -1:    #Add the line containing the number
            pruneContent.append( content[i] )
            i += 1
            pruneContent.append( content[i] )


        i += 1
        
    return pruneContent

def pruneOrbitzHotelListPage(content):
    """Prunes the page returned by orbitz listing all hotels in a city.
        
    Inputs:
    - content : Content list of the original hotel list page
    
    """
    #Need the url of next page (else blank) along with urls and names of the hotels
    nextS = "\" class=\"link\" rel=\"nofollow\">Next</a>"
    nextS2 = "<a href=\""
    hotelSufS = "class=\"hotelNameLink link\""
    pruneContent = []
    foundNext = False

    i = 0
    while i < len(content):
        line = content[i]

        if not foundNext:
            ind1 = line.find(nextS)
            if ind1 != -1:    #Extract the next url
                foundNext = True
                pruneContent.insert(0,line [ line.find(nextS2) + len(nextS2): ind1])


        if line.find(hotelSufS) != -1:    #Add the line containing the number
            pruneContent.append( content[i] )


        i += 1

    if not foundNext:
        pruneContent.insert(0,"")

    return pruneContent
        
def pruneHotelListFile(hlContents, fileName, option, city):
    """Prunes the hotel list file contents from the entire website to only what is required"""  
    print "Finished downloading hotel list page"
    if option == "tripadvisor":
        prunedHLContents = pruneTAHotelListPage(hlContents)
    else:
        prunedHLContents = pruneOrbitzHotelListPage(hlContents)
    with open(path+'/'+ fileName.replace("/","\\/"),'w') as outF:
        for line in prunedHLContents:
            outF.write(line+'\n')
    print city,"hotel list pruned to ", len(prunedHLContents)," lines from ", len(hlContents)," lines"
    return prunedHLContents

def getTAHotels(content):
    """For trip advisor gets all hotels in a city.
        
    Inputs:
    - content : Pruned content of the hotel list page
    
    """
    pages = []
    names = []
    sufStr = "\" class=\"property_title\""
    preStr = "<a href=\""
    i = 1
    while i < len(content):
        line = content[i]
        i += 1
        if len(line) > 1:
            preInd = line.find(preStr)  + len(preStr)
            sufInd = line.find(sufStr,preInd)
            url = line[preInd:sufInd]
            pages.append( url )

            name = content[i]
            i += 1
            name = name[ : name.find("</a>")].replace('/','--')
            names.append( name )

    return (pages, names)
    
def getOrbitzHotels(content):
    """For orbitz gets all hotels in a city.
        
    Inputs:
    - content : Pruned content of the hotel list page
    
    """
    pages = []
    names = []
    ids = []
    sufStr = "\" class=\"hotelNameLink"
    preStr = "<a href=\""
    sufStr2 = "</a>"
    preStr2 = "\">"
    idStr = "&hotel.hid="
    i = 1
    while i < len(content):
        line = content[i]
        i += 1
        if len(line) > 1:
            preInd = line.find(preStr)  + len(preStr)
            sufInd = line.find(sufStr,preInd)        
            url = line[preInd:sufInd]
            idInd = url.find(idStr) + len(idStr)
            idSt = url[idInd:url.find("&",idInd)]
            pages.append( url+"#reviews" )
            ids.append(idSt)

            sufInd +=  len(sufStr)
            preInd2 = line.find(preStr2,sufInd)  + len(preStr2)
            sufInd2 = line.find(sufStr2,preInd2)        
            name = line[preInd2:sufInd2].strip().replace('/','--')
            names.append( name )
    return (pages, names, ids)

def pruneTAReviewPage(contents):
    """For trip advisor pruned the page containing all the review to just the vital lines containing required information
        
    Inputs:
    - content : Pruned content of the review page
    
    """
    prunedContents = []

    preNumRStr = "<h3 class=\"reviews_header\">"
    sufNumRStr = " reviews from our community"
    sufNumR2Str = " review from our community"
    foundNumR = False

    addrStr1 = "<span dir=\"ltr\""
    addrStr2 = "<span property=\"v:locality\""
    addrStr3 = "<span class=\"locality\""
    foundAddr = False

    userRevURL = "<a href=\"/ShowUserReviews"

    insideReviewState = 0
    startRevStr1 = "class=\"reviewSelector\""
    startRevStr2 = "review basic_review"
    endRevStr1 = "Was this review helpful?"
    endRevStr2 = "wrap reportProblem"

    dateStr = "class=\"ratingDate\""
    dateStr2 = "Reviewed "

    starStr1 = "sprite-ratings"
    starStr2 = "of 5 stars"
    starStr3 = "alt=\""

    textStr1 = "class=\"partial_entry\""
    textStr2 = "class=\"partnerRvw\""

    curText = ""
    startedText = False

    foundStars = False
    foundDate = False
    foundText = False

    for line in contents:
        line = line.strip()

        if not foundAddr and line.find(addrStr1) != -1  and (line.find(addrStr2) != -1 or line.find(addrStr3) != -1):
            prunedContents.append("Address:"+line)
            foundAddr = True

        if not foundNumR:
            fInd = line.find(sufNumRStr)
            if line.find(sufNumR2Str) != -1 :    #Find the number of reviews
                fInd = line.find(sufNumR2Str)
            if fInd != -1:
                preInd = line.find(preNumRStr)  + len(preNumRStr)
                prunedContents.append( "TotReviews:"+ line[preInd : fInd].replace(",","") )
                foundNumR = True

        if insideReviewState == 0:
            ind = line.find(startRevStr1)
            if ind!=-1:
                insideReviewState = 1
        elif insideReviewState == 1:
            ind = line.find(startRevStr2)
            if ind!=-1:
                insideReviewState = 2

                foundStars = False
                foundDate = False
                foundText = False
                startedText = False
                curText = ""

                prunedContents.append("StartNewReview")

        elif insideReviewState == 2:

            #Search for required information here
            #Get the line containing the full url

            if line.find(userRevURL) != -1:
                prunedContents.append(line.strip())

            #A) Number of Stars
            if not foundStars:
                ind1 = line.find(starStr1)
                if ind1!=-1:
                    ind2 = line.find(starStr2)
                    ind3 = line.find(starStr3)
                    if ind2!= -1 and ind3 != -1:
                        starVal = line[ind3+len(starStr3): ind2]
                        prunedContents.append("Rating:"+ starVal)
                        foundStars = True

            #B) Date
            if not foundDate:
                ind = line.find(dateStr)
                if ind!=-1:
                    dateVal = line[line.find(dateStr2) + len(dateStr2):]
                    prunedContents.append("Date:"+ dateVal)
                    foundDate = True

            #C) Text
            if not foundText:
                if not startedText:
                    ind = line.find(textStr1)
                    if ind!=-1:
                        startedText = True
                else:
                    ind = line.find(textStr2)
                    if ind!=-1:
                        prunedContents.append("ReviewText:"+curText)
                        foundText = True
                        startedText = False
                    else:
                        curText += line +" -newline- "

            #Now checking exit condition
            ind = line.find(endRevStr1)
            if ind!=-1:
                insideReviewState = 3
        elif insideReviewState == 3:
            ind = line.find(endRevStr2)
            if ind!=-1:
                insideReviewState = 0
                prunedContents.append("EndOfReview")
    
    return prunedContents

def pruneOrbitzReviewPage(contents):
    """For orbitz prune the page containing all the review to just the vital lines containing required information
        
    Inputs:
    - content : Pruned content of the review page
    
    """
    prunedContents = []

    nextStr = "\" class=\"link\">Next</a>"
    nextStr2 = "<a href=\""
    foundNext = False

    addrStr1 = "<a href=\"#mapAndAreaInfo\" class=\"link\">"
    addrStr2 = "</a>"
    foundAddr = False

    cityStr0 = "link rel=\"canonical\""
    cityStr1 = "United_States--TX/"
    cityStr2 = "/"
    foundCity = False

    insideReviewState = 0
    startRevStr1 = "<div class=\"reviewDetails\">"
    startRevStr2 = "<p class=\"userReviewLabel offscreen\">Reviewer score</p>"
    endRevStr1 = "<div class=\"showHideView block\">"

    dateStr1 = "<abbr class=\"date dtreviewed\" title=\""
    dateStr2 = "\">"

    starStr1 = "<div class=\"score\">  <span class=\"rating\">"
    starStr2 = "</span>"

    textStr1 = "<p class=\"reviewComment description\""
    textStr2 = "<span class=\"ellipsis inline\""
    textStr3 = "</p>"

    exTextStr1 = "<span class=\"extendedReviewText noneInline\">"
    exTextStr2 = "</span>"

    curText = ""
    startedText = False
    expectMore = False
    startedMore = False

    foundStars = False
    foundDate = False
    foundText = False
    foundMore = False

    for line in contents:
        line = line.strip()

        if not foundNext:    #Next Review
            sufInd = line.find(nextStr)
            if sufInd != -1 :    #Find the number of reviews
                preInd = line.find(nextStr2) + len(nextStr2)
                nextUrl = line[preInd : sufInd].replace("&amp;","&")
                prunedContents.insert(0, "Next:"+ nextUrl )
                foundNext = True

        if not foundCity and line.find(cityStr0) !=  -1:    #City of hotel
            ind1 = line.find(cityStr1)
            if ind1 != -1:
                ind1 += len(cityStr1)
                ind2 = line.find(cityStr2, ind1)
                curPos = min(1,len(prunedContents))
                prunedContents.insert(curPos,"City:"+line[ind1:ind2])
                foundCity = True

        if not foundAddr:    #Full Address
            ind1 = line.find(addrStr1)
            if ind1 != -1:
                ind1 += len(addrStr1)
                ind2 = line.find(addrStr2, ind1)
                curPos = min(2,len(prunedContents))
                prunedContents.insert(curPos,"Address:"+line[ind1:ind2].strip())
                foundAddr = True

        #Get each review
        if insideReviewState == 0:
            ind = line.find(startRevStr1)
            if ind!=-1:
                insideReviewState = 1
        elif insideReviewState == 1:
            ind = line.find(startRevStr2)
            if ind!=-1:
                insideReviewState = 2
                foundStars = False
                foundDate = False
                foundText = False
                foundMore = False
                startedText = False
                startedMore = False
                curText = ""
                prunedContents.append("StartNewReview")

        elif insideReviewState == 2:
            #A) Number of Stars
            if not foundStars:
                ind1 = line.find(starStr1)
                if ind1!=-1:
                    ind1 += len(starStr1)
                    ind2 = line.find(starStr2, ind1)
                    prunedContents.append("Rating:"+ line[ind1: ind2])
                    foundStars = True

            #B) Date
            if not foundDate:
                ind1 = line.find(dateStr1)
                if ind1!=-1:
                    ind1 += len(dateStr1)
                    dateVal = line[ind1: line.find(dateStr2, ind1)]
                    prunedContents.append("Date:"+ dateVal)
                    foundDate = True

            #C) Text
            if not foundText:
                if not startedText:
                    ind = line.find(textStr1)
                    if ind!=-1:
                        startedText = True
                else:
                    ind1 = line.find(textStr2)
                    ind2 = line.find(textStr3)
                    if ind1==-1 and ind2==-1:
                        curText += line +" -newline- "
                    else:
                        if ind1!=-1:
                            remText = line[:ind1]
                            expectMore = True
                        else:
                            remText = line[:ind2]
                            expectMore = False
                        curText += remText

                        foundText = True
                        startedText = False


            #D) Extended Text
            if expectMore and not foundMore:
                if not startedMore:
                    ind = line.find(exTextStr1)
                    if ind!=-1:
                        startedMore = True
                        line = line[ ind + len(exTextStr1) : ]

                if startedMore:
                    ind1 = line.find(exTextStr2)
                    if ind1!=-1:
                        remText = line[:ind1]
                        curText += remText
                        foundMore = True
                        startedMore = False                        
                    else:
                        curText += line +" -newline- "
                

            #Now checking exit condition
            ind = line.find(endRevStr1)
            if ind!=-1:
                insideReviewState = 0
                prunedContents.append("ReviewText:"+curText)
                prunedContents.append("EndOfReview")
    

    if not foundNext:
        prunedContents.insert(0, "Next:" )

    if not foundCity:
        prunedContents.insert(1, "Next:" )

    if not foundAddr:
        prunedContents.insert(2, "Address:" )

    return prunedContents

def pruneReviewFile(revContents, fileName, option, city):
    """Prunes the review file"""
    print "Finished downloading review page"
    if option == "tripadvisor":
        prunedRevContents = pruneTAReviewPage(revContents)
    else:
        prunedRevContents = pruneOrbitzReviewPage(revContents)
    with open(path+'/'+ fileName.replace("/","\\/"),'w') as outF:
        for line in prunedRevContents:
            outF.write(line+'\n')
    print city,"review file pruned to ", len(prunedRevContents)," lines from ", len(revContents)," lines"
    return prunedRevContents
   
def analyzeReviewPageModified(hotelid, contents, hName, option, nextpath):
    """Analyzes the review page and and gets details about them which it then writes to the output file
    
    Inputs:
    - contents : Content string
    - hName : Name of the hotel
    - option : Tripad/Orbitz
    - outF : File to write to
    
    """
    select = pq(contents)
    totalRatings = len(select(".reviewSelector"))
    # create a new url which has expanded reviews
    base = "http://www.tripadvisor.in/ExpandedUserReviews-"
    targetStr = pq(select(".reviewSelector")[0]).attr('id')
    targetId = int(targetStr[targetStr.find('_')+ 1:])
    setOfReviewIds = []
    count = 0
    while count < totalRatings:
        tStr = pq(select(".reviewSelector")[count]).attr('id')
        tId = int(tStr[tStr.find('_')+ 1:])
        setOfReviewIds.append(tId)
        count = count + 1
    targetUrl = str(hotelid) + "?target=" + str(targetId) + "&context=1&reviews=" + ','.join(str(x) for x in setOfReviewIds) + "&servlet=Hotel_Review&expand=1"
    print("target url: ", targetUrl)
    (fileContents, downloaded) = downloadToFile(base + targetUrl, targetUrl + ".html")
    outFile = open(nextpath + '/review.txt','a')
    fileContentsStr = '\n'.join(fileContents)
    mincount = 0
    while mincount < 3:
     try:
      select = pq(fileContentsStr)
      break
     except:
      print "Oops wrong file contents."
      mincount = mincount + 1
     
    totalRatings = len(select(".innerBubble"))
    count = 0
    while count < totalRatings:
        rating = pq(select(".innerBubble")[count])(".sprite-rating_s_fill").attr('alt')
        dateStr = pq(select(".innerBubble")[count])(".ratingDate").text()
        textStr = pq(select(".innerBubble")[count])(".entry").text()
#        strtowrite = (hName+'\n'+str(rating)+'\n'+textStr+'\n\n').encode('utf8')
#        outFile.write(strtowrite)
        strtowrite = (textStr+'\n\n').encode('utf8')
        outFile.write(strtowrite)
        count = count + 1
        
    outFile.flush()
    outFile.close()
    return
    
def analyzeReviewPage(contents, hName, option, outF):
    """Analyzes the review page and and gets details about them which it then writes to the output file
    
    Inputs:
    - contents : Content string
    - hName : Name of the hotel
    - option : Tripad/Orbitz
    - outF : File to write to
    
    """
    outFile = open(outF,'a')
    ratStr = "Rating:"
    dateStr = "Date:"
    textStr = "ReviewText:"
    print("content: ", contents)
    if option == "tripadvisor":
        city = getAddress(contents[0])
        fullAddr = getFullAddress(contents[0])
        i = 2
    else:
        city = contents[1][len("City:"):]
        fullAddr = contents[2][len("Address:"):]
        i = 3
    global totReviews
    
    while i < len(contents) - 5:
        if option == "tripadvisor":
            i += 2
            ratInd = contents[i].find(ratStr)
            if ratInd != -1:
                rating = contents[i][ratInd + len(ratStr):]
                i += 1
            else:
                rating = ""
            dateInd = contents[i].find(dateStr)
            if dateInd != -1:
                date = contents[i][dateInd + len(dateStr):]
                i += 1
            else:
                date = ""

            textInd = contents[i].find(textStr)
            if textInd != -1:
                text = contents[i][textInd + len(textStr):]
                i += 1
            else:
                text = ""

            i += 1
        else:
            rating = contents[i + 1][ len("Rating:"): ]
            date = contents[i + 2][ len("Date:"): ]
            text = contents[i + 3][len("ReviewText:"):]
            i += 5
            
        outFile.write(hName+'\t'+city+'\t'+date+'\t'+rating+'\t'+text+'\t'+fullAddr+'\n')
        totReviews += 1
        outFile.flush()
    outFile.close()
    return

def getTAReviewsForHotel( revUrl, city, key):
    """Function to get all reviews for a particular hotel from tripadvisor"""
    revStr = "-Reviews-"
    #hUrlInd = revUrl.find(revStr) + len(revStr)
    
    (fileContent, dwnld) = downloadToFile(baseUrl+revUrl, revUrl)
    #if dwnld:
    #    fileContent = pruneReviewFile(fileContent, revUrl, "tripadvisor", city)
    
    #setup
    #pdb.set_trace()
    fileContentStr = '\n'.join(fileContent)
    select = pq(fileContentStr)
    # title
    title = select("h1").text()
    # street address
    stAddress = select(".street-address").text()
    # locality
    locality = select(".locality").text()
    # image
    overallrating = select(".sprite-rating_cl_gry_fill").attr('alt')
    # parse all the individual reviews.
    # total number of pages
    length = len(select(".pgLinks")("a"))
    if length == 0:
       return
    try:
      totalpg = int(select(".pgLinks")("a")[1].text)
    except:
      totalpg = 1
      print "ERROR: Not able to parse number of pages: ", select(".pgLinks")("a")
    print ("total pages: ", totalpg)
    count = 0
    hotelidStr = "Hotel_Review-"
    hotelidStartIndex = revUrl.find(hotelidStr) + len(hotelidStr)
    hotelidEndIndex = revUrl.find(revStr)
    hotelid = revUrl[hotelidStartIndex:hotelidEndIndex]
    nextpath = key + '/' + hotelid
    try:
        os.mkdir(nextpath)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass 
        else:
            pass
    while count < totalpg:
        # create a url
        substr = "or" + str(count * 10) + "-"
        centerpoint = revUrl.find(revStr) + len(revStr)
        secondpoint = revUrl.find(title.split(' ')[0])
        newrevUrl = revUrl[:centerpoint] + substr + revUrl[secondpoint:]
        (fileContent, dwnld) = downloadToFile(baseUrl+newrevUrl, newrevUrl)
        analyzeReviewPageModified(hotelid, fileContentStr,  title, "tripadvisor", nextpath)
        count = count + 1
#        if count == 1:
#         break

    #Get the number of reviews for each    
    #numReviews = getNumberOfReviews(fileContent)
    #global totReviews, trueNumH
    #numAddPages = (numReviews - 1)/numReviewsPerPage

#    if numAddPages > 0:
#        for i in range(1,numAddPages + 1):
#            newUrl = revUrl[:hUrlInd] +  "or"+str(10*i)+"-"+revUrl[hUrlInd:]
#            (newFileContent, dwnld) = downloadToFile(baseUrl + newUrl,newUrl)
#            if dwnld:
#                newFileContent = pruneReviewFile(newFileContent,newUrl, "tripadvisor", city)
#            analyzeReviewPage(newFileContent,  hName, "tripadvisor", outF)
#
#    trueNumH += 1
    #print "********************Total Reviews So Far : ", totReviews," for ", trueNumH," hotels"
    return
    
def getOrbitzReviewsForHotel( revUrl,  hName, hInd, city, outF ):
    """Function to get all reviews for a particular hotel from Orbitz"""
    fileName = "hotelReviews_ind-"+str(hInd)+"_pg-1.html"
    (fileContent, dwnld) = downloadToFile(revUrl, fileName)

    if dwnld:
        fileContent = pruneReviewFile(fileContent, fileName, "orbitz", city)
    analyzeReviewPage(fileContent,  hName, "orbitz", outF)

    numPages = 1
    while len( fileContent[0][len("Next:"):] ) > 2:
        numPages += 1
        newUrl = fileContent[0][len("Next:"):]
        fileName = "hotelReviews_ind-"+str(hInd)+"_pg-"+str(numPages)+".html"
        (fileContent, dwnld) = downloadToFile(newUrl,fileName)
        if dwnld:
            fileContent = pruneReviewFile(fileContent,fileName, "orbitz", city)
        analyzeReviewPage(fileContent,  hName, "orbitz", outF)

    global totReviews,trueNumH
    trueNumH += 1
    print "********************Total Reviews So Far : ", totReviews," for ", trueNumH ," hotels"
    return

def checkIfExists(hUrl):
    """Checks to see if the current url has already been scraped from before"""  
    ind = bisect.bisect_left(allHotelsSoFar,hUrl)
    if ind < len(allHotelsSoFar) and allHotelsSoFar[ind] == hUrl:
        return True
    allHotelsSoFar.insert(ind,hUrl)
    return False

def createKey(city, state):
  return city.upper() + ":" + state.upper()
   
def getAllTAReviews(cityList, outF, path):
    """Gets all the reviews from tripadvisor"""
    missingCityF = open(path+"missingCities.txt",'w')
    outFile =  open(outF,'w')
    outFile.close()
    totHotels = 0

    for city in cityList:
        #Step 1: Issue all the cities and get the list of hotels for each
        items = city.split(',')
        state = items[1].strip()
        city = items[0].strip()
        print "1) Searching for the hotels page for ", city," in state ", state
        urlCity = city.replace(' ','+')
        urlState = state.replace(' ', '+')
        key = createKey(urlCity, urlState)
        try:
            os.mkdir(key)
        except OSError as exc:
            if os.path.isdir(path):
                pass 
            else:
                pass
        citySearchUrl = baseUrl+"Search?q="+urlCity+"%2C+"+urlState+"&sub-search=SEARCH&geo=&returnTo=__2F__"
        fileName = "citySearch_city-"+urlCity+"_state-"+state+".html"

        print("city search url: ", citySearchUrl)
        (searchContents, dwnld) = downloadToFile(citySearchUrl,fileName)
        
        #if dwnld:    #If downloaded then prune the page
            #searchContents = pruneSearchFile(searchContents, fileName, city)
        
        # 1. build url of the list of hotels. down load that url.
        # 2. from that url build url of pages of list of hotels.
        # 3. for each of the page, for each hotel in it build its url.
        searchContents = '\n'.join(searchContents)
        if dwnld:
            a = pq(searchContents)
            hotelPageListUrl = pq(a('.srGeoLinks')[0])('a').attr('href')[1:]
            print("hotel page list: ", hotelPageListUrl)
            newurl = baseUrl + hotelPageListUrl
            (nextsearchcontents,dwld) = downloadToFile(newurl, hotelPageListUrl)
            nextsearchcontents = '\n'.join(nextsearchcontents)
            a = pq(nextsearchcontents)
            numPages = int(pq(pq(a('#pager_bottom')[0])('a')[1]).text())
            count = 0
            results = []
            print ("num pages: ", numPages)
            while count < numPages:
                # construct url
                # 1. find the pattern.
                substr = re.search(r'g\d+', newurl).group()
                print("sub str: ", substr)
                print("newurl: ", newurl)
                index = newurl.find(substr) + len(substr)
                if count == 0:
                    strToBeAdded = "-"
                else:
                    strToBeAdded = "-oa" + str(count * 30)
                newnewurl = newurl[:index] + strToBeAdded + newurl[index:]
                (searchContents, dwnld) = downloadToFile(newnewurl, newnewurl[newnewurl.find(baseUrl) + len(baseUrl):])
                #searchContents = '\n'.join(searchContents)
                results = results + getCityHotelListPage(searchContents)
                count = count + 1

        if len(searchContents) == 1 and len(searchContents[0]) <2:
            missingCityF.write(city+'\n')
            missingCityF.flush()

        #Step 2: Get the list of hotels page for each
        #hotelPages = getCityHotelListPage(searchContents)
        print("Total TA Hotels: ", len(results))
        hotelURLs = results
        print("length of hotel urls: ", len(hotelURLs))
        count = 0
        while count < len(hotelURLs):
            #Step 4: Get the page for each hotel
            hUrl = hotelURLs[count]
            print("checking for url: ", count, " : ", hUrl)
            if not checkIfExists(hUrl):
                #hName = hotelNames[hind]
                #hName = "Test hotel"
                #print "5) Getting reviews for hotel", hName    #Step 5: Get the reviews for each hotel
                print("5) Getting reviews for hotel ", hUrl)
                getTAReviewsForHotel(hUrl,city, key)
            count = count + 1
#            if count >= 5:
#                break

        # Step 3: Get more such pages
        # numR = getNumberOfHotels(hlContents)
        # totHotels += numR
            
        # numAddHotelPages = numR/numHotelsPerPage
        # insertInd = getHotelListInsertIndex(page)
            
        # for nahp in range(1,numAddHotelPages + 1):
        #     print "3) Getting additional hotel names"
        #     hotelListUrl = baseUrl+page[:insertInd]+"oa"+str(numHotelsPerPage * nahp)+"-"+page[insertInd:]
        #     hlFileName = "hotelList_cit-"+urlCity+"_st-"+state+"_pg-"+str(numP)+"_respg-"+str(nahp+1)+".html"

        #     (hlContents, dwnld) = downloadToFile(hotelListUrl,hlFileName)
        #     if dwnld:    #If downloaded then prune the page
        #         hlContents = pruneHotelListFile(hlContents, hlFileName, "tripadvisor", city)
        #         if len(hlContents) < 2:
        #             continue

        #     (hotelURLs, hotelNames) = getTAHotels(hlContents)
        #     for hind in range( len( hotelURLs) ):        #Step 4: Get the page for each hotel
        #         hUrl = hotelURLs[hind][1:]
        #         if not checkIfExists(hUrl):
        #             hName = hotelNames[hind]
        #             print "5) Getting reviews for hotel", hName    #Step 5: Get the reviews for each hotel
        #             getTAReviewsForHotel(hUrl,hName,city,outF)

        print "----->Total number of hotels so far: ", totHotels

    missingCityF.close()

def getAllOrbitzReviews(cityList, outF):
    """Gets all the reviews from orbitz"""
    outFile =  open(outF,'w')
    totHotels = 0
    for city in cityList:
        #Step 1: Issue all the cities and get the list of hotels for each
        print "1) Getting the list of hotels page for ", city," in state ", state
        urlCity = city.replace(' ','+')

        hotelListUrl = baseUrl+"shop/home?type=hotel&hotel.type=keyword&hotel.rooms%5B0%5D.adlts=2&hotel.rooms%5B0%5D.chlds=0&search=Search&hotel.keyword.key="+urlCity+"%2C+"+urlState
        hlFileName = "hotelList_cit-"+urlCity+"_st-"+state+"_respg-1.html"
        (hlContents, dwnld) = downloadToFile(hotelListUrl,hlFileName)

        if dwnld:    #If downloaded then prune the page
            hlContents = pruneHotelListFile(hlContents, hlFileName, "orbitz", city)
            if len(hlContents) < 2:
                continue

        (hotelURLs, hotelNames, hotelIds) = getOrbitzHotels(hlContents)
        print("orbitz hotel urls ", len(hotelURLs), " : ", hotelURLs[0])
        if len(hotelURLs) < 1:
            missingCityF.write(city+'\n')
            missingCityF.flush()
        
        for hind in range( len( hotelURLs) ):
            if not checkIfExists(hotelIds[hind]):
                print "5) Getting reviews for hotel", hotelNames[hind]
                totHotels += 1
                getOrbitzReviewsForHotel(hotelURLs[hind],hotelNames[hind], hotelIds[hind],city,outF)

        #while a next page exists
        nahp = 1
        while len(hlContents[0]) > 1:
            nahp += 1
            hotelListUrl = hlContents[0]
            hlFileName = "hotelList_cit-"+urlCity+"_st-"+state+"_respg-"+str(nahp)+".html"

            (hlContents, dwnld) = downloadToFile(hotelListUrl,hlFileName)
            if dwnld:    #If downloaded then prune the page
                hlContents = pruneHotelListFile(hlContents, hlFileName, "orbitz", city)
                if len(hlContents) < 2:
                    continue

            (hotelURLs, hotelNames, hotelIds) = getOrbitzHotels(hlContents)
            for hind in range( len( hotelURLs) ):        
                if not checkIfExists(hotelIds[hind]):
                    print "5)Getting reviews for hotel", hotelNames[hind]
                    totHotels += 1
                    getOrbitzReviewsForHotel(hotelURLs[hind],hotelNames[hind], hotelIds[hind],city,outF)

        print "----->Total number of hotels so far: ", totHotels

    outFile.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This module scrapes review data from hotels (date, rating and review text) from Tridadvisor/Orbitz for all hotels in the given list of cities in an US state.')
    parser.add_argument('-state', type=str, default='TX', help='State for which the city data is required.', required=True)
    parser.add_argument('-cities', type=str, help='Filename containing list of cities for which data is required', required=True)
    parser.add_argument('-delay', type=int, default = 1, help='Amount of time to pause after downloading a website')
    parser.add_argument('-site', type=str, help='Either tripadvisor or orbitz', required=True)
    parser.add_argument('-o', type=str, metavar='OUTPUT', help='Path to output file for reviews', required=True)
    parser.add_argument('-path', type=str, help='Directory where the webpages should be downloaded', required=True)
    args = parser.parse_args()    #Parse the command line arguments
    argVars= vars(args)
        
    #Print out the value of all the key variables read    
    #state = argVars['state']
    #urlState = state.replace(' ','+')
    #print 'State = ', state

    cityListFile = argVars['cities']
    cityList = getCities(cityListFile)
    print 'City file = ', cityListFile

    print 'Output file = ', argVars['o']
    
    #Read in the other variables
    delayTime = argVars['delay']
    path = argVars['path']
    
    
        
    website = argVars['site']
    if website == "tripadvisor":
        baseUrl = "http://www.tripadvisor.com/"
        getAllTAReviews(cityList, argVars['o'], path)
    elif website == "orbitz":
        baseUrl = "http://www.orbitz.com/"
        getAllOrbitzReviews(cityList, argVars['o'])
