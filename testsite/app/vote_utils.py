#!/usr/bin/python

from flask import Flask
import flask_gzip
import json
import re
from functools import wraps
from collections import namedtuple
from flask import redirect, request, current_app, jsonify
import psycopg2
import psycopg2.extras
from collections import defaultdict
import os
from itertools import groupby
from shapely.ops import cascaded_union
from shapely.geometry import mapping, asShape
from shapely import speedups

def pickBestVote(votes, preferSmear=True):
  maxVote = None
  selfVotes = [v for v in votes if v['source'] == 'self']
  positiveSelfVotes = None
  if len(selfVotes) > 0:
    negativeSelfVotes = [v for v in selfVotes if v['count'] < 0]
    positiveSelfVotes = [v for v in selfVotes if v['count'] > 1]
    if negativeSelfVotes and not positiveSelfVotes:
      return None
    else:
      votes = positiveSelfVotes
  if not maxVote and len(votes) > 0:
    maxVote = max(votes, key=lambda x:x['count'])

  smearVotes = [v for v in votes if v['source'] == 'smear']
  if preferSmear and smearVotes and not positiveSelfVotes:
    return smearVotes[0]

  return maxVote


def getVotes(conn, areaid, user): 
  cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

  statefp10 = areaid[0:2]
  countyfp10 = areaid[2:]

  cur.execute("""select geoid10, ST_AsGeoJSON(ST_Transform(geom, 4326)) as geojson_geom FROM tabblock10 tb WHERE statefp10 = %s AND countyfp10 = %s AND blockce10 NOT LIKE '0%%'""", (statefp10, countyfp10))
  rows = cur.fetchall()

  cur.execute("""select woe_id, id, label, count, source, name FROM votes v JOIN geoplanet_places ON label::int = woe_id WHERE id LIKE '%s%%'""" % (areaid))

  votes = defaultdict(list)
  for r in cur.fetchall():
    votes[r['id']].append({
      'label': r['name'], 
      'id': r['woe_id'], 
      'count': r['count'], 
      'source': r['source']
    })
 
  user_votes = {}
  print 'user? %s' % user
  print user
  if user:
    userId = user['id']
    cur.execute("""select g.woe_id, blockid, name, weight FROM user_votes v JOIN geoplanet_places g ON v.woe_id = g.woe_id WHERE v.userid = %s AND v.blockid LIKE '%s%%'""" % (userId, areaid))
    for r in cur.fetchall():
      votes[r['blockid']].append({
        'label': r['name'], 
        'id': r['woe_id'], 
        'source': 'self',
        'count': r['weight']
      })

  return (rows, votes)
