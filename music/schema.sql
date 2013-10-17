drop table if exists entries;
create table entries (
  id integer primary key autoincrement,
  title text not null,
  artist text not null,
  url text not null,
  created_at integer,
  genre text
);
