#! /usr/bin/python

''' next: select locations and highlight on map; provide "edit" option which
provides five options'''

# imports

import os
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, \
    render_template, flash
from shapely.geometry import MultiPoint
from flask_googlemaps import GoogleMaps
from processing import location_process as loc
from werkzeug.utils import secure_filename
import json
from StringIO import StringIO
from math import radians, cos, sin, asin, sqrt

# create the app

app = Flask(__name__)
app.config.from_object(__name__)

UPLOAD_FOLDER = 'storage'
ALLOWED_EXTENSIONS = set(['txt','md'])
GoogleMaps(app)

# loads default config and override config from an environment variable

app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'polfr.db'),
    SECRET_KEY='800mer!!',
    USERNAME='admin',
    PASSWORD='default'
))
app.config.from_envvar('POLFR_SETTINGS',silent=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def connect_db():
    '''Connects to the specified db'''
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def get_db():
    '''opens new db connection if none, leaves open'''
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    '''closes db at end of request and removes rows'''
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

@app.cli.command('initdb')
def initdb_command():
    init_db()

@app.route('/')
def show_locations():
    click = request.args.get('click')
    locations = get_locations()
    responses = make_points(locations)
    coords = [(float(point[0]),float(point[1])) for point in responses]
    cent = centroid(coords)
    if click != None:
        for loc in responses: 
            if loc[4] == click:
                loc[3] = 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png'
                cent = centroid([(loc[0],loc[1])])
    books = get_books()
    authors = get_authors()
    ## ideally need to dedupe country_list and locations - in template?
    region_list = list(set([ location[0] for location in locations if location[7] == "A" ]))
    # This creates a list of countries relevant to the region list so that I don't get 
    # eg Florida in Uruguay when I just want Florida in the US; must also allow for country = None
    country_list =  list(set([ location[6] for location in locations if location[7] == "A" or location[7] == "L" ]))
    return render_template('show_locations.html', locations=locations, cent=cent, responses=responses, authors=authors, books=books,country_list=country_list,region_list=region_list)

def make_points(locations):
    '''formats get_locations output for use in google map'''
    points = [ [location[1],location[2],'<b>'+location[0]+'</b><br>'+'...'+location[5]+'...','http://maps.google.com/mapfiles/ms/icons/yellow-dot.png',location[0]+str(location[3]),location[7]] for location in locations ]
    return points

@app.route('/edit_location/<location_code>/')
def edit_location(location_code):
    '''need a way to enable click so that users can tell which one to select;
    maybe a function that sets a click option to yes/no'''
    db = get_db()
    location_cur = db.execute('select * from locations where location_id = ?',
                        [location_code])
    location = location_cur.fetchall()[0]
    show_all = request.args.get('showall')  
    if show_all == None or show_all == 'None':
        responses = loc.geonames_query_full_record(location[1],count=5)
        coordinates = [ [response['lat'],response['lng'],response.get('countryName','None')] for response in responses ]
    elif show_all == 'showall':
        responses = loc.geonames_query_full_record(location[1],count=0)
        coordinates = [ [response['lat'],response['lng'],response.get('countryName','None')] for response in responses ]
    responses = [ [coordinate[1][0],coordinate[1][1],str(coordinate[0]),'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png',coordinate[1][2]] for coordinate in enumerate(coordinates) ]
    cent = centroid([(float(response[0]),float(response[1])) for response in responses])
    click_code = request.args.get('click')
    if click_code != None:
        for response in responses:
            if click_code == response[2]:
                response[3] = 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png'
                cent = (response[0],response[1])
    return render_template('edit_location.html',location=location,responses=responses, cent=cent,location_code=location_code,click_code=click_code,show_all=show_all)
    
@app.route('/update_location/manual', methods=['POST'])
def update_location_manual():
    # ?id=<loc_id>&lat=<lat>&lng=<lng>
    loc_id = request.args.get('id')
    lat = request.form['latitude']
    lng = request.form['longitude']
    if request.args.get('next_id') != None:
        next_id = int(request.args.get('next_id'))
    else:
        next_id = ''
    if request.args.get('book_id') != None:
        book_id = int(request.args.get('book_id'))
    else:
        book_id = ''

    db = get_db()
    db.execute('update locations set lat = ?, lon = ?, confidence=3 where location_id = ?',
                [lat,lng,loc_id])
    db.commit()
    if next_id == '':
        return redirect(url_for('show_locations'))
    else:
        return redirect('/place_entry?book_id='+str(book_id)+'&location_id='+str(next_id))

@app.route('/update_location_manual_all', methods=['GET','POST','PUT'])
def update_location_manual_all():
    # ?id=<loc_id>&lat=<lat>&lng=<lng>
    if request.args.get('next_id') != None:
        next_id = int(request.args.get('next_id'))
    else:
        next_id = ''
    if request.args.get('book_id') != None:
        book_id = int(request.args.get('book_id'))
    else:
        book_id = ''

    loc_id = request.args.get('id')
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    country = request.args.get('country')
    fcode = request.args.get('fcode')
    db = get_db()
    location_cur = db.execute('select location from locations where location_id = ?', [loc_id])
    location = location_cur.fetchall()[0][0]
    book_id_cur = db.execute('select book_id from locations where location_id = ?', [loc_id])
    book_id = book_id_cur.fetchall()[0][0]
    db.execute('update locations set lat = ?, lon = ?, country_name = ?, fcode = ?, confidence = 3 where location = ? and book_id = ?',
                [lat,lng,country,fcode,location,int(book_id)])
    db.commit()
    if next_id == '':
        return redirect(url_for('show_locations'))
    else:
        return redirect('/place_entry?book_id='+str(book_id)+'&location_id='+str(next_id))
 
    
@app.route('/update_location/')
def update_location():
    # ?id=<loc_id>&lat=<lat>&lng=<lng>
    if request.args.get('next_id') != None:
        next_id = int(request.args.get('next_id'))
    else:
        next_id = ''
    if request.args.get('book_id') != None:
        book_id = int(request.args.get('book_id'))
    else:
        book_id = ''
    loc_id = request.args.get('id')
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    country = request.args.get('country')
    fcode = request.args.get('fcode')
    db = get_db()
    db.execute('update locations set lat = ?, lon = ?, country_name = ?, fcode = ?, confidence = 3 where location_id = ?',
                [lat,lng,country,fcode,loc_id])
    db.commit()
    if next_id == '':
        return redirect(url_for('show_locations'))
    else:
        return redirect('/place_entry?book_id='+str(book_id)+'&location_id='+str(next_id))
        

@app.route('/update_location/all', methods=['GET','POST','PUT'])
def update_location_all():
    # ?id=<loc_id>&lat=<lat>&lng=<lng>
    if request.args.get('next_id') != 'None':
        next_id = int(request.args.get('next_id'))
    else:
        next_id = ''
    if request.args.get('book_id') != 'None':
        book_id = int(request.args.get('book_id'))
    else:
        book_id = ''

    loc_id = request.args.get('id')
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    country = request.args.get('country')
    fcode = request.args.get('fcode')
    db = get_db()
    location_cur = db.execute('select location from locations where location_id = ?', [loc_id])
    location = location_cur.fetchall()[0][0]
    book_id_cur = db.execute('select book_id from locations where location_id = ?', [loc_id])
    book_id = book_id_cur.fetchall()[0][0]
    db.execute('update locations set lat = ?, lon = ?, country_name = ?, fcode = ?, confidence = 3 where location = ? and book_id = ?',
                [lat,lng,country,fcode,location,int(book_id)])
    db.commit()
    if next_id == '':
        return redirect(url_for('show_locations'))
    else:
        return redirect('/place_entry?book_id='+str(book_id)+'&location_id='+str(next_id))
     
    

def centroid(points):
    if len(points)>0:
        points = MultiPoint(points)
        cent = points.centroid
        return (cent.x,cent.y)
    else:
        cent = 'No points'
        return cent

@app.cli.command('centroid')
def centroid_command():
    my_centroid = centroid()
    
    
@app.route('/add', methods=['POST'])
def add_location():
    if not session.get('logged_in'):
        abort(401)
    db = get_db()
    db.execute('insert into locations (location, lat, lon) values (?, ?, ?)',
                [request.form['location'],request.form['lat'],request.form['lon']])
    db.commit()
    flash('new location posted')
    return redirect(url_for('show_locations'))

@app.route('/delete/<int:postID>',methods=['POST'])
def delete_location(postID):
    if not session.get('logged_in'):
        abort(401)
    if request.args.get('next_id') != None:
        next_id = int(request.args.get('next_id'))
    else:
        next_id = ''
    if request.args.get('book_id') != None:
        book_id = int(request.args.get('book_id'))
    else:
        book_id = ''
    db = get_db()
    db.execute('delete from locations where location_id=?', [postID])
    db.commit()
    flash('location was deleted')   
    if next_id == '':
        return redirect(url_for('show_locations'))
    else:
        return redirect('/place_entry?book_id='+str(book_id)+'&location_id='+str(next_id))

@app.route('/delete_all', methods=['POST'])
def delete_all():
    '''queries are book_id and location_name'''
    if not session.get('logged_in'):
        abort(401)
    if request.args.get('next_id') != None:
        next_id = int(request.args.get('next_id'))
    else:
        next_id = ''
    db = get_db()
    book_id = request.args.get('book_id')
    location_name = request.args.get('location_name')
    db.execute('delete from locations where location=? and book_id=?',
                [location_name,int(book_id)])
    db.commit()
    if next_id == '':
        return redirect(url_for('show_locations'))
    else:
        return redirect('/place_entry?book_id='+str(book_id)+'&location_id='+str(next_id))

@app.route('/delete_author', methods=['POST'])
def delete_author():
    '''queries are book_id and location_name'''
    if not session.get('logged_in'):
        abort(401)
    db = get_db()
    author_id = request.args.get('author_id')
    book_ids_cur = db.execute('select book_id from books where author_id = ?',
                [int(author_id)])
    book_ids = book_ids_cur.fetchall()
    for bid in book_ids:
        db.execute('delete from locations where book_id=?',
                [int(bid[0])])
    db.execute('delete from books where author_id=?',
                [int(author_id)])
    db.execute('delete from authors where author_id=?',
                [int(author_id)])
    db.commit()
    return redirect(url_for('show_locations'))

@app.route('/delete_book/<int:book_id>', methods=['GET','POST'])
def delete_book(book_id):
    '''queries are book_id and location_name'''
    if not session.get('logged_in'):
        abort(401)
    db = get_db()
    db.execute('delete from locations where book_id=?',
                [book_id])
    db.execute('delete from books where book_id=?',
                [book_id])
    db.commit()
    return redirect(url_for('show_locations'))


@app.cli.command('clear')
def clear_command():
    db = get_db()
    db.execute('delete from locations')
    db.execute('delete from authors')
    db.execute('delete from books')
    db.commit()

@app.route('/clear/',methods=['POST'])
def clear_table():
    ''' clears existing db table'''
    db = get_db()
    db.execute('delete from locations')
    db.execute('delete from authors')
    db.execute(' delete from books')
    db.commit()
    return redirect(url_for('show_locations'))


@app.route('/login',methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash('You were logged in')
            return redirect(url_for('show_locations'))
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('you were logged out')
    return redirect(url_for('show_locations'))

@app.route('/text_process', methods=['POST'])
def text_process():
    if not session.get('logged_in'):
        abort(401)
    ''' [index, name, lat, lon, context ]'''
    coordinates = loc.main(request.form['text'])
    add_coordinates(coordinates)
    flash('new location posted')
    return redirect(url_for('show_locations'))
    
def add_coordinates(coordinates,book_id):
    db = get_db()
    coordinates_set = list(set([tuple(x[1:]) for x in coordinates]))
    for item in coordinates_set:
        if len(coordinates)>0:
            #if isinstance(item[2],float) and isinstance(item[3],float):
            if len(item[1])>0 and len(item[2])>0 and item[1] != '0' \
                and item[2] != '0':
                db.execute('insert into locations (location, lat, lon,book_id,context,country_name,fcode) values (?, ?, ?, ?, ?, ?, ?)',
                            [item[0],float(item[1]),float(item[2]),book_id,item[3],item[4],item[5]])
    db.commit()

@app.route('/confirm_locations',methods=['GET','POST'])
def confirm_locations():
    ''' is this made obsolete by place_entry? or does it take care 
    of cycling through all of them?'''
    if not session.get('logged_in'):
        abort(401)
    book_id = int(request.args.get('book_id'))
    db = get_db()
    places_cur = db.execute('select location_id,location,confidence from locations where book_id=? order by confidence asc',
                        [book_id])
    places = [ place for place in sorted(places_cur.fetchall(),key=lambda x: x[2]) ]
    return place_entry(places[0][0],book_id)

@app.route('/place_entry',methods=['GET','POST'])
def place_entry(location_id=0,book_id=0):
    '''need a way to enable click so that users can tell which one to select;
    maybe a function that sets a click option to yes/no'''
            
    if request.args.get('book_id') != None:
        book_id = int(request.args.get('book_id'))
    db = get_db()
    all_locs_cur = db.execute('select location_id,location,confidence from locations where book_id = ? order by confidence asc',
                        [book_id])
    all_locs_full = [ x for x in sorted(all_locs_cur.fetchall(),key=lambda x: x[2]) ] # sorting , but returning only id
    all_locs = [ x[0] for x in all_locs_full ]
    
    if request.args.get('location_id') != None and request.args.get('location_id') != 'None': # support for queries or variables passed thru function
        location_id = int(request.args.get('location_id'))
    loc_index = all_locs.index(location_id)


    ## find index of next location, try to find next and previous uniques

    if loc_index != 0 and loc_index != (len(all_locs)-1):
        prev_loc = all_locs[loc_index-1]
        next_loc = all_locs[loc_index+1]
        # find index of previous unique location
        unique = False
        temp_index = loc_index - 1
        while unique is False:
            if all_locs_full[temp_index][1] != all_locs_full[loc_index][1]:
                prev_type = all_locs[temp_index]
                unique = True
            else:
                temp_index -= 1

        # find index of next unique location
        unique = False
        temp_index = loc_index + 1
        while unique is False:
            if len(all_locs_full) > temp_index + 1:
                if all_locs_full[temp_index][1] != all_locs_full[loc_index][1]:
                    next_type = all_locs[temp_index]
                    unique = True
                else:
                    temp_index += 1
            else:
                next_type = 'None'
                unique = True
            
    elif loc_index == 0:
        prev_loc = 'None'
        next_loc = all_locs[1]
        prev_type = 'None'
        # find index of next unique location
        unique = False
        temp_index = loc_index + 1
        while unique is False:
            if all_locs_full[temp_index][1] != all_locs_full[loc_index][1]:
                next_type = all_locs[temp_index]
                unique = True
            else:
                temp_index += 1

    elif loc_index == (len(all_locs)-1):
        prev_loc = all_locs[loc_index-1]
        next_loc = 'None'
        # find index of previous unique location
        unique = False
        temp_index = loc_index - 1
        while unique is False:
            if all_locs_full[temp_index][1] != all_locs_full[loc_index][1]:
                prev_type = all_locs[temp_index]
                unique = True
            else:
                temp_index -= 1
        next_type = 'None'

    # end index finder; should break this out into a function; only necessary 
    # variables appear to be all_locs and loc_index

        
    location_cur = db.execute('select * from locations where location_id = ?',
                        [location_id])
    location = location_cur.fetchall()[0]
    location_context = location[5]
    full_context_bool = request.args.get('full_context')
    if full_context_bool == 'True':
        full_context = full_context_location(location[1],book_id)
        locs_full_context = context_lookup(location[1],full_context,book_id)
        full_context_coordinates = [ [response['geometry']['location']['lat'],response['geometry']['location']['lng'],response['formatted_address']] for response in locs_full_context ]
    else:
        full_context_coordinates = []
    show_all = request.args.get('showall')  
    if show_all == None or show_all == 'None':
        responses = loc.geonames_query_full_record(location[1],count=5)
        coordinates = [ [response['lat'],response['lng'],response.get('countryName','None'),response.get('fcl','None')] for response in responses ]
        google_responses = loc.google_maps_api(location[1],count=5)
        google_coordinates = [ [response['geometry']['location']['lat'],response['geometry']['location']['lng'],response['formatted_address']] for response in google_responses ]
    elif show_all == 'showall':
        responses = loc.geonames_query_full_record(location[1],count=0)
        coordinates = [ [response['lat'],response['lng'],response.get('countryName','None'),response.get('fcl','')] for response in responses ]
        google_responses = loc.google_maps_api(location[1],count=0)
        google_coordinates = [ [response['geometry']['location']['lat'],response['geometry']['location']['lng'],response['formatted_address']] for response in google_responses ]
    responses = [ [coordinate[1][0],coordinate[1][1],str(coordinate[0]+1),'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png',coordinate[1][2],coordinate[1][3]] for coordinate in enumerate(coordinates) ]
    context_responses = context_lookup(location,location_context,book_id)
    context_coordinates = [ [response[2],response[3],response[1],'http://maps.google.com/mapfiles/ms/icons/red-dot.png',response[6]] for response in context_responses ]
    google_responses = [ [gcoordinate[1][0],gcoordinate[1][1],str(gcoordinate[0]+1),'http://maps.google.com/mapfiles/ms/icons/blue-dot.png',gcoordinate[1][2]] for gcoordinate in enumerate(google_coordinates) ]
    cent = centroid([(float(response[0]),float(response[1])) for response in responses])
    click_code = request.args.get('click')
    if click_code != None:
        for response in responses:
            if click_code == response[2]:
                response[3] = 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png'
                cent = (response[0],response[1])
    all_responses = responses+google_responses+context_coordinates
    return render_template('place_entry.html',location=location,responses=responses,cent=cent,location_code=location_id,click_code=click_code,show_all=show_all,next_loc=next_loc,prev_loc=prev_loc,next_type=next_type,prev_type=prev_type,book_id=book_id,location_id=location_id,context=location[5],google_responses=google_responses,all_responses=all_responses,context_coordinates=context_coordinates)
 

### File uploads

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.',1)[1] in ALLOWED_EXTENSIONS

#@app.route('/',methods=['GET','POST'])
def upload_file(file):
    if not session.get('logged_in'):
        abort(401)
    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('show_locations'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash('file uploaded')
        return redirect(url_for('show_locations'))
    return redirect(url_for('show_locations'))

#@app.route('/delete_item/<fname>', methods=['GET', 'POST'])
def delete_item(fname):
    if not session.get('logged_in'):
        abort(401)
    new_id = fname
    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], fname))
    return redirect(url_for('show_locations'))

@app.route('/process_file',methods=['GET', 'POST'])
def process_file(): 
    if not session.get('logged_in'):
        abort(401)
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(url_for('show_locations'))
        ## add data to db
        db = get_db()
        author_fname = request.form['first_name']
        author_lname = request.form['last_name']
        book_title = str(request.form['title'])
        checked = request.form.getlist('checked')
       
        
        ## get all auths from db, check if exists, else create
        auth_cur = db.execute('select * from authors where first_name = ? and last_name = ?',
                            [author_fname,author_lname])
        if len(auth_cur.fetchall()) == 0:
            db.execute('insert into authors (first_name, last_name) values (?, ?)',
                        [author_fname,author_lname])
        auth_cur = db.execute('select author_id from authors where first_name = ? and last_name = ?',
                            [author_fname,author_lname])
        auth_id = auth_cur.fetchall()


        db.execute('insert into books (title, author_id) values (?, ?)',
                            [book_title, auth_id[0][0]])
        db.commit()
        
        ## get new book id for locations
        
        book_id_cur = db.execute('select book_id from books where title = ? and author_id = ?',
                                [book_title, auth_id[0][0]])
        book_id = book_id_cur.fetchall()[0]
        db.commit()
    
        file = request.files['file']
        fname = file.filename
        upload_file(file)
        fpath = os.path.join(app.config['UPLOAD_FOLDER'],fname)
        coordinates = loc.main_file(fpath)
        add_coordinates(coordinates, book_id[0])
        if checked != 'checked':
            add_confidence(coordinates,book_id[0])
        delete_item(fname)
        flash('new item uploaded and processed')
    return redirect(url_for('show_locations'))
        
def get_author_books(author_id):
    db = get_db()
    book_cur = db.execute('select * from books where author_id = ?',
                            [author_id])
    all_books = book_cur.fetchall()
    return all_books

def get_authors():
    db = get_db()
    auth_cur = db.execute('select * from authors order by last_name desc')
    all_authors = auth_cur.fetchall()
    return all_authors

def get_book_locations(book_id):
    db = get_db()
    loc_cur = db.execute('select * from locations where book_id = ?',
                        [book_id])
    all_locations = loc_cur.fetchall()
    return all_locations

def get_books():
    db = get_db()
    book_cur = db.execute('select * from books order by title desc')
    all_books = book_cur.fetchall()
    return all_books

def get_locations(book_ids=[]):
    db = get_db()

    loc_cur = db.execute('select location, lat, lon, location_id, book_id, context, country_name, fcode, confidence from locations order by location asc')
    if len(book_ids) != 0:
        all_locations = [ loc for loc in loc_cur.fetchall() if loc[4] in book_ids ]
    else:
        all_locations = loc_cur.fetchall()
    return all_locations


@app.route('/author',methods=['GET', 'POST'])
def author_view():
    if not session.get('logged_in'):
        abort(401)
    db = get_db()
    author_id = int(request.args.get('author_id'))
    click = request.args.get('click')
    
    ## get all auth info from db
    auth_cur = db.execute('select * from authors where author_id = ?',
                        [author_id])
    author_info = auth_cur.fetchall()
    author_fname = author_info[0][1]
    author_lname = author_info[0][2]
   
    ## Get book info for author 
    books_cur = db.execute('select * from books where author_id = ?',
                        [author_id])
    books = books_cur.fetchall()
    
    author_book_ids = [ book[0] for book in books ]
    locations = get_locations(book_ids=author_book_ids)
    responses = make_points(locations)
    coords = [(float(point[0]),float(point[1])) for point in responses]
    cent = centroid(coords)
    if click != None:
        for loc in responses: 
            if loc[4] == click:
                loc[3] = 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png'
                cent = centroid([(loc[0],loc[1])])

    return render_template('author_view.html',locations=locations, cent=cent, responses=responses, books=books, fname=author_fname, lname=author_lname)

@app.route('/book',methods=['GET', 'POST'])
def book_view():
    if not session.get('logged_in'):
        abort(401)
    db = get_db()
    book_id = int(request.args.get('book_id'))
    click = request.args.get('click')
    
    ## get all auth info from db
    ## Get book info for author 
    books_cur = db.execute('select * from books where book_id = ?',
                        [book_id])
    books = books_cur.fetchall()[0]
    
    locations = get_locations(book_ids=[book_id])
    responses = make_points(locations)
    coords = [(float(point[0]),float(point[1])) for point in responses]
    cent = centroid(coords)
    if click != None:
        for loc in responses: 
            if loc[4] == click:
                loc[3] = 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png'
                cent = centroid([(loc[0],loc[1])])

    return render_template('book_view.html',locations=locations, cent=cent, responses=responses, books=books)



#location=location,responses=responses, cent=cent,location_code=location_id,click_code=click_code,show_all=show_all,next_loc=next_loc,prev_loc=prev_loc,next_type=next_type,prev_type=prev_type,book_id=book_id,location_id=location_id,context=location[5],fname=author_fname,lname=author_lname)


## Certainty measures

def calculate_certainty(location, book_id):
    '''based on population, feature code, and proximity to context centroid
    relative to other top-five locations, calculate the probability on a 3-pt
    scale that top five possible toponym resolutions are correct'''
    
    # compare populations of top five locations

    # compare feature codes of top five centroids; use someone else's 
    # hierarchization from the literature

    # is closest to context centroid? y/n

## Here I'm going for a context-centroid implementation


def full_context_location(location,book_id):
    '''gather context for all instances of location in book'''
    db = get_db()
    context_cur = db.execute('select context from locations where book_id = ? and location = ?',
                            [book_id,location])
    contexts_messy = context_cur.fetchall()
    contexts = [ c[0] for c in contexts_messy ]
    joined_contexts = ' '.join(contexts)
    return joined_contexts
    

def context_lookup(toponym,context,book_id):
    ''' returns the index for a list of the top five
    hits of a given toponym based on locations in its context.
    If no locations in context, returns 0'''

    # remove toponym from context and tag remainder
    db = get_db()
    toked_context = loc.text_tokenize(context)
    clean_context = [ toke for toke in toked_context if toponym != toke]
    tagged_ctxt_locs = loc.tag_locations(clean_context)
    '''if len(tagged_ctxt_locs) == 0:
        return None
    existing_locs = []
    for place in tagged_ctxt_locs:
        place_cur = db.execute('select location_id, location, lat, lon, country_name, fcode from locations where location = ? and book_id = ?',
                    [place,int(book_id)])
        if len(place_cur.fetchall()) > 0:
            place_coord = place_cur.fetchall()
            existing_locs.append(place_coord)
    taken_places = [ location for location in existing_locs ]
    remaining_places = [ location for location in tagged_ctxt_locs if location not in taken_places ]
    remainder_lookup = loc.lookup_locations_google(remaining_places,context)
    ctxt_lookup = existing_locs+remainder_lookup'''
    ctxt_lookup = loc.lookup_locations_google(tagged_ctxt_locs,context)
    return ctxt_lookup

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    km = 6367 * c
    return km

def context_centroid(toponym,book_id):
    ''' returns the index for a list of the top five
    hits of a given toponym based on locations in its context.
    If no locations in context, returns 0'''

    full_context = full_context_location(toponym,book_id)
    
    ctxt_lookup = context_lookup(toponym,full_context,book_id)
    if len(ctxt_lookup) == 0:
        return 0


    # isolate coordinates and calc centroid
    ctxt_coords = [ (float(x[2]),float(x[3])) for x in ctxt_lookup ]
    ctxt_centroid = centroid(ctxt_coords)


    # find coordinates for top five location hits in geonames
    topo_hits = loc.geonames_query_full_record(toponym,count=5)
    if len(topo_hits) > 0:
            hits_coords = [ (hit['lat'],hit['lng']) for hit in topo_hits ] #geonames_query(place)[0]
    distances = []
    for hit in hits_coords: 
        dist = haversine(float(hit[0]),float(hit[1]),float(ctxt_centroid[0]),float(ctxt_centroid[1]))
        distances.append(dist)
    print 'distances',distances
    shortest_distance = min(distances)
    print 'shortest',shortest_distance
    winner = distances.index(shortest_distance) + 1
    
    return winner

## Population comparison

def population_comparison(location):
    responses = loc.geonames_query_full_record(location,count=5)
    populations = [ r['population'] for r in responses ]
    max_pop = max(populations)
    winner = populations.index(max_pop) + 1
    return winner

## Featurecode comparison

def featurecode_comparison(location):
    responses = loc.geonames_query_full_record(location,count=5)
    if len(responses)>0:
        feature_codes = [ r['fcl'] for r in responses if 'fcl' in r.keys()]
        print feature_codes
        code_values = {'A':3,'P':2,'L':1}
        feature_values = [ code_values[f] if f in code_values.keys() else 0 for f in feature_codes ]
        max_value = max(feature_values)
        winner = feature_values.index(max_value) + 1 
        return winner
    else:
        return 0 

def all_certainty_measures(toponym,book_id):
    featurecode_measure = featurecode_comparison(toponym)
    population_measure = population_comparison(toponym)
    context_centroid_measure = context_centroid(toponym,book_id)
    # return format is (fcode,pop,context)
    return (featurecode_measure,population_measure,context_centroid_measure)

def add_confidence(coordinates,book_id):
    locations = list(set([ coord[1] for coord in coordinates]))
    db = get_db()
    for place in locations:
        score = 0
        certainties = all_certainty_measures(place,book_id)
        for cert in certainties:
            if cert == 1:
                score += 1
        db.execute('update locations set confidence=? where location=? and book_id=?',
                    [score,place,book_id])
    db.commit()

@app.route('/finish_confidence/<int:book_id>',methods=['GET', 'POST'])
def complete_incomplete_confidence(book_id):
    db = get_db()
    book_locations_cur = db.execute('select location, confidence from locations where book_id=?',
                                    [book_id])
    book_locations = book_locations_cur.fetchall()
    print "booklocs",book_locations
    unique_locs = list(set(book_locations))
    for place in unique_locs:
        print "place",place
        if place[1] is None:
            print 'check'
            score = 0
            certainties = all_certainty_measures(place[0],book_id)
            for cert in certainties:
                if cert == 1:
                    score += 1
            print place,score
            db.execute('update locations set confidence=? where location=? and book_id=?',
                        [score,place[0],book_id])
    db.commit()
    return redirect(url_for('show_locations'))
