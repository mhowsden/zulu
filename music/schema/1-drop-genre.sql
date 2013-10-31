
CREATE TABLE entries_new (
  id integer primary key autoincrement,
  title text not null,
  artist text not null,
  url text not null,
  created_at integer);

INSERT INTO entries_new (title, artist, url, created_at) SELECT title, artist, url, created_at FROM entries;
DROP TABLE entries;
ALTER TABLE entries_new RENAME TO entries;
