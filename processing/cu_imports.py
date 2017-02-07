# coding: utf-8
from nltk import tokenize
from nltk.tag.stanford import StanfordNERTagger
import json
import csv
import re
from time import sleep
from urllib2 import Request, urlopen, URLError
import pickle

#Note: change path/to/file to the location of your stanford directory
st = StanfordNERTagger('/path/to/file/stanford-ner-2015-04-20/classifiers/english.all.3class.distsim.crf.ser.gz','/path/to/file/stanford-ner-2015-04-20/stanford-ner.jar')




