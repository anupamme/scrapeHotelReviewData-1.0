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
import threading

#Set the global variables
path = ''
delayTime = 1

baseUrl = "http://www.tripadvisor.com/"
outFile = None

totReviews = 0
trueNumH = 0

allHotelsSoFar = []
response = None


class MyThread(threading.Thread):
    def run(self):
        print("{} started!".format(self.getName()) )
        searchACity(self.getName())
        "{} finished!".format(self.getName()) 

def startThreads():
    for x in range(4):
        mythread = MyThread(name = "Thread-{}".format(x + 1) )
        mythread.start()
        time.sleep(0.9)
        
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
    select = pq(content)
    total = len(select('.quality.wrap'))
    count = 0
    while count < total:
        url = pq(select('.quality.wrap')[count])('a').attr('href')
        pages.append(url[1:])
        count = count + 1
    print("Total hotel urls parsed: ", len(pages))
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
        if os.path.isdir(path):
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
        if dwnld:
            analyzeReviewPageModified(hotelid, fileContentStr,  title, "tripadvisor", nextpath)
        count = count + 1
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
        #searchACity(city)
        mythread = MyThread(name = city )
        mythread.start()

    missingCityF.close()

def searchACity(city):
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
    results = []
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
        print ("num pages: ", numPages)
        while count < numPages:
            # construct url
            # 1. find the pattern.
            substr = re.search(r'g\d+', newurl).group()
            index = newurl.find(substr) + len(substr)
            if count == 0:
                strToBeAdded = "-"
            else:
                strToBeAdded = "-oa" + str(count * 30)
            newnewurl = newurl[:index] + strToBeAdded + newurl[index:]
            (searchContents, dwnld) = downloadToFile(newnewurl, newnewurl[newnewurl.find(baseUrl) + len(baseUrl):])
            searchContents = '\n'.join(searchContents)
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
            print("5) Getting reviews for hotel ", hUrl)
            getTAReviewsForHotel(hUrl,city, key)
        count = count + 1
        if count > 10:
            break

    print "----->Total number of hotels so far: ", totHotels
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This module scrapes review data from hotels (date, rating and review text) from Tridadvisor/Orbitz for all hotels in the given list of cities in an US state.')
    parser.add_argument('-cities', type=str, help='Filename containing list of cities for which data is required', required=True)
    parser.add_argument('-delay', type=int, default = 1, help='Amount of time to pause after downloading a website')
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
    
    
        
    baseUrl = "http://www.tripadvisor.com/"
    getAllTAReviews(cityList, argVars['o'], path)