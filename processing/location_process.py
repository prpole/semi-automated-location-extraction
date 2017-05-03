#! /usr/bin/python

# coding: utf-8
from nltk import tokenize
from nltk.tag.stanford import StanfordNERTagger
import json
import csv
import re
from time import sleep
from urllib2 import Request, urlopen, URLError, quote
import cPickle as pickle
from unidecode import unidecode

st = StanfordNERTagger('/home/prpole/venv/polfr/processing/stanford-ner-2015-04-20/classifiers/english.all.3class.distsim.crf.ser.gz','/home/prpole/venv/polfr/processing/stanford-ner-2015-04-20/stanford-ner.jar')

#Note: explain how to use the Stanford NER

def main(text):
    '''1. prep text'''
    raw = text_tokenize(text)
    tagged = tag_locations(raw)
    coordinates = lookup_locations(tagged,raw)
    # writeout = csv_writeout(coordinates,fname)
    return coordinates

def main_file(fname):
    '''1. prep text'''
    raw = read_and_toke(fname)
    tagged = tag_locations(raw)
    coordinates = lookup_locations(tagged,raw)
    # writeout = csv_writeout(coordinates,fname)
    return coordinates



def read_and_toke(fname):
    #open
    with open(fname,'r') as f:
        try:
            raw_text = f.read().decode("utf-8")
        except UnicodeDecodeError:
            near_raw_text = f.read().decode("utf-8-sig")
            raw_text = f.read().encode("utf-8")
        #raw_text = f.read().decode("utf-8", errors="replace")
        
    #toke
    toke_text = tokenize.word_tokenize(raw_text)
    return toke_text

def text_tokenize(text):
    toke_text = tokenize.word_tokenize(text)
    return toke_text

def tag_locations(tokes):
    '''use Stanford NER tagger to tag entities;
    filter locations; combine consecutive "location" words'''
    #function variables: store locations, iteration counter
    locations = []
    counter = 0

    #run stanford tagger
    tagged = st.tag(tokes)

    #group consecutive "location" words
    while counter<len(tagged):
        ##temporary storage for full location names
        full_location = []

        ##group consecutive words tagged as locations
        if tagged[counter][1] == 'LOCATION':
            ###add first word
            full_location.append(tagged[counter][0])
            
            ###continue to add consecutive words marked "location";
            ###break when you find a non-location word
            position = 1 #temporary counter for look-ahead check
            while True:
                ####see if the next word in the list is a location
                if counter+position < len(tagged)-1:
                    if tagged[counter+position][1] == 'LOCATION':
                        full_location.append(tagged[counter+position][0])
                        ####iterate to next word
                        position += 1
                    else:
                        break
                else:
                    break
            ###skip to position after multi-token location to avoid duplicates
            counter += position
            ###turn list of location tokens into space-separated string
            join_location = ' '.join(full_location)
            locations.append((counter,join_location))

        ##if the first word is not a location, pass
        else:
            counter += 1

    return locations

def geonames_query(location,count=1):
    '''queries geonames for given location name;
    bounding box variables contain default values'''
    #initial variables
    baseurl = 'http://api.geonames.org/searchJSON?' #baseurl for geonames
    username = 'prpole' #make a geonames username
    json_decode = json.JSONDecoder() #used to parse json response
    
    #use try/except to catch timeout errors
    try:
        ##combine all variables into query string
        ##line commented out includes a query with bounding-box parameters around Philadelphia
        #query_string = baseurl+'username=%s&name_equals=%s&north=%s&south=%s&east=%s&west=%s&orderby=population' % (username,location,north,south,east,west)
        query_string = baseurl+'username=%s&name_equals=%s&orderby=population&fuzzy=1' % (username,location)
        ##run query, read output, and parse json response
        response = urlopen(unidecode(query_string))
        response_string = response.read()
        parsed_response = json_decode.decode(response_string)
        #check to make sure there is a response to avoid keyerror
        if len(parsed_response['geonames']) > 0:
            if count == 1:
                first_response = parsed_response['geonames'][0]
                coordinates = [(first_response['lat'],first_response['lng'])]
            elif count > 1:
                if len(parsed_response['geonames']) >= count:
                    responses = parsed_response['geonames'][:count]
                else:
                    responses = parsed_response['geonames'][:len(parsed_response['geonames'])]
                coordinates = [ (response['lat'],response['lng']) for response in responses]
            elif count == 0:
                responses = parsed_response['geonames'][:len(parsed_response['geonames'])]
                coordinates = [ (response['lat'],response['lng']) for response in responses]
        else: 
            coordinates = [('','')]
    except URLError, e:
        coordinates = [('','')]
        pass
    
    return coordinates

def geonames_query_full_record(location,count=1):
    '''queries geonames for given location name;
    bounding box variables contain default values'''
    #initial variables
    baseurl = 'http://api.geonames.org/searchJSON?' #baseurl for geonames
    username = 'prpole' #make a geonames username
    json_decode = json.JSONDecoder() #used to parse json response
    
    #use try/except to catch timeout errors
    try:
        ##combine all variables into query string
        ##line commented out includes a query with bounding-box parameters around Philadelphia
        #query_string = baseurl+'username=%s&name_equals=%s&north=%s&south=%s&east=%s&west=%s&orderby=population' % (username,location,north,south,east,west)
        if count != 0:
            query_string = baseurl+'username=%s&q=%s&maxRows=%s' % (username,quote(location.encode('utf-8')),count)
        else:
            query_string = baseurl+'username=%s&q=%s' % (username, quote(location.encode('utf-8')))
        ##run query, read output, and parse json response
        response = urlopen(unidecode(query_string))
        response_string = response.read()
        parsed_response = json_decode.decode(response_string)
        #check to make sure there is a response to avoid keyerror
        if len(parsed_response['geonames']) > 0:
            if count == 1:
                responses = parsed_response['geonames'][0]
                coordinates = [(responses['lat'],responses['lng'])]
            elif count > 1:
                if len(parsed_response['geonames']) >= count:
                    responses = parsed_response['geonames'][:count]
                else:
                    responses = parsed_response['geonames'][:len(parsed_response['geonames'])]
                coordinates = [ (response['lat'],response['lng']) for response in responses]
            elif count == 0:
                responses = parsed_response['geonames'][:len(parsed_response['geonames'])]
                coordinates = [ (response['lat'],response['lng']) for response in responses]
        else: 
            responses = {}
            coordinates = [('','')]
    except URLError, e:
        responses = {}
        coordinates = [('','')]
        pass
    
    return responses

def resolved_unresolved(locations):
    responses = [ geonames_query_full_record(location,count=5) for location in locations ]
    results = []
    for response in responses:
        resp_formatted = [ entry['population'] for entry in response  if entry['fcl']=='P' and entry['fcode'] != 'PPLX']
        resp_formatted.sort(reverse=True)
        pop_coeff = float(resp_formatted[0])/float(resp_formatted[1])
        if pop_coeff >= 10:
            result = (response[0]['toponymName'],'resolved')
        else:
            result = (response[0]['toponymName'],'unresolved')
        results.append(result)
    return results
        

def lookup_locations(locations,raw):
    location_names = [ x[1] for x in locations ] #separate names from index
    '''given list of locations, run query for each and return dict'''
    coordinates = {} #dict to store coordinates
    all_locations = []
    unique_locs = list(set(location_names)) #only look up locations once
    #get coordinates for every unique location
    for place in unique_locs:
        place_response = geonames_query_full_record(place)
        if len(place_response) > 0:
            place_coord = (place_response['lat'],place_response['lng'],place_response.get('countryName',''),place_response.get('fcl','')) #geonames_query(place)[0]
            coordinates[place] = place_coord
    #array for each location mention: index, name, lat, lon, context
    for place in locations:
        if place[1] in coordinates.keys():
            location_position = place[0]
            location_name = place[1]
            location_lat = coordinates[location_name][0]
            location_lon = coordinates[location_name][1]
            country_name = coordinates[location_name][2]
            fcl = coordinates[location_name][3]
            context = ' '.join(raw[location_position-100:location_position+100])
            row = [location_position,location_name,location_lat,location_lon,context,country_name,fcl]
            all_locations.append(row)
        
    return all_locations

def lookup_locations_google(locations,raw):
    location_names = [ x[1] for x in locations ] #separate names from index
    '''given list of locations, run query for each and return dict'''
    coordinates = {} #dict to store coordinates
    all_locations = []
    unique_locs = list(set(location_names)) #only look up locations once
    #get coordinates for every unique location
    for place in unique_locs:
        place_response = google_maps_api(place)
        if len(place_response) > 0:
            place_coord = (place_response['geometry']['location']['lat'],place_response['geometry']['location']['lng'],place_response['formatted_address'],'')
            coordinates[place] = place_coord
    #array for each location mention: index, name, lat, lon, context
    for place in locations:
        if place[1] in coordinates.keys():
            location_position = place[0]
            location_name = place[1]
            location_lat = coordinates[location_name][0]
            location_lon = coordinates[location_name][1]
            country_name = coordinates[location_name][2]
            fcl = coordinates[location_name][3]
            context = ' '.join(raw[location_position-100:location_position+100])
            row = [location_position,location_name,location_lat,location_lon,context,country_name,fcl]
            all_locations.append(row)
        
    return all_locations



def csv_writeout(all_locations,fname):
    with open(fname[:-4]+'_locations.csv','w') as f:
        cwrite = csv.writer(f)
        cwrite.writerow(['index','name','lat','lon','context'])
        for row in all_locations:
            cwrite.writerow(row)


def google_maps_api(location,count=1):
    ## generate additional results from google maps
    api_key = 'AIzaSyAFihHQXTLksseRyvKayTX3clyx9dQ6eks'
    baseurl = 'https://maps.googleapis.com/maps/api/geocode/json?'
    query_string = baseurl+'address=%s&key=%s' % (location,api_key)
    json_decode = json.JSONDecoder() #used to parse json response
    
    try:
        response = urlopen(unidecode(query_string))
        response_string = response.read()
        parsed_response = json_decode.decode(response_string)
        #check to make sure there is a response to avoid keyerror
        if len(parsed_response['results']) > 0:
            if count == 1:
                responses = parsed_response['results'][0]
                coordinates = [(responses['geometry']['location']['lat'],responses['geometry']['location']['lng'])]
            elif count > 1:
                if len(parsed_response['results']) >= count:
                    responses = parsed_response['results'][:count]
                else:
                    responses = parsed_response['results'][:len(parsed_response['results'])]
                coordinates = [ (response['geometry']['location']['lat'],response['geometry']['location']['lng']) for response in responses]
            elif count == 0:
                responses = parsed_response['results'][:len(parsed_response['results'])]
                coordinates = [ (response['geometry']['location']['lat'],response['geometry']['location']['lng']) for response in responses]
        else: 
            responses = {}
            coordinates = [('','')]
    except URLError, e:
        responses = {}
        coordinates = [('','')]
        pass
    return responses

