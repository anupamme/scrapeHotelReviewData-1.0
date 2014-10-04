-------------------------
README File For HotelRev-Scrape
-------------------------
Karthik Raman

Version 1.0
31/08/2012

http://www.cs.cornell.edu/~karthik/projects/hotelrev-scrape/index.html


-------------------------
INTRODUCTION
-------------------------

HotelRev-Scrape is a python class for scraping review data from hotels (date, rating and review text) from Tridadvisor/Orbitz for all hotels in (and close to) the given list of cities in an US state.

It does this in 5 steps:
Step 1: Get the list of cities and the URLs listing hotels for that. (Only needed for Tripadvisor)
Step 2: Get the list of URLs for each hotel in a city.
Step 3: Get the list of review pages for each hotel.
Step 4: From each hotel get the review information needed.
Step 5: Get the stats for each hotel

It also has the ability to be interrupted and (effectively) resume from where it stopped without having to redownload all the previous files. It does this by performs optimizations such as storing the webpages it has downloaded and compacting the downloaded pages into a format that is easy to process.

Note that no Personal Information of the reviewers such as their account name or address is scraped..

-------------------------
COMPILING
-------------------------

HotelRev-Scrape can works in Windows, Linux and Mac environment.

**NOTE**
HotelRev-Scrape does require Python version 2.7 or newer in order to run properly.

You can download the latest version of Python at http://www.python.org/download/

-------------------------
INSTALLATION
-------------------------

If you want to install this module in your directory for third-party Python modules then run

python setup.py install

-------------------------
RUNNING
-------------------------

To run the function 

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

-------------------------
INPUT DATA FORMAT
-------------------------

The function takes in input via the command line as mentioned above. 
The list of file containing the cities is expected to be in the following format: Text file with each line corresponding to the name of the city.

The sample file (sample_cities.txt) is an example for the same.


-------------------------
OUTPUT DATA FORMAT
-------------------------

TSV (Tab-seperated) file containing 1 review per line. Reviews are buched as per the hotel. The format is as follows:

Format: Hotel Name	City	Date	Rating	Review-Text	Hotel-Address

Note that Review-Text has no newlines as they are instead replaced with a -newline-
-------------------------
CONTENTS
-------------------------

The source distribution includes the following files:

1. README.txt : This readme file.
2. LICENSE.txt : License under which software is released.
3. sample_cities.txt : Sample input file to indicate data format.
4. scrapeHotelReviewData.py : The python module.
5. setup.py : The setup file
6. DOCUMENTATION.html : The file containing detailed documentation of the code.

There is also a windows binary .exe file available (untested though).

-------------------------
SAMPLE USAGE
-------------------------

1. To run on tripadvisor for a list of Texas cities given in sample_cities.txt with delay 0:

python scrapeHotelReviewData.py  -state Texas -cities sample_cities.txt -delay 0 -site tripadvisor -o trip_advisor_reviews.txt -path Webpages/TA/

2. The same for orbitz instead

python scrapeHotelReviewData.py  -state Texas -cities sample_cities.txt -delay 0 -site orbitz -o orbitz_advisor_reviews.txt -path Webpages/Orbitz

-------------------------
FURTHER DOCUMENTATION
-------------------------

Please see the html file for Documentation about the different functions as well as more details.

