create table entries (
  id integer primary key autoincrement,
  title text not null,
  artist text not null,
  url text not null,
  created_at integer,
  genre text
);
create table tags (
  id integer primary key autoincrement,
  name text not null,
  entry_id integer,
  FOREIGN KEY(entry_id) REFERENCES entries(id)
);
