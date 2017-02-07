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
    print 'initialized the database'

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
    return render_template('show_locations.html', locations=locations, cent=cent, responses=responses, authors=authors, books=books)

def make_points(locations):
    '''formats get_locations output for use in google map'''
    points = [ [location[1],location[2],'<strong>'+location[0]+'</strong><br>'+'...'+location[5]+'...','http://maps.google.com/mapfiles/ms/icons/yellow-dot.png',location[0]+str(location[3])] for location in locations ]
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
    lat = request.form['lat']
    lng = request.form['lon']
    db = get_db()
    db.execute('update locations set lat = ?, lon = ? where location_id = ?',
                [lat,lng,loc_id])
    db.commit()
    return redirect(url_for('show_locations'))
 
    
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
    db = get_db()
    db.execute('update locations set lat = ?, lon = ?, country_name = ? where location_id = ?',
                [lat,lng,country,loc_id])
    db.commit()
    if next_id == '':
        return redirect(url_for('show_locations'))
    else:
        return redirect('/place_entry?book_id='+str(book_id)+'&location_id='+str(next_id))
        

@app.route('/update_location/all', methods=['GET','POST','PUT'])
def update_location_all():
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
    db = get_db()
    location_cur = db.execute('select location from locations where location_id = ?', [loc_id])
    location = location_cur.fetchall()[0][0]
    book_id_cur = db.execute('select book_id from locations where location_id = ?', [loc_id])
    book_id = book_id_cur.fetchall()[0][0]
    db.execute('update locations set lat = ?, lon = ?, country_name = ? where location = ? and book_id = ?',
                [lat,lng,country,location,int(book_id)])
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
    print my_centroid
    
    
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
        print item
        if len(coordinates)>0:
            #if isinstance(item[2],float) and isinstance(item[3],float):
            if len(item[1])>0 and len(item[2])>0 and item[1] != '0' \
                and item[2] != '0':
                db.execute('insert into locations (location, lat, lon,book_id,context,country_name) values (?, ?, ?, ?, ?, ?)',
                            [item[0],float(item[1]),float(item[2]),book_id,item[3],item[4]])
    db.commit()

@app.route('/confirm_locations',methods=['GET','POST'])
def confirm_locations():
    if not session.get('logged_in'):
        abort(401)
    book_id = int(request.args.get('book_id'))
    db = get_db()
    places_cur = db.execute('select location_id,location from locations where book_id=? order by location',
                        [book_id])
    places = [ place for place in sorted(places_cur.fetchall(),key=lambda x: x[1]) ]
    print places,'quack'
    return place_entry(places[0][0],book_id)

@app.route('/place_entry',methods=['GET','POST'])
def place_entry(location_id=0,book_id=0):
    '''need a way to enable click so that users can tell which one to select;
    maybe a function that sets a click option to yes/no'''
            
    if request.args.get('book_id') != None:
        book_id = int(request.args.get('book_id'))
    db = get_db()
    all_locs_cur = db.execute('select location_id,location from locations where book_id = ? order by location',
                        [book_id])
    all_locs_full = [ x for x in sorted(all_locs_cur.fetchall(),key=lambda x: x[1]) ] # sorting alphabetically, but returning only id
    all_locs = [ x[0] for x in all_locs_full ]
    print all_locs_full
    
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
            if all_locs_full[temp_index][1] != all_locs_full[loc_index][1]:
                next_type = all_locs[temp_index]
                unique = True
            else:
                temp_index += 1
            
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

        
    location_cur = db.execute('select * from locations where location_id = ?',
                        [location_id])
    location = location_cur.fetchall()[0]
    show_all = request.args.get('showall')  
    if show_all == None or show_all == 'None':
        responses = loc.geonames_query_full_record(location[1],count=5)
        coordinates = [ [response['lat'],response['lng'],response.get('countryName','None')] for response in responses ]
    elif show_all == 'showall':
        responses = loc.geonames_query_full_record(location[1],count=0)
        coordinates = [ [response['lat'],response['lng'],response.get('countryName','None')] for response in responses ]
    responses = [ [coordinate[1][0],coordinate[1][1],str(coordinate[0]+1),'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png',coordinate[1][2]] for coordinate in enumerate(coordinates) ]
    cent = centroid([(float(response[0]),float(response[1])) for response in responses])
    click_code = request.args.get('click')
    if click_code != None:
        for response in responses:
            if click_code == response[2]:
                response[3] = 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png'
                cent = (response[0],response[1])
    return render_template('place_entry.html',location=location,responses=responses, cent=cent,location_code=location_id,click_code=click_code,show_all=show_all,next_loc=next_loc,prev_loc=prev_loc,next_type=next_type,prev_type=prev_type,book_id=book_id,location_id=location_id,context=location[5])
 

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
        
        ## get new book id for locations
        
        book_id_cur = db.execute('select book_id from books where title = ? and author_id = ?',
                                [book_title, auth_id[0][0]])
        book_id = book_id_cur.fetchall()
        db.commit()
    
        file = request.files['file']
        fname = file.filename
        upload_file(file)
        fpath = os.path.join(app.config['UPLOAD_FOLDER'],fname)
        coordinates = loc.main_file(fpath)
        add_coordinates(coordinates, book_id[0][0])
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

def get_locations():
    db = get_db()
    loc_cur = db.execute('select location, lat, lon, location_id, book_id, context, country_name from locations order by location asc')
    all_locations = loc_cur.fetchall()
    return all_locations
