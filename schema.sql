drop table if exists locations;
create table locations(
    location_id integer primary key autoincrement,
    location varchar not null,
    lat float not null,
    lon float not null,
    book_id references books(book_id),
    context varchar not null,
    country_name varchar,
    fcode varchar
);

drop table if exists books;
create table books (
    book_id integer primary key autoincrement,
    title varchar not null,
    author_id references authors(author_id)
);

drop table if exists authors;
create table authors (
    author_id integer primary key autoincrement,
    first_name varchar not null,
    last_name varchar not null
);




