import os
from dotenv import load_dotenv
import pymongo
from pymongo import MongoClient

load_dotenv()

CONNECTION_STRING = os.getenv('CONNECTION_STRING')

client = MongoClient(CONNECTION_STRING)

db = client['classconfig']
subject_col = db['subject']

def get_subject():
	res = subject_col.find()
	subject = {}
	for r in res:
		subject[r['_id']] = r
	return subject

def set_subject(id, field, val):
	subject_col.update_one({'_id': id}, {'$set' : {field : val}})
	return get_subject()
